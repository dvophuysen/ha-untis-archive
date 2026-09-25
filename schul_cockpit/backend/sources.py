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
from .materials import printed_list
from .mentor_context import rows, school_start
from .queries import _subject_short_from_payload
from .subject_names import key as subject_key, label as subject_label

import logging

log = logging.getLogger("schul_cockpit.sources")

# Wie eine Quelle geschrieben wird und was sie ist. „cda" ist bei Spanisch das
# Cuaderno de actividades. Latein hat zwei Bücher: den Textband („TB") und
# den Begleitband („BB") mit Wortschatz und Grammatik; „Schulbuch" allein
# wäre dort zu grob, eine Seite 13 gibt es in beiden. Die Zuordnung ist eine
# Annahme; sie steht in der Anzeige, damit sie widersprochen werden kann.
PARTS: list[tuple[str, str, str]] = [
    # (Muster, Anzeigename, Art)
    (r"begleitband", "Begleitband", "book"),
    (r"textband", "Textband", "book"),
    # „TB" heißt im Englischen Text Book, also das Schulbuch. Nur in Latein ist
    # es der Textband; das steht in SUBJECT_PARTS und geht hier vor (D114).
    (r"lehrbuch|schulbuch|kursbuch|textbook|\bSB\b|\bTB\b|\blibro\b|\bbuch\b", "Schulbuch", "book"),
    (r"vocabulario|wordbank|wortschatzteil", "Schulbuch, Vokabelteil", "book"),
    # „WB" ist das Workbook, also das Arbeitsheft.
    (r"arbeitsheft|\bA-?Heft\b|\bAH\b|workbook|\bWB\b|cuaderno|\bcda\b|übungsheft|uebungsheft|arbeitsbuch", "Arbeitsheft", "workbook"),
    (r"grammatikheft|grammatisches beiheft|beiheft", "Grammatikheft", "workbook"),
    (r"arbeitsblatt|\bAB\b|handout|merkblatt|kopie", "Arbeitsblatt", "worksheet"),
]
# Kürzel, die je Fach etwas anderes bedeuten. Sie gelten vor der allgemeinen
# Tabelle. Latein hat zwei Bücher, Textband („TB") und Begleitband („BB"); im
# Englischen ist „TB" das Text Book und „BB" nichts Bekanntes (D114).
# In den modernen Fremdsprachen steht der Wortschatz im Anhang des Schulbuchs,
# und „Voc." ist die übliche Kurzform dafür. In Latein wäre es der Begleitband,
# ein eigenes Buch — dort bleibt die Kurzform lieber unbestimmt, als die falsche
# Seite zu belegen (D117).
_VOC = (r"vocabulary|\bvoc\b", "Schulbuch, Vokabelteil", "book")
SUBJECT_PARTS: dict[str, list[tuple[str, str, str]]] = {
    "latein": [(r"\bTB\b", "Textband", "book"), (r"\bBB\b", "Begleitband", "book")],
    "englisch": [_VOC],
    "spanisch": [_VOC],
    "französisch": [_VOC],
    "franzoesisch": [_VOC],
}
# Solange keine Stunde das Kürzel auflöst, steht in einer Hausaufgabe nur „LA".
# Ein Kürzel wird genau verglichen, nie als Teilwort: „la" steckt auch in
# „Klassenlehrerstunde".
SUBJECT_SHORTS = {"la": "latein", "lat": "latein"}
PART_LABELS = [label for _, label, _ in PARTS]
BOOK_LABELS = {label for _, label, kind in PARTS if kind == "book"}
# Ein Buchteil, den es nur als eigenes Buch gibt: Eine Seite des Textbands
# oder des digitalen Schulbuchs belegt keine Begleitband-Seite und umgekehrt.
SEPARATE_BOOKS = {"Begleitband"}


def serves(have: str | None, want: str | None) -> bool:
    """Ob eine Seite mit Buchteil `have` eine genannte Stelle im Teil `want` belegt.

    Gleicher Teil immer. Ohne Angabe auf einer der Seiten gilt das Hauptbuch:
    „Schulbuch", „Textband" und der Vokabelteil sind dasselbe Buch, ein
    nacktes „S. 19" meint es auch. Der Begleitband bleibt für sich.
    """
    have = (have or "").strip()
    want = (want or "").strip()
    unknown = {"", "Unbekannte Quelle"}
    if have == want:
        return True
    if want in unknown:
        # Ein nacktes „S. 10" kann in jedem Buch des Fachs stehen.
        return have in unknown or have in BOOK_LABELS
    if want in SEPARATE_BOOKS or have in SEPARATE_BOOKS:
        return False
    main = unknown | (BOOK_LABELS - SEPARATE_BOOKS)
    return have in main and want in main


def book_serves(book_title: str | None, label: str | None) -> bool:
    """Ob das digitale Buch im Regal die Stelle liefern kann."""
    title = (book_title or "").casefold()
    own = next((part for part in SEPARATE_BOOKS if part.casefold() in title), "")
    return serves(own, label)


# Nur eine ausdrückliche Seitenangabe zählt. Ohne diese Regel wird aus
# „#libro, p. 50 vocabulario 4 b" eine Seite 4, obwohl 4 b die Aufgabe ist.
PAGE = re.compile(r"\b(?:S\.|Seite|(?P<plural>pp\.)|p\.|páginas?|paginas?)\s*(?P<first>\d{1,3})"
                  r"(?:\s*(?:-|–|bis)\s*(?P<last>\d{1,3}))?", re.I)
# „pp. 216/7" heißt im Englischen Seite 216 und 217: Die zweite Zahl ist die
# abgekürzte Folgeseite. Nur nach dem Plural „pp."; hinter „S. 60/1" steht die
# Aufgabe, nicht die nächste Seite (D117).
_SHORT_NEXT = re.compile(r"\s*/\s*(\d{1,3})(?![\w.])")
# Eine Aufzählung hinter der Angabe („S. 10, 11, 14, 15") gehört dazu, solange
# sie aufsteigt und nah bleibt; „S. 12, 3a" ist Seite 12 und Aufgabe 3a.
_MORE = re.compile(r"\s*,\s*(\d{1,3})(?:\s*(?:-|–|bis)\s*(\d{1,3}))?(?![\w.])")


def _span(first: int, last: int | None) -> list[int]:
    last = last if last is not None else first
    if last < first or last - first > 30:
        last = first
    return list(range(first, last + 1))


def page_hits(text: str) -> list[tuple[int, int, list[int]]]:
    """Jede Seitenangabe als (Anfang, Ende, Seiten), Aufzählungen eingeschlossen.

    Eine Spanne über dreißig Seiten ist ein Tippfehler und zählt als ihre
    erste Seite; `wide_spans` sagt, welche Angaben so gekürzt wurden."""
    return [(start, end, pages) for start, end, pages, _ in _hits(text)]


def wide_spans(text: str) -> set[int]:
    return {start for start, _, _, wide in _hits(text) if wide}


def _hits(text: str) -> list[tuple[int, int, list[int], bool]]:
    text = text or ""
    out = []
    for hit in PAGE.finditer(text):
        first = int(hit.group("first"))
        last = int(hit.group("last")) if hit.group("last") else None
        wide = last is not None and (last < first or last - first > 30)
        pages = _span(first, last)
        end = hit.end()
        if hit.group("plural") and last is None:
            # Die abgekürzte Folgeseite: „pp. 216/7" sind 216 und 217.
            short = _SHORT_NEXT.match(text, end)
            if short:
                tail = int(short.group(1))
                whole = first - (first % (10 ** len(short.group(1)))) + tail
                if first < whole <= first + 30:
                    pages = list(range(first, whole + 1))
                    end = short.end()
        while True:
            more = _MORE.match(text, end)
            if not more:
                break
            first = int(more.group(1))
            if first <= pages[-1] or first - pages[-1] > 30:
                break
            pages += _span(first, int(more.group(2)) if more.group(2) else None)
            end = more.end()
        out.append((hit.start(), end, pages, wide))
    return out


def _subject_parts(subject: str) -> list[tuple[str, str, str]]:
    """Die Sonderkürzel eines Fachs, auch wenn es „Latein bilingual" heißt."""
    folded = subject_key(subject)
    named = SUBJECT_SHORTS.get(folded)
    if named:
        return SUBJECT_PARTS[named]
    for name, rules in SUBJECT_PARTS.items():
        if name in folded:
            return rules
    return []


def part_of(text: str, subject: str = "") -> tuple[str, str]:
    """Der zuletzt genannte Buchteil vor einer Seitenangabe.

    Mit `subject` gelten zuerst die Kürzel dieses Fachs: „TB" ist in Latein der
    Textband, im Englischen das Text Book, also das Schulbuch (D114)."""
    best = ("", "")
    at = -1
    for pattern, label, kind in _subject_parts(subject) + PARTS:
        for hit in re.finditer(pattern, text, re.I):
            if hit.start() > at:
                at, best = hit.start(), (label, kind)
    return best


# Ein Arbeitsblatt hat keine Seitenzahl und ist trotzdem die Originalquelle
# der Aufgabe („Arbeitsblatt beenden"). Es wird als Seite 0 geführt.
SHEET = re.compile(PARTS[-1][0], re.I)


def sheet_mentions(text: str, subject: str = "") -> list[re.Match]:
    """Arbeitsblätter, die ohne Seitenangabe genannt sind."""
    text = text or ""
    covered = {start for start, _, _ in page_hits(text) if part_of(text[:start], subject)[1] == "worksheet"}
    if covered:
        return []
    return list(SHEET.finditer(text))


def citations(text: str, subject: str = "") -> list[dict]:
    """Jede Seitenangabe mit dem Buchteil, der davor steht, dazu Blätter ohne Seite."""
    found = []
    for start, _, pages in page_hits(text):
        # Der zuletzt genannte Teil gilt weiter: In „Buch, S. 30-32 … Aufgabe 1
        # auf S. 34" gehört auch die 34 ins Buch.
        label, kind = part_of(text[:start], subject)
        found.append({"label": label or "Unbekannte Quelle", "kind": kind or "unknown", "pages": pages})
    if sheet_mentions(text, subject):
        found.append({"label": "Arbeitsblatt", "kind": "worksheet", "pages": [0]})
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
    for row in exam_notices(account_id):
        written = (row["subject_name"] or "").strip()
        subject = short_to_name.get(written.casefold(), written)
        if row["text"] and subject and row["date"] >= start:
            found.append({"kind": "exam_notice", "id": row["id"], "subject": subject,
                          "date": row["date"], "text": row["text"]})
    return found, start


def exam_notices(account_id: int) -> list[dict]:
    """Was die Lehrkraft für die Arbeit angekündigt hat: der abfotografierte
    Zettel mit dem Stoff. Jede Stelle darauf ist eine Quelle wie aus Untis,
    mit Vorrang beim Holen. `verified` sagt, ob ein Elternteil die Lesung
    gegengelesen hat."""
    with closing(webapp_conn()) as conn:
        if "source_label" not in {r[1] for r in conn.execute("PRAGMA table_info(materials)")}:
            return []
        rows = conn.execute(
            "SELECT id,subject_name,title,summary,content_text,document_date,created_at,verified FROM materials "
            "WHERE account_id=? AND hidden=0 AND kind='exam_notice' ORDER BY id", (account_id,)).fetchall()
    return [{"id": r["id"], "subject_name": r["subject_name"], "verified": bool(r["verified"]),
             "date": (r["document_date"] or r["created_at"] or "")[:10],
             "text": " ".join(filter(None, (r["content_text"], r["title"] if not r["content_text"] else None,
                                            r["summary"] if not r["content_text"] else None))).strip()}
            for r in rows]


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
            for cite in citations(entry["text"], entry["subject"]):
                if entry["kind"] == "exam_notice" and cite["kind"] == "worksheet" and cite["pages"] == [0]:
                    # Ein Blatt ohne Seite auf dem Themenzettel ist der Zettel
                    # selbst, kein fehlendes Material (D196). Ein Elternbrief zur
                    # Sprechprüfung ergab sonst „Arbeitsblatt ohne Seitenangabe“.
                    continue
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


def _scanned_pages(account_id: int) -> dict[str, dict[tuple[str, int], int]]:
    """Welche Seiten je Fach ein Foto oder Scan aus der Ablage belegt, mit Buchteil.

    Zuerst zählt, was die Auswertung oder die Einkaufsliste an der Datei
    festgehalten hat (gedruckte Seitenzahl, Buchteil). Nur ohne diese Angabe
    gilt eine Seitenangabe in Titel oder Kurzbeschreibung; der erkannte Text
    zählt nicht, weil ein Verweis „→ S. 12" auf einer Seite 15 keine Seite 12
    belegt.
    """
    have: dict[str, dict[tuple[str, int], int]] = {}
    with closing(webapp_conn()) as conn:
        for row in conn.execute(
            "SELECT id,subject_name,title,summary,source_label,source_page,printed_pages,kind FROM materials "
            "WHERE account_id=? AND hidden=0 AND origin!='book_fetch' AND kind NOT IN ('exam_notice','toc')", (account_id,)):
            subject = (row["subject_name"] or "").strip().casefold()
            pages = have.setdefault(subject, {})
            # Ohne ausdrücklichen Buchteil sagt die Art der Datei, was sie ist.
            label = (row["source_label"] or "").strip() or {"workbook": "Arbeitsheft", "worksheet": "Arbeitsblatt"}.get(row["kind"], "")
            if row["source_page"]:
                # Eine fotografierte Doppelseite belegt beide gedruckten Seiten.
                printed = printed_list(row["printed_pages"])
                for page in [row["source_page"]] + [p for p in printed if abs(p - row["source_page"]) <= 1]:
                    pages.setdefault((label, page), row["id"])
                continue
            text = " ".join(filter(None, (row["title"], row["summary"])))
            for cite in citations(text, row["subject_name"]):
                for page in cite["pages"]:
                    if page:
                        pages.setdefault((label or (cite["label"] if cite["label"] != "Unbekannte Quelle" else ""), page), row["id"])
    return have


def scan_for(scanned: dict[str, dict[tuple[str, int], int]], subject: str, label: str, page: int) -> int | None:
    """Das Foto, das diese Stelle belegt: gleicher Buchteil zuerst, dann was
    das Hauptbuch ebenfalls belegt."""
    candidates = scanned.get(subject.casefold(), {})
    exact = candidates.get((label, page))
    if exact:
        return exact
    for (have, have_page), material_id in candidates.items():
        if have_page == page and serves(have, label):
            return material_id
    return None


def _book_pages(account_id: int) -> dict[str, dict[int, dict]]:
    """Welche Buchseiten je Fach abgerufen im Bestand liegen, mit Prüfstand.

    Eine Doppelseite deckt beide gedruckten Seiten ab: Wer 160/161 bestellt hat,
    hat auch die 161 im Bestand, und sie noch einmal zu bestellen brachte nur
    eine Dublette (D138). Die gedruckte Zahl schlägt dabei die bestellte."""
    have: dict[str, dict[int, dict]] = {}
    with closing(webapp_conn()) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id,subject_name,source_book,source_page,printed_pages,page_check,fits_quote,analysis_state "
            "FROM materials WHERE account_id=? AND hidden=0 AND origin='book_fetch' AND source_page IS NOT NULL",
            (account_id,))]
    for row in rows:
        subject = (row["subject_name"] or "").strip().casefold()
        have.setdefault(subject, {}).setdefault(row["source_page"], row)
    for row in rows:
        subject = (row["subject_name"] or "").strip().casefold()
        for page in printed_list(row["printed_pages"]):
            vorhanden = have[subject].get(page)
            if vorhanden is None or (vorhanden.get("page_check") != "ok" and row.get("page_check") == "ok"):
                have[subject][page] = row
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


# Nur diese Arten sind ein Blatt, das eine Hausaufgabe „Arbeitsblatt“ belegt.
# Eine Mitschrift oder eine eigene Ausarbeitung (notes, own_work) ist das
# Ergebnis einer Hausaufgabe, nicht ihr Blatt; „other“ ist unbestimmt.
SHEET_KINDS = ("worksheet", "handout")


def is_sheet_link(kind: str, relation: str | None) -> bool:
    """Ob eine Verknüpfung sagt: Dieses Material ist das Blatt des Eintrags.
    Ausdrücklich über die Rolle, sonst über die Materialart (D85)."""
    if relation:
        return relation == "blatt"
    return kind in SHEET_KINDS


def _sheet_photos(account_id: int) -> dict:
    """Fotografierte Blätter, die eine Hausaufgabe oder Stunde ausdrücklich
    belegen (D83, D85): über eine Aufgabe (→ ihre Hausaufgabe), eine
    Hausaufgabe oder eine Stunde. Dazu die losen Blätter je Fach mit Datum,
    aus denen nur noch Vorschläge werden, nie eine Bindung.

    Ein Foto, das ein Mensch an einen Eintrag gehängt hat, gehört zu diesem
    Eintrag und zu keinem anderen; es kommt nie in den losen Vorrat. Und es
    belegt seinen Eintrag nur als Blatt, wenn die Rolle oder die Materialart
    ein Blatt sagt, nicht bei der Bearbeitung des Kindes.
    """
    found: dict = {}
    with closing(webapp_conn()) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id,subject_name,kind,document_date,created_at FROM materials WHERE account_id=? AND hidden=0 "
            f"AND origin!='book_fetch' AND kind IN ({','.join('?' * len(SHEET_KINDS))})", (account_id, *SHEET_KINDS))]
        links = [dict(r) for r in conn.execute(
            "SELECT l.material_id,l.kind AS link_kind,l.target_id,l.relation,m.kind FROM material_links l "
            "JOIN materials m ON m.id=l.material_id WHERE l.kind IN ('task','homework','lesson') AND m.account_id=? AND m.hidden=0",
            (account_id,))]
        tasks = {r["id"]: dict(r) for r in conn.execute("SELECT id,title,notes FROM tasks WHERE account_id=?", (account_id,))}
    attached = {link["material_id"] for link in links}
    task_links = [l for l in links if l["link_kind"] == "task" and is_sheet_link(l["kind"], l["relation"])]
    if task_links:
        with closing(history_conn()) as hconn:
            for link in task_links:
                task = tasks.get(link["target_id"])
                if not task:
                    continue
                try:
                    homework = homework_for_task(hconn, account_id, task)
                except Exception:
                    homework = None
                if homework:
                    found.setdefault(("homework", homework), link["material_id"])
    for link in links:
        if link["link_kind"] in ("homework", "lesson") and is_sheet_link(link["kind"], link["relation"]):
            found.setdefault((link["link_kind"], link["target_id"]), link["material_id"])
    for row in rows:
        if row["id"] in attached:
            continue
        day = (row["document_date"] or row["created_at"] or "")[:10]
        found.setdefault(("loose", (row["subject_name"] or "").strip().casefold()), []).append((day, row["id"]))
    return found


SUBJECT_SHORT = {"deutsch": "DE", "englisch": "EN", "mathematik": "MA", "latein": "LA", "spanisch": "SP",
                 "französisch": "FR", "geschichte": "GE", "physik": "PH", "chemie": "CH", "biologie": "BI",
                 "politik": "PO", "erdkunde": "EK", "kunst": "KU", "musik": "MU", "religion": "RE",
                 "sport": "SP", "informatik": "IF"}


def sheet_label(material: dict, entry_date: str | None = None) -> str:
    """Die Kennung eines Blatts: „AB GE 16.09. Lückentext“.

    Sie wird nicht gespeichert, sondern aus Bezug und Material abgeleitet
    (D85). Der Ausgabetag ist das Datum des verknüpften Eintrags, sonst das
    aufgedruckte Datum, sonst der Tag der Aufnahme mit dem Vermerk „ungefähr“."""
    subject = (material.get("subject_name") or "").strip()
    short = SUBJECT_SHORT.get(subject.casefold(), subject[:2].upper() if subject else "")
    day = (entry_date or material.get("document_date") or "")[:10]
    ungefaehr = not day
    if ungefaehr:
        day = (material.get("created_at") or "")[:10]
    stamp = ""
    if len(day) == 10:
        stamp = f"{day[8:10]}.{day[5:7]}."
        if ungefaehr:
            stamp = "ca. " + stamp
    title = (material.get("title") or "").strip()
    parts = ["AB", short, stamp, title]
    return " ".join(x for x in parts if x).strip()


def sheet_for_task(account_id: int, task_id: int) -> dict | None:
    """Das Arbeitsblatt, das ausdrücklich zu dieser Hausaufgabe gehört.

    Nur über einen gesetzten Bezug, nie über Nähe im Datum (D85). Gibt es
    keinen, bekommt der Mentor das auch so gesagt und bittet um ein Foto,
    statt ein fremdes Blatt zu benutzen."""
    if not task_id:
        return None
    with closing(webapp_conn()) as conn:
        row = conn.execute(
            "SELECT m.id,m.title,m.subject_name,m.document_date,m.created_at,m.kind,m.content_text,l.relation "
            "FROM material_links l JOIN materials m ON m.id=l.material_id "
            "WHERE l.kind='task' AND l.target_id=? AND m.account_id=? AND m.hidden=0 "
            "AND (l.relation='blatt' OR m.kind IN ('worksheet','handout')) "
            "ORDER BY (l.relation='blatt') DESC, m.id DESC LIMIT 1", (task_id, account_id)).fetchone()
    if not row:
        return None
    material = dict(row)
    return {"id": material["id"], "kennung": sheet_label(material), "art": material["kind"],
            "text": (material["content_text"] or "")[:4000]}


def sheet_candidates(account_id: int, material: dict, days: int = 14, limit: int = 3) -> list[dict]:
    """Zu welchem Eintrag ein loses Blatt gehören könnte: Hausaufgaben und
    Stunden desselben Fachs, die ein Blatt nennen und noch keins haben, nach
    Nähe zum Datum des Blatts. Ein Vorschlag zum Antippen, keine Bindung (D85)."""
    from datetime import date
    subject = (material.get("subject_name") or "").strip()
    day = (material.get("document_date") or material.get("created_at") or "")[:10]
    if not subject or not day:
        return []
    try:
        anchor = date.fromisoformat(day)
    except ValueError:
        return []
    with closing(webapp_conn()) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT entry_kind,entry_id,entry_date,quote FROM source_links WHERE account_id=? AND page=0 AND status='paper' "
            "AND part_kind='worksheet' AND lower(subject_name)=lower(?) AND entry_kind IN ('homework','lesson')",
            (account_id, subject))]
    out = []
    for row in rows:
        try:
            gap = abs((date.fromisoformat(row["entry_date"][:10]) - anchor).days)
        except ValueError:
            continue
        if gap <= days:
            out.append({"kind": row["entry_kind"], "id": row["entry_id"], "date": row["entry_date"][:10],
                        "quote": row["quote"], "days": gap})
    out.sort(key=lambda c: (c["days"], c["date"]))
    return out[:limit]


def with_subject(account_id: int, task: dict) -> dict:
    """Die Hausaufgabe mit ihrem Fach, so wie der Chat es sieht.

    Aus Untis kommt das Fach oft nur im Titel („DEUTSCH"), das Fachfeld bleibt
    leer. Ohne diesen Schritt fand die Suche nach passendem Material für eine
    solche Aufgabe gar nichts, obwohl der Chat sie längst dem Fach zuordnete.
    """
    try:
        from .subject_names import SubjectCatalog
        return SubjectCatalog(account_id).task(task)
    except Exception:
        return task


def task_candidates(account_id: int, task_id: int, limit: int = 12) -> list[dict]:
    """Bereits abgelegte Materialien, die zu dieser Hausaufgabe passen könnten.

    Der Rückweg zu `sheet_candidates()`: Dort sucht ein loses Blatt seinen
    Eintrag, hier sucht ein Eintrag seine Blätter. Gereiht wird nach Nähe zur
    Aufgabe — zuerst, was eine im Auftrag genannte Stelle wirklich zeigt, dann
    Blätter desselben Fachs aus den Tagen um die Aufgabe, dann der Rest des
    Fachs. Jeder Vorschlag sagt, warum er dasteht; gebunden wird nichts von
    selbst (D85, D106).
    """
    from datetime import date
    from .materials import canonical_subject
    with closing(webapp_conn()) as conn:
        task = conn.execute("SELECT id,title,notes,subject_name,due_date,created_at FROM tasks WHERE id=? AND account_id=?",
                            (task_id, account_id)).fetchone()
        if not task:
            return []
        task = dict(task)
        linked = {r[0] for r in conn.execute(
            "SELECT material_id FROM material_links WHERE kind='task' AND target_id=?", (task_id,))}
    task = with_subject(account_id, task)
    subject = canonical_subject(account_id, task["subject_name"] or "") or (task["subject_name"] or "")
    wanted = citations(task_text(task), task.get("subject_name") or "")
    anchor_day = (task["due_date"] or task["created_at"] or "")[:10]
    with closing(webapp_conn()) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id,title,kind,subject_name,source_label,source_page,printed_pages,document_date,created_at,origin "
            "FROM materials WHERE account_id=? AND hidden=0 AND kind NOT IN ('exam_notice','toc') "
            "AND lower(COALESCE(subject_name,''))=lower(?) ORDER BY id DESC", (account_id, subject))] if subject else []
    out = []
    for row in rows:
        if row["id"] in linked:
            continue
        pages = {row["source_page"]} - {None} | set(printed_list(row["printed_pages"]))
        label = (row["source_label"] or "").strip()
        hit = next((w for w in wanted if pages & set(w["pages"]) and serves(label, w["label"])), None)
        day = (row["document_date"] or row["created_at"] or "")[:10]
        gap = None
        if anchor_day and day:
            try:
                gap = abs((date.fromisoformat(day) - date.fromisoformat(anchor_day)).days)
            except ValueError:
                gap = None
        if hit:
            rank, why = 0, f"zeigt {hit['label']} {page_list(sorted(pages & set(hit['pages'])))}"
        elif row["kind"] in SHEET_KINDS and gap is not None and gap <= 14:
            rank, why = 1, f"Blatt desselben Fachs vom {day}"
        elif row["origin"] == "book_fetch":
            rank, why = 3, f"Buchseite {row['source_page']}" if row["source_page"] else "Buchseite"
        else:
            rank, why = 2, f"gleiches Fach, vom {day}" if day else "gleiches Fach"
        out.append({"material_id": row["id"], "title": row["title"] or "", "kind": row["kind"],
                    "label": label, "page": row["source_page"], "reason": why,
                    "_rank": (rank, gap if gap is not None else 999, -row["id"])})
    out.sort(key=lambda x: x["_rank"])
    for item in out:
        item.pop("_rank")
    return out[:limit]


def solution_for_task(account_id: int, task_id: int) -> dict | None:
    """Die abgelegte Bearbeitung des Kindes zu dieser Hausaufgabe (D123).

    Die Kontrolle fragte bisher immer nach einem Foto, obwohl die bearbeitete
    Seite längst eingelesen war — bei „Ah S. 74" lag Arbeitsheft S. 74 mit den
    Eintragungen des Kindes im Bestand, nur am Thema statt an der Aufgabe.
    Gesucht wird deshalb beides: was an der Aufgabe hängt und was eine im
    Auftrag genannte Stelle zeigt. Eintragungen des Kindes muss es tragen —
    ohne sie ist es die gedruckte Aufgabe, nicht die Lösung. Eine abgerufene
    Buchseite ist nie die Bearbeitung.
    """
    from .materials import canonical_subject
    with closing(webapp_conn()) as conn:
        task = conn.execute("SELECT id,title,notes,subject_name,due_date,created_at FROM tasks WHERE id=? AND account_id=?",
                            (task_id, account_id)).fetchone()
        if not task:
            return None
        task = dict(task)
        linked = {r[0] for r in conn.execute(
            "SELECT material_id FROM material_links WHERE kind='task' AND target_id=?", (task_id,))}
        keys = {r[1] for r in conn.execute("PRAGMA table_info(materials)")}
        if "pupil_entries" not in keys:
            return None
        task = with_subject(account_id, task)
        subject = canonical_subject(account_id, task["subject_name"] or "") or (task["subject_name"] or "")
        rows = [dict(r) for r in conn.execute(
            "SELECT id,title,kind,source_label,source_page,printed_pages,document_date,created_at,origin,"
            "pupil_entries,handwritten FROM materials WHERE account_id=? AND hidden=0 AND analysis_state='ready' "
            "AND COALESCE(origin,'')!='book_fetch' AND kind NOT IN ('exam_notice','toc') "
            "AND lower(COALESCE(subject_name,''))=lower(?) ORDER BY id DESC", (account_id, subject))] if subject else []
    wanted = citations(task_text(task), task.get("subject_name") or "")
    best = None
    for row in rows:
        if not (row["pupil_entries"] or row["handwritten"] or row["kind"] == "own_work"):
            continue
        pages = {row["source_page"]} - {None} | set(printed_list(row["printed_pages"]))
        label = (row["source_label"] or "").strip()
        hit = next((w for w in wanted if pages & set(w["pages"]) and serves(label, w["label"])), None)
        day = (row["document_date"] or row["created_at"] or "")[:10]
        if hit:
            rank, why = (0, f"{hit['label']} {page_list(sorted(pages & set(hit['pages'])))}")
        elif row["id"] in linked:
            rank, why = (1, "hängt an dieser Hausaufgabe")
        else:
            continue
        found = {"material_id": row["id"], "title": row["title"] or "", "kind": row["kind"],
                 "label": label, "page": row["source_page"], "date": day, "reason": why,
                 "linked": row["id"] in linked, "_rank": (rank, -(row["id"]))}
        if best is None or found["_rank"] < best["_rank"]:
            best = found
    if best:
        best.pop("_rank")
    return best


def _sheet_near(sheets: dict, subject: str, entry_date: str, days: int = 5) -> int | None:
    from datetime import date, timedelta
    try:
        anchor = date.fromisoformat(entry_date[:10])
    except ValueError:
        return None
    for day, material_id in sheets.get(("loose", subject), []):
        try:
            if abs((date.fromisoformat(day) - anchor).days) <= days:
                return material_id
        except ValueError:
            continue
    return None


UNKNOWN_PART = "Unbekannte Quelle"


def claim(account_id: int, subject: str, label: str, page: int, material_id: int) -> None:
    """Ein Foto einer Stelle zuordnen und die Stelle sofort als belegt führen."""
    with closing(webapp_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO source_claims(account_id,subject_key,part_label,page,material_id,created_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(account_id,subject_key,part_label,page) DO UPDATE SET material_id=excluded.material_id,"
            "created_at=excluded.created_at",
            (account_id, subject.strip().casefold(), label, page, material_id, now_iso()))
        conn.execute(
            "UPDATE source_links SET status='scanned',detail='foto',material_id=?,updated_at=? "
            "WHERE account_id=? AND lower(subject_name)=lower(?) AND part_label=? AND page=?",
            (material_id, now_iso(), account_id, subject.strip(), label, page))
        # Die Datei weiß danach selbst, welche Seite sie zeigt.
        # „Unbekannte Quelle“ ist kein Buchteil und gehört nicht in die Datei.
        conn.execute("UPDATE materials SET source_label=COALESCE(NULLIF(source_label,''),?),"
                     "source_page=COALESCE(source_page,?),updated_at=? WHERE id=? AND account_id=?",
                     (None if label == UNKNOWN_PART else label, page or None, now_iso(), material_id, account_id))


def _claims(account_id: int) -> dict[tuple, int]:
    with closing(webapp_conn()) as conn:
        return {(r["subject_key"], r["part_label"], r["page"]): r["material_id"] for r in conn.execute(
            "SELECT c.subject_key,c.part_label,c.page,c.material_id FROM source_claims c "
            "JOIN materials m ON m.id=c.material_id AND m.hidden=0 WHERE c.account_id=?", (account_id,))}


# --- „Nicht nötig“ (D196) ------------------------------------------------------
# Ein Elternteil streicht eine fehlende Stelle, und sie kommt nicht wieder: weder
# als fehlend noch in den Summen. Eine Buchseite ist eine Buchseite, auf Dauer.
# Ein Blatt ohne Seite (Seite 0) gilt bis zum Tag der Streichung; ein später
# genanntes Blatt ist ein neues Blatt.

def dismiss(account_id: int, subject: str, label: str, pages: list[int], user_id: int | None, until: str | None = None) -> None:
    stamp = now_iso()
    until = until or today_local().isoformat()
    with closing(webapp_conn()) as conn, conn:
        for page in sorted(set(pages)):
            conn.execute(
                "INSERT INTO source_dismissed(account_id,subject_key,part_label,page,until,dismissed_at,user_id) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(account_id,subject_key,part_label,page) DO UPDATE SET until=MAX(until,excluded.until),"
                "dismissed_at=excluded.dismissed_at,user_id=excluded.user_id",
                (account_id, subject.strip().casefold(), label, page, until, stamp, user_id))


def undismiss(account_id: int, subject: str, label: str, pages: list[int]) -> int:
    with closing(webapp_conn()) as conn, conn:
        return sum(conn.execute("DELETE FROM source_dismissed WHERE account_id=? AND subject_key=? AND part_label=? AND page=?",
                                (account_id, subject.strip().casefold(), label, page)).rowcount for page in set(pages))


def _dismissed(account_id: int) -> dict[tuple, str]:
    with closing(webapp_conn()) as conn:
        return {(r["subject_key"], r["part_label"], r["page"]): r["until"] or "" for r in conn.execute(
            "SELECT subject_key,part_label,page,until FROM source_dismissed WHERE account_id=?", (account_id,))}


def is_dismissed(dismissed: dict[tuple, str], link: dict) -> bool:
    until = dismissed.get(((link.get("subject_name") or "").strip().casefold(), link.get("part_label"), link.get("page")))
    if until is None:
        return False
    return bool(link.get("page")) or (link.get("entry_date") or "") <= until


# --- Woher eine fehlende Stelle kommt (D196) -----------------------------------

def _short(text: str | None, limit: int = 120) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _ddmm(iso: str | None) -> str:
    iso = (iso or "")[:10]
    return f"{iso[8:10]}.{iso[5:7]}." if len(iso) == 10 else ""


def mention_sources(links: list[dict], subject: str, limit: int = 3) -> list[dict]:
    """Die Nennungen hinter einer Stelle: ausdrückliche vor der Kapitelregel,
    die neueste zuerst, je Eintrag einmal."""
    ordered = sorted(sorted(links, key=lambda l: l.get("entry_date") or "", reverse=True),
                     key=lambda l: l.get("entry_kind") == "chapter")
    picked, seen = [], set()
    for link in ordered:
        mark = (link.get("entry_kind"), link.get("entry_id"))
        if mark in seen:
            continue
        seen.add(mark)
        picked.append(link)
        if len(picked) == limit:
            break
    notices = [l["entry_id"] for l in picked if l.get("entry_kind") == "exam_notice"]
    titles: dict[int, str] = {}
    if notices:
        with closing(webapp_conn()) as conn:
            titles = {r[0]: r[1] for r in conn.execute(
                f"SELECT id,title FROM materials WHERE id IN ({','.join('?' * len(notices))})", tuple(notices))}
    name = subject_label(subject)
    out = []
    for link in picked:
        kind, day = link.get("entry_kind"), _ddmm(link.get("entry_date"))
        if kind == "homework":
            label = f"Hausaufgabe {name} vom {day}"
        elif kind == "lesson":
            label = f"Stunde {name} vom {day}"
        elif kind == "exam_notice":
            label = f"{(titles.get(link['entry_id']) or '').strip() or 'Themenzettel'} (abgelegt {day})"
        else:
            label = f"Kapitel aus dem Unterricht (ab {day})"
        # Nur der Zettel und ein Foto haben ein eigenes Ziel; Stunden und
        # Hausaufgaben lassen sich bisher nicht direkt aufrufen.
        material = link["entry_id"] if kind == "exam_notice" else link.get("material_id")
        out.append({"entry_kind": kind, "entry_id": link.get("entry_id"), "date": (link.get("entry_date") or "")[:10],
                    "quote": _short(link.get("quote")), "label": label,
                    "href": f"#/materialien?material={material}" if material else None})
    return out


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
    sheets = _sheet_photos(account_id)
    claims = _claims(account_id)
    stamp = now_iso()
    with closing(webapp_conn()) as conn, conn:
        links = [dict(r) for r in conn.execute("SELECT * FROM source_links WHERE account_id=?", (account_id,))]
        habits = subject_habits(links)
        for link in links:
            folded = link["subject_name"].casefold()
            page = link["page"]
            status, detail, material = "paper", None, None
            claimed = claims.get((folded, link["part_label"], page))
            if claimed:
                # Von Hand zugeordnet schlägt jede Herleitung.
                if ("scanned", "foto", claimed) != (link["status"], link["detail"], link["material_id"]):
                    conn.execute("UPDATE source_links SET status='scanned',detail='foto',material_id=?,updated_at=? WHERE id=?",
                                 (claimed, stamp, link["id"]))
                continue
            book = shelf.get(folded)
            if book and not book_serves(book["title"], link["part_label"]):
                # Das digitale Buch ist ein anderes Buch (Begleitband).
                book = None
            stored = books.get(folded, {}).get(page) if book else None
            photo = scan_for(scanned, folded, link["part_label"], page)
            if page == 0:
                # Nur ein ausdrücklicher Bezug belegt ein Blatt; die Nähe im
                # Datum ist höchstens ein Vorschlag (D85, sheet_candidates).
                photo = sheets.get(("homework", link["entry_id"])) or sheets.get(("lesson", link["entry_id"]))
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
    dismissed = _dismissed(account_id)
    links = [l for l in links if not is_dismissed(dismissed, l)]
    by_subject: dict[str, dict] = {}
    for link in links:
        bucket = by_subject.setdefault(link["subject_name"], {
            "subject": link["subject_name"], "digital": set(), "scanned": set(), "pending": set(),
            "have": [], "groups": {}})
        # Dieselbe Seite als „Schulbuch" und als „Unbekannte Quelle" genannt
        # ist eine Seite, nicht zwei.
        key = link["page"]
        if link["status"] == "digital":
            bucket["digital"].add(key);bucket["have"].append((link["part_label"], key))
        elif link["status"] == "scanned":
            bucket["scanned"].add(key);bucket["have"].append((link["part_label"], key))
        elif link["status"] == "pending":
            bucket["pending"].add(key)
        else:
            reason = link["detail"] if link["status"] == "paper" and link["detail"] in ("passt_nicht", "gewohnheit") else link["status"]
            group = bucket["groups"].setdefault((link["part_label"], link["part_kind"], reason), {
                "label": link["part_label"], "kind": link["part_kind"], "reason": reason, "pages": {}})
            # Ein Blatt (Seite 0) ist je Eintrag ein eigener Posten: „Arbeitsblatt
            # beenden“ vom 16.09. und „AB besprochen“ vom 20.09. sind womöglich
            # zwei Blätter; zugeordnet wird je Eintrag (D85).
            page_key = (0, link["entry_kind"], link["entry_id"]) if link["page"] == 0 else link["page"]
            entry = group["pages"].setdefault(page_key, {"page": link["page"], "dates": set(), "quote": "", "quote_date": "",
                                                         "entry_kind": link["entry_kind"], "entry_id": link["entry_id"]})
            entry["dates"].add(link["entry_date"])
            if link["entry_date"] >= entry["quote_date"]:
                entry["quote_date"], entry["quote"] = link["entry_date"], link["quote"]

    subjects = []
    for bucket in by_subject.values():
        missing = []
        guesser = _book_guesser(account_id, bucket["subject"])
        for group in bucket["groups"].values():
            # Dieselbe Seite unter zwei Bezeichnungen ist eine Seite. „Buch S. 48“
            # und „Schulbuch S. 48“ standen nebeneinander, eine davon galt als da
            # und die andere als fehlend (D99). Was schon vorliegt, fehlt nicht.
            gaps = [e for e in group["pages"].values()
                    if e["page"] == 0 or not any(page == e["page"] and serves(label, group["label"])
                                                 for label, page in bucket["have"])]
            if not gaps:
                continue
            newest = max(gaps, key=lambda e: e["quote_date"])
            guesses = {guesser(e["page"]) for e in gaps} if group["kind"] == "unknown" else set()
            guess = guesses.pop() if len(guesses) == 1 and None not in guesses else None
            missing.append({
                "label": group["label"], "kind": group["kind"], "reason": group["reason"],
                # Ohne Buchteil im Text: das Buch, dessen gerade behandeltes
                # Kapitel die Seite enthält. Eine Vermutung, so benannt; ein
                # Foto des anderen Buchs streicht die Stelle trotzdem.
                "guess": guess,
                "pages": sorted(e["page"] for e in gaps),
                "pages_label": page_list([e["page"] for e in gaps]),
                "quote": newest["quote"], "last_date": newest["quote_date"],
                "mentions": sum(len(e["dates"]) for e in gaps),
                # Je Seite ein Eintrag zum Abhaken: antippen, fotografieren, fertig.
                "items": [{"page": e["page"], "label": page_list([e["page"]]), "quote": e["quote"], "date": e["quote_date"],
                           "entry_kind": e["entry_kind"], "entry_id": e["entry_id"]}
                          for e in sorted(gaps, key=lambda e: (e["page"], e["quote_date"]))],
            })
        book = shelf.get(bucket["subject"].casefold())
        missing_count = sum(len(m["pages"]) for m in missing)
        chapters = []
        from .book_structure import overview, paper_books
        if book:
            try:
                chapters = overview(account_id, book["title"], bucket["subject"])
            except Exception:
                log.warning("Kapitelübersicht für %s nicht berechenbar", bucket["subject"], exc_info=True)
        for paper in paper_books(account_id, bucket["subject"]):
            try:
                chapters += overview(account_id, paper["title"], bucket["subject"], paper["part_label"])
            except Exception:
                log.warning("Kapitelübersicht für %s nicht berechenbar", paper["title"], exc_info=True)
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
    from .book_structure import paper_books, units_of
    books = [{"title": book["title"], "subject": subject, "part_label": "Schulbuch", "pages_stored": stored.get(book["title"], 0),
              "units": units_of(account_id, book["title"]), "access": book.get("access")} for subject, book in sorted(shelf.items())]
    # Papierbücher stehen mit dazu: was von ihnen fotografiert vorliegt.
    scanned = _scanned_pages(account_id)
    for paper in paper_books(account_id):
        pages = {page for (have, page) in scanned.get(paper["subject_name"].casefold(), {}) if serves(have, paper["part_label"])}
        books.append({"title": paper["title"], "subject": paper["subject_name"].casefold(), "part_label": paper["part_label"],
                      "pages_stored": len(pages), "units": units_of(account_id, paper["title"]),
                      "access": {"status": "paper", "toc_state": paper["toc_state"], "page": None, "checked_at": paper["updated_at"], "detail": None}})
    return {"since": sync["since"], "subjects": subjects,
            "missing_total": sum(s["missing_count"] for s in subjects),
            "pending_total": sum(s["pending"] for s in subjects),
            "books": books}


def _book_guesser(account_id: int, subject: str):
    """Welches Buch eine Seite ohne Buchteil meint: das mit einem gerade
    angeschnittenen Kapitel, das die Seite enthält (D51). Zwei Kandidaten
    sind keine Antwort; dann bleibt es offen und jedes Foto zählt."""
    from .book_structure import chapter_of, chapters_of, paper_books, touched_chapters
    books: list[tuple[str, list[dict], set[int]]] = []
    try:
        shelf = _shelf(account_id).get(subject.casefold())
        if shelf:
            chapters = chapters_of(account_id, shelf["title"])
            if chapters:
                touched = {c["id"] for c in touched_chapters(account_id, shelf["title"], subject, chapters)}
                books.append(("Schulbuch", chapters, touched))
        for paper in paper_books(account_id, subject):
            chapters = chapters_of(account_id, paper["title"])
            if chapters:
                touched = {c["id"] for c in touched_chapters(account_id, paper["title"], subject, chapters, label=paper["part_label"])}
                books.append((paper["part_label"], chapters, touched))
    except Exception:
        log.warning("Buchvermutung für %s nicht möglich", subject, exc_info=True)

    def guess(page: int) -> str | None:
        hits = [label for label, chapters, touched in books
                if (chapter := chapter_of(chapters, page)) and chapter["id"] in touched]
        if len(hits) == 1:
            return hits[0]
        # Kein angeschnittenes Kapitel: reicht ein einziges Buch bis zu dieser Seite?
        within = [label for label, chapters, _ in books if chapter_of(chapters, page)]
        return within[0] if len(within) == 1 else None
    return guess


def page_list(pages: list[int]) -> str:
    """6, 7, 8 und 12 statt einer langen Aufzählung; Seite 0 ist das Blatt selbst."""
    pages = [p for p in pages if p]
    if not pages:
        return "ohne Seitenangabe"
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
            "WHERE account_id=? AND status='paper' AND entry_kind IN ('lesson','homework','exam_notice') ORDER BY entry_date DESC",
            (account_id,))]
    dismissed = _dismissed(account_id)
    links = [l for l in links if not is_dismissed(dismissed, l)]
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


def segments(text: str, subject: str = "") -> list[dict]:
    """Den Text in Stücke zerlegen: Fließtext und Seitenangaben mit Buchteil."""
    text = text or ""
    out: list[dict] = []
    pos = 0
    for start, end, pages in page_hits(text):
        if start > pos:
            out.append({"text": text[pos:start]})
        label, kind = part_of(text[:start], subject)
        out.append({"text": text[start:end], "pages": pages,
                    "label": label or "Unbekannte Quelle", "kind": kind or "unknown"})
        pos = end
    if pos < len(text):
        out.append({"text": text[pos:]})
    sheets = sheet_mentions(text, subject)
    if sheets:
        first = sheets[0]
        # Das erste genannte Blatt wird zum Link; sein Stück Text wird geteilt.
        offset = 0
        result = []
        for seg in out:
            length = len(seg["text"])
            if "pages" not in seg and offset <= first.start() < offset + length:
                cut = first.start() - offset
                if cut:
                    result.append({"text": seg["text"][:cut]})
                result.append({"text": first.group(0), "pages": [0], "label": "Arbeitsblatt", "kind": "worksheet"})
                rest = seg["text"][cut + len(first.group(0)):]
                if rest:
                    result.append({"text": rest})
            else:
                result.append(seg)
            offset += length
        return result
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


def _decorate(text: str, links: list[dict], analysis: dict[int, str], subject: str = "") -> tuple[list[dict], str | None, list[int]]:
    """Segmente mit Stand und Material versehen; dazu der Gesamtstand."""
    by_page: dict[tuple[str, int], dict] = {}
    for link in links:
        by_page.setdefault((link.get("part_label") or "", link["page"]), link)
        by_page.setdefault((link["part_kind"], link["page"]), link)
    states: list[str | None] = []
    materials: list[int] = []
    out = []
    for seg in segments(text, subject):
        if "pages" not in seg:
            out.append(seg)
            continue
        page_states = []
        page_materials = []
        for page in seg["pages"]:
            link = by_page.get((seg["label"], page)) or by_page.get((seg["kind"], page)) \
                or by_page.get(("unknown", page)) or by_page.get(("book", page))
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


# Die Verknüpfungen werden im Sammellauf und beim Aufruf der Bilanz erneuert.
# Eine Ansicht, die dazwischen einen neuen Untis-Eintrag zeigt, zieht sie
# selbst nach, höchstens alle zehn Minuten je Kind.
_SYNCED: dict[int, float] = {}


def ensure_synced(account_id: int, max_age: float = 600.0) -> None:
    import time
    now = time.monotonic()
    if now - _SYNCED.get(account_id, -1e9) < max_age:
        return
    _SYNCED[account_id] = now
    try:
        sync_links(account_id)
        refresh_status(account_id)
    except Exception:
        log.warning("Quellen für Konto %s nicht nachgezogen", account_id, exc_info=True)


def annotate_lessons(account_id: int, lessons: list[dict], key: str = "lstext", id_key: str = "id") -> None:
    """Jeder Stunde ihre Textsegmente mit Quellenstand anhängen."""
    ensure_synced(account_id)
    ids = [l[id_key] for l in lessons if l.get(key)]
    if not ids:
        return
    marks = ",".join("?" * len(ids))
    with closing(webapp_conn()) as conn:
        links = [dict(r) for r in conn.execute(
            f"SELECT entry_id,part_kind,part_label,page,status,detail,material_id FROM source_links "
            f"WHERE account_id=? AND entry_kind='lesson' AND entry_id IN ({marks})", (account_id, *ids))]
        analysis = _analysis_states(conn, [l["material_id"] for l in links if l["material_id"]])
    by_lesson: dict[int, list[dict]] = {}
    for link in links:
        by_lesson.setdefault(link["entry_id"], []).append(link)
    for lesson in lessons:
        if not lesson.get(key):
            continue
        segs, state, _ = _decorate(lesson[key], by_lesson.get(lesson[id_key], []), analysis, lesson.get("subject_name") or "")
        lesson[f"{key}_segments"] = segs
        lesson["source_state"] = state


_META_LINE = re.compile(r"^\s*(gegeben\s+am|f(?:ä|ae)llig(?:\s+bis)?)\s*:", re.I)


def task_text(task: dict) -> str:
    """Der Auftrag einer Aufgabe. Aus Untis kommt er in den Notizen, mit
    Kennung und Datumszeilen; der Titel ist dort nur das Fach."""
    kept = []
    for raw in (task.get("notes") or "").splitlines():
        line = _TAG.sub(" ", raw).strip()
        if not line or _META_LINE.match(line):
            continue
        kept.append(re.sub(r"^\s*#\s?", "", line).strip())
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
    ensure_synced(account_id)
    with closing(history_conn()) as hconn:
        homework_ids = {t["id"]: homework_for_task(hconn, account_id, t) for t in tasks}
    with closing(webapp_conn()) as conn:
        hw_ids = [h for h in homework_ids.values() if h]
        links: list[dict] = []
        if hw_ids:
            marks = ",".join("?" * len(hw_ids))
            links = [dict(r) for r in conn.execute(
                f"SELECT entry_id,part_kind,part_label,page,status,detail,material_id FROM source_links "
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
        segs, state, materials = _decorate(body, by_homework.get(hw, []) if hw else [], analysis, task.get("subject_name") or "")
        for extra in attached.get(task["id"], []):
            if extra not in materials:
                materials.append(extra)
        task["text"] = body
        task["text_segments"] = segs
        task["title_segments"] = segs if body == (task.get("title") or "").strip() else None
        task["source_state"] = state
        task["homework_id"] = hw
        task["materials"] = [details[m] for m in materials if m in details]


# --- Der Quellenstand einer Arbeit ---------------------------------------------
# Auf der Klausurkarte steht, ob das Material für den angenommenen Stoff
# vorliegt: jede im Zeitraum genannte Stelle, die Kapitel dazu, der Zettel
# der Lehrkraft. Was fehlt, ist ein Link zur Einkaufsliste des Fachs.


def exam_sources(account_id: int, subject: str, since: str, until: str) -> dict | None:
    """Was für die Arbeit eines Fachs im Zeitraum an Quellen vorliegt und fehlt."""
    if not subject:
        return None
    ensure_synced(account_id)
    with closing(webapp_conn()) as conn:
        links = [dict(r) for r in conn.execute(
            "SELECT subject_name,part_label,part_kind,page,status,detail,material_id,entry_kind,entry_id,entry_date,quote "
            "FROM source_links WHERE account_id=? AND lower(subject_name)=lower(?) AND entry_date>=? AND entry_date<=?",
            (account_id, subject, since, until))]
        analysis = _analysis_states(conn, [l["material_id"] for l in links if l["material_id"]])
    # Von den Eltern als „nicht nötig“ gestrichen: zählt weder als fehlend noch mit (D196).
    dismissed = _dismissed(account_id)
    links = [l for l in links if not is_dismissed(dismissed, l)]
    if not links:
        notices = [n for n in exam_notices(account_id) if n["subject_name"] and n["subject_name"].casefold() == subject.casefold()
                   and since <= n["date"] <= until]
        return {"total": 0, "ready": 0, "pending": 0, "missing": 0, "missing_items": [], "chapters": [],
                "notice": bool(notices), "subject": subject, **_notice_summary(notices)} if notices else None
    # Dieselbe Seite aus Stunde, Hausaufgabe und Kapitelregel ist eine Stelle.
    best: dict[tuple[str, int], str] = {}
    why: dict[tuple[str, int], dict] = {}
    rank = {"missing": 0, "pending": 1, "ready": 2}
    for link in links:
        state = _state_of(link, analysis) or "missing"
        key = (link["part_label"], link["page"])
        if key not in best or rank[state] > rank[best[key]]:
            best[key] = state
            if state == "pending":
                # Liegt die Seite schon da (Foto oder Abruf), fehlt nur das Lesen;
                # sonst wird sie noch aus dem digitalen Buch geholt.
                present = link["status"] in ("scanned", "digital") and link["material_id"]
                kind = "unread" if present else "fetching"
                if present and analysis.get(link["material_id"]) == "failed":
                    kind = "failed"
                why[key] = {"label": label_or_book(link), "page": link["page"], "kind": kind, "material_id": link["material_id"]}
    if any(w["kind"] == "failed" for w in why.values()):
        # Der Grund des Scheiterns entscheidet, was die Karte sagt: 429 ist der KI-Rahmen.
        ids = [w["material_id"] for w in why.values() if w["kind"] == "failed"]
        with closing(webapp_conn()) as conn:
            errors = {r[0]: r[1] for r in conn.execute(
                f"SELECT id,analysis_error FROM materials WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))}
        for w in why.values():
            if w["kind"] == "failed":
                w["error"] = errors.get(w["material_id"]) or ""
                if str(w["error"]).strip() == "429":
                    w["kind"] = "budget"
    counts = {"ready": 0, "pending": 0, "missing": 0}
    gaps: dict[str, list[int]] = {}
    pending_items = []
    for (label, page), state in best.items():
        counts[state] += 1
        if state == "missing":
            gaps.setdefault(label, []).append(page)
        elif state == "pending" and (label, page) in why:
            pending_items.append(why[(label, page)])
    # Woher die Lücke kommt: die Nennungen dahinter, damit niemand rätselt (D196).
    missing_items = [{"label": label, "pages": sorted(pages), "pages_label": page_list(pages),
                      "from": mention_sources([l for l in links if l["part_label"] == label and l["page"] in pages], subject)}
                     for label, pages in sorted(gaps.items(), key=lambda kv: -len(kv[1]))]
    chapters = []
    from .book_structure import overview, paper_books
    book = _shelf(account_id).get(subject.casefold())
    try:
        if book:
            chapters += overview(account_id, book["title"], subject)
        for paper in paper_books(account_id, subject):
            chapters += overview(account_id, paper["title"], subject, paper["part_label"])
    except Exception:
        log.warning("Kapitel für die Arbeit in %s nicht berechenbar", subject, exc_info=True)
    chapters = [{"part_label": c.get("part_label"), "number": c["number"], "title": c["title"],
                 "start_page": c["start_page"], "end_page": c["end_page"], "pages": c["pages"],
                 "pages_stored": c["pages_stored"], "inferred": c.get("inferred", False)}
                for c in chapters if since <= c["first_date"] <= until]
    notices = [n for n in exam_notices(account_id) if n["subject_name"] and n["subject_name"].casefold() == subject.casefold()
               and since <= n["date"] <= until]
    return {"total": len(best), **counts, "missing_items": missing_items, "pending_items": pending_items, "chapters": chapters,
            "notice": bool(notices), "subject": subject, **_notice_summary(notices)}


def label_or_book(link: dict) -> str:
    return (link.get("part_label") or "").strip() or "Schulbuch"


def _notice_checked(notice: dict) -> bool:
    """Braucht der Zettel keinen Blick? Bestätigt, oder sauber gelesen und jede
    genannte Seite ist aus dem Unterricht bekannt (D167). Ein ganzer Zettel wird
    nicht mehr aus Prinzip vorgelegt."""
    if notice["verified"]:
        return True
    from . import materials as store, notice_check
    with closing(webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (notice["id"],)).fetchone()
    if not row or store.needs_review(row):
        return False
    try:
        found = notice_check.checker(row["account_id"])(dict(row))
    except Exception:
        log.debug("Zettel %s nicht gegen den Unterricht prüfbar", notice["id"], exc_info=True)
        return True
    return not (found or {}).get("unknown")


def _notice_summary(notices: list[dict]) -> dict:
    if not notices:
        return {}
    newest = max(notices, key=lambda n: n["date"])
    return {"notice_id": newest["id"], "notice_text": newest["text"][:300],
            "notice_verified": all(_notice_checked(n) for n in notices)}
