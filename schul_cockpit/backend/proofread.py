"""Gegenlesen nur dort, wo die Lesung unsicher ist (D118).

Bisher verlangte jede Seite mit Handschrift einen Blick, und gezeigt wurde der
ganze gelesene Text am Stück, ohne das Foto daneben. Auf einer Arbeitsheftseite
mit sechzig Zeilen sind drei davon handschriftlich; wer das Dutzendfach
bestätigt, bestätigt irgendwann blind. Hier entsteht deshalb die kurze Fassung:
die Zweifelsstellen mit einer Zeile Zusammenhang, dazwischen eine Lücke.

Zweifelhaft ist eine Stelle aus zwei Gründen. Die Lesung selbst meldet sie
(`doubts`, mit Vorschlag und Begründung), oder der Text trägt eine Marke: was
das Kind eingetragen hat (`[Kind: …]`), was es gestrichen hat und was gar nicht
lesbar war (`[…]`). Die Marken stehen schon in jedem gelesenen Text und wirken
darum auch ohne neues Lesen.
"""

from __future__ import annotations

import re

# Die Marken, die eine Lesung im Text hinterlässt (D98): Eintragung des Kindes,
# Gestrichenes und Unleserliches. Nicht gierig, damit zwei Eintragungen in einer
# Zeile zwei Stellen bleiben.
PUPIL = re.compile(r"\[Kind(?: gestrichen)?:[^\]\n]{0,300}\]")
UNREADABLE = re.compile(r"\[(?:…|\.\.\.)\]")


def marks(text: str) -> list[dict]:
    """Die Stellen, die schon im Text markiert sind."""
    out = []
    for pattern, source in ((PUPIL, "pupil"), (UNREADABLE, "unreadable")):
        for hit in pattern.finditer(text or ""):
            out.append({"start": hit.start(), "end": hit.end(), "text": hit.group(),
                        "suggest": "", "reason": "", "source": source})
    return out


def _find(text: str, needle: str) -> tuple[int, int] | None:
    """Wo die gemeldete Stelle im Text steht. Wortgetreu zuerst; sonst mit
    beliebigem Zwischenraum, weil ein Zeilenumbruch im Text steht, den die
    Meldung als Leerzeichen wiedergibt."""
    needle = (needle or "").strip()
    if not needle:
        return None
    at = text.find(needle)
    if at >= 0:
        return at, at + len(needle)
    loose = r"\s+".join(re.escape(part) for part in needle.split())
    hit = re.search(loose, text)
    return (hit.start(), hit.end()) if hit else None


def spots(text: str, doubts: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Alle Zweifelsstellen mit Position, und was sich nicht wiederfinden ließ.

    Eine gemeldete Stelle geht einer Marke vor: Sie trägt den Vorschlag. Beide
    an derselben Stelle werden zu einer zusammengelegt."""
    text = text or ""
    found = list(marks(text))
    loose: list[dict] = []
    for doubt in doubts or []:
        where = _find(text, doubt.get("text", ""))
        entry = {"text": doubt.get("text", ""), "suggest": doubt.get("alternative", ""),
                 "reason": doubt.get("reason", ""), "source": "read"}
        if where is None:
            loose.append(entry)
            continue
        found.append({**entry, "start": where[0], "end": where[1]})
    found.sort(key=lambda s: (s["start"], -s["end"]))
    merged: list[dict] = []
    for spot in found:
        if merged and spot["start"] < merged[-1]["end"]:
            before = merged[-1]
            keep = before if before["source"] == "read" else spot
            merged[-1] = {**keep, "start": min(before["start"], spot["start"]),
                          "end": max(before["end"], spot["end"])}
            merged[-1]["text"] = text[merged[-1]["start"]:merged[-1]["end"]]
            continue
        merged.append(spot)
    return merged, loose


def _lines(text: str) -> list[tuple[int, int]]:
    """Anfang und Ende jeder Zeile, den Umbruch eingeschlossen."""
    out, start = [], 0
    for index, char in enumerate(text):
        if char == "\n":
            out.append((start, index + 1))
            start = index + 1
    out.append((start, len(text)))
    return out


def excerpt(text: str, found: list[dict], context: int = 1) -> list[dict]:
    """Der Text auf die Zweifelsstellen gekürzt.

    Jede Stelle steht mit `context` Zeilen davor und dahinter da; was dazwischen
    wegfällt, wird als Lücke mit ihrer Zeilenzahl gemeldet. Ohne Zweifelsstelle
    bleibt der Text ganz — dann ist nichts zu suchen, sondern alles zu prüfen.
    """
    text = text or ""
    if not found:
        return [{"kind": "text", "text": text}] if text else []
    rows = _lines(text)
    keep: set[int] = set()
    for spot in found:
        first = next(i for i, (a, b) in enumerate(rows) if a <= spot["start"] < b or i == len(rows) - 1)
        last = next(i for i, (a, b) in enumerate(rows) if a < spot["end"] <= b or i == len(rows) - 1)
        keep.update(range(max(0, first - context), min(len(rows) - 1, last + context) + 1))
    out: list[dict] = []
    index = 0
    while index < len(rows):
        if index not in keep:
            gap = 0
            while index < len(rows) and index not in keep:
                gap += 1
                index += 1
            # Eine einzelne ausgelassene Zeile spart nichts und zerreißt den
            # Zusammenhang; sie bleibt stehen.
            if gap == 1:
                out.append({"kind": "text", "text": text[rows[index - 1][0]:rows[index - 1][1]]})
            else:
                out.append({"kind": "gap", "lines": gap})
            continue
        block = index
        while index < len(rows) and index in keep:
            index += 1
        start, end = rows[block][0], rows[index - 1][1]
        at = start
        for spot in found:
            if spot["start"] < start or spot["end"] > end:
                continue
            if spot["start"] > at:
                out.append({"kind": "text", "text": text[at:spot["start"]]})
            out.append({"kind": "mark", "text": text[spot["start"]:spot["end"]],
                        "suggest": spot.get("suggest", ""), "reason": spot.get("reason", ""),
                        "source": spot["source"]})
            at = spot["end"]
        if at < end:
            out.append({"kind": "text", "text": text[at:end]})
    return [part for part in out if part["kind"] != "text" or part["text"]]


def view(text: str, doubts: list[dict] | None = None, context: int = 1) -> dict:
    """Was die Gegenlese-Karte zeigt: die gekürzte Fassung, die Zahl der
    Zweifelsstellen und die gemeldeten Stellen ohne Fundort."""
    found, loose = spots(text, doubts)
    segments = excerpt(text, found, context)
    return {"segments": segments, "spots": len(found), "loose": loose,
            "shortened": any(part["kind"] == "gap" for part in segments)}


def uncertain(text: str, doubts: list[dict] | None = None) -> bool:
    """Ob diese Lesung einen Blick braucht. Eine Eintragung des Kindes allein
    reicht nicht: Sauber gelesene Handschrift kostet keinen Blick (D118). Eine
    unleserliche Stelle schon — sie ist das Eingeständnis, nicht gelesen zu
    haben."""
    return bool(doubts) or bool(UNREADABLE.search(text or ""))


def resolve(text: str, spot: str, replace: str | None) -> str | None:
    """Eine Zweifelsstelle im Text durch die gelesene Fassung der Eltern
    ersetzen. None, wenn die Stelle so nicht mehr dasteht — dann hat sich der
    Text seit dem Anzeigen geändert."""
    where = _find(text or "", spot)
    if where is None or replace is None:
        return None if where is None else text
    return text[:where[0]] + replace + text[where[1]:]
