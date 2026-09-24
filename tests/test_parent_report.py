"""Der Wochenbericht als Mitteilung an die Eltern: nur an Elterngeräte, zur
eingestellten Zeit, je Woche, Kind und Gerät höchstens einmal."""
from contextlib import closing
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from test_learning import env, child  # noqa: F401
from test_week_review import seed
from backend import app_notify, db, parent_report
from backend.routers import usage as routes

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.fixture
def sent(env, monkeypatch):
    client, state, patch = env
    seed(patch)
    calls = []
    monkeypatch.setattr(app_notify, "send", lambda service, title, message, url: calls.append((service, title, message)) or True)
    monkeypatch.setattr(app_notify, "own_panel", lambda: "/app")
    monkeypatch.setattr(app_notify, "services", lambda: ["mobile_app_eltern", "mobile_app_kind"])
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO reminder_app_targets(account_id,service) VALUES(1,'mobile_app_kind')")
    client.app.include_router(routes.router, prefix="/api")
    return client, state, calls


def test_child_devices_cannot_receive_the_report(sent):
    client, state, calls = sent
    r = client.put("/api/parent-report", json={"weekday": 6, "at": "18:00", "targets": ["mobile_app_kind"]})
    assert r.status_code == 422 and "Kindes" in r.json()["detail"]
    view = client.get("/api/parent-report").json()
    assert {"service": "mobile_app_kind", "child_device": True} in view["devices"]
    child(state)
    assert client.get("/api/parent-report").status_code == 403


def test_the_report_goes_out_once_a_week_at_the_set_time(sent):
    client, state, calls = sent
    assert client.put("/api/parent-report", json={"weekday": 6, "at": "18:00", "targets": ["mobile_app_eltern"]}).status_code == 200
    parent_report.run_once(datetime(2026, 9, 20, 17, 59, tzinfo=BERLIN))
    assert calls == []
    parent_report.run_once(datetime(2026, 9, 20, 18, 1, tzinfo=BERLIN))
    assert [c[0] for c in calls] == ["mobile_app_eltern", "mobile_app_eltern"]  # zwei Kinder
    assert calls[0][1].startswith("Woche 14.09. bis 20.09.: ") and "aktiv" in calls[0][2]
    parent_report.run_once(datetime(2026, 9, 20, 18, 5, tzinfo=BERLIN))
    assert len(calls) == 2, "nicht zweimal in derselben Woche"
    parent_report.run_once(datetime(2026, 9, 21, 18, 1, tzinfo=BERLIN))
    assert len(calls) == 2, "Montag ist kein Berichtstag"


def test_a_test_message_does_not_use_up_the_weekly_one(sent):
    client, state, calls = sent
    client.put("/api/parent-report", json={"weekday": 6, "at": "18:00", "targets": ["mobile_app_eltern"]})
    assert client.post("/api/parent-report/test").json()["sent"] == {"mobile_app_eltern": 2}
    parent_report.run_once(datetime(2026, 9, 20, 18, 1, tzinfo=BERLIN))
    assert len(calls) == 4
