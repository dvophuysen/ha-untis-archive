"""Sprechproben für Sprechprüfungen (D194).

Das Kind führt mit dem Lernbegleiter als Prüfer ein Gespräch in der Fremdsprache,
per Sprechknopf. Am Ende bewertet ein eigener Modellaufruf das Gespräch nach
sechs Kriterien (1–4, je mit Beleg aus dem Gesagten) gegen das Niveau des
Jahrgangs und den Stoff aus dem Unterricht, findet höchstens drei Baustellen und
prüft die Baustellen der letzten Probe nach. Aussprache wird nicht bewertet: Das
Modell sieht nur die Abschrift.
"""
from __future__ import annotations

import json
import logging
from contextlib import closing
from typing import Literal

from pydantic import BaseModel, Field

from .db import webapp_conn
from .learning import now_iso

LOG = logging.getLogger("schul_cockpit.oral_exam")

CRITERIA = [
    ("aufgabe", "Aufgabe und Inhalt"),
    ("interaktion", "Interaktion"),
    ("wortschatz", "Wortschatz"),
    ("grammatik", "Grammatik"),
    ("ausdruck", "Komplexität und Ausdruck"),
    ("fluessigkeit", "Flüssigkeit"),
]
LABELS = dict(CRITERIA)
READY_SCORE = 3       # jedes Kriterium mindestens 3 von 4
READY_RUNS = 2        # in den letzten zwei Proben zum Thema
MIN_ANSWERS = 3       # darunter ist eine Bewertung nicht verlässlich
TOPIC_TURNS = 8       # Antworten, nach denen der Prüfer eine Themenprobe abrundet
FULL_TURNS = 14       # dasselbe für die Gesamtprobe

# Niveau nach Kerncurriculum Niedersachsen (Gymnasium, erste Fremdsprache):
# Ende Jahrgang 6 A1+/A2 mit den Themen Familie und Freunde, Essen und Trinken,
# Einkaufen, Schule, Hobbys, nähere Umgebung. Spätere Jahrgänge grob nach GER.
LEVELS = [
    (6, "GER A1+ bis A2 (Kerncurriculum Niedersachsen, Ende Jahrgang 6): elementarer Wortschatz aus Einzelwörtern und "
        "Wendungen für konkrete Situationen und einfache Grundbedürfnisse; Themen Familie und Freunde, Essen und Trinken, "
        "Einkaufen, Schule, Hobbys, nähere Umgebung. Kurze, einfache Sätze, verbunden mit and, but, because, then; einfache "
        "Fragen stellen und beantworten; über Vergangenes in einfachen Sätzen berichten. Pausen, Wiederholen und "
        "Umformulieren sind auf diesem Niveau normal; der Gesprächspartner hilft mit."),
    (8, "GER A2 bis A2+ (Jahrgang 7 und 8): zusammenhängend über Erlebnisse, Pläne und Vorlieben sprechen, kurze "
        "Begründungen und Vergleiche, einfache Gespräche ohne viel Hilfe führen."),
    (10, "GER B1 (Ende Jahrgang 10): zusammenhängend erzählen, Meinungen begründen, auf Unerwartetes reagieren, Gespräche "
         "zu vertrauten Themen weitgehend selbstständig führen."),
    (13, "GER B2 (Oberstufe): klar und detailliert zu vielen Themen, Standpunkte erläutern, Vor- und Nachteile abwägen."),
]


def level_for(grade) -> str:
    try:
        g = int(str(grade).strip()[:2])
    except (TypeError, ValueError):
        g = 6
    return next((text for top, text in LEVELS if g <= top), LEVELS[-1][1])


# ------------------------------------------------------------------ Referenzen

def references(account_id: int, exam_key: str, subject: str | None) -> list[dict]:
    """Was im Unterricht vorkam, als ankreuzbare Referenz für die Bewertung:
    die Themen aus dem Unterricht (auch die zurückgetretenen) und die Einheiten
    des Vokabeltrainers. Voreingestellt ist alles angekreuzt."""
    from .exam_meta import excluded_refs
    off = set(excluded_refs(account_id, exam_key))
    out = []
    with closing(webapp_conn()) as c:
        for r in c.execute("SELECT id,title,detail FROM exam_topics WHERE account_id=? AND exam_key=? AND origin='assumed' "
                           "ORDER BY position,id", (account_id, exam_key)):
            label = r["title"] + (f" · {r['detail']}" if r["detail"] and r["detail"] != r["title"] else "")
            out.append({"key": f"topic:{r['id']}", "label": label[:160], "kind": "topic"})
    for u in _vocab_units(account_id, subject):
        out.append({"key": f"vocab:{u['unit']}", "label": f"Vokabeln {u.get('label') or u['unit']}", "kind": "vocab"})
    return [{**r, "checked": r["key"] not in off} for r in out]


def _vocab_units(account_id: int, subject: str | None) -> list[dict]:
    if not subject:
        return []
    try:
        from . import vocab
        return [u for u in vocab.units(account_id, subject.casefold()) if u.get("unit")]
    except Exception:
        LOG.debug("Vokabeleinheiten nicht lesbar", exc_info=True)
        return []


def _unit_words(account_id: int, subject: str, unit: str, limit: int = 40) -> list[str]:
    try:
        from . import vocab
        cards = vocab.cards(account_id, subject.casefold(), unit, 1, "from", limit)
    except Exception:
        return []
    return [str(w.get("foreign_word") or w.get("foreign") or w.get("front") or "")[:40] for w in cards if w][:limit]


def reference_context(account_id: int, exam_key: str, subject: str | None) -> dict:
    """Die angekreuzten Referenzen für Prüfer und Bewertung."""
    refs = [r for r in references(account_id, exam_key, subject) if r["checked"]]
    topics = [r["label"] for r in refs if r["kind"] == "topic"]
    units = []
    for r in [r for r in refs if r["kind"] == "vocab"][:6]:
        if r["kind"] == "vocab":
            unit = r["key"].split(":", 1)[1]
            units.append({"einheit": r["label"], "woerter": _unit_words(account_id, subject or "", unit)})
    return {"themen_im_unterricht": topics, "vokabeln": units}


# ------------------------------------------------------------------ Proben

def sims(account_id: int, exam_key: str, limit: int = 20) -> list[dict]:
    try:
        with closing(webapp_conn()) as c:
            rows = [dict(r) for r in c.execute(
                "SELECT o.*, t.title AS topic_title FROM oral_sims o LEFT JOIN exam_topics t ON t.id=o.topic_id "
                "WHERE o.account_id=? AND o.exam_key=? ORDER BY o.id DESC LIMIT ?", (account_id, exam_key, limit))]
    except Exception:
        return []
    return [public(r) for r in rows]


def public(r: dict) -> dict:
    scores = json.loads(r.get("scores_json") or "[]")
    return {"id": r["id"], "session_id": r["session_id"], "topic_id": r["topic_id"], "full": bool(r["full"]),
            "topic_title": r.get("topic_title") or ("Gesamtprobe" if r["full"] else ""), "created_at": r["created_at"],
            "scores": scores, "weak_spots": json.loads(r.get("weak_json") or "[]"),
            "followups": json.loads(r.get("followups_json") or "[]"), "summary": r.get("summary") or "",
            "level_note": r.get("level_note") or "", "reliable": bool(r["reliable"]), "measures": json.loads(r.get("measures_json") or "{}"),
            "verdict": r.get("verdict"), "lowest": min((s.get("score") or 0 for s in scores), default=0)}


def open_weak_spots(account_id: int, exam_key: str) -> list[dict]:
    """Die Baustellen der letzten verlässlichen Probe dieser Arbeit: Die nächste
    Probe soll sie gezielt ansprechen und nachprüfen."""
    for s in sims(account_id, exam_key, 5):
        if s["reliable"]:
            return s["weak_spots"]
    return []


def calibration(account_id: int, exam_key: str) -> list[str]:
    """Was Eltern zu früheren Bewertungen gesagt haben (zu streng, passt, zu mild)."""
    notes = []
    for s in sims(account_id, exam_key, 10):
        if s["verdict"]:
            notes.append({"streng": "Eltern: diese Bewertung war zu streng", "passt": "Eltern: diese Bewertung passte",
                          "mild": "Eltern: diese Bewertung war zu mild"}[s["verdict"]] +
                         f" (Probe vom {s['created_at'][:10]}, Punkte {[x.get('score') for x in s['scores']]})")
    return notes[:5]


def set_verdict(account_id: int, sim_id: int, verdict: str | None) -> bool:
    with closing(webapp_conn()) as c, c:
        return bool(c.execute("UPDATE oral_sims SET verdict=?,verdict_at=? WHERE id=? AND account_id=?",
                              (verdict, now_iso(), sim_id, account_id)).rowcount)


def topic_ready(account_id: int, exam_key: str, topic_id: int) -> bool:
    """Ein Sprechthema sitzt, wenn die letzten zwei verlässlichen Proben, die es
    abdecken (Themenprobe oder Gesamtprobe), in jedem Kriterium mindestens 3 haben."""
    runs = [s for s in sims(account_id, exam_key, 20) if s["reliable"] and (s["full"] or s["topic_id"] == topic_id)][:READY_RUNS]
    return len(runs) == READY_RUNS and all(s["lowest"] >= READY_SCORE for s in runs)


def measured(account_id: int, exam_key: str) -> bool:
    """Gab es schon eine verlässliche Probe? Sonst kommt zuerst der Einstiegstest (D195)."""
    return any(s["reliable"] for s in sims(account_id, exam_key, 20))


def full_ready(account_id: int, exam_key: str) -> bool:
    runs = [s for s in sims(account_id, exam_key, 20) if s["reliable"] and s["full"]][:1]
    return bool(runs) and runs[0]["lowest"] >= READY_SCORE and not runs[0]["weak_spots"]


def done_on(account_id: int, exam_key: str, topic_id: int | None, first: str, last: str) -> bool:
    try:
        with closing(webapp_conn()) as c:
            if topic_id:
                q, args = "topic_id=?", (topic_id,)
            else:
                q, args = "full=1", ()
            return bool(c.execute(f"SELECT 1 FROM oral_sims WHERE account_id=? AND exam_key=? AND {q} "
                                  "AND substr(created_at,1,10) BETWEEN ? AND ? LIMIT 1", (account_id, exam_key, *args, first, last)).fetchone())
    except Exception:
        return False


# ------------------------------------------------------------------ Prüfer

def pictures(account_id: int, subject: str | None, limit: int = 12, prefer: list[int] | None = None) -> list[dict]:
    """Bilder für die Bildbeschreibung: Fotos, Zeichnungen, Comics und Karten aus
    den abgelegten Seiten des Fachs, mit Beschreibung (D198)."""
    if not subject:
        return []
    try:
        from .page_figures import PICTURE_KINDS, for_subject
        return [{"id": f["id"], "beschreibung": f["beschreibung"], "seite": f["seite"]}
                for f in for_subject(account_id, subject, PICTURE_KINDS, limit, prefer=prefer)]
    except Exception:
        LOG.debug("Bilder für die Sprechprobe nicht lesbar", exc_info=True)
        return []

def spoken_topics(account_id: int, exam_key: str) -> list[dict]:
    """Die Sprechthemen: von Eltern eingetragen. Der Zettel der Lehrkraft
    beschreibt bei einer Sprechprüfung den Ablauf, keine Themen (D195)."""
    with closing(webapp_conn()) as c:
        return [dict(r) for r in c.execute(
            "SELECT id,title,detail FROM exam_topics WHERE account_id=? AND exam_key=? AND stale=0 AND origin='manual' "
            "ORDER BY position,id", (account_id, exam_key))]


def structure(account_id: int, exam_key: str) -> list[dict]:
    """Aufbau und Ablauf der Prüfung laut Zettel der Lehrkraft (Teile, Bewertung, Organisation)."""
    with closing(webapp_conn()) as c:
        return [{"punkt": r[0], "inhalt": r[1]} for r in c.execute(
            "SELECT title,detail FROM exam_topics WHERE account_id=? AND exam_key=? AND stale=0 AND origin='notice' "
            "ORDER BY position,id", (account_id, exam_key))]

def context(account_id: int, source: dict, subject: str, grade) -> dict:
    """Was der Prüfer in jedem Zug weiß."""
    from .exam_meta import get, pinned, pinned_context
    key = source.get("exam_key") or ""
    meta = get(account_id, key)
    topics, layout = spoken_topics(account_id, key), structure(account_id, key)
    this = next((t for t in topics if t["id"] == source.get("topic_id")), None)
    return {
        "art": "Gesamtprobe wie die echte Prüfung, Teil für Teil nach oral.pruefungsaufbau" if source.get("full") else "Themenprobe",
        "thema": {"titel": this["title"], "hinweis": this["detail"]} if this else None,
        "alle_sprechthemen": [{"titel": t["title"], "hinweis": t["detail"]} for t in topics],
        "pruefungsaufbau": layout,
        "hinweise_eltern": meta.get("note") or "",
        "niveau": level_for(grade),
        "unterricht": reference_context(account_id, key, subject),
        "baustellen_letztes_mal": open_weak_spots(account_id, key),
        "bilder": pictures(account_id, subject, prefer=pinned(account_id, key)),
        "material_eltern": pinned_context(account_id, key, 2500),
        "bild_gezeigt": source.get("bild"),
        "antworten_bis_zum_abrunden": FULL_TURNS if source.get("full") else TOPIC_TURNS,
    }


ORAL_RULE = (
    "SPRECHPROBE: Du bist der Prüfer einer mündlichen Prüfung in der Fremdsprache (oral.art, oral.thema, "
    "oral.hinweise_eltern). Steht in oral.pruefungsaufbau der Ablauf laut Lehrkraft (etwa Interview, Monologue, "
    "Dialogue), folgst du ihm in der Gesamtprobe Teil für Teil und kündigst jeden Teil kurz an; gibt es in oral.bilder "
    "kein passendes Bild, beschreibst du ein Bild in zwei, drei einfachen Sätzen und lässt das Kind weiter "
    "beschreiben und deuten; im Dialogue spielst du den Partner. Für eine Bildbeschreibung wähle, wenn vorhanden, ein "
    "passendes Bild aus oral.bilder (nach beschreibung) und setze bild auf seine id: Das Kind sieht es dann in der App und "
    "du ab dem nächsten Zug auch; kündige es an („Look at the picture.“). Nur ein Bild je Teil. Sprich ausschließlich in der Fremdsprache, freundlich und natürlich, in kurzen Sätzen auf "
    "dem Niveau oral.niveau und mit Wörtern aus oral.unterricht. Jeder Zug: höchstens eine kurze Reaktion auf das "
    "Gesagte und genau eine Frage oder ein Sprechanlass (erzählen, beschreiben, begründen, nachfragen, Rollenspiel). "
    "Korrigiere während der Probe nicht und bewerte nicht, wie in einer echten Prüfung; die Bewertung kommt am Ende "
    "von der App. Baue gezielt Gelegenheiten für oral.baustellen_letztes_mal ein (etwa nach dem letzten Wochenende "
    "fragen, wenn die Vergangenheit eine Baustelle war), ohne sie zu nennen. Antwortet das Kind auf Deutsch oder "
    "versteht es nicht, formuliere einfacher und gib höchstens ein Stichwort; eine Übersetzung nur, wenn es ausdrücklich "
    "fragt. Wenn es nur mit einzelnen Wörtern antwortet, bitte um einen ganzen Satz. Stelle keine Aufgaben mit Auswahl "
    "oder Lücken: action ist clarify, task und assessment bleiben leer, choices leer. Nach etwa "
    "oral.antworten_bis_zum_abrunden Antworten des Kindes rundest du mit einem Satz ab und setzt action finish. "
    "summary: Stichpunkte auf Deutsch, was das Kind bisher gesagt hat. ")


# ------------------------------------------------------------------ Bewertung

class Score(BaseModel):
    criterion: Literal["aufgabe", "interaktion", "wortschatz", "grammatik", "ausdruck", "fluessigkeit"]
    score: int = Field(ge=1, le=4)
    evidence: str = Field(default="", max_length=300)
    comment: str = Field(default="", max_length=300)


class WeakSpot(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    example: str = Field(default="", max_length=200)
    better: str = Field(default="", max_length=200)
    next_check: str = Field(default="", max_length=200)


class Followup(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    status: Literal["besser", "gleich", "schlechter", "nicht_geprueft"]
    evidence: str = Field(default="", max_length=200)


class Assessment(BaseModel):
    scores: list[Score] = Field(min_length=1, max_length=6)
    weak_spots: list[WeakSpot] = Field(default_factory=list, max_length=3)
    followups: list[Followup] = Field(default_factory=list, max_length=6)
    summary: str = Field(min_length=2, max_length=900)
    level_note: str = Field(default="", max_length=200)
    reliable: bool = True


ASSESS_INSTRUCTION = (
    "Du bewertest eine Sprechprobe eines Schulkindes (Abschrift unten, gespraech). Bewerte jedes der sechs Kriterien "
    "(kriterien) von 1 bis 4: 4 = für den Jahrgang sicher und darüber, 3 = entspricht dem Niveau, 2 = teilweise, "
    "1 = noch deutlich darunter. Maßstab ist niveau, dazu der Stoff aus unterricht: Strukturen und Wörter, die dort "
    "vorkamen, zählen voll; Fehler darin sind Baustellen. Was im Unterricht noch nicht vorkam, ist Bonus, nie Abzug. "
    "Jede Punktzahl braucht als evidence ein wörtliches Zitat des Kindes aus dem Gespräch. Aussprache bewertest du "
    "nicht, du siehst nur eine Abschrift; die Spracherkennung glättet Fehler eher, als dass sie welche erfindet. "
    "Flüssigkeit schätzt du aus messwerte (Wörter je Minute beim Sprechen, Länge der Antworten) und daraus, ob das "
    "Kind selbst weiterspricht. weak_spots: höchstens drei, die wichtigsten zuerst, je mit label (kurz, deutsch), "
    "example (Zitat des Kindes), better (bessere Formulierung in der Fremdsprache) und next_check (wie der Prüfer es "
    "beim nächsten Mal gezielt prüft). followups: für jede Baustelle aus baustellen_letztes_mal der Stand heute "
    "(besser, gleich, schlechter, nicht_geprueft) mit Zitat. summary: 2 bis 4 Sätze auf Deutsch direkt an das Kind, "
    "ehrlich und ermutigend, mit einem konkreten Tipp. level_note: ein Satz zur Einordnung gegen das Niveau. "
    "reliable false, wenn das Kind weniger als drei inhaltliche Antworten gegeben hat. Gab es eine Bildbeschreibung "
    "(gezeigtes_bild, das Bild liegt bei), prüfe bei Aufgabe und Inhalt, ob das Beschriebene wirklich zu sehen ist. kalibrierung enthält Urteile "
    "der Eltern zu früheren Bewertungen; richte die Strenge danach aus. Antworte ausschließlich im JSON-Schema: ")


def transcript(c, session_id: int) -> tuple[list[dict], dict]:
    rows = [dict(r) for r in c.execute("SELECT role,text,payload FROM mentor_messages WHERE session_id=? ORDER BY id", (session_id,))]
    talk, words, secs, answers = [], 0, 0, 0
    for r in rows:
        p = json.loads(r["payload"] or "{}")
        if r["role"] == "assistant":
            if p.get("oral_result"):
                continue
            talk.append({"pruefer": r["text"]})
        elif r["role"] == "user":
            if p.get("kind") == "finish":
                continue
            n = len(r["text"].split())
            answers += 1
            words += n
            if p.get("spoken") and p.get("seconds"):
                secs += int(p["seconds"])
            talk.append({"kind": r["text"], "gesprochen": bool(p.get("spoken")), "sekunden": p.get("seconds")})
    measures = {"antworten": answers, "woerter": words, "woerter_je_antwort": round(words / answers, 1) if answers else 0,
                "woerter_je_minute": round(words / secs * 60) if secs >= 10 else None,
                "gesprochen": sum(1 for t in talk if t.get("gesprochen"))}
    return talk, measures


async def assess(account_id: int, session: dict, source: dict, grade) -> dict:
    """Die Bewertung am Ende einer Sprechprobe, gespeichert als Probe der Arbeit."""
    from . import ai_gateway as ai
    key = source.get("exam_key") or ""
    with closing(webapp_conn()) as c:
        talk, measures = transcript(c, session["id"])
    ctx = {**context(account_id, source, session["subject"], grade),
           "kriterien": [{"key": k, "name": v} for k, v in CRITERIA],
           "gespraech": talk, "messwerte": measures, "kalibrierung": calibration(account_id, key)}
    ctx.pop("antworten_bis_zum_abrunden", None)
    ctx.pop("bilder", None)
    images = []
    shown = source.get("bild") or (json.loads(session.get("source_json") or "{}").get("bild"))
    if shown:
        from .page_figures import image_part
        part = image_part(account_id, shown["id"])
        if part:
            images.append(part)
            ctx["gezeigtes_bild"] = shown.get("beschreibung") or ""
    if measures["antworten"] < MIN_ANSWERS:
        result = Assessment(scores=[Score(criterion=k, score=1, evidence="", comment="zu kurz") for k, _ in CRITERIA],
                            summary="Das war noch zu kurz für eine Bewertung. Beim nächsten Mal ein paar Fragen mehr, dann sage ich dir, was schon gut klingt.",
                            reliable=False)
    else:
        raw, _, _ = await ai.complete(account_id, "mentor", ASSESS_INSTRUCTION + json.dumps(Assessment.model_json_schema()), ctx,
                                      images or None, max_output=3000, session_id=session["id"], effort="medium")
        result = Assessment.model_validate_json(raw)
        result.reliable = result.reliable and measures["antworten"] >= MIN_ANSWERS
    seen = {s.criterion for s in result.scores}
    scores = [s.model_dump() | {"label": LABELS[s.criterion]} for s in result.scores]
    scores += [{"criterion": k, "label": v, "score": None, "evidence": "", "comment": "nicht bewertet"} for k, v in CRITERIA if k not in seen]
    order = [k for k, _ in CRITERIA]
    scores.sort(key=lambda s: order.index(s["criterion"]))
    with closing(webapp_conn()) as c, c:
        sid = c.execute(
            "INSERT INTO oral_sims(account_id,exam_key,topic_id,full,session_id,created_at,scores_json,weak_json,followups_json,summary,level_note,reliable,measures_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (account_id, key, source.get("topic_id"), int(bool(source.get("full"))), session["id"], now_iso(),
             json.dumps([s for s in scores if s["score"] is not None], ensure_ascii=False),
             json.dumps([w.model_dump() for w in result.weak_spots], ensure_ascii=False),
             json.dumps([f.model_dump() for f in result.followups], ensure_ascii=False),
             result.summary, result.level_note, int(result.reliable), json.dumps(measures, ensure_ascii=False))).lastrowid
        row = dict(c.execute("SELECT * FROM oral_sims WHERE id=?", (sid,)).fetchone())
    return public(row)
