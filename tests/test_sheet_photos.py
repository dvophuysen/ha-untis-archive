"""Ein an eine Aufgabe gehängtes Foto gehört zu dieser Aufgabe und belegt kein fremdes Arbeitsblatt (D83)."""
from contextlib import closing

from test_learning import env  # noqa: F401
from backend import db, sources


def _material(conn, kind, subject="GESCHICHTE", created="2026-09-17T05:50:00"):
    return conn.execute(
        "INSERT INTO materials(account_id,kind,subject_name,title,analysis_state,confidence,origin,created_at,updated_at) "
        "VALUES(1,?,?,?,'ready',0.9,'upload',?,?)", (kind, subject, kind, created, created)).lastrowid


def test_attached_photos_stay_with_their_task_and_only_sheets_count(env, monkeypatch):
    with closing(db.webapp_conn()) as conn, conn:
        old = conn.execute("INSERT INTO tasks(account_id,title,subject_name,notes,source,created_at,updated_at) "
                           "VALUES(1,'Geschichte','GESCHICHTE','Buch S. 132 Nr. 1 Recherche','ha_todo','now','now')").lastrowid
        other = conn.execute("INSERT INTO tasks(account_id,title,subject_name,notes,source,created_at,updated_at) "
                             "VALUES(1,'Geschichte','GESCHICHTE','Arbeitsblatt beenden','ha_todo','now','now')").lastrowid
        # Die Ausarbeitung des Kindes zur alten Hausaufgabe, von Hand an die Aufgabe gehängt.
        notes = _material(conn, "notes")
        conn.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at) VALUES(?,?,?,?,?)", (notes, "task", old, "mensch", "now"))
        # Ein echtes Blatt an derselben Aufgabe, ein loses Blatt im Fach, eine lose Mitschrift.
        sheet = _material(conn, "worksheet")
        conn.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at) VALUES(?,?,?,?,?)", (sheet, "task", old, "mensch", "now"))
        loose_sheet = _material(conn, "worksheet", created="2026-09-15T10:00:00")
        loose_notes = _material(conn, "notes", created="2026-09-16T10:00:00")
    monkeypatch.setattr(sources, "homework_for_task", lambda hconn, account_id, task: {old: 10, other: 11}.get(task["id"]))
    monkeypatch.setattr(sources, "history_conn", lambda: closing(db.webapp_conn()).__enter__())
    found = sources._sheet_photos(1)
    # Nur das Blatt belegt die eigene Hausaufgabe; die Ausarbeitung nie.
    assert found[("homework", 10)] == sheet
    assert ("homework", 11) not in found
    # Angehängte Fotos kommen nicht in den losen Vorrat; eine lose Mitschrift ist kein Blatt.
    assert found[("loose", "geschichte")] == [("2026-09-15", loose_sheet)]
    # Die neue Hausaufgabe „Arbeitsblatt beenden“ bekommt höchstens das lose Blatt der Nachbartage.
    assert sources._sheet_near(found, "geschichte", "2026-09-18") == loose_sheet
    assert sources._sheet_near(found, "geschichte", "2026-09-30") is None
