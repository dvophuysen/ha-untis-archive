"""Central material storage: upload, corrections, analysis and context choice."""

import asyncio
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
    assert {"kind": "task", "target_id": 7, "origin": "mensch", "relation": None} in body["links"]


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
    assert {"kind": "topic", "target_id": topic_id, "origin": "ai", "relation": None} in links
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


def test_an_empty_text_field_in_a_correction_is_not_a_correction(env):
    """Textband S. 10/11: Das Formular schickte den leeren Text mit, die Sperre
    verhinderte jede spätere Lesung. Leere Textfelder werden ignoriert."""
    client = client_for(env)
    body = upload(client).json()
    fixed = client.patch(f"{URL}/{body['id']}", json={"source_label": "Textband", "source_page": 10, "content_text": "", "summary": "  ", "title": ""}).json()
    assert set(fixed["locked_fields"]) == {"source_label", "source_page"}
    insight = analysis.Insight(kind="book_page", subject_name="Latein", title="Gefahr im Circus Maximus",
                               summary="Lektionstext", content_text="Die Freizeit der Kinder …", confidence=0.98)
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (body["id"],)).fetchone()
        analysis._apply(conn, 1, row, insight)
    after = client.get(f"{URL}/{body['id']}").json()
    assert after["content_text"] == "Die Freizeit der Kinder …" and after["title"] == "Gefahr im Circus Maximus"


def test_the_repair_unlocks_empty_locked_texts_and_queues_a_new_reading(env):
    client = client_for(env)
    body = upload(client).json()
    with closing(db.webapp_conn()) as conn, conn:
        conn.execute("UPDATE materials SET content_text='',summary='',analysis_state='ready',"
                     "locked_fields='[\"content_text\",\"source_label\",\"summary\",\"title\"]' WHERE id=?", (body["id"],))
        sql = dict(db._MIGRATIONS)["materials_013_unlock_empty_text"]
        conn.executescript(sql)
    after = client.get(f"{URL}/{body['id']}").json()
    assert after["analysis_state"] == "pending" and set(after["locked_fields"]) == {"source_label", "title"}
    # Ein gelesenes Material mit Text bleibt unangetastet.
    other = upload(client).json()
    with closing(db.webapp_conn()) as conn, conn:
        conn.execute("UPDATE materials SET content_text='Text da',analysis_state='ready',locked_fields='[\"content_text\"]' WHERE id=?", (other["id"],))
        conn.executescript(sql)
    assert client.get(f"{URL}/{other['id']}").json()["analysis_state"] == "ready"


def test_compare_texts_sees_digit_and_line_errors_that_word_recall_misses():
    stored = "2.\na) 12 − (5 − x) = 10\nd) 14x − (8 + 3x) · 5 = 0\nk) 85x − (5 + 9x) · 9 = 3x − 5\nVoc. 1. Lektion S. 10, 11"
    read = "2.\na) 12 − (5 − x) = 10\nd) 14x − (8 + 3x) · 5 = 4\nk) 85x − (5 + 9x) · 9 = 3x\nVoc. 7. Lektion S. 70, 77"
    m = analysis.compare_texts(stored, read)
    # Die Wörter stimmen fast alle, die Zahlen nicht: genau das war das blinde Auge der ersten Eichung.
    assert m["word_recall"] >= 0.8
    assert m["number_recall"] < 0.8 and set(m["missing_numbers"]) >= {"0", "1", "10", "11"}
    assert m["only_stored"] == ["d) 14x − (8 + 3x) · 5 = 0", "k) 85x − (5 + 9x) · 9 = 3x − 5", "Voc. 1. Lektion S. 10, 11"]
    assert len(m["only_read"]) == 3 and m["formula_lines_stored"] == 3 == m["formula_lines_read"]
    assert analysis.compare_texts("", "")["text_ratio"] == 1.0


def test_a_confident_reading_of_handwriting_needs_no_second_pair_of_eyes(env):
    client = client_for(env)
    body = upload(client).json()
    insight = analysis.Insight(kind="notes", subject_name="Latein", title="Zettel", summary="Kurz", content_text="BB S. 13",
                               confidence=0.97, page_type="handwriting", handwritten=True)
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (body["id"],)).fetchone()
        analysis._apply(conn, 1, row, insight)
    after = client.get(f"{URL}/{body['id']}").json()
    assert after["page_type"] == "handwriting" and after["handwritten"] == 1
    # Handschrift allein löst kein Gegenlesen mehr aus: Die Lesung war sich
    # sicher und hat keine Zweifelsstelle gemeldet (D118).
    assert after["needs_review"] is False
    printed = upload(client).json()
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (printed["id"],)).fetchone()
        analysis._apply(conn, 1, row, analysis.Insight(kind="worksheet", title="Blatt", content_text="Aufgabe 1", confidence=0.97, page_type="formula"))
    other = client.get(f"{URL}/{printed['id']}").json()
    assert other["page_type"] == "formula" and other["needs_review"] is False


def test_a_double_page_can_be_corrected_by_hand_and_a_link_carries_its_role(env):
    """Von Hand „10-11“: beide Seiten gelten, die Korrektur überlebt die Lesung (0.81.0);
    eine Verknüpfung trägt die Rolle blatt und bekommt sie auch nachträglich (D85)."""
    client = client_for(env)
    body = upload(client, subject_name="Physik", kind="book_page").json()
    fixed = client.patch(f"{URL}/{body['id']}", json={"printed_pages": [11, 10]}).json()
    assert fixed["source_page"] == 10 and json.loads(fixed["printed_pages"]) == [10, 11]
    assert {"printed_pages", "source_page"} <= set(fixed["locked_fields"])
    insight = analysis.Insight(kind="book_page", subject_name="Physik", title="Seite", summary="Kurz",
                               content_text="Text", confidence=0.9, printed_pages=[12])
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (body["id"],)).fetchone()
        analysis._apply(conn, 1, row, insight)
    after = client.get(f"{URL}/{body['id']}").json()
    assert after["source_page"] == 10 and json.loads(after["printed_pages"]) == [10, 11]
    # Verknüpfung ohne Rolle, dann mit Rolle: dieselbe Zeile, Rolle nachgetragen.
    assert client.post(f"{URL}/{body['id']}/links", json={"kind": "homework", "target_id": 5}).status_code == 200
    linked = client.post(f"{URL}/{body['id']}/links", json={"kind": "homework", "target_id": 5, "relation": "blatt"}).json()
    assert [(l["kind"], l["target_id"], l["relation"]) for l in linked["links"] if l["kind"] == "homework"] == [("homework", 5, "blatt")]
    assert client.post(f"{URL}/{body['id']}/links", json={"kind": "homework", "target_id": 5, "relation": "egal"}).status_code == 422


def test_a_homework_can_take_an_already_stored_material(env):
    """In der Hausaufgabenhilfe ließ sich nur Neues ablegen; ein bereits
    eingelesenes Material konnte man nicht auswählen. Jetzt schlägt die Ansicht
    die passenden vor — beste Treffer zuerst — und hängt sie an (D106)."""
    client = client_for(env)
    with closing(db.webapp_conn()) as conn, conn:
        conn.execute("INSERT INTO tasks(id,account_id,title,notes,subject_name,task_type,status,due_date,source,"
                     "created_at,updated_at) VALUES(7,1,'Hausaufgabe','Buch, S. 48 lesen und Arbeitsblatt bearbeiten',"
                     "'POLITIK','homework','open','2026-09-16','manual','2026-09-15','2026-09-15')")
        rows = [('Buchseite 48', 'book_page', 'Schulbuch', 48, '2026-09-15'),
                ('Arbeitsblatt Wahlen', 'worksheet', '', None, '2026-09-16'),
                ('Buchseite 90', 'book_page', 'Schulbuch', 90, '2026-09-15'),
                ('Mathe-Blatt', 'worksheet', '', None, '2026-09-16')]
        for title, kind, label, page, day in rows:
            conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,"
                         "document_date,analysis_state,created_at,updated_at) VALUES(1,?,?,?,?,?,?,'ready',?,?)",
                         (kind, 'MATHEMATIK' if title.startswith('Mathe') else 'POLITIK', title, label, page, day, day, day))
    found = client.get(f"{URL}/for-task/7").json()
    order = [c['title'] for c in found['candidates']]
    # Die im Auftrag genannte Seite zuerst, dann das Blatt vom Tag der Aufgabe,
    # dann die übrige Buchseite. Ein anderes Fach taucht gar nicht auf.
    assert order == ['Buchseite 48', 'Arbeitsblatt Wahlen', 'Buchseite 90']
    assert found['candidates'][0]['reason'].startswith('zeigt Schulbuch S. 48')
    assert 'Mathe-Blatt' not in order
    # Anhängen und wieder lösen.
    first = found['candidates'][0]['material_id']
    assert client.post(f"{URL}/{first}/links", json={'kind': 'task', 'target_id': 7}).status_code == 200
    again = client.get(f"{URL}/for-task/7").json()
    assert [m['id'] for m in again['linked']] == [first]
    assert first not in [c['material_id'] for c in again['candidates']], 'was dranhängt, wird nicht noch einmal vorgeschlagen'
    assert client.request('DELETE', f"{URL}/{first}/links", params={'kind': 'task', 'target_id': 7}).status_code == 200
    assert client.get(f"{URL}/for-task/7").json()['linked'] == []
    # Eine fremde Aufgabe gibt es nicht.
    assert client.get(f"{URL}/for-task/999").status_code == 404


def test_a_doubt_is_the_only_thing_that_asks_for_a_second_pair_of_eyes(env):
    """Der Weg von der Lesung bis zur erledigten Zweifelsstelle (D118): Die
    Lesung meldet, wo sie unsicher war, die Karte zeigt nur diese Stellen mit
    einer Zeile Zusammenhang, und ein Tipp berichtigt oder bestätigt sie."""
    client = client_for(env)
    body = upload(client).json()
    seite = ("1 Berechne.\n" + "\n".join(f"{c}) Aufgabe = ___" for c in "abcdefgh")
             + "\ni) 2/7 + 4/7 = ___ [Kind: 6/7]\nj) letzte Zeile")
    insight = analysis.Insight(kind="workbook", subject_name="Mathematik", title="Brüche", summary="Kurz",
                               content_text=seite, confidence=0.95, page_type="mixed", handwritten=True,
                               pupil_entries=True,
                               doubts=[{"text": "i) 2/7 + 4/7", "alternative": "i) 2/7 + 1/7", "reason": "4 oder 1 im Zähler"}])
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (body["id"],)).fetchone()
        analysis._apply(conn, 1, row, insight)
    after = client.get(f"{URL}/{body['id']}").json()
    assert after["needs_review"] is True
    assert [d["alternative"] for d in after["doubts"]] == ["i) 2/7 + 1/7"]
    # Gezeigt wird der Auszug, nicht die ganze Seite.
    # Die Eintragung des Kindes steht als Zusammenhang markiert daneben, ist aber kein Grund (D165).
    assert after["review"]["shortened"] and after["review"]["spots"] == 2
    gezeigt = "".join(s.get("text", "") for s in after["review"]["segments"])
    assert "i) 2/7 + 4/7" in gezeigt and "1 Berechne." not in gezeigt

    # „Heißt 1/7“: Der Text wird berichtigt, die Stelle ist erledigt, und die
    # Korrektur der Eltern überschreibt keine spätere Lesung mehr.
    fixed = client.post(f"{URL}/{body['id']}/doubts/resolve",
                        json={"text": "i) 2/7 + 4/7", "replace": "i) 2/7 + 1/7"}).json()
    assert "i) 2/7 + 1/7" in fixed["content_text"] and "i) 2/7 + 4/7" not in fixed["content_text"]
    assert fixed["doubts"] == [] and fixed["needs_review"] is False
    assert "content_text" in fixed["locked_fields"]
    # Dieselbe Stelle ein zweites Mal gibt es nicht mehr.
    assert client.post(f"{URL}/{body['id']}/doubts/resolve",
                       json={"text": "i) 2/7 + 4/7", "replace": "i) 2/7 + 3/7"}).status_code == 409


def test_a_doubt_can_simply_be_confirmed_without_changing_the_text(env):
    client = client_for(env)
    body = upload(client).json()
    insight = analysis.Insight(kind="workbook", subject_name="Mathematik", title="Brüche",
                               content_text="a) 1/2 + 1/2 = ___ [Kind: 1]", confidence=0.95,
                               handwritten=True, pupil_entries=True,
                               doubts=[{"text": "a) 1/2 + 1/2", "alternative": "a) 1/2 + 1/4", "reason": "2 oder 4 im Nenner"}])
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (body["id"],)).fetchone()
        analysis._apply(conn, 1, row, insight)
    kept = client.post(f"{URL}/{body['id']}/doubts/resolve", json={"text": "a) 1/2 + 1/2"}).json()
    assert kept["content_text"] == "a) 1/2 + 1/2 = ___ [Kind: 1]"
    assert kept["doubts"] == [] and kept["needs_review"] is False
    # Ohne Änderung bleibt der Text frei für eine spätere, bessere Lesung.
    assert "content_text" not in kept["locked_fields"]


def test_the_page_is_read_on_the_small_tier_and_the_careful_one_is_a_bonus(env, monkeypatch):
    """Der erste Durchgang liest eine gedruckte Seite und wird hart nachgeprüft;
    er läuft auf der kleinen Stufe. Die gründliche Stufe holt das Urteil, wo es
    nötig ist — ist sie nicht erreichbar, gilt die erste Lesung, statt die Seite
    auf „nicht gelesen" stehen zu lassen (D137)."""
    assert analysis.FIRST_TIER == "klein"
    stufen = []

    async def extract(account_id, row, tier=None, effort=None):
        stufen.append(tier)
        if tier == analysis.CAREFUL_TIER:
            raise RuntimeError("kein Kontingent")
        return analysis.Insight(kind="workbook", content_text="Text", confidence=0.9, handwritten=True), tier
    monkeypatch.setattr(analysis, "extract", extract)
    row = {"id": 7, "kind": "workbook", "subject_name": "DEUTSCH", "origin": ""}
    insight, tier = asyncio.run(analysis.read_material(1, row))
    assert stufen == ["klein", "hoch"], "erst klein, dann die gründliche Stufe"
    assert tier == "klein" and insight.content_text == "Text"


def test_an_overlong_doubt_does_not_throw_away_the_whole_reading():
    """Bis 1.13.13 verwarf eine Zweifelsnotiz mit 130 statt 120 Zeichen die
    ganze, bezahlte Lesung einer Seite samt ihrem Text."""
    raw = {"content_text": "Seitentext", "title": "T" * 200,
           "doubts": [{"text": "Stelle", "reason": "r" * 130}] * 14, "topics": ["a"] * 8}
    insight = analysis.Insight.model_validate(raw)
    assert insight.content_text == "Seitentext"
    assert len(insight.doubts) == 12 and len(insight.doubts[0].reason) == 120
    assert len(insight.title) == 160 and len(insight.topics) == 6


def _read(client, **insight):
    body = upload(client).json()
    defaults = dict(kind="book_page", subject_name="Englisch", title="Vokabeln", summary="Kurz",
                    content_text="admission [əd'mɪʃn] Eintritt\nchild [tʃaɪld] Kind", confidence=0.95)
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (body["id"],)).fetchone()
        analysis._apply(conn, 1, row, analysis.Insight(**{**defaults, **insight}))
    return body["id"]


def test_only_real_doubts_ask_the_parents(env):
    """Lautschrift und Eintragungen des Kindes brauchen keinen Blick der Eltern,
    und was sauber gelesen ist, zählt nicht als „wartet auf deinen Blick“ (D165)."""
    client = client_for(env)
    ipa = _read(client, doubts=[{"text": "admission [əd'mɪʃn]", "reason": "Lautschrift (Betonungszeichen) klein"}])
    pupil = _read(client, kind="workbook", content_text="c) 7/9 + 6/9 = ___ [Kind: 1 4/9]", pupil_entries=True,
                  doubts=[{"text": "c) 7/9 + 6/9 = ___ [Kind: 1 4/9]", "reason": "handgeschriebene gemischte Zahl unsicher"}])
    clean = _read(client)
    blurry_ipa = _read(client, confidence=0.5, doubts=[{"text": "child [tʃaɪld]", "reason": "Lautschrift im Bild etwas unscharf"}])
    unsure_pupil = _read(client, kind="workbook", confidence=0.6, content_text="a) 1/10 + 7/10 = ___",
                         doubts=[{"text": "a) 1/10 + 7/10 = ___", "reason": "Ergebnisfeld leer, nicht ausgefüllt"}])
    real = _read(client, doubts=[{"text": "child [tʃaɪld] Kind", "alternative": "chill", "reason": "Wort unsicher"}])
    listing = client.get(URL).json()
    by_id = {m["id"]: m for m in listing["materials"]}
    assert [i for i in (ipa, pupil, clean, blurry_ipa, unsure_pupil, real) if by_id[i]["needs_review"]] == [real]
    assert not by_id[blurry_ipa]["retake"] and not by_id[unsure_pupil]["retake"]
    assert listing["needs_check"] == 1


def test_a_blurry_page_goes_to_the_child_and_a_new_photo_replaces_it(env):
    client = client_for(env)
    blurry = _read(client, kind="book_page", subject_name="Mathematik", title="Brüche S. 12",
                   content_text="25 d) […]\ne) […]",
                   doubts=[{"text": "d) […]", "reason": "Aufgabe unten abgeschnitten, Brüche unscharf"}])
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at) VALUES(?,?,?,?,?)",
                     (blurry, "task", 7, "test", "now"))
    item = next(m for m in client.get(URL).json()["materials"] if m["id"] == blurry)
    assert item["retake"] and item["needs_review"] is False
    assert [r["id"] for r in store.retakes(1)] == [blurry]
    new = upload(client, replaces=str(blurry)).json()
    assert new["id"] != blurry
    with closing(db.webapp_conn()) as conn:
        old = conn.execute("SELECT hidden FROM materials WHERE id=?", (blurry,)).fetchone()
        moved = conn.execute("SELECT 1 FROM material_links WHERE material_id=? AND kind='task' AND target_id=7",
                             (new["id"],)).fetchone()
    assert old["hidden"] == 1 and moved
    assert store.retakes(1) == []
