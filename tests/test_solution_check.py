"""Qualitätssicherung der Musterlösungen (D217): rechnerisch und fachlich
geprüft, bevor ein Kind eine Arbeit bekommt; beim Bewerten zählt das Richtige.
Anlass: Kurztest mit 2x − 6 = 3 und der Musterlösung x = 4."""
import asyncio
import json

import pytest

from test_learning import env  # noqa: F401
from backend import ai_gateway as ai, solution_check as sc

pytestmark = pytest.mark.real_solution_check

WRONG = {"prompt": "Löse die Gleichung. Gib kurz die Umformungen an und die Lösung.\n\na) 2x - 6 = 3\nb) 3/4 x + 8 = 7\nc) 3 + 1,5x = 12",
         "solution": "a) 2x - 6 = 3  → +6  → 2x = 9  → :2  → x = 4\nb) 3/4 x + 8 = 7  → -8  → 3/4 x = -1  → : (3/4)  → x = -1 / (3/4) = -4/3 = -1,333...\n"
                     "c) 3 + 1,5x = 12  → -3  → 1,5x = 9  → :1,5  → x = 6",
         "criteria": "a) 1 P +6, 1 P :2, 1 P Ergebnis x=4; b) 1 P -8, 1 P :3/4, 1 P x=-4/3; c) 1 P -3, 1 P :1,5, 1 P x=6", "points": 9}
RIGHT = {**WRONG, "solution": WRONG["solution"].replace("x = 4\n", "x = 4,5\n"), "criteria": WRONG["criteria"].replace("x=4;", "x=4,5;")}


def test_the_calculator_finds_the_wrong_result_in_solution_and_criteria():
    issues = sc.math_issues(WRONG)
    assert [(x["teil"], x["stelle"]) for x in issues] == [("a", "Musterlösung"), ("a", "Kriterien")]
    assert "richtig ist x = 9/2 (≈ 4,5)" in issues[0]["text"]
    assert sc.math_issues(RIGHT) == [], "gerundetes -1,333… gilt als -4/3"


def test_the_calculator_reads_equations_in_sentences_and_stays_silent_when_unsure():
    probe = {"prompt": "Löse die Gleichung und prüfe die Lösung: 4·(x - 2) + 3 = 2·(x + 1) + x. Zeige alle Schritte.",
             "solution": "4x - 8 + 3 = 2x + 2 + x → 4x - 5 = 3x + 2 → x = 7", "criteria": "1 P Klammern; 1 P x = 7"}
    assert sc.math_issues(probe) == []
    assert sc.math_issues({**probe, "solution": probe["solution"].replace("x = 7", "x = 6")})[0]["richtig"] == "7"
    assert sc.solve_linear("x^2 = 4") is None and sc.solve_linear("2x = 2x") is None
    word = {"prompt": "Ein Fisch: Kopf ein Drittel, Schwanz ein Viertel, Mittelstück 10 Pfund.", "solution": "x = 24", "criteria": "x = 24"}
    assert sc.math_issues(word) == [], "Textaufgaben ohne Gleichung prüft die fachliche Prüfung"


def fake_checker(monkeypatch, *answers):
    calls = []

    async def complete(account_id, purpose, instruction, context, *a, **kw):
        calls.append(context)
        return json.dumps(answers[len(calls) - 1]), {}, "call"
    monkeypatch.setattr(ai, "complete", complete)
    return calls


def run(coro):
    return asyncio.run(coro)


def test_a_wrong_solution_is_corrected_and_checked_again(monkeypatch):
    calls = fake_checker(monkeypatch,
                         {"tasks": [{"nr": 1, "eigene_loesung": "x = 4,5 …", "ok": False, "fehler": "a) 9 : 2 = 4,5",
                                     "solution": RIGHT["solution"], "criteria": RIGHT["criteria"]}]},
                         {"tasks": [{"nr": 1, "eigene_loesung": "x = 4,5 …", "ok": True}]})
    out = run(sc.assure(1, "Mathematik", [WRONG]))
    assert out[0]["solution"] == RIGHT["solution"] and out[0]["geprueft"]["berichtigt"]
    assert "2x - 6 = 3: richtig ist x = 9/2" in calls[0]["aufgaben"][0]["rechnerpruefung"][0], "der Prüfer erfährt den Befund"
    assert len(calls) == 2


def test_no_paper_when_doubt_remains(monkeypatch):
    # Der Prüfer übersieht den Fehler, die Rechnerprüfung nicht: keine Arbeit.
    fake_checker(monkeypatch, {"tasks": [{"nr": 1, "eigene_loesung": "…", "ok": True}]})
    with pytest.raises(sc.CheckFailed):
        run(sc.assure(1, "Mathematik", [WRONG]))
    # Nach der Berichtigung weiter fehlerhaft: keine Arbeit.
    fake_checker(monkeypatch,
                 {"tasks": [{"nr": 1, "eigene_loesung": "…", "ok": False, "fehler": "x", "solution": "y", "criteria": "z"}]},
                 {"tasks": [{"nr": 1, "eigene_loesung": "…", "ok": False, "fehler": "immer noch"}]})
    with pytest.raises(sc.CheckFailed):
        run(sc.assure(1, "Deutsch", [{"prompt": "Erkläre.", "solution": "a", "criteria": "b"}]))
    # Unlesbare Prüfung, zweimal: keine Arbeit.
    fake_checker(monkeypatch, {"nichts": 1}, {"nichts": 2})
    with pytest.raises(sc.CheckFailed):
        run(sc.assure(1, "Deutsch", [RIGHT]))


def test_a_correct_paper_passes_with_a_mark(monkeypatch):
    fake_checker(monkeypatch, {"tasks": [{"nr": 1, "eigene_loesung": "…", "ok": True}]})
    out = run(sc.assure(1, "Mathematik", [RIGHT]))
    assert out[0]["geprueft"]["berichtigt"] is False and out[0]["solution"] == RIGHT["solution"]


def test_grading_learns_about_the_wrong_solution_and_marks_the_task():
    from backend.routers import practice as routes
    assert sc.grading_hints(WRONG) and not sc.grading_hints(RIGHT)
    grade = lambda pts, flag=False: routes.PaperGrade(tasks=[routes.TaskGrade(
        nr=1, points=pts, rationale="Alles richtig gelöst.", next_step="Weiter so.", loesung_falsch=flag,
        loesung_hinweis="a) richtig ist 4,5" if flag else "")])
    final, open_nrs = routes.consensus([grade(9, True), grade(9)], [WRONG])
    assert final[1]["points"] == 9 and final[1]["loesung_falsch"] and "4,5" in final[1]["loesung_hinweis"]
    final, _ = routes.consensus([grade(9), grade(9)], [WRONG])
    assert final[1]["loesung_falsch"], "die Rechnerprüfung allein reicht für den Vermerk"
    final, _ = routes.consensus([grade(9), grade(9)], [RIGHT])
    assert "loesung_falsch" not in final[1] or not final[1]["loesung_falsch"]
    assert "Rechne jede Aufgabe selbst nach" in routes.QUALITY_RULES


def test_open_papers_are_checked_at_start_and_only_solutions_change(env, monkeypatch):
    """Beim Start: eine offene Arbeit ohne Prüfvermerk wird nachgeprüft und
    berichtigt; der Aufgabentext bleibt, eine abgegebene Arbeit bleibt unberührt."""
    from contextlib import closing
    from datetime import datetime, timezone
    from backend import db
    monkeypatch.setattr(sc, "RECHECK_DAYS", 14)

    async def no_wait(_):
        return None
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    fake_checker(monkeypatch,
                 {"tasks": [{"nr": 1, "eigene_loesung": "…", "ok": False, "fehler": "a) 4,5", "solution": RIGHT["solution"], "criteria": RIGHT["criteria"]}]},
                 {"tasks": [{"nr": 1, "eigene_loesung": "…", "ok": True}]})
    now = datetime.now(timezone.utc).isoformat()
    with closing(db.webapp_conn()) as c, c:
        ids = []
        for status in ("active", "graded"):
            eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,created_at,status,exam_key,paper_format) "
                            "VALUES(1,'K','Mathematik','{}',?,20,?,'published','ma','kurz')", (json.dumps([WRONG]), now)).lastrowid
            ids.append(c.execute("INSERT INTO mentor_exam_attempts(account_id,exam_id,user_id,snapshot,started_at,status,is_test) VALUES(1,?,2,?,?,?,0)",
                                 (eid, json.dumps({"subject": "Mathematik", "tasks": [WRONG]}), now, status)).lastrowid)
    run(sc.recheck_open())
    with closing(db.webapp_conn()) as c:
        rows = {r[0]: (json.loads(r[1])["tasks"][0], json.loads(r[2])[0]) for r in c.execute(
            "SELECT a.id, a.snapshot, e.tasks_json FROM mentor_exam_attempts a JOIN mentor_exams e ON e.id=a.exam_id")}
    snap, exam = rows[ids[0]]
    assert snap["solution"] == RIGHT["solution"] and snap["prompt"] == WRONG["prompt"] and snap["geprueft"]["berichtigt"]
    assert exam["solution"] == RIGHT["solution"]
    assert rows[ids[1]][0]["solution"] == WRONG["solution"], "abgegebene Arbeit: nicht angefasst"
