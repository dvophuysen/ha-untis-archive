"""Welche Quellen der Unterricht nennt — und welche davon noch fehlen.

Die Lehrkräfte schreiben die Stelle im Buch meistens selbst dazu: „TB S. 13
Aufg. C, AH S. 7", „#cda, p. 28", „Arbeitsheft S. 85, Aufg. 5". Daraus lässt
sich ohne KI eine Liste der Quellen bauen, auf die sich der Stoff stützt.

Ein Teil davon liegt digital im Medienregal und braucht niemanden. Der Rest
existiert nur auf Papier: Arbeitshefte, Arbeitsblätter, eigene Mitschriften.
Genau die fehlen der App, wenn sie eine Lernkarte oder eine Übungsklausur auf
den tatsächlichen Stoff stützen soll, statt etwas Ähnliches zu erfinden.

Hier wird nur gerechnet und angezeigt. Nichts wird angefordert und nichts
abgerufen.
"""

from __future__ import annotations

import re
from contextlib import closing
from datetime import timedelta

from .courses import hidden_keys, lesson_is_hidden
from .db import history_conn, webapp_conn
from .learning import today_local
from .mentor_context import rows, school_start
from .queries import _subject_short_from_payload

# Wie eine Quelle geschrieben wird und was sie ist. „cda" ist bei Spanisch das
# Cuaderno de actividades, „TB" der Textband. Die Zuordnung ist eine Annahme;
# sie steht in der Anzeige, damit sie widersprochen werden kann.
PARTS: list[tuple[str, str, str]] = [
    # (Muster, Anzeigename, Art)
    (r"textband|lehrbuch|schulbuch|kursbuch|textbook|\bTB\b|\bSB\b|\blibro\b|\bbuch\b", "Schulbuch", "book"),
    (r"vocabulario|wordbank|wortschatzteil", "Schulbuch, Vokabelteil", "book"),
    (r"arbeitsheft|\bA-?Heft\b|\bAH\b|workbook|cuaderno|\bcda\b|übungsheft|uebungsheft|arbeitsbuch", "Arbeitsheft", "workbook"),
    (r"grammatikheft|grammatisches beiheft|beiheft", "Grammatikheft", "workbook"),
    (r"arbeitsblatt|\bAB\b|handout|merkblatt|kopie", "Arbeitsblatt", "worksheet"),
]

# Nur eine ausdrückliche Seitenangabe zählt. Ohne diese Regel wird aus
# „#libro, p. 50 vocabulario 4 b" eine Seite 4, obwohl 4 b die Aufgabe ist.
PAGE = re.compile(r"\b(?:S\.|Seite|pp?\.|página|pagina)\s*(\d{1,3})(?:\s*(?:-|–|bis)\s*(\d{1,3}))?", re.I)


def part_of(text: str) -> tuple[str, str]:
    """Der zuletzt genannte Buchteil vor einer Seitenangabe."""
    best = ("", "")
    at = -1
    for pattern, label, kind in PARTS:
        for hit in re.finditer(pattern, text, re.I):
            if hit.start() > at:
                at, best = hit.start(), (label, kind)
    return best


def citations(text: str) -> list[dict]:
    """Jede Seitenangabe mit dem Buchteil, der davor steht."""
    found = []
    for hit in PAGE.finditer(text or ""):
        first = int(hit.group(1))
        last = int(hit.group(2)) if hit.group(2) else first
        if last < first or last - first > 30:
            last = first
        # Der zuletzt genannte Teil gilt weiter: In „Buch, S. 30-32 … Aufgabe 1
        # auf S. 34" gehört auch die 34 ins Buch.
        label, kind = part_of(text[:hit.start()])
        found.append({"label": label or "Unbekannte Quelle", "kind": kind or "unknown",
                      "pages": list(range(first, last + 1))})
    return found


def _material_pages(account_id: int) -> dict[str, set[int]]:
    """Welche Seiten je Fach schon in der Ablage liegen."""
    have: dict[str, set[int]] = {}
    with closing(webapp_conn()) as conn:
        for row in conn.execute(
            "SELECT subject_name,title,summary,content_text FROM materials "
            "WHERE account_id=? AND hidden=0", (account_id,)):
            subject = (row["subject_name"] or "").strip().casefold()
            text = " ".join(filter(None, (row["title"], row["summary"], row["content_text"])))
            pages = have.setdefault(subject, set())
            for cite in citations(text):
                pages.update(cite["pages"])
    return have


def _shelf(account_id: int) -> set[str]:
    """Fächer, für die ein digitales Buch im Regal liegt.

    Ein stilles except hatte hier den falschen Spaltennamen verschluckt und
    damit jede Buchseite auf die Einkaufsliste gesetzt.
    """
    with closing(webapp_conn()) as conn:
        have = {r[1] for r in conn.execute("PRAGMA table_info(digital_textbook_catalog)")}
        if "subject_name" not in have:
            return set()
        return {(r[0] or "").strip().casefold() for r in conn.execute(
            "SELECT subject_name FROM digital_textbook_catalog WHERE account_id=?", (account_id,)) if r[0]}


def subject_map(lessons: list[dict]) -> dict[str, str]:
    """Das Kürzel einer Hausaufgabe auf den Fachnamen der Stunden abbilden.

    Hausaufgaben führen in Untis nie eine Fach-ID, nur das Kürzel („LA", „SN").
    Das echte Kürzel steht im payload_json der Stunde (su[0].name); ohne diesen
    Weg stünde Latein zweimal auf der Liste, einmal als „LATEIN" und einmal als
    „LA". Ein selbst gepflegter Alias hat Vorrang.
    """
    found: dict[str, str] = {}
    for row in lessons:
        name = (row.get("subject_name") or "").strip()
        short = (_subject_short_from_payload(row.get("payload_json")) or "").strip()
        if name and short:
            found.setdefault(short.casefold(), name)
    return found


def _aliases(account_id: int) -> dict[str, str]:
    with closing(webapp_conn()) as conn:
        have = {r[1] for r in conn.execute("PRAGMA table_info(subject_aliases)")}
        if not {"alias", "subject_name"} <= have:
            return {}
        return {(r[0] or "").strip().casefold(): r[1] for r in conn.execute(
            "SELECT alias,subject_name FROM subject_aliases WHERE account_id=?", (account_id,)) if r[0] and r[1]}


def _sources(account_id: int) -> tuple[list[dict], str]:
    """Alle genannten Stellen des laufenden Schuljahres, nach Fach."""
    day = today_local()
    with closing(history_conn()) as conn:
        start = school_start(conn, account_id, day)
        lessons = rows(conn, "lessons",
                       "id date subject_name subject_untis_id teacher_untis_id code lstext lstext_manual_override "
                       "payload_json is_supervision_guess supervision_manual_override",
                       account_id, "AND date>=? AND date<=? ORDER BY date", (start, day.isoformat()))
        homework = rows(conn, "homework", "id subject_name text assigned_date",
                        account_id, "AND assigned_date>=? ORDER BY assigned_date", (start,))
    hidden = hidden_keys(account_id)
    short_to_name = subject_map(lessons) | _aliases(account_id)

    entries = []
    for row in lessons:
        if lesson_is_hidden(row, hidden) or str(row.get("code") or "").casefold() == "cancelled":
            continue
        override = row.get("supervision_manual_override")
        if override if override is not None else row.get("is_supervision_guess"):
            continue
        text = row.get("lstext_manual_override") or row.get("lstext") or ""
        entries.append(((row.get("subject_name") or "").strip(), row["date"], text))
    for row in homework:
        written = (row.get("subject_name") or "").strip()
        entries.append((short_to_name.get(written.casefold(), written),
                        row.get("assigned_date") or "", row.get("text") or ""))

    seen: set[tuple] = set()
    by_subject: dict[str, dict] = {}
    for subject, when, text in entries:
        text = (text or "").strip()
        if not text or not when or not subject:
            continue
        key = (subject, when, text)
        if key in seen:
            continue
        seen.add(key)
        for cite in citations(text):
            bucket = by_subject.setdefault(subject, {"subject": subject, "parts": {}})
            part = bucket["parts"].setdefault(
                (cite["label"], cite["kind"]),
                {"label": cite["label"], "kind": cite["kind"], "pages": {}})
            for page in cite["pages"]:
                entry = part["pages"].setdefault(page, {"page": page, "dates": set(), "quote": "", "quote_date": ""})
                entry["dates"].add(when)
                if when >= entry["quote_date"]:
                    entry["quote_date"], entry["quote"] = when, text[:220]
    return list(by_subject.values()), start


def ledger(account_id: int) -> dict:
    """Die Einkaufsliste: was genannt wurde, was da ist, was fehlt."""
    found, start = _sources(account_id)
    have, shelf = _material_pages(account_id), _shelf(account_id)
    subjects = []
    for bucket in found:
        subject = bucket["subject"]
        folded = subject.casefold()
        digital_book = folded in shelf
        scanned_pages = have.get(folded, set())
        missing, digital, scanned = [], 0, 0
        for part in bucket["parts"].values():
            gaps = []
            for page in sorted(part["pages"]):
                entry = part["pages"][page]
                if part["kind"] == "book" and digital_book:
                    digital += 1
                elif page in scanned_pages:
                    scanned += 1
                else:
                    gaps.append(entry)
            if gaps:
                newest = max(gaps, key=lambda e: e["quote_date"])
                missing.append({
                    "label": part["label"],
                    "kind": part["kind"],
                    "pages": [e["page"] for e in gaps],
                    "pages_label": page_list([e["page"] for e in gaps]),
                    "quote": newest["quote"],
                    "last_date": newest["quote_date"],
                    "mentions": sum(len(e["dates"]) for e in gaps),
                })
        total = digital + scanned + sum(len(m["pages"]) for m in missing)
        subjects.append({"subject": subject, "digital": digital, "scanned": scanned,
                         "missing": sorted(missing, key=lambda m: (-len(m["pages"]), m["label"])),
                         "missing_count": sum(len(m["pages"]) for m in missing), "total": total,
                         "has_book": digital_book})
    subjects.sort(key=lambda s: (-s["missing_count"], s["subject"]))
    return {"since": start, "subjects": subjects,
            "missing_total": sum(s["missing_count"] for s in subjects)}


def page_list(pages: list[int]) -> str:
    """6, 7, 8 und 12 statt einer langen Aufzählung."""
    spans, run = [], []
    for page in sorted(set(pages)):
        if run and page == run[-1] + 1:
            run.append(page)
        else:
            if run:
                spans.append(run)
            run = [page]
    if run:
        spans.append(run)
    parts = [str(s[0]) if len(s) == 1 else f"{s[0]}–{s[-1]}" for s in spans]
    if len(parts) == 1:
        return f"S. {parts[0]}"
    return "S. " + ", ".join(parts[:-1]) + " und " + parts[-1]
