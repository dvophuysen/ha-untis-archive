"""Plausibilität einer Themenliste gegen den Unterricht (D79).

Kein Modell liest die handschriftliche 1 eines Kindes zuverlässig als 1; die
Eichung las auf einem Zettel jede 1 als 7 („S. 70, 71“ statt 10, 11). Der
Zusammenhang kennt die Antwort: Der Unterricht und die Hausaufgaben desselben
Fachs nennen die Stellen, die dran waren. Eine Seite auf dem Zettel, die
nirgends im Unterricht vorkommt, wird in der Gegenlese-Karte benannt, und wenn
eine Ziffernverwechslung (1/7, 0/6, 4/9) auf eine bekannte Stelle führt, wird
diese vorgeschlagen. Die Entscheidung bleibt beim Menschen; hier wird nichts
verändert.
"""

from __future__ import annotations

import logging
import re

from .sources import citations, mentions, page_hits, part_of, serves
from .subject_names import key as subject_key

LOG = logging.getLogger("schul_cockpit.notice_check")

# Ziffern, die in Handschrift ineinander übergehen.
CONFUSIONS = {"1": "7", "7": "1", "0": "6", "6": "0", "4": "9", "9": "4"}


def taught_places(texts: list[str], subject: str = "") -> dict[str, set[int]]:
    """Alle genannten Stellen aus Stunden- und Hausaufgabentexten, je Buchteil."""
    known: dict[str, set[int]] = {}
    for text in texts:
        for cite in citations(text, subject):
            pages = {p for p in cite["pages"] if p > 0}
            if pages:
                known.setdefault(cite["label"], set()).update(pages)
    return known


def _known(known: dict[str, set[int]], label: str, page: int) -> bool:
    return any(serves(have, label) and page in pages for have, pages in known.items())


def variants(page: int) -> list[int]:
    """Seitenzahlen, die durch Ziffernverwechslung entstehen: erst je eine
    Ziffer, dann alle verwechselbaren Ziffern zugleich (aus 77 wird 11, wenn
    ein Kind seine Einsen wie Siebenen schreibt)."""
    text = str(page)
    candidates = []
    for index, digit in enumerate(text):
        other = CONFUSIONS.get(digit)
        if other is not None:
            candidates.append(text[:index] + other + text[index + 1:])
    candidates.append("".join(CONFUSIONS.get(d, d) for d in text))
    out: list[int] = []
    for candidate in candidates:
        if candidate[0] == "0" and len(candidate) > 1:
            continue
        value = int(candidate)
        if value > 0 and value != page and value not in out:
            out.append(value)
    return out


def check(text: str, known: dict[str, set[int]], subject: str = "") -> dict:
    """Die Stellen eines Zettels gegen die bekannten Stellen des Fachs halten."""
    cited, unknown = 0, []
    # span nummeriert die Seitenangabe im Text: „S. 70, 71“ ist eine, und ihre
    # Seiten werden zusammen berichtigt, weil der Parser nach der ersten
    # Berichtigung („S. 10, 71“) die zweite nicht mehr als Aufzählung liest.
    for span, cite in enumerate(citations(text or "", subject)):
        for page in cite["pages"]:
            if page <= 0:
                continue
            cited += 1
            if _known(known, cite["label"], page):
                continue
            suggest = next((v for v in variants(page) if _known(known, cite["label"], v)), None)
            unknown.append({"label": cite["label"], "page": page, "suggest": suggest, "span": span})
    return {"checked": bool(known), "cited": cited, "unknown": unknown,
            "known_pages": sum(len(p) for p in known.values())}


def replace_pages(text: str, fixes: list[dict], subject: str = "") -> str | None:
    """Falsch gelesene Seiten durch die Vorschläge ersetzen, alle in einem
    Durchgang über den ursprünglichen Text: nur innerhalb der Seitenangabe des
    passenden Buchteils, nie eine Aufgabennummer, eine Lektion oder ein Datum.
    None, wenn keine der Stellen mehr im Text steht."""
    out = text or ""
    changed = False
    # Von hinten nach vorn, damit die Positionen der früheren Treffer gültig bleiben.
    for start, end, pages in reversed(page_hits(out)):
        have, _ = part_of(out[:start], subject)
        label = have or "Unbekannte Quelle"
        piece = out[start:end]
        for fix in fixes:
            if fix["label"] != label or fix["page"] not in pages:
                continue
            piece, count = re.subn(rf"(?<!\d){int(fix['page'])}(?!\d)", str(int(fix["suggest"])), piece)
            changed = changed or bool(count)
        out = out[:start] + piece + out[end:]
    return out if changed else None


def handwritten_pages(text: str) -> set[int]:
    """Welche der genannten Seitenzahlen das Kind selbst geschrieben hat.

    Die Prüfung ist gegen die Handschrift gemacht: Eine 1, die wie eine 7
    aussieht. Eine gedruckte Seitenzahl ist dagegen sicher gelesen, und ein
    gedruckter Querverweis („▶ S. 48") steht selten in einem Stundentext — er
    wäre also dauernd „unbekannt", ohne dass irgendetwas falsch wäre (D118).
    Zählt deshalb nur, was innerhalb einer Eintragung des Kindes steht."""
    from .proofread import PUPIL
    spans = [(hit.start(), hit.end()) for hit in PUPIL.finditer(text or "")]
    if not spans:
        return set()
    out: set[int] = set()
    for start, _, pages in page_hits(text or ""):
        if any(first <= start < last for first, last in spans):
            out.update(pages)
    return out


def checker(account_id: int):
    """Einmal je Anfrage die Stellen des Schuljahrs lesen, dann je Zettel prüfen."""
    cache: dict[str, dict[str, set[int]]] = {}
    found = None

    def run(material: dict) -> dict | None:
        nonlocal found
        subject = (material.get("subject_name") or "").strip()
        text = material.get("content_text") or ""
        if not subject or not text:
            return None
        if found is None:
            try:
                found, _ = mentions(account_id)
            except Exception:
                LOG.debug("Stellen des Unterrichts für Konto %s nicht lesbar", account_id, exc_info=True)
                found = []
        key = subject_key(subject)
        if key not in cache:
            cache[key] = taught_places([m["text"] for m in found
                                        if m["kind"] in ("lesson", "homework") and subject_key(m["subject"]) == key], subject)
        return check(text, cache[key], subject)

    return run
