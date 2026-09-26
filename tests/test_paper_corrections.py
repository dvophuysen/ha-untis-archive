"""Einmalige Berichtigungen ausgewerteter Übungsarbeiten (D218): Punkte, Posten
und Lernstand passen danach zusammen, und ein zweiter Lauf ändert nichts."""
import json
from contextlib import closing

from test_learning import env  # noqa: F401
from backend import db, lernstand

KEY = "fix_paper_d218_nachgerechnet"


def _task(points, most):
    return {"points": points, "earned": [{"text": "x", "points": points}],
            "lost": [{"points": most - points, "kind": "rechenfehler", "why": "", "fix": ""}] if most > points else [],
            "rationale": "", "uncertain": False}


def _seed(c, acc, aid, feedback, answers):
    eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,created_at,status,exam_key,paper_format) "
                    "VALUES(?,'Ü','Mathematik','{}','[]',30,'t','published','k','kurz')", (acc,)).lastrowid
    c.execute("INSERT INTO mentor_exam_attempts(id,account_id,exam_id,user_id,snapshot,feedback_json,started_at,status,is_test) "
              "VALUES(?,?,?,2,'{}',?,'t','graded',0)", (aid, acc, eid, json.dumps(feedback)))
    for tid, afb, pts, most in answers:
        c.execute("INSERT OR IGNORE INTO exam_topics(id,account_id,subject,exam_key,title,stage,created_at,updated_at) "
                  "VALUES(?,?,'Mathematik','k',?,'sitzt','t','t')", (tid, acc, f"T{tid}"))
        c.execute("INSERT INTO topic_answers(account_id,topic_id,session_id,task_kind,result,help_used,re_explained,afb,task_form,"
                  "created_at,points,max_points,attempt_id,source) VALUES(?,?,?,'',?,0,0,?,'','2026-09-26T12:00:00+02:00',?,?,?,'paper')",
                  (acc, tid, -aid, "correct" if pts / most >= 0.8 else "partial", afb, pts, most, aid))


def test_both_gradings_are_corrected_consistently_and_only_once(env):
    most1, most2 = [3, 3, 4], [6, 7, 5, 8]
    with closing(db.webapp_conn()) as c, c:
        n1 = _task(2.0, 3)
        n1["lost"][0]["kind"] = "nicht_bearbeitet"
        _seed(c, 1, 6, {"0": _task(2.5, 3), "1": n1, "2": _task(4, 4)},
              [(12, 1, 2.5, 3), (12, 1, 2.0, 3), (12, 2, 4, 4)])
        _seed(c, 2, 4, {"0": _task(6, 6), "1": _task(5.5, 7), "2": _task(5, 5), "3": _task(3.0, 8)},
              [(24, 1, 6, 6), (25, 1, 5.5, 7), (24, 2, 5, 5), (25, 2, 3, 8)])
        sql = dict(db._MIGRATIONS)[KEY]
        db._run_migration(c, sql)
        first = {r[0]: json.loads(r[1]) for r in c.execute("SELECT id,feedback_json FROM mentor_exam_attempts")}
        db._run_migration(c, sql)
        again = {r[0]: json.loads(r[1]) for r in c.execute("SELECT id,feedback_json FROM mentor_exam_attempts")}
        assert again == first, "ein zweiter Lauf ändert nichts"
        for aid, most in ((6, most1), (4, most2)):
            fb = first[aid]
            for i, m in enumerate(most):
                t = fb[str(i)]
                assert sum(x["points"] for x in t["earned"]) == t["points"]
                assert sum(x["points"] for x in t["lost"]) == m - t["points"]
                assert all(x["kind"] in ("nicht_bearbeitet", "unvollstaendig", "rechenweg", "rechenfehler", "form") for x in t["lost"])
        assert sum(first[6][str(i)]["points"] for i in range(3)) == 8
        assert sum(first[4][str(i)]["points"] for i in range(4)) == 16
        assert first[4]["2"]["loesung_falsch"] is True
        from backend.feedback import loss_summary
        assert loss_summary(first[4]) == first[4]["losses"]
        assert {x["kind"]: x["points"] for x in first[6]["losses"]} == {"unvollstaendig": 1.0, "nicht_bearbeitet": 1.0}
        answers = sorted((r[0], r[1], r[2], r[3], r[4]) for r in c.execute(
            "SELECT attempt_id,topic_id,afb,points,result FROM topic_answers"))
        assert answers == [(4, 24, 1, 6, "correct"), (4, 24, 2, 4, "correct"), (4, 25, 1, 5, "partial"), (4, 25, 2, 1, "partial"),
                           (6, 12, 1, 2, "partial"), (6, 12, 1, 2, "partial"), (6, 12, 2, 4, "correct")]
        assert sorted(r[0] for r in c.execute("SELECT topic_id FROM topic_recheck")) == [12, 24, 25]
        assert lernstand.heal(c) == 3
