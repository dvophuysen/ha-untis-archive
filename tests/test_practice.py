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
        return json.dumps(outputs.pop(0)), {}, "fake"
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
    grades[5]["uncertain"] = True
    seen.clear()
    mock(patch, [{"tasks": grades, "overall": "Gut begonnen."}], seen)
    r = client.post(f"{BASE}/attempts/{a['id']}/grade", json={"answers": {"1": "x = 3"}})
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["status"] == "graded" and g["feedback"]["2"]["points"] == 1 and "loesung" in json.dumps(seen[0][1])
    assert seen[0][0] == "exam_paper" and len(seen[0][2][0]) == 1
    with closing(db.webapp_conn()) as c:
        rows = [dict(x) for x in c.execute("SELECT * FROM topic_answers ORDER BY id")]
    assert len(rows) == 6 and rows[0]["source"] == "paper" and rows[0]["points"] == 4 and rows[0]["session_id"] == -a["id"]
    assert rows[5]["result"] == "uncertain" and rows[5]["points"] is None
    raster = client.get(BASE, params={"exam_key": KEY}).json()
    first = raster["topics"][0]
    assert first["cells"]["1"]["state"] == "fast" and first["cells"]["2"]["state"] == "fast"
    assert raster["topics"][2]["cells"]["1"]["state"] == "unsicher"
    assert raster["topics"][2]["cells"]["2"]["state"] == "offen"      # unklar gewertet
    assert raster["papers"][0]["points"] == 4 * 4 + 1 and raster["papers"][0]["points_max"] == 24
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
