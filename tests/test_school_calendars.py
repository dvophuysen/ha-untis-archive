"""School calendars straight from IServ: repair, discovery, roles, merging."""

import asyncio
from contextlib import closing
from datetime import date


def _date_today():
    return date.today()

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_learning import env  # noqa: F401  (fixture)
from test_mentor import setup as mentor_setup  # noqa: F401  (fixture)
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
        "https://gaw-iserv.de/caldav/": '<d:multistatus xmlns:d="DAV:"><d:response><d:propstat><d:prop>'
                                        "<d:current-user-principal><d:href>/caldav/caldav.php/kind/</d:href>"
                                        "</d:current-user-principal></d:prop></d:propstat></d:response></d:multistatus>",
        "https://gaw-iserv.de/caldav/caldav.php/kind/": homes,
    }
    listings = {
        "https://gaw-iserv.de/caldav/caldav.php/kind/": collection("/caldav/caldav.php/kind/", "Kind", "Home"),
        "https://gaw-iserv.de/caldav/caldav.php/klasse8d/":
            collection("/caldav/caldav.php/klasse8d/", "Klasse8D", "Klasse8D Calendar"),
    }

    async def propfind(client, url, body, depth):
        text = listings[url] if depth == "1" else answers[url]
        return ElementTree.fromstring(text)

    monkeypatch.setattr(ical, "_propfind", propfind)
    found = asyncio.run(ical.discover("https://gaw-iserv.de", "kind", "x"))
    names = [c["name"] for c in found]
    # The class calendar comes along, the to-do list does not, and the stale
    # "<Gruppe> Calendar" label is replaced by the group name.
    assert names == ["Home", "Klasse8D"]


def test_discovery_reads_names_and_skips_non_calendars(monkeypatch):
    answer = """<?xml version="1.0"?>
    <d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"
                   xmlns:a="http://apple.com/ns/ical/">
      <d:response><d:href>/caldav/noah/</d:href><d:propstat><d:prop>
        <d:resourcetype><d:collection/></d:resourcetype><d:displayname>Home</d:displayname>
      </d:prop></d:propstat></d:response>
      <d:response><d:href>/caldav/noah/klausuren-8d/</d:href><d:propstat><d:prop>
        <d:resourcetype><d:collection/><c:calendar/></d:resourcetype>
        <d:displayname>Klausuren 8D</d:displayname><a:calendar-color>#ff0000</a:calendar-color>
      </d:prop></d:propstat></d:response>
      <d:response><d:href>/caldav/noah/aufgaben/</d:href><d:propstat><d:prop>
        <d:resourcetype><d:collection/><c:calendar/></d:resourcetype>
        <d:displayname>Aufgaben</d:displayname>
        <c:supported-calendar-component-set><c:comp name="VTODO"/></c:supported-calendar-component-set>
      </d:prop></d:propstat></d:response>
    </d:multistatus>"""
    from xml.etree import ElementTree

    async def propfind(client, url, body, depth):
        return ElementTree.fromstring(answer)

    monkeypatch.setattr(ical, "_propfind", propfind)
    found = asyncio.run(ical.discover("https://gaw-iserv.de", "noah", "x"))
    assert [c["name"] for c in found] == ["Klausuren 8D"]
    assert found[0]["url"].endswith("/caldav/noah/klausuren-8d/")


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
        "https://gaw-iserv.de", "kind", "geheim",
        "https://gaw-iserv.de/iserv/calendar4/plugin?plugin=exam-plan",
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
            "https://gaw-iserv.de", "kind", "geheim",
            "https://fremd.example/iserv/calendar4/plugin?plugin=exam-plan",
            date(2026, 9, 1), date(2026, 10, 1)))


def test_the_exam_plan_counts_as_exams_without_being_asked(env):
    from contextlib import closing as _closing

    with _closing(db.webapp_conn()) as conn, conn:
        store._remember(conn, 1, [
            {"url": "https://gaw-iserv.de/iserv/calendar4/plugin?plugin=exam-plan", "name": "Klausurplan"},
            {"url": "https://gaw-iserv.de/iserv/calendar4/plugin?plugin=holiday", "name": "Ferien & Feiertage"},
            {"url": "https://gaw-iserv.de/caldav/caldav.php/klasse8d/calendar/", "name": "Klasse8D"},
        ])
    roles = {c["name"]: c["role"] for c in store.calendars(1)}
    assert roles["Klausurplan"] == "exam"
    assert roles["Ferien & Feiertage"] == "other"
    # A plain collection still waits for the parents to decide.
    assert roles["Klasse8D"] == "unused"


def test_a_subject_written_into_one_word_still_matches():
    from backend.exams import match_subject

    amap = {
        "spanisch": {"subject_name": "SPANISCH", "subject_untis_id": 1, "multiword": False},
        "englisch": {"subject_name": "ENGLISCH", "subject_untis_id": 2, "multiword": False},
        "ku": {"subject_name": "KUNST", "subject_untis_id": 3, "multiword": False},
        "werte und normen": {"subject_name": "Werte und Normen", "subject_untis_id": 4, "multiword": True},
    }
    status, subs = match_subject("Spanischarbeit n°1 (Klausur) - Klasse8D", amap)
    assert status == "auto" and subs[0]["subject_name"] == "SPANISCH"
    status, subs = match_subject("Englischarbeit Nr. 1 (Klausur)", amap)
    assert status == "auto" and subs[0]["subject_name"] == "ENGLISCH"
    # A Kürzel stays exact, otherwise it claims every word that starts alike.
    assert match_subject("Kuchenverkauf in der Pause", amap)[0] == "unmatched"
    assert match_subject("Arbeit in Ku", amap)[1][0]["subject_name"] == "KUNST"
    assert match_subject("Klausur Werte und Normen", amap)[1][0]["subject_name"] == "Werte und Normen"


def test_a_date_already_in_the_exam_plan_cannot_be_entered_by_hand(env, monkeypatch):
    from contextlib import closing as _closing
    from backend.routers import exams as exam_routes

    client_env, state, _ = env
    app = FastAPI()
    app.include_router(exam_routes.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    with _closing(db.webapp_conn()) as conn, conn:
        ids = store._remember(conn, 1, [{
            "url": "https://gaw-iserv.de/iserv/calendar4/plugin?plugin=exam-plan",
            "name": "Klausurplan"}])
    store._store_events(1, list(ids.values())[0], [{
        "uid": "exam-plan-exam-1", "summary": "Physik (Klausur) - Klasse8D", "description": "",
        "location": "", "start_date": "2026-11-26", "end_date": "2026-11-26",
        "start_time": "11:35", "end_time": "12:20", "all_day": False,
    }], date(2026, 11, 1), date(2026, 12, 1))
    from backend import exams as exam_logic
    monkeypatch.setattr(exam_logic, "build_alias_map", lambda account: {
        "physik": {"subject_name": "PHYSIK", "subject_untis_id": 7, "multiword": False}})
    with TestClient(app) as client:
        same = client.post("/api/accounts/1/manual-exams", json={
            "exam_date": "2026-11-26", "subject_name": "PHYSIK"})
        assert same.status_code == 409, same.text
        assert "Klausurplan" in same.json()["detail"]
        # A date the plan does not carry is exactly what the hand entry is for.
        other = client.post("/api/accounts/1/manual-exams", json={
            "exam_date": "2026-12-19", "subject_name": "PHYSIK", "title": "Nachschreibtermin"})
        assert other.status_code == 201, other.text


def test_closing_a_school_year_hides_it_without_losing_it(env, monkeypatch):
    from datetime import date as _date
    from backend.routers import exams as exam_routes

    client_env, state, _ = env
    app = FastAPI()
    app.include_router(exam_routes.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user

    entries = [
        {"source": "manual", "exam_key": "manual:1", "date": "2026-06-17",
         "subject_name": "MATHEMATIK", "title": "MATHEMATIK", "status": "manual"},
        {"source": "manual", "exam_key": "manual:2", "date": "2026-09-02",
         "subject_name": "DEUTSCH", "title": "DEUTSCH", "status": "manual"},
    ]

    async def stub(account_id, **kwargs):
        return {"exams": list(entries), "calendar_error": None, "entity_id": None}

    monkeypatch.setattr(exam_routes, "resolve_exams", stub)
    # The exam stage only decides how a grade is spelled; not what is tested here.
    from backend import erlass
    monkeypatch.setattr(erlass, "resolve_section", lambda account: ("sek1", "8D", "test"))
    with TestClient(app) as client:
        before = client.get("/api/accounts/1/exams/all").json()
        assert {e["date"] for e in before["past"]} == {"2026-06-17", "2026-09-02"}
        assert before["archived_count"] == 0
        # The school year starts on 1 August, so only June is closed.
        assert before["school_year_start"] == exam_routes.school_year_start(_date.today()).isoformat()
        done = client.post("/api/accounts/1/exams/archive", json={})
        assert done.status_code == 200, done.text
        assert done.json()["archive_before"] == before["school_year_start"]
        after = client.get("/api/accounts/1/exams/all").json()
        assert {e["date"] for e in after["past"]} == {"2026-09-02"}
        assert after["archived_count"] == 1
        # Nothing is gone, it only moved out of the way.
        archived = client.get("/api/accounts/1/exams/archive").json()
        assert [e["date"] for e in archived["exams"]] == ["2026-06-17"]
        client.post("/api/accounts/1/exams/archive", json={"clear": True})
        assert client.get("/api/accounts/1/exams/all").json()["archived_count"] == 0


def test_the_school_year_starts_in_august():
    from datetime import date as _date
    from backend.routers.exams import school_year_start

    assert school_year_start(_date(2026, 9, 14)) == _date(2026, 8, 1)
    assert school_year_start(_date(2026, 7, 31)) == _date(2025, 8, 1)
    assert school_year_start(_date(2027, 1, 5)) == _date(2026, 8, 1)


def test_practice_is_counted_only_within_the_window(env):
    from contextlib import closing as _closing
    from datetime import timedelta as _td
    from backend.routers.exams import practice_by_subject

    today = _date_today()
    with _closing(db.webapp_conn()) as conn, conn:
        for when, subject in (
            (today - _td(days=3), 'PHYSIK'),
            (today - _td(days=200), 'PHYSIK'),
            (today - _td(days=200), 'MUSIK'),
        ):
            conn.execute(
                "INSERT INTO mentor_sessions(account_id,user_id,subject,goal,max_minutes,"
                "created_at,updated_at,is_test,is_demo) VALUES(1,2,?,'Üben',10,?,?,0,0)",
                (subject, when.isoformat(), when.isoformat()))
    found = practice_by_subject(1)
    assert found['physik']['units'] == 1
    # Was nur weit vor dem Fenster liegt, taucht gar nicht erst auf.
    assert 'musik' not in found
    assert found['physik']['days'] == 60


def test_the_scope_of_an_exam_starts_after_the_previous_one(env):
    from datetime import date as _d
    from backend.routers.exams import scope_start

    entries = [
        {"subject_name": "MATHEMATIK", "date": "2026-09-30"},
        {"subject_name": "MATHEMATIK", "date": "2026-11-20"},
        {"subject_name": "DEUTSCH", "date": "2026-10-10"},
    ]
    # Die zweite Arbeit beginnt bei der ersten desselben Fachs.
    assert scope_start("MATHEMATIK", "2026-11-20", entries) == "2026-09-30"
    # Die erste beginnt beim Schuljahr, nicht bei einer Arbeit eines anderen Fachs.
    assert scope_start("MATHEMATIK", "2026-09-30", entries) == "2026-08-01"
    assert scope_start("DEUTSCH", "2026-10-10", entries) == "2026-08-01"
    # Eine Arbeit im Frühjahr zählt weiterhin ab dem vorigen August.
    assert scope_start("KUNST", "2027-03-05", entries) == "2026-08-01"
    # Eine Arbeit aus dem vorigen Schuljahr öffnet kein Fenster über die Ferien.
    alt = [{"subject_name": "SPANISCH", "date": "2026-06-11"}]
    assert scope_start("SPANISCH", "2026-09-24", alt) == "2026-08-01"


def test_a_taught_topic_counts_as_scope_until_it_is_shown(mentor_setup):
    from contextlib import closing as _closing
    import sqlite3 as _sq
    from backend.routers import exams as exam_routes

    with _sq.connect(db.SETTINGS.history_db_path) as hist:
        hist.executescript(
            "CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY,account_id INTEGER,date TEXT,"
            "subject_name TEXT,subject_untis_id INTEGER,lstext TEXT,was_absent INTEGER);")
        hist.execute("INSERT INTO lessons(id,account_id,date,subject_name,lstext,was_absent) "
                     "VALUES(901,1,'2026-09-02','PHYSIK','Reihenschaltung',0)")
        hist.execute("INSERT INTO lessons(id,account_id,date,subject_name,lstext,was_absent) "
                     "VALUES(902,1,'2026-09-09','PHYSIK','Parallelschaltung',0)")
        # Vor dem Zeitraum unterrichtet, gehört also nicht zu dieser Arbeit.
        hist.execute("INSERT INTO lessons(id,account_id,date,subject_name,lstext,was_absent) "
                     "VALUES(903,1,'2026-06-02','PHYSIK','Ladungen',0)")
    with _closing(db.webapp_conn()) as c, c:
        pid = c.execute("SELECT id FROM learning_profiles WHERE account_id=1 AND active=1").fetchone()[0]
        ids = {}
        for lesson, title in ((901, "Reihenschaltung"), (902, "Parallelschaltung"), (903, "Ladungen")):
            tid = c.execute(
                "INSERT INTO learning_topics(profile_id,subject,title,objective,method,status,priority,"
                "source_note,created_at,updated_at) VALUES(?,'PHYSIK',?,'Ich kann das','explain','active',1,'','now','now')",
                (pid, title)).lastrowid
            ids[title] = tid
            c.execute("INSERT INTO learning_discovery_items(account_id,profile_id,lesson_id,fingerprint,topic_id,note) "
                      "VALUES(1,?,?,'x',?,'')", (pid, lesson, tid))
        skill = c.execute("INSERT INTO mentor_skills(account_id,subject,title,objective,created_at,updated_at) "
                          "VALUES(1,'PHYSIK','Reihenschaltung','Ich kann das','now','now')").lastrowid
        c.execute("INSERT INTO learning_plan_links VALUES(1,?,?)", ('discovered:' + str(ids['Reihenschaltung']), skill))
        c.execute("INSERT INTO mentor_evidence(account_id,skill_id,task_json,answer,result,rationale,"
                  "help_used,variant_hash,created_at) VALUES(1,?,'{}','richtig','correct','passend',0,'h','now')", (skill,))

    scope = exam_routes.exam_scope(1, 'PHYSIK', '2026-08-01', '2026-09-14')
    titles = {t['title']: t['shown'] for t in scope['topics']}
    assert titles == {'Reihenschaltung': True, 'Parallelschaltung': False}
    assert scope['parts'] == 2 and scope['shown'] == 1
    assert scope['verified'] is False
