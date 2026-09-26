"""Verlässliche Auswertung (D202): Es zählt nur, worin zwei unabhängige
Durchgänge übereinstimmen. Gemeinsam für Übungsarbeit, Übungsklausur und
Vokabeltest auf Papier; was offen bleibt, prüfen die Eltern."""
from __future__ import annotations

TOLERANCE = 1.0  # Punkte, um die zwei Durchgänge je Aufgabe höchstens auseinanderliegen
VERDICTS = ("richtig", "falsch")


def agreeing(xs: list) -> list:
    """Die Durchgänge einer Aufgabe, die sich einig sind (höchstens TOLERANCE
    auseinander, mindestens zwei sicher gelesene); sonst leer."""
    sure = [x for x in xs if not x.uncertain]
    if len(sure) < 2:
        return []
    vals = sorted(x.points for x in sure)
    if vals[-1] - vals[0] <= TOLERANCE:
        return sure
    if len(sure) >= 3:
        mid = vals[len(vals) // 2]
        agree = [x for x in sure if abs(x.points - mid) <= TOLERANCE]
        return agree if len(agree) >= 2 else []
    return []


def settle(xs: list, most: float, exclude: set[str] | None = None) -> dict:
    """Ergebnis einer Aufgabe aus ihren Durchgängen: bei Einigkeit deren Mittel
    auf halbe Punkte, sonst uncertain mit den gelesenen Punkten (spread)."""
    agree = agreeing(xs)
    if agree:
        pts = min(most, round(sum(x.points for x in agree) / len(agree) * 2) / 2)
        best = min(agree, key=lambda x: abs(x.points - pts))
        return {**best.model_dump(exclude=exclude), "points": pts, "uncertain": False}
    sure = [x for x in xs if not x.uncertain]
    best = (sure or xs)[0]
    return {**best.model_dump(exclude=exclude), "uncertain": True, "spread": [x.points for x in sure]}


def diverge(xs: list) -> bool:
    """Ob sicher gelesene Durchgänge verschiedene Punkte geben (D217): Dann
    kommt ein dritter dazu, statt zu mitteln."""
    return len({x.points for x in xs if not x.uncertain}) > 1


def settle_exact(xs: list, most: float, exclude: set[str] | None = None) -> dict:
    """Wie settle, aber bei drei oder mehr einigen Durchgängen zählt der mittlere
    echte Durchgang mit seiner eigenen Begründung, kein Mittelwert (D217). Ein
    Mittel aus 3 und 2 Punkten ergab 2,5 mit einer Begründung, in der die Tabelle
    nur einen halben Punkt bekam, obwohl sie stimmte."""
    agree = agreeing(xs)
    if len(agree) >= 3:
        mid = sorted(agree, key=lambda x: x.points)[len(agree) // 2]
        return {**mid.model_dump(exclude=exclude), "points": min(most, mid.points), "uncertain": False}
    return settle(xs, most, exclude)


def majority(votes: list[str]) -> str | None:
    """Ein Wort: richtig oder falsch, wenn mindestens zwei Durchgänge es so
    lesen; unklar oder uneinig bleibt offen (None)."""
    for v in VERDICTS:
        if votes.count(v) >= 2:
            return v
    return None
