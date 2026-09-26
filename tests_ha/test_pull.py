"""Abruf-Pipeline der Komponente gegen einen nachgebauten WebUntis-Client
(0.5.5): robuste Normalisierung, Lehrstoff-Nachholen, Geisterstunden,
gelöschte Fehlzeiten, Schüler-ID, Verfügbarkeit, Aufräumen, Zeitzone und
Sicherung."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.untis_archive import backup as backup_mod
from custom_components.untis_archive import coordinator as coord_mod
from custom_components.untis_archive.api import UntisApiError, UntisSession
from custom_components.untis_archive.const import DOMAIN, TOPIC_BACKFILL_MAX_PER_PULL
from custom_components.untis_archive.storage import UntisStorage

DATA = {"display_name": "Kind A", "server": "schule.example.de", "school": "Beispielschule",
        "username": "kind.a", "password": "pw"}
TODAY = date(2026, 9, 24)


def _u(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


def _period(pid: int, day: date, start: int = 800, code: str = "") -> dict[str, Any]:
    return {"id": pid, "date": _u(day), "startTime": start, "endTime": start + 45,
            "code": code, "su": [{"id": 1, "name": "MA", "longname": "Mathematik"}],
            "te": [{"id": 2, "name": "LEH"}], "ro": [{"id": 3, "name": "R1"}]}


@dataclass
class Fake:
    """Was der nachgebaute Client liefert und was er gefragt wurde."""
    timetable: list[dict[str, Any]] = field(default_factory=list)
    import_time: int | None = 1
    homework: dict[str, Any] = field(default_factory=dict)
    absences: dict[str, Any] = field(default_factory=lambda: {"data": {"absences": []}})
    absences_fail: bool = False
    lstext: dict[int, str] = field(default_factory=dict)
    period_fail: set[int] = field(default_factory=set)
    person_type: int = 5
    period_calls: list[int] = field(default_factory=list)
    timetable_calls: list[tuple[int | None, int | None]] = field(default_factory=list)
    absence_students: list[int | None] = field(default_factory=list)
    schoolyear: dict[str, Any] = field(
        default_factory=lambda: {"id": 9, "name": "2026/2027", "startDate": 20260801,
                                 "endDate": 20270731})

    def client(self):
        fake = self

        class Client:
            def __init__(self, *args, **kwargs):
                pass

            async def login(self):
                return UntisSession("geheim", fake.person_type, 42, 3)

            async def close(self):
                pass

            async def get_latest_import_time(self):
                return fake.import_time

            async def get_timetable(self, start, end, *, elem_id=None, elem_type=None):
                fake.timetable_calls.append((elem_id, elem_type))
                return list(fake.timetable)

            async def get_period_info(self, *, day, start_time, end_time, period_id,
                                      elem_id=None, elem_type=None):
                fake.period_calls.append(period_id)
                if period_id in fake.period_fail:
                    raise UntisApiError("boom")
                text = fake.lstext.get(period_id, "")
                return {"data": {"blocks": [[{"lessonTopic": {"text": text}}]]}}

            async def get_homework(self, start, end):
                return fake.homework

            async def get_absences(self, start, end, *, student_id=None):
                fake.absence_students.append(student_id)
                if fake.absences_fail:
                    raise UntisApiError("absences HTTP 500")
                return fake.absences

            async def get_current_schoolyear(self):
                return fake.schoolyear

            async def get_teachers(self):
                return []

            async def get_klassen(self):
                return []

            async def get_holidays(self):
                return []

        return Client


@pytest.fixture
async def berlin(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-24 10:00:00+02:00")


async def _setup(hass, fake: Fake, data: dict[str, Any] | None = None):
    entry = MockConfigEntry(domain=DOMAIN, title="Kind A", data=data or DATA,
                            unique_id="kind.a@schule")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, hass.data[DOMAIN][entry.entry_id]["coordinator"]


def _db(hass) -> sqlite3.Connection:
    conn = sqlite3.connect(hass.config.path("untis_archive", "history.db"))
    conn.row_factory = sqlite3.Row
    return conn


async def test_one_broken_record_does_not_break_the_pull(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY), {"id": 2, "date": None}],
                homework={"data": {"homeworks": [
                    {"id": 11, "lessonId": None, "text": "S. 3", "dueDate": _u(TODAY)},
                    {"id": 12, "lessonId": 5, "text": {"kaputt": 1}},
                ], "lessons": []}},
                absences={"data": {"absences": [
                    {"id": 21, "startDate": _u(TODAY), "endDate": _u(TODAY),
                     "startTime": 800, "endTime": 1300, "reason": "krank"},
                    {"id": 22, "startDate": _u(TODAY)},
                ]}})
    with patch.object(coord_mod, "UntisClient", fake.client()):
        entry, coordinator = await _setup(hass, fake)
    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success
    with _db(hass) as conn:
        assert [r[0] for r in conn.execute("SELECT untis_homework_id FROM homework")] == [11]
        assert [r[0] for r in conn.execute("SELECT untis_absence_id FROM absences")] == [21]
        assert conn.execute("SELECT was_absent FROM lessons WHERE untis_period_id=1").fetchone()[0] == 1
    hw = hass.states.get("sensor.untis_archive_kind_a_hausaufgaben_offen")
    assert hw.state == "1"


async def test_lehrstoff_is_fetched_later_without_a_new_import(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY - timedelta(days=1)), _period(2, TODAY),
                           _period(3, TODAY + timedelta(days=1)),
                           _period(4, TODAY - timedelta(days=1), 900, code="cancelled")])
    with patch.object(coord_mod, "UntisClient", fake.client()):
        _entry, coordinator = await _setup(hass, fake)
        # Erster Abruf: der ganze Stundenplan fragt period/info (Ausfall nicht).
        assert sorted(fake.period_calls) == [1, 2, 3]
        # Die Lehrkraft trägt den Lehrstoff nach; der Import-Zeitstempel
        # bleibt gleich, der Stundenplan-Pass wird übersprungen.
        fake.period_calls.clear()
        fake.lstext = {1: "Brüche erweitern"}
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert len(fake.timetable_calls) == 1
    # Nur vergangene und heutige Stunden ohne Lehrstoff, keine Zukunft,
    # kein Ausfall.
    assert sorted(fake.period_calls) == [1, 2]
    with _db(hass) as conn:
        row = conn.execute("SELECT lstext FROM lessons WHERE untis_period_id=1").fetchone()
    assert row[0] == "Brüche erweitern"
    # Beim nächsten Abruf ist Stunde 1 versorgt.
    fake.period_calls.clear()
    with patch.object(coord_mod, "UntisClient", fake.client()):
        await coordinator.async_refresh()
    assert fake.period_calls == [2]


async def test_topic_backfill_is_capped(hass, berlin):
    periods = [_period(100 + i, TODAY - timedelta(days=i % 5), 700 + i) for i in range(60)]
    fake = Fake(timetable=periods)
    with patch.object(coord_mod, "UntisClient", fake.client()):
        _entry, coordinator = await _setup(hass, fake)
        fake.period_calls.clear()
        await coordinator.async_refresh()
    assert len(fake.period_calls) == TOPIC_BACKFILL_MAX_PER_PULL
    assert coordinator.data["topics"]["backfill"] == TOPIC_BACKFILL_MAX_PER_PULL


async def test_failed_topics_do_not_repeat_the_timetable_pass(hass, berlin):
    """Scheitert ein Lehrstoff-Abruf, gilt der Import trotzdem als gelesen:
    Sonst holte jeder Abruf den ganzen Stundenplan neu. Den Lehrstoff holt
    der Nachlauf für Stunden ohne Lehrstoff."""
    fake = Fake(timetable=[_period(1, TODAY)], period_fail={1})
    with patch.object(coord_mod, "UntisClient", fake.client()):
        _entry, coordinator = await _setup(hass, fake)
        with _db(hass) as conn:
            assert conn.execute("SELECT latest_import_time FROM accounts").fetchone()[0] == 1
        fake.period_fail.clear()
        fake.period_calls.clear()
        await coordinator.async_refresh()
        assert len(fake.timetable_calls) == 1
        assert fake.period_calls, "der Nachlauf fragt die Stunde ohne Lehrstoff erneut"


async def test_ghost_lessons_disappear_from_sensor_and_calendar(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY), _period(2, TODAY, 900),
                           _period(3, TODAY + timedelta(days=1))], import_time=None)
    with patch.object(coord_mod, "UntisClient", fake.client()):
        _entry, coordinator = await _setup(hass, fake)
        assert len(hass.states.get("sensor.untis_archive_kind_a_lehrstoff_heute")
                   .attributes["items"]) == 2
        # Stunde 2 fällt ersatzlos aus dem Plan, für morgen liefert WebUntis
        # (Fenster gekürzt) nichts: Stunde 3 bleibt.
        fake.timetable = [_period(1, TODAY)]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data["lessons"]["removed"] == 1
        # Leere Antwort: nichts wird gekennzeichnet.
        fake.timetable = []
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data["lessons"]["removed"] == 0
    items = hass.states.get("sensor.untis_archive_kind_a_lehrstoff_heute").attributes["items"]
    assert [i["start"] for i in items] == [800]
    with _db(hass) as conn:
        rows = dict(conn.execute("SELECT untis_period_id, removed_at IS NOT NULL FROM lessons"))
    assert rows == {1: 0, 2: 1, 3: 0}


async def test_deleted_absence_clears_was_absent_also_outside_the_window(hass, berlin):
    old = TODAY - timedelta(days=20)
    absences = {"data": {"absences": [
        {"id": 21, "startDate": _u(old), "endDate": _u(old), "startTime": 800,
         "endTime": 1300, "reason": "krank"},
        {"id": 22, "startDate": _u(TODAY), "endDate": _u(TODAY), "startTime": 800,
         "endTime": 1300, "reason": "krank"},
    ]}}
    fake = Fake(timetable=[_period(1, TODAY)], absences=absences)
    with patch.object(coord_mod, "UntisClient", fake.client()):
        _entry, coordinator = await _setup(hass, fake)
        # Eine alte Stunde außerhalb des Stundenplan-Fensters.
        await hass.async_add_executor_job(
            coordinator.storage.upsert_lesson, coordinator.account_id,
            {"untis_period_id": 9, "date": old.isoformat(), "start_time": 900,
             "end_time": 945, "subject_name": "Deutsch"})
        with _db(hass) as conn:
            assert conn.execute("SELECT was_absent FROM lessons WHERE untis_period_id=9").fetchone()[0] == 0
        # Die Schule ändert die alte Fehlzeit: Neuberechnung über ihren Bereich.
        absences["data"]["absences"][0]["text"] = "Attest"
        await coordinator.async_refresh()
        with _db(hass) as conn:
            assert conn.execute("SELECT was_absent FROM lessons WHERE untis_period_id=9").fetchone()[0] == 1
        # Fehlzeiten-Abruf scheitert: nichts wird gelöscht.
        fake.absences_fail = True
        await coordinator.async_refresh()
        with _db(hass) as conn:
            assert conn.execute("SELECT COUNT(*) FROM absences").fetchone()[0] == 2
        # Die Schule löscht die alte Fehlzeit.
        fake.absences_fail = False
        del absences["data"]["absences"][0]
        await coordinator.async_refresh()
    with _db(hass) as conn:
        assert [r[0] for r in conn.execute("SELECT untis_absence_id FROM absences")] == [22]
        assert [r[0] for r in conn.execute("SELECT untis_absence_id FROM absence_deletions")] == [21]
        assert conn.execute("SELECT was_absent FROM lessons WHERE untis_period_id=9").fetchone()[0] == 0
        assert conn.execute("SELECT was_absent FROM lessons WHERE untis_period_id=1").fetchone()[0] == 1
    assert coordinator.data["absences"]["unchanged"] == 1


async def test_student_id_is_used_as_student_element(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY)], person_type=12)
    with patch.object(coord_mod, "UntisClient", fake.client()):
        await _setup(hass, fake, {**DATA, "student_id": 7})
    assert fake.timetable_calls == [(7, 5)]
    assert fake.absence_students == [7]


async def test_without_student_id_the_session_person_is_used(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY)])
    with patch.object(coord_mod, "UntisClient", fake.client()):
        await _setup(hass, fake)
    assert fake.timetable_calls == [(42, 5)]
    assert fake.absence_students == [42]


async def test_entities_stay_available_during_webuntis_maintenance(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY)])
    with patch.object(coord_mod, "UntisClient", fake.client()):
        _entry, coordinator = await _setup(hass, fake)

    class Down(fake.client()):
        async def login(self):
            from custom_components.untis_archive.api import UntisAuthError
            raise UntisAuthError("Wartung", code=-8520)

    with patch.object(coord_mod, "UntisClient", Down):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert not coordinator.last_update_success
    for entity_id in ("sensor.untis_archive_kind_a_lehrstoff_heute",
                      "sensor.untis_archive_kind_a_hausaufgaben_offen",
                      "calendar.untis_archive_kind_a_stundenplan",
                      "calendar.untis_archive_kind_a_ereignisse"):
        assert hass.states.get(entity_id).state != "unavailable", entity_id
    assert hass.states.get("sensor.untis_archive_kind_a_lehrstoff_heute").state == "0"


async def test_failed_first_refresh_closes_the_database(hass, berlin):
    closed = []
    orig = UntisStorage.close

    def close(self):
        closed.append(self)
        orig(self)

    class Broken(Fake().client()):
        async def get_timetable(self, *args, **kwargs):
            raise UntisApiError("HTTP 503")

    entry = MockConfigEntry(domain=DOMAIN, title="Kind A", data=DATA, unique_id="kind.a@schule")
    entry.add_to_hass(hass)
    with patch.object(coord_mod, "UntisClient", Broken), patch.object(UntisStorage, "close", close):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert len(closed) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        closed[0]._conn.execute("SELECT 1")


async def test_failed_platform_unload_keeps_the_database_open(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY)])
    with patch.object(coord_mod, "UntisClient", fake.client()):
        entry, coordinator = await _setup(hass, fake)
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
        assert not await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator.storage_ready
    assert entry.entry_id in hass.data[DOMAIN]


async def test_mark_lesson_updates_entities_without_a_pull(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY)])
    with patch.object(coord_mod, "UntisClient", fake.client()):
        _entry, coordinator = await _setup(hass, fake)
        calls = len(fake.timetable_calls)
        with _db(hass) as conn:
            lesson_id = conn.execute("SELECT id FROM lessons").fetchone()[0]
        await hass.services.async_call(DOMAIN, "mark_lesson",
                                       {"lesson_id": lesson_id, "lstext": "Eigener Eintrag"},
                                       blocking=True)
        await hass.async_block_till_done()
    assert len(fake.timetable_calls) == calls
    state = hass.states.get("sensor.untis_archive_kind_a_lehrstoff_heute")
    assert state.state == "1"
    assert state.attributes["items"][0]["lstext"] == "Eigener Eintrag"


async def test_today_follows_the_ha_time_zone(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Berlin")
    # 23:30 UTC ist in Berlin schon der nächste Tag.
    freezer.move_to("2026-09-24 23:30:00+00:00")
    tomorrow = TODAY + timedelta(days=1)
    fake = Fake(timetable=[_period(1, TODAY), _period(2, tomorrow)])
    with patch.object(coord_mod, "UntisClient", fake.client()):
        await _setup(hass, fake)
    items = hass.states.get("sensor.untis_archive_kind_a_lehrstoff_heute").attributes["items"]
    assert len(items) == 1
    with _db(hass) as conn:
        pid = conn.execute("SELECT untis_period_id FROM lessons WHERE date=?",
                           (tomorrow.isoformat(),)).fetchone()[0]
    assert pid == 2


async def test_export_markdown_writes_files(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY)], lstext={1: "Brüche"})
    with patch.object(coord_mod, "UntisClient", fake.client()):
        await _setup(hass, fake)
    await hass.services.async_call(DOMAIN, "export_markdown", {"account": "Kind A"},
                                   blocking=True)
    out = hass.config.path("untis_archive", "docs", "kind_a", "mathematik.md")
    text = await hass.async_add_executor_job(lambda: open(out, encoding="utf-8").read())
    assert "Brüche" in text


async def test_backup_hooks_pause_checkpoints_and_never_raise(hass, berlin):
    fake = Fake(timetable=[_period(1, TODAY)])
    with patch.object(coord_mod, "UntisClient", fake.client()):
        _entry, coordinator = await _setup(hass, fake)
    conn = coordinator.storage._conn

    def autocheckpoint():
        return conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0]

    await backup_mod.async_pre_backup(hass)
    assert await hass.async_add_executor_job(autocheckpoint) == 0
    await backup_mod.async_post_backup(hass)
    assert await hass.async_add_executor_job(autocheckpoint) == 1000

    with patch.object(UntisStorage, "prepare_backup", side_effect=sqlite3.OperationalError("x")):
        await backup_mod.async_pre_backup(hass)
    await backup_mod.async_post_backup(hass)
