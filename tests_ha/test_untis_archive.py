"""Sensoren und Kalender lesen die Datenbank nicht in der Ereignisschleife,
die großen Listen gehen nicht in den Recorder, und ein abgelehntes
Passwort führt zur Neuanmeldung statt zu endlosen Fehlversuchen."""
import asyncio
from datetime import date
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.untis_archive import coordinator as coord_mod
from custom_components.untis_archive.api import UntisAuthError
from custom_components.untis_archive.const import DOMAIN
from custom_components.untis_archive.storage import UntisStorage

DATA = {"display_name": "Kind A", "server": "schule.example.de", "school": "Beispielschule",
        "username": "kind.a", "password": "alt", "student_id": 7}
READS = ("lessons_for_day", "lessons_between", "open_homework", "absences_between",
         "missed_lessons", "recent_lesson_changes")


def _entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Kind A", data=DATA, unique_id="kind.a@schule")
    entry.add_to_hass(hass)
    return entry


async def test_sensors_read_in_the_executor_and_keep_lists_out_of_the_recorder(hass):
    in_loop = []

    def guard(name, fn):
        def inner(self, *args, **kwargs):
            try:
                asyncio.get_running_loop()
                in_loop.append(name)
            except RuntimeError:
                pass
            return fn(self, *args, **kwargs)
        return inner

    patches = [patch.object(UntisStorage, n, guard(n, getattr(UntisStorage, n)))
               for n in READS]
    for p in patches:
        p.start()
    try:
        entry = _entry(hass)
        with patch.object(coord_mod.UntisCoordinator, "_async_update_data", return_value={}):
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            homework = {"untis_homework_id": 1, "subject_name": "Mathematik",
                        "text": "S. 12 Nr. 3", "due_date": date.today().isoformat(),
                        "assigned_date": date.today().isoformat()}
            await hass.async_add_executor_job(
                coordinator.storage.upsert_homework, coordinator.account_id, homework)
            await coordinator.async_refresh()
            await hass.async_block_till_done()
    finally:
        for p in patches:
            p.stop()

    homework = hass.states.get("sensor.untis_archive_kind_a_hausaufgaben_offen")
    assert homework is not None and homework.state == "1"
    assert homework.attributes["items"][0]["text"] == "S. 12 Nr. 3"
    verlauf = hass.states.get("sensor.untis_archive_kind_a_fach_verlauf")
    assert verlauf is not None and verlauf.state == "0" and verlauf.attributes["subjects"] == {}
    assert hass.states.get("calendar.untis_archive_kind_a_stundenplan") is not None
    assert in_loop == [], f"Datenbank in der Ereignisschleife gelesen: {sorted(set(in_loop))}"

    from custom_components.untis_archive.sensor import _Base
    assert {"items", "subjects", "subject_list", "periods"} <= _Base._unrecorded_attributes


async def test_a_rejected_password_asks_for_a_new_one(hass):
    entry = _entry(hass)

    class Rejecting:
        def __init__(self, *args):
            pass

        async def login(self):
            raise UntisAuthError("bad credentials", code=-8504)

        async def close(self):
            pass

    with patch.object(coord_mod, "UntisClient", Rejecting):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = [f for f in hass.config_entries.flow.async_progress()
             if f["context"]["source"] == SOURCE_REAUTH]
    assert len(flows) == 1

    class Accepting(Rejecting):
        async def login(self):
            return None

    from custom_components.untis_archive import config_flow
    with patch.object(config_flow, "UntisClient", Accepting), \
            patch.object(coord_mod.UntisCoordinator, "_async_update_data", return_value={}):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {"password": "neu"})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data["password"] == "neu"


async def test_a_temporary_lockout_does_not_ask_for_a_new_password(hass):
    entry = _entry(hass)

    class Locked:
        def __init__(self, *args):
            pass

        async def login(self):
            raise UntisAuthError("too many requests", code=-8998)

        async def close(self):
            pass

    with patch.object(coord_mod, "UntisClient", Locked):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not [f for f in hass.config_entries.flow.async_progress()
                if f["context"]["source"] == SOURCE_REAUTH]
