"""Material und Stoff je Arbeit (D199): Themen abwählen, Material anheften."""
import io
import sys
from contextlib import closing
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from test_lernstand import exam_env, EXAMS, notice  # noqa: F401
from test_learning import env, child  # noqa: F401
from test_mentor import setup, mock  # noqa: F401
from backend import db, exam_meta, lernstand, practice
from backend.routers import materials as materials_router

KEY = "cal:latein-2026-09-21"


def material(subject="Latein", page=13):
    out = io.BytesIO()
    Image.new("RGB", (800, 1000), "white").save(out, format="JPEG")
    with closing(db.webapp_conn()) as c, c:
        return c.execute("INSERT INTO materials(account_id,kind,subject_name,title,summary,content_text,created_at,updated_at,hidden,verified,"
                         "source_label,source_page,mime_type,file_bytes) VALUES(1,'worksheet',?,'Übungsblatt','','servus, servi: Übung zur o-Deklination',"
                         "'2026-09-20T10:00:00','t',0,1,'Blatt',?,'image/jpeg',?)", (subject, page, out.getvalue())).lastrowid


def test_exclude_topics_and_pin_material(exam_env):
    client, state, patch, nid, extraction = exam_env
    client.app.include_router(materials_router.router, prefix="/api")
    mock(patch, [extraction], [])
    mid = material()
    exam = client.get("/api/accounts/1/exams/all").json()["upcoming"][0]
    assert [m["id"] for m in exam["materials"]] == [mid, nid] and not any(m["pinned"] for m in exam["materials"]), "Jüngstes zuerst, Zettel dabei"
    topics = [t for t in exam["topics"] if not t["stale"]]
    drop = topics[1]["id"]  # a-/o-Deklination; das Vokabelthema zählt ohnehin nicht fürs Raster
    r = client.post("/api/accounts/1/exams/note", json={"exam_key": KEY, "note": "", "excluded_refs": [f"topic:{drop}"],
                                                        "pinned_materials": [mid, 999999]})
    assert r.status_code == 200, r.text
    assert exam_meta.pinned(1, KEY) == [mid], "fremdes oder unbekanntes Material wird nicht angeheftet"
    assert drop not in [t["id"] for t in practice.topics(1, KEY)], "abgewähltes Thema zählt nicht für Plan und Übungsarbeit"
    exam = client.get("/api/accounts/1/exams/all").json()["upcoming"][0]
    assert next(t for t in exam["topics"] if t["id"] == drop)["excluded"] and exam["materials"][0]["id"] == mid and exam["materials"][0]["pinned"]
    ctx = lernstand.context_for(1, topics[2]["id"])
    assert ctx["material_eltern"][0]["material"] == "Blatt S. 13" and "o-Deklination" in ctx["material_eltern"][0]["text"]
    thumb = client.get(f"/api/accounts/1/materials/{mid}/thumb")
    assert thumb.status_code == 200 and max(Image.open(io.BytesIO(thumb.content)).size) <= 320
    # Wieder angekreuzt zählt es wieder.
    client.post("/api/accounts/1/exams/note", json={"exam_key": KEY, "note": "", "excluded_refs": []})
    assert drop in [t["id"] for t in practice.topics(1, KEY)]
    child(state)
    assert client.post("/api/accounts/1/exams/note", json={"exam_key": KEY, "pinned_materials": []}).status_code in (403, 404)
