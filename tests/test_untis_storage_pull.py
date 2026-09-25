"""Speicherschicht der UNTIS-Archive-Komponente (0.5.5): robuste
Normalisierung, Geisterstunden, gelöschte Fehlzeiten, Aufsichts-Vermutung,
nachträgliche Stunden, Batch-Schreiben und Sicherungsvorbereitung.

storage.py wird direkt geladen, ohne den HA-Stack aus ``__init__.py``.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sqlite3
import sys
from pathlib import Path

import pytest

_STORAGE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "untis_archive"
    / "storage.py"
)
_spec = importlib.util.spec_from_file_location("untis_archive_storage_pull", _STORAGE_PATH)
assert _spec is not None and _spec.loader is not None
st = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = st
_spec.loader.exec_module(st)


@pytest.fixture
def db(tmp_path):
    storage = st.UntisStorage(tmp_path / "history.db")
    account = storage.ensure_account(
        entry_id="e1", name="Kind A", server="s", school="x", username="u",
        student_id=None, student_type=None,
    )
    yield storage, account
    storage.close()


def _lesson(pid, day, start=800, **extra):
    out = {"untis_period_id": pid, "date": day, "start_time": start,
           "end_time": start + 45, "subject_name": "Mathematik", "code": ""}
    out.update(extra)
    return out


def _absence(aid, start="2026-09-10", end="2026-09-10", **extra):
    out = {"untis_absence_id": aid, "start_date": start, "end_date": end,
           "start_time": 800, "end_time": 1300, "reason": "krank",
           "payload_json": json.dumps({"id": aid})}
    out.update(extra)
    return out


def _row(storage, sql, *args):
    return storage._conn.execute(sql, args).fetchone()


# ---- H4: ein kaputter Eintrag bricht den Abruf nicht ab --------------------

def test_homework_with_null_lesson_id_and_broken_entries(caplog):
    payload = {"data": {
        "homeworks": [
            {"id": 1, "lessonId": None, "text": "S. 3", "date": 20260901, "dueDate": 20260902},
            {"lessonId": 5},                      # ohne id: wie bisher ignoriert
            {"id": "kaputt", "lessonId": 5},       # int("kaputt") -> ValueError
            {"id": 2, "lessonId": 7, "text": {"x": 1}},  # text kein String
            {"id": 3, "lessonId": 7, "text": "Nr. 4", "dueDate": 20260903},
        ],
        "lessons": [{"id": 7, "subject": "Deutsch"}, {"id": None}],
    }}
    with caplog.at_level(logging.WARNING):
        items = list(st.collect_homework(payload))
    assert [h["untis_homework_id"] for h in items] == [1, 3]
    assert items[0]["untis_lesson_id"] is None
    assert items[1]["subject_name"] == "Deutsch"
    assert "übersprungen" in caplog.text


def test_absence_without_dates_is_skipped(caplog):
    payload = {"data": {"absences": [
        {"id": 1, "startDate": 20260910, "endDate": 20260910, "startTime": 800, "endTime": 900},
        {"id": 2, "startDate": 20260911},               # Zeitfelder fehlen
        {"id": 3, "startDate": None, "endDate": 20260911, "startTime": 800, "endTime": 900},
    ]}}
    with caplog.at_level(logging.WARNING):
        items = list(st.collect_absences(payload))
    assert [a["untis_absence_id"] for a in items] == [1]
    # Die IDs aller gelieferten Einträge zählen trotzdem als geliefert.
    assert st.absence_ids_in_payload(payload) == {1, 2, 3}


def test_absence_ids_unclear_payloads():
    assert st.absence_ids_in_payload({}) is None
    assert st.absence_ids_in_payload({"data": {"errorMessage": "x"}}) is None
    assert st.absence_ids_in_payload({"data": {"absences": [{"x": 1}]}}) is None
    assert st.absence_ids_in_payload({"data": {"absences": []}}) == set()
    assert st.absence_ids_in_payload({"absences": [{"id": 4}]}) == {4}


# ---- Batch-Schreiben -------------------------------------------------------

def test_upsert_lessons_isolates_a_broken_row(db):
    storage, acc = db
    results = storage.upsert_lessons(acc, [
        _lesson(1, "2026-09-10"),
        {"untis_period_id": 2},             # date fehlt -> KeyError / NOT NULL
        _lesson(3, "2026-09-10", 900),
    ], today="2026-09-20")
    assert [getattr(r, "action", None) for r in results] == ["inserted", None, "inserted"]
    ids = {r[0] for r in storage._conn.execute("SELECT untis_period_id FROM lessons")}
    assert ids == {1, 3}
    again = storage.upsert_lessons(acc, [_lesson(1, "2026-09-10")], today="2026-09-20")
    assert again[0].action == "unchanged"


def test_wal_with_synchronous_normal(db):
    storage, _ = db
    assert _row(storage, "PRAGMA journal_mode")[0] == "wal"
    assert _row(storage, "PRAGMA synchronous")[0] == 1  # NORMAL


# ---- H6: nachträglich eingetragene Stunden --------------------------------

def test_late_addition_only_for_past_days_after_first_pull(db):
    storage, acc = db
    storage.upsert_lessons(acc, [_lesson(1, "2026-09-01"), _lesson(2, "2026-09-30")],
                           today="2026-09-20")
    storage.mark_pull_complete(acc)
    storage.upsert_lessons(acc, [
        _lesson(3, "2026-09-25"),   # neuer Tag im Fenster, später als heute
        _lesson(4, "2026-09-20"),   # heute
        _lesson(5, "2026-09-18"),   # vergangen, erst jetzt aufgetaucht
    ], today="2026-09-20")
    flags = dict(storage._conn.execute("SELECT untis_period_id, is_late_addition FROM lessons"))
    assert flags == {1: 0, 2: 0, 3: 0, 4: 0, 5: 1}


# ---- H13: Aufsichts-Vermutung ---------------------------------------------

def test_supervision_guess_follows_stored_lstext(db):
    storage, acc = db
    guess = lambda: _row(storage, "SELECT is_supervision_guess FROM lessons WHERE untis_period_id=9")[0]  # noqa: E731
    storage.upsert_lesson(acc, _lesson(9, "2026-09-10", code="irregular", is_supervision_guess=True))
    assert guess() == 1
    storage.upsert_lesson(acc, {"untis_period_id": 9, "date": "2026-09-10", "start_time": 800,
                                "end_time": 845, "lstext": "Brüche", "period_info_json": "{}"})
    assert guess() == 0
    # Der nächste Stundenplan-Pass (ohne lstext, mit Vermutung aus der
    # Stundenplan-Antwort) setzt sie nicht wieder auf 1.
    res = storage.upsert_lesson(acc, _lesson(9, "2026-09-10", code="irregular",
                                             is_supervision_guess=True))
    assert guess() == 0 and res.action == "unchanged"
    storage.upsert_lesson(acc, _lesson(9, "2026-09-10", code=""))
    assert guess() == 0


# ---- H2: Geisterstunden ----------------------------------------------------

def test_ghost_lessons_are_marked_and_restored(db):
    storage, acc = db
    storage.upsert_lessons(acc, [_lesson(1, "2026-09-10"), _lesson(2, "2026-09-10", 900),
                                 _lesson(3, "2026-09-11"), _lesson(4, "2026-09-12")],
                           today="2026-09-10")
    # WebUntis liefert für den 10. nur Stunde 1, für den 11. Stunde 3,
    # für den 12. nichts (Tag nicht abgedeckt: Stunde 4 bleibt).
    removed, restored = storage.mark_removed_lessons(acc, {1, 3}, {"2026-09-10", "2026-09-11"})
    assert (removed, restored) == (1, 0)
    assert [r["untis_period_id"] for r in storage.lessons_for_day(acc, "2026-09-10")] == [1]
    assert [r["untis_period_id"] for r in storage.lessons_between(acc, "2026-09-01", "2026-09-30")] == [1, 3, 4]
    # Die Zeile ist noch da, nur gekennzeichnet.
    assert _row(storage, "SELECT removed_at FROM lessons WHERE untis_period_id=2")[0]
    # Kommt sie wieder, verschwindet die Kennzeichnung.
    assert storage.mark_removed_lessons(acc, {1, 2, 3}, {"2026-09-10"}) == (0, 1)
    assert len(storage.lessons_for_day(acc, "2026-09-10")) == 2


def test_ghost_marking_needs_returned_ids_and_days(db):
    storage, acc = db
    storage.upsert_lesson(acc, _lesson(1, "2026-09-10"))
    assert storage.mark_removed_lessons(acc, set(), {"2026-09-10"}) == (0, 0)
    assert storage.mark_removed_lessons(acc, {99}, set()) == (0, 0)
    assert len(storage.lessons_for_day(acc, "2026-09-10")) == 1


def test_removed_lessons_leave_missed_and_topic_lists(db):
    storage, acc = db
    storage.upsert_lessons(acc, [_lesson(1, "2026-09-10"), _lesson(2, "2026-09-10", 900)],
                           today="2026-09-10")
    storage.upsert_absence(acc, _absence(50))
    storage.recompute_attendance(acc, "2026-09-01", "2026-09-30")
    storage.mark_removed_lessons(acc, {1}, {"2026-09-10"})
    assert [r["untis_period_id"] for r in storage.missed_lessons(acc, "2026-09-01", "2026-09-30")] == [1]
    assert [r["untis_period_id"] for r in storage.lessons_missing_lstext(acc, "2026-09-01", "2026-09-30")] == [1]


def test_missing_lstext_newest_first_without_cancelled(db):
    storage, acc = db
    storage.upsert_lessons(acc, [
        _lesson(1, "2026-09-08"), _lesson(2, "2026-09-09"),
        _lesson(3, "2026-09-09", 900, code="cancelled"),
        _lesson(4, "2026-09-10", lstext="Da"),
    ], today="2026-09-10")
    rows = storage.lessons_missing_lstext(acc, "2026-09-05", "2026-09-10")
    assert [r["untis_period_id"] for r in rows] == [2, 1]


# ---- H3/H12: Fehlzeiten ----------------------------------------------------

def test_upsert_absence_reports_unchanged(db):
    storage, acc = db
    assert storage.upsert_absence(acc, _absence(1)) == "inserted"
    assert storage.upsert_absence(acc, _absence(1)) == "unchanged"
    assert storage.upsert_absence(acc, _absence(1, text="Arzt")) == "updated"
    assert storage.upsert_absences(acc, [_absence(1, text="Arzt"), _absence(2)]) == ["unchanged", "inserted"]


def test_deleted_absence_is_archived_and_attendance_follows(db):
    storage, acc = db
    storage.upsert_lessons(acc, [_lesson(1, "2026-09-10"), _lesson(2, "2026-09-15")],
                           today="2026-09-20")
    storage.upsert_absences(acc, [_absence(1), _absence(2, "2026-09-15", "2026-09-15"),
                                  _absence(3, "2025-06-01", "2025-06-01")])
    storage.recompute_attendance(acc, "2026-09-01", "2026-09-30")
    assert len(storage.missed_lessons(acc, "2026-09-01", "2026-09-30")) == 2

    span = storage.delete_absences_not_in(acc, {2}, "2026-08-01", "2026-10-20")
    assert span == ("2026-09-10", "2026-09-10")
    ids = {r[0] for r in storage._conn.execute("SELECT untis_absence_id FROM absences")}
    assert ids == {2, 3}  # 3 liegt vor dem Schuljahr: bleibt
    archived = storage._conn.execute("SELECT untis_absence_id, row_json FROM absence_deletions").fetchall()
    assert [a[0] for a in archived] == [1]
    assert json.loads(archived[0][1])["reason"] == "krank"
    storage.recompute_attendance(acc, *span)
    assert [r["untis_period_id"] for r in storage.missed_lessons(acc, "2026-09-01", "2026-09-30")] == [2]


def test_absence_deletion_guards(db):
    storage, acc = db
    storage.upsert_absences(acc, [_absence(i, "2026-09-1%d" % i, "2026-09-1%d" % i) for i in range(1, 8)])
    # Leere Antwort: nichts löschen.
    assert storage.delete_absences_not_in(acc, set(), "2026-08-01", "2026-10-20") is None
    # Zu viele auf einmal: eher eine unvollständige Antwort, nichts löschen.
    assert storage.delete_absences_not_in(acc, {1}, "2026-08-01", "2026-10-20", max_delete=5) is None
    assert _row(storage, "SELECT COUNT(*) FROM absences")[0] == 7
    assert _row(storage, "SELECT COUNT(*) FROM absence_deletions")[0] == 0


def test_absence_span(db):
    storage, acc = db
    storage.upsert_absences(acc, [_absence(1, "2026-03-02", "2026-03-04"), _absence(2, "2026-05-01", "2026-05-02")])
    assert storage.absence_span(acc, [1, 2]) == ("2026-03-02", "2026-05-02")
    assert storage.absence_span(acc, []) is None
    assert storage.absence_span(acc, [77]) is None


# ---- H5: offene Hausaufgaben begrenzt -------------------------------------

def test_open_homework_since_day(db):
    storage, acc = db
    for hid, due in ((1, "2026-08-01"), (2, "2026-09-10"), (3, None), (4, "2026-09-30")):
        storage.upsert_homework(acc, {"untis_homework_id": hid, "text": "t", "due_date": due})
    assert {h["untis_homework_id"] for h in storage.open_homework(acc)} == {1, 2, 3, 4}
    assert {h["untis_homework_id"] for h in storage.open_homework(acc, "2026-09-06")} == {2, 3, 4}


# ---- Sicherung -------------------------------------------------------------

def test_prepare_and_finish_backup(db):
    storage, acc = db
    storage.upsert_lesson(acc, _lesson(1, "2026-09-10"))
    busy, _log, _done = storage.prepare_backup()
    assert busy == 0
    assert _row(storage, "PRAGMA wal_autocheckpoint")[0] == 0
    wal = Path(str(storage._path) + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0
    storage.upsert_lesson(acc, _lesson(2, "2026-09-10", 900))
    storage.finish_backup()
    assert _row(storage, "PRAGMA wal_autocheckpoint")[0] == 1000


# ---- Vertrag mit dem Add-on -----------------------------------------------

def test_history_db_still_matches_addon_contract(db, tmp_path):
    from backend.history_schema import REQUIRED_TABLES, assert_compatible
    storage, _ = db
    assert_compatible(str(storage._path))
    cols = {r[1] for r in storage._conn.execute("PRAGMA table_info(lessons)")}
    lesson_spec = next(t for t in REQUIRED_TABLES if t.name == "lessons")
    assert lesson_spec.required_columns <= cols and "removed_at" in cols


def test_migration_adds_removed_at_to_an_old_db(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(st.SCHEMA.replace("    removed_at TEXT,\n", ""))
    conn.execute("INSERT INTO accounts (entry_id, name, server, school, username, created_at) "
                 "VALUES ('e', 'n', 's', 'x', 'u', 'now')")
    conn.execute("INSERT INTO lessons (account_id, untis_period_id, date, start_time, end_time, "
                 "first_seen_at, last_updated_at) VALUES (1, 5, '2026-09-10', 800, 845, 'a', 'a')")
    conn.commit()
    assert "removed_at" not in {r[1] for r in conn.execute("PRAGMA table_info(lessons)")}
    conn.close()
    storage = st.UntisStorage(path)
    try:
        assert [r["untis_period_id"] for r in storage.lessons_for_day(1, "2026-09-10")] == [5]
    finally:
        storage.close()


def test_close_while_other_threads_read_does_not_crash(tmp_path):
    """Schließen ohne Sperre, während Sensoren im Executor lasen, ließ den
    Prozess mit einem Speicherzugriffsfehler abstürzen."""
    import threading

    storage = st.UntisStorage(tmp_path / "history.db")
    acc = storage.ensure_account(entry_id="e", name="n", server="s", school="x",
                                 username="u", student_id=None, student_type=None)
    storage.upsert_lessons(acc, [_lesson(i, "2026-09-10", 700 + i) for i in range(50)],
                           today="2026-09-10")
    errors: list[BaseException] = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                storage.lessons_between(acc, "2026-09-01", "2026-09-30")
            except sqlite3.ProgrammingError:
                return  # geschlossen: sauberer Fehler statt Absturz
            except BaseException as err:  # noqa: BLE001
                errors.append(err)
                return

    threads = [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    storage.close()
    stop.set()
    for t in threads:
        t.join(5)
    assert errors == []
