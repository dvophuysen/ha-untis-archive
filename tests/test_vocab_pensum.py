"""Vokabelpensum mit Zielkurve und Vokabeltest auf Papier (D181)."""
import io
import json
import sys
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, child  # noqa: F401
from test_mentor import setup  # noqa: F401
from backend import db, lernstand, rewards, view_mode, vocab_pensum as vp, ai_gateway as ai
from backend.routers import vocab_daily

MON = date(2026, 10, 5)  # Montag
EN = "ENGLISCH"


@pytest.fixture
def free(monkeypatch):
    """Schultage: Montag bis Freitag, außer den Tagen in der Menge."""
    off = set()

    def days(account, first, last):
        out = [first + timedelta(days=i) for i in range((last - first).days + 1)]
        return [d for d in out if d.weekday() < 5 and d not in off]
    monkeypatch.setattr(rewards, "school_days", days)
    return off


def words(n, unit="Unit 3", page=200, subject=EN, material=1):
    with closing(db.webapp_conn()) as c, c:
        for i in range(n):
            c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,position,foreign_word,plain,meanings_json,created_at) "
                      "VALUES(1,?,?,'Schulbuch',?,?,?,?,?,?,'now')",
                      (subject, material, page, unit, i, f"word{material}x{i}", f"word{material}x{i}", json.dumps([f"Wort {material}/{i}"])))
        return [r[0] for r in c.execute("SELECT id FROM vocab_words WHERE material_id=? ORDER BY position", (material,))]


def exam(key, when, title="Vocabulary Unit 3", page=200, subject=EN, extra_topic=None):
    t = lernstand.add_manual(1, key, subject, title)
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE exam_topics SET places_json=? WHERE id=?", (json.dumps([{"label": "Schulbuch", "pages": [page]}]), t["id"]))
        c.execute("CREATE TABLE IF NOT EXISTS exam_dates(account_id INTEGER NOT NULL, exam_key TEXT NOT NULL, exam_date TEXT NOT NULL, PRIMARY KEY(account_id, exam_key))")
        c.execute("INSERT OR REPLACE INTO exam_dates VALUES(1,?,?)", (key, when.isoformat()))
    if extra_topic:
        lernstand.add_manual(1, key, subject, extra_topic)


def attempt(wid, day, result="correct", user=2, hh=16):
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,created_at,user_id) VALUES(1,?,1,'from','x',?,?,?)",
                  (wid, result, f"{day.isoformat()}T{hh:02d}:00:00+02:00", user))


def test_target_curve_limits_and_rise():
    assert vp.target_for(200, 0, 25, None) == 10          # wenig je Tag: Mindestpensum
    assert vp.target_for(60, 0, 5, None) == 12
    assert vp.target_for(60, 0, 3, None) == 24            # die letzten Tage legen zu
    assert vp.target_for(60, 0, 5, 0.42) == 17            # schwache Trefferquote legt zu
    assert vp.target_for(60, 0, 5, 0.9) == 12
    assert vp.target_for(60, 4, 5, None) == 16            # fällige Wiederholungen dazu
    assert vp.target_for(400, 5, 2, 0.3) == 40            # nie mehr als 40
    assert vp.target_for(0, 0, 1, None) == 10
    # Bei gleichem Rest steigt die Kurve bis zum Test.
    curve = [vp.target_for(120, 0, n, 0.5) for n in range(20, 0, -1)]
    assert curve == sorted(curve) and curve[0] < curve[-1] == 40


def test_exam_entry_spreads_open_words_over_school_days(env, free):
    ids = words(60)
    exam("cal:en-voc", MON + timedelta(days=14), extra_topic=None)
    items = vp.daily(1, MON)
    assert len(items) == 1
    e = items[0]
    assert e["subject"] == EN and e["unit"] == "Unit 3" and e["exam_key"] == "cal:en-voc"
    assert e["href"] == "#/vokabeln/ENGLISCH?unit=Unit%203"
    assert e["days_left"] == 10 and e["open"] == 60 and e["target"] == 10 and not e["done"]
    assert e["why"].startswith("Der Vokabeltest ist in 10 Schultagen. 60 Wörter sitzen noch nicht")
    # Schwache Trefferquote und drei Tage vor dem Test: mehr Wörter.
    for wid in ids[:10]:
        attempt(wid, MON - timedelta(days=3), "incorrect")
    attempt(ids[10], MON - timedelta(days=3), "correct")
    thu = MON + timedelta(days=10)
    e = vp.daily(1, thu)[0]
    assert e["days_left"] == 2 and e["rate"] == 0.09
    assert e["target"] == 40 and "etwas mehr" in e["why"] and "am Montag" in e["why"]


def test_a_mixed_exam_names_the_exam_and_fully_secure_units_rest(env, free):
    ids = words(12)
    exam("cal:en-1", MON + timedelta(days=30), extra_topic="Simple past")
    e = vp.daily(1, MON)[0]
    assert e["why"].startswith("Die Arbeit ist in ")
    for wid in ids:
        attempt(wid, MON - timedelta(days=2)); attempt(wid, MON - timedelta(days=2), hh=17)
    assert vp.daily(1, MON) == [], "alles sicher und der Test noch weit: kein Pensum"


def test_weekend_is_free_unless_the_time_would_not_suffice(env, free):
    words(60)
    sat = MON + timedelta(days=5)
    exam("cal:far", sat + timedelta(days=16))
    assert vp.daily(1, sat) == [], "Wochenende frei, die Schultage reichen"
    exam("cal:near", sat + timedelta(days=2), title="Vocabulary Unit 4", page=210)
    words(50, unit="Unit 4", page=210, material=2)
    e = vp.daily(1, sat)
    assert [x["exam_key"] for x in e] == ["cal:near"]
    assert e[0]["target"] == 40 and "Eigentlich ist heute frei" in e[0]["why"] and "morgen" not in e[0]["why"]
    # Ferientag mitten in der Woche zählt wie ein Wochenende.
    free.add(MON)
    assert vp.daily(1, MON) == []


def test_next_test_first_and_at_most_two_entries(env, free):
    words(30, unit="Unit 1", page=100, material=1)
    words(30, unit="Unit 2", page=150, material=2)
    words(30, unit="Unit 3", page=200, material=3)
    exam("cal:c", MON + timedelta(days=30), title="Vocabulary Unit 3", page=200)
    exam("cal:a", MON + timedelta(days=8), title="Vocabulary Unit 1", page=100)
    exam("cal:b", MON + timedelta(days=15), title="Vocabulary Unit 2", page=150)
    exam("cal:x", MON + timedelta(days=60), title="Vocabulary Unit 2 again", page=150)
    items = vp.daily(1, MON)
    assert [e["exam_key"] for e in items] == ["cal:a", "cal:b"]
    assert items[0]["unit"] == "Unit 1"


def test_done_counts_only_the_childs_practice_today(env, free):
    ids = words(60)
    exam("cal:en-voc", MON + timedelta(days=14))
    for wid in ids[:9]:
        attempt(wid, MON)
    attempt(ids[9], MON, user=1)                 # Elternteil im Elternmodus
    attempt(ids[10], MON, result="unclear")      # Rückfrage zählt nicht
    attempt(ids[11], MON - timedelta(days=1))    # gestern
    e = vp.daily(1, MON)[0]
    assert e["practiced"] == 9 and not e["done"]
    with closing(db.webapp_conn()) as c, c:        # Kind am Elterngerät
        c.execute("INSERT INTO reward_events VALUES(1,'vocab',?,?,'t')", (f"{ids[9]}:1", MON.isoformat()))
    e = vp.daily(1, MON)[0]
    assert e["practiced"] == 10 and e["done"] and e["target"] == 10, "das Pensum bleibt über den Tag gleich"


def test_without_a_test_ten_due_reviews(env, free):
    ids = words(20)
    for wid in ids[:12]:
        attempt(wid, MON - timedelta(days=7)); attempt(wid, MON - timedelta(days=7), hh=17)
    items = vp.daily(1, MON)
    assert len(items) == 1 and items[0]["exam_key"] is None
    assert items[0]["target"] == 10 and items[0]["due"] == 12 and "Wiederholen" in items[0]["why"]
    assert vp.daily(1, MON + timedelta(days=5)) == [], "am Wochenende kein Grundpensum"
    assert vp.daily(1, MON - timedelta(days=6)) == [], "nichts fällig"


def test_one_subject_whatever_its_spelling(env, free):
    """Buch und Wortliste schreiben das Fach verschieden („SPANISCH“, „spanisch“).
    Das Grundpensum zählt die fälligen Wörter der Einheit zusammen, statt die
    Einheit je Schreibweise einmal mit einem Teil davon zu rechnen."""
    upper = words(6, subject="SPANISCH", material=1)
    lower = words(6, subject="spanisch", material=2)
    for wid in upper + lower:
        attempt(wid, MON - timedelta(days=7)); attempt(wid, MON - timedelta(days=7), hh=17)
    items = vp.daily(1, MON)
    assert len(items) == 1 and items[0]["due"] == 12 and items[0]["target"] == 10


def test_unit_words_are_the_trainer_cards(env, free):
    from backend import vocab
    words(5, unit="Unit 3"); words(4, unit="Unit 3 A", material=2, page=201); words(3, unit="Unit 4", material=3, page=210)
    for unit in ("Unit 3", "Unit 3 A", "Unit 4"):
        cards = sorted(w["id"] for w in vocab.cards(1, EN, unit, 1, "from", 100000))
        assert sorted(vocab.unit_word_ids(1, EN, unit)) == cards and cards


def test_holidays_beyond_the_timetable_are_not_school_days(env, monkeypatch):
    """Hinter dem bekannten Stundenplan zählen Ferien nicht als Lerntage (A13)."""
    import sqlite3
    week = [MON + timedelta(days=i) for i in range(5)]
    monkeypatch.setattr(rewards, "school_days", lambda a, first, last: [d for d in week if first <= d <= last])
    with sqlite3.connect(db.SETTINGS.history_db_path) as h:
        h.execute("CREATE TABLE IF NOT EXISTS master_holidays(account_id INTEGER, name TEXT, longName TEXT, startDate TEXT, endDate TEXT)")
        h.execute("INSERT INTO master_holidays VALUES(1,'HF','Herbstferien','2026-10-12','2026-10-23')")
    days = vp.school_days(1, MON, MON + timedelta(days=25))
    assert days[:5] == week and days[5:] == [date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 30)]


def test_pensum_endpoint(env, free):
    client, state, _ = env
    client.app.include_router(vocab_daily.router, prefix="/api")
    words(60)
    exam("cal:en-voc", MON + timedelta(days=14))
    child(state)
    r = client.get("/api/accounts/1/vocab/pensum", params={"day": MON.isoformat()})
    assert r.status_code == 200, r.text
    assert r.json()["day"] == MON.isoformat() and r.json()["items"][0]["target"] == 10
    child(state, 3)
    assert client.get("/api/accounts/1/vocab/pensum").status_code == 403


# ------------------------------------------------------------------ Papiertest

def image():
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(out, format="JPEG")
    return out.getvalue()


def mock(patch, output, seen):
    async def complete(account, purpose, instruction, context, images=None, **kw):
        seen.append((purpose, context, images))
        return json.dumps(output(context)), {}, "fake"
    patch.setattr(ai, "complete", complete)


def test_paper_vocab_test_from_print_to_trainer(setup):
    client, state, patch = setup
    client.app.include_router(vocab_daily.router, prefix="/api")
    ids = words(25)
    child(state)
    r = client.post("/api/accounts/1/vocab/papers", json={"subject": EN, "unit": "Unit 3", "count": 10})
    assert r.status_code == 200, r.text
    p = r.json()
    assert len(p["words"]) == 10 and p["direction"] == "into" and p["code"] == f"V{p['id']}"
    assert "expected" not in json.dumps(p) and "word1x" not in json.dumps(p), "keine Lösungen vor der Auswertung"
    sheet = client.get(f"/api/accounts/1/vocab/papers/{p['id']}/print").text
    assert f"Blatt V{p['id']}" in sheet and "Deutsch → Englisch" in sheet and "word1x" not in sheet
    assert client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade").status_code == 422
    r = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    assert r.status_code == 200 and len(r.json()["pages"]) == 1
    assert client.get(f"/api/accounts/1/vocab/papers/{p['id']}/pages/{r.json()['pages'][0]}").status_code == 200
    verdicts = ["richtig"] * 6 + ["falsch"] * 3 + ["unklar"]
    seen = []
    mock(patch, lambda ctx: {"words": [{"nr": w["nr"], "verdict": verdicts[w["nr"] - 1], "read": "x"} for w in ctx["woerter"]],
                             "overall": "Gut gemacht."}, seen)
    r = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade")
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["status"] == "graded" and g["result"] == {"richtig": 6, "falsch": 3, "unklar": 1}
    assert all(w["expected"].startswith("word1x") for w in g["words"])
    purpose, ctx, images = seen[0]
    assert purpose == "vocab_paper" and ai.MAX_IMAGES["vocab_paper"] == 4
    assert len(images) == 1 and images[0]["page"] is True and ctx["blatt"] == f"V{p['id']}"
    with closing(db.webapp_conn()) as c:
        rows = [dict(x) for x in c.execute("SELECT result,source,unit_scope,direction FROM vocab_attempts")]
        noted = c.execute("SELECT COUNT(*) FROM reward_events WHERE kind='vocab'").fetchone()[0]
    assert len(rows) == 9 and {x["source"] for x in rows} == {"paper"} and {x["unit_scope"] for x in rows} == {"Unit 3"}
    assert sorted(x["result"] for x in rows).count("correct") == 6 and noted == 9
    # Nochmals auswerten bucht nichts doppelt.
    assert client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade").status_code == 200
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM vocab_attempts").fetchone()[0] == 9
    assert client.get("/api/accounts/1/vocab/papers", params={"subject": EN}).json()["papers"][0]["right"] == 6
    assert ids


def test_paper_of_a_parent_does_not_count_and_bad_grading_is_refused(setup):
    client, state, patch = setup
    client.app.include_router(vocab_daily.router, prefix="/api")
    words(12)
    p = client.post("/api/accounts/1/vocab/papers", json={"subject": EN, "unit": "Unit 3", "count": 10}).json()
    assert p["counts"] is False
    client.post(f"/api/accounts/1/vocab/papers/{p['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    seen = []
    mock(patch, lambda ctx: {"words": [{"nr": 1, "verdict": "richtig"}]}, seen)
    r = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade")
    assert r.status_code == 502
    assert client.get(f"/api/accounts/1/vocab/papers/{p['id']}").json()["status"] == "active"
    mock(patch, lambda ctx: {"words": [{"nr": w["nr"], "verdict": "richtig"} for w in ctx["woerter"]]}, seen)
    assert client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade").json()["result"]["richtig"] == 10
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM vocab_attempts").fetchone()[0] == 0
    child(state)
    assert client.get(f"/api/accounts/1/vocab/papers/{p['id']}").status_code == 404
    assert client.post("/api/accounts/1/vocab/papers", json={"subject": "Mathematik", "unit": "x"}).status_code == 422


def passes(patch, verdict_lists, seen):
    """Ein Durchgang je Liste der Reihe nach; die letzte bleibt stehen (D202)."""
    outs = list(verdict_lists)

    async def complete(account, purpose, instruction, context, images=None, **kw):
        seen.append(purpose)
        v = outs.pop(0) if len(outs) > 1 else outs[0]
        return json.dumps({"words": [{"nr": w["nr"], "verdict": v[w["nr"] - 1], "read": f"r{w['nr']}"} for w in context["woerter"]],
                           "overall": "Gut."}), {}, "fake"
    patch.setattr(ai, "complete", complete)


def child_paper(client, state):
    client.app.include_router(vocab_daily.router, prefix="/api")
    words(12)
    child(state)
    p = client.post("/api/accounts/1/vocab/papers", json={"subject": EN, "unit": "Unit 3", "count": 10}).json()
    client.post(f"/api/accounts/1/vocab/papers/{p['id']}/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    return p


def test_word_counts_only_when_two_passes_agree(setup):
    """D202: Uneinig heißt dritter Durchgang, die Mehrheit entscheidet; was offen
    bleibt, zählt nicht und steht als nicht sicher gelesen da."""
    client, state, patch = setup
    p = child_paper(client, state)
    R, F, U = "richtig", "falsch", "unklar"
    seen = []
    passes(patch, [[R] * 10, [F, U, U] + [R] * 7, [F, R, U] + [R] * 7], seen)
    g = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade").json()
    assert len(seen) == 3 and g["status"] == "graded"
    by = {w["nr"]: w for w in g["words"]}
    assert by[1]["verdict"] == F and by[2]["verdict"] == R and by[3]["verdict"] == U and by[3]["votes"] == [R, U, U]
    assert g["result"] == {"richtig": 8, "falsch": 1, "unklar": 1} and g["check"]["unsure"] == [3] and not g["check"]["held"]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM vocab_attempts").fetchone()[0] == 9
    assert vocab_daily.majority([R, F]) is None and vocab_daily.majority([U, U, R]) is None


def test_too_many_unsure_words_hold_the_paper_for_the_parents(setup):
    """D202: Bleiben mehr als 10 % der Wörter offen, zählt nichts, das Kind sieht
    kein Ergebnis, und die Eltern entscheiden je Wort."""
    client, state, patch = setup
    parent = state.user
    p = child_paper(client, state)
    R, F, U = "richtig", "falsch", "unklar"
    seen = []
    passes(patch, [[R] * 10, [U, U, F] + [R] * 7, [U, F, U] + [R] * 7], seen)
    g = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade").json()
    assert len(seen) == 3 and g["status"] == "review" and g["result"] is None and g["check"] is None
    assert "verdict" not in json.dumps(g["words"]) and "expected" not in json.dumps(g["words"]), "Kind sieht nichts"
    assert client.get("/api/accounts/1/vocab/papers", params={"subject": EN}).json()["papers"][0]["right"] == 0
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM vocab_attempts").fetchone()[0] == 0
    assert client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade").json()["status"] == "review"
    assert client.post(f"/api/accounts/1/vocab/papers/{p['id']}/review", json={"verdicts": {}}).status_code == 403
    state.user = parent
    seen_by_parent = client.get(f"/api/accounts/1/vocab/papers/{p['id']}").json()
    assert seen_by_parent["check"]["unsure"] == [1, 2, 3] and seen_by_parent["words"][0]["expected"]
    assert vocab_daily.review_items(1) == [{"paper_id": p["id"], "code": f"V{p['id']}", "subject": EN, "open": [1, 2, 3], "passes": 3}]
    from backend.parent_todo import vocab_review_items
    todo = vocab_review_items(1, "Beispielkind")
    assert todo[0]["title"].startswith(f"Vokabeltest V{p['id']} von Beispielkind prüfen") and "3 Wörter" in todo[0]["reason"]
    assert todo[0]["action"]["page"] == "vokabeln" and todo[0]["action"]["args"] == [EN] and todo[0]["action"]["query"] == {"paper": str(p["id"])}
    assert client.post(f"/api/accounts/1/vocab/papers/{p['id']}/review", json={"verdicts": {"1": R}}).status_code == 422
    r = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/review", json={"verdicts": {"1": R, "2": F, "3": R}})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "graded" and r.json()["result"] == {"richtig": 9, "falsch": 1, "unklar": 0}
    with closing(db.webapp_conn()) as c:
        rows = [dict(x) for x in c.execute("SELECT result,user_id FROM vocab_attempts")]
    assert len(rows) == 10 and {x["user_id"] for x in rows} == {2}, "zählt für das Kind"
    assert vocab_daily.review_items(1) == []


def test_parents_check_a_vocab_paper_themselves_and_the_trainer_follows(setup):
    """D207: Jedes falsche Wort bekommt Grund, Hinweis und Merkhilfe; Eltern prüfen
    ein ausgewertetes Blatt selbst, auf Wunsch mit KI-Vorschlag, und die
    Antworten im Trainer werden ersetzt, nicht doppelt gezählt."""
    client, state, patch = setup
    parent = state.user
    p = child_paper(client, state)
    seen = []

    async def complete(account, purpose, instruction, context, images=None, **kw):
        seen.append(context)
        ws = [{"nr": w["nr"], "verdict": "richtig", "read": f"r{w['nr']}"} for w in context["woerter"]]
        ws[0] = {"nr": 1, "verdict": "falsch", "read": "hause", "kind": "sprache", "note": "ou statt au.", "tip": "house wie Haus, nur mit ou."}
        return json.dumps({"words": ws, "overall": "Gut.", "focus": ["Schreibung mit ou üben"]}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    g = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/grade").json()
    w1 = g["words"][0]
    assert w1["kind"] == "sprache" and w1["tip"].startswith("house") and g["losses"] == [{"kind": "sprache", "label": "Rechtschreibung", "count": 1}]
    assert g["summary"]["focus"] == ["Schreibung mit ou üben"] and g["check"]["counted_at"]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM vocab_attempts WHERE result='incorrect'").fetchone()[0] == 1
    body = {"words": {str(n): {"verdict": "richtig"} for n in range(1, 11)}, "overall": {"text": "Alles richtig.", "focus": ["Weiter so"]}}
    assert client.post(f"/api/accounts/1/vocab/papers/{p['id']}/manual", json=body).status_code == 403, "Kind prüft nicht selbst"
    state.user = parent
    s = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/manual/suggest", json={"hint": "Wort 1 ist richtig."}).json()
    assert seen[-1]["eltern_hinweis"] == "Wort 1 ist richtig." and seen[-1]["woerter"][0]["bisher"] == "falsch" and s["words"]["1"]["kind"] == "sprache"
    assert client.post(f"/api/accounts/1/vocab/papers/{p['id']}/manual", json={"words": {"1": {"verdict": "richtig"}}}).status_code == 422
    body["words"]["2"] = {"verdict": "falsch", "kind": "regel", "note": "Artikel fehlt.", "tip": "Immer mit Artikel lernen."}
    done = client.post(f"/api/accounts/1/vocab/papers/{p['id']}/manual", json=body).json()
    assert done["result"] == {"richtig": 9, "falsch": 1, "unklar": 0} and done["check"]["manual"]
    assert done["words"][1]["checked_by_parent"] and done["words"][1]["read"] == "r2"
    with closing(db.webapp_conn()) as c:
        rows = [tuple(x) for x in c.execute("SELECT word_id,result FROM vocab_attempts ORDER BY id")]
    assert len(rows) == 10 and sum(1 for x in rows if x[1] == "incorrect") == 1, "ersetzt, nicht doppelt"
    child(state)
    kid = client.get(f"/api/accounts/1/vocab/papers/{p['id']}").json()
    assert kid["overall"] == "Alles richtig." and kid["words"][1]["tip"] == "Immer mit Artikel lernen." and "_prior" not in json.dumps(kid)


def test_test_mode_blocks_paper_writes_but_not_the_pensum():
    assert view_mode.TEST_BLOCKED.match("/api/accounts/1/vocab/papers")
    assert view_mode.TEST_BLOCKED.match("/api/accounts/1/learning/vocab/attempts")
    assert not view_mode.TEST_BLOCKED.match("/api/accounts/1/vocabulary")


def task(title, notes, due):
    with closing(db.webapp_conn()) as c, c:
        return c.execute("INSERT INTO tasks(account_id,title,notes,status,due_date,source,created_at,updated_at) "
                         "VALUES(1,?,?,'open',?,'ha_todo','t','t')", (title, notes, due.isoformat())).lastrowid


def test_a_vocab_test_announced_in_homework_becomes_the_pensum(env, free):
    """D187: „Vokabeln Unit 3 lernen (Überprüfung … am TT.MM.JJJJ)“ reicht als Testtermin."""
    words(60)
    tid = task("Englisch", "Vocabulary Unit 3 lernen (Überprüfung der Vokabeln am 16.10.2026)\nFällig bis: Fr 16.10.",
               MON + timedelta(days=11))
    items = vp.daily(1, MON)
    assert len(items) == 1 and items[0]["exam_key"] == f"task:{tid}" and items[0]["unit"] == "Unit 3"
    assert items[0]["days_left"] == 9 and items[0]["why"].startswith("Der Vokabeltest ist")
    assert vp.missing_units(1, MON) == []
    # Erledigt oder ohne Lektion: kein Test; Lektion unbekannt: „fehlt“.
    task("Englisch", "Vokabeln Unit 4 lernen (Überprüfung am 16.10.2026)", MON + timedelta(days=11))
    task("Englisch", "Text lesen", MON + timedelta(days=2))
    assert [m["unit_ref"] for m in vp.missing_units(1, MON)] == ["Unit 4"]
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE tasks SET status='done' WHERE id=?", (tid,))
    assert all(i["exam_key"] is None for i in vp.daily(1, MON))
