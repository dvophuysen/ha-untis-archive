"""Der Wochenrückblick: Sätze aus gespeicherten Zahlen, kein Modell, keine Note."""
import asyncio
import sqlite3
from contextlib import closing
from datetime import date

from test_learning import env, child
from test_day_close import LESSON_COLUMNS
from backend import db, week_review
from backend.routers import week_review as routes

TODAY = date(2026, 9, 17)   # Donnerstag


def seed(patch):
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f'CREATE TABLE IF NOT EXISTS lessons({LESSON_COLUMNS})')
        for i, day in enumerate(['2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17', '2026-09-18', '2026-09-10', '2026-09-11'], start=1):
            c.execute('INSERT INTO lessons(id,account_id,date,start_time,end_time,subject_name,code,was_absent) VALUES(?,1,?,800,845,?,NULL,0)',
                      (i, day, 'Mathematik'))
    with closing(db.webapp_conn()) as c, c:
        c.executescript(
            "INSERT INTO day_closures VALUES(1,'2026-09-13','2026-09-13T17:00','erledigt',0,0,0,0);"
            "INSERT INTO day_closures VALUES(1,'2026-09-14','2026-09-14T20:00','erledigt',1,0,0,0);"
            "INSERT INTO day_closures VALUES(1,'2026-09-15','2026-09-15T19:00','erledigt',0,0,0,0);"
            "INSERT INTO day_closures VALUES(1,'2026-09-09','2026-09-09T19:00','erledigt',0,0,0,0);"
            "INSERT INTO exam_topics(id,account_id,subject,exam_key,position,title,stage,created_at,updated_at) VALUES"
            " (1,1,'LATEIN','cal:l',1,'a-/o-Deklination','sitzt','2026-09-10','2026-09-10'),"
            " (2,1,'LATEIN','cal:l',2,'Konjugation','wackelt','2026-09-10','2026-09-10'),"
            " (3,1,'Mathematik','cal:m',1,'Brüche kürzen','gefestigt','2026-09-10','2026-09-10');"
            "INSERT INTO topic_events(account_id,topic_id,stage_before,stage_after,reason,created_at) VALUES"
            " (1,1,'wackelt','sitzt','3 Aufgaben in 2 Arten','2026-09-15T16:00:00'),"
            " (1,2,'sitzt','wackelt','bei der Prüfung mit Hinweis','2026-09-16T16:00:00'),"
            " (1,3,'sitzt','gefestigt','Prüfung nach 7 Tagen bestanden','2026-09-16T17:00:00'),"
            " (1,1,'neu','wackelt','','2026-09-08T16:00:00');"
            "INSERT INTO mentor_sessions(account_id,user_id,subject,goal,status,elapsed_seconds,created_at,updated_at,is_test,is_demo) VALUES"
            " (1,2,'LATEIN','Deklination','completed',900,'2026-09-15T15:00','2026-09-15T15:20',0,0),"
            " (1,2,'Mathematik','Brüche','completed',600,'2026-09-16T15:00','2026-09-16T15:12',0,0),"
            " (1,1,'Mathematik','Demo','completed',600,'2026-09-16T15:00','2026-09-16T15:12',0,1),"
            " (1,2,'LATEIN','Vorwoche','completed',600,'2026-09-10T15:00','2026-09-10T15:12',0,0),"
            " (1,2,'LATEIN','offen','active',60,'2026-09-17T15:00','2026-09-17T15:01',0,0);"
            # Gezählt wird, worin das Kind in der Woche geschrieben hat; die
            # offene Einheit 5 wurde nur geöffnet.
            "INSERT INTO mentor_messages(account_id,session_id,request_key,role,text,created_at) VALUES"
            " (1,1,'r1','user','x','2026-09-15T15:05'),(1,2,'r2','user','x','2026-09-16T15:05'),"
            " (1,3,'r3','user','x','2026-09-16T15:05'),(1,4,'r4','user','x','2026-09-10T15:05'),"
            " (1,5,'r5','assistant','Hallo','2026-09-17T15:00');"
            "INSERT INTO tasks(account_id,title,status,source,due_date,completed_at,created_at,updated_at) VALUES"
            " (1,'Erledigt A','done','manual','2026-09-15','2026-09-14T18:00','now','now'),"
            " (1,'Erledigt B','done','manual','2026-09-16','2026-09-15T18:00','now','now'),"
            " (1,'Alt erledigt','done','manual','2026-09-10','2026-09-09T18:00','now','now'),"
            " (1,'Überfällig','open','manual','2026-09-16',NULL,'now','now'),"
            " (1,'Kommt noch','open','manual','2026-09-22',NULL,'now','now');"
            "INSERT INTO afternoon_checks(account_id,school_day,answer,created_at) VALUES"
            " (1,'2026-09-14','photo','now'),(1,'2026-09-14','photo','now'),(1,'2026-09-15','nothing','now');"
            "INSERT INTO mentor_ai_calls(id,account_id,purpose,month,day,model,status,reserved_micro,charged_micro,input_rate,output_rate,created_at) VALUES"
            " ('a',1,'mentor','2026-09','2026-09-15','test','settled',900000,410000,10,45,'now'),"
            " ('b',1,'mentor','2026-09','2026-09-16','test','reserved',300000,0,10,45,'now'),"
            " ('c',1,'mentor','2026-09','2026-09-10','test','settled',900000,900000,10,45,'now'),"
            " ('d',2,'mentor','2026-09','2026-09-16','test','settled',900000,900000,10,45,'now');")

    async def exams(account_id, **kw):
        return {"exams": [{"exam_key": "cal:l", "subject_name": "LATEIN", "date": "2026-09-21", "title": "Latein"},
                          {"exam_key": "cal:m", "subject_name": "Mathematik", "date": "2026-09-25", "title": "Mathe"}]}
    patch.setattr("backend.exams.resolve_exams", exams)
    patch.setattr("backend.sources.photo_requests", lambda account_id, found, day: [
        {"subject": "LATEIN", "exam_date": "2026-09-21", "label": "Begleitband", "pages_label": "S. 13"}])


def test_the_review_puts_the_weeks_numbers_into_plain_sentences(env):
    client, state, patch = env
    seed(patch)
    view = asyncio.run(week_review.review(1, TODAY))
    assert view["week"] == {"start": "2026-09-14", "end": "2026-09-20", "label": "14.09. bis 20.09."}
    # Abende vor einem Schultag: So, Mo, Di, Mi; der heutige Do ist noch nicht vorbei
    # und zählt erst, wenn er abgeschlossen ist. Zwei ohne Erinnerung erledigt.
    assert view["evenings"]["current"]["evenings"] == 4 and view["evenings"]["current"]["own"] == 2
    assert view["evenings"]["previous"]["own"] == 1
    assert [u["title"] for u in view["stages"]["ups"]] == ["a-/o-Deklination", "Brüche kürzen"]
    assert [d["title"] for d in view["stages"]["downs"]] == ["Konjugation"] and view["stages"]["checks_passed"] == 1
    assert view["units"] == {"count": 2, "minutes": 25, "subjects": ["Latein", "Mathematik"]}
    assert view["homework"] == {"done": 2, "overdue": 1} and view["afternoon"] == {"days": 2, "photos": 2}
    assert view["costs_eur"] == 0.71     # 0,41 abgerechnet plus 0,30 reserviert; Vorwoche und anderes Konto zählen nicht
    assert view["material_missing"][0]["subject"] == "Latein" and view["exams_ahead"][0]["date"] == "2026-09-21"
    lines = view["lines"]
    assert lines[0] == "An 2 von 4 Abenden vor einem Schultag war vor der Erinnerung alles erledigt (Vorwoche 1 von 2)."
    assert lines[1] == "2 Themen eine Stufe weiter: a-/o-Deklination (sitzt), Brüche kürzen (gefestigt)."
    assert lines[2] == "1 Thema zurück: Konjugation (wackelt)."
    assert lines[3] == "1 Kurzprüfung nach Tagen bestanden (gefestigt)."
    assert lines[4] == "2 Einheiten mit dem Mentor, rund 25 Minuten, in Latein, Mathematik."
    assert lines[5] == "2 Aufgaben erledigt, 1 überfällig."
    assert lines[6] == "An 2 Tagen nach der Schule geantwortet, 2 Fotos."
    assert lines[7] == "Für Latein am 21.09. fehlt noch: Begleitband S. 13."
    assert lines[8] == "Mathematik am 25.09.: Material liegt vor."
    assert lines[9] == "KI-Kosten diese Woche: 0.71 € (Anrechnung, keine Rechnung)."
    assert not any(word in " ".join(lines) for word in ("Note", "Score", "%"))


def test_an_empty_week_says_so_without_inventing_anything(env):
    client, state, patch = env

    async def none(account_id, **kw):
        return {"exams": []}
    patch.setattr("backend.exams.resolve_exams", none)
    view = asyncio.run(week_review.review(1, TODAY))
    assert view["lines"] == ["In dieser Woche noch kein Abend vor einem Schultag.",
                             "Keine Einheit mit dem Mentor in dieser Woche.",
                             "0 Aufgaben erledigt.",
                             "KI-Kosten diese Woche: 0.00 € (Anrechnung, keine Rechnung)."]


def test_the_route_serves_child_and_parent_within_the_account(env):
    client, state, patch = env
    seed(patch)
    client.app.include_router(routes.router, prefix="/api")
    patch.setattr(routes, "today_local", lambda: TODAY)
    assert client.get("/api/accounts/1/week-review").json()["units"]["count"] == 2
    child(state)
    assert client.get("/api/accounts/1/week-review").status_code == 200
    assert client.get("/api/accounts/2/week-review").status_code == 403


def test_open_homework_help_counts_and_dont_know_and_rejected_calls_are_told_apart(env):
    """Hausaufgabenhilfe bleibt offen (D25) und zählt trotzdem; „Weiß ich
    nicht" ist kein Irrtum; ein abgelehnter Aufruf hat nichts gekostet."""
    client, state, patch = env
    seed(patch)
    with closing(db.webapp_conn()) as c, c:
        c.executescript(
            "INSERT INTO mentor_messages(account_id,session_id,request_key,role,text,created_at) VALUES"
            " (1,5,'r6','user','Wie geht Nr. 3?','2026-09-17T15:01');"
            "INSERT INTO vocab_words(id,account_id,subject,material_id,foreign_word,plain,created_at) VALUES"
            " (1,1,'LATEIN',1,'servus','servus','now');"
            "INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,created_at) VALUES"
            " (1,1,1,'from','Sklave','correct','2026-09-16T16:00'),(1,1,1,'from','','incorrect','2026-09-16T16:01'),"
            " (1,1,1,'from','Herr','incorrect','2026-09-16T16:02');"
            "INSERT INTO mentor_ai_calls(id,account_id,purpose,month,day,model,status,reserved_micro,charged_micro,input_rate,output_rate,created_at) VALUES"
            " ('e',1,'mentor','2026-09','2026-09-16','test','released',500000,0,10,45,'now');")
    view = asyncio.run(week_review.review(1, TODAY))
    assert view["units"]["count"] == 3
    assert "3 Vokabelabfragen, 1 davon richtig, 1× „Weiß ich nicht“." in view["lines"]
    assert view["costs_eur"] == 0.71
