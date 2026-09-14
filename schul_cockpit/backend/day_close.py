"""Wann ein Abend erledigt war — abgeleitet, nicht abgefragt.

Die App braucht die Unterscheidung zwischen „für morgen ist nichts mehr offen"
und „niemand hat draufgeschaut", sonst trifft die Morgenmitteilung auch den, der
fertig ist. Ein eigener Knopf dafür wäre ein Ritual, das die Kinder nicht haben:
Sie lassen Dinge offen oder sie erledigen sie. Also zählt genau das.

Erledigt heißt: keine Aufgabe mehr fällig, die Tasche für morgen bestätigt, die
Stunden zurückgemeldet. Dieselben drei Zahlen, die abends über die Erinnerung
entscheiden. Festgehalten wird der Zeitpunkt, an dem das Letzte davon wegfiel,
und ob die Erinnerung da schon draußen war.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timedelta

from .db import history_conn, webapp_conn
from .queries import lessons_in_range

# Kein Knopfdruck, sondern der Stand der Dinge.
BY_WORK = "erledigt"


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


def record_if_clear(account_id: int, day: str, counts: dict, now: datetime) -> dict | None:
    """Der erste Moment des Tages, in dem nichts mehr offen ist, zählt.

    Später am Abend kann wieder etwas auflaufen — eine nachgetragene Aufgabe,
    eine neue Stunde. Das macht den Moment nicht ungeschehen, in dem das Kind
    fertig war.
    """
    if any(counts.values()):
        return None
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
            "open_homework,open_material,open_feedback) VALUES(?,?,?,?,?,0,0,0)",
            (account_id, day, now.isoformat(), BY_WORK, int(reminded(conn, account_id, day))),
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
        # Selbstständig heißt: ohne dass vorher erinnert werden musste.
        if not row["after_reminder"]:
            bucket["own"] += 1
    ordered = [buckets[k] for k in sorted(buckets)]
    current = next((b for b in ordered if b["week"] == _week_start(today).isoformat()), None)
    return {"weeks": ordered, "current": current}
