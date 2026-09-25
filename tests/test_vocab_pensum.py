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


def test_test_mode_blocks_paper_writes_but_not_the_pensum():
    assert view_mode.TEST_BLOCKED.match("/api/accounts/1/vocab/papers")
    assert view_mode.TEST_BLOCKED.match("/api/accounts/1/learning/vocab/attempts")
    assert not view_mode.TEST_BLOCKED.match("/api/accounts/1/vocabulary")
