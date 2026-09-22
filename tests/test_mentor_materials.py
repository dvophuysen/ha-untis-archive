"""Mehrere abgelegte Seiten im Hausaufgaben-Chat einbinden: Hilfe und Kontrolle."""
import io
import json
from contextlib import closing

import pytest
from fastapi import HTTPException
from PIL import Image

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from test_learning import child, env, path  # noqa: F401  (Fixture env)
from test_mentor import B, reply, send, setup  # noqa: F401  (Fixture setup)
from backend import ai_gateway as ai, db


def png():
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, format="PNG")
    return out.getvalue()


def page(c, subject, title, *, account=1, text="", image=True, page_no=None, pupil=0):
    return c.execute(
        "INSERT INTO materials(account_id,kind,subject_name,title,content_text,source_label,source_page,pupil_entries,"
        "handwritten,analysis_state,filename,mime_type,file_bytes,document_date,created_at,updated_at) "
        "VALUES(?,'notes',?,?,?,'Heft',?,?,0,'ready',?,?,?,'2026-09-10','2026-09-10','2026-09-10')",
        (account, subject, title, text, page_no, pupil, "seite.png" if image else "blatt.pdf",
         "image/png" if image else "application/pdf", png() if image else b"%PDF-1.4")).lastrowid


def capture(patch, contexts, images):
    async def complete(account, purpose, instruction, context, images_in=None, *args, **kw):
        contexts.append((instruction, context))
        images.append(len(images_in or []))
        return json.dumps(reply(task=None, action="clarify", message="Schauen wir auf deine Seiten.")), {}, "fake"
    patch.setattr(ai, "complete", complete)


def links(c, task_id):
    return {r[0]: r[1] for r in c.execute(
        "SELECT material_id,relation FROM material_links WHERE kind='task' AND target_id=?", (task_id,))}


def test_help_takes_several_filed_pages_of_the_subject(setup):
    client, state, patch = setup
    child(state)
    with closing(db.webapp_conn()) as c, c:
        tid = c.execute("INSERT INTO tasks(account_id,title,subject_name,notes,source,created_at,updated_at) "
                        "VALUES(1,'Aufgabe 4','Deutsch','Erkläre den Arbeitsauftrag','manual','now','now')").lastrowid
        one = page(c, "Deutsch", "Heftseite 1", text="Regel: Nomen groß [Kind: das Gute]", page_no=12, pupil=1)
        two = page(c, "Deutsch", "Heftseite 2", text="Beispiele")
        sheet = page(c, "Deutsch", "Arbeitsblatt", text="Lückentext", image=False)
        maths = page(c, "Mathe", "Bruchrechnung", text="1/2 + 1/4")
        foreign = page(c, "Deutsch", "Fremdes Heft", account=2, text="geheim")
        # Schon vorher an der Aufgabe: bleibt, auch wenn das Kind die Seite wieder löst.
        c.execute("INSERT INTO material_links(material_id,kind,target_id,origin,relation,created_at) "
                  "VALUES(?,'task',?,'mensch','blatt','now')", (sheet, tid))
    s = client.post(B + "/sessions", json={"homework_task_id": tid}).json()
    assert s["mode"] == "homework_help" and s["materials"] == []

    offer = client.get(B + f"/sessions/{s['id']}/materials")
    assert offer.status_code == 200, offer.text
    items = offer.json()["items"]
    ids = [x["id"] for x in items]
    assert ids[0] == sheet and items[0]["group"] == "linked"
    assert {one, two, sheet} <= set(ids) and maths not in ids and foreign not in ids

    for wrong in (maths, foreign):
        r = client.post(B + f"/sessions/{s['id']}/materials", json={"material_ids": [one, wrong]})
        assert r.status_code == 404, r.text
    r = client.post(B + f"/sessions/{s['id']}/materials", json={"material_ids": [one, two, sheet, one]})
    assert r.status_code == 200, r.text
    s = r.json()
    assert [x["id"] for x in s["materials"]] == [one, two, sheet]
    assert not any(x["shown"] for x in s["materials"])
    with closing(db.webapp_conn()) as c:
        assert links(c, tid) == {one: None, two: None, sheet: "blatt"}

    contexts, images = [], []
    capture(patch, contexts, images)
    # Ohne Text: Die frischen Seiten sind die Nachricht.
    r = send(client, s, text="")
    assert r.status_code == 200, r.text
    s = r.json()
    instruction, ctx = contexts[-1]
    assert "eingebunden" in instruction
    pages = {x["id"]: x for x in ctx["eingebunden"]}
    assert list(pages) == [one, two, sheet]
    assert pages[one]["eintragungen_des_kindes"] == ["das Gute"] and pages[one]["wo"] == "Heft S. 12"
    assert pages[one]["als_bild"] and pages[two]["als_bild"] and not pages[sheet]["als_bild"]
    assert images[-1] == 2
    assert "eingebunden" not in ctx["source"]
    user_msg = [m for m in s["messages"] if m["role"] == "user"][-1]
    assert user_msg["text"] == "Meine Seiten ansehen" and user_msg["payload"]["material_ids"] == [one, two, sheet]
    assert all(x["shown"] for x in s["materials"])

    # Die Hilfe sieht eine Seite einmal als Bild, danach reicht ihr Text.
    r = send(client, s, text="Und jetzt Aufgabe 2?")
    assert r.status_code == 200, r.text
    s = r.json()
    assert images[-1] == 0 and len(contexts[-1][1]["eingebunden"]) == 3
    assert not any(x["als_bild"] for x in contexts[-1][1]["eingebunden"])
    assert send(client, s, text="").status_code == 422

    r = client.delete(B + f"/sessions/{s['id']}/materials/{two}")
    assert r.status_code == 200, r.text
    r = client.delete(B + f"/sessions/{s['id']}/materials/{sheet}")
    assert r.status_code == 200, r.text
    assert [x["id"] for x in r.json()["materials"]] == [one]
    with closing(db.webapp_conn()) as c:
        assert links(c, tid) == {one: None, sheet: "blatt"}
    assert client.delete(B + f"/sessions/{s['id']}/materials/{two}").status_code == 404


def test_the_check_reviews_the_chosen_pages_every_turn(setup):
    from backend import sources
    client, state, patch = setup
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO tasks(id,account_id,title,notes,subject_name,status,source,created_at,updated_at) "
                  "VALUES(920,1,'Ah S. 74, Aufg. 2 und 3','','DEUTSCH','open','untis','2026-09-17','2026-09-17')")
        filed = c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,source_label,source_page,"
                          "pupil_entries,handwritten,analysis_state,document_date,created_at,updated_at) "
                          "VALUES(1,'workbook','DEUTSCH','Wechsel des s-Lauts','1 a) das Gras [Kind: Gräser]',"
                          "'Arbeitsheft',74,1,1,'ready','2026-09-17','2026-09-17','2026-09-17')").lastrowid
        first = page(c, "DEUTSCH", "Heft S. 1", text="2 a) [Kind: Fässer]", pupil=1)
        second = page(c, "DEUTSCH", "Heft S. 2", text="3 b) [Kind: Küsse]", pupil=1)
    assert sources.solution_for_task(1, 920)["material_id"] == filed
    s = client.post(B + "/sessions", json={"homework_task_id": 920, "check": True}).json()
    assert "neuester Stand" in s["messages"][0]["text"]

    # Wer selbst Seiten wählt, hat die Rückfrage zur gefundenen Bearbeitung beantwortet.
    r = client.post(B + f"/sessions/{s['id']}/materials", json={"material_ids": [first, second]})
    assert r.status_code == 200, r.text
    s = r.json()
    with closing(db.webapp_conn()) as c:
        assert links(c, 920) == {first: "ergebnis", second: "ergebnis"}
        source = json.loads(c.execute("SELECT source_json FROM mentor_sessions WHERE id=?", (s["id"],)).fetchone()[0])
    assert "solution" not in source

    contexts, images = [], []
    capture(patch, contexts, images)
    async def no_book(*args, **kw):
        return [], {"status": "no_pages"}
    from backend import textbook_context
    patch.setattr(textbook_context, "homework_page_images", no_book)
    r = send(client, s, text="Stimmt das so?")
    assert r.status_code == 200, r.text
    instruction, ctx = contexts[-1]
    assert instruction.startswith(__import__("backend.routers.mentor", fromlist=["x"]).CHECK_INSTRUCTION)
    assert [x["id"] for x in ctx["eingebunden"]] == [first, second] and images[-1] == 2
    assert all(x["als_bild"] for x in ctx["eingebunden"])
    # Die Kontrolle braucht die geschriebene Seite jedes Mal als Bild.
    r = send(client, r.json(), text="Und Aufgabe 3?")
    assert r.status_code == 200, r.text
    assert images[-1] == 2


def test_the_chat_takes_six_images_other_calls_two(setup):
    import asyncio
    part = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    with pytest.raises(HTTPException) as err:
        asyncio.run(ai.complete(1, "mentor", "x", {}, [part] * 7))
    assert err.value.status_code == 413 and "6" in err.value.detail
    with pytest.raises(HTTPException) as err:
        asyncio.run(ai.complete(1, "exam_grade", "x", {}, [part] * 3))
    assert err.value.status_code == 413 and "2" in err.value.detail
