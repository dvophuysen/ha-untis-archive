"""Der Tagesabschluss: die Angabe, die der App bisher gefehlt hat.

Bisher wusste die App nur, ob gerade etwas offen ist. Ob ein Kind seinen Tag
selbst durchgegangen ist, war nicht unterscheidbar von einem Tag, an dem
ohnehin nichts anlag. Daran scheiterten die Morgenmitteilung (sie hätte auch
den getroffen, der fertig war) und jedes Maß für die eigene Verlässlichkeit.

Festgehalten wird deshalb nicht nur *dass* abgeschlossen wurde, sondern auch
von wem und ob die Erinnerung schon draußen war. Nur „vom Kind selbst, ohne
Erinnerung" ist das, was die Vision unter Selbstständigkeit versteht.

Ein Abschluss bei noch offenen Punkten ist erlaubt und wird ehrlich vermerkt.
Die App verhängt nichts; sie hält fest.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timedelta

from .db import history_conn, webapp_conn
from .queries import lessons_in_range

BY_CHILD = "kind"
BY_PARENT = "eltern"


def reminded(conn, account_id: int, day: str) -> bool:
    """War die abendliche Mitteilung an diesem Tag schon zugestellt?"""
    row = conn.execute(
        "SELECT 1 FROM reminder_app_deliveries "
        "WHERE account_id=? AND school_day=? AND status='accepted' LIMIT 1",
        (account_id, day),
    ).fetchone()
    return bool(row)


def closure(account_id: int, day: str) -> dict | None:
    with closing(webapp_conn()) as conn:
        row = conn.execute(
            "SELECT * FROM day_closures WHERE account_id=? AND school_day=?",
            (account_id, day),
        ).fetchone()
    return dict(row) if row else None


def close(account_id: int, day: str, by: str, counts: dict, now: datetime) -> dict:
    """Der erste Abschluss eines Tages zählt.

    Ein zweiter Druck auf den Knopf darf das Bild nicht schönen: Wer abends um
    acht mit zwei offenen Aufgaben abgeschlossen hat, hat genau das getan.
    """
    with closing(webapp_conn()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        already = conn.execute(
            "SELECT * FROM day_closures WHERE account_id=? AND school_day=?",
            (account_id, day),
        ).fetchone()
        if already:
            return dict(already)
        conn.execute(
            "INSERT INTO day_closures(account_id,school_day,closed_at,closed_by,after_reminder,"
            "open_homework,open_material,open_feedback) VALUES(?,?,?,?,?,?,?,?)",
            (account_id, day, now.isoformat(), by, int(reminded(conn, account_id, day)),
             int(counts.get("homework", 0)), int(counts.get("material", 0)),
             int(counts.get("feedback", 0))),
        )
        row = conn.execute(
            "SELECT * FROM day_closures WHERE account_id=? AND school_day=?",
            (account_id, day),
        ).fetchone()
    return dict(row)


def school_days(account_id: int, first: date, last: date) -> set[str]:
    """Tage mit Unterricht. Ferien und Wochenenden zählen nirgends mit."""
    try:
        with closing(history_conn()) as conn:
            rows = lessons_in_range(conn, account_id, first.isoformat(), last.isoformat())
    except Exception:
        return set()
    return {l["date"] for l in rows
            if not l.get("is_cancelled") and not l.get("was_absent")}


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def reliability(account_id: int, today: date, weeks: int = 4) -> dict:
    """An wie vielen Schultagen hat das Kind selbst abgeschlossen?

    Gezählt wird der Abend *vor* einem Schultag: Wer am Sonntag packt, hat für
    den Montag abgeschlossen. Ein Abend gehört deshalb in die Woche des
    Schultags, den er vorbereitet, nicht in die des Abends selbst — sonst fiele
    jeder Sonntagabend in die vergangene Woche.
    """
    start = _week_start(today) - timedelta(weeks=weeks - 1)
    days = sorted(school_days(account_id, start, today + timedelta(days=1)))
    with closing(webapp_conn()) as conn:
        rows = {r["school_day"]: dict(r) for r in conn.execute(
            "SELECT * FROM day_closures WHERE account_id=? AND school_day>=?",
            (account_id, (start - timedelta(days=1)).isoformat()))}
    buckets: dict[str, dict] = {}
    for day in days:
        evening = date.fromisoformat(day) - timedelta(days=1)
        if evening > today:
            continue
        week = _week_start(date.fromisoformat(day)).isoformat()
        bucket = buckets.setdefault(week, {"week": week, "evenings": 0, "closed": 0, "own": 0})
        bucket["evenings"] += 1
        row = rows.get(evening.isoformat())
        if not row:
            continue
        bucket["closed"] += 1
        if row["closed_by"] == BY_CHILD and not row["after_reminder"]:
            bucket["own"] += 1
    ordered = [buckets[k] for k in sorted(buckets)]
    current = next((b for b in ordered if b["week"] == _week_start(today).isoformat()), None)
    return {"weeks": ordered, "current": current}
