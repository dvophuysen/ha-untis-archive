"""Plausibilität einer Themenliste gegen den Unterricht: die 1 dieses Kindes sieht aus wie eine 7."""
from test_learning import env
from backend import notice_check as nc

LESSONS = [
    "Wortschatztraining Lektion 1, Übungen zu debere (TB S. 13 Aufg. C, AH S. 7 Aufg. C und Z)",
    "Textband Seite 10, 11 lesen, für die Klassenarbeit lernen",
    "Begleitband S. 13-15 Deklination und Konjugation; BB S. 14 Subjekt und Prädikat",
    "Lernwörter Lektion 1 BB S. 10, 11",
    "Gefahr im Circus Maximus: Textband S. 14, 15 übersetzen",
]


def test_the_lessons_places_are_collected_per_part():
    known = nc.taught_places(LESSONS)
    assert known["Textband"] == {10, 11, 13, 14, 15} and known["Arbeitsheft"] == {7}
    assert known["Begleitband"] == {10, 11, 13, 14, 15}


def test_variants_are_single_digit_confusions():
    assert nc.variants(70) == [10, 76, 16]
    assert nc.variants(11) == [71, 17, 77] and nc.variants(77) == [17, 71, 11]
    assert nc.variants(5) == [] and nc.variants(100) == [700, 160, 106, 766]


def test_a_misread_notice_is_flagged_with_the_taught_page_as_suggestion():
    known = nc.taught_places(LESSONS)
    misread = "Voc. 7. Lektion S. 70, 77\nSubstantive: a/o-Deklination BB. S. 73\nVerben a/e/i-Konjugation BB S. 73-75\nSubjekt im Prädikat BB S. 74\nGefahr im C.M. TB S. 70, 77, 74, 75"
    result = nc.check(misread, known)
    # „TB S. 70, 77, 74, 75“: der Parser nimmt nur die aufsteigende Aufzählung (70, 77), also neun Stellen.
    assert result["checked"] and result["cited"] == 9
    flagged = {(u["label"], u["page"]): u["suggest"] for u in result["unknown"]}
    # Jede 7 ist eine 1: der Unterricht kennt 10, 11, 13, 14, 15, nie 70 oder 73.
    assert flagged[("Begleitband", 73)] == 13 and flagged[("Begleitband", 74)] == 14 and flagged[("Begleitband", 75)] == 15
    assert flagged[("Textband", 70)] == 10 and flagged[("Textband", 77)] == 11
    assert all(v is not None for v in flagged.values())
    # Die richtige Lesung hat nichts zu beanstanden.
    right = "Voc. 1. Lektion S. 10, 11\nSubstantive: a/o-Deklination BB. S. 13\nVerben a/e/i-Konjugation BB S. 13-15\nSubjekt im Prädikat BB. S. 14\nGefahr im C.M. TB S. 10, 11, 14, 15"
    assert nc.check(right, known)["unknown"] == []
    # Ohne Unterricht wird nichts behauptet.
    assert nc.check(right, {})["checked"] is False


def test_the_review_card_gets_the_check_for_notices_only(env):
    from contextlib import closing
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend import db
    from backend.auth import get_current_user
    from backend.routers import materials as routes
    client, state, patch = env
    app = FastAPI(); app.include_router(routes.router, prefix="/api"); app.dependency_overrides[get_current_user] = lambda: state.user
    c = TestClient(app)
    patch.setattr(nc, "mentions", lambda account_id: ([{"kind": "lesson", "subject": "LATEIN", "text": t} for t in LESSONS], "2026-08-01"))
    with closing(db.webapp_conn()) as conn, conn:
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,analysis_state,confidence,handwritten,created_at,updated_at) "
                     "VALUES(1,'exam_notice','LATEIN','Zettel','Voc. 7. Lektion S. 70, 77 BB S. 73','ready',0.78,1,'now','now')")
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,analysis_state,confidence,created_at,updated_at) "
                     "VALUES(1,'worksheet','LATEIN','Blatt','S. 70 üben','ready',0.5,'now','now')")
    items = {m["kind"]: m for m in c.get("/api/accounts/1/materials?books=0").json()["materials"]}
    notice = items["exam_notice"]
    assert notice["needs_review"] and notice["plausibility"]["checked"]
    assert [(u["page"], u["suggest"]) for u in notice["plausibility"]["unknown"]] == [(70, 10), (77, 11), (73, 13)]
    # Ein gedrucktes Arbeitsblatt bekommt keine Prüfung, auch wenn es zum Gegenlesen steht.
    assert items["worksheet"]["needs_review"] and "plausibility" not in items["worksheet"]
