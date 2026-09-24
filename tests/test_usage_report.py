"""Der Nutzungsbericht für Eltern: beschreibt, wie die App genutzt wurde,
bewertet nicht, und jede Auffälligkeit sagt, was die App nicht sieht."""
from contextlib import closing
from datetime import date, datetime
from zoneinfo import ZoneInfo

from test_learning import env, child  # noqa: F401
from test_week_review import TODAY, seed
from backend import db, usage_report
from backend.routers import usage as routes

BERLIN = ZoneInfo("Europe/Berlin")


def fill():
    with closing(db.webapp_conn()) as c, c:
        c.executescript(
            # Einheit 5 (offen) mit viel Hilfe: vier Hilfeanfragen in sechs Nachrichten,
            # spät am Abend, angemeldet als Kind (Konto 2).
            "INSERT INTO mentor_messages(account_id,session_id,request_key,role,text,payload,user_id,created_at) VALUES"
            " (1,5,'u1','user','Nr. 3?','{\"kind\":\"message\"}',2,'2026-09-17T22:10:00+02:00'),"
            " (1,5,'u2','user','kp','{\"kind\":\"hint\"}',2,'2026-09-17T22:12:00+02:00'),"
            " (1,5,'u3','user','und weiter?','{\"kind\":\"hint\"}',2,'2026-09-17T22:14:00+02:00'),"
            " (1,5,'u4','user','Beispiel','{\"kind\":\"example\"}',2,'2026-09-17T22:16:00+02:00'),"
            " (1,5,'u5','user','weiter','{\"kind\":\"hint\"}',2,'2026-09-17T22:18:00+02:00'),"
            " (1,5,'u6','user','ok','{\"kind\":\"answer\"}',2,'2026-09-17T22:20:00+02:00');"
            # Zwei Einheiten geöffnet, nie begonnen.
            "INSERT INTO mentor_sessions(account_id,user_id,subject,goal,status,created_at,updated_at,is_test,is_demo) VALUES"
            " (1,2,'ENGLISCH','x','active','2026-09-15T16:00:00+02:00','2026-09-15T16:00:00+02:00',0,0),"
            " (1,2,'DEUTSCH','x','active','2026-09-16T16:00:00+02:00','2026-09-16T16:00:00+02:00',0,0);"
            "INSERT INTO vocab_words(id,account_id,subject,material_id,foreign_word,plain,created_at) VALUES"
            " (1,1,'LATEIN',1,'servus','servus','now'),(2,1,'LATEIN',1,'dominus','dominus','now'),"
            " (3,1,'LATEIN',1,'villa','villa','now');")
        # 16 Mal schnell „Weiß ich nicht“, nur eines der Wörter später richtig.
        for i in range(16):
            c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,seconds,created_at) "
                      "VALUES(1,?,1,'from','','incorrect',1,?)", (1 + i % 3, f"2026-09-16T17:00:{i:02d}+02:00"))
        c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,seconds,created_at) "
                  "VALUES(1,1,1,'from','Sklave','correct',5,'2026-09-16T17:05:00+02:00')")


def test_the_report_describes_the_week_and_names_what_it_cannot_see(env):
    client, state, patch = env
    seed(patch)
    fill()
    view = usage_report.week(1, TODAY)
    assert view["week"]["start"] == "2026-09-14"
    titles = [w["title"] for w in view["warnings"]]
    assert "2 Mentor-Einheiten geöffnet, ohne eigene Antwort" in titles
    assert any(t.startswith("Viel Hilfe, keine Aufgabe ohne Hilfe gelöst") for t in titles)
    assert "Vokabeln schnell aufgedeckt, ohne dass sie später saßen" in titles
    assert "Nutzung spät am Abend oder früh am Morgen" in titles
    assert all(w["unseen"] and w["meaning"] and w["evidence"] for w in view["warnings"])
    unit = next(u for u in view["mentor"]["units"] if u["session_id"] == 5)
    assert (unit["turns"], unit["help"], unit["own_evidence"]) == (6, 4, 0)
    assert view["vocab"]["dont_know"] == 16 and view["vocab"]["revealed_later_correct"] == 1
    assert view["vocab"]["fast_series"] == 16
    assert "Auffälligkeiten" in view["headline"]
    text = " ".join(view["lines"]) + " ".join(w["title"] for w in view["warnings"])
    assert not any(word in text for word in ("Note", "Score", "Punkte", "Rang"))


def test_late_hours_count_only_on_the_childs_own_login(env):
    """Eltern prüfen abends auf ihrem Gerät: Das ist keine späte Nutzung des Kindes.
    Ohne Kontoangabe (ältere Zeilen, Abgleich aus HA) gibt es ebenfalls keinen Hinweis."""
    client, state, patch = env
    seed(patch)
    with closing(db.webapp_conn()) as c, c:
        c.executescript(
            "INSERT INTO mentor_messages(account_id,session_id,request_key,role,text,payload,user_id,created_at) VALUES"
            " (1,5,'p1','user','Bitte bewerten','{}',1,'2026-09-17T00:08:00+02:00'),"
            " (1,5,'p2','user','Meine Seiten ansehen','{}',1,'2026-09-17T00:16:00+02:00'),"
            " (1,5,'o1','user','alt','{}',NULL,'2026-09-16T23:30:00+02:00'),"
            " (1,5,'k1','user','Nr. 1','{}',2,'2026-09-16T16:00:00+02:00');")
        c.execute("INSERT INTO tasks(id,account_id,title,task_type,status,source,completed_at,created_at,updated_at) "
                  "VALUES(90,1,'Lesen','homework','done','ha_todo','2026-09-15T23:40:00+00:00','now','now')")
        c.execute("INSERT INTO audit_log(user_id,account_id,op_type,target_kind,target_id,label,created_at) "
                  "VALUES(2,1,'update','task',91,'Rechnen: open → done','2026-09-15T15:30:00+00:00')")
    view = usage_report.week(1, TODAY)
    assert view["late"] == []
    assert "Nutzung spät am Abend oder früh am Morgen" not in [w["title"] for w in view["warnings"]]
    days = {d["day"]: d for d in view["active_days"]}
    assert days["2026-09-17"]["parent"] == {"from": "00:08", "to": "00:16"} and days["2026-09-17"]["own"] is None
    assert days["2026-09-16"]["own"] == {"from": "16:00", "to": "16:00"}
    # Der Abgleich aus HA liefert keine Uhrzeit, das Abhaken in der App schon.
    assert "2026-09-16" not in days or days["2026-09-16"]["to"] != "01:40"
    assert days["2026-09-15"]["own"] == {"from": "17:30", "to": "17:30"}
    assert "17.09. 00:08–00:16 auf dem Elterngerät" in view["lines"][0]


def test_only_parents_see_the_report(env):
    client, state, patch = env
    seed(patch)
    client.app.include_router(routes.router, prefix="/api")
    patch.setattr(usage_report, "today_local", lambda: TODAY)
    assert client.get("/api/accounts/1/usage-week?day=2026-09-17").status_code == 200
    child(state)
    assert client.get("/api/accounts/1/usage-week").status_code == 403


def test_the_heartbeat_keeps_day_sums_per_actor_and_forgets_after_ninety_days(env):
    client, state, patch = env
    client.app.include_router(routes.router, prefix="/api")
    child(state)
    assert client.post("/api/usage/ping", json={"account_id": 1, "view": "today", "seconds": 60, "open": True}).status_code == 204
    assert client.post("/api/usage/ping", json={"account_id": 1, "view": "learning", "seconds": 999}).status_code == 422
    assert client.post("/api/usage/ping", json={"account_id": 1, "view": "../x", "seconds": 90}).status_code == 204
    assert client.post("/api/usage/ping", json={"account_id": 2, "view": "today", "seconds": 60}).status_code == 403
    with closing(db.webapp_conn()) as c:
        row = dict(c.execute("SELECT * FROM usage_days WHERE account_id=1").fetchone())
    assert row["actor"] == "child" and row["opens"] == 1 and row["active_seconds"] == 150
    assert '"sonst": 90' in row["views_json"] and '"today": 60' in row["views_json"]
    usage_report.record_ping(1, "child", "today", 60, False, now=datetime(2026, 5, 1, 12, tzinfo=BERLIN))
    assert usage_report.purge(date(2026, 9, 17)) == 1


def test_the_feed_for_home_assistant_needs_the_token(env):
    client, state, patch = env
    seed(patch)
    fill()
    client.app.include_router(routes.router, prefix="/api")
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO account_settings(account_id,default_daily_budget_minutes,notify_token,created_at,updated_at) "
                  "VALUES(1,60,'geheim','now','now')")
    assert client.get("/api/notify/1/usage-week?token=falsch").status_code == 401
    feed = client.get("/api/notify/1/usage-week?token=geheim&day=2026-09-17").json()
    assert feed["title"].startswith("Schul-Cockpit: Woche 14.09. bis 20.09.")
    assert "Auffällig: Nutzung spät am Abend" in feed["text"] and feed["warnings"] >= 3
