"""Archiv nach der Arbeit (D182)."""
import json
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, child  # noqa: F401
from test_mentor import setup, B  # noqa: F401
from backend import db, learning_archive as la

TODAY = date(2026, 9, 25)


def test_rules():
    exam = date(2026, 9, 24)
    assert la.is_archived({"topic_id": 1}, exam, TODAY) == (True, "Arbeit am 24.09. geschrieben")
    assert not la.is_archived({"topic_id": 1}, exam, date(2026, 9, 24))[0], "am Tag der Arbeit noch da"
    assert la.is_archived({"topic_id": 1, "unarchived_at": "2026-09-25"}, exam, TODAY) == (False, "")
    hw = {"mode": "homework_help", "task_status": "done", "task_completed_at": "2026-09-20T10:00", "last_at": "2026-09-24"}
    assert la.is_archived(hw, None, TODAY)[0]
    hw = {"mode": "homework_help", "task_status": "open", "task_due": "2026-09-22", "last_at": "2026-09-24"}
    assert not la.is_archived(hw, None, TODAY)[0], "drei Tage Karenz"
    assert la.is_archived(hw, None, date(2026, 9, 26))[0]
    idle = {"mode": "practice", "last_at": "2026-09-10T12:00"}
    assert not la.is_archived(idle, None, date(2026, 9, 23))[0]
    assert la.is_archived(idle, None, TODAY)[0]
    assert not la.is_archived({**idle, "unarchived_at": "2026-09-24"}, None, TODAY)[0]


def test_dashboard_splits_and_unarchive_brings_back(setup):
    client, state, patch = setup
    from backend.routers import mentor as m
    patch.setattr(m, "today_local", lambda: TODAY)
    with closing(db.webapp_conn()) as c, c:
        c.execute("CREATE TABLE IF NOT EXISTS exam_dates(account_id INTEGER NOT NULL, exam_key TEXT NOT NULL, exam_date TEXT NOT NULL, PRIMARY KEY(account_id, exam_key))")
        c.execute("INSERT INTO exam_dates VALUES(1,'de','2026-09-24')")
        tid = c.execute("INSERT INTO exam_topics(account_id,subject,exam_key,title,created_at,updated_at) VALUES(1,'Deutsch','de','Nominalisierung','t','t')").lastrowid
        for goal, topic, updated in (("Alt", tid, "2026-09-22T10:00"), ("Frisch", None, "2026-09-24T10:00")):
            c.execute("INSERT INTO mentor_sessions(account_id,user_id,subject,goal,status,phase,source_json,created_at,updated_at,is_test,topic_id) "
                      "VALUES(1,2,'Deutsch',?,'active','clarify',?,?,?,0,?)", (goal, json.dumps({"mode": "topic" if topic else "practice"}), updated, updated, topic))
    child(state)
    d = client.get(B).json()
    assert [s["goal"] for s in d["sessions"]] == ["Frisch"]
    assert [(s["goal"], s["archive_reason"]) for s in d["archived_sessions"]] == [("Alt", "Arbeit am 24.09. geschrieben")]
    sid = d["archived_sessions"][0]["id"]
    assert client.post(B + f"/sessions/{sid}/unarchive").status_code == 200
    d = client.get(B).json()
    assert {s["goal"] for s in d["sessions"]} == {"Frisch", "Alt"} and d["archived_sessions"] == []
