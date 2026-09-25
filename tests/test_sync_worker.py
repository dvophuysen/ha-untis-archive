"""Regression tests for the HA-ToDo → App sync (Schul-Cockpit).

Covers the two bugs that made current homework disappear from both the
HA todo list and the app:

1. ``todo.update_item`` was addressed by TITLE. Untis todo items all
   carry the bare subject name as title ("Mathematik"), so pushing a
   done-state completed the FIRST matching item in HA — regularly a
   different, current homework of the same subject.
2. The dedup key was the Untis tag alone (``[MA260901]`` = subject +
   assigned date). Two real homeworks of the same subject assigned on
   the same day share that tag and were collapsed into one row / rebound
   onto a done row.

Run with::

    pytest tests/test_sync_worker.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make `backend` importable and point its webapp.db at a throwaway dir —
# must happen before the backend imports below (SETTINGS is read at
# import time).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "schul_cockpit"))
os.environ.setdefault("WEBAPP_DATA_DIR", tempfile.mkdtemp(prefix="webapp-test-"))

from backend import sync_worker  # noqa: E402
from backend.db import init_webapp_db, webapp_conn  # noqa: E402

ENTITY = "todo.test_kind"


class FakeSupervisor:
    """Stands in for SupervisorClient; records update_todo_item calls."""

    available = True

    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.updates: list[tuple[str, str, str | None]] = []

    async def get_todo_items(self, entity_id: str) -> list[dict]:
        return [dict(i) for i in self.items]

    async def update_todo_item(
        self, entity_id: str, item: str, *, status: str | None = None, rename: str | None = None
    ) -> None:
        self.updates.append((entity_id, item, status))


def _item(uid: str, summary: str, desc: str, due: str, status: str = "needs_action") -> dict:
    return {"uid": uid, "summary": summary, "description": desc, "due": due, "status": status}


def _rows(account_id: int) -> list[dict]:
    conn = webapp_conn()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM tasks WHERE account_id = ? ORDER BY id", (account_id,)
            ).fetchall()
        ]
    finally:
        conn.close()


def _mark_done(task_id: int) -> None:
    conn = webapp_conn()
    try:
        conn.execute(
            "UPDATE tasks SET status='done', completed_at=?, updated_at=? WHERE id=?",
            ("2026-09-01T10:00:00+00:00", "2026-09-01T10:00:00+00:00", task_id),
        )
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _fresh_db():
    init_webapp_db()
    yield
    conn = webapp_conn()
    try:
        conn.execute("DELETE FROM tasks")
    finally:
        conn.close()


def test_dedup_key_distinguishes_same_tag_different_text():
    k1 = sync_worker._dedup_key("Buch S. 12 Nr. 3-5 [MA260901]")
    k2 = sync_worker._dedup_key("Arbeitsblatt 3 [MA260901]")
    assert k1 is not None and k2 is not None
    assert k1 != k2
    # Whitespace/Case-Normalisierung: gleicher Inhalt → gleicher Schlüssel.
    assert sync_worker._dedup_key("  buch s. 12   nr. 3-5\n[MA260901]") == k1
    assert sync_worker._dedup_key("kein Tag hier") is None
    assert sync_worker._dedup_key(None) is None


async def test_two_homeworks_same_subject_same_day_both_survive():
    """Zwei echte Hausaufgaben mit identischem Untis-Tag dürfen nicht
    aufeinander kollabiert oder als 'done' verschluckt werden."""
    account = 101
    sup = FakeSupervisor(
        [
            _item("u-1", "Mathematik", "Buch S. 12 Nr. 3-5 [MA260901]", "2026-09-03"),
            _item("u-2", "Mathematik", "Arbeitsblatt 3 [MA260901]", "2026-09-03"),
        ]
    )
    await sync_worker._sync_one(account, ENTITY, sup)
    # Zweiter Lauf: Dedup/Orphan-Pfade dürfen nichts wegräumen.
    await sync_worker._sync_one(account, ENTITY, sup)

    rows = _rows(account)
    assert len(rows) == 2
    assert all(r["status"] == "open" for r in rows)
    assert sup.updates == []  # nichts in HA abgehakt


async def test_uid_rotation_keeps_done_and_pushes_by_uid():
    """UID-Rotation der HA-Automation: erledigte Aufgabe bleibt erledigt,
    und der Done-Push nach HA adressiert die neue UID — nie den Titel."""
    account = 102
    sup = FakeSupervisor(
        [_item("u-old", "Mathematik", "Buch S. 12 Nr. 3-5 [MA260901]", "2026-09-03")]
    )
    await sync_worker._sync_one(account, ENTITY, sup)
    (row,) = _rows(account)
    _mark_done(row["id"])

    # Automation liefert dieselbe Aufgabe mit neuer UID und nachgeschobener
    # Fälligkeit (der typische Untis-Edit) als needs_action.
    sup.items = [_item("u-new", "Mathematik", "Buch S. 12 Nr. 3-5 [MA260901]", "2026-09-04")]
    stats = await sync_worker._sync_one(account, ENTITY, sup)
    assert stats["rebound_to_done"] == 1

    rows = _rows(account)
    assert len(rows) == 1
    assert rows[0]["status"] == "done"
    assert rows[0]["ha_uid"] == "u-new"

    # Nächster Lauf: HA meldet weiter needs_action → App gewinnt und pusht
    # completed, adressiert per UID.
    await sync_worker._sync_one(account, ENTITY, sup)
    assert (ENTITY, "u-new", "completed") in sup.updates
    assert all(item != "Mathematik" for _, item, _ in sup.updates)


async def test_app_done_push_uses_uid_not_title():
    account = 103
    sup = FakeSupervisor(
        [
            _item("u-a", "Mathematik", "Buch S. 12 [MA260901]", "2026-09-03"),
            _item("u-b", "Mathematik", "Vokabeln [MA260902]", "2026-09-04"),
        ]
    )
    await sync_worker._sync_one(account, ENTITY, sup)
    rows = _rows(account)
    target = next(r for r in rows if r["ha_uid"] == "u-b")
    _mark_done(target["id"])

    await sync_worker._sync_one(account, ENTITY, sup)
    assert sup.updates == [(ENTITY, "u-b", "completed")]


async def test_done_row_with_vanished_uid_pushes_nothing():
    """Ist das HA-Item wirklich gelöscht, darf kein Titel-basierter Push
    ein anderes Item desselben Fachs abhaken."""
    account = 104
    sup = FakeSupervisor(
        [_item("u-x", "Mathematik", "Buch S. 12 [MA260901]", "2026-09-03")]
    )
    await sync_worker._sync_one(account, ENTITY, sup)
    (row,) = _rows(account)
    _mark_done(row["id"])

    # Item verschwindet aus HA, eine andere offene Mathe-Aufgabe existiert.
    sup.items = [_item("u-y", "Mathematik", "Ganz andere Aufgabe [MA260902]", "2026-09-05")]
    await sync_worker._sync_one(account, ENTITY, sup)

    assert sup.updates == []
    rows = _rows(account)
    statuses = {r["ha_uid"]: r["status"] for r in rows}
    assert statuses["u-y"] == "open"  # die neue Aufgabe bleibt offen


# --------------------------------------------------------------- opt_day

def _set(task_id: int, **cols) -> None:
    conn = webapp_conn()
    try:
        sets = ", ".join(f"{k} = ?" for k in cols)
        conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", (*cols.values(), task_id))
    finally:
        conn.close()


def _one(sql: str, *params):
    conn = webapp_conn()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


async def test_user_note_does_not_break_rebind_and_keeps_subitems():
    """Der Dedup-Schlüssel kommt aus der HA-Beschreibung, nicht aus den
    Notizen: Nach einer Notiz und neuer HA-UID bleibt die offene Aufgabe samt
    Unterpunkt, statt gelöscht und neu angelegt zu werden."""
    account = 201
    desc = "Buch S. 12 Nr. 3-5 [MA260901]"
    sup = FakeSupervisor([_item("u-1", "Mathematik", desc, "2026-09-03")])
    await sync_worker._sync_one(account, ENTITY, sup)
    (row,) = _rows(account)
    assert row["ha_description"] == desc
    _set(row["id"], notes="Nr. 4 war schwer, morgen nachfragen")
    conn = webapp_conn()
    try:
        conn.execute("INSERT INTO task_subitems(task_id,title,done,position) VALUES(?,?,0,0)", (row["id"], "Nr. 3"))
    finally:
        conn.close()

    sup.items = [_item("u-2", "Mathematik", desc, "2026-09-03")]
    stats = await sync_worker._sync_one(account, ENTITY, sup)
    assert stats["rebound_to_done"] == 1 and stats["orphans_deleted"] == 0 and stats["inserted"] == 0
    (after,) = _rows(account)
    assert after["id"] == row["id"] and after["ha_uid"] == "u-2"
    assert after["notes"] == "Nr. 4 war schwer, morgen nachfragen"
    assert _one("SELECT COUNT(*) FROM task_subitems WHERE task_id=?", row["id"])[0] == 1


async def test_done_task_with_user_note_stays_done_after_uid_rotation():
    account = 202
    desc = "Arbeitsblatt 7 [DE260902]"
    sup = FakeSupervisor([_item("u-1", "Deutsch", desc, "2026-09-04")])
    await sync_worker._sync_one(account, ENTITY, sup)
    (row,) = _rows(account)
    _mark_done(row["id"])
    _set(row["id"], notes="erledigt, Blatt liegt in der Mappe")
    sup.items = [_item("u-2", "Deutsch", desc, "2026-09-04")]
    await sync_worker._sync_one(account, ENTITY, sup)
    rows = _rows(account)
    assert len(rows) == 1 and rows[0]["status"] == "done" and rows[0]["ha_uid"] == "u-2"


async def test_done_in_ha_closes_a_running_timer_and_skipped_follows():
    """Erledigt in HA gilt für jeden offenen Stand, nicht nur 'open'."""
    account = 203
    sup = FakeSupervisor([
        _item("u-t", "Mathematik", "Buch S. 20 [MA260903]", "2026-09-05"),
        _item("u-s", "Englisch", "Vokabeln [EN260903]", "2026-09-05"),
    ])
    await sync_worker._sync_one(account, ENTITY, sup)
    rows = {r["ha_uid"]: r for r in _rows(account)}
    _set(rows["u-t"]["id"], status="in_progress")
    _set(rows["u-s"]["id"], status="skipped")
    conn = webapp_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO users(id,ha_user_id,role,display_name,first_seen_at,last_seen_at) "
                     "VALUES(77,'t-77','child','Test','now','now')")
        conn.execute("INSERT INTO task_time_log(task_id,user_id,started_at) VALUES(?,77,?)",
                     (rows["u-t"]["id"], "2026-09-01T10:00:00+00:00"))
    finally:
        conn.close()
    for i in sup.items:
        i["status"] = "completed"
    await sync_worker._sync_one(account, ENTITY, sup)
    after = {r["ha_uid"]: r for r in _rows(account)}
    assert after["u-t"]["status"] == "done" and after["u-t"]["completed_at"]
    assert after["u-s"]["status"] == "done"
    log = _one("SELECT ended_at, minutes FROM task_time_log WHERE task_id=?", rows["u-t"]["id"])
    assert log["ended_at"] is not None and log["minutes"] >= 0
    assert sup.updates == []


async def test_empty_list_with_open_tasks_deletes_nothing():
    account = 204
    sup = FakeSupervisor([_item("u-1", "Mathematik", "Buch S. 12 [MA260901]", "2026-09-03")])
    await sync_worker._sync_one(account, ENTITY, sup)
    sup.items = []
    stats = await sync_worker._sync_one(account, ENTITY, sup)
    assert stats["orphans_deleted"] == 0
    assert len(_rows(account)) == 1


async def test_duplicate_ha_entries_keep_one_stable_binding():
    """HA führt denselben Eintrag doppelt: eine Reihe, die nicht jede Runde
    ihre UID wechselt und nicht neu angelegt oder gelöscht wird."""
    account = 205
    desc = "Buch S. 30 [MA260904]"
    sup = FakeSupervisor([_item("u-1", "Mathematik", desc, "2026-09-06")])
    await sync_worker._sync_one(account, ENTITY, sup)
    (row,) = _rows(account)
    sup.items = [_item("u-2", "Mathematik", desc, "2026-09-06"), _item("u-3", "Mathematik", desc, "2026-09-06")]
    await sync_worker._sync_one(account, ENTITY, sup)
    first = _rows(account)
    assert len(first) == 1 and first[0]["id"] == row["id"]
    for _ in range(3):
        stats = await sync_worker._sync_one(account, ENTITY, sup)
        again = _rows(account)
        assert len(again) == 1 and again[0]["id"] == row["id"]
        assert again[0]["ha_uid"] == first[0]["ha_uid"], "Bindung springt nicht"
        assert stats == {"inserted": 0, "orphans_deleted": 0, "duplicates_collapsed": 0, "rebound_to_done": 0}


async def test_fresh_duplicate_entries_create_one_row():
    account = 206
    desc = "Heft S. 3 [BI260905]"
    sup = FakeSupervisor([_item("u-a", "Biologie", desc, "2026-09-07"), _item("u-b", "Biologie", desc, "2026-09-07")])
    await sync_worker._sync_one(account, ENTITY, sup)
    await sync_worker._sync_one(account, ENTITY, sup)
    rows = _rows(account)
    assert len(rows) == 1 and rows[0]["ha_uid"] == "u-a"


class BrokenSupervisor(FakeSupervisor):
    async def get_todo_items(self, entity_id: str) -> list[dict]:
        raise sync_worker.SupervisorError("HA nicht erreichbar")


async def test_unreachable_ha_changes_nothing_and_does_not_raise():
    account = 207
    sup = FakeSupervisor([_item("u-1", "Mathematik", "Buch S. 12 [MA260901]", "2026-09-03")])
    await sync_worker._sync_one(account, ENTITY, sup)
    stats = await sync_worker._sync_one(account, ENTITY, BrokenSupervisor([]))
    assert stats["orphans_deleted"] == 0 and len(_rows(account)) == 1


async def test_client_turns_timeouts_and_missing_entity_into_supervisor_errors(monkeypatch):
    import httpx
    from backend import supervisor_client as sc

    real = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(sc.httpx, "AsyncClient",
                            lambda **kw: real(transport=httpx.MockTransport(handler), **kw))

    client = sc.SupervisorClient()
    client._token = "t"

    def timeout(request):
        raise httpx.ConnectTimeout("zu langsam", request=request)
    install(timeout)
    with pytest.raises(sc.SupervisorError):
        await client.get_todo_items(ENTITY)
    with pytest.raises(sc.SupervisorError):
        await client.update_todo_item(ENTITY, "u-1", status="completed")

    install(lambda request: httpx.Response(200, json={"service_response": {}}))
    with pytest.raises(sc.SupervisorError):
        await client.get_todo_items(ENTITY)

    install(lambda request: httpx.Response(200, json={"service_response": {ENTITY: {"items": []}}}))
    assert await client.get_todo_items(ENTITY) == []


async def test_one_failing_account_does_not_stop_the_others(monkeypatch):
    calls = []

    async def one(account_id, entity_id, sup):
        calls.append(account_id)
        if account_id == 1:
            raise RuntimeError("kaputt")
        return {"inserted": 0}

    monkeypatch.setattr(sync_worker, "_sync_one", one)
    monkeypatch.setattr(sync_worker, "get_supervisor", lambda: FakeSupervisor([]))
    monkeypatch.setattr(sync_worker, "_get_account_lists", lambda conn: [(1, "todo.a"), (2, "todo.b")])
    await sync_worker.sync_all()
    assert calls == [1, 2]


def test_migration_fills_the_key_from_existing_notes():
    from backend import db
    conn = webapp_conn()
    try:
        conn.execute(
            "INSERT INTO tasks(account_id,ha_uid,title,status,notes,source,created_at,updated_at) "
            "VALUES(208,'u-m','Mathematik','open','Buch S. 1 [MA260906]','ha_todo','now','now')")
        conn.execute(
            "INSERT INTO tasks(account_id,title,status,notes,source,created_at,updated_at) "
            "VALUES(208,'Eigene','open','[MA260906] eigene','manual','now','now')")
        conn.execute("UPDATE tasks SET ha_description=NULL WHERE account_id=208")
        conn.execute("DELETE FROM schema_meta WHERE key='migration:opt_day_tasks_ha_description_fill'")
        db._apply_migrations(conn)
        got = {r["source"]: r["ha_description"] for r in conn.execute(
            "SELECT source, ha_description FROM tasks WHERE account_id=208")}
    finally:
        conn.close()
    assert got == {"ha_todo": "Buch S. 1 [MA260906]", "manual": None}
