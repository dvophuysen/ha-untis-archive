"""Lernen als Kompass (D186): alles für die Lernseite des Kindes in einem Aufruf.

Die Seite beantwortet von oben nach unten: Wo stehe ich? Was ist heute Pflicht,
und warum? Was ist meine Stärke, was meine Baustelle? Was kann ich freiwillig
tun? Wie hat sich mein Lernen entwickelt? Dazu die offenen Einheiten, frühere
Arbeiten und das Archiv (D182).

Kein Modellaufruf. Die Pflicht kommt unverändert aus dem Tagesplan (D180), der
Stand aus dem Raster der Arbeiten (D178) und den Stufen (D59). Der
Arbeitenkalender wird wie auf „Heute“ gelesen und gemerkt, aber mit einer Frist;
ohne Kalender reichen die gemerkten Termine. Gemessen wird in Ergebnissen, nie in
Minuten.
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import closing
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlencode

from . import practice, rewards, study_plan
from .db import webapp_conn
from .subject_names import key as subject_key, label as subject_label

LOG = logging.getLogger("schul_cockpit.learning_compass")

HORIZON = study_plan.HORIZON      # Arbeiten der nächsten sechs Wochen (D188)
PAST_DAYS = 120                   # so weit zurück stehen frühere Arbeiten
MAX_PAST = 6
STRENGTH_DAYS = 28                # Stärken: was in vier Wochen sicher wurde
GAP_DAYS = 14                     # Baustellen: Rückmeldungen der letzten zwei Wochen
HISTORY_WEEKS = 4
MAX_ITEMS = 3                     # je höchstens drei Stärken und Baustellen
MAX_OPEN_SESSIONS = 3
LESSON_DAYS = 42                  # Fächer des Kindes aus dem Unterricht
RECENT_TOPIC_DAYS = 21            # „Neues Thema“: Stunden der letzten drei Wochen
EXAM_TIMEOUT = 4.0
WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
AFB_NAMES = practice.AFB_NAMES
SECURE_STAGES = ("sitzt", "gefestigt")


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _de(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d.day:02d}.{d.month:02d}."


def _short(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}."


# ------------------------------------------------------------------ Eingaben

async def _calendar(account_id: int, day: date) -> dict[str, dict]:
    """Arbeiten aus dem Kalender, mit Frist wie auf der Woche (D184). Die Termine
    werden für den Plan gemerkt, so wie „Heute“ es tut."""
    try:
        from .exams import resolve_exams
        data = await asyncio.wait_for(resolve_exams(account_id, days_ahead=HORIZON), timeout=EXAM_TIMEOUT)
    except Exception:
        LOG.info("Arbeitenkalender für Konto %s nicht rechtzeitig lesbar", account_id, exc_info=True)
        return {}
    found = {}
    for e in data.get("exams", []):
        if not e.get("exam_key") or not e.get("date"):
            continue
        found[e["exam_key"]] = e
        try:
            from . import mentor_opening
            mentor_opening.remember_exam(account_id, e["exam_key"], e["date"])
        except Exception:
            LOG.debug("Termin %s nicht gemerkt", e.get("exam_key"), exc_info=True)
    return found


def _remembered(c, account_id: int, first: date, last: date) -> dict[str, date]:
    try:
        rows = c.execute("SELECT exam_key, exam_date FROM exam_dates WHERE account_id=? "
                         "AND substr(exam_date,1,10) BETWEEN ? AND ?",
                         (account_id, first.isoformat(), last.isoformat())).fetchall()
    except Exception:
        return {}  # die Tabelle entsteht mit dem ersten gemerkten Termin
    return {r[0]: d for r in rows if (d := _day(r[1]))}


def _topics(c, account_id: int, keys: list[str]) -> list[dict]:
    if not keys:
        return []
    marks = ",".join("?" * len(keys))
    return [dict(r) for r in c.execute(
        f"SELECT id, exam_key, subject, title, stage, places_json, position FROM exam_topics "
        f"WHERE account_id=? AND stale=0 AND exam_key IN ({marks}) ORDER BY position, id", (account_id, *keys))]


def _school_days(lessons: list[dict], first: date, last: date) -> list[date]:
    """Schultage wie beim Vokabelpensum: bekannte Tage mit Unterricht, jenseits
    des bekannten Stundenplans Montag bis Freitag."""
    known = {d for l in lessons if rewards._held(l) and (d := _day(l.get("date"))) and first <= d <= last}
    horizon = max((_day(l.get("date")) for l in lessons if _day(l.get("date"))), default=first - timedelta(days=1))
    rest = (first + timedelta(days=i) for i in range(max(0, (last - first).days + 1)))
    return sorted(known | {d for d in rest if d > horizon and d.weekday() < 5})


# ------------------------------------------------------------------ Raster

def dot_state(row: dict) -> str:
    """Ein Punkt je Thema in den Farben der Stufen (D176)."""
    cells = row["cells"]
    if row["ready"]:
        return "gefestigt" if cells["2"]["state"] == "bestaetigt" else "sitzt"
    if any(cells[k]["state"] == "unsicher" for k in ("1", "2")):
        return "wackelt"
    if any(c["tasks"] or c.get("implied") for c in cells.values()):
        return "angefangen"
    return "neu"


def _raster_view(r: dict) -> list[dict]:
    return [{"id": t["id"], "title": t["title"], "state": dot_state(t), "ready": t["ready"],
             "cells": {k: v["state"] for k, v in t["cells"].items()}} for t in r["topics"]]


def path_of(r: dict, recent_probe: bool = False) -> tuple[str, list[dict]]:
    """Der Weg zur Arbeit: Einstiegstest, Lücken schließen, Probearbeit, Arbeit.
    Dieselben Phasen wie der Tagesplan (D180)."""
    rows = r["topics"]
    if not rows:
        return "", []
    if all(c["state"] == "offen" for t in rows for c in t["cells"].values()):
        now = "einstieg"
    elif r["ready"] < r["total"]:
        now = "luecken"
    elif recent_probe or all(t["cells"]["2"]["state"] == "bestaetigt" for t in rows):
        now = "arbeit"
    else:
        now = "probe"
    order = ["einstieg", "luecken", "probe", "arbeit"]
    texts = {
        "einstieg": ("Einstiegstest", "Zeigt, wo du bei jedem Thema stehst."),
        "luecken": ("Lücken schließen", f"Jedes Thema sicher im Wiedergeben und Anwenden. {r['ready']} von {r['total']} geschafft."),
        "probe": ("Probearbeit", "Alle Themen zusammen, wie in der echten Arbeit."),
        "arbeit": ("Arbeit", "Gut vorbereitet hingehen."),
    }
    at = order.index(now)
    return now, [{"key": k, "label": texts[k][0], "text": texts[k][1],
                  "state": "done" if i < at else "now" if i == at else "todo"} for i, k in enumerate(order)]


def plan_verdict(p: dict) -> tuple[str, str]:
    """Die Einschätzung aus demselben Bedarf wie der Tagesplan (D188): was laut
    Raster noch fehlt, gegen die Lerntage bis zum Puffer vor der Arbeit."""
    need, days = p["need"], p["days"]
    steps = f"noch etwa {need} {'Schritt' if need == 1 else 'Schritte'} in {days} {'Schultag' if days == 1 else 'Schultagen'}"
    if not need:
        return "auf_kurs", "Auf Kurs: Alles sitzt. Jetzt nur noch wiederholen."
    if p["weekend"] or p["behind"]:
        return "eng", f"Eng: {steps}. Das Wochenende ist nur Notpuffer für die Freitagsliste."
    if need > days:
        return "knapp", f"Knapp: {steps}. Jeden Tag dranbleiben."
    return "auf_kurs", f"Auf Kurs: {steps}."


def verdict(ready: int, total: int, left: int) -> tuple[str, str]:
    """Ein Satz Einschätzung, ohne Zeitschätzung. Eng wie im Tagesplan (D180):
    weniger Schultage als offene Themen oder nur noch zwei Tage; knapp, wenn für
    ein offenes Thema weniger als zwei Schultage bleiben."""
    if not total:
        return "", ""
    open_topics = total - ready
    if not open_topics:
        return "auf_kurs", "Auf Kurs: Alle Themen sitzen. Eine Probearbeit zeigt, ob es auch unter Zeit klappt."
    if left <= open_topics or left <= 2:
        return "eng", "Eng: Jeder Schritt zählt jetzt, auch am Wochenende."
    if left < 2 * open_topics:
        return "knapp", "Knapp: Bleib jeden Schultag dran, dann reicht es."
    return "auf_kurs", "Auf Kurs: Für die offenen Themen bleiben genug Schultage."


# ------------------------------------------------------------------ Verlauf

def sure_moments(answers: list[dict]) -> tuple[dict[str, str], str | None]:
    """Wann jede Zelle zum ersten Mal sicher wurde (ohne „mit gezeigt“) und
    wann das Thema zum ersten Mal vorbereitet war (I und II sicher)."""
    cells: dict[str, str] = {}
    ready_at = None
    for i, a in enumerate(answers):
        row = practice.row_of(answers[: i + 1])
        for k, c in row["cells"].items():
            if k not in cells and practice.is_sure(c) and not c.get("implied"):
                cells[k] = a["created_at"]
        if ready_at is None and row["ready"]:
            ready_at = a["created_at"]
    return cells, ready_at


def _progress(c, account_id: int, day: date) -> dict:
    """Themen und Zellen, die in den letzten Wochen sicher geworden sind."""
    since = day - timedelta(days=max(STRENGTH_DAYS, HISTORY_WEEKS * 7))
    fresh = [r[0] for r in c.execute("SELECT DISTINCT topic_id FROM topic_answers WHERE account_id=? AND substr(created_at,1,10)>=?",
                                     (account_id, since.isoformat()))]
    events = [dict(r) for r in c.execute(
        "SELECT e.topic_id, e.stage_before, e.stage_after, e.created_at, t.subject, t.title, t.stage, t.exam_key "
        "FROM topic_events e JOIN exam_topics t ON t.id=e.topic_id "
        "WHERE e.account_id=? AND substr(e.created_at,1,10)>=? ORDER BY e.created_at, e.id", (account_id, since.isoformat()))]
    ids = sorted(set(fresh) | {e["topic_id"] for e in events})
    info: dict[int, dict] = {}
    answers: dict[int, list[dict]] = {i: [] for i in ids}
    if ids:
        marks = ",".join("?" * len(ids))
        from .lernstand import is_vocab_topic
        for r in c.execute(f"SELECT id, subject, title, stage, exam_key, places_json FROM exam_topics WHERE account_id=? AND id IN ({marks})",
                           (account_id, *ids)):
            info[r["id"]] = {**dict(r), "vocab": is_vocab_topic(dict(r))}
        for r in c.execute(f"SELECT * FROM topic_answers WHERE account_id=? AND topic_id IN ({marks}) ORDER BY created_at, id",
                           (account_id, *ids)):
            answers[r["topic_id"]].append(dict(r))
    # Erstmals sicher vor dem Zeitraum: gilt nicht als neu sicher geworden.
    earlier = {r[0]: r[1] for r in c.execute(
        "SELECT topic_id, MIN(created_at) FROM topic_events WHERE account_id=? AND stage_after IN ('sitzt','gefestigt') GROUP BY topic_id",
        (account_id,))}
    topics, cells = [], []
    for tid in ids:
        t = info.get(tid)
        if not t:
            continue
        moments, ready_at = sure_moments(answers[tid]) if not t["vocab"] else ({}, None)
        stage_at = earlier.get(tid)
        first = min(filter(None, [ready_at, stage_at]), default=None)
        if first and _day(first) and _day(first) >= since:
            topics.append({"topic_id": tid, "subject": subject_label(t["subject"]), "title": t["title"],
                           "stage": t["stage"], "at": first[:10], "exam_key": t["exam_key"]})
        for k, when in moments.items():
            if _day(when) and _day(when) >= since:
                cells.append({"topic_id": tid, "subject": subject_label(t["subject"]), "title": t["title"],
                              "afb": int(k), "at": when[:10], "exam_key": t["exam_key"]})
    return {"topics": topics, "cells": cells}


def history(progress: dict, day: date) -> dict:
    """Vier Wochen, je Woche die Themen, die sicher geworden sind (Montag bis Sonntag)."""
    monday = day - timedelta(days=day.weekday())
    names = ["vor 3 Wochen", "vor 2 Wochen", "letzte Woche", "diese Woche"]
    weeks = []
    for i in range(HISTORY_WEEKS):
        start = monday - timedelta(days=7 * (HISTORY_WEEKS - 1 - i))
        end = start + timedelta(days=6)
        inside = lambda x: start <= date.fromisoformat(x["at"]) <= end  # noqa: E731
        weeks.append({"start": start.isoformat(), "label": names[i],
                      "topics": sum(1 for t in progress["topics"] if inside(t)),
                      "cells": sum(1 for c in progress["cells"] if inside(c))})
    first = date.fromisoformat(weeks[0]["start"])
    topics = [t for t in progress["topics"] if date.fromisoformat(t["at"]) >= first]
    cells = [c for c in progress["cells"] if date.fromisoformat(c["at"]) >= first]
    if topics:
        n = len(topics)
        by: dict[str, int] = {}
        for t in topics:
            by[t["subject"]] = by.get(t["subject"], 0) + 1
        top, most = max(by.items(), key=lambda kv: (kv[1], kv[0]))
        sentence = f"{n} {'Thema ist' if n == 1 else 'Themen sind'} sicher geworden"
        sentence += f", {most} davon in {top}." if len(by) > 1 else f", alle in {top}." if n > 1 else f", in {top}."
    elif cells:
        n = len(cells)
        sentence = f"Noch kein Thema ganz sicher, aber {n} {'Bereich ist' if n == 1 else 'Bereiche sind'} sicher geworden."
    else:
        sentence = "Noch nichts sicher geworden. Jede gelöste Aufgabe zählt, der erste Balken kommt bald."
    return {"weeks": weeks, "topics": len(topics), "cells": len(cells), "sentence": sentence,
            "max": max([w["topics"] for w in weeks] + [1])}


def _skills(c, account_id: int, since: date) -> list[dict]:
    """Was der Lernbegleiter mit Abstand selbstständig gesehen hat (früher „Was
    schon klappt“): zweimal ohne Hilfe richtig, mindestens sieben Tage auseinander."""
    try:
        rows = [dict(r) for r in c.execute(
            "SELECT s.id, s.subject, s.title, MIN(e.created_at) first, MAX(e.created_at) last, "
            "COUNT(DISTINCT e.variant_hash) variants FROM mentor_skills s JOIN mentor_evidence e "
            "ON e.skill_id=s.id AND e.account_id=s.account_id AND e.invalidated=0 AND e.result='correct' AND e.help_used=0 "
            "AND NOT EXISTS (SELECT 1 FROM mentor_sessions ms WHERE ms.id=e.session_id AND ms.is_test=1) "
            "WHERE s.account_id=? GROUP BY s.id", (account_id,))]
    except Exception:
        return []
    out = []
    for r in rows:
        first, last = _day(r["first"]), _day(r["last"])
        if r["variants"] >= 2 and first and last and (last - first).days >= 7 and last >= since:
            out.append({"kind": "skill", "subject": subject_label(r["subject"]), "title": r["title"],
                        "text": "Mit Abstand selbstständig gezeigt", "at": last.isoformat()})
    return sorted(out, key=lambda x: x["at"], reverse=True)


# ------------------------------------------------------------------ Stärken, Baustellen

def strengths(progress: dict, skills: list[dict], day: date) -> list[dict]:
    since = day - timedelta(days=STRENGTH_DAYS)
    out, seen = [], set()
    for t in sorted(progress["topics"], key=lambda x: x["at"], reverse=True):
        if date.fromisoformat(t["at"]) < since or t["topic_id"] in seen:
            continue
        seen.add(t["topic_id"])
        text = "gefestigt" if t["stage"] == "gefestigt" else f"sicher seit {_short(date.fromisoformat(t['at']))}"
        out.append({"kind": "topic", "topic_id": t["topic_id"], "subject": t["subject"], "title": t["title"], "text": text})
    for cl in sorted(progress["cells"], key=lambda x: (x["at"], x["afb"]), reverse=True):
        if date.fromisoformat(cl["at"]) < since or cl["topic_id"] in seen:
            continue
        seen.add(cl["topic_id"])
        out.append({"kind": "cell", "topic_id": cl["topic_id"], "subject": cl["subject"], "title": cl["title"],
                    "text": f"{AFB_NAMES[cl['afb']]} sicher seit {_short(date.fromisoformat(cl['at']))}"})
    for s in skills:
        out.append({"kind": "skill", "topic_id": None, "subject": s["subject"], "title": s["title"], "text": s["text"]})
    return out[:MAX_ITEMS]


def _topic_href(topic_id: int) -> str:
    return f"#/learning?topic_id={topic_id}"


def _lesson_href(l: dict) -> str:
    return "#/learning?" + urlencode({"lesson_id": str(l["id"]), "subject": l.get("subject_name") or "",
                                      "title": l.get("lstext") or ""})


def gaps(upcoming: list[dict], lessons: list[dict], ratings: dict[int, int], day: date) -> list[dict]:
    """Baustellen: Themen, die wackeln, und unsichere Zellen der anstehenden
    Arbeiten (die nächste zuerst), dann Fächer mit wiederholt 😟 oder 😐 in den
    letzten zwei Wochen."""
    out, seen = [], set()
    for e in upcoming:
        for t in e.get("raster", []):
            if t["id"] in seen:
                continue
            why = ""
            if t.get("stage") == "wackelt":
                why = "Das Thema wackelt noch."
            else:
                weak = [k for k in ("1", "2") if t["cells"].get(k) == "unsicher"]
                if weak:
                    why = f"{AFB_NAMES[int(weak[0])]} ist noch unsicher."
            if why:
                seen.add(t["id"])
                out.append({"kind": "topic", "topic_id": t["id"], "subject": e["subject"], "title": t["title"],
                            "why": f"{why} Arbeit am {_short(date.fromisoformat(e['date']))}", "href": _topic_href(t["id"])})
    since = day - timedelta(days=GAP_DAYS)
    by_subject: dict[str, list[dict]] = {}
    for l in lessons:
        d = _day(l.get("date"))
        if d and since <= d <= day and ratings.get(l["id"]) in (1, 2) and l.get("subject_name"):
            by_subject.setdefault(subject_key(l["subject_name"]), []).append(l)
    for group in sorted(by_subject.values(), key=lambda g: (-len(g), g[-1]["date"])):
        if len(group) < 2:
            continue
        last = max(group, key=lambda x: (x["date"], x.get("start_time") or 0, x["id"]))
        name = subject_label(last["subject_name"])
        worried = sum(1 for l in group if ratings.get(l["id"]) == 1)
        why = (f"{len(group)} Stunden in zwei Wochen nicht ganz klar" + (f", {worried}× 😟." if worried else "."))
        out.append({"kind": "lessons", "lesson_id": last["id"], "subject": name,
                    "title": last.get("lstext") or f"Stunde vom {_short(date.fromisoformat(last['date']))}",
                    "why": why, "href": _lesson_href(last)})
    return out[:MAX_ITEMS]


# ------------------------------------------------------------------ Extra

def extra(lessons: list[dict], upcoming: list[dict], day: date) -> list[dict]:
    """Fächer des Kindes aus dem Unterricht der letzten Wochen, je Fach die
    Stunden der letzten drei Wochen als mögliche neue Themen."""
    from .vocab import language_of
    exams = {}
    for e in upcoming:
        if e["total"]:
            exams.setdefault(subject_key(e["subject"]), e["exam_key"])
    subjects: dict[str, dict] = {}
    since = day - timedelta(days=RECENT_TOPIC_DAYS)
    for l in sorted(lessons, key=lambda x: (x.get("date") or "", x.get("start_time") or 0), reverse=True):
        name = (l.get("subject_name") or "").strip()
        d = _day(l.get("date"))
        if not name or not d or d > day:
            continue
        k = subject_key(subject_label(name))
        entry = subjects.setdefault(k, {"name": name, "label": subject_label(name), "language": bool(language_of(name)),
                                        "exam_key": exams.get(k), "vocab_href": f"#/vokabeln/{quote(name, safe='')}",
                                        "recent": []})
        text = (l.get("lstext") or "").strip()
        if (d >= since and rewards._held(l) and text and len(entry["recent"]) < 4
                and all(r["title"].casefold() != text.casefold() for r in entry["recent"])):
            entry["recent"].append({"lesson_id": l["id"], "title": text[:120], "date": d.isoformat(),
                                    "href": _lesson_href(l)})
    return sorted(subjects.values(), key=lambda s: s["label"])


# ------------------------------------------------------------------ Vokabeln

def _vocab_state(account_id: int, exam: dict, topics: list[dict], pensum: list[dict]) -> dict | None:
    """Vokabelthemen einer Arbeit: Pensum von heute, falls es eins gibt, sonst
    der Hinweis, dass die Lektion im Bestand fehlt."""
    from .lernstand import is_vocab_topic
    vocab = [t for t in topics if is_vocab_topic(t)]
    if not vocab:
        return None
    mine = [p for p in pensum if p.get("exam_key") == exam["exam_key"]]
    if mine:
        p = mine[0]
        return {"unit": p.get("unit_label") or p.get("unit"), "target": p.get("target"), "practiced": p.get("practiced"),
                "done": bool(p.get("done")), "href": p.get("href"), "missing": False}
    try:
        from . import vocab_pensum
        found = [vocab_pensum.trainer_unit(account_id, t["subject"], json.loads(t["places_json"] or "[]")) for t in vocab]
    except Exception:
        LOG.debug("Lektion zu %s nicht bestimmbar", exam["exam_key"], exc_info=True)
        found = [None]
    if any(f is None for f in found):
        return {"missing": True, "unit": vocab[0]["title"], "href": None}
    return {"missing": False, "unit": found[0][1], "href": f"#/vokabeln/{quote(vocab[0]['subject'], safe='')}?unit={quote(found[0][0], safe='')}",
            "target": None, "practiced": None, "done": False}


# ------------------------------------------------------------------ Zusammenbauen

def _recent_probe(c, account_id: int, ids: list[int], day: date) -> bool:
    try:
        return study_plan._recent_probe(c, account_id, ids, day)
    except Exception:
        return False


async def build(account_id: int, user, now: datetime | None = None) -> dict:
    now = now or rewards.now_local()
    day = now.date()
    calendar = await _calendar(account_id, day)
    lessons = rewards._lessons(account_id, day - timedelta(days=LESSON_DAYS), day + timedelta(days=HORIZON))
    plan = study_plan.today(account_id, user, now)
    try:
        from . import vocab_pensum
        pensum = list(vocab_pensum.daily(account_id, day) or [])
    except Exception:
        LOG.debug("Vokabelpensum nicht lesbar", exc_info=True)
        pensum = []
    school = _school_days(lessons, day, day + timedelta(days=HORIZON))

    with closing(webapp_conn()) as c:
        future = _remembered(c, account_id, day, day + timedelta(days=HORIZON))
        past = _remembered(c, account_id, day - timedelta(days=PAST_DAYS), day - timedelta(days=1))
        for k, e in calendar.items():
            d = _day(e.get("date"))
            if d and day <= d <= day + timedelta(days=HORIZON):
                future.setdefault(k, d)
        topics = _topics(c, account_id, list(future) + list(past))
        stage_of = {t["id"]: t["stage"] for t in topics}
        upcoming = []
        try:
            plans = {p["exam_key"]: p for p in study_plan.plans(account_id, day)}
        except Exception:
            plans = {}
        for k, d in sorted(future.items(), key=lambda kv: (kv[1], kv[0])):
            mine = [t for t in topics if t["exam_key"] == k]
            cal = calendar.get(k) or {}
            subject = subject_label((mine[0]["subject"] if mine else None) or cal.get("subject_name") or "")
            if not subject:
                continue
            r = practice.raster(account_id, k)
            raster = [{**row, "stage": stage_of.get(row["id"])} for row in _raster_view(r)]
            left = sum(1 for s in school if day <= s < d)
            now_key, path = path_of(r, _recent_probe(c, account_id, [t["id"] for t in r["topics"]], day))
            level, sentence = plan_verdict(plans[k]) if k in plans else verdict(r["ready"], r["total"], left)
            vocab = _vocab_state(account_id, {"exam_key": k}, mine, pensum)
            title = (cal.get("title") or "").strip()
            kind = "vokabeltest" if vocab and not r["total"] else "arbeit"
            upcoming.append({"exam_key": k, "subject": subject, "title": title, "date": d.isoformat(), "day_label": _de(d),
                             "days": (d - day).days, "school_days_left": left, "kind": kind,
                             "ready": r["ready"], "total": r["total"], "raster": raster,
                             "afb_names": {str(a): n for a, n in AFB_NAMES.items()},
                             "stage": now_key, "path": path, "verdict": level, "verdict_text": sentence,
                             "vocab": vocab, "topics_missing": not mine})
        earlier = []
        for k, d in sorted(past.items(), key=lambda kv: (kv[1], kv[0]), reverse=True):
            mine = [t for t in topics if t["exam_key"] == k]
            if not mine:
                continue
            r = practice.raster(account_id, k, until=d.isoformat())
            if not r["total"]:
                continue
            earlier.append({"exam_key": k, "subject": subject_label(mine[0]["subject"]), "date": d.isoformat(),
                            "day_label": _de(d), "ready": r["ready"], "total": r["total"], "raster": _raster_view(r)})
            if len(earlier) >= MAX_PAST:
                break

        progress = _progress(c, account_id, day)
        skills = _skills(c, account_id, day - timedelta(days=STRENGTH_DAYS))
        ids = [l["id"] for l in lessons if (d := _day(l.get("date"))) and day - timedelta(days=GAP_DAYS) <= d <= day]
        ratings = {}
        if ids:
            marks = ",".join("?" * len(ids))
            ratings = {r[0]: r[1] for r in c.execute(
                f"SELECT lesson_id, rating FROM lesson_checkins WHERE account_id=? AND lesson_id IN ({marks})", (account_id, *ids))}
        from .routers.mentor import session_lists
        sessions, archived = session_lists(c, account_id, day)
        profile = c.execute("SELECT ai_enabled FROM learning_profiles WHERE account_id=? AND active=1", (account_id,)).fetchone()

    next_exam = next((e for e in upcoming if e["total"]), None) or next((e for e in upcoming if e["vocab"]), None)
    calm = None
    if not next_exam:
        calm = {"text": "Keine Arbeit in Sicht. Zeit, Sicheres sicher zu halten.",
                "vocab": [{"subject": p.get("subject"), "unit": p.get("unit_label") or p.get("unit"), "target": p.get("target"),
                           "practiced": p.get("practiced"), "done": bool(p.get("done")), "href": p.get("href"), "why": p.get("why")}
                          for p in pensum]}
    open_sessions = [s for s in sessions if s["status"] == "active" and not s["task_done"]][:MAX_OPEN_SESSIONS]
    from .view_mode import acts_as_parent, current
    try:
        from .routers.learning import access
        access(user, account_id, write=True)
        writable = current.get() != "mirror"
    except Exception:
        writable = False
    from . import ai_gateway as ai
    return {
        "day": day.isoformat(),
        "can_write": writable,
        "can_manage": acts_as_parent(user),
        "ai_enabled": bool(profile and profile[0]),
        "speech": bool(ai.transcribe_url()),
        "next_exam": next_exam,
        "calm": calm,
        "plan": plan,
        "plan_explain": [
            "Jeden Morgen entsteht der Plan neu: aus dem, was je Thema noch fehlt, und den Lerntagen bis zur Arbeit.",
            "Der Stoff soll zwei Schultage vor der Arbeit durch sein. So bleibt Luft für spontane Tests und viele Hausaufgaben.",
            "Am Wochenende kommt nichts Neues dazu. Ist die Freitagsliste lang, darf sie bis Sonntagabend fertig werden. Alle nahen Prüfungen kommen im Wechsel dran.",
        ],
        "exams": upcoming,
        "strengths": strengths(progress, skills, day),
        "gaps": gaps(upcoming, lessons, ratings, day),
        "extra": extra(lessons, upcoming, day),
        "history": history(progress, day),
        "sessions": open_sessions,
        "past_exams": earlier,
        "archived_sessions": archived,
    }
