"""Fach-Auflösung für Hausaufgaben (untis_archive 0.5.1).

Zwei reale Probleme:

1. ``normalize_homework`` erwartete ``lessons[].subject`` als Dict —
   reale Installationen liefern an dieser Stelle aber teils einen
   nackten String, wodurch ``subject_name`` dauerhaft NULL blieb.
2. Auch mit NULL-Zeilen im Bestand soll ``open_homework`` das Fach
   liefern: Langname aus der lessons-Tabelle (Join über
   ``homework.untis_lesson_id == lessons.lsnumber``) und das
   Untis-Kürzel (``subject_code``) aus dem Stunden-Payload.

Run with::

    pytest tests/test_homework_subjects.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# storage.py direkt laden, damit der Test nicht den HA-Runtime-Stack
# über custom_components/untis_archive/__init__.py hereinzieht.
_STORAGE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "untis_archive"
    / "storage.py"
)
_spec = importlib.util.spec_from_file_location("untis_archive_storage_hw", _STORAGE_PATH)
assert _spec is not None and _spec.loader is not None
_storage_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _storage_mod
_spec.loader.exec_module(_storage_mod)

UntisStorage = _storage_mod.UntisStorage
normalize_homework = _storage_mod.normalize_homework


def test_normalize_homework_subject_as_dict():
    hw = normalize_homework(
        {"id": 1, "lessonId": 10, "text": "S. 5", "date": 20260901, "dueDate": 20260902},
        {10: {"subject": {"id": 7, "name": "MA"}}},
    )
    assert hw["subject_untis_id"] == 7
    assert hw["subject_name"] == "MA"


def test_normalize_homework_subject_as_string():
    hw = normalize_homework(
        {"id": 2, "lessonId": 11, "text": "S. 6", "date": 20260901, "dueDate": 20260902},
        {11: {"subject": "Mathematik"}},
    )
    assert hw["subject_untis_id"] is None
    assert hw["subject_name"] == "Mathematik"


def test_normalize_homework_subject_missing():
    hw = normalize_homework(
        {"id": 3, "lessonId": 12, "text": "S. 7", "date": 20260901, "dueDate": 20260902},
        {},
    )
    assert hw["subject_untis_id"] is None
    assert hw["subject_name"] is None


def _make_account(storage: UntisStorage) -> int:
    return storage.ensure_account(
        entry_id="test-entry",
        name="Testkind",
        server="server",
        school="school",
        username="user",
        student_id=1,
        student_type=1,
    )


def test_open_homework_resolves_subject_via_lessons(tmp_path):
    storage = UntisStorage(tmp_path / "hist.db")
    try:
        account_id = _make_account(storage)
        storage.upsert_lesson(
            account_id,
            {
                "untis_period_id": 1001,
                "date": "2026-09-01",
                "start_time": 800,
                "end_time": 845,
                "subject_untis_id": 7,
                "subject_name": "MATHEMATIK",
                "lsnumber": 555,
                "payload_json": json.dumps(
                    {"su": [{"id": 7, "name": "MA", "longname": "MATHEMATIK"}]}
                ),
            },
        )
        # Hausaufgabe ohne subject_name (so sehen die Bestandszeilen aus).
        storage.upsert_homework(
            account_id,
            {
                "untis_homework_id": 42,
                "untis_lesson_id": 555,
                "subject_untis_id": None,
                "subject_name": None,
                "text": "Seite 102 Aufgabe 12)",
                "assigned_date": "2026-09-01",
                "due_date": "2026-09-02",
                "completed": False,
                "payload_json": "{}",
            },
        )
        rows = storage.open_homework(account_id)
        assert len(rows) == 1
        assert rows[0]["subject_name"] == "MATHEMATIK"
        assert rows[0]["subject_code"] == "MA"
    finally:
        storage.close()


def test_open_homework_without_lesson_match_keeps_none(tmp_path):
    storage = UntisStorage(tmp_path / "hist.db")
    try:
        account_id = _make_account(storage)
        storage.upsert_homework(
            account_id,
            {
                "untis_homework_id": 43,
                "untis_lesson_id": 999,  # keine passende Lesson vorhanden
                "subject_untis_id": None,
                "subject_name": None,
                "text": "AB fertig machen",
                "assigned_date": "2026-09-01",
                "due_date": "2026-09-03",
                "completed": False,
                "payload_json": "{}",
            },
        )
        rows = storage.open_homework(account_id)
        assert len(rows) == 1
        assert rows[0]["subject_name"] is None
        assert rows[0]["subject_code"] is None
    finally:
        storage.close()
