"""Tägliches Vokabelpensum mit Zielkurve bis zum Test (D181).

Steht in den nächsten sechs Wochen ein Vokabeltest oder eine Arbeit mit einem
Vokabelthema an, verteilt die App die Wörter der Einheit, die noch nicht sicher
sitzen, auf die verbleibenden Schultage und legt die fälligen Wiederholungen
dazu. Mindestens 10, höchstens 40 Wörter am Tag; je näher der Test und je
schwächer die Trefferquote, desto mehr. Der nächste Test kommt zuerst, höchstens
zwei Einträge am Tag. Ohne anstehenden Test kommt ein Grundpensum aus der
aktiven Einheit, in der am meisten dran ist: Wackelwörter, fällige
Wiederholungen und noch neue Wörter, höchstens 15 (D212).

Das Pensum wird aus dem Stand vor dem Tag gerechnet und bleibt über den Tag
gleich; erledigt ist es, wenn das Kind heute mindestens so viele verschiedene
Wörter der Einheit im Trainer geübt hat. Wochenenden und Ferien sind frei
(D179), außer die Zeit bis zum Test reicht sonst nicht.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from contextlib import closing
from datetime import date, timedelta

from .db import webapp_conn
from .request_cache import memo

LOG = logging.getLogger("schul_cockpit.vocab_pensum")

HORIZON = 42
MIN_WORDS, MAX_WORDS = 10, 40
# Ohne Test (D212): höchstens so viele Wörter aus einer aktiven Einheit am Tag.
# Aktiv ist eine Einheit, die in den letzten sechs Wochen geübt wurde oder die
# der Unterricht der letzten zwei Wochen nennt („Unidad 3“ im Stundenthema).
BASE_MAX = 15
LESSON_DAYS = 14
UNSCOPED_MIN = 3
MAX_ENTRIES = 2
SECURE = ("sitzt", "gefestigt")
# Ab so vielen gewerteten Antworten gilt die Trefferquote als belastbar.
RATE_MIN_ANSWERS = 5
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


# ------------------------------------------------------------------ Grundlagen

def school_days(account_id: int, first: date, last: date) -> list[date]:
    """Schultage im Zeitraum. Der Stundenplan reicht nicht beliebig weit nach
    vorn: Jenseits des letzten bekannten Unterrichtstags zählen Montag bis
    Freitag ohne Ferien und Feiertage, wie im Lernplan (A13). Vorher verteilte
    das Pensum einen Test nach den Herbstferien auch auf die Ferientage."""
    if last < first:
        return []
    from . import rewards
    from .schoolday import project
    known = set(rewards.school_days(account_id, first, last))
    horizon = max(known) if known else first - timedelta(days=1)
    return project(account_id, known, first, last, horizon)


def _upcoming(account_id: int, day: date) -> list[dict]:
    """Arbeiten der nächsten sechs Wochen mit wenigstens einem Vokabelthema."""
    from .lernstand import is_vocab_topic
    until = day + timedelta(days=HORIZON)
    with closing(webapp_conn()) as c:
        try:
            dates = {r[0]: r[1] for r in c.execute(
                "SELECT exam_key,exam_date FROM exam_dates WHERE account_id=? AND exam_date>? AND exam_date<=?",
                (account_id, day.isoformat(), until.isoformat()))}
        except Exception:
            return []  # Tabelle entsteht erst mit der ersten Arbeit
        if not dates:
            return []
        marks = ",".join("?" * len(dates))
        topics = [dict(r) for r in c.execute(
            f"SELECT id,exam_key,subject,title,places_json FROM exam_topics WHERE account_id=? AND stale=0 "
            f"AND exam_key IN ({marks}) ORDER BY position,id", (account_id, *dates))]
    out = []
    for key, when in sorted(dates.items(), key=lambda kv: (kv[1], kv[0])):
        mine = [t for t in topics if t["exam_key"] == key]
        vocab_topics = [t for t in mine if is_vocab_topic(t)]
        if vocab_topics:
            out.append({"exam_key": key, "date": date.fromisoformat(when[:10]), "topics": vocab_topics,
                        "only_vocab": len(vocab_topics) == len(mine)})
    return out


# Vokabeltests stehen oft nur in der Hausaufgabe: „Vokabeln Lektion 2 lernen
# (Überprüfung der Vokabeln von Lektion 2 am 02.10.2026)“ (D187).
HOMEWORK_VOCAB = re.compile(r"vokabel|wortschatz|lernwörter|lernwoerter|vocabulary|vocab|vocabulario|words", re.I)
HOMEWORK_UNIT = re.compile(r"\b(unidad|unit|lektion|lecci[oó]n|le[cç]on|m[oó]dulo|kapitel|chapter|module)\s*0*(\d{1,2})\b", re.I)
HOMEWORK_DATE = re.compile(r"\bam\s+(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _unit_number(label: str) -> tuple[str, int] | None:
    from .vocab import UNIT_KEY
    m = UNIT_KEY.match((label or "").strip())
    return (m.group(1).casefold()[:3], int(m.group(2))) if m else None


@memo
def _homework_tests(account_id: int, day: date) -> list[dict]:
    """Offene Hausaufgaben, die einen Vokabeltest zu einer Lektion ankündigen.
    Termin: das Datum „am TT.MM.JJJJ“ im Text, sonst der Fälligkeitstag."""
    from . import vocab
    from .subject_names import SubjectCatalog
    until = day + timedelta(days=HORIZON)
    with closing(webapp_conn()) as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id,title,notes,subject_name,subject_untis_id,due_date FROM tasks WHERE account_id=? "
            "AND status NOT IN ('done','skipped') AND due_date IS NOT NULL AND due_date>? AND due_date<=?",
            (account_id, day.isoformat(), until.isoformat()))]
    if not rows:
        return []
    catalog = SubjectCatalog(account_id)
    out = []
    for row in rows:
        text = f"{row.get('title') or ''} {row.get('notes') or ''}"
        unit_ref = HOMEWORK_UNIT.search(text)
        if not HOMEWORK_VOCAB.search(text) or not unit_ref:
            continue
        subject = (catalog.task(row).get("subject_name") or row.get("subject_name")
                   or ((row.get("title") or "").split() or [""])[0])
        if not subject or not vocab.language_of(subject):
            continue
        when = date.fromisoformat(row["due_date"][:10])
        m = HOMEWORK_DATE.search(text)
        if m:
            try:
                when = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
        if not day < when <= until:
            continue
        want = (unit_ref.group(1).casefold()[:3], int(unit_ref.group(2)))
        found = next(((u["unit"], u.get("label") or u["unit"]) for u in vocab.units(account_id, subject)
                      if u.get("words") and _unit_number(u.get("label") or u["unit"]) == want), None)
        out.append({"exam_key": f"task:{row['id']}", "date": when, "only_vocab": True, "subject": subject,
                    "unit": found, "unit_ref": f"{unit_ref.group(1).capitalize()} {want[1]}", "task_id": row["id"]})
    return sorted(out, key=lambda e: e["date"])


def missing_units(account_id: int, day: date) -> list[dict]:
    """Angekündigte Vokabeltests, deren Lektion noch nicht im Trainer steht."""
    try:
        return [{"subject": e["subject"], "unit_ref": e["unit_ref"], "date": e["date"].isoformat(), "task_id": e["task_id"]}
                for e in _homework_tests(account_id, day) if not e["unit"]]
    except Exception:
        LOG.warning("Vokabeltests aus Hausaufgaben nicht lesbar", exc_info=True)
        return []


def trainer_unit(account_id: int, subject: str, places: list[dict]) -> tuple[str, str] | None:
    """Die Einheit des Trainers (Schlüssel und Anzeigename) zu den Stellen eines
    Vokabelthemas. Mit geprüftem Buchbestand heißen die Einheiten anders als die
    gelesenen Wörter; ohne ihn führt das Verzeichnis die Namen (D113)."""
    from . import vocab, vocab_catalog
    from .sources import serves
    if vocab_catalog.active(account_id, subject):
        votes: Counter = Counter()
        for w in vocab_catalog.catalog_words(account_id, subject):
            for m in w["memberships"]:
                if m["nodes"] and any(m["page"] in p.get("pages", []) and serves(m["book"], p.get("label") or "")
                                      for p in places):
                    votes[m["nodes"][0]] += 1
        if not votes:
            return None
        key = votes.most_common(1)[0][0]
        label = next((u.get("label") or u["unit"] for u in vocab_catalog.units(account_id, subject) if u["unit"] == key), key)
        return key, label
    from .lernstand import vocab_unit_for
    raw = vocab_unit_for(account_id, subject, places)
    if not raw:
        return None
    for u in vocab.units(account_id, subject):
        if raw == u["unit"] or raw in vocab.unit_family(account_id, subject, u["unit"]):
            return u["unit"], u.get("label") or u["unit"]
    return raw, raw


@memo
def _unit_words(account_id: int, subject: str, unit: str) -> list[int]:
    from . import vocab
    return vocab.unit_word_ids(account_id, subject, unit)


def _states(account_id: int, ids: list[int], day: date) -> dict[int, dict]:
    from . import vocab
    with closing(webapp_conn()) as c:
        return vocab.word_states(c, account_id, ids, before=day.isoformat())


def _is_due(state: dict, day: date) -> bool:
    """Ein sicheres Wort, dessen Termin erreicht ist (Wiederholung, D212)."""
    s1 = state["s1"]
    return s1["stage"] in SECURE and bool(s1.get("due")) and s1["due"] <= day.isoformat()


def practiced(account_id: int, day: date, word_ids: list[int] | None = None) -> set[int]:
    """Verschiedene Wörter, die das Kind an diesem Tag geübt hat (richtig oder
    falsch, Rückfragen nicht). Eltern zählen nur als „Kind am Elterngerät“; das
    hält die Belohnung mit fest (reward_events, D175).

    „Weiß ich nicht“ im Trainer (falsch ohne Antwort) zählt nicht als geübt:
    Wer das Wort danach noch einmal beantwortet, hat es geübt, auch falsch. Ein
    leeres Feld im Papiertest ist dagegen eine geschriebene Antwort."""
    with closing(webapp_conn()) as c:
        rows = c.execute(
            "SELECT a.word_id,a.user_id,u.role FROM vocab_attempts a LEFT JOIN users u ON u.id=a.user_id "
            "WHERE a.account_id=? AND substr(a.created_at,1,10)=? AND a.result!='unclear' "
            "AND NOT (a.result='incorrect' AND TRIM(COALESCE(a.answer,''))='' AND COALESCE(a.source,'')!='paper') "
            "AND COALESCE((SELECT excluded FROM vocab_attempt_reviews r WHERE r.attempt_id=a.id ORDER BY r.id DESC LIMIT 1),0)=0",
            (account_id, day.isoformat())).fetchall()
        noted = {r[0].split(":", 1)[0] for r in c.execute(
            "SELECT ref FROM reward_events WHERE account_id=? AND kind='vocab' AND day=?", (account_id, day.isoformat()))}
    found = {r["word_id"] for r in rows if r["user_id"] is None or r["role"] == "child" or str(r["word_id"]) in noted}
    return found if word_ids is None else found & set(word_ids)


def _href(subject: str, unit: str) -> str:
    from urllib.parse import quote
    return f"#/vokabeln/{quote(subject, safe='')}?unit={quote(unit, safe='')}"


# ---------------------------------------------------------------- Zielkurve

def target_for(open_words: int, due: int, days_left: int, rate: float | None) -> int:
    """Wörter für heute: offene Wörter gleichmäßig auf die Schultage bis zum
    Test, dazu die fälligen Wiederholungen. Die letzten fünf Schultage legen bis
    zu 40 % zu, eine Trefferquote unter 80 % ebenso viel. Grenzen 10 und 40."""
    days_left = max(1, days_left)
    base = math.ceil(open_words / days_left) + due
    close = 1 + 0.1 * max(0, 5 - days_left)
    weak = 1 + max(0.0, 0.8 - rate) if rate is not None else 1.0
    return max(MIN_WORDS, min(MAX_WORDS, round(base * close * weak)))


def _when(exam: date, day: date, days_left: int) -> str:
    gap = (exam - day).days
    if gap == 1:
        return "morgen"
    if gap <= 6:
        return f"am {WEEKDAYS[exam.weekday()]}"
    return f"in {days_left} Schultagen"


def _rate(states: dict[int, dict]) -> float | None:
    right = sum(s["s1"].get("correct_count", 0) for s in states.values())
    wrong = sum(s["s1"].get("wrong_count", 0) for s in states.values())
    return right / (right + wrong) if right + wrong >= RATE_MIN_ANSWERS else None


def _test_entry(account_id: int, day: date, exam: dict, subject: str, unit: str, label: str) -> dict | None:
    ids = _unit_words(account_id, subject, unit)
    if not ids:
        return None
    states = _states(account_id, ids, day)
    open_words = sum(1 for s in states.values() if s["s1"]["stage"] not in SECURE)
    due = sum(1 for s in states.values() if _is_due(s, day))
    left = [d for d in school_days(account_id, day, exam["date"] - timedelta(days=1))]
    free_day = day not in left
    n = len(left) + (1 if free_day else 0)
    if free_day and open_words <= MAX_WORDS * len(left):
        return None  # Wochenende und Ferien bleiben frei, solange die Zeit reicht (D179)
    if not open_words and not due and n > 3:
        return None  # alles sicher; kurz vor dem Test wird trotzdem wiederholt
    rate = _rate(states)
    target = min(target_for(open_words, due, n, rate), len(ids))
    done_words = practiced(account_id, day, ids)
    what = "Der Vokabeltest" if exam["only_vocab"] else "Die Arbeit"
    why = f"{what} ist {_when(exam['date'], day, n)}. "
    why += f"{open_words} {'Wort sitzt' if open_words == 1 else 'Wörter sitzen'} noch nicht" if open_words else "Alle Wörter sitzen"
    why += f", dazu {due} zum Wiederholen." if due else "."
    if rate is not None and rate < 0.65:
        why += " Heute etwas mehr, damit die Wörter sicherer werden."
    if free_day:
        why += " Eigentlich ist heute frei, aber sonst reicht die Zeit bis zum Test nicht."
    return {"subject": subject, "unit": unit, "unit_label": label, "target": target, "done": len(done_words) >= target,
            "practiced": len(done_words), "href": _href(subject, unit), "exam_key": exam["exam_key"],
            "exam_date": exam["date"].isoformat(), "days_left": n, "open": open_words, "due": due,
            "rate": round(rate, 2) if rate is not None else None, "why": why}


def _lesson_units(account_id: int, day: date) -> set[tuple[str, str, int]]:
    """Einheiten, die das Stundenthema der letzten zwei Wochen nennt: (Sprache,
    Art, Nummer), etwa („Spanisch“, „uni“, 3) für „Unidad 3 Texto A“."""
    from . import vocab
    from .db import history_conn
    try:
        with closing(history_conn()) as c:
            rows = c.execute(
                "SELECT subject_name, COALESCE(NULLIF(lstext_manual_override,''), lstext) FROM lessons "
                "WHERE account_id=? AND date>=? AND date<? AND COALESCE(NULLIF(lstext_manual_override,''), lstext, '')!=''",
                (account_id, (day - timedelta(days=LESSON_DAYS)).isoformat(), day.isoformat())).fetchall()
    except Exception:
        LOG.warning("Stundenthemen für das Vokabelpensum nicht lesbar", exc_info=True)
        return set()
    out = set()
    for subject, text in rows:
        lang = vocab.language_of(subject or "")
        for m in HOMEWORK_UNIT.finditer(text or ""):
            if lang:
                out.add((lang["name"], m.group(1).casefold()[:3], int(m.group(2))))
    return out


def _base_entry(account_id: int, day: date) -> dict | None:
    """Ohne anstehenden Test (D212): aus der aktiven Einheit, in der am meisten
    dran ist, bis zu 15 Wörter. Dran sind Wörter, die zuletzt falsch waren,
    sichere Wörter mit erreichtem Termin und in einer aktiven Einheit die noch
    nicht geübten. Der Stand vor dem Tag entscheidet (D181)."""
    from . import vocab
    since = (day - timedelta(days=HORIZON)).isoformat()
    with closing(webapp_conn()) as c:
        spellings = c.execute("SELECT subject, COUNT(*) FROM vocab_words WHERE account_id=? AND hidden=0 GROUP BY subject",
                              (account_id,)).fetchall()
        recent = c.execute("SELECT DISTINCT word_id, unit_scope FROM vocab_attempts WHERE account_id=? AND created_at>=? AND created_at<?",
                           (account_id, since, day.isoformat())).fetchall()
    # Geübt heißt: in dieser Einheit geübt. Seit 1.13.4 steht die gewählte
    # Einheit an jeder Antwort; ein Wort, das auch in anderen Einheiten
    # vorkommt, macht diese nicht aktiv. Ältere Antworten ohne Angabe zählen,
    # wenn mindestens drei Wörter der Einheit geübt wurden.
    scoped = {r[1] for r in recent if r[1]}
    unscoped = {r[0] for r in recent if not r[1]}
    # Ein Fach, gleich wie es geschrieben ist (1.37.2); Name: die häufigste Schreibweise.
    subjects: dict[str, tuple[str, int]] = {}
    for subject, n in spellings:
        key = subject.casefold()
        if key not in subjects or (n, subject) > (subjects[key][1], subjects[key][0]):
            subjects[key] = (subject, n)
    named = _lesson_units(account_id, day)
    best = None
    for subject, _ in subjects.values():
        lang = vocab.language_of(subject)
        if not lang:
            continue
        for u in vocab.units(account_id, subject):
            if not u.get("words"):
                continue
            ids = _unit_words(account_id, subject, u["unit"])
            number = _unit_number(u.get("label") or u["unit"])
            practiced_here = u["unit"] in scoped or len(unscoped & set(ids)) >= UNSCOPED_MIN
            active = practiced_here or bool(number and (lang["name"], *number) in named)
            if not active:
                continue
            states = _states(account_id, ids, day)
            relearn = [w for w, st in states.items() if st["s1"].get("relearn")]
            due = [w for w, st in states.items() if _is_due(st, day)]
            new = [w for w, st in states.items() if st["s1"]["stage"] == "neu"]
            if not (relearn or due or new):
                continue
            rank = (len(relearn) + len(due), len(new))
            if best is None or rank > best[0]:
                best = (rank, subject, u["unit"], u.get("label") or u["unit"], ids, len(relearn), len(due), len(new))
    if not best:
        return None
    _, subject, unit, label, ids, relearn, due, new = best
    need = relearn + due + new
    target = min(BASE_MAX, need)
    done_words = practiced(account_id, day, ids)
    parts = []
    if relearn:
        parts.append(f"{relearn} {'Wort wackelt' if relearn == 1 else 'Wörter wackeln'}.")
    if due:
        parts.append(f"{due} {'ist' if due == 1 else 'sind'} zum Wiederholen fällig.")
    if new:
        parts.append(f"{new} {'ist' if new == 1 else 'sind'} noch neu.")
    why = " ".join(parts) + (" Die Wörter, die zuerst kommen, brauchen es am meisten." if need > target
                             else " Kurz üben, dann bleibt die Einheit sicher.")
    return {"subject": subject, "unit": unit, "unit_label": label, "target": target, "done": len(done_words) >= target,
            "practiced": len(done_words), "href": _href(subject, unit), "exam_key": None, "exam_date": None,
            "days_left": None, "open": new + relearn, "due": due, "relearn": relearn, "new": new, "rate": None, "why": why}


# ------------------------------------------------------------------ Schnittstelle

@memo
def daily(account_id: int, day: date) -> list[dict]:
    """Das Vokabelpensum eines Tages, der nächste Test zuerst, höchstens zwei Einträge.

    Je Eintrag: subject, unit, target, done, href, exam_key (None beim
    Grundpensum) und why; dazu unit_label, practiced und die Rechengrößen."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    try:
        homework = [e for e in _homework_tests(account_id, day) if e["unit"]]
    except Exception:
        LOG.warning("Vokabeltests aus Hausaufgaben nicht lesbar", exc_info=True)
        homework = []
    # Arbeiten mit Vokabelthema und angekündigte Tests aus Hausaufgaben, der nächste zuerst.
    for exam in sorted(_upcoming(account_id, day) + homework, key=lambda e: e["date"]):
        if "topics" not in exam:
            subject, (unit, label) = exam["subject"], exam["unit"]
            if (subject.casefold(), unit) in seen:
                continue
            try:
                entry = _test_entry(account_id, day, exam, subject, unit, label)
            except Exception:
                LOG.warning("Vokabelpensum für %s nicht berechenbar", label, exc_info=True)
                continue
            if entry:
                seen.add((subject.casefold(), unit))
                out.append(entry)
            if len(out) >= MAX_ENTRIES:
                return out
            continue
        for topic in exam["topics"]:
            try:
                found = trainer_unit(account_id, topic["subject"], json.loads(topic["places_json"] or "[]"))
                if not found or (topic["subject"].casefold(), found[0]) in seen:
                    continue
                entry = _test_entry(account_id, day, exam, topic["subject"], *found)
            except Exception:
                LOG.warning("Vokabelpensum für %s nicht berechenbar", topic["title"], exc_info=True)
                continue
            if entry:
                seen.add((topic["subject"].casefold(), found[0]))
                out.append(entry)
            if len(out) >= MAX_ENTRIES:
                return out
    if out or day not in school_days(account_id, day, day):
        return out
    try:
        base = _base_entry(account_id, day)
    except Exception:
        LOG.warning("Grundpensum Vokabeln nicht berechenbar", exc_info=True)
        base = None
    return [base] if base else []
