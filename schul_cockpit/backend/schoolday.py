"""Schultage jenseits des bekannten Stundenplans (A13).

Der Stundenplan reicht nur ein, zwei Wochen voraus. Dahinter zählten Plan und
Kompass Montag bis Freitag als Schultage, auch in den Ferien: Vor den
Herbstferien sah eine Arbeit danach aus, als blieben zwei Wochen zum Lernen.
Ferien und Feiertage aus UNTIS (`master_holidays`) zählen jetzt nicht mit,
soweit die Integration sie liefert; ohne sie bleibt es bei Montag bis Freitag.
"""
from __future__ import annotations

from datetime import date, timedelta

from .request_cache import memo


@memo(shallow=True)
def _holidays(account_id: int, first: date, last: date) -> list[tuple[str, str]]:
    from .week_rolling import holidays
    return [(h["start"][:10], h["end"][:10]) for h in holidays(account_id, first, last)]


def free_days(account_id: int, first: date, last: date) -> set[date]:
    """Tage in Ferien oder an Feiertagen im Zeitraum."""
    if last < first:
        return set()
    out: set[date] = set()
    for start, end in _holidays(account_id, first, last):
        try:
            a, b = date.fromisoformat(start), date.fromisoformat(end)
        except ValueError:
            continue
        d = max(a, first)
        while d <= min(b, last):
            out.add(d)
            d += timedelta(days=1)
    return out


def project(account_id: int, known: set[date], first: date, last: date, horizon: date) -> list[date]:
    """Die bekannten Schultage, dahinter (nach ``horizon``) Montag bis Freitag
    ohne Ferien und Feiertage."""
    days = (first + timedelta(days=i) for i in range(max(0, (last - first).days + 1)))
    ahead = [d for d in days if d > horizon and d.weekday() < 5]
    if ahead:
        off = free_days(account_id, ahead[0], ahead[-1])
        ahead = [d for d in ahead if d not in off]
    return sorted(set(known) | set(ahead))
