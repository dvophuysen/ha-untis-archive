"""Hausaufgaben-Erlass Niedersachsen (RdErl. d. MK v. 12.09.2019 – 36-82 100,
zuletzt geändert 16.05.2024). Liefert pro Kind und Datum das laut Erlass
zulässige Tagesbudget.

Quelle:
  Primarbereich (Klassen 1–4):  max. 30 min/Tag, kein Wochenende, keine Ferien.
  Sekundarbereich I (5–10):     max. 60 min/Tag, grundsätzlich kein Wochenende.
  Sekundarbereich II (11–13):   max. 120 min/Tag, Sek-I-Vorgaben als Orientierung.
  An Tagen mit Nachmittagsunterricht: HA "in geringerem Umfang".
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from .db import history_conn

Section = Literal["primar", "sek1", "sek2"]

ERLASS_DAILY_MIN: dict[Section, int] = {
    "primar": 30,
    "sek1": 60,
    "sek2": 120,
}
# Erlass: keine HA Fr→Mo. Wir setzen damit Sa+So = 0.
WEEKEND_MIN = 0
# "Geringerer Umfang" wenn heute Nachmittagsunterricht — der Erlass nennt
# keine Zahl; -25 % (auf 15 min gerundet) ist eine konservative Lesart.
AFTERNOON_REDUCTION_FACTOR = 0.75
# Stunden, die später als diese Schwelle starten, gelten als Nachmittag.
AFTERNOON_THRESHOLD_HHMM = 1330


def parse_section_from_klasse(klasse_name: str | None) -> tuple[int | None, Section | None]:
    """Bestes-Effort-Parse aus dem Klassennamen.
    Rückgabe: (grade, section) — grade ist 1–13 oder None."""
    if not klasse_name:
        return None, None
    s = klasse_name.strip().upper()
    m = re.match(r"^(\d{1,2})", s)
    if m:
        try:
            grade = int(m.group(1))
        except ValueError:
            grade = 0
        if 1 <= grade <= 4:
            return grade, "primar"
        if 5 <= grade <= 10:
            return grade, "sek1"
        if 11 <= grade <= 13:
            return grade, "sek2"
    # Niedersachsen-Oberstufen: EF = Einführungsphase (Kl. 11), Q1–Q4 = Qualifikation (Kl. 12/13).
    if s.startswith("E"):
        return 11, "sek2"
    if s.startswith("Q"):
        return 12, "sek2"
    return None, None


def get_current_klasse(account_id: int) -> tuple[str | None, str | None]:
    """Latest enrollment for this account → (klasse_name, klasse_longName)."""
    hconn = history_conn()
    try:
        row = hconn.execute(
            "SELECT mk.name, mk.longName FROM enrollment e "
            "JOIN master_klasse mk ON mk.account_id = e.account_id AND mk.id = e.klasse_id "
            "WHERE e.account_id = ? "
            "ORDER BY e.schoolyear_id DESC, e.last_seen_at DESC LIMIT 1",
            (account_id,),
        ).fetchone()
        if not row:
            return None, None
        return row["name"], row["longName"]
    finally:
        hconn.close()


def has_afternoon_school(account_id: int, target_date: date) -> bool:
    """Hat das Kind an diesem Datum tatsächlich Unterricht nach AFTERNOON_THRESHOLD?"""
    hconn = history_conn()
    try:
        row = hconn.execute(
            "SELECT 1 FROM lessons WHERE account_id = ? AND date = ? "
            "AND (code IS NULL OR LOWER(code) != 'cancelled') "
            "AND start_time >= ? LIMIT 1",
            (account_id, target_date.isoformat(), AFTERNOON_THRESHOLD_HHMM),
        ).fetchone()
        return row is not None
    finally:
        hconn.close()


def _round_to_15(minutes: int) -> int:
    # Erlass nennt 15-Minuten-Schritte praktisch nicht explizit, aber für
    # die Anzeige sehen runde Werte deutlich besser aus.
    return max(0, round(minutes / 15) * 15)


def erlass_budget_minutes(
    section: Section,
    target_date: date,
    *,
    has_afternoon: bool = False,
) -> int:
    """Pro Tag laut Erlass."""
    if target_date.weekday() >= 5:
        return WEEKEND_MIN
    base = ERLASS_DAILY_MIN[section]
    if has_afternoon:
        return _round_to_15(int(base * AFTERNOON_REDUCTION_FACTOR))
    return base


def resolve_section(
    account_id: int,
    override: str | None = None,
) -> tuple[Section | None, str | None, str | None]:
    """Returns (section, detected_class_name, source).
    `source` ∈ {'override', 'auto', 'none'} — gut für die UI-Begründung."""
    if override and override in ERLASS_DAILY_MIN:
        klasse_name, _ = get_current_klasse(account_id)
        return override, klasse_name, "override"  # type: ignore[return-value]
    klasse_name, _ = get_current_klasse(account_id)
    if not klasse_name:
        return None, None, "none"
    _, section = parse_section_from_klasse(klasse_name)
    if section is None:
        return None, klasse_name, "none"
    return section, klasse_name, "auto"
