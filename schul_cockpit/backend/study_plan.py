"""Der Lern-Pflichtplan des Tages (D180).

Die App rechnet jeden Tag neu, was heute zum Lernen Pflicht ist, rückwärts von
den Arbeiten der nächsten vier Wochen und gemessen am Raster Thema ×
Anforderungsbereich (D178). Eltern müssen nie eingreifen.

Der Plan wird beim ersten Aufruf des Tages durch das Kind berechnet und für
diesen Tag eingefroren; sonst würde ein erledigter Schritt sofort durch den
nächsten ersetzt und „Lernen" wäre nie fertig. Ob ein Schritt erledigt ist,
wird dagegen live geprüft. Freiwilliges ersetzt nie einen Pflichtschritt,
zählt aber auch nicht dagegen.

Je Arbeit ein Schritt:
  alles offen                 Einstiegstest
  ein Thema nicht sicher      Lücken schließen: Kurztest zum schwächsten
                              Thema, im Wechsel mit einer Einheit beim
                              Lernbegleiter (zuletzt Gespräch → Kurztest)
  alles sicher                Probearbeit, wenn keine in den letzten 3 Tagen
  letzter Schultag davor      Mix als kurzer Abschluss, wenn nicht alles
                              bestätigt ist
Dringlichkeit: (1 − sicher/alle) / max(1, Schultage bis zur Arbeit). An
Schultagen höchstens zwei Schritte, am Wochenende und in Ferien keiner, außer
die Zeit wird eng (D179). Grundpensum: an jedem Schultag mindestens ein
Schritt, sonst aus dem Vokabelpensum oder zur jüngsten „nicht verstanden“-
Rückmeldung.
"""
from __future__ import annotations

import json
import logging
from contextlib import closing
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from . import practice, rewards
from .db import webapp_conn

LOG = logging.getLogger("schul_cockpit.study_plan")

HORIZON = 28          # Tage voraus, in denen eine Arbeit zählt
MAX_SCHOOL = 2        # Pflichtschritte aus Arbeiten an einem Schultag
DIALOG_ANSWERS = 3    # Antworten im Gespräch, die einen Gesprächsschritt erledigen
PROBE_GAP = 3         # Tage, in denen keine zweite Probearbeit fällig wird
FEEDBACK_DAYS = 7     # so weit zurück zählt eine „nicht verstanden“-Rückmeldung


def _de(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day:02d}.{d.month:02d}."


# ------------------------------------------------------------------ Eingaben

def _exams(account_id: int, day: date) -> list[dict]:
    """Anstehende Arbeiten mit Themen: Termin aus exam_dates (die Klausurseite
    merkt ihn sich), Fach aus exam_topics. Die Tabelle kann fehlen."""
    last = day + timedelta(days=HORIZON)
    try:
        with closing(webapp_conn()) as c:
            rows = c.execute(
                "SELECT d.exam_key, d.exam_date, "
                "(SELECT subject FROM exam_topics t WHERE t.account_id=d.account_id AND t.exam_key=d.exam_key "
                " AND t.stale=0 LIMIT 1) AS subject "
                "FROM exam_dates d WHERE d.account_id=? AND substr(d.exam_date,1,10)>? AND substr(d.exam_date,1,10)<=? "
                "ORDER BY d.exam_date", (account_id, day.isoformat(), last.isoformat())).fetchall()
    except Exception:
        return []
    return [{"exam_key": r[0], "exam_date": r[1][:10], "subject": r[2]} for r in rows if r[2]]


def _last_was_dialog(c, account_id: int, topic_id: int) -> bool:
    row = c.execute("SELECT source FROM topic_answers WHERE account_id=? AND topic_id=? ORDER BY created_at DESC, id DESC LIMIT 1",
                    (account_id, topic_id)).fetchone()
    return bool(row) and row[0] in (None, "dialog")


def _recent_probe(c, account_id: int, topic_ids: list[int], day: date) -> bool:
    if not topic_ids:
        return False
    since = (day - timedelta(days=PROBE_GAP)).isoformat()
    return bool(c.execute(
        f"SELECT 1 FROM topic_answers WHERE account_id=? AND paper_format='probe' AND substr(created_at,1,10)>=? "
        f"AND topic_id IN ({','.join('?' * len(topic_ids))}) LIMIT 1", (account_id, since, *topic_ids)).fetchone())


def _vocab(account_id: int, day: date) -> list[dict]:
    """Das Vokabelpensum des Tages (Stufe C, eigenes Modul). Fehlt es, gibt es keins."""
    try:
        from . import vocab_pensum  # type: ignore[attr-defined]
        return list(vocab_pensum.daily(account_id, day) or [])
    except Exception:
        return []


def _vocab_key(v: dict) -> str:
    return f"vocab:{v.get('subject') or ''}:{v.get('unit') or ''}"


def _vocab_step(v: dict) -> dict:
    unit = v.get("unit")
    return {"key": _vocab_key(v), "kind": "vocab", "title": f"Vokabeln {v.get('subject') or ''}{': ' + unit if unit else ''}".strip(),
            "why": v.get("why") or "Jeden Tag ein paar Wörter sitzen besser als alle am Abend vorher.",
            "subject": v.get("subject"), "exam_key": v.get("exam_key"), "exam_date": None, "format": None,
            "topic_id": None, "level": None, "href": v.get("href") or "#/vokabeln", "target": v.get("target")}


# ---------------------------------------------------------------- Berechnen

def exam_step(account_id: int, exam: dict, day: date, school: list[date]) -> dict | None:
    """Der eine Schritt, den diese Arbeit heute braucht, oder keiner."""
    exam_day = date.fromisoformat(exam["exam_date"])
    left = sum(1 for d in school if day <= d < exam_day)
    last = not any(day < d < exam_day for d in school)
    r = practice.raster(account_id, exam["exam_key"])
    rows, total, ready = r["topics"], r["total"], r["ready"]
    if not total:
        return None
    not_ready = [t for t in rows if not t["ready"]]
    urgency = (1 - ready / total) / max(1, left)
    # Eng: weniger Schultage als offene Themen, oder die letzten zwei und nicht alles sicher.
    tight = bool(not_ready) and (left <= len(not_ready) or left <= 2)
    from .subject_names import label as subject_label
    subject, when = subject_label(exam["subject"]) or exam["subject"], _de(exam["exam_date"])
    base = {"subject": subject, "exam_key": exam["exam_key"], "exam_date": exam["exam_date"], "topic_id": None,
            "level": None, "href": None, "urgency": round(urgency, 4), "tight": tight, "days_left": left}

    def paper(fmt, title, why, topic_id=None):
        return {**base, "key": f"paper:{exam['exam_key']}:{fmt}", "kind": "paper", "format": fmt,
                "title": title, "why": why, "topic_id": topic_id}

    # Noch gar nichts gemessen: zuerst der Einstiegstest, auch am letzten Tag.
    if all(cell["state"] == "offen" for t in rows for cell in t["cells"].values()):
        return paper("einstieg", f"Einstiegstest {subject}", f"Zeigt, wo du für die Arbeit am {when} stehst.")
    if last:
        if all(t["cells"]["2"]["state"] == "bestaetigt" for t in rows):
            return None
        return paper("mix", f"Mix {subject}", f"Die Arbeit ist am {when}: ein kurzer Abschluss mit den schwächsten Themen.")
    with closing(webapp_conn()) as c:
        if not_ready:
            weak = sorted(not_ready, key=practice._weakness)[0]
            if _last_was_dialog(c, account_id, weak["id"]):
                return paper("kurz", f"Kurztest {subject}: {weak['title']}",
                             f"Im Gespräch geübt, jetzt zeigst du es auf Papier. Arbeit am {when}", weak["id"])
            return {**base, "key": f"dialog:{weak['id']}", "kind": "dialog", "format": None, "topic_id": weak["id"],
                    "title": f"{subject}: {weak['title']}", "href": f"#/learning?topic_id={weak['id']}",
                    "why": f"Das Thema sitzt noch nicht sicher. Drei Aufgaben mit dem Lernbegleiter, Arbeit am {when}"}
        if _recent_probe(c, account_id, [t["id"] for t in rows], day):
            return None
    return paper("probe", f"Probearbeit {subject}", f"Alle Themen sitzen. Die Probearbeit zeigt, ob es auch wie in der echten Arbeit am {when} klappt.")


def _lesson_step(account_id: int, day: date) -> dict | None:
    """Grundpensum ohne Arbeit und ohne Vokabeln: die Stunde der letzten sieben
    Tage, die das Kind zuletzt als „nicht“ oder „teilweise verstanden“ gemeldet hat."""
    lessons = {l["id"]: l for l in rewards._lessons(account_id, day - timedelta(days=FEEDBACK_DAYS), day) if rewards._held(l)}
    if not lessons:
        return None
    ids = list(lessons)
    marks = ",".join("?" * len(ids))
    with closing(webapp_conn()) as c:
        rated = {r[0] for r in c.execute(
            f"SELECT lesson_id FROM lesson_checkins WHERE account_id=? AND rating IN (1,2) AND lesson_id IN ({marks})", (account_id, *ids))}
        caught = {r[0] for r in c.execute(f"SELECT lesson_id FROM caught_up WHERE account_id=? AND lesson_id IN ({marks})", (account_id, *ids))}
    cand = [lessons[i] for i in rated - caught]
    if not cand:
        return None
    l = max(cand, key=lambda x: (x["date"], x.get("start_time") or 0, x["id"]))
    subject = l.get("subject_name") or l.get("subject_short") or ""
    title = l.get("lstext") or ""
    href = "#/learning?" + urlencode({"lesson_id": str(l["id"]), "subject": subject, "title": title})
    return {"key": f"lesson:{l['id']}", "kind": "dialog", "title": f"{subject}: {title or 'Stunde vom ' + _de(l['date'])} verstehen",
            "why": "Das war noch nicht ganz klar. Mit dem Lernbegleiter klärst du es, solange es frisch ist.",
            "subject": subject, "exam_key": None, "exam_date": None, "format": None, "topic_id": None,
            "level": None, "href": href, "lesson_id": l["id"]}


def compute(account_id: int, day: date) -> list[dict]:
    """Die Pflichtschritte eines Tages aus dem jetzigen Stand."""
    school = rewards.school_days(account_id, day, day + timedelta(days=HORIZON))
    school_day = day in school
    cands = []
    for exam in _exams(account_id, day):
        try:
            step = exam_step(account_id, exam, day, school)
        except Exception:
            LOG.warning("Lernschritt für %s nicht berechenbar", exam.get("exam_key"), exc_info=True)
            continue
        if step:
            cands.append(step)
    cands.sort(key=lambda s: (-s["urgency"], s["exam_date"]))
    if school_day:
        steps = cands[:MAX_SCHOOL]
    else:
        # Wochenende und Ferien dienen der Erholung (D179), außer die Zeit wird eng.
        steps = [s for s in cands if s["tight"]][:1]
    if not school_day:
        return steps
    vocab = _vocab(account_id, day)
    # Steht ein Vokabeltest an, ist das Pensum zusätzlich Pflicht, außerhalb der zwei.
    steps += [_vocab_step(v) for v in vocab if v.get("exam_key")]
    if not steps:
        # Grundpensum: jeden Schultag etwas, das erspart das Büffeln am Ende.
        steps = [_vocab_step(v) for v in vocab[:1]]
    if not steps:
        lesson = _lesson_step(account_id, day)
        steps = [lesson] if lesson else []
    return steps


# -------------------------------------------------------------- Einfrieren

def stored(account_id: int, day: date) -> list[dict] | None:
    try:
        with closing(webapp_conn()) as c:
            row = c.execute("SELECT steps_json FROM study_plan_days WHERE account_id=? AND day=?",
                            (account_id, day.isoformat())).fetchone()
    except Exception:
        return None
    return json.loads(row[0]) if row else None


def ensure(account_id: int, day: date) -> list[dict]:
    """Den Plan des Tages einmal berechnen und festhalten; danach bleibt er."""
    found = stored(account_id, day)
    if found is not None:
        return found
    steps = compute(account_id, day)
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT OR IGNORE INTO study_plan_days(account_id,day,steps_json,computed_at) VALUES(?,?,?,?)",
                  (account_id, day.isoformat(), json.dumps(steps, ensure_ascii=False), rewards.now_local().isoformat()))
    return stored(account_id, day) or steps


# ----------------------------------------------------------------- Erledigt

def _paper_done(c, account_id: int, s: dict, first: str, last: str) -> bool:
    # Jede heute ausgewertete Übungsarbeit dieser Arbeit erledigt den Papier-Schritt,
    # gleich welches Format: gemessen ist gemessen.
    return bool(c.execute(
        "SELECT 1 FROM mentor_exam_attempts a JOIN mentor_exams e ON e.id=a.exam_id "
        "WHERE a.account_id=? AND e.exam_key=? AND a.status='graded' AND a.is_test=0 AND ("
        " EXISTS(SELECT 1 FROM topic_answers t WHERE t.attempt_id=a.id AND substr(t.created_at,1,10) BETWEEN ? AND ?)"
        " OR substr(a.submitted_at,1,10) BETWEEN ? AND ?) LIMIT 1",
        (account_id, s["exam_key"], first, last, first, last)).fetchone())


def _dialog_done(c, account_id: int, s: dict, first: str, last: str) -> bool:
    n = c.execute("SELECT COUNT(*) FROM topic_answers WHERE account_id=? AND topic_id=? AND (source IS NULL OR source='dialog') "
                  "AND substr(created_at,1,10) BETWEEN ? AND ?", (account_id, s["topic_id"], first, last)).fetchone()[0]
    return n >= DIALOG_ANSWERS


def _lesson_done(c, account_id: int, s: dict, first: str, last: str) -> bool:
    lid = s.get("lesson_id")
    if c.execute("SELECT 1 FROM caught_up WHERE account_id=? AND lesson_id=? AND substr(caught_up_at,1,10) BETWEEN ? AND ?",
                 (account_id, lid, first, last)).fetchone():
        return True
    return bool(c.execute(
        "SELECT 1 FROM mentor_sessions WHERE account_id=? AND is_test=0 AND json_extract(source_json,'$.lesson_id')=? "
        "AND turns>=2 AND substr(updated_at,1,10) BETWEEN ? AND ? LIMIT 1", (account_id, lid, first, last)).fetchone())


def mark_done(account_id: int, steps: list[dict], day: date, until: date | None = None) -> list[dict]:
    """Jeden Schritt live prüfen. Zählt ab dem Plantag bis ``until``: Wer einen
    Tag rettet (D172), holt den Schritt am nächsten Morgen nach."""
    first, last = day.isoformat(), (until or day).isoformat()
    vocab = None
    out = []
    with closing(webapp_conn()) as c:
        for s in steps:
            done = False
            try:
                if s["kind"] == "paper":
                    done = _paper_done(c, account_id, s, first, last)
                elif s["kind"] == "dialog" and s.get("topic_id"):
                    done = _dialog_done(c, account_id, s, first, last)
                elif s["kind"] == "dialog" and s.get("lesson_id"):
                    done = _lesson_done(c, account_id, s, first, last)
                elif s["kind"] == "vocab":
                    if vocab is None:
                        vocab = {_vocab_key(v): v for v in _vocab(account_id, day)}
                    done = bool((vocab.get(s["key"]) or {}).get("done"))
            except Exception:
                LOG.debug("Lernschritt %s nicht prüfbar", s.get("key"), exc_info=True)
            out.append({**s, "done": done})
    return out


def open_count(account_id: int, day: date, until: date | None = None) -> int:
    """Offene Pflichtschritte des eingefrorenen Plans; ohne Plan keine."""
    steps = stored(account_id, day)
    if not steps:
        return 0
    return sum(1 for s in mark_done(account_id, steps, day, until) if not s["done"])


# ------------------------------------------------------------------ Ansicht

PUBLIC = ("key", "kind", "title", "why", "subject", "exam_key", "exam_date", "format", "topic_id", "level", "href",
          "done", "tight")


def view(account_id: int, day: date, *, store: bool) -> dict:
    """Der Plan für Heute. Berechnet und eingefroren wird nur für das Kind
    (auch am Elterngerät); Eltern sehen den festgehaltenen Plan oder, solange
    das Kind heute noch nicht da war, eine Vorschau, die nichts festhält."""
    steps = ensure(account_id, day) if store else stored(account_id, day)
    frozen = steps is not None
    if steps is None:
        steps = compute(account_id, day)
    checked = mark_done(account_id, steps, day)
    try:
        free = day not in rewards.school_days(account_id, day, day)
    except Exception:
        free = False
    tight = [{"subject": s["subject"], "exam_date": s["exam_date"]} for s in checked if s.get("tight")]
    return {"day": day.isoformat(), "steps": [{k: s.get(k) for k in PUBLIC} for s in checked],
            "engpass": bool(tight), "tight": tight, "free_day": free, "frozen": frozen, "read_only": not store,
            "done": sum(1 for s in checked if s["done"]), "total": len(checked)}


def today(account_id: int, user, now: datetime | None = None) -> dict:
    now = now or rewards.now_local()
    return view(account_id, now.date(), store=rewards.acting_child(user))
