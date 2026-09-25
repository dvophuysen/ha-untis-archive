"""Zählung der Lern-Abzeichen aus Stufe C (D181): Probearbeit, Aufsteiger,
Zielniveau und Extrameile.

Probearbeit, Aufsteiger und Zielniveau werden aus den gespeicherten Antworten
(`topic_answers`) und Terminen abgelesen, nicht mitgeschrieben; so bleibt die
Zählung auch nach einer Korrektur stimmig. Nur die Extrameile braucht ein
Ereignis (`reward_events` kind 'extra'), weil das Pflichtpensum eines Tages
später nicht mehr bekannt ist. Extra zählt nur zusätzlich, nie statt Pflicht.
"""
from __future__ import annotations

import logging
from contextlib import closing
from datetime import date, timedelta

from .db import webapp_conn

LOG = logging.getLogger("schul_cockpit.reward_extras")

# Wörter über dem Tagespensum, ab denen ein Tag als Extrameile zählt.
EXTRA_WORDS = 10


def _today() -> date:
    from .rewards import now_local
    return now_local().date()


def _extra(account_id: int, ref: str, day: date) -> None:
    from .rewards import now_local
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT OR IGNORE INTO reward_events(account_id,kind,ref,day,created_at) VALUES(?,?,?,?,?)",
                  (account_id, "extra", ref, day.isoformat(), now_local().isoformat()))


def note_extra_vocab(account_id: int, user, day: date | None = None) -> bool:
    """Vokabeln über das Pensum hinaus: Ist das Tagespensum erledigt und hat das
    Kind heute mindestens zehn Wörter mehr geübt, zählt der Tag einmal."""
    from . import rewards, vocab_pensum
    if not rewards.acting_child(user):
        return False
    day = day or _today()
    try:
        with closing(webapp_conn()) as c:
            if c.execute("SELECT 1 FROM reward_events WHERE account_id=? AND kind='extra' AND ref=?",
                         (account_id, f"vocab:{day.isoformat()}")).fetchone():
                return False
        done = vocab_pensum.practiced(account_id, day)
        if len(done) < EXTRA_WORDS:
            return False
        items = vocab_pensum.daily(account_id, day)
        if any(not e["done"] for e in items):
            return False
        if len(done) < sum(e["target"] for e in items) + EXTRA_WORDS:
            return False
        _extra(account_id, f"vocab:{day.isoformat()}", day)
        return True
    except Exception:
        LOG.warning("Extrameile Vokabeln für Konto %s nicht erfasst", account_id, exc_info=True)
        return False


def note_extra_practice(account_id: int, attempt_id: int, exam_key: str | None, user, day: date | None = None) -> bool:
    """Eine Übungsarbeit an einem Tag ohne Pflicht: an einem Tag ohne Unterricht
    (D179) oder wenn die Arbeit noch mehr als sechs Wochen entfernt ist."""
    from . import rewards, vocab_pensum
    if not rewards.acting_child(user):
        return False
    day = day or _today()
    try:
        free = day not in vocab_pensum.school_days(account_id, day, day)
        far = False
        if exam_key:
            with closing(webapp_conn()) as c:
                try:
                    row = c.execute("SELECT exam_date FROM exam_dates WHERE account_id=? AND exam_key=?",
                                    (account_id, exam_key)).fetchone()
                except Exception:
                    row = None
            far = bool(row and row[0][:10] > (day + timedelta(days=vocab_pensum.HORIZON)).isoformat())
        if free or far:
            _extra(account_id, f"practice:{attempt_id}", day)
            return True
    except Exception:
        LOG.warning("Extrameile Übungsarbeit für Konto %s nicht erfasst", account_id, exc_info=True)
    return False


# ------------------------------------------------------------------ Zählung

def _answers(c, account_id: int) -> list[dict]:
    return [dict(r) for r in c.execute(
        "SELECT a.*, t.exam_key, t.title FROM topic_answers a JOIN exam_topics t ON t.id=a.topic_id "
        "WHERE a.account_id=? ORDER BY a.created_at,a.id", (account_id,))]


def probe_papers(answers: list[dict], start: date) -> int:
    """Ausgewertete Probearbeiten, je Arbeitsversuch einmal."""
    return len({a["attempt_id"] for a in answers
                if a.get("paper_format") == "probe" and a.get("attempt_id") and a["created_at"][:10] >= start.isoformat()})


def risen_cells(answers: list[dict], start: date) -> int:
    """Zellen Thema × Bereich, die erstmals sicher wurden (ab dem Start)."""
    from . import practice as pr
    cells: dict[tuple, list[dict]] = {}
    for a in answers:
        cells.setdefault((a["topic_id"], a.get("afb") or 1), []).append(a)
    count = 0
    for rows in cells.values():
        for i in range(len(rows)):
            if pr.is_sure(pr.cell(rows[: i + 1])):
                count += rows[i]["created_at"][:10] >= start.isoformat()
                break
    return count


def ready_exams(c, account_id: int, answers: list[dict], start: date, today: date) -> int:
    """Arbeiten, bei denen vor dem Termin jedes Thema sein Zielniveau erreicht hatte
    (I und II sicher, D178). Vokabelthemen haben kein Raster und zählen nicht mit."""
    from . import practice as pr
    from .lernstand import is_vocab_topic
    try:
        dates = c.execute("SELECT exam_key,exam_date FROM exam_dates WHERE account_id=? AND exam_date>=? AND exam_date<=?",
                          (account_id, start.isoformat(), today.isoformat())).fetchall()
    except Exception:
        return 0
    count = 0
    for key, when in dates:
        topics = [dict(r) for r in c.execute(
            "SELECT id,title FROM exam_topics WHERE account_id=? AND exam_key=? AND stale=0", (account_id, key))]
        topics = [t for t in topics if not is_vocab_topic(t)]
        if not topics:
            continue
        before = [a for a in answers if a["created_at"][:10] < when[:10]]
        if all(pr.row_of([a for a in before if a["topic_id"] == t["id"]])["ready"] for t in topics):
            count += 1
    return count


def counts(account_id: int, start: date, today: date) -> dict:
    """Werte der vier Abzeichen für rewards.summary."""
    out = {"probearbeit": 0, "aufsteiger": 0, "zielniveau": 0, "extrameile": 0}
    try:
        with closing(webapp_conn()) as c:
            answers = _answers(c, account_id)
            out["probearbeit"] = probe_papers(answers, start)
            out["aufsteiger"] = risen_cells(answers, start)
            out["zielniveau"] = ready_exams(c, account_id, answers, start, today)
            out["extrameile"] = c.execute("SELECT COUNT(*) FROM reward_events WHERE account_id=? AND kind='extra' AND day>=?",
                                          (account_id, start.isoformat())).fetchone()[0]
    except Exception:
        LOG.warning("Lern-Abzeichen für Konto %s nicht zählbar", account_id, exc_info=True)
    return out
