"""Arbeitsblätter mit Bezug (D83, D85): ein angehängtes Foto gehört zu seinem Eintrag,
nur ein ausdrücklicher Bezug belegt, Nähe im Datum ist höchstens ein Vorschlag."""
from contextlib import closing

from test_learning import env  # noqa: F401
from backend import db, sources


def _material(conn, kind, subject="GESCHICHTE", created="2026-09-17T05:50:00"):
    return conn.execute(
        "INSERT INTO materials(account_id,kind,subject_name,title,analysis_state,confidence,origin,created_at,updated_at) "
        "VALUES(1,?,?,?,'ready',0.9,'upload',?,?)", (kind, subject, kind, created, created)).lastrowid


def _link(conn, material, kind, target, relation=None):
    conn.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at,relation) VALUES(?,?,?,?,?,?)",
                 (material, kind, target, "mensch", "now", relation))


def _source_link(conn, entry_kind, entry_id, day, quote, subject="GESCHICHTE"):
    conn.execute("INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,part_kind,page,quote,"
                 "status,synced_at,updated_at) VALUES(1,?,?,?,?,'Arbeitsblatt','worksheet',0,?,'paper','now','now')",
                 (entry_kind, entry_id, day, subject, quote))


def test_attached_photos_stay_with_their_entry_and_only_sheets_count(env, monkeypatch):
    with closing(db.webapp_conn()) as conn, conn:
        old = conn.execute("INSERT INTO tasks(account_id,title,subject_name,notes,source,created_at,updated_at) "
                           "VALUES(1,'Geschichte','GESCHICHTE','Buch S. 132 Nr. 1 Recherche','ha_todo','now','now')").lastrowid
        # Die Bearbeitung des Kindes zur alten Hausaufgabe, von Hand an die Aufgabe gehängt.
        notes = _material(conn, "own_work"); _link(conn, notes, "task", old)
        # Ein echtes Blatt an derselben Aufgabe, ein Blatt mit ausdrücklicher Rolle an einer Stunde,
        # ein ausgefülltes Blatt (Bearbeitung mit Rolle blatt), ein loses Blatt, eine lose Mitschrift.
        sheet = _material(conn, "worksheet"); _link(conn, sheet, "task", old)
        lesson_sheet = _material(conn, "worksheet"); _link(conn, lesson_sheet, "lesson", 77, "blatt")
        filled = _material(conn, "own_work"); _link(conn, filled, "homework", 12, "blatt")
        loose_sheet = _material(conn, "worksheet", created="2026-09-15T10:00:00")
        _material(conn, "notes", created="2026-09-16T10:00:00")
    monkeypatch.setattr(sources, "homework_for_task", lambda hconn, account_id, task: {old: 10}.get(task["id"]))
    monkeypatch.setattr(sources, "history_conn", lambda: closing(db.webapp_conn()).__enter__())
    found = sources._sheet_photos(1)
    assert found[("homework", 10)] == sheet and found[("lesson", 77)] == lesson_sheet and found[("homework", 12)] == filled
    # Angehängte Fotos kommen nicht in den losen Vorrat; eine lose Mitschrift ist kein Blatt.
    assert found[("loose", "geschichte")] == [("2026-09-15", loose_sheet)]


def test_a_nearby_sheet_is_a_suggestion_not_a_binding(env):
    with closing(db.webapp_conn()) as conn, conn:
        _source_link(conn, "homework", 11, "2026-09-16", "Arbeitsblatt beenden")
        _source_link(conn, "lesson", 501, "2026-09-15", "Laborgeräte AB bearbeitet", subject="CHEMIE")
        _source_link(conn, "homework", 3, "2026-08-20", "Arbeitsblatt Brüche")
        loose = _material(conn, "worksheet", created="2026-09-17T05:50:00")
    sources.refresh_status(1)
    with closing(db.webapp_conn()) as conn:
        rows = conn.execute("SELECT entry_id,status,material_id FROM source_links WHERE account_id=1 ORDER BY entry_id").fetchall()
    # Kein Blatt gebunden, obwohl eines zwei Tage entfernt liegt.
    assert [(r["status"], r["material_id"]) for r in rows] == [("paper", None)] * 3
    material = sources.__dict__["webapp_conn"]().execute("SELECT * FROM materials WHERE id=?", (loose,)).fetchone()
    found = sources.sheet_candidates(1, dict(material))
    # Nur dasselbe Fach, nur in Reichweite, das Nächste zuerst.
    assert [(c["kind"], c["id"], c["quote"]) for c in found] == [("homework", 11, "Arbeitsblatt beenden")]
    # Ein Tipp bindet: Verknüpfung mit Rolle blatt, danach ist die Stelle belegt.
    from backend import materials as store
    assert store.link(1, loose, "homework", 11, relation="blatt")
    sources.refresh_status(1)
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT status,material_id FROM source_links WHERE entry_id=11").fetchone()
        assert (row["status"], row["material_id"]) == ("scanned", loose)
    # Der Ledger führt jedes Blatt je Eintrag, mit Eintragskennung zum Zuordnen.
    subjects = {s["subject"]: s for s in sources.ledger(1)["subjects"]}
    items = [i for need in subjects["GESCHICHTE"]["missing"] for i in need["items"]]
    assert [(i["entry_kind"], i["entry_id"], i["quote"]) for i in items] == [("homework", 3, "Arbeitsblatt Brüche")]
