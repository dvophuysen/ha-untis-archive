"""Abbildungen aus abgelegten Seiten (D198): einmal verzeichnen, als Ausschnitt
zeigen, in Aufgaben, Übungsarbeiten und der Sprechprobe nutzen."""
import io
import json
import sys
from contextlib import closing
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, child  # noqa: F401
from test_mentor import setup, B, TASK  # noqa: F401
from backend import db, exam_meta, lernstand, page_figures, ai_gateway as ai
from backend.routers import materials as materials_router, mentor as m


def page(subject="PHYSIK", page_no=12, account=1):
    img = Image.new("RGB", (1000, 1400), "white")
    for x in range(500, 900):  # ein schwarzer Kasten als „Abbildung“ rechts oben
        for y in range(100, 500, 50):
            img.putpixel((x, y), (0, 0, 0))
    out = io.BytesIO()
    img.save(out, format="JPEG")
    with closing(db.webapp_conn()) as c, c:
        return c.execute("INSERT INTO materials(account_id,kind,subject_name,title,summary,content_text,created_at,updated_at,hidden,verified,"
                         "source_label,source_page,mime_type,file_bytes,analysis_state) VALUES(?,'book_page',?,'Seite','','Stromkreise',"
                         "'t','t',0,1,'Buch',?,'image/jpeg',?,'done')", (account, subject, page_no, out.getvalue())).lastrowid


SCAN = {"figures": [
    {"kind": "schaltplan", "box": [0.5, 0.07, 0.9, 0.36], "caption": "Abb. 3",
     "description": "Batterie, Schalter, zwei Lampen L1 und L2 parallel, Amperemeter A1 im Hauptzweig."},
    {"kind": "foto", "box": [0.0, 0.0, 0.02, 0.02], "caption": "", "description": "winziges Symbol"}]}


def fake(patch, outputs, seen=None):
    async def complete(account, purpose, instruction, context, *args, **kw):
        if seen is not None:
            seen.append({"purpose": purpose, "instruction": instruction, "context": context, "images": (args[0] if args else kw.get("images")) or []})
        out = outputs[0] if len(outputs) == 1 else outputs.pop(0)
        return json.dumps(out), {}, "x"
    patch.setattr(ai, "complete", complete)


async def test_index_crop_and_endpoint(setup):
    client, state, patch = setup
    client.app.include_router(materials_router.router, prefix="/api")
    mid = page()
    seen = []
    fake(patch, [SCAN], seen)
    assert page_figures.pending() == [(1, mid)]
    assert await page_figures.cycle() == 1
    assert seen[0]["purpose"] == "background" and len(seen[0]["images"]) == 1
    figs = page_figures.for_materials(1, [mid])
    assert [f["kind"] for f in figs] == ["schaltplan"], "zu kleine Kästen sind keine Abbildung"
    assert figs[0]["seite"] == "Buch S. 12" and "parallel" in figs[0]["beschreibung"]
    assert page_figures.pending() == [], "jede Seite nur einmal"
    data = page_figures.crop(1, figs[0]["id"])
    w, h = Image.open(io.BytesIO(data)).size
    assert 400 <= w <= 440 and 400 <= h <= 450
    r = client.get(f"/api/accounts/1/materials/figures/{figs[0]['id']}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get("/api/accounts/1/materials/figures/999").status_code == 404
    child(state)
    assert client.get(f"/api/accounts/1/materials/figures/{figs[0]['id']}").status_code == 200
    assert client.get(f"/api/accounts/2/materials/figures/{figs[0]['id']}").status_code in (403, 404)


async def test_topic_task_shows_a_figure_and_the_answer_is_judged_on_it(setup):
    client, state, patch = setup
    child(state)
    mid = page()
    fake(patch, [SCAN])
    await page_figures.index(1, mid)
    fid = page_figures.for_materials(1, [mid])[0]["id"]
    tid = lernstand.add_manual(1, "cal:physik", "PHYSIK", "Knotenregel")["id"]
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE exam_topics SET places_json=? WHERE id=?", (json.dumps([{"label": "Buch", "pages": [12]}]), tid))
    assert [f["id"] for f in lernstand.context_for(1, tid)["abbildungen"]] == [fid]
    seen = []
    task = {**TASK, "prompt": "Wie groß ist der Strom in A1?", "abbildung": fid}
    fake(patch, [{"message": "Schau dir den Schaltplan an.", "choices": [], "action": "task", "task": task, "assessment": None, "summary": "x"}], seen)
    s = client.post(B + "/sessions", json={"topic_id": tid}).json()
    r = client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": "figure_1_x", "version": s["version"], "text": "Los"})
    assert r.status_code == 200, r.text
    s = r.json()
    shown = s["messages"][-1]["payload"]["task"]
    assert shown["abbildung"] == fid and "parallel" in shown["abbildung_text"] and shown["abbildung_seite"] == "Buch S. 12"
    assert "topic.abbildungen" in seen[-1]["instruction"]
    fake(patch, [{"message": "Richtig.", "choices": [], "action": "clarify", "task": None,
                  "assessment": {"result": "correct", "rationale": "Knotenregel angewendet."}, "summary": "x"}], seen)
    client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": "figure_2_x", "version": s["version"], "text": "0,5 A", "kind": "answer"})
    assert len(seen[-1]["images"]) == 1, "beim Auswerten sieht das Modell die Abbildung"
    # Eine erfundene ID wird verworfen.
    fake(patch, [{"message": "Neue Aufgabe.", "choices": [], "action": "task", "task": {**TASK, "prompt": "Noch eine?", "abbildung": 999}, "assessment": None, "summary": "x"}])
    s = client.get(B + f"/sessions/{s['id']}").json()
    s = client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": "figure_3_x", "version": s["version"], "text": "weiter"}).json()
    assert s["messages"][-1]["payload"]["task"]["abbildung"] is None


async def test_speaking_exam_shows_a_picture_from_the_book(setup):
    client, state, patch = setup
    child(state)
    mid = page(subject="ENGLISCH", page_no=20)
    fake(patch, [{"figures": [{"kind": "foto", "box": [0.1, 0.1, 0.9, 0.5], "caption": "", "description": "Children at a market buying fruit."}]}])
    await page_figures.index(1, mid)
    fid = page_figures.for_materials(1, [mid])[0]["id"]
    exam_meta.remember(1, "uid:sp", "Sprechprüfung Englisch")
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO exam_topics(account_id,subject,exam_key,position,title,origin,created_at,updated_at) VALUES(1,'ENGLISCH','uid:sp',0,'Ablauf','notice','t','t')")
    seen = []
    fake(patch, [{"message": "Look at the picture. What can you see?", "choices": [], "action": "clarify", "task": None, "assessment": None, "summary": "x", "bild": fid}], seen)
    r = client.post(B + "/sessions", json={"oral_exam_key": "uid:sp"})
    assert r.status_code == 200, r.text
    s = r.json()
    s = client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": "picture_1_x", "version": s["version"], "text": "Hello", "spoken": True, "seconds": 3}).json()
    assert seen[-1]["context"]["oral"]["bilder"][0]["id"] == fid
    assert s["messages"][-1]["payload"]["picture"]["figure_id"] == fid
    fake(patch, [{"message": "Tell me more.", "choices": [], "action": "clarify", "task": None, "assessment": None, "summary": "x"}], seen)
    client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": "picture_2_x", "version": s["version"], "text": "I can see children.", "spoken": True, "seconds": 4})
    assert len(seen[-1]["images"]) == 1, "der Prüfer sieht das gezeigte Bild"


def test_print_embeds_the_figure():
    from backend.exam_print import sheet
    html = sheet({"id": 1, "title": "Kurztest", "subject": "Physik", "minutes": 20},
                 [{"prompt": "Wie groß ist I?", "points": 3, "abbildung_src": "data:image/jpeg;base64,AAAA", "abbildung_text": "Schaltplan"}])
    assert '<img class="fig" src="data:image/jpeg;base64,AAAA" alt="Schaltplan">' in html
    assert "<img" not in sheet({"id": 1, "title": "T", "subject": "P", "minutes": 5},
                               [{"prompt": "x", "points": 1, "abbildung_src": "javascript:alert(1)"}])
