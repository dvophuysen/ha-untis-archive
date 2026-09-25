"""Bidirectional sync between HA todo lists and the app's tasks table.

The Untis→HA-ToDo automation runs in HA and is untouched. We sync:
  - Ingress: new HA todo items → INSERT rows into `tasks` (source='ha_todo')
  - Mark-done from HA → UPDATE tasks status to 'done'
  - Mark-done in app → push update_item(status='completed') to HA

Dedup key from HA-side is the item's `uid`. Conflict resolution is
last-write-wins via timestamps.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
from datetime import datetime, timezone

from .db import webapp_conn
from .supervisor_client import SupervisorClient, SupervisorError, get_supervisor

_LOGGER = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 120

# Untis-Tag im Notes-Feld, z.B. [MA260611] = Mathe, gegeben am 11.06.26.
# Die HA-Automation schreibt diesen Tag in JEDE Variante derselben Aufgabe
# (gleicher Code, egal wie oft sie neue UIDs vergibt). Der Tag allein ist
# aber NICHT eindeutig: er codiert nur Fach + Vergabedatum. Gibt eine
# Lehrkraft am selben Tag zwei Aufgaben im selben Fach auf, tragen beide
# denselben Tag — deshalb geht der normalisierte Aufgabentext mit in den
# Dedup-Schlüssel. Fälligkeits-Verschiebungen (der häufige Untis-Edit)
# ändern den Schlüssel weiterhin nicht; nur ein editierter Aufgabentext
# lässt den Eintrag als neue offene Aufgabe wieder auftauchen (fail-open —
# lieber ein Duplikat als eine verschluckte echte Hausaufgabe).
#
# Der Schlüssel kommt aus `tasks.ha_description`, der Beschreibung, wie HA
# sie zuletzt geliefert hat. Bis 1.31 kam er aus `notes`; die kann der
# Nutzer bearbeiten, und nach einer Notiz plus neuer HA-UID wurde eine offene
# Aufgabe samt Unterpunkten gelöscht oder eine erledigte kam offen zurück.
_UNTIS_ID_RE = re.compile(r"\[([A-Za-zÄÖÜäöüß]{1,5}\d+)\]")


def _dedup_key(notes: str | None) -> str | None:
    """Kanonischer Dedup-Schlüssel: Untis-Tag + normalisierter Resttext."""
    if not notes:
        return None
    m = _UNTIS_ID_RE.search(notes)
    if not m:
        return None
    tag = m.group(1).upper()
    text = _UNTIS_ID_RE.sub(" ", notes)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return f"{tag}|{text}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_due(due: str | None) -> tuple[str | None, str | None]:
    """HA todo `due` can be a date (YYYY-MM-DD) or a datetime. Return
    (date, time) where time is HH:MM or None for all-day items."""
    if not due:
        return None, None
    due = str(due)
    if "T" in due:
        date_part, _, time_part = due.partition("T")
        return date_part or None, time_part[:5] if time_part else None
    if " " in due:
        date_part, _, time_part = due.partition(" ")
        return date_part or None, time_part[:5] if time_part else None
    return due, None


def _get_account_lists(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    return [
        (r["account_id"], r["ha_entity_id"])
        for r in conn.execute(
            "SELECT account_id, ha_entity_id FROM account_todo_lists"
        ).fetchall()
    ]


def _empty_stats() -> dict[str, int]:
    return {
        "inserted": 0,
        "orphans_deleted": 0,
        "duplicates_collapsed": 0,
        "rebound_to_done": 0,
    }


def _close_timers(conn: sqlite3.Connection, task_id: int, now: str) -> None:
    """Laufende Zeitmessungen einer Aufgabe beenden, die in HA erledigt wurde.
    Dieselbe Rechnung wie beim Stoppen in der App (routers/tasks.timer_stop)."""
    ended = datetime.fromisoformat(now)
    for r in conn.execute(
        "SELECT id, started_at FROM task_time_log WHERE task_id = ? AND ended_at IS NULL",
        (task_id,),
    ).fetchall():
        try:
            minutes = max(0, int((ended - datetime.fromisoformat(r["started_at"])).total_seconds() // 60))
        except (TypeError, ValueError):
            minutes = 0
        conn.execute(
            "UPDATE task_time_log SET ended_at = ?, minutes = ? WHERE id = ?",
            (now, minutes, r["id"]),
        )


def _apply_items(
    conn: sqlite3.Connection, account_id: int, ha_items: list[dict], now: str
) -> tuple[dict[str, int], list[str]]:
    """Die HA-Liste in die Tabelle übernehmen. Nur Datenbank, kein Netz, damit
    die Runde in einer Transaktion läuft. Gibt die Statistik und die UIDs
    zurück, die danach in HA noch abgehakt werden müssen."""
    stats = _empty_stats()
    to_push: list[str] = []
    existing = {
        r["ha_uid"]: dict(r)
        for r in conn.execute(
            "SELECT id, ha_uid, status, updated_at, completed_at, title, "
            "due_date, due_time, notes, ha_description "
            "FROM tasks WHERE account_id = ? AND ha_uid IS NOT NULL",
            (account_id,),
        ).fetchall()
    }

    ha_seen_uids: set[str] = set()
    # Alle UIDs, die HA in dieser Runde liefert: Eine Reihe, deren UID darunter
    # ist, gehört zu ihrem Eintrag und wird nicht auf einen anderen umgebunden.
    ha_uids = {item.get("uid") or item.get("summary") for item in ha_items} - {None, ""}

    # Index existierender Reihen nach Dedup-Schlüssel (Untis-Tag +
    # Aufgabentext) — wenn HA für dieselbe Aufgabe eine neue UID
    # schickt, finden wir die alte Reihe darüber und re-binden sie,
    # statt eine zweite Reihe anzulegen. Done-Status gewinnt: eine
    # abgehakte Reihe darf nicht durch neue UID-Lieferung wieder auf
    # "offen" springen.
    by_untis: dict[str, list[dict]] = {}
    for r in existing.values():
        key = _dedup_key(r.get("ha_description"))
        if key:
            by_untis.setdefault(key, []).append(r)

    for item in ha_items:
        uid = item.get("uid") or item.get("summary")
        if not uid:
            continue
        ha_seen_uids.add(uid)
        ha_status = item.get("status", "needs_action")
        ha_summary = item.get("summary") or ""
        ha_description = item.get("description") or None
        ha_due_date, ha_due_time = _split_due(item.get("due"))

        new_status = "done" if ha_status == "completed" else "open"

        row = existing.get(uid)
        if row is None:
            # Vor dem Insert: gibt's schon eine Reihe mit demselben
            # Dedup-Schlüssel (Untis-Tag + Aufgabentext)? Dann ist das
            # dieselbe Aufgabe mit neuer HA-UID. Re-binden, Status
            # beibehalten (done bleibt done), kein neues Aktiv-Duplikat
            # erzeugen. Infrage kommen nur Reihen, deren UID HA nicht mehr
            # liefert: Führt HA denselben Eintrag doppelt, bleibt die Reihe
            # an ihrer UID, statt jede Runde hin und her zu springen.
            tag = _dedup_key(ha_description)
            candidates = (by_untis.get(tag) or []) if tag else []
            if candidates:
                orphaned = [r for r in candidates if r["ha_uid"] not in ha_uids]
                if not orphaned:
                    # Doppelter HA-Eintrag; eine Reihe steht schon für ihn.
                    continue
                done = [r for r in orphaned if r["status"] == "done"]
                pool = done if done else orphaned
                target = max(pool, key=lambda r: r["updated_at"] or "")
                old_uid = target["ha_uid"]
                conn.execute(
                    "UPDATE tasks SET ha_uid = ?, ha_description = ?, ha_last_synced_at = ? "
                    "WHERE id = ?",
                    (uid, ha_description, now, target["id"]),
                )
                existing.pop(old_uid, None)
                target["ha_uid"] = uid
                existing[uid] = target
                stats["rebound_to_done"] += 1
                continue
            cur = conn.execute(
                "INSERT INTO tasks "
                "(account_id, ha_uid, title, task_type, status, due_date, "
                " due_time, notes, ha_description, source, created_at, updated_at, "
                " completed_at, ha_last_synced_at) "
                "VALUES (?, ?, ?, 'homework', ?, ?, ?, ?, ?, 'ha_todo', ?, ?, ?, ?)",
                (
                    account_id,
                    uid,
                    ha_summary,
                    new_status,
                    ha_due_date,
                    ha_due_time,
                    ha_description,
                    ha_description,
                    now,
                    now,
                    now if new_status == "done" else None,
                    now,
                ),
            )
            stats["inserted"] += 1
            if tag:
                # Ein zweiter gleicher Eintrag derselben Liste legt dann
                # nichts nach (siehe oben).
                by_untis.setdefault(tag, []).append(
                    {"id": cur.lastrowid, "ha_uid": uid, "status": new_status, "updated_at": now}
                )
            continue

        updates: list[tuple[str, str | None]] = []
        if row["status"] != new_status:
            # Conflict resolution:
            #   App=done, HA=needs_action → App wins. The user just
            #     ticked it off here; HA may still report the old state
            #     for a moment due to the eventual-consistency lag.
            #     We push 'completed' to HA below instead of reverting
            #     the local state.
            #   App nicht erledigt (open, in_progress mit laufender Uhr,
            #     skipped), HA=completed → HA wins. The item was ticked
            #     off externally (HA UI, another device, automation), so
            #     we mirror that into the app. Bis 1.31 galt das nur für
            #     'open'; mit laufender Uhr blieb die Aufgabe offen.
            if row["status"] != "done" and new_status == "done":
                updates.append(("status", "done"))
                updates.append(("completed_at", now))
                if row["status"] == "in_progress":
                    _close_timers(conn, row["id"], now)
            elif row["status"] == "done" and new_status == "open":
                to_push.append(uid)

        # Untis owns title + due date: keep them authoritative on every
        # sync (the app cannot override them). Notes/description fill in
        # only when still empty so a user's own note is never clobbered.
        if (row.get("title") or "") != ha_summary and ha_summary:
            updates.append(("title", ha_summary))
        if (row.get("due_date") or None) != ha_due_date:
            updates.append(("due_date", ha_due_date))
        if (row.get("due_time") or None) != ha_due_time:
            updates.append(("due_time", ha_due_time))
        if ha_description and not (row.get("notes") or ""):
            updates.append(("notes", ha_description))

        # Der Dedup-Schlüssel folgt immer HA, ohne updated_at anzufassen
        # (updated_at entscheidet unten, welche Reihe einer Gruppe bleibt).
        if updates:
            set_clause = (", ".join(f"{c} = ?" for c, _ in updates)
                          + ", updated_at = ?, ha_last_synced_at = ?, ha_description = ?")
            params = [v for _, v in updates] + [now, now, ha_description, row["id"]]
            conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?",
                params,
            )
        else:
            conn.execute(
                "UPDATE tasks SET ha_last_synced_at = ?, ha_description = ? WHERE id = ?",
                (now, ha_description, row["id"]),
            )

    for uid, row in existing.items():
        if uid in ha_seen_uids:
            continue
        if row["status"] == "done":
            # Erledigte Reihe, deren UID nicht mehr in HA existiert:
            # nichts pushen. Früher wurde hier per TITEL "completed"
            # nachgeschoben — der Titel ist aber nur der Fachname und
            # traf damit regelmäßig eine ANDERE, aktuelle Hausaufgabe
            # desselben Fachs in der HA-Liste. Hat die Automation die
            # Aufgabe mit neuer UID neu angelegt, greift der
            # Rebind-Pfad oben und der Done-Status wird beim nächsten
            # Lauf regulär per UID gepusht. Ist das Item in HA wirklich
            # gelöscht, gibt es nichts mehr abzuhaken.
            pass
        else:
            # Offene ha_todo-Zeile, die nicht mehr in HA steht → die
            # Quelle der Wahrheit hat sie entfernt (oder die Automation
            # hat eine neue UID für denselben Eintrag erzeugt). Weg
            # damit, sonst sammelt sich Müll an.
            conn.execute("DELETE FROM tasks WHERE id = ?", (row["id"],))
            stats["orphans_deleted"] += 1

    # Dedup (Cross-Status): alle ha_todo-Reihen mit demselben
    # Dedup-Schlüssel (Untis-Tag + Aufgabentext) gehören zusammen,
    # egal wie oft die HA-Automation neue UIDs vergeben hat. Done
    # schlägt offen — eine abgehakte Aufgabe darf nicht durch neue
    # UID-Lieferungen wieder als aktiv auftauchen. Der Tag allein
    # reicht als Schlüssel NICHT: zwei echte Hausaufgaben desselben
    # Fachs am selben Tag tragen denselben Tag und wurden früher
    # fälschlich auf eine Reihe kollabiert.
    all_rows = conn.execute(
        "SELECT id, ha_uid, status, ha_description, updated_at FROM tasks "
        "WHERE account_id = ? AND ha_uid IS NOT NULL",
        (account_id,),
    ).fetchall()
    groups: dict[str, list[sqlite3.Row]] = {}
    for r in all_rows:
        key = _dedup_key(r["ha_description"])
        if key:
            groups.setdefault(key, []).append(r)

    for tag, group in groups.items():
        if len(group) <= 1:
            continue
        done_rows = [r for r in group if r["status"] == "done"]
        pool = done_rows if done_rows else group
        keeper = max(pool, key=lambda r: r["updated_at"] or "")
        # Vor dem Rebind die anderen Reihen löschen — sonst kollidiert
        # die UNIQUE(account_id, ha_uid)-Constraint, weil die UID, die
        # wir dem Keeper geben wollen, noch in einer anderen Reihe der
        # Gruppe steckt.
        new_uid = None
        if keeper["ha_uid"] not in ha_seen_uids:
            new_uid = next(
                (
                    r["ha_uid"] for r in group
                    if r["id"] != keeper["id"] and r["ha_uid"] in ha_seen_uids
                ),
                None,
            )
        for r in group:
            if r["id"] == keeper["id"]:
                continue
            conn.execute("DELETE FROM tasks WHERE id = ?", (r["id"],))
            stats["duplicates_collapsed"] += 1
        if new_uid:
            conn.execute(
                "UPDATE tasks SET ha_uid = ?, ha_last_synced_at = ? "
                "WHERE id = ?",
                (new_uid, now, keeper["id"]),
            )
    return stats, to_push


async def _sync_one(
    account_id: int, entity_id: str, sup: SupervisorClient
) -> dict[str, int]:
    """Sync one account's HA todo list into the app. Returns a small stats
    dict so the manual sync endpoint can give UI feedback (`inserted`,
    `orphans_deleted`, `duplicates_collapsed`)."""
    try:
        ha_items = await sup.get_todo_items(entity_id)
    except SupervisorError as exc:
        _LOGGER.warning("todo.get_items %s failed: %s", entity_id, exc)
        return _empty_stats()

    now = _now()
    conn = webapp_conn()
    try:
        if not ha_items:
            # Leere Liste, obwohl hier offene HA-Aufgaben stehen: eher eine
            # halb geladene Liste als ein Kind ohne jede Hausaufgabe. Nichts
            # löschen; der nächste Abgleich mit Inhalt räumt regulär auf.
            open_local = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE account_id = ? AND ha_uid IS NOT NULL "
                "AND status != 'done'",
                (account_id,),
            ).fetchone()[0]
            if open_local:
                _LOGGER.warning(
                    "sync %s: HA liefert eine leere Liste, %d offene Aufgaben bleiben; Runde übersprungen",
                    entity_id, open_local,
                )
                return _empty_stats()
        # Eine Runde ist eine Einheit: Bricht sie ab, bleibt der alte Stand
        # ganz, statt halb umgebundener oder gelöschter Reihen.
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            stats, to_push = _apply_items(conn, account_id, ha_items, now)
    finally:
        conn.close()

    for uid in to_push:
        # WICHTIG: per UID adressieren, nie per Titel. Der Titel
        # ist bei Untis-Aufgaben nur der Fachname ("Mathematik")
        # und damit mehrdeutig — HA nimmt beim Titel-Match das
        # ERSTE Item mit diesem Summary und hakt sonst eine ganz
        # andere (aktuelle!) Hausaufgabe ab.
        try:
            await sup.update_todo_item(
                entity_id,
                uid,
                status="completed",
            )
        except SupervisorError as exc:
            _LOGGER.warning(
                "todo.update_item %s for %s failed: %s",
                entity_id, uid, exc,
            )

    if (
        stats["duplicates_collapsed"]
        or stats["orphans_deleted"]
        or stats["rebound_to_done"]
    ):
        _LOGGER.info(
            "sync %s: +%d inserted, %d orphans, %d dup, %d done-rebinds",
            entity_id,
            stats["inserted"],
            stats["orphans_deleted"],
            stats["duplicates_collapsed"],
            stats["rebound_to_done"],
        )
    return stats


async def sync_account(account_id: int) -> dict[str, int]:
    """Trigger one sync round for a single account; returns stats so the
    manual-sync endpoint can give the UI feedback (`inserted`,
    `orphans_deleted`, `duplicates_collapsed`)."""
    empty = _empty_stats()
    sup = get_supervisor()
    if not sup.available:
        return empty
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT ha_entity_id FROM account_todo_lists WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return empty
    return await _sync_one(account_id, row["ha_entity_id"], sup)


async def reopen_in_ha(account_id: int, uid: str) -> bool:
    """Eine in der App wieder geöffnete Aufgabe auch in der HA-Liste wieder
    öffnen, per UID. Sonst sieht der nächste Abgleich „in HA erledigt, in der
    App offen“, lässt HA gewinnen, und die Aufgabe ist sofort wieder
    erledigt (bis 1.13.24 ließ sich eine Untis-Aufgabe so nie wieder öffnen)."""
    sup = get_supervisor()
    if not sup.available:
        return False
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT ha_entity_id FROM account_todo_lists WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return False
    try:
        await sup.update_todo_item(row["ha_entity_id"], uid, status="needs_action")
    except SupervisorError as exc:
        _LOGGER.warning("todo.update_item (wieder öffnen) %s für %s: %s", row["ha_entity_id"], uid, exc)
        return False
    return True


async def sync_all() -> None:
    sup = get_supervisor()
    if not sup.available:
        return
    conn = webapp_conn()
    try:
        pairs = _get_account_lists(conn)
    finally:
        conn.close()
    for account_id, entity_id in pairs:
        # Ein Konto, das scheitert, hält die anderen nicht auf.
        try:
            stats = await _sync_one(account_id, entity_id, sup)
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("HA-todo sync für %s fehlgeschlagen", entity_id)
            continue
        if (stats or {}).get("inserted"):
            # Neue Aufgaben nennen oft neue Stellen: gleich nachholen, nicht erst um 14 Uhr.
            from . import triggers
            triggers.request(account_id, "neue Aufgaben")


async def background_sync_loop() -> None:
    # Ein Abbruch beim Herunterfahren muss durchgehen; bis 1.13.10 schluckte
    # ein suppress(CancelledError) ihn, die Schleife lief weiter und HA musste
    # den Container hart beenden.
    while True:
        try:
            await sync_all()
        except Exception:
            _LOGGER.exception("Background HA-todo sync failed")
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
