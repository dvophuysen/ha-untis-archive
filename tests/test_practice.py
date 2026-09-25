"""Übungsarbeiten zu einer Arbeit und das Raster Thema × Anforderungsbereich (D178)."""
import io
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, child  # noqa: F401
from test_mentor import setup, TASK  # noqa: F401
from backend import db, ai_gateway as ai, practice as pr
from backend.auth import CurrentUser
from backend.routers import practice as rp

KEY = "cal:mathe-1"
BASE = "/api/accounts/1/practice"


def ans(afb, points, most=4, help_used=0, fmt=None, result=None):
    return {"afb": afb, "points": points, "max_points": most, "help_used": help_used, "paper_format": fmt,
            "result": result or ("correct" if points / most >= .8 else "partial" if points else "incorrect")}


def test_cell_states():
    assert pr.cell([])["state"] == "offen"
    assert pr.cell([ans(1, 1)])["state"] == "unsicher"
    assert pr.cell([ans(1, 4)])["state"] == "fast"          # erst eine Aufgabe
    assert pr.cell([ans(1, 4), ans(1, 3.5)])["state"] == "sicher"
    assert pr.cell([ans(1, 4), ans(1, 4, fmt="probe")])["state"] == "bestaetigt"
    assert pr.cell([ans(1, 4), ans(1, 4, help_used=1)])["state"] == "fast"   # mit Hilfe zählt nicht
    # D192: volle Punkte im Einstiegstest kalibrieren gleich, sonst bleibt es „fast“.
    assert pr.cell([ans(1, 4, fmt="einstieg")])["state"] == "sicher"
    assert pr.cell([ans(1, 3.5, fmt="einstieg")])["state"] == "fast"
    assert pr.cell([ans(1, 4, fmt="einstieg", help_used=1)])["state"] == "offen"
    # Nur die letzten vier zählen: alte Fehler wachsen heraus.
    assert pr.cell([ans(1, 0)] * 3 + [ans(1, 4)] * 4)["state"] == "sicher"
    # Gesprächsaufgaben ohne Punkte zählen 1/½/0, unklare gar nicht.
    assert pr.cell([{"afb": 1, "result": "correct"}, {"afb": 1, "result": "correct"}, {"afb": 1, "result": "uncertain"}])["state"] == "sicher"


def test_row_implies_lower_levels_and_target():
    row = pr.row_of([ans(2, 4), ans(2, 4)])
    assert row["cells"]["1"]["state"] == "sicher" and row["cells"]["1"]["implied"]
    assert row["level"] == 2 and row["ready"] and row["target"] == 3
    row = pr.row_of([ans(1, 4), ans(1, 4), ans(2, 1)])
    assert row["level"] == 1 and not row["ready"] and row["target"] == 2


def _rows(n):
    return [{"id": i, **pr.row_of([])} for i in range(1, n + 1)]


def test_slots_per_format():
    rows = _rows(4)
    s = pr.slots("einstieg", rows)
    assert [x["afb"] for x in s] == [1] * 4 + [2] * 4
    s = pr.slots("kurz", rows, [2])
    assert [x["topic_id"] for x in s] == [2, 2, 2] and [x["afb"] for x in s] == [1, 1, 2]
    assert [x["afb"] for x in pr.slots("kurz", rows, [2], level=3)] == [3, 3, 3]
    s = pr.slots("probe", rows)
    assert len(s) == 6 and {x["topic_id"] for x in s} == {1, 2, 3, 4}
    assert [x["afb"] for x in s].count(3) >= 1
    assert len(pr.slots("einstieg", _rows(9))) == pr.MAX_TASKS
    assert pr.slots("mix", []) == []


@pytest.fixture
def paper(setup):
    client, state, patch = setup
    client.app.include_router(rp.router, prefix="/api")
    with closing(db.webapp_conn()) as c, c:
        for i, t in enumerate(["Lineare Gleichungen lösen", "Wertetabellen", "Graphen zeichnen"]):
            c.execute("INSERT INTO exam_topics(account_id,subject,exam_key,position,title,detail,created_at,updated_at) "
                      "VALUES(1,'Mathematik',?,?,?,'', 'now','now')", (KEY, i, t))
    return client, state, patch


def mock(patch, outputs, seen=None):
    async def complete(account, purpose, instruction, context, *args, **kw):
        if seen is not None:
            seen.append((purpose, context, args))
        # Die letzte Antwort bleibt stehen: Jede Auswertung läuft zwei- bis dreimal (D202).
        return json.dumps(outputs.pop(0) if len(outputs) > 1 else outputs[0]), {}, "fake"
    patch.setattr(ai, "complete", complete)


def pack(n):
    return {"title": "Einstiegstest Gleichungen", "tasks": [
        {**TASK, "prompt": f"Aufgabe {i}", "points": 4, "minutes": 3, "slot": i} for i in range(1, n + 1)]}


def image():
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(out, format="JPEG")
    return out.getvalue()


def test_paper_from_creation_to_raster(paper):
    client, state, patch = paper
    child(state)
    r = client.get(BASE, params={"exam_key": KEY})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 3 and r.json()["ready"] == 0
    seen = []
    mock(patch, [pack(6)], seen)
    r = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert [t["afb"] for t in a["exam"]["tasks"]] == [1, 1, 1, 2, 2, 2]
    assert a["exam"]["tasks"][0]["skill_title"] == "Lineare Gleichungen lösen"
    assert TASK["solution"] not in json.dumps(a)
    assert len(seen[0][1]["plaetze"]) == 6
    sheet = client.get(f"{BASE}/attempts/{a['id']}/print").text
    assert f"Blatt Ü{a['id']}" in sheet and TASK["solution"] not in sheet
    r = client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    assert r.status_code == 200, r.text and len(r.json()["pages"]) == 1
    grades = [{"nr": i, "points": 4 if i != 3 else 1, "rationale": "Passt.", "next_step": "Weiter so."} for i in range(1, 7)]
    seen.clear()
    mock(patch, [{"tasks": grades, "overall": "Gut begonnen."}], seen)
    r = client.post(f"{BASE}/attempts/{a['id']}/grade", json={"answers": {"1": "x = 3"}})
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["status"] == "graded" and g["feedback"]["2"]["points"] == 1 and "loesung" in json.dumps(seen[0][1])
    assert len(seen) == 2 and g["feedback"]["check"] == {"passes": 2, "open": []}, "zwei übereinstimmende Durchgänge"
    assert seen[0][0] == "exam_paper" and len(seen[0][2][0]) == 1
    with closing(db.webapp_conn()) as c:
        rows = [dict(x) for x in c.execute("SELECT * FROM topic_answers ORDER BY id")]
    assert len(rows) == 6 and rows[0]["source"] == "paper" and rows[0]["points"] == 4 and rows[0]["session_id"] == -a["id"]
    assert rows[5]["result"] == "correct" and rows[5]["points"] == 4
    raster = client.get(BASE, params={"exam_key": KEY}).json()
    first = raster["topics"][0]
    # Volle Punkte im Einstiegstest: gleich sicher (D192).
    assert first["cells"]["1"]["state"] == "sicher" and first["cells"]["2"]["state"] == "sicher" and first["ready"]
    assert raster["topics"][2]["cells"]["1"]["state"] == "unsicher"
    assert raster["topics"][2]["cells"]["2"]["state"] == "sicher"
    assert raster["papers"][0]["points"] == 5 * 4 + 1 and raster["papers"][0]["points_max"] == 24
    # Zweimal auswerten kostet nichts.
    assert client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()["status"] == "graded"
    assert client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")}).status_code == 409


def test_parent_paper_is_test_and_unreliable_grading_can_be_retried(paper):
    client, state, patch = paper
    mock(patch, [pack(6)])
    a = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).json()
    mock(patch, [{"tasks": [{"nr": 1, "points": 4, "rationale": "Passt.", "next_step": "Weiter."}]}])
    r = client.post(f"{BASE}/attempts/{a['id']}/grade", json={"answers": {"0": "x"}})
    assert r.status_code == 502
    assert client.get(f"{BASE}/attempts/{a['id']}").json()["status"] == "submitted"
    grades = [{"nr": i, "points": 4, "rationale": "Passt.", "next_step": "Weiter."} for i in range(1, 7)]
    mock(patch, [{"tasks": grades}])
    assert client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()["status"] == "graded"
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM topic_answers").fetchone()[0] == 0


def test_incomplete_paper_is_not_stored_and_empty_submission_is_refused(paper):
    client, state, patch = paper
    child(state)
    mock(patch, [pack(4)])
    assert client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).status_code == 502
    assert client.get(BASE, params={"exam_key": KEY}).json()["papers"] == []
    mock(patch, [pack(3)])
    a = client.post(BASE, json={"exam_key": KEY, "format": "kurz", "topic_ids": []}).json()
    assert client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).status_code == 422
    assert client.get(BASE, params={"exam_key": "unbekannt"}).json()["total"] == 0
    assert client.post(BASE, json={"exam_key": "unbekannt", "format": "kurz"}).status_code == 404


def test_parent_adopts_an_old_exam_as_measurement(paper):
    client, state, patch = paper
    with closing(db.webapp_conn()) as c, c:
        tasks = [{**TASK, "prompt": f"Alt {i}", "points": 5, "minutes": 5, "skill_title": f"Alt-Thema {i}"} for i in range(3)]
        eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,status,created_at) "
                        "VALUES(1,'Alte Klausur','MATHEMATIK',?,?,45,'published','now')",
                        (json.dumps({"topics": ["x"]}), json.dumps(tasks))).lastrowid
        ids = [r[0] for r in c.execute("SELECT id FROM exam_topics ORDER BY position")]
    body = {"exam_id": eid, "exam_key": KEY, "topic_ids": [ids[0], ids[0], ids[2]]}
    assert client.post(f"{BASE}/adopt", json={**body, "topic_ids": ids[:2]}).status_code == 422
    r = client.post(f"{BASE}/adopt", json=body)
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["exam"]["tasks"][2]["skill_title"] == "Graphen zeichnen" and a["format"] == "probe"
    assert client.post(f"{BASE}/adopt", json=body).status_code == 404, "nur einmal"
    assert client.get("/api/accounts/1/learning/mentor/exams").json()["exams"] == []
    client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    mock(patch, [{"tasks": [{"nr": i, "points": 5, "rationale": "Passt.", "next_step": "Weiter."} for i in range(1, 4)]}])
    assert client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()["status"] == "graded"
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE source='paper'").fetchone()[0] == 3
    child(state)
    assert client.post(f"{BASE}/adopt", json=body).status_code == 403


def test_old_exam_on_paper_counts_for_the_next_exam(paper):
    client, state, patch = paper
    from backend.routers import mentor_exams as ex
    client.app.include_router(ex.router, prefix="/api")
    with closing(db.webapp_conn()) as c, c:
        c.execute("CREATE TABLE IF NOT EXISTS exam_dates(account_id INTEGER NOT NULL, exam_key TEXT NOT NULL, exam_date TEXT NOT NULL, PRIMARY KEY(account_id, exam_key))")
        c.execute("INSERT INTO exam_dates VALUES(1,?, '2099-01-01')", (KEY,))
        tasks = [{**TASK, "prompt": f"Alt {i}", "points": 4, "minutes": 5} for i in range(2)]
        eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,status,created_at) "
                        "VALUES(1,'Alte Klausur','MATHEMATIK',?,?,30,'published','now')",
                        (json.dumps({"topics": ["x"]}), json.dumps(tasks))).lastrowid
    child(state)
    a = client.post(f"/api/accounts/1/learning/mentor/exams/{eid}/start").json()
    assert a["is_test"] == 0
    client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    seen = []
    mock(patch, [{"tasks": [{"nr": 1, "points": 4, "rationale": "Passt.", "next_step": "Weiter.", "thema_nr": 2},
                            {"nr": 2, "points": 2, "rationale": "Halb.", "next_step": "Üben.", "thema_nr": 9}]}], seen)
    g = client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()
    assert g["status"] == "graded" and [t["titel"] for t in seen[0][1]["themen"]][1] == "Wertetabellen"
    assert g["exam"]["tasks"][0]["skill_title"] == "Wertetabellen"
    with closing(db.webapp_conn()) as c:
        rows = [dict(r) for r in c.execute("SELECT topic_id, points FROM topic_answers")]
    assert len(rows) == 1 and rows[0]["points"] == 4, "ohne gültiges Thema zählt die Aufgabe nicht"


def test_paper_task_may_print_a_figure_of_the_topic_pages(paper, monkeypatch):
    """D198: Die Abbildungen der Themenseiten gehen mit; eine Aufgabe darf eine
    davon mitdrucken, eine erfundene ID wird verworfen."""
    client, state, patch = paper
    child(state)
    from backend import page_figures
    fig = {"id": 5, "material_id": 9, "kind": "diagramm", "caption": "", "beschreibung": "Gerade durch (0|1) und (2|5).", "seite": "Buch S. 30"}
    monkeypatch.setattr(page_figures, "for_places", lambda *a, **k: [fig])
    monkeypatch.setattr(page_figures, "data_uri", lambda account, fid: "data:image/jpeg;base64,QUJD" if fid == 5 else None)
    seen = []
    tasks = pack(6)
    tasks["tasks"][0]["abbildung"] = 5
    tasks["tasks"][1]["abbildung"] = 77
    mock(patch, [tasks], seen)
    a = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).json()
    assert seen[0][1]["abbildungen"][0]["id"] == 5
    t0, t1 = a["exam"]["tasks"][0], a["exam"]["tasks"][1]
    assert t0["abbildung"] == 5 and t0["abbildung_seite"] == "Buch S. 30" and t1["abbildung"] is None
    sheet = client.get(f"{BASE}/attempts/{a['id']}/print").text
    assert sheet.count('<img class="fig" src="data:image/jpeg;base64,QUJD"') == 1


def test_paper_task_may_bring_a_drawn_figure(paper):
    """D197: In Mathematik darf eine Aufgabe eine gezeichnete Abbildung mitbringen;
    eine ungültige heißt neu erstellen."""
    client, state, patch = paper
    child(state)
    strip = {"type": "zahlenstrahl", "von": 0, "bis": 2, "schritt": "1/4"}
    bad = pack(6)
    bad["tasks"][0]["figur"] = {"type": "zahlenstrahl", "von": 5, "bis": 1}
    seen = []
    mock(patch, [bad], seen)
    assert client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).status_code == 502
    good = pack(6)
    good["tasks"][0]["figur"] = strip
    mock(patch, [good], seen)
    a = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).json()
    assert a["exam"]["tasks"][0]["figur_src"].startswith("data:image/svg+xml;base64,")
    sheet = client.get(f"{BASE}/attempts/{a['id']}/print").text
    assert sheet.count('<img class="fig" src="data:image/svg+xml;base64,') == 1


def test_new_result_is_announced_until_the_child_opens_it_and_parents_can_reopen(paper):
    """D201: „Heute“ meldet eine neue Auswertung, bis das Kind sie öffnet; die
    Lernseite zeigt die Übungsarbeiten je Arbeit; Eltern öffnen eine Auswertung
    wieder, wenn die Fotos schlecht lesbar waren."""
    client, state, patch = paper
    child(state)
    mock(patch, [pack(6)])
    a = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).json()
    client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    grades = [{"nr": i, "points": 4, "rationale": "Passt.", "next_step": "Weiter."} for i in range(1, 7)]
    grades[2]["points"] = 2
    mock(patch, [{"tasks": grades, "overall": "Gut."}])
    assert client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()["status"] == "graded"
    news = rp.new_results(1)
    assert [(n["attempt_id"], n["points"], n["points_max"], n["unclear"]) for n in news] == [(a["id"], 22, 24, 0)]
    from backend.learning_compass import _papers_of
    from types import SimpleNamespace
    papers = _papers_of(1, KEY, SimpleNamespace(id=2))
    assert papers[0]["attempt_id"] == a["id"] and papers[0]["status"] == "graded"
    client.get(f"{BASE}/attempts/{a['id']}")
    assert rp.new_results(1) == [], "vom Kind geöffnet: nicht mehr neu"
    # Kind darf nicht neu öffnen, Eltern schon.
    assert client.post(f"{BASE}/attempts/{a['id']}/regrade").status_code == 403
    state.user = CurrentUser(1, "p", "Eltern", "parent", False, "ingress")
    r = client.post(f"{BASE}/attempts/{a['id']}/regrade")
    assert r.status_code == 200 and r.json()["status"] == "active"
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE attempt_id=?", (a["id"],)).fetchone()[0] == 0
    grades[2]["points"] = 4
    mock(patch, [{"tasks": grades, "overall": "Besser lesbar."}])
    again = client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()
    assert again["status"] == "graded" and again["feedback"]["overall"]["text"] == "Besser lesbar."
    assert rp.new_results(1)[0]["points"] == 24, "neu ausgewertet: wieder als neu gemeldet"


def g_pass(points, uncertain=()):
    return {"tasks": [{"nr": i + 1, "points": p, "uncertain": (i + 1) in uncertain, "rationale": "Begründung.", "next_step": "Weiter."}
                      for i, p in enumerate(points)], "overall": "Gesamt."}


def test_consensus_needs_two_agreeing_passes():
    """D202: Es zählt nur, worin zwei Durchgänge übereinstimmen (höchstens 1 Punkt)."""
    tasks = [{"points": 4}, {"points": 6}, {"points": 4}]
    P = rp.PaperGrade.model_validate
    final, open_nrs = rp.consensus([P(g_pass([3, 5, 2])), P(g_pass([4, 5, 2]))], tasks)
    assert open_nrs == [] and [final[n]["points"] for n in (1, 2, 3)] == [3.5, 5, 2]
    final, open_nrs = rp.consensus([P(g_pass([4, 1, 2])), P(g_pass([4, 5, 2]))], tasks)
    assert open_nrs == [2], "4 Punkte auseinander: offen, bis ein dritter Durchgang entscheidet"
    final, open_nrs = rp.consensus([P(g_pass([4, 1, 2])), P(g_pass([4, 5, 2])), P(g_pass([4, 5.5, 2]))], tasks)
    assert open_nrs == [] and final[2]["points"] == 5.0, "zwei von drei einig: deren Mittel"
    final, open_nrs = rp.consensus([P(g_pass([4, 5, 2], uncertain={3})), P(g_pass([4, 5, 0], uncertain={3})), P(g_pass([4, 5, 2]))], tasks)
    assert open_nrs == [3], "nur ein Durchgang konnte lesen: offen"
    assert final[3]["uncertain"]


def test_unsure_grading_is_held_for_the_parents_and_never_counts(paper):
    """D202: Bleibt eine Aufgabe nach drei Durchgängen unsicher, sieht das Kind
    keine Punkte, nichts geht in den Lernstand, die Eltern bekommen eine Aufgabe
    und tragen die Punkte ein."""
    client, state, patch = paper
    child(state)
    mock(patch, [pack(6)])
    a = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).json()
    client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    seen = []
    mock(patch, [g_pass([4, 4, 4, 4, 4, 0], uncertain={6}), g_pass([4, 4, 4, 4, 4, 4]), g_pass([4, 4, 4, 4, 4, 1], uncertain={6})], seen)
    r = client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()
    assert len(seen) == 3 and r["status"] == "review" and r["feedback"]["check"]["open"] == [6]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE attempt_id=?", (a["id"],)).fetchone()[0] == 0
    assert rp.new_results(1) == [] and rp.review_items(1)[0]["open"] == [6]
    from backend.parent_todo import paper_review_items
    todo = paper_review_items(1, "Beispielkind")
    assert todo[0]["title"].startswith("Einstiegstest von Beispielkind prüfen") and "Aufgabe 6" in todo[0]["reason"]
    assert todo[0]["action"]["page"] == "klausuren" and todo[0]["action"]["query"]["paper"] == str(a["id"])
    assert client.post(f"{BASE}/attempts/{a['id']}/review", json={"points": {"5": 3}}).status_code == 403, "Kind prüft nicht selbst"
    state.user = CurrentUser(1, "p", "Eltern", "parent", False, "ingress")
    assert client.post(f"{BASE}/attempts/{a['id']}/review", json={"points": {}}).status_code == 422
    assert client.post(f"{BASE}/attempts/{a['id']}/review", json={"points": {"5": 9}}).status_code == 422
    done = client.post(f"{BASE}/attempts/{a['id']}/review", json={"points": {"5": 3.5}}).json()
    assert done["status"] == "graded" and done["feedback"]["5"]["points"] == 3.5 and done["feedback"]["5"]["checked_by_parent"]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE attempt_id=?", (a["id"],)).fetchone()[0] == 6
    assert rp.new_results(1)[0]["points"] == 23.5 and rp.review_items(1) == []


def test_older_unsure_results_are_held_back_once(paper):
    """D202: Ältere Auswertungen mit unklaren Aufgaben verlassen beim Start den Lernstand."""
    client, state, patch = paper
    child(state)
    mock(patch, [pack(6)])
    a = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).json()
    client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    mock(patch, [g_pass([4] * 6)])
    client.post(f"{BASE}/attempts/{a['id']}/grade", json={})
    with closing(db.webapp_conn()) as c, c:  # so sah eine Auswertung vor D202 aus
        fb = json.loads(c.execute("SELECT feedback_json FROM mentor_exam_attempts WHERE id=?", (a["id"],)).fetchone()[0])
        fb.pop("check")
        fb["2"]["uncertain"] = True
        c.execute("UPDATE mentor_exam_attempts SET feedback_json=? WHERE id=?", (json.dumps(fb), a["id"]))
    assert rp.hold_uncertain() == 1 and rp.hold_uncertain() == 0
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT status FROM mentor_exam_attempts WHERE id=?", (a["id"],)).fetchone()[0] == "review"
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE attempt_id=?", (a["id"],)).fetchone()[0] == 0
