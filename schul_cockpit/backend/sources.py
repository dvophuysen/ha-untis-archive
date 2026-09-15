"""Welche Quellen der Unterricht nennt — und welche davon noch fehlen.

Die Lehrkräfte schreiben die Stelle im Buch meistens selbst dazu: „TB S. 13
Aufg. C, AH S. 7", „#cda, p. 28", „Arbeitsheft S. 85, Aufg. 5". Daraus lässt
sich ohne KI eine Liste der Quellen bauen, auf die sich der Stoff stützt.

Ein Teil davon liegt digital im Medienregal und braucht niemanden. Der Rest
existiert nur auf Papier: Arbeitshefte, Arbeitsblätter, eigene Mitschriften.
Genau die fehlen der App, wenn sie eine Lernkarte oder eine Übungsklausur auf
den tatsächlichen Stoff stützen soll, statt etwas Ähnliches zu erfinden.

Jede genannte Stelle wird an ihren Untis-Eintrag gebunden (`source_links`)
und mit dem Material verknüpft, das sie belegt: eine abgerufene Buchseite,
ein Foto aus der Ablage. Was weder da ist noch geholt werden kann, steht auf
der Einkaufsliste. Geholt wird in `source_collector`; hier wird gebunden,
abgeglichen und gerechnet.
"""

from __future__ import annotations

import re
from contextlib import closing
from datetime import timedelta

from .courses import hidden_keys, lesson_is_hidden
from .db import history_conn, webapp_conn
from .learning import now_iso, today_local
from .mentor_context import rows, school_start
from .queries import _subject_short_from_payload

import logging

log = logging.getLogger("schul_cockpit.sources")

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


def mentions(account_id: int) -> tuple[list[dict], str]:
    """Jeder Stunden- und Hausaufgabentext des Schuljahres, mit Fach und Tag."""
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

    found = []
    for row in lessons:
        if lesson_is_hidden(row, hidden) or str(row.get("code") or "").casefold() == "cancelled":
            continue
        override = row.get("supervision_manual_override")
        if override if override is not None else row.get("is_supervision_guess"):
            continue
        text = (row.get("lstext_manual_override") or row.get("lstext") or "").strip()
        subject = (row.get("subject_name") or "").strip()
        if text and subject and row.get("date"):
            found.append({"kind": "lesson", "id": row["id"], "subject": subject, "date": row["date"], "text": text})
    for row in homework:
        written = (row.get("subject_name") or "").strip()
        subject = short_to_name.get(written.casefold(), written)
        text = (row.get("text") or "").strip()
        if text and subject and row.get("assigned_date"):
            found.append({"kind": "homework", "id": row["id"], "subject": subject,
                          "date": row["assigned_date"], "text": text})
    return found, start


def sync_links(account_id: int) -> dict:
    """Die Stellen aus den Untis-Texten in source_links binden.

    Ein Eintrag kann nachträglich geändert werden; was in diesem Durchlauf
    nicht mehr genannt wird, verschwindet. Status und Versuche einer weiter
    genannten Stelle bleiben erhalten.
    """
    found, start = mentions(account_id)
    stamp = now_iso()
    count = 0
    with closing(webapp_conn()) as conn, conn:
        for entry in found:
            for cite in citations(entry["text"]):
                for page in cite["pages"]:
                    conn.execute(
                        "INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,"
                        "part_kind,page,quote,synced_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(account_id,entry_kind,entry_id,part_kind,part_label,page) DO UPDATE SET "
                        "entry_date=excluded.entry_date,subject_name=excluded.subject_name,quote=excluded.quote,"
                        "synced_at=excluded.synced_at",
                        (account_id, entry["kind"], entry["id"], entry["date"], entry["subject"],
                         cite["label"] or "Unbekannte Quelle", cite["kind"] or "unknown", page,
                         entry["text"][:220], stamp, stamp))
                    count += 1
    with closing(webapp_conn()) as conn, conn:
        gone = conn.execute("DELETE FROM source_links WHERE account_id=? AND synced_at<? AND entry_kind!='chapter'",
                            (account_id, stamp)).rowcount
    # Die Kapitelregel hängt an den eben gebundenen Stellen und trägt
    # denselben Zeitstempel, damit ihre Zeilen den Abgleich überleben. Was
    # kein Eintrag mehr anschneidet, fällt danach weg.
    from .book_structure import expand
    try:
        count += expand(account_id, stamp)
    except Exception:
        log.warning("Kapitelregel für Konto %s ausgesetzt", account_id, exc_info=True)
    with closing(webapp_conn()) as conn, conn:
        gone += conn.execute("DELETE FROM source_links WHERE account_id=? AND synced_at<?",
                             (account_id, stamp)).rowcount
    return {"since": start, "links": count, "removed": gone}


def _scanned_pages(account_id: int) -> dict[str, dict[int, int]]:
    """Welche Seiten je Fach ein Foto oder Scan aus der Ablage belegt."""
    have: dict[str, dict[int, int]] = {}
    with closing(webapp_conn()) as conn:
        for row in conn.execute(
            "SELECT id,subject_name,title,summary,content_text FROM materials "
            "WHERE account_id=? AND hidden=0 AND origin!='book_fetch'", (account_id,)):
            subject = (row["subject_name"] or "").strip().casefold()
            text = " ".join(filter(None, (row["title"], row["summary"], row["content_text"])))
            pages = have.setdefault(subject, {})
            for cite in citations(text):
                for page in cite["pages"]:
                    pages.setdefault(page, row["id"])
    return have


def _book_pages(account_id: int) -> dict[str, dict[int, dict]]:
    """Welche Buchseiten je Fach abgerufen im Bestand liegen, mit Prüfstand."""
    have: dict[str, dict[int, dict]] = {}
    with closing(webapp_conn()) as conn:
        for row in conn.execute(
            "SELECT id,subject_name,source_book,source_page,page_check,fits_quote,analysis_state FROM materials "
            "WHERE account_id=? AND hidden=0 AND origin='book_fetch' AND source_page IS NOT NULL", (account_id,)):
            subject = (row["subject_name"] or "").strip().casefold()
            have.setdefault(subject, {})[row["source_page"]] = dict(row)
    return have


def _shelf(account_id: int) -> dict[str, dict]:
    """Je Fach das digitale Buch im Regal und der nachgewiesene Zugriff."""
    with closing(webapp_conn()) as conn:
        have = {r[1] for r in conn.execute("PRAGMA table_info(digital_textbook_catalog)")}
        if "subject_name" not in have:
            return {}
        books = {}
        for r in conn.execute("SELECT title,subject_name FROM digital_textbook_catalog WHERE account_id=?", (account_id,)):
            if r["subject_name"]:
                books.setdefault(r["subject_name"].strip().casefold(), {"title": r["title"], "access": None, "attempts": 0})
        for r in conn.execute("SELECT book_title,status,page,checked_at,detail,toc_state FROM digital_textbook_access WHERE account_id=?",
                              (account_id,)):
            for book in books.values():
                if book["title"] == r["book_title"]:
                    book["access"] = {"status": r["status"], "page": r["page"], "checked_at": r["checked_at"],
                                      "detail": r["detail"], "toc_state": r["toc_state"]}
    return books


def subject_habits(links: list[dict]) -> dict[str, str]:
    """Welchen Buchteil eine Lehrkraft nennt, wenn sie einen nennt.

    Ab drei ausdrücklichen Angaben, von denen vier Fünftel auf denselben
    Teil zeigen, gilt der für die Stellen ohne Buchteil im selben Fach.
    """
    counts: dict[str, dict[str, int]] = {}
    for link in links:
        if link["entry_kind"] == "chapter" or link["part_kind"] == "unknown":
            continue
        bucket = counts.setdefault(link["subject_name"].casefold(), {})
        bucket[link["part_kind"]] = bucket.get(link["part_kind"], 0) + 1
    habits = {}
    for subject, bucket in counts.items():
        total = sum(bucket.values())
        kind, n = max(bucket.items(), key=lambda kv: kv[1])
        if total >= 3 and n / total >= 0.8:
            habits[subject] = kind
    return habits


def refresh_status(account_id: int) -> None:
    """Jede gebundene Stelle mit dem Bestand abgleichen und ihren Stand setzen.

    digital: die Buchseite liegt abgerufen im Bestand. scanned: ein Foto aus
    der Ablage nennt die Seite. pending: Buchseite, die noch geholt wird.
    unavailable: das digitale Buch liefert nichts Lesbares. paper: existiert
    nur auf Papier oder ist nicht das Schulbuch — muss fotografiert werden.
    """
    scanned, books, shelf = _scanned_pages(account_id), _book_pages(account_id), _shelf(account_id)
    stamp = now_iso()
    with closing(webapp_conn()) as conn, conn:
        links = [dict(r) for r in conn.execute("SELECT * FROM source_links WHERE account_id=?", (account_id,))]
        habits = subject_habits(links)
        for link in links:
            folded = link["subject_name"].casefold()
            page = link["page"]
            status, detail, material = "paper", None, None
            book = shelf.get(folded)
            stored = books.get(folded, {}).get(page)
            photo = scanned.get(folded, {}).get(page)
            habit = habits.get(folded)
            if link["part_kind"] == "unknown" and habit in ("workbook", "worksheet") and not (
                    stored and stored.get("fits_quote") == "ja"):
                # Schreibt die Lehrkraft sonst immer „AH“, ist ein nacktes
                # „S. 64“ das Arbeitsheft, nicht das Schulbuch.
                status, detail = ("scanned", None) if photo else ("paper", "gewohnheit")
                material = photo
            elif link["part_kind"] in ("book", "unknown"):
                if stored and stored.get("page_check") not in ("mismatch", "blank") and not (
                        link["part_kind"] == "unknown" and stored.get("fits_quote") == "nein"):
                    # Belegt: Seitenzahl abgelesen und Inhalt passt zum Zitat.
                    # Plausibel: gelesen, aber ohne bestätigten Bezug.
                    # Ungeprüft: liegt da, die KI hat sie noch nicht gelesen.
                    status, material = "digital", stored["id"]
                    if stored.get("page_check") == "ok" and stored.get("fits_quote") == "ja":
                        detail = "belegt"
                    elif stored.get("analysis_state") == "ready":
                        detail = "plausibel"
                    else:
                        detail = "ungeprüft"
                elif stored and link["part_kind"] == "unknown" and stored.get("fits_quote") == "nein":
                    status, detail = "paper", "passt_nicht"
                elif photo:
                    status, material = "scanned", photo
                elif not book:
                    status, detail = "paper", "kein_buch"
                elif (book.get("access") or {}).get("status") in ("blank", "viewer_error") and link["attempts"] >= 2:
                    status, detail = "unavailable", (book["access"] or {}).get("status")
                else:
                    status = "pending"
            elif photo:
                status, material = "scanned", photo
            if (status, detail, material) != (link["status"], link["detail"], link["material_id"]) or (
                    book and link["book_title"] != book["title"]):
                conn.execute("UPDATE source_links SET status=?,detail=?,material_id=?,book_title=?,updated_at=? WHERE id=?",
                             (status, detail, material, book["title"] if book else None, stamp, link["id"]))


def ledger(account_id: int) -> dict:
    """Die Bilanz je Fach: was da ist, was geholt wird, was fotografiert werden muss."""
    sync = sync_links(account_id)
    refresh_status(account_id)
    shelf = _shelf(account_id)
    with closing(webapp_conn()) as conn:
        links = [dict(r) for r in conn.execute(
            "SELECT * FROM source_links WHERE account_id=? ORDER BY subject_name,part_kind,part_label,page", (account_id,))]
        stored = {r["source_book"]: r["n"] for r in conn.execute(
            "SELECT source_book, COUNT(*) AS n FROM materials WHERE account_id=? AND origin='book_fetch' AND hidden=0 "
            "GROUP BY source_book", (account_id,))}
    by_subject: dict[str, dict] = {}
    for link in links:
        bucket = by_subject.setdefault(link["subject_name"], {
            "subject": link["subject_name"], "digital": set(), "scanned": set(), "pending": set(),
            "groups": {}})
        # Dieselbe Seite als „Schulbuch" und als „Unbekannte Quelle" genannt
        # ist eine Seite, nicht zwei.
        key = link["page"]
        if link["status"] == "digital":
            bucket["digital"].add(key)
        elif link["status"] == "scanned":
            bucket["scanned"].add(key)
        elif link["status"] == "pending":
            bucket["pending"].add(key)
        else:
            reason = link["detail"] if link["status"] == "paper" and link["detail"] in ("passt_nicht", "gewohnheit") else link["status"]
            group = bucket["groups"].setdefault((link["part_label"], link["part_kind"], reason), {
                "label": link["part_label"], "kind": link["part_kind"], "reason": reason, "pages": {}})
            entry = group["pages"].setdefault(link["page"], {"page": link["page"], "dates": set(), "quote": "", "quote_date": ""})
            entry["dates"].add(link["entry_date"])
            if link["entry_date"] >= entry["quote_date"]:
                entry["quote_date"], entry["quote"] = link["entry_date"], link["quote"]

    subjects = []
    for bucket in by_subject.values():
        missing = []
        for group in bucket["groups"].values():
            gaps = list(group["pages"].values())
            newest = max(gaps, key=lambda e: e["quote_date"])
            missing.append({
                "label": group["label"], "kind": group["kind"], "reason": group["reason"],
                "pages": sorted(e["page"] for e in gaps),
                "pages_label": page_list([e["page"] for e in gaps]),
                "quote": newest["quote"], "last_date": newest["quote_date"],
                "mentions": sum(len(e["dates"]) for e in gaps),
            })
        book = shelf.get(bucket["subject"].casefold())
        missing_count = sum(len(m["pages"]) for m in missing)
        chapters = []
        if book:
            from .book_structure import overview
            try:
                chapters = overview(account_id, book["title"], bucket["subject"])
            except Exception:
                log.warning("Kapitelübersicht für %s nicht berechenbar", bucket["subject"], exc_info=True)
        subjects.append({
            "chapters": chapters,
            "subject": bucket["subject"],
            "digital": len(bucket["digital"]), "scanned": len(bucket["scanned"]), "pending": len(bucket["pending"]),
            "pending_pages": sorted(bucket["pending"]),
            "missing": sorted(missing, key=lambda m: (-len(m["pages"]), m["label"])),
            "missing_count": missing_count,
            "total": len(bucket["digital"]) + len(bucket["scanned"]) + len(bucket["pending"]) + missing_count,
            "has_book": bool(book),
            "book_access": (book or {}).get("access"),
        })
    subjects.sort(key=lambda s: (-s["missing_count"], -s["pending"], s["subject"]))
    books = [{"title": book["title"], "subject": subject, "pages_stored": stored.get(book["title"], 0),
              "access": book.get("access")} for subject, book in sorted(shelf.items())]
    return {"since": sync["since"], "subjects": subjects,
            "missing_total": sum(s["missing_count"] for s in subjects),
            "pending_total": sum(s["pending"] for s in subjects),
            "books": books}


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


def photo_requests(account_id: int, exams: list[dict], day: str, days_ahead: int = 14, limit: int = 3) -> list[dict]:
    """Was vor einer anstehenden Arbeit noch fotografiert werden müsste.

    Nur bei anstehender Arbeit, höchstens drei Bitten, konkret mit Heft, Seite
    und dem Unterrichtszitat. Ohne Arbeit wird nichts eingefordert; die Liste
    steht dann nur auf der Materialseite.
    """
    from datetime import date, timedelta
    horizon = (date.fromisoformat(day) + timedelta(days=days_ahead)).isoformat()
    soon = {}
    for exam in exams or []:
        subject = (exam.get("subject_name") or "").strip()
        when = (exam.get("date") or exam.get("start_date") or "")[:10]
        if subject and day <= when <= horizon:
            soon.setdefault(subject.casefold(), (subject, when))
    if not soon:
        return []
    with closing(webapp_conn()) as conn:
        links = [dict(r) for r in conn.execute(
            "SELECT subject_name,part_label,part_kind,page,quote,entry_date,detail FROM source_links "
            "WHERE account_id=? AND status='paper' AND entry_kind IN ('lesson','homework') ORDER BY entry_date DESC",
            (account_id,))]
    groups: dict[tuple, dict] = {}
    for link in links:
        hit = soon.get(link["subject_name"].casefold())
        if not hit:
            continue
        subject, when = hit
        group = groups.setdefault((subject, link["part_label"]), {
            "subject": subject, "exam_date": when, "label": link["part_label"], "kind": link["part_kind"],
            "pages": set(), "quote": link["quote"], "quote_date": link["entry_date"]})
        group["pages"].add(link["page"])
    out = []
    for group in sorted(groups.values(), key=lambda g: (g["exam_date"], -len(g["pages"]))):
        out.append({**group, "pages": sorted(group["pages"]), "pages_label": page_list(sorted(group["pages"]))})
    return out[:limit]


# --- Quellen im Text sichtbar machen -------------------------------------------
# Überall, wo ein Untis-Text steht, soll die genannte Stelle ein Link zum
# Material sein, in der Farbe ihres Stands: ready (liegt vor und ist
# ausgewertet), pending (wird geholt oder gelesen), missing (liegt nicht vor).

_TAG = re.compile(r"\[([A-Za-zÄÖÜäöüß]{1,5})(\d+)\]")


def segments(text: str) -> list[dict]:
    """Den Text in Stücke zerlegen: Fließtext und Seitenangaben mit Buchteil."""
    text = text or ""
    out: list[dict] = []
    pos = 0
    for hit in PAGE.finditer(text):
        if hit.start() > pos:
            out.append({"text": text[pos:hit.start()]})
        first = int(hit.group(1))
        last = int(hit.group(2)) if hit.group(2) else first
        if last < first or last - first > 30:
            last = first
        label, kind = part_of(text[:hit.start()])
        out.append({"text": text[hit.start():hit.end()], "pages": list(range(first, last + 1)),
                    "label": label or "Unbekannte Quelle", "kind": kind or "unknown"})
        pos = hit.end()
    if pos < len(text):
        out.append({"text": text[pos:]})
    return out


def _state_of(link: dict | None, analysis: dict[int, str]) -> str | None:
    if not link:
        return None
    if link["status"] in ("digital", "scanned"):
        return "ready" if analysis.get(link["material_id"]) == "ready" else "pending"
    if link["status"] == "pending":
        return "pending"
    return "missing"


def _worst(states: list[str | None]) -> str | None:
    for state in ("missing", "pending", "ready"):
        if state in states:
            return state
    return None


def _decorate(text: str, links: list[dict], analysis: dict[int, str]) -> tuple[list[dict], str | None, list[int]]:
    """Segmente mit Stand und Material versehen; dazu der Gesamtstand."""
    by_page: dict[tuple[str, int], dict] = {}
    for link in links:
        by_page.setdefault((link["part_kind"], link["page"]), link)
    states: list[str | None] = []
    materials: list[int] = []
    out = []
    for seg in segments(text):
        if "pages" not in seg:
            out.append(seg)
            continue
        page_states = []
        page_materials = []
        for page in seg["pages"]:
            link = by_page.get((seg["kind"], page)) or by_page.get(("unknown", page)) or by_page.get(("book", page))
            state = _state_of(link, analysis)
            page_states.append(state)
            if link and link.get("material_id"):
                page_materials.append(link["material_id"])
        seg["state"] = _worst(page_states)
        seg["material_id"] = page_materials[0] if page_materials else None
        seg["material_ids"] = page_materials
        materials.extend(m for m in page_materials if m not in materials)
        states.append(seg["state"])
        out.append(seg)
    return out, _worst(states), materials


def _analysis_states(conn, material_ids: list[int]) -> dict[int, str]:
    if not material_ids:
        return {}
    marks = ",".join("?" * len(material_ids))
    return {r["id"]: r["analysis_state"] for r in conn.execute(
        f"SELECT id,analysis_state FROM materials WHERE id IN ({marks})", tuple(material_ids))}


def annotate_lessons(account_id: int, lessons: list[dict], key: str = "lstext", id_key: str = "id") -> None:
    """Jeder Stunde ihre Textsegmente mit Quellenstand anhängen."""
    ids = [l[id_key] for l in lessons if l.get(key)]
    if not ids:
        return
    marks = ",".join("?" * len(ids))
    with closing(webapp_conn()) as conn:
        links = [dict(r) for r in conn.execute(
            f"SELECT entry_id,part_kind,page,status,detail,material_id FROM source_links "
            f"WHERE account_id=? AND entry_kind='lesson' AND entry_id IN ({marks})", (account_id, *ids))]
        analysis = _analysis_states(conn, [l["material_id"] for l in links if l["material_id"]])
    by_lesson: dict[int, list[dict]] = {}
    for link in links:
        by_lesson.setdefault(link["entry_id"], []).append(link)
    for lesson in lessons:
        if not lesson.get(key):
            continue
        segs, state, _ = _decorate(lesson[key], by_lesson.get(lesson[id_key], []), analysis)
        lesson[f"{key}_segments"] = segs
        lesson["source_state"] = state


_META_LINE = re.compile(r"^\s*(gegeben\s+am|f(?:ä|ae)llig(?:\s+bis)?)\s*:", re.I)


def task_text(task: dict) -> str:
    """Der Auftrag einer Aufgabe. Aus Untis kommt er in den Notizen, mit
    Kennung und Datumszeilen; der Titel ist dort nur das Fach."""
    kept = []
    for raw in (task.get("notes") or "").splitlines():
        line = raw.strip()
        if not line or _META_LINE.match(line) or _TAG.fullmatch(line):
            continue
        kept.append(re.sub(r"^\s*#\s?", "", raw).strip())
    body = "\n".join(kept).strip()
    return body or (task.get("title") or "").strip()


def _plain(text: str) -> str:
    return " ".join(re.sub(r"(^|\s)#", r"\1", text or "").split()).casefold()


def homework_for_task(conn, account_id: int, task: dict) -> int | None:
    """Die Untis-Hausaufgabe hinter einer Aufgabe: über die Kennung in den
    Notizen, sonst über denselben Wortlaut."""
    tag = _TAG.search(task.get("notes") or "")
    columns = {r[1] for r in conn.execute("PRAGMA table_info(homework)")}
    if tag and "untis_homework_id" in columns:
        row = conn.execute("SELECT id FROM homework WHERE account_id=? AND untis_homework_id=?",
                           (account_id, int(tag.group(2)))).fetchone()
        if row:
            return row["id"]
    if "text" not in columns:
        return None
    body = _plain(task_text(task))
    if not body:
        return None
    for row in conn.execute("SELECT id,text FROM homework WHERE account_id=? ORDER BY assigned_date DESC LIMIT 400",
                            (account_id,)):
        if _plain(row["text"]) == body:
            return row["id"]
    return None


def annotate_tasks(account_id: int, tasks: list[dict]) -> None:
    """Jeder Aufgabe ihre Textsegmente, den Quellenstand und die Materialien
    anhängen: die Buchseiten und Fotos zu den genannten Stellen sowie alles,
    was ausdrücklich an die Aufgabe gehängt wurde."""
    if not tasks:
        return
    with closing(history_conn()) as hconn:
        homework_ids = {t["id"]: homework_for_task(hconn, account_id, t) for t in tasks}
    with closing(webapp_conn()) as conn:
        hw_ids = [h for h in homework_ids.values() if h]
        links: list[dict] = []
        if hw_ids:
            marks = ",".join("?" * len(hw_ids))
            links = [dict(r) for r in conn.execute(
                f"SELECT entry_id,part_kind,page,status,detail,material_id FROM source_links "
                f"WHERE account_id=? AND entry_kind='homework' AND entry_id IN ({marks})", (account_id, *hw_ids))]
        task_ids = [t["id"] for t in tasks]
        marks = ",".join("?" * len(task_ids))
        attached: dict[int, list[int]] = {}
        for r in conn.execute(
                f"SELECT l.material_id,l.target_id FROM material_links l JOIN materials m ON m.id=l.material_id "
                f"WHERE l.kind='task' AND l.target_id IN ({marks}) AND m.account_id=? AND m.hidden=0",
                (*task_ids, account_id)):
            attached.setdefault(r["target_id"], []).append(r["material_id"])
        wanted = {l["material_id"] for l in links if l["material_id"]} | {m for ms in attached.values() for m in ms}
        analysis = _analysis_states(conn, list(wanted))
        details = {}
        if wanted:
            marks = ",".join("?" * len(wanted))
            details = {r["id"]: dict(r) for r in conn.execute(
                f"SELECT id,title,kind,mime_type,analysis_state,summary,source_book,source_page,origin FROM materials "
                f"WHERE id IN ({marks})", tuple(wanted))}
    by_homework: dict[int, list[dict]] = {}
    for link in links:
        by_homework.setdefault(link["entry_id"], []).append(link)
    for task in tasks:
        hw = homework_ids.get(task["id"])
        body = task_text(task)
        segs, state, materials = _decorate(body, by_homework.get(hw, []) if hw else [], analysis)
        for extra in attached.get(task["id"], []):
            if extra not in materials:
                materials.append(extra)
        task["text"] = body
        task["text_segments"] = segs
        task["title_segments"] = segs if body == (task.get("title") or "").strip() else None
        task["source_state"] = state
        task["homework_id"] = hw
        task["materials"] = [details[m] for m in materials if m in details]
