"""Central material storage: upload, corrections, analysis and context choice."""

import io
import json
from contextlib import closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_learning import child, env  # noqa: F401  (fixture)
from backend import db, material_analysis as analysis, materials as store
from backend.auth import get_current_user
from backend.routers import materials as routes

URL = "/api/accounts/1/materials"


def png(shade=200, size=(40, 30)):
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", size, (shade, shade, shade)).save(out, "PNG")
    return out.getvalue()


def client_for(env):
    _, state, _ = env
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    return TestClient(app)


def profile(ai_enabled=True, active=True):
    """A learning profile is the anchor for topics and for the night run."""
    with closing(db.webapp_conn()) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at)"
            " VALUES(1,'2026/2027',8,?,?,'2026-09-01')", (int(ai_enabled), int(active)))
        return conn.execute("SELECT id FROM learning_profiles WHERE account_id=1").fetchone()[0]


def upload(client, blob=None, name="blatt.png", **form):
    return client.post(URL, files={"file": (name, blob or png(), "image/png")}, data=form)


def test_a_photo_alone_is_enough_to_file_it(env):
    client = client_for(env)
    answer = upload(client)
    assert answer.status_code == 200
    body = answer.json()
    assert body["analysis_state"] == "pending"
    assert body["mime_type"] == "image/jpeg"   # stored downscaled like a chat photo
    assert body["has_file"] and body["file_size"] > 0
    assert client.get(URL).json()["materials"][0]["id"] == body["id"]


def test_hints_from_the_calling_screen_become_links(env):
    client = client_for(env)
    body = upload(client, task_id=7, subject_name="Physik", kind="worksheet").json()
    assert body["subject_name"] == "Physik" and body["kind"] == "worksheet"
    assert {"kind": "task", "target_id": 7, "origin": "mensch"} in body["links"]


def test_unknown_file_types_are_refused(env):
    client = client_for(env)
    answer = client.post(URL, files={"file": ("a.txt", b"nur text", "text/plain")})
    assert answer.status_code == 415


def test_children_may_submit_and_hide_but_not_delete(env):
    _, state, _ = env
    kid = client_for(env)
    child(state)
    body = upload(kid).json()
    assert kid.post(f"{URL}/{body['id']}/hidden", json={"value": True}).status_code == 200
    assert kid.patch(f"{URL}/{body['id']}", json={"title": "x"}).status_code == 403
    assert kid.request("DELETE", f"{URL}/{body['id']}").status_code == 403
    assert kid.post(f"{URL}/{body['id']}/verified", json={"value": True}).status_code == 403


def test_a_parent_correction_is_locked_against_later_analysis(env):
    client = client_for(env)
    body = upload(client).json()
    fixed = client.patch(f"{URL}/{body['id']}", json={"subject_name": "Physik", "title": "Stromstärke"}).json()
    assert set(fixed["locked_fields"]) == {"subject_name", "title"}

    insight = analysis.Insight(kind="worksheet", subject_name="Mathematik", title="Etwas anderes",
                               summary="Kurz", content_text="Aufgabe 1", confidence=0.9)
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (body["id"],)).fetchone()
        analysis._apply(conn, 1, row, insight)
    after = client.get(f"{URL}/{body['id']}").json()
    assert after["subject_name"] == "Physik" and after["title"] == "Stromstärke"
    # Everything the parent did not touch is filled in.
    assert after["summary"] == "Kurz" and after["content_text"] == "Aufgabe 1"
    assert after["analysis_state"] == "ready"


def test_analysis_links_topics_it_recognises(env):
    client = client_for(env)
    pid = profile()
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT INTO learning_topics(profile_id,subject,title,objective,method,status,created_at,updated_at)"
                     " VALUES(?,'PHYSIK','Stromstärke in verzweigten Stromkreisen','Ziel','explain','active','2026-09-01','2026-09-01')",
                     (pid,))
        topic_id = conn.execute("SELECT id FROM learning_topics ORDER BY id DESC LIMIT 1").fetchone()[0]
    body = upload(client).json()
    insight = analysis.Insight(topics=["Stromstärke in verzweigten Stromkreisen", "Erfundenes Thema"],
                               content_text="M6", confidence=0.8)
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (body["id"],)).fetchone()
        analysis._apply(conn, 1, row, insight)
    links = client.get(f"{URL}/{body['id']}").json()["links"]
    assert {"kind": "topic", "target_id": topic_id, "origin": "ai"} in links
    # An invented topic creates nothing.
    assert len([l for l in links if l["kind"] == "topic"]) == 1


def test_context_prefers_the_material_of_this_homework(env):
    client = client_for(env)
    near = upload(client, task_id=42, subject_name="Physik").json()
    far = upload(client, subject_name="Physik").json()
    for mid, text in ((near["id"], "Genau diese Aufgabe"), (far["id"], "Irgendetwas anderes")):
        client.patch(f"{URL}/{mid}", json={"content_text": text, "summary": "s"})
    chosen = store.for_context(1, subject="Physik", task_id=42)
    assert [c["id"] for c in chosen][0] == near["id"]
    assert chosen[0]["inhalt"] == "Genau diese Aufgabe"


def test_context_keeps_other_subjects_out_unless_they_are_linked(env):
    client = client_for(env)
    other = upload(client, subject_name="Deutsch").json()
    client.patch(f"{URL}/{other['id']}", json={"summary": "Deutschblatt"})
    assert store.for_context(1, subject="Physik") == []
    client.post(f"{URL}/{other['id']}/links", json={"kind": "task", "target_id": 5})
    assert [c["id"] for c in store.for_context(1, subject="Physik", task_id=5)] == [other["id"]]


def test_context_budget_limits_full_text(env):
    client = client_for(env)
    body = upload(client, subject_name="Physik").json()
    client.patch(f"{URL}/{body['id']}", json={"content_text": "x" * 5000, "summary": "kurz"})
    chosen = store.for_context(1, subject="Physik", budget=100)
    assert len(chosen[0]["inhalt"]) == 100
    assert chosen[0]["summary"] == "kurz"


def test_solutions_stay_usable_but_are_marked(env):
    client = client_for(env)
    body = upload(client, subject_name="Physik").json()
    client.patch(f"{URL}/{body['id']}", json={"contains_solutions": True, "content_text": "Lösung: 0,6 A",
                                             "summary": "Musterlösung"})
    chosen = store.for_context(1, subject="Physik")
    assert chosen[0]["enthaelt_loesungen"] is True
    assert chosen[0]["inhalt"] == "Lösung: 0,6 A"


def test_night_run_picks_up_what_is_still_open(env):
    profile()
    client = client_for(env)
    body = upload(client).json()
    assert (1, body["id"]) in analysis.due()
    with closing(db.webapp_conn()) as conn:
        conn.execute("UPDATE materials SET analysis_state='ready',analysis_version=?,analysis_model=?,"
                     "subject_name='Physik' WHERE id=?",
                     (analysis.ANALYSIS_VERSION, "", body["id"]))
        conn.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at)"
                     " VALUES(?,'topic',1,'ai','2026-09-01')", (body["id"],))
    assert (1, body["id"]) not in analysis.due()
    # A newer analysis version brings it back.
    with closing(db.webapp_conn()) as conn:
        conn.execute("UPDATE materials SET analysis_version=? WHERE id=?",
                     (analysis.ANALYSIS_VERSION - 1, body["id"]))
    assert (1, body["id"]) in analysis.due()


def test_pdf_text_is_read_without_a_model():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    out = io.BytesIO()
    writer.write(out)
    blob = out.getvalue()
    assert store.pdf_pages(blob) == 1
    assert store.sniff(blob) == "application/pdf"


def test_material_is_dated_when_the_homework_was_set_not_when_it_is_due():
    """A worksheet comes with the assignment; the deadline is the wrong anchor."""
    task = {"lesson_id": None, "due_date": "2026-09-17", "created_at": "2026-09-11T10:00:00+00:00",
            "notes": "Politik Buch, S.30-32.\n\nGegeben am: Do 10.09.\n\nFällig bis: Do 17.09."}
    assert analysis.task_given_date(task) == "2026-09-10"


def test_a_task_set_before_new_year_keeps_the_old_year():
    task = {"lesson_id": None, "due_date": "2027-01-08", "created_at": "2026-12-18T10:00:00+00:00",
            "notes": "Gegeben am: Fr 18.12."}
    assert analysis.task_given_date(task) == "2026-12-18"


def test_without_a_given_date_the_creation_day_is_used():
    task = {"lesson_id": None, "due_date": "2026-09-17", "created_at": "2026-09-11T10:00:00+00:00",
            "notes": "ohne Angabe"}
    assert analysis.task_given_date(task) == "2026-09-11"
