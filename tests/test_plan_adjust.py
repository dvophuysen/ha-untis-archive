"""Eltern passen den Lernplan an (D214): weniger, mehr, streichen, hinzufügen,
zurücksetzen; Hinzugefügtes zählt als Pflicht, Gestrichenes nie als versäumt."""
from datetime import timedelta
from types import SimpleNamespace

from test_learning import env  # noqa: F401
from test_study_plan import world, exam, MON  # noqa: F401
from backend import plan_adjust as pa, study_plan as sp
from backend.auth import CurrentUser


def keys(steps):
    return [s["key"] for s in steps]


def test_less_more_drop_add_and_reset_on_a_frozen_day(world):
    exam("ma", "Mathematik", MON + timedelta(days=1), ["Gleichungen", "Wertetabellen"])
    exam("mu", "Musik", MON + timedelta(days=9), ["Noten"])
    raw = sp.ensure(1, MON)
    assert raw and sp.open_count(1, MON) == len(raw)
    st = pa.change(1, MON, MON, "less", None, 1)
    assert keys(sp.stored(1, MON)) == keys(raw)[:-1] and st["open"] == len(raw) - 1
    assert sp.open_count(1, MON) == len(raw) - 1, "Gestrichenes zählt nicht als offen"
    assert st["changes"][0]["action"] == "drop" and st["changes"][0]["title"] == raw[-1]["title"]
    first = st["candidates"][0]
    assert first["key"] == raw[-1]["key"], "das Gestrichene steht zuerst zum Wiederaufnehmen da"
    st = pa.change(1, MON, MON, "more", None, 1)
    now = sp.stored(1, MON)
    assert keys(now) == keys(raw) and now[-1]["by_parent"], "mehr holt den gestrichenen Schritt zurück"
    extra = next(c for c in st["candidates"] if c["subject"] == "Musik")
    pa.change(1, MON, MON, "add", extra["key"], 1)
    assert keys(sp.stored(1, MON))[-1] == extra["key"] and sp.open_count(1, MON) == len(raw) + 1, "zählt als Pflicht"
    pa.change(1, MON, MON, "drop", raw[0]["key"], 1)
    assert raw[0]["key"] not in keys(sp.stored(1, MON))
    view = sp.view(1, MON, store=False)
    assert any(s["by_parent"] for s in view["steps"]), "das Kind sieht, was die Eltern hinzugefügt haben"
    pa.change(1, MON, MON, "reset", None, 1)
    assert keys(sp.stored(1, MON)) == keys(raw) and pa.rows(1, MON) == []


def test_a_count_for_tomorrow_becomes_steps_when_the_day_is_fixed(world):
    exam("ma", "Mathematik", MON + timedelta(days=3), ["Gleichungen", "Wertetabellen", "Terme"])
    tue = MON + timedelta(days=1)
    preview = sp.compute(1, tue)
    st = pa.change(1, tue, MON, "less", None, 1)
    assert not st["frozen"] and st["total"] == len(preview) - 1
    assert [r["action"] for r in pa.rows(1, tue)] == ["less"]
    raw = sp.ensure(1, tue)
    assert [r["action"] for r in pa.rows(1, tue)] == ["drop"], "beim Festhalten ein bestimmter Schritt"
    assert len(raw) == len(sp.stored_raw(1, tue)) - 1


def test_only_parents_and_only_today_and_the_next_school_day(env, world, monkeypatch):
    client, state, patch = env
    from backend.routers import study_plan as routes
    client.app.include_router(routes.router, prefix="/api")
    monkeypatch.setattr(routes, "today_local", lambda: MON)
    exam("ma", "Mathematik", MON + timedelta(days=2), ["Gleichungen"])
    body = client.get("/api/accounts/1/study-plan/adjust").json()
    assert [d["day"] for d in body["days"]] == [MON.isoformat(), (MON + timedelta(days=1)).isoformat()]
    assert body["days"][0]["label"] == "Heute" and body["days"][1]["label"].startswith("Nächster Schultag, Dienstag")
    r = client.post("/api/accounts/1/study-plan/adjust", json={"day": (MON + timedelta(days=5)).isoformat(), "action": "less"})
    assert r.status_code == 400
    r = client.post("/api/accounts/1/study-plan/adjust", json={"day": MON.isoformat(), "action": "drop"})
    assert r.status_code == 422
    r = client.post("/api/accounts/1/study-plan/adjust", json={"day": MON.isoformat(), "action": "less"})
    assert r.status_code == 200 and r.json()["label"] == "Heute"
    state.user = CurrentUser(2, "test-2", "Test", "child", False, "pin")
    assert client.post("/api/accounts/1/study-plan/adjust", json={"day": MON.isoformat(), "action": "more"}).status_code == 403
    assert client.get("/api/accounts/1/study-plan/adjust").status_code == 403


def test_on_the_weekend_the_friday_list_is_the_one_to_adjust(world):
    sat = MON + timedelta(days=5)
    days = pa.days(1, sat)
    assert [d["day"] for d in days] == [MON + timedelta(days=4), MON + timedelta(days=7)]
    assert days[0]["label"].startswith("Liste vom Freitag")
