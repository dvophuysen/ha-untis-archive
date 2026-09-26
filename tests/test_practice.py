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
    # D219: auch volle Punkte im Einstiegstest sind erst eine Aufgabe („fast“).
    assert pr.cell([ans(1, 4, fmt="einstieg")])["state"] == "fast"
    assert pr.cell([ans(1, 4, fmt="einstieg"), ans(1, 4)])["state"] == "sicher"
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
    # Volle Punkte im Einstiegstest sind erst eine Aufgabe (D219, vorher D192: gleich sicher).
    assert first["cells"]["1"]["state"] == "fast" and first["cells"]["2"]["state"] == "fast" and not first["ready"]
    assert raster["topics"][2]["cells"]["1"]["state"] == "unsicher"
    assert raster["topics"][2]["cells"]["2"]["state"] == "fast"
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


def test_parents_regrade_a_held_paper_with_its_pages_in_one_step(paper):
    """D206: Eine zurückgehaltene oder ausgewertete Arbeit werten Eltern mit den
    vorhandenen Seiten sofort neu aus, mit voller Doppelauswertung. Scheitert das
    Auswerten, zählt nichts Altes weiter, und die Arbeit lässt sich erneut abgeben."""
    client, state, patch = paper
    child(state)
    mock(patch, [pack(6)])
    a = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).json()
    client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    mock(patch, [g_pass([4] * 6)])
    client.post(f"{BASE}/attempts/{a['id']}/grade", json={})
    with closing(db.webapp_conn()) as c, c:  # frühere Einzelauswertung, beim Start zurückgehalten
        fb = json.loads(c.execute("SELECT feedback_json FROM mentor_exam_attempts WHERE id=?", (a["id"],)).fetchone()[0])
        fb["check"] = {"passes": 1, "open": [3], "held_later": True}
        fb["2"]["uncertain"] = True
        c.execute("UPDATE mentor_exam_attempts SET status='review',feedback_json=? WHERE id=?", (json.dumps(fb), a["id"]))
        c.execute("DELETE FROM topic_answers WHERE attempt_id=?", (a["id"],))
    assert client.post(f"{BASE}/attempts/{a['id']}/regrade", json={"now": True}).status_code == 403, "Kind wertet nicht selbst neu aus"
    state.user = CurrentUser(1, "p", "Eltern", "parent", False, "ingress")
    seen = []
    mock(patch, [g_pass([4, 4, 3, 4, 4, 2])], seen)
    r = client.post(f"{BASE}/attempts/{a['id']}/regrade", json={"now": True})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["status"] == "graded" and r["feedback"]["check"] == {"passes": 2, "open": []} and len(seen) == 2
    assert r["pages"], "die vorhandenen Seiten bleiben"
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE attempt_id=?", (a["id"],)).fetchone()[0] == 6
    assert rp.review_items(1) == [] and rp.new_results(1)[0]["points"] == 21
    # Ausgewertet: noch einmal, diesmal scheitert das Auswerten.
    async def broken(*a, **k):
        return "kein JSON", {}, "fake"
    patch.setattr(ai, "complete", broken)
    assert client.post(f"{BASE}/attempts/{a['id']}/regrade", json={"now": True}).status_code == 502
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT status FROM mentor_exam_attempts WHERE id=?", (a["id"],)).fetchone()[0] == "submitted"
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE attempt_id=?", (a["id"],)).fetchone()[0] == 0
    mock(patch, [g_pass([4] * 6)])
    assert client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()["status"] == "graded", "erneut abgeben geht"


def test_feedback_parts_add_up_and_losses_are_summed():
    """D207: Einzelteile passen zur Punktzahl; die Zusammenfassung bündelt Abzüge nach Grund."""
    from backend.feedback import balance, for_child
    e = balance({"points": 3.5, "earned": [{"text": "Ansatz", "points": 3}],
                 "lost": [{"points": 1, "kind": "rechenweg", "why": "fehlt", "fix": "so"}]}, 4)
    assert e["earned"][0]["points"] == 3.5 and e["lost"][0]["points"] == 0.5
    view = for_child({"0": {"points": 0, "lost": [{"points": 4, "kind": "nicht_bearbeitet", "why": "leer", "fix": "x"}]},
                      "1": {"points": 2, "lost": [{"points": 1, "kind": "rechenweg", "why": "a", "fix": "b"},
                                                   {"points": 1, "kind": "nicht_bearbeitet", "why": "c", "fix": "d"}]},
                      "_prior": [{"0": {}}], "check": {"passes": 2}})
    assert "_prior" not in view
    assert [(x["kind"], x["points"]) for x in view["losses"]] == [("nicht_bearbeitet", 5), ("rechenweg", 1)]


def detail(points, most, why="Rechenweg fehlt."):
    lost = [{"points": most - points, "kind": "rechenweg", "why": why, "fix": "So: 3x + 5 = 2x + 11."}] if points < most else []
    return {"points": points, "rationale": "Begründung der Eltern.", "next_step": "Rechenwege aufschreiben.",
            "earned": [{"text": "Ansatz", "points": points}] if points else [], "lost": lost, "model": "Volle Lösung."}


def test_parents_check_any_paper_themselves_with_ai_support(paper):
    """D207: Eltern prüfen jede ausgewertete Arbeit selbst, mit KI-Vorschlag auf
    Wunsch; das ersetzt die Bewertung der App im Lernstand, das Kind sieht nur
    die aktuelle Bewertung mit allen Begründungen."""
    client, state, patch = paper
    child(state)
    mock(patch, [pack(6)])
    a = client.post(BASE, json={"exam_key": KEY, "format": "einstieg"}).json()
    client.post(f"{BASE}/attempts/{a['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    rich = g_pass([4, 2, 0, 4, 4, 4])
    rich["tasks"][1]["lost"] = [{"points": 2, "kind": "rechenfehler", "why": "7 statt 6.", "fix": "11 - 5 = 6."}]
    rich["focus"] = ["Klammern auflösen üben"]
    mock(patch, [rich])
    r = client.post(f"{BASE}/attempts/{a['id']}/grade", json={}).json()
    assert r["status"] == "graded" and r["feedback"]["1"]["lost"][0]["fix"] == "11 - 5 = 6."
    assert r["feedback"]["overall"]["focus"] == ["Klammern auflösen üben"]
    assert r["feedback"]["losses"][0]["kind"] == "rechenfehler"
    body = {"tasks": {"0": detail(3, 4), "1": detail(0, 4), "2": detail(1, 4), **{str(k): detail(4, 4) for k in (3, 4, 5)}},
            "overall": {"text": "Gesamt.", "strengths": ["Einfache Gleichungen"], "focus": ["Rechenwege"]}}
    assert client.post(f"{BASE}/attempts/{a['id']}/manual", json=body).status_code == 403, "Kind prüft nicht selbst"
    state.user = CurrentUser(1, "p", "Eltern", "parent", False, "ingress")
    seen = []
    mock(patch, [g_pass([3, 0, 1, 4, 4, 4])], seen)
    s = client.post(f"{BASE}/attempts/{a['id']}/manual/suggest", json={"hint": "Aufgabe 1 steht unter Aufgabe 2."}).json()
    assert len(seen) == 1 and seen[0][1]["eltern_hinweis"] == "Aufgabe 1 steht unter Aufgabe 2."
    assert seen[0][1]["bisherige_bewertung"][0]["punkte"] == 4
    assert s["tasks"]["0"]["points"] == 3 and "nr" not in s["tasks"]["0"]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT feedback_json FROM mentor_exam_attempts WHERE id=?", (a["id"],)).fetchone()[0].count('"points": 4') >= 1, "Vorschlag speichert nichts"
    bad = {**body, "tasks": {"0": detail(3, 4)}}
    assert client.post(f"{BASE}/attempts/{a['id']}/manual", json=bad).status_code == 422
    over = {**body, "tasks": {**body["tasks"], "0": {**detail(3, 4), "points": 4.5}}}
    assert client.post(f"{BASE}/attempts/{a['id']}/manual", json=over).status_code == 422
    done = client.post(f"{BASE}/attempts/{a['id']}/manual", json=body).json()
    assert done["status"] == "graded" and done["feedback"]["check"]["manual"] and done["feedback"]["1"]["checked_by_parent"]
    assert done["prior"]["1"]["points"] == 2, "Eltern sehen die frühere Bewertung"
    with closing(db.webapp_conn()) as c:
        pts = [x[0] for x in c.execute("SELECT points FROM topic_answers WHERE attempt_id=? ORDER BY id", (a["id"],))]
    assert pts == [3, 0, 1, 4, 4, 4], "der Lernstand folgt der Elternprüfung"
    assert rp.new_results(1)[0]["points"] == 16, "geändert: für das Kind wieder neu"
    child(state)
    kid = client.get(f"{BASE}/attempts/{a['id']}").json()
    assert "prior" not in kid and "_prior" not in kid["feedback"]
    assert kid["feedback"]["0"]["lost"][0]["fix"].startswith("So:") and kid["feedback"]["losses"] == [{"kind": "rechenweg", "label": "Rechenweg oder Begründung fehlt", "points": 8}]


def test_the_final_probe_weights_topics_by_their_size_and_covers_every_level():
    """D220: Die Probearbeit verteilt die Aufgaben nach Umfang im Buch, jedes
    Thema mindestens zweimal, und jedes Thema bekommt zuerst verschiedene Bereiche."""
    rows = _rows(2)
    even = pr.slots("probe", rows)
    per = {t: sorted(x["afb"] for x in even if x["topic_id"] == t) for t in (1, 2)}
    assert per == {1: [1, 2, 3], 2: [1, 2, 3]}, "ohne Seitenangaben gleich verteilt"
    heavy = pr.slots("probe", rows, weights={1: 16, 2: 7})
    per = {t: sorted(x["afb"] for x in heavy if x["topic_id"] == t) for t in (1, 2)}
    assert len(per[1]) == 4 and len(per[2]) == 2 and per[2] == [1, 2] and set(per[1]) == {1, 2, 3}
    assert sorted(x["afb"] for x in heavy) == [1, 1, 2, 2, 3, 3], "40/40/20 bleibt"
    assert pr.slots("probe", rows, weights={1: 16, 2: 0}) == even, "fehlt eine Angabe, gleich verteilt"


def test_the_probe_gets_the_book_sections_model_pages_and_the_teachers_list(monkeypatch):
    from backend import exam_scope, sources
    idx = lambda *pairs: [{"page": p, "title": t} for p, t in pairs]  # noqa: E731
    chapters = [
        {"number": "1", "title": "Gleichungen", "start_page": 8, "end_page": 35, "first_date": "2026-08-24",
         "page_index": idx((10, "Gleichungen aufstellen und lösen"), (32, "Check-up"), (34, "Sichern und Vernetzen – Vermischte Aufgaben"))},
        {"number": "1.1", "title": "Gleichungen aufstellen und lösen", "start_page": 10, "end_page": 17, "first_date": "2026-08-17",
         "page_index": idx((10, "Gleichungen aufstellen und lösen"))},
        {"number": "1.2", "title": "Gleichungen lösen mit systematischem Probieren", "start_page": 18, "end_page": 24, "first_date": "2026-08-18",
         "page_index": idx((18, "Systematisches Probieren"), (21, "Gleichungen grafisch und mit Tabellen lösen"))},
        {"number": "2", "title": "Lineare Funktionen", "start_page": 36, "end_page": 60, "first_date": "2026-10-10", "page_index": []},
    ]
    monkeypatch.setattr(exam_scope, "book_chapters", lambda *a: chapters)
    monkeypatch.setattr(sources, "exam_notices", lambda a: [
        {"subject_name": "MATHEMATIK", "date": "2026-09-20", "text": "Themen: Gleichungen aufstellen, Probieren, Äquivalenzumformungen"},
        {"subject_name": "DEUTSCH", "date": "2026-09-20", "text": "Kommasetzung"}])
    topics = [{"places": [{"label": "Buch", "pages": list(range(10, 18))}]}, {"places": [{"label": "Buch", "pages": [18, 21, 32]}]}]
    got = pr.stoff(1, "Mathematik", topics, "2026-09-28")
    assert [x["abschnitt"] for x in got["abschnitte"]] == ["1.1 Gleichungen aufstellen und lösen", "1.2 Gleichungen lösen mit systematischem Probieren"]
    assert got["abschnitte"][1]["inhalt"] == ["Systematisches Probieren", "Gleichungen grafisch und mit Tabellen lösen"]
    assert got["abschnitte"][0]["umfang_seiten"] == 8 and got["seiten_wie_eine_arbeit"] == [32, 34]
    assert got["themenliste_lehrkraft"] == ["Themen: Gleichungen aufstellen, Probieren, Äquivalenzumformungen"]
    assert pr.stoff(1, "Mathematik", [], "2026-09-28")["abschnitte"][0]["abschnitt"].startswith("1.1"), "ohne Seiten: die Kapitel der letzten Wochen"
    # Wie live: Die Themen kennen nur die im Unterricht genannte Seite 18. Das
    # angeschnittene Kapitel gehört ganz dazu; Abschnitte ohne Seitentreffer
    # gehen nach Stichwörtern an ein Thema.
    chapters.append({"number": "1.3", "title": "Gleichungen lösen mit Äquivalenzumformungen", "start_page": 25, "end_page": 32,
                     "first_date": "2026-09-08", "page_index": idx((25, "Gleichungen lösen mit Äquivalenzumformungen"))})
    live = [{"id": 11, "title": "Gleichungen aufstellen, umformen und lösen", "places": [{"label": "Buch", "pages": [18]}]},
            {"id": 12, "title": "Wertetabellen, Graphen und grafisches Lösen von Gleichungen", "places": [{"label": "Buch", "pages": [18]}]}]
    got = pr.stoff(1, "Mathematik", live, "2026-09-28")
    assert [x["abschnitt"][:3] for x in got["abschnitte"]] == ["1.1", "1.2", "1.3"]
    mine = {t: [x["abschnitt"][:3] for x in v] for t, v in got["_je_thema"].items()}
    assert mine == {11: ["1.2", "1.1", "1.3"], 12: ["1.2"]}


def test_each_probe_place_gets_a_book_section_and_odd_points_are_found():
    """D220: Jeder Abschnitt kommt in der Probearbeit vor; Punkte und Zeit wie
    in einer echten Arbeit (vorher: 57 Punkte in 45 Minuten, Bereich I mit 13)."""
    by_topic = {11: [{"abschnitt": "1.1 Aufstellen", "seiten": "S. 10–17", "umfang": 8},
                     {"abschnitt": "1.3 Äquivalenzumformungen", "seiten": "S. 25–32", "umfang": 8}],
                12: [{"abschnitt": "1.2 Probieren", "seiten": "S. 18–24", "umfang": 7}]}
    plan = [{"topic_id": 12, "afb": 1}, {"topic_id": 11, "afb": 1}, {"topic_id": 12, "afb": 2},
            {"topic_id": 11, "afb": 2}, {"topic_id": 13, "afb": 3}]
    assert pr.assign_sections(plan, by_topic) == ["1.2 Probieren (S. 18–24)", "1.1 Aufstellen (S. 10–17)", "1.2 Probieren (S. 18–24)",
                                                  "1.3 Äquivalenzumformungen (S. 25–32)", None]
    good = [{"afb": 1, "points": 4, "minutes": 6}, {"afb": 1, "points": 5, "minutes": 7}, {"afb": 2, "points": 6, "minutes": 8},
            {"afb": 2, "points": 7, "minutes": 8}, {"afb": 3, "points": 8, "minutes": 8}, {"afb": 3, "points": 8, "minutes": 8}]
    assert pr.paper_issues(good, 45, "probe") == []
    bad = [{**good[0], "points": 13}, {**good[1], "points": 12}] + good[2:]
    got = pr.paper_issues(bad, 45, "probe")
    assert got[0].startswith("Aufgabe 1 hat 13 Punkte") and got[1].startswith("Aufgabe 2 hat 12") and "Zusammen 54 Punkte" in got[2]
    assert pr.paper_issues([{**t, "minutes": 2} for t in good], 45, "probe")[-1] == "Die Minuten der Aufgaben ergeben 12, die Arbeit hat 45."


def test_topics_are_weighted_by_their_sections_and_take_their_own_first():
    by_topic = {11: [{"abschnitt": "1.2", "seiten": "S. 18–24", "umfang": 7}, {"abschnitt": "1.1", "seiten": "S. 10–17", "umfang": 8},
                     {"abschnitt": "1.3", "seiten": "S. 25–32", "umfang": 8}],
                12: [{"abschnitt": "1.2", "seiten": "S. 18–24", "umfang": 7}]}
    assert pr.section_weights(by_topic) == {11: 19.5, 12: 3.5}
    plan = pr.slots("probe", _rows(12)[10:], weights=pr.section_weights(by_topic))
    got = [(p["topic_id"], s) for p, s in zip(plan, pr.assign_sections(plan, by_topic))]
    assert sorted(got) == [(11, "1.1 (S. 10–17)"), (11, "1.1 (S. 10–17)"), (11, "1.3 (S. 25–32)"), (11, "1.3 (S. 25–32)"),
                           (12, "1.2 (S. 18–24)"), (12, "1.2 (S. 18–24)")]
