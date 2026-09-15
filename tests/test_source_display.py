"""Quellen im Text sichtbar: Segmente, Aufgabenverknüpfung, Einstiegshilfe."""
import json
import sqlite3
from contextlib import closing

from test_learning import env  # noqa: F401
from test_sources import history, SN, LA
from test_source_collector import shelf
from backend import db, sources, source_collector as collector


def test_a_text_is_split_into_prose_and_page_references():
    segs = sources.segments("Wortschatz (TB S. 13 Aufg. C, AH S. 7) lernen")
    assert [s["text"] for s in segs] == ["Wortschatz (TB ", "S. 13", " Aufg. C, AH ", "S. 7", ") lernen"]
    assert (segs[1]["label"], segs[1]["pages"]) == ("Textband", [13])
    assert (segs[3]["label"], segs[3]["kind"]) == ("Arbeitsheft", "workbook")
    assert sources.segments("") == [] and sources.segments("Klassenfahrt") == [{"text": "Klassenfahrt"}]


def test_lessons_and_tasks_carry_the_state_of_each_reference(env):
    history(lessons=[(1, '2026-09-11', 'SPANISCH', SN, 'Repaso (#libro, p. 50 und #cda, p. 28)')],
            homework=[(7, 'SN', '#libro, p. 50 vocabulario 4 b', '2026-09-10')])
    shelf()
    with closing(sqlite3.connect(db.SETTINGS.history_db_path)) as c:
        c.execute("ALTER TABLE homework ADD COLUMN untis_homework_id INTEGER")
        c.execute("UPDATE homework SET untis_homework_id=4711 WHERE id=7")
        c.commit()
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,origin,source_book,source_page,page_check,"
                     "fits_quote,analysis_state,mime_type,created_at,updated_at) VALUES(1,'book_page','SPANISCH','Apúntate S. 50',"
                     "'book_fetch','¡Apúntate! 2',50,'ok','ja','ready','image/jpeg','now','now')")
    sources.ledger(1)
    lessons = [{"id": 1, "lstext": "Repaso (#libro, p. 50 und #cda, p. 28)", "subject_name": "SPANISCH"}]
    sources.annotate_lessons(1, lessons)
    refs = [s for s in lessons[0]["lstext_segments"] if "pages" in s]
    assert [(r["text"], r["state"]) for r in refs] == [("p. 50", "ready"), ("p. 28", "missing")]
    assert refs[0]["material_id"] is not None and lessons[0]["source_state"] == "missing"

    # Die Aufgabe findet ihre Untis-Hausaufgabe über die Kennung in den Notizen …
    tasks = [{"id": 1, "title": "#libro, p. 50 vocabulario 4 b", "notes": "[HA4711] Gegeben am: 10.09.", "subject_name": "SPANISCH"},
             {"id": 2, "title": "#libro, p. 50 vocabulario 4 b", "notes": "", "subject_name": "SPANISCH"},
             {"id": 3, "title": "Vokabeln lernen", "notes": "", "subject_name": "SPANISCH"}]
    sources.annotate_tasks(1, tasks)
    assert tasks[0]["homework_id"] == 7 and tasks[0]["source_state"] == "ready"
    assert tasks[0]["materials"][0]["source_page"] == 50
    # … oder über denselben Wortlaut; ohne Quelle bleibt sie neutral.
    assert tasks[1]["homework_id"] == 7 and tasks[1]["source_state"] == "ready"
    assert tasks[2]["source_state"] is None and tasks[2]["materials"] == []


def test_the_task_list_carries_segments_and_photos_hung_on_the_task(env):
    client, state, _ = env
    from backend.routers import tasks as task_routes
    client.app.include_router(task_routes.router, prefix="/api")
    history(homework=[(7, 'LA', 'TB S. 13 Aufg. C', '2026-09-10')])
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT INTO tasks(account_id,title,task_type,status,source,notes,subject_name,created_at,updated_at) "
                     "VALUES(1,'TB S. 13 Aufg. C','homework','open','ha_todo','[HA1]','LA','now','now')")
        tid = conn.execute("SELECT id FROM tasks").fetchone()[0]
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,mime_type,analysis_state,created_at,updated_at) "
                     "VALUES(1,'worksheet','LA','Blatt','image/jpeg','ready','now','now')")
        mid = conn.execute("SELECT id FROM materials").fetchone()[0]
        conn.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at) VALUES(?,'task',?,'mensch','now')", (mid, tid))
    sources.ledger(1)
    body = client.get("/api/accounts/1/tasks").json()["tasks"][0]
    assert [s.get("state") for s in body["title_segments"] if "pages" in s] == ["missing"], "kein digitales Buch für Latein: fotografieren"
    assert [m["id"] for m in body["materials"]] == [mid] and body["intro"] is None


async def test_intros_are_written_once_the_sources_are_there(env, monkeypatch):
    history(lessons=[(1, '2026-09-09', 'SPANISCH', SN, 'Unidad 3: la ciudad')],
            homework=[(7, 'SN', '#libro, p. 50 vocabulario 4 b', '2026-09-10'), (8, 'SN', 'libro p. 51', '2026-09-11')])
    shelf()
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT OR IGNORE INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at) VALUES(1,'2026/27',8,1,1,'now')")
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,origin,source_book,source_page,page_check,fits_quote,"
                     "analysis_state,content_text,mime_type,created_at,updated_at) VALUES(1,'book_page','SPANISCH','S. 50','book_fetch',"
                     "'¡Apúntate! 2',50,'ok','ja','ready','Vocabulario: la ciudad, el barrio …','image/jpeg','now','now')")
        for title in ("#libro, p. 50 vocabulario 4 b", "libro p. 51"):
            conn.execute("INSERT INTO tasks(account_id,title,task_type,status,source,subject_name,due_date,created_at,updated_at) "
                         "VALUES(1,?,'homework','open','ha_todo','SPANISCH','2026-09-12','now','now')", (title,))
    sources.ledger(1)
    asked = []

    async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None):
        asked.append((purpose, context["aufgabe"], [m["titel"] for m in context["material"]], context["letzte_stunden"]))
        return json.dumps({"intro": "Es geht um die Vokabeln der Stadt. Lies zuerst die Liste auf Seite 50 laut."}), 0, 0
    monkeypatch.setattr(collector.ai, "complete", complete)
    result = await collector.prepare_intros(1)
    assert result == {"written": 1, "waiting": 1}, "Seite 51 ist noch unterwegs, dafür kommt die Hilfe später"
    assert asked == [("sources", "#libro, p. 50 vocabulario 4 b", ["S. 50"], ["Unidad 3: la ciudad"])]
    with closing(db.webapp_conn()) as conn:
        rows = conn.execute("SELECT title,intro FROM tasks ORDER BY id").fetchall()
    assert rows[0]["intro"].startswith("Es geht um") and rows[1]["intro"] is None
    assert await collector.prepare_intros(1) == {"written": 0, "waiting": 1}, "einmal geschrieben bleibt geschrieben"


def test_the_material_list_shows_everything_and_pages(env):
    client, state, _ = env
    from backend.routers import materials as material_routes
    client.app.include_router(material_routes.router, prefix="/api")
    with closing(db.webapp_conn()) as conn:
        for i in range(5):
            conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,origin,source_book,source_page,analysis_state,created_at,updated_at) "
                         "VALUES(1,'book_page','MATHEMATIK',?,'book_fetch','Neue Wege 8',?,'ready','now','now')", (f"S. {10+i}", 10 + i))
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,analysis_state,created_at,updated_at) "
                     "VALUES(1,'worksheet','MATHEMATIK','Blatt','ready','now','now')")
    first = client.get("/api/accounts/1/materials?limit=4").json()
    assert len(first["materials"]) == 4 and first["has_more"] is True, "Buchseiten sind Teil der Liste"
    rest = client.get("/api/accounts/1/materials?limit=4&offset=4").json()
    assert len(rest["materials"]) == 2 and rest["has_more"] is False
    assert {m["source_book"] for m in first["materials"] + rest["materials"]} == {"Neue Wege 8", None}


def test_untis_tasks_carry_the_assignment_in_their_notes(env):
    history(homework=[(9, 'SN', '#cda, p. 28, n°1a+b', '2026-09-11')])
    shelf()
    task = {"id": 5, "title": "Spanisch", "subject_name": "SPANISCH",
            "notes": "#cda, p. 28, n°1a+b\n\nGegeben am: Fr 11.09.\n\nFällig bis: Mi 16.09.\n\n[SN050675]"}
    assert sources.task_text(task) == "cda, p. 28, n°1a+b"
    sources.ledger(1)
    sources.annotate_tasks(1, [task])
    assert task["homework_id"] == 9, "ohne Kennung in der Historie zählt der Wortlaut, auch ohne das führende #"
    assert [(s["text"], s["state"]) for s in task["text_segments"] if "pages" in s] == [("p. 28", "missing")]
    assert task["title_segments"] is None and task["source_state"] == "missing"


def test_a_worksheet_without_a_page_is_a_missing_source_until_a_photo_hangs_on_the_task(env):
    history(homework=[(11, 'GE', 'Arbeitsblatt beenden\nText schreiben zu Aufgabe A oder B', '2026-09-11')])
    assert [(c["label"], c["pages"]) for c in sources.citations("Arbeitsblatt beenden")] == [("Arbeitsblatt", [0])]
    assert sources.citations("AB S. 3 fertig") == [{"label": "Arbeitsblatt", "kind": "worksheet", "pages": [3]}], "mit Seite zählt die Seite, nicht doppelt"
    segs = sources.segments("Arbeitsblatt beenden\nText schreiben")
    assert [s["text"] for s in segs] == ["Arbeitsblatt", " beenden\nText schreiben"] and segs[0]["pages"] == [0]
    book = sources.ledger(1)
    need = book["subjects"][0]["missing"][0]
    assert (need["label"], need["pages_label"], need["reason"]) == ("Arbeitsblatt", "ohne Seitenangabe", "paper")
    task = {"id": 3, "title": "Geschichte", "subject_name": "GE",
            "notes": "Arbeitsblatt beenden\nText schreiben zu Aufgabe A oder B\n\nGegeben am: Fr 11.09.\n\n[GE1]"}
    sources.annotate_tasks(1, [task])
    assert task["source_state"] == "missing" and task["text_segments"][0]["state"] == "missing"
    # Das Foto an der Aufgabe macht das Blatt zur vorhandenen Quelle.
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT INTO tasks(id,account_id,title,task_type,status,source,notes,subject_name,created_at,updated_at) "
                     "VALUES(3,1,'Geschichte','homework','open','ha_todo',?,'GE','now','now')", (task["notes"],))
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,mime_type,analysis_state,created_at,updated_at) "
                     "VALUES(1,'worksheet','GE','Blatt','image/jpeg','ready','now','now')")
        mid = conn.execute("SELECT id FROM materials").fetchone()[0]
        conn.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at) VALUES(?,'task',3,'mensch','now')", (mid,))
    sources.ledger(1)
    sources.annotate_tasks(1, [task])
    assert task["source_state"] == "ready" and task["text_segments"][0]["material_id"] == mid
    assert sources.ledger(1)["missing_total"] == 0


def test_a_photo_taken_from_the_checklist_settles_exactly_that_entry(env):
    """Antippen, fotografieren, fertig: das Foto gehört zur Stelle, auch bevor
    die Auswertung eine Seitenzahl gelesen hat."""
    client, state, _ = env
    from backend.routers import materials as material_routes
    client.app.include_router(material_routes.router, prefix="/api")
    history(homework=[(1, 'SN', '#cda, p. 26-28', '2026-09-10')])
    shelf()
    book = sources.ledger(1)["subjects"][0]
    need = book["missing"][0]
    assert [i["label"] for i in need["items"]] == ["S. 26", "S. 27", "S. 28"], "je Seite ein Eintrag zum Abhaken"
    from PIL import Image
    import io
    out = io.BytesIO(); Image.new("RGB", (40, 40), (200, 100, 50)).save(out, "JPEG")
    answer = client.post("/api/accounts/1/materials", files={"file": ("s27.jpg", out.getvalue(), "image/jpeg")},
                         data={"subject_name": "SPANISCH", "source_label": "Arbeitsheft", "source_page": "27"})
    assert answer.status_code == 200
    created = answer.json()
    assert created["kind"] == "workbook" and created["title"] == "Arbeitsheft S. 27"
    book = sources.ledger(1)["subjects"][0]
    assert book["missing"][0]["pages"] == [26, 28] and book["scanned"] == 1
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT status,detail,material_id FROM source_links WHERE page=27").fetchone()
    assert tuple(row) == ("scanned", "foto", created["id"])
    # Der Stand überlebt jeden neuen Abgleich, auch wenn die Auswertung nichts liest.
    sources.ledger(1)
    with closing(db.webapp_conn()) as conn:
        assert conn.execute("SELECT status FROM source_links WHERE page=27").fetchone()[0] == "scanned"
