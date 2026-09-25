"""Fehlendes Material mit Herkunft, Fehlalarm aus Themenzetteln, „Nicht nötig“ (D196)."""
from contextlib import closing
from datetime import date

from test_learning import env, child  # noqa: F401
from test_sources import history
from backend import db, parent_todo, sources
from backend.routers import materials as materials_routes

URL = "/api/accounts/1/materials/sources/dismiss"
LETTER = "Liebe Eltern, zur Sprechprüfung bitte das Merkblatt beachten. Wiederholung: Schulbuch S. 20"


def _notice(text=LETTER, title="Elternbrief Sprechprüfung"):
    with closing(db.webapp_conn()) as c, c:
        return c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,document_date,analysis_state,"
                         "created_at,updated_at) VALUES(1,'exam_notice','ENGLISCH',?,?,'2026-09-10','ready','now','now')",
                         (title, text)).lastrowid


def _card():
    sources._SYNCED.clear()
    return sources.exam_sources(1, "ENGLISCH", "2026-08-01", "2026-09-30")


def _todo(monkeypatch):
    from backend.routers import exams as exam_routes
    monkeypatch.setattr(exam_routes, "scope_start", lambda subject, day, entries: "2026-08-01")
    sources._SYNCED.clear()
    exams = [{"exam_key": "cal:e", "date": "2026-10-01", "subject_name": "ENGLISCH"}]
    return [i for i in parent_todo.exam_items(1, exams, exams, date(2026, 9, 25)) if i["kind"] == "missing_material"]


def test_a_missing_item_says_where_it_comes_from(env, monkeypatch):
    history(homework=[(1, "ENGLISCH", "Arbeitsblatt   zu Unit 1\nbeenden", "2026-09-07")])
    notice = _notice()
    card = _card()
    items = {m["label"]: m for m in card["missing_items"]}
    sheet = items["Arbeitsblatt"]["from"]
    assert sheet == [{"entry_kind": "homework", "entry_id": 1, "date": "2026-09-07", "quote": "Arbeitsblatt zu Unit 1 beenden",
                      "label": "Hausaufgabe Englisch vom 07.09.", "href": None}]
    book = items["Schulbuch"]["from"][0]
    assert book["label"] == "Elternbrief Sprechprüfung (abgelegt 10.09.)"
    assert book["href"] == f"#/materialien?material={notice}" and book["entry_kind"] == "exam_notice"
    # In „Erledigen“: der erste Grund im Satz und als Feld.
    [todo] = _todo(monkeypatch)
    first = card["missing_items"][0]
    assert todo["source"]["label"] == first["from"][0]["label"] and todo["source"]["label"] in todo["reason"]
    assert "Aus: " in todo["reason"]
    assert todo["dismiss"]["subject"] == "ENGLISCH" and todo["dismiss"]["label"] == first["label"]


def test_a_sheet_on_the_notice_is_the_notice_itself(env):
    # Das „Merkblatt“ im Elternbrief ist der Brief selbst; die Buchseite darauf zählt.
    history(lessons=[(1, "2026-09-11", "ENGLISCH", None, "Unit 1")])
    _notice()
    with closing(db.webapp_conn()) as c, c:
        # Ein Rest aus der Zeit vor der Regel verschwindet beim nächsten Abgleich.
        c.execute("INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,part_kind,page,"
                  "synced_at,updated_at) VALUES(1,'exam_notice',1,'2026-09-10','ENGLISCH','Arbeitsblatt','worksheet',0,'2000-01-01','2000-01-01')")
    sources.sync_links(1)
    with closing(db.webapp_conn()) as c:
        rows = {(r[0], r[1]) for r in c.execute("SELECT part_kind,page FROM source_links WHERE entry_kind='exam_notice'")}
    assert rows == {("book", 20)}
    assert {m["label"] for m in _card()["missing_items"]} == {"Schulbuch"}
    # In einer Hausaufgabe bleibt ein Blatt ohne Seite ein fehlendes Blatt.
    history(homework=[(1, "ENGLISCH", "AB fertig machen", "2026-09-08")])
    assert {m["label"] for m in _card()["missing_items"]} == {"Schulbuch", "Arbeitsblatt"}


def test_not_needed_hides_an_item_everywhere_until_undone(env, monkeypatch):
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix="/api")
    history(homework=[(1, "ENGLISCH", "Arbeitsblatt zu Unit 1 beenden", "2026-09-07"),
                      (2, "ENGLISCH", "Workbook p. 12-13", "2026-09-08")])
    assert _card()["missing"] == 3
    before = sources.ledger(1)["missing_total"]
    assert before == 3
    body = {"subject": "ENGLISCH", "label": "Arbeitsblatt", "page": 0}
    r = client.post(URL, json={**body, "until": "2026-09-20"})
    assert r.status_code == 200, r.text
    card = _card()
    assert card["missing"] == 2 and card["total"] == 2
    assert {m["label"] for m in card["missing_items"]} == {"Arbeitsheft"}
    ledger = sources.ledger(1)
    assert ledger["missing_total"] == 2
    assert all(m["label"] != "Arbeitsblatt" for s in ledger["subjects"] for m in s["missing"])
    [todo] = _todo(monkeypatch)
    assert "Arbeitsblatt" not in todo["reason"] and todo["dismiss"]["pages"] == [12, 13]
    # Eine Buchstelle mit mehreren Seiten auf einmal: der Punkt verschwindet ganz.
    assert client.post(URL, json={"subject": "ENGLISCH", "label": "Arbeitsheft", "pages": [12, 13]}).status_code == 200
    assert _todo(monkeypatch) == [] and sources.ledger(1)["missing_total"] == 0
    # Ein später genanntes Blatt ist ein neues Blatt.
    history(homework=[(3, "ENGLISCH", "Arbeitsblatt 2 bearbeiten", "2026-09-30")])
    assert _card()["missing"] == 1
    # Zurücknehmen bringt alles wieder.
    r = client.request("DELETE", URL, json=body)
    assert r.status_code == 200 and r.json()["restored"] == 1
    assert client.request("DELETE", URL, json={"subject": "ENGLISCH", "label": "Arbeitsheft", "pages": [12, 13]}).json()["restored"] == 2
    assert sources.ledger(1)["missing_total"] >= before


def test_only_parents_dismiss(env):
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix="/api")
    history(homework=[(1, "ENGLISCH", "Arbeitsblatt beenden", "2026-09-07")])
    body = {"subject": "ENGLISCH", "label": "Arbeitsblatt", "page": 0}
    child(state)
    assert client.post(URL, json=body).status_code == 403
    assert client.request("DELETE", URL, json=body).status_code == 403
    assert client.post("/api/accounts/1/materials/sources/dismiss", json={"subject": "ENGLISCH", "label": "Arbeitsblatt"}).status_code == 403
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM source_dismissed").fetchone()[0] == 0
    assert sources.ledger(1)["missing_total"] == 1


def test_a_parent_device_in_child_mode_cannot_dismiss(env):
    from test_parent_shell import PARENT, _app
    client = _app({"user": PARENT})
    body = {"subject": "ENGLISCH", "label": "Arbeitsblatt", "page": 0}
    for mode in ("child", "mirror"):
        assert client.post(URL, json=body, headers={"x-view-mode": mode}).status_code == 403
    assert client.post(URL, json=body).status_code == 200
