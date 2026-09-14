"""School calendars straight from IServ: repair, discovery, roles, merging."""

import asyncio
from contextlib import closing
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_learning import env  # noqa: F401  (fixture)
from backend import db, iserv_calendar as ical, school_calendars as store
from backend.auth import get_current_user
from backend.routers import calendars as routes

URL = "/api/accounts/1/calendars"

BROKEN = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:klausur-1
SUMMARY:Klausur Physik
DTSTART;TZID=+02:00:20260917T080000
DTEND;TZID=+02:00:20260917T093000
END:VEVENT
BEGIN:VEVENT
UID:ganztag-1
SUMMARY:Projekttag
DTSTART;VALUE=DATE:20260920
DTEND;VALUE=DATE:20260921
END:VEVENT
END:VCALENDAR"""


def test_the_offset_timezone_that_breaks_home_assistant_is_repaired():
    # IServ writes TZID=+02:00; the standard wants a named zone and HA drops
    # the whole file over it.
    fixed = ical.repair_ics(BROKEN)
    assert "TZID=Europe/Berlin" in fixed and "+02:00" not in fixed


def test_events_are_read_including_the_malformed_one():
    events = ical.parse_events(ical.repair_ics(BROKEN), date(2026, 9, 1), date(2026, 10, 1))
    by_uid = {e["uid"]: e for e in events}
    assert by_uid["klausur-1"]["start_date"] == "2026-09-17"
    assert by_uid["klausur-1"]["start_time"] == "08:00"
    assert by_uid["klausur-1"]["all_day"] is False
    # An all-day end date is exclusive in iCalendar, so the day before counts.
    assert by_uid["ganztag-1"]["end_date"] == "2026-09-20"
    assert by_uid["ganztag-1"]["all_day"] is True


def test_events_outside_the_window_are_skipped():
    assert ical.parse_events(ical.repair_ics(BROKEN), date(2026, 1, 1), date(2026, 2, 1)) == []


def test_unparsable_calendar_does_not_lose_the_others():
    text = "BEGIN:VCALENDAR\nkaputt\nBEGIN:VEVENT\n" + "\n" + ical.repair_ics(BROKEN)
    assert len(ical.parse_events(text, date(2026, 9, 1), date(2026, 10, 1))) == 2


def test_discovery_follows_every_shared_principal(monkeypatch):
    """IServ lists one principal per shared group; each keeps its calendar
    one level below. Following only the first finds no class calendar."""
    from xml.etree import ElementTree

    homes = """<?xml version="1.0"?>
    <d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:response>
      <d:href>/caldav/caldav.php/kind/</d:href><d:propstat><d:prop>
      <c:calendar-home-set>
        <d:href>/caldav/caldav.php/kind/</d:href>
        <d:href>/caldav/caldav.php/klasse8d/</d:href>
      </c:calendar-home-set></d:prop></d:propstat></d:response></d:multistatus>"""

    def collection(home, name, calendar_name):
        return f"""<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
          <d:response><d:href>{home}</d:href><d:propstat><d:prop>
            <d:resourcetype><d:collection/><d:principal/></d:resourcetype>
            <d:displayname>{name}</d:displayname></d:prop></d:propstat></d:response>
          <d:response><d:href>{home}calendar/</d:href><d:propstat><d:prop>
            <d:resourcetype><d:collection/><c:calendar/></d:resourcetype>
            <d:displayname>{calendar_name}</d:displayname></d:prop></d:propstat></d:response>
          <d:response><d:href>{home}todos/</d:href><d:propstat><d:prop>
            <d:resourcetype><d:collection/><c:calendar/></d:resourcetype>
            <d:displayname>To-dos</d:displayname>
            <c:supported-calendar-component-set><c:comp name="VTODO"/></c:supported-calendar-component-set>
          </d:prop></d:propstat></d:response>
        </d:multistatus>"""

    answers = {
        "https://beispiel-iserv.de/caldav/": '<d:multistatus xmlns:d="DAV:"><d:response><d:propstat><d:prop>'
                                        "<d:current-user-principal><d:href>/caldav/caldav.php/kind/</d:href>"
                                        "</d:current-user-principal></d:prop></d:propstat></d:response></d:multistatus>",
        "https://beispiel-iserv.de/caldav/caldav.php/kind/": homes,
    }
    listings = {
        "https://beispiel-iserv.de/caldav/caldav.php/kind/": collection("/caldav/caldav.php/kind/", "Kind", "Home"),
        "https://beispiel-iserv.de/caldav/caldav.php/klasse8d/":
            collection("/caldav/caldav.php/klasse8d/", "Klasse8D", "Klasse8D Calendar"),
    }

    async def propfind(client, url, body, depth):
        text = listings[url] if depth == "1" else answers[url]
        return ElementTree.fromstring(text)

    monkeypatch.setattr(ical, "_propfind", propfind)
    found = asyncio.run(ical.discover("https://beispiel-iserv.de", "kind", "x"))
    names = [c["name"] for c in found]
    # The class calendar comes along, the to-do list does not, and the stale
    # "<Gruppe> Calendar" label is replaced by the group name.
    assert names == ["Home", "Klasse8D"]


def test_discovery_reads_names_and_skips_non_calendars(monkeypatch):
    answer = """<?xml version="1.0"?>
    <d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"
                   xmlns:a="http://apple.com/ns/ical/">
      <d:response><d:href>/caldav/kind_a/</d:href><d:propstat><d:prop>
        <d:resourcetype><d:collection/></d:resourcetype><d:displayname>Home</d:displayname>
      </d:prop></d:propstat></d:response>
      <d:response><d:href>/caldav/kind_a/klausuren-8d/</d:href><d:propstat><d:prop>
        <d:resourcetype><d:collection/><c:calendar/></d:resourcetype>
        <d:displayname>Klausuren 8D</d:displayname><a:calendar-color>#ff0000</a:calendar-color>
      </d:prop></d:propstat></d:response>
      <d:response><d:href>/caldav/kind_a/aufgaben/</d:href><d:propstat><d:prop>
        <d:resourcetype><d:collection/><c:calendar/></d:resourcetype>
        <d:displayname>Aufgaben</d:displayname>
        <c:supported-calendar-component-set><c:comp name="VTODO"/></c:supported-calendar-component-set>
      </d:prop></d:propstat></d:response>
    </d:multistatus>"""
    from xml.etree import ElementTree

    async def propfind(client, url, body, depth):
        return ElementTree.fromstring(answer)

    monkeypatch.setattr(ical, "_propfind", propfind)
    found = asyncio.run(ical.discover("https://beispiel-iserv.de", "kind_a", "x"))
    assert [c["name"] for c in found] == ["Klausuren 8D"]
    assert found[0]["url"].endswith("/caldav/kind_a/klausuren-8d/")


def test_a_rebuilt_calendar_keeps_its_role(env):
    with closing(db.webapp_conn()) as conn, conn:
        store._remember(conn, 1, [{"url": "https://s/caldav/n/klausuren-2025/", "name": "Klausuren 8D"}])
        conn.execute("UPDATE iserv_calendars SET role='exam' WHERE account_id=1")
        # Next school year: same name, new address, the old one is gone.
        store._remember(conn, 1, [{"url": "https://s/caldav/n/klausuren-2026/", "name": "Klausuren 8D"}])
    rows = {c["url"]: c for c in store.calendars(1)}
    assert rows["https://s/caldav/n/klausuren-2026/"]["role"] == "exam"
    assert rows["https://s/caldav/n/klausuren-2025/"]["missing_since"]


def test_the_same_exam_in_two_calendars_appears_once(env):
    with closing(db.webapp_conn()) as conn, conn:
        ids = store._remember(conn, 1, [
            {"url": "https://s/a/", "name": "Klausuren 8D"},
            {"url": "https://s/b/", "name": "Klausuren Kurs"},
        ])
        conn.execute("UPDATE iserv_calendars SET role='exam' WHERE account_id=1")
    for calendar_id in ids.values():
        store._store_events(1, calendar_id, [{
            "uid": f"u{calendar_id}", "summary": "Klausur Physik", "description": "", "location": "",
            "start_date": "2026-09-17", "end_date": "2026-09-17", "start_time": "08:00",
            "end_time": "09:30", "all_day": False,
        }], date(2026, 9, 1), date(2026, 10, 1))
    found = store.events(1, "2026-09-01", "2026-10-01")
    assert len(found) == 1 and found[0]["summary"] == "Klausur Physik"


def test_roles_and_listing_are_parent_only(env):
    client_env, state, _ = env
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    with TestClient(app) as client:
        body = client.get(URL).json()
        assert body["roles"] == list(store.ROLES)
        assert body["access_configured"] is False
        with closing(db.webapp_conn()) as conn, conn:
            store._remember(conn, 1, [{"url": "https://s/a/", "name": "Klausuren 8D"}])
        calendar_id = store.calendars(1)[0]["id"]
        assert client.put(f"{URL}/{calendar_id}/role", json={"role": "exam"}).status_code == 200
        assert store.calendars(1)[0]["role"] == "exam"
        assert client.put(f"{URL}/{calendar_id}/role", json={"role": "quatsch"}).status_code == 422

        from tests.test_learning import child
        child(state)
        assert client.get(URL).status_code == 403


PLUGIN_ANSWER = [
    {"id": "exam-plan-exam-17865", "title": "Spanischarbeit n°1 (Klausur) - Klasse8D",
     "start": "2026-09-24T07:50:00+02:00", "end": "2026-09-24T09:25:00+02:00", "allDay": False,
     "displayFields": [{"text": "Klasse8D", "label": "Gruppen"}, {"text": None, "label": "Beschreibung"}]},
    {"id": "holiday-1", "title": "Herbstferien", "start": "2026-10-12T02:00:00+02:00",
     "end": "2026-10-25T02:00:00+02:00", "allDay": True, "displayFields": []},
    {"id": "spaeter", "title": "Weit weg", "start": "2027-09-01T08:00:00+02:00",
     "end": "2027-09-01T09:00:00+02:00", "allDay": False},
]


def test_the_exam_plugin_is_read_because_caldav_cannot_see_it(monkeypatch):
    from backend import iserv_portal

    async def answer(client, url):
        assert "start=2026-09-01" in url and "end=2026-10-31" in url
        return PLUGIN_ANSWER

    class Session:
        async def aclose(self):
            return None

    async def login(*args, **kwargs):
        return Session()

    monkeypatch.setattr(iserv_portal, "login", login)
    monkeypatch.setattr(iserv_portal, "_json", answer)
    events = asyncio.run(iserv_portal.plugin_events(
        "https://beispiel-iserv.de", "kind", "geheim",
        "https://beispiel-iserv.de/iserv/calendar4/plugin?plugin=exam-plan",
        date(2026, 9, 1), date(2026, 10, 31)))
    by_uid = {e["uid"]: e for e in events}
    # Outside the window it does not belong in the store.
    assert "spaeter" not in by_uid
    exam = by_uid["exam-plan-exam-17865"]
    assert exam["start_date"] == "2026-09-24" and exam["start_time"] == "07:50"
    assert exam["all_day"] is False and "Gruppen: Klasse8D" in exam["description"]
    holiday = by_uid["holiday-1"]
    assert holiday["all_day"] is True and holiday["start_time"] is None
    assert holiday["start_date"] == "2026-10-12" and holiday["end_date"] == "2026-10-25"


def test_a_foreign_plugin_address_is_refused():
    from backend import iserv_portal
    from backend.iserv_connector import IservLoginError

    import pytest

    with pytest.raises(IservLoginError):
        asyncio.run(iserv_portal.plugin_events(
            "https://beispiel-iserv.de", "kind", "geheim",
            "https://fremd.example/iserv/calendar4/plugin?plugin=exam-plan",
            date(2026, 9, 1), date(2026, 10, 1)))


def test_the_exam_plan_counts_as_exams_without_being_asked(env):
    from contextlib import closing as _closing

    with _closing(db.webapp_conn()) as conn, conn:
        store._remember(conn, 1, [
            {"url": "https://beispiel-iserv.de/iserv/calendar4/plugin?plugin=exam-plan", "name": "Klausurplan"},
            {"url": "https://beispiel-iserv.de/iserv/calendar4/plugin?plugin=holiday", "name": "Ferien & Feiertage"},
            {"url": "https://beispiel-iserv.de/caldav/caldav.php/klasse8d/calendar/", "name": "Klasse8D"},
        ])
    roles = {c["name"]: c["role"] for c in store.calendars(1)}
    assert roles["Klausurplan"] == "exam"
    assert roles["Ferien & Feiertage"] == "other"
    # A plain collection still waits for the parents to decide.
    assert roles["Klasse8D"] == "unused"
