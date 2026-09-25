"""Archiv nach der Arbeit (D182).

Was der Vorbereitung auf eine Arbeit diente, verschwindet am Tag danach aus
der Lernseite, so wie erledigte Hausaufgaben. Nichts wird gelöscht: Nachweise
und Stufen bleiben, und „Wieder aufnehmen“ holt eine Einheit zurück.

  Einheit zu einem Thema der Arbeit   am Tag nach der Arbeit
  Hausaufgabenhilfe                   wenn die Aufgabe abgehakt ist, oder drei
                                      Tage nach dem Fälligkeitstag
  alles andere                        nach 14 Tagen ohne Aktivität

Die Regel wird beim Lesen angewandt, nicht gespeichert: Wird eine Arbeit
verschoben, kommt ihre Einheit von selbst zurück.
"""
from __future__ import annotations

from datetime import date, timedelta

HOMEWORK_GRACE = 3
IDLE_DAYS = 14
HOMEWORK_MODES = ("homework_help", "homework_check")


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def exam_dates_for_topics(c, account_id: int, topic_ids: list[int]) -> dict[int, date]:
    """Termin der Arbeit je Thema; die Tabelle exam_dates kann fehlen."""
    ids = [t for t in topic_ids if t]
    if not ids:
        return {}
    try:
        rows = c.execute(
            f"SELECT t.id, d.exam_date FROM exam_topics t JOIN exam_dates d "
            f"ON d.account_id=t.account_id AND d.exam_key=t.exam_key "
            f"WHERE t.account_id=? AND t.id IN ({','.join('?' * len(ids))})", (account_id, *ids)).fetchall()
    except Exception:
        return {}
    return {r[0]: _day(r[1]) for r in rows if _day(r[1])}


def trigger(row: dict, exam_day: date | None) -> tuple[date | None, str]:
    """Ab welchem Tag ein Verlauf ins Archiv gehört, und warum."""
    if row.get("topic_id") and exam_day:
        return exam_day + timedelta(days=1), f"Arbeit am {exam_day:%d.%m.} geschrieben"
    if row.get("mode") in HOMEWORK_MODES and row.get("task_status") is not None:
        if row.get("task_status") == "done":
            return (_day(row.get("task_completed_at")) or _day(row.get("last_at")) or date.min), "Hausaufgabe erledigt"
        due = _day(row.get("task_due"))
        if due:
            return due + timedelta(days=HOMEWORK_GRACE + 1), f"Hausaufgabe war am {due:%d.%m.} fällig"
    last = max(filter(None, [_day(row.get("last_at")), _day(row.get("unarchived_at"))]), default=None)
    if last:
        return last + timedelta(days=IDLE_DAYS), f"seit {last:%d.%m.} nicht weitergemacht"
    return None, ""


def is_archived(row: dict, exam_day: date | None, today: date) -> tuple[bool, str]:
    when, why = trigger(row, exam_day)
    if not when or today < when:
        return False, ""
    back = _day(row.get("unarchived_at"))
    if back and back >= when:
        return False, ""
    return True, why
