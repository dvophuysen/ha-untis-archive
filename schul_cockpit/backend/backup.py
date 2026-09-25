"""Backup / restore of the add-on's webapp.db (admin only).

The DB runs in WAL mode, so a naive file copy can be inconsistent. We use
SQLite's online backup API after a FULL checkpoint to produce a coherent
single-file snapshot. Restore validates the uploaded file's schema before
replacing the live DB, and keeps the previous DB as a .bak so the
operation is reversible.
"""

from __future__ import annotations

import json
import os
import logging
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path

from .config import SETTINGS
from .db import webapp_conn

# Tables we expect in a valid webapp.db (subset is enough to reject a
# foreign file; we don't pin exact columns so older/newer backups still
# restore and then get migrated forward on next start).
EXPECTED_WEBAPP_TABLES = {
    "schema_meta",
    "users",
    "user_account_links",
    "tasks",
    "lesson_checkins",
    "caught_up",
    "account_settings",
}

_KEEP_BAKS = 3


LOG = logging.getLogger("schul_cockpit.backup")


def _count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def status() -> dict:
    db_path = SETTINGS.webapp_db_path
    size = db_path.stat().st_size if db_path.exists() else 0
    conn = webapp_conn()
    try:
        counts = {
            "tasks": _count(conn, "tasks"),
            "checkins": _count(conn, "lesson_checkins"),
            "caught_up": _count(conn, "caught_up"),
            "manual_exams": _count(conn, "manual_exams"),
            "exam_progress": _count(conn, "exam_progress"),
            "users": _count(conn, "users"),
            "hidden_courses": _count(conn, "hidden_courses"),
        }
    finally:
        conn.close()
    return {"db_size_bytes": size, "counts": counts}


def _snapshot_db(conn: sqlite3.Connection) -> Path:
    fd, tmp = tempfile.mkstemp(prefix="sc-snap-", suffix=".db")
    os.close(fd)
    dest = sqlite3.connect(tmp)
    try:
        # Seitenweise mit kurzen Pausen, damit Schreiber nicht minutenlang warten.
        conn.backup(dest, pages=4096, sleep=0.02)
    finally:
        dest.close()
    return Path(tmp)


def make_snapshot() -> Path:
    """Consistent copy of webapp.db (caller deletes).

    Ein FULL-Checkpoint wartete auf alle Schreiber und scheiterte im Betrieb
    mit „database is locked" (Sammellauf, Auswertungen). PASSIVE genügt: Die
    Online-Backup-API kopiert auch ohne Checkpoint einen kohärenten Stand
    und wiederholt bei zwischenzeitlichen Schreibern von sich aus."""
    src = webapp_conn()
    try:
        src.execute("PRAGMA busy_timeout = 60000")
        try:
            src.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except sqlite3.OperationalError:
            pass
        return _snapshot_db(src)
    finally:
        src.close()


def _snapshot_history() -> Path | None:
    """Consistent read-only copy of history.db (the UNTIS archive), if it
    exists. The integration owns it live; the online backup API copies it
    coherently without locking writers out."""
    hp = SETTINGS.history_db_path
    if not hp.exists():
        return None
    conn = sqlite3.connect(f"file:{hp}?mode=ro", uri=True)
    try:
        return _snapshot_db(conn)
    finally:
        conn.close()


def make_combined_zip() -> Path:
    """One archive holding BOTH databases + a manifest. They are
    interdependent (webapp.db references history.db ids), so we capture
    them together at one point in time."""
    web = make_snapshot()
    hist = _snapshot_history()
    st = status()
    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "contains": ["webapp.db"] + (["history.db"] if hist else []),
        "webapp_counts": st["counts"],
        "note": (
            "Restore: webapp.db kann das Add-on direkt zurückspielen. "
            "history.db bitte über HA-Backup-Restore wiederherstellen "
            "(die UNTIS-Integration hält sie im Betrieb geöffnet)."
        ),
    }
    fd, zpath = tempfile.mkstemp(prefix="sc-backup-", suffix=".zip")
    os.close(fd)
    try:
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(web, "webapp.db")
            if hist:
                zf.write(hist, "history.db")
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    finally:
        web.unlink(missing_ok=True)
        if hist:
            hist.unlink(missing_ok=True)
    return Path(zpath)


def validate_db_file(path: Path) -> tuple[bool, str]:
    """Check the uploaded file is a SQLite DB with our expected tables and
    passes SQLite's integrity check."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return False, f"Keine gültige Datenbank: {exc}"
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        tables = {r[0] for r in rows}
        missing = EXPECTED_WEBAPP_TABLES - tables
        if missing:
            return False, f"Backup passt nicht (fehlende Tabellen: {sorted(missing)})"
        check = conn.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            return False, f"Backup ist beschädigt: {check[0] if check else 'keine Antwort'}"
    except sqlite3.DatabaseError as exc:
        return False, f"Datei ist keine SQLite-Datenbank: {exc}"
    finally:
        conn.close()
    return True, "ok"


def pending_path() -> Path:
    """Hier wartet ein geprüftes Backup auf den nächsten Start."""
    db_path = SETTINGS.webapp_db_path
    return db_path.with_name(db_path.name + ".restore-pending")


def _copy_into(src_file, target: Path) -> None:
    """Datei neben die Datenbank schreiben und atomar umbenennen. Ein
    ``os.replace`` aus /tmp scheitert, wenn /data ein anderes Dateisystem ist."""
    part = target.with_name(target.name + ".part")
    try:
        with open(part, "wb") as dst:
            while chunk := src_file.read(1 << 20):
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)


def stage_restore(uploaded: Path) -> dict:
    """Prüft ein hochgeladenes Backup (rohe .db oder die webapp.db im
    kombinierten .zip) und legt es als ``webapp.db.restore-pending`` ab.
    Getauscht wird beim nächsten Start, bevor die Datenbank geöffnet ist
    (apply_pending_restore). Bis 1.31 wurde die Datei im laufenden Betrieb
    ersetzt, während offene Verbindungen weiter die alte Datei beschrieben.
    history.db is NOT restored here (the integration owns it live)."""
    pending = pending_path()
    candidate = pending.with_name(pending.name + ".check")
    try:
        had_history = False
        if zipfile.is_zipfile(uploaded):
            with zipfile.ZipFile(uploaded) as zf:
                names = zf.namelist()
                if "webapp.db" not in names:
                    raise ValueError("ZIP enthält keine webapp.db")
                had_history = "history.db" in names
                with zf.open("webapp.db") as src:
                    _copy_into(src, candidate)
        else:
            with open(uploaded, "rb") as src:
                _copy_into(src, candidate)
        ok, msg = validate_db_file(candidate)
        if not ok:
            raise ValueError(msg)
        os.replace(candidate, pending)
    finally:
        candidate.unlink(missing_ok=True)
    return {
        "pending": pending.name,
        "history_db_in_archive": had_history,
        "history_restore_hint": (
            "Das Archiv enthielt auch history.db. Diese wird hier NICHT "
            "wiederhergestellt — bitte über ein HA-Backup-Restore einspielen."
            if had_history else None
        ),
    }


def apply_pending_restore() -> str | None:
    """Beim Start, vor dem ersten Öffnen: ein abgelegtes Backup einsetzen.
    Der bisherige Stand bleibt als ``webapp.db.bak-…`` (über die Backup-API,
    also samt WAL). Scheitert etwas, gilt der bisherige Stand weiter; ein
    unbrauchbares Backup wird beiseitegelegt, damit nicht jeder Start es neu
    versucht. Gibt den Namen der Sicherungskopie zurück."""
    pending = pending_path()
    if not pending.exists():
        return None
    db_path = SETTINGS.webapp_db_path
    data_dir = db_path.parent
    ts = time.strftime("%Y%m%d-%H%M%S")
    try:
        ok, msg = validate_db_file(pending)
        if not ok:
            LOG.error("Abgelegtes Backup nicht eingespielt: %s", msg)
            os.replace(pending, pending.with_name(f"{pending.name}.rejected-{ts}"))
            return None
        bak = data_dir / f"webapp.db.bak-{ts}"
        if db_path.exists():
            src = sqlite3.connect(db_path)
            try:
                dst = sqlite3.connect(bak)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
                try:
                    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.Error:
                    pass
            finally:
                src.close()
        # Alte WAL-/SHM-Dateien dürfen nie auf die neue Datei angewandt werden.
        for suffix in ("-wal", "-shm"):
            Path(str(db_path) + suffix).unlink(missing_ok=True)
        os.replace(pending, db_path)
        _prune_baks(data_dir)
        LOG.warning("Backup eingespielt; der vorherige Stand liegt als %s", bak.name)
        return bak.name
    except Exception:
        LOG.exception("Backup nicht eingespielt; es gilt der bisherige Stand")
        return None


def _prune_baks(data_dir: Path) -> None:
    baks = sorted(data_dir.glob("webapp.db.bak-*"), reverse=True)
    for old in baks[_KEEP_BAKS:]:
        try:
            old.unlink()
        except OSError:
            pass


# --- Nächtliche Sicherung über den Supervisor -----------------------------------
# Die automatischen HA-Backups sichern nur die dort ausgewählten Add-ons; am
# 16.09. enthielten sie das Schul-Cockpit nicht, nur ein Hand-Backup vom 14.09.
# Deshalb sichert sich das Add-on selbst: jede Nacht ein Teil-Backup nur von
# sich, die letzten sieben bleiben. Sichtbar in HA unter Einstellungen →
# System → Sicherungen, wiederherstellbar wie jedes andere Backup.

OWN_PREFIX = "Schul-Cockpit"
KEEP_OWN = 7
NIGHT_FROM, NIGHT_TO = 3, 6


def own_backups(backups: list[dict], slug: str) -> list[dict]:
    """Die Backups, die dieses Add-on enthalten, neueste zuerst."""
    found = []
    for b in backups or []:
        addons = (b.get("content") or {}).get("addons") or []
        names = [a.get("slug") if isinstance(a, dict) else a for a in addons]
        if slug in names:
            found.append(b)
    return sorted(found, key=lambda b: b.get("date") or "", reverse=True)


def to_prune(backups: list[dict], slug: str, keep: int = KEEP_OWN) -> list[dict]:
    """Eigene Nachtsicherungen jenseits der letzten `keep`; Hand-Backups und
    HA-Backups mit weiteren Add-ons bleiben unangetastet."""
    import re
    nightly = re.compile(r"^" + re.escape(OWN_PREFIX) + r" \S+ \d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
    mine = [b for b in own_backups(backups, slug)
            if nightly.match(str(b.get("name") or ""))
            and len((b.get("content") or {}).get("addons") or []) == 1
            and not (b.get("content") or {}).get("homeassistant")]
    return mine[keep:]


def backup_state(backups: list[dict], slug: str) -> dict:
    mine = own_backups(backups, slug)
    dates = [b.get("date") for b in backups or [] if b.get("date")]
    return {
        "last_ha_backup": max(dates) if dates else None,
        "last_addon_backup": mine[0].get("date") if mine else None,
        "last_addon_backup_name": mine[0].get("name") if mine else None,
        "addon_backups": len(mine),
        "nightly": {"from": NIGHT_FROM, "to": NIGHT_TO, "keep": KEEP_OWN},
    }


async def backup_now(reason: str = "nightly") -> dict:
    """Ein Teil-Backup dieses Add-ons anlegen und alte eigene aufräumen."""
    from .supervisor_client import get_supervisor
    sup = get_supervisor()
    if not sup.available:
        raise RuntimeError("Supervisor nicht erreichbar")
    info = await sup.self_info()
    slug, version = info.get("slug"), info.get("version")
    if not slug:
        raise RuntimeError("Add-on-Slug unbekannt")
    stamp = time.strftime("%Y-%m-%d %H:%M")
    name = f"{OWN_PREFIX} {version} {stamp}"
    result = await sup.create_partial_backup(name, [slug])
    pruned = []
    try:
        listing = await sup.list_backups()
        for old in to_prune(listing.get("backups", []) or [], slug):
            await sup.delete_backup(old["slug"])
            pruned.append(old.get("name"))
    except Exception:
        LOG.warning("Alte Sicherungen nicht aufgeräumt", exc_info=True)
    LOG.info("Sicherung %s angelegt (%s), %s alte entfernt", name, reason, len(pruned))
    return {"name": name, "slug": result.get("slug"), "pruned": pruned}


async def nightly_backup_loop() -> None:
    """Zwischen drei und sechs Uhr einmal sichern, wenn die letzte eigene
    Sicherung älter als zwanzig Stunden ist. Prüft alle dreißig Minuten."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    from .supervisor_client import get_supervisor
    await asyncio.sleep(120)
    while True:
        try:
            hour = datetime.now(ZoneInfo("Europe/Berlin")).hour
            sup = get_supervisor()
            if NIGHT_FROM <= hour < NIGHT_TO and sup.available:
                info = await sup.self_info()
                listing = await sup.list_backups()
                state = backup_state(listing.get("backups", []) or [], info.get("slug") or "")
                last = state["last_addon_backup"]
                fresh = False
                if last:
                    try:
                        when = datetime.fromisoformat(last.replace("Z", "+00:00"))
                        fresh = datetime.now(timezone.utc) - when < timedelta(hours=20)
                    except ValueError:
                        fresh = False
                if not fresh:
                    await backup_now("nightly")
        except Exception:
            LOG.warning("Nächtliche Sicherung nicht möglich", exc_info=True)
        await asyncio.sleep(1800)
