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
