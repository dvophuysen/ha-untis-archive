"""Central material storage: worksheets, workbook pages, notes, scans, exams.

A material belongs to a child, not to a topic. Subject, kind, date, topic and
readable text come from the analysis; links to topics, homework, lessons and
exams are added on top and may be several.
"""

from __future__ import annotations

import io
import json
import re
import logging
import subprocess
from contextlib import closing
from datetime import datetime, timezone

from . import proofread
from .db import webapp_conn

_LOGGER = logging.getLogger("schul_cockpit.materials")

MAX_FILE = 12 * 1024 * 1024
MAX_ACCOUNT_FILES = 200 * 1024 * 1024
MAX_TEXT = 30000
# Two images per model call, and no more than this many pages of one document.
PAGES_PER_CALL = 2
MAX_ANALYSIS_PAGES = 4

KINDS = (
    "worksheet",   # Arbeitsblatt der Lehrkraft
    "workbook",    # Arbeitsheft-Seite
    "book_page",   # Buchseite auf Papier
    "notes",       # eigene Mitschrift, Heftseite, digitales Heft
    "assignment",  # Aufgabenstellung
    "own_work",    # bearbeitete Lösung des Kindes
    "exam",        # geschriebene Arbeit
    "handout",     # Informations- oder Merkblatt
    "exam_notice", # offizielle Themenliste der Lehrkraft für eine Arbeit
    "toc",         # Inhaltsverzeichnis eines Buchs, das nur auf Papier existiert
    "other",
)
# Buchteile, die eine Datei zeigen kann; die Namen sind die der Quellenbilanz.
BOOK_PARTS = ("Textband", "Begleitband", "Schulbuch", "Arbeitsheft", "Grammatikheft", "Arbeitsblatt")

LINK_KINDS = ("topic", "task", "lesson", "exam", "homework")
# Rolle einer Verknüpfung (D85). Ohne Angabe folgt sie aus der Materialart.
RELATIONS = ("blatt", "ergebnis", "stoff")

# Fields a parent may correct. A correction is remembered in locked_fields and
# survives every later analysis run.
EDITABLE = (
    "kind", "subject_name", "title", "summary", "content_text",
    "document_date", "period_start", "period_end", "contains_solutions",
    "source_label", "source_page", "printed_pages",
)


def canonical_subject(account_id: int, name: str | None) -> str | None:
    """Die Schreibweise des Stundenplans („LATEIN"), egal wie es getippt wurde.

    Materialien und Quellen werden über den Fachnamen zusammengeführt; ein
    „Latein" neben „LATEIN" wäre ein zweites Fach.
    """
    name = (name or "").strip()
    if not name:
        return None
    try:
        from .subject_names import SubjectCatalog
        found = SubjectCatalog(account_id).resolve(name)
    except Exception:
        found = None
    return found["name"] if found else name


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sniff(content: bytes) -> str | None:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _taken_at(blob: bytes) -> str | None:
    """Capture time from the image itself, so a photo keeps its own date."""
    try:
        from PIL import Image

        raw = (Image.open(io.BytesIO(blob)).getexif() or {}).get(36867)
        if not raw:
            return None
        return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        return None


# Unter dieser Kantenvarianz (Graustufen, 1000 Pixel, FIND_EDGES) ist ein Foto
# unscharf: scharfe Buchseiten liegen gemessen bei 1700 bis 4400, dasselbe
# Foto mit zwei Pixeln Weichzeichnung bei 300.
BLURRY_BELOW = 800.0


def fingerprint(image) -> tuple[str, float]:
    """Bildabdruck (Mittelwert-Hash 8×8) und Schärfe eines Fotos.

    Zwei Aufnahmen derselben Seite haben denselben Abdruck; leicht anderer
    Ausschnitt oder Licht ändern höchstens wenige Bits."""
    from PIL import ImageFilter, ImageStat
    grey = image.convert("L")
    small = grey.resize((8, 8))
    pixels = list(small.getdata())
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if p > mean else "0" for p in pixels)
    probe = grey.copy()
    probe.thumbnail((1000, 1000))
    sharp = ImageStat.Stat(probe.filter(ImageFilter.FIND_EDGES)).var[0]
    return f"{int(bits, 2):016x}", round(float(sharp), 1)


def hash_distance(a: str | None, b: str | None) -> int:
    if not a or not b:
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def prepare_image(blob: bytes) -> tuple[bytes, str, str | None, dict]:
    """Downscale like a chat photo; the original size buys nothing here.
    Returns the bytes, the type, the capture time and the fingerprint."""
    from PIL import Image, ImageOps

    captured = _taken_at(blob)
    image = Image.open(io.BytesIO(blob))
    if image.width * image.height > 50_000_000:
        raise ValueError("Bild zu groß")
    image.load()
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((1800, 1800))
    try:
        phash, sharpness = fingerprint(image)
    except Exception:
        phash, sharpness = None, None
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85)
    return out.getvalue(), "image/jpeg", captured, {"phash": phash, "sharpness": sharpness}


def pdf_pages(blob: bytes) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(blob)).pages)
    except Exception:
        return 0


def pdf_text(blob: bytes, limit: int = MAX_TEXT) -> str:
    """Text of a digital notebook PDF. Costs nothing and needs no model."""
    try:
        from pypdf import PdfReader

        parts = []
        for page in PdfReader(io.BytesIO(blob)).pages[:20]:
            parts.append(page.extract_text() or "")
            if sum(len(p) for p in parts) > limit:
                break
        return "\n".join(parts).strip()[:limit]
    except Exception:
        return ""


def pdf_page_images(blob: bytes, first: int, count: int) -> list[bytes]:
    """Render scanned pages so a vision model can read them."""
    try:
        result = subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "150", "-f", str(first), "-l", str(first + count - 1), "-"],
            input=blob, capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0 or not result.stdout:
        return []
    # pdftoppm concatenates JPEGs on stdout; split on the start marker.
    pages, current = [], bytearray()
    for chunk in result.stdout.split(b"\xff\xd8\xff"):
        if current:
            pages.append(b"\xff\xd8\xff" + bytes(current))
        current = bytearray(chunk)
    if current:
        pages.append(b"\xff\xd8\xff" + bytes(current))
    return [p for p in pages if len(p) > 512][:count]


def account_usage(conn, account_id: int, exclude: int | None = None) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(length(file_bytes)),0) FROM materials WHERE account_id=? AND id IS NOT ?",
        (account_id, exclude),
    ).fetchone()[0]


def create(account_id: int, user_id: int | None, content: bytes, filename: str, mime: str,
           hints: dict | None = None) -> int:
    """Store the file and queue it for analysis. Nothing else is required."""
    hints = hints or {}
    captured = None
    page_count = 0
    text = ""
    print_ = {"phash": None, "sharpness": None}
    if mime == "application/pdf":
        page_count = pdf_pages(content)
        text = pdf_text(content)
    else:
        content, mime, captured, print_ = prepare_image(content)
    stamp = now_iso()
    with closing(webapp_conn()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        if account_usage(conn, account_id) + len(content) > MAX_ACCOUNT_FILES:
            raise ValueError("Der Materialspeicher dieses Kindes ist voll.")
        material_id = conn.execute(
            "INSERT INTO materials(account_id,kind,subject_name,title,content_text,captured_at,"
            "created_by,filename,mime_type,file_bytes,page_count,analysis_state,created_at,updated_at,"
            "source_label,source_page,phash,sharpness) VALUES(?,?,?,?,?,?,?,?,?,?,?,'pending',?,?,?,?,?,?)",
            (account_id, hints.get("kind") or "other", hints.get("subject_name"),
             (hints.get("title") or filename or "Material")[:200], text,
             captured or stamp, user_id, (filename or "Material")[:200], mime, content,
             page_count, stamp, stamp, hints.get("source_label") or None, hints.get("source_page") or None,
             print_["phash"], print_["sharpness"]),
        ).lastrowid
        for kind in LINK_KINDS:
            target = hints.get(f"{kind}_id")
            if target:
                conn.execute(
                    "INSERT OR IGNORE INTO material_links(material_id,kind,target_id,origin,created_at) "
                    "VALUES(?,?,?,'mensch',?)", (material_id, kind, int(target), stamp))
    return material_id


def duplicate_of(account_id: int, material_id: int, max_distance: int = 3) -> dict | None:
    """Ein früheres Foto derselben Seite, wenn es eines gibt: gleicher oder
    fast gleicher Bildabdruck im selben Konto."""
    with closing(webapp_conn()) as conn:
        me = conn.execute("SELECT phash FROM materials WHERE id=? AND account_id=?", (material_id, account_id)).fetchone()
        if not me or not me["phash"]:
            return None
        for row in conn.execute(
                "SELECT id,title,kind,source_label,source_page,phash FROM materials WHERE account_id=? AND id!=? "
                "AND hidden=0 AND phash IS NOT NULL ORDER BY id DESC LIMIT 500", (account_id, material_id)):
            if hash_distance(me["phash"], row["phash"]) <= max_distance:
                return {"id": row["id"], "title": row["title"], "kind": row["kind"],
                        "source_label": row["source_label"], "source_page": row["source_page"]}
    return None


def links(conn, material_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT kind,target_id,origin,relation FROM material_links WHERE material_id=?", (material_id,))]


# Lesungen mit Folgen: Aus einem Zettel werden Stellen gebunden, aus einem
# Verzeichnis Kapitel. Was daraus wird, hängt an jedem gelesenen Zeichen, und
# Handschrift liest das Modell nicht sicher („70" statt „10"). Solche
# Materialien bitten um ein Gegenlesen, bis ein Elternteil sie bestätigt.
REVIEW_KINDS = ("exam_notice", "toc")
REVIEW_CONFIDENCE = 0.7


def doubts_of(row) -> list[dict]:
    """Die Zweifelsstellen einer Lesung, ob als JSON in der Zeile oder schon
    ausgelesen in einem fertigen Eintrag."""
    keys = row.keys() if hasattr(row, "keys") else row
    if "doubts" not in keys:
        return []
    found = row["doubts"]
    if isinstance(found, str):
        try:
            found = json.loads(found or "[]")
        except ValueError:
            return []
    if not isinstance(found, list):
        return []
    return [d for d in found if isinstance(d, dict) and (d.get("text") or "").strip()]


def needs_review(row) -> bool:
    keys = row.keys() if hasattr(row, "keys") else row
    if (row["origin"] if "origin" in keys else "") == "book_fetch":
        return False
    if row["analysis_state"] != "ready" or row["verified"]:
        return False
    if row["kind"] in REVIEW_KINDS:
        return True
    # Gegengelesen wird, wo die Lesung unsicher ist, nicht wo Handschrift steht
    # (D118). Handschrift allein verlangte bisher immer einen Blick (D77); bei
    # einer Arbeitsheftseite mit drei eingetragenen Brüchen unter sechzig Zeilen
    # führte das zum Bestätigen ohne Hinsehen. Eine sauber gelesene Eintragung
    # kostet jetzt keinen Blick mehr, eine unleserliche Stelle schon: Sie ist
    # das Eingeständnis, nicht gelesen zu haben.
    if doubts_of(row):
        return True
    text = row["content_text"] if "content_text" in keys else ""
    if proofread.UNREADABLE.search(text or ""):
        return True
    confidence = row["confidence"] if "confidence" in keys else None
    return confidence is not None and confidence < REVIEW_CONFIDENCE


def _public(row, with_links=None) -> dict:
    result = {k: row[k] for k in row.keys() if k not in ("file_bytes",)}
    result["has_file"] = bool(row["filename"])
    result["locked_fields"] = json.loads(row["locked_fields"] or "[]")
    result["needs_review"] = needs_review(row)
    # Die gedruckte Seite ohne die Eintragungen des Kindes: So schlägt das Kind
    # im Lernraum dieselbe Seite auf, die der Mentor als Grundlage hat (D101).
    keys = row.keys()
    if "content_text" in keys:
        result["printed_text"] = printed_only(row["content_text"])
    # Was gegenzulesen ist, kommt fertig gekürzt aus dem Backend: die
    # Zweifelsstellen mit einer Zeile Zusammenhang, dazwischen die Lücke (D118).
    if "doubts" in keys:
        result["doubts"] = doubts_of(row)
    if result["needs_review"] and "content_text" in keys:
        result["review"] = proofread.view(row["content_text"] or "", result.get("doubts") or [])
    result["blurry"] = bool("sharpness" in keys and row["sharpness"] is not None and row["sharpness"] < BLURRY_BELOW)
    if with_links is not None:
        result["links"] = with_links
    return result


def call_for_review(item: dict) -> dict:
    """Ein Material nachträglich zum Gegenlesen stellen. Die Plausibilitäts-
    prüfung kennt den Unterricht und sieht damit Zweifel, die der Lesung allein
    entgehen: eine Seitenzahl, die es im Fach nie gab (D79)."""
    item["needs_review"] = True
    item.setdefault("doubts", [])
    if "review" not in item:
        item["review"] = proofread.view(item.get("content_text") or "", item["doubts"])
    return item


def listing(account_id: int, *, subject: str | None = None, kind: str | None = None,
            start: str | None = None, end: str | None = None, query: str | None = None,
            state: str | None = None, include_hidden: bool = False, include_books: bool = True,
            task_id: int | None = None, offset: int = 0, limit: int = 100) -> list[dict]:
    where = ["account_id=?"]
    args: list = [account_id]
    if not include_hidden:
        where.append("hidden=0")
    if not include_books:
        where.append("origin!='book_fetch'")
    if task_id:
        where.append("id IN (SELECT material_id FROM material_links WHERE kind='task' AND target_id=?)")
        args.append(task_id)
    if subject:
        where.append("lower(subject_name)=lower(?)")
        args.append(subject)
    if kind:
        where.append("kind=?")
        args.append(kind)
    if start:
        where.append("COALESCE(document_date,substr(created_at,1,10))>=?")
        args.append(start)
    if end:
        where.append("COALESCE(document_date,substr(created_at,1,10))<=?")
        args.append(end)
    if state:
        where.append("analysis_state=?")
        args.append(state)
    if query:
        where.append("(title LIKE ? OR summary LIKE ? OR content_text LIKE ?)")
        args.extend([f"%{query}%"] * 3)
    args.extend([max(1, min(limit, 300)), max(0, offset)])
    with closing(webapp_conn()) as conn:
        rows = conn.execute(
            "SELECT id,account_id,kind,subject_name,title,summary,document_date,period_start,period_end,"
            "captured_at,created_by,filename,mime_type,page_count,verified,contains_solutions,hidden,"
            "locked_fields,analysis_state,analysis_model,analysis_version,analyzed_at,analysis_error,"
            "confidence,created_at,updated_at,origin,source_book,source_page,source_label,printed_pages,page_type,handwritten,"
            "pupil_entries,doubts,"
            # Der gelesene Text gehört in die Liste, wo er gegengelesen werden
            # soll — sonst hätte die Karte nichts zu zeigen.
            "CASE WHEN verified=0 AND (kind IN ('exam_notice','notes','toc') OR handwritten=1 OR pupil_entries=1 "
            "OR COALESCE(doubts,'') NOT IN ('','[]')) THEN content_text ELSE '' END AS content_text, "
            "length(file_bytes) AS file_size "
            "FROM materials WHERE " + " AND ".join(where) +
            " ORDER BY COALESCE(document_date,substr(created_at,1,10)) DESC, id DESC LIMIT ? OFFSET ?",
            tuple(args)).fetchall()
        return [_public(r, links(conn, r["id"])) for r in rows]


def detail(account_id: int, material_id: int) -> dict | None:
    with closing(webapp_conn()) as conn:
        row = conn.execute(
            "SELECT *, length(file_bytes) AS file_size FROM materials WHERE id=? AND account_id=?",
            (material_id, account_id)).fetchone()
        if not row:
            return None
        return _public(row, links(conn, material_id))


def update(account_id: int, material_id: int, changes: dict, *, by_parent: bool) -> dict | None:
    """A human correction wins and stays: the field is locked against analysis."""
    fields = {k: v for k, v in changes.items() if k in EDITABLE}
    with closing(webapp_conn()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT locked_fields FROM materials WHERE id=? AND account_id=?",
                           (material_id, account_id)).fetchone()
        if not row:
            return None
        locked = set(json.loads(row["locked_fields"] or "[]"))
        if by_parent:
            locked |= set(fields)
        assignments = ", ".join(f"{name}=?" for name in fields)
        args = list(fields.values())
        if assignments:
            conn.execute(f"UPDATE materials SET {assignments},locked_fields=?,updated_at=? WHERE id=?",
                         (*args, json.dumps(sorted(locked)), now_iso(), material_id))
        else:
            conn.execute("UPDATE materials SET locked_fields=?,updated_at=? WHERE id=?",
                         (json.dumps(sorted(locked)), now_iso(), material_id))
    return detail(account_id, material_id)


def set_flag(account_id: int, material_id: int, field: str, value: int) -> dict | None:
    if field not in ("verified", "hidden"):
        raise ValueError("Unbekanntes Feld")
    with closing(webapp_conn()) as conn, conn:
        changed = conn.execute(f"UPDATE materials SET {field}=?,updated_at=? WHERE id=? AND account_id=?",
                               (int(value), now_iso(), material_id, account_id)).rowcount
    return detail(account_id, material_id) if changed else None


def link(account_id: int, material_id: int, kind: str, target_id: int, origin: str = "mensch",
         relation: str | None = None) -> bool:
    if kind not in LINK_KINDS:
        raise ValueError("Unbekannte Verknüpfung")
    if relation is not None and relation not in RELATIONS:
        raise ValueError("Unbekannte Rolle")
    with closing(webapp_conn()) as conn, conn:
        if not conn.execute("SELECT 1 FROM materials WHERE id=? AND account_id=?",
                            (material_id, account_id)).fetchone():
            return False
        # Eine bestehende Verknüpfung bekommt die Rolle nachgetragen, statt zu verschwinden.
        conn.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at,relation) VALUES(?,?,?,?,?,?) "
                     "ON CONFLICT(material_id,kind,target_id) DO UPDATE SET relation=COALESCE(excluded.relation,relation),"
                     "origin=CASE WHEN excluded.relation IS NOT NULL THEN excluded.origin ELSE origin END",
                     (material_id, kind, int(target_id), origin, now_iso(), relation))
    return True


def unlink(account_id: int, material_id: int, kind: str, target_id: int) -> bool:
    with closing(webapp_conn()) as conn, conn:
        return bool(conn.execute(
            "DELETE FROM material_links WHERE material_id IN (SELECT id FROM materials WHERE id=? AND account_id=?) "
            "AND kind=? AND target_id=?", (material_id, account_id, kind, int(target_id))).rowcount)


def remove(account_id: int, material_id: int) -> bool:
    with closing(webapp_conn()) as conn, conn:
        conn.execute("DELETE FROM material_links WHERE material_id=?", (material_id,))
        return bool(conn.execute("DELETE FROM materials WHERE id=? AND account_id=?",
                                 (material_id, account_id)).rowcount)


def file_of(account_id: int, material_id: int):
    with closing(webapp_conn()) as conn:
        return conn.execute(
            "SELECT filename,mime_type,file_bytes FROM materials WHERE id=? AND account_id=?",
            (material_id, account_id)).fetchone()


def for_context(account_id: int, *, subject: str | None = None, task_id: int | None = None,
                topic_ids: list[int] | None = None, start: str | None = None, end: str | None = None,
                material_ids: list[int] | None = None, budget: int = 6000, top: int = 4) -> list[dict]:
    """Materials for a mentor or exam call, ranked by how closely they belong.

    Everything in reach contributes its short summary; only the closest few
    contribute full text, until the character budget is used up.
    """
    with closing(webapp_conn()) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT m.id,m.kind,m.subject_name,m.title,m.summary,m.content_text,m.document_date,"
            "m.contains_solutions,m.verified,m.created_at FROM materials m "
            "WHERE m.account_id=? AND m.hidden=0 AND (m.summary!='' OR m.content_text!='') "
            "ORDER BY COALESCE(m.document_date,substr(m.created_at,1,10)) DESC, m.id DESC LIMIT 200",
            (account_id,))]
        related = {r["material_id"]: r["kind"] for r in conn.execute(
            "SELECT material_id,kind,target_id FROM material_links WHERE kind='task' AND target_id=?",
            (task_id or -1,))}
        # Die Quellen einer bestimmten Stunde (Nachholen) zählen wie die Verknüpfung zur Aufgabe.
        for mid in material_ids or []:
            related.setdefault(mid, "lesson")
        topic_hits = set()
        if topic_ids:
            marks = ",".join("?" * len(topic_ids))
            topic_hits = {r[0] for r in conn.execute(
                f"SELECT material_id FROM material_links WHERE kind='topic' AND target_id IN ({marks})",
                tuple(topic_ids))}

    def rank(row) -> tuple:
        day = row["document_date"] or row["created_at"][:10]
        in_window = bool(start and end and start <= day <= end)
        return (
            0 if row["id"] in related else 1,
            0 if row["id"] in topic_hits else 1,
            # Der Zettel mit dem Klausurstoff steht vor jedem Arbeitsblatt.
            0 if row["kind"] == "exam_notice" and subject and (row["subject_name"] or "").casefold() == subject.casefold() else 1,
            0 if (subject and (row["subject_name"] or "").casefold() == subject.casefold()) else 1,
            0 if in_window else 1,
            row["created_at"],
        )

    def keeps(row) -> bool:
        # A material of another subject is only of interest when it is linked
        # to exactly this homework or topic.
        if subject and row["subject_name"] and row["subject_name"].casefold() != subject.casefold():
            return row["id"] in related or row["id"] in topic_hits
        if end and (row["document_date"] or row["created_at"][:10]) > end:
            return row["id"] in related or row["id"] in topic_hits
        return True

    rows = [r for r in rows if keeps(r)]
    rows.sort(key=rank)
    chosen, used = [], 0
    for index, row in enumerate(rows[:20]):
        entry = {"id": row["id"], "title": row["title"], "kind": row["kind"],
                 "subject": row["subject_name"], "date": row["document_date"],
                 "summary": row["summary"][:400]}
        if row["contains_solutions"]:
            entry["enthaelt_loesungen"] = True
        if index < top and used < budget:
            text = row["content_text"][: max(0, budget - used)]
            if text:
                entry["inhalt"] = text
                used += len(text)
        chosen.append(entry)
    return chosen


# Die gedruckte Seite ohne die Eintragungen des Kindes. Die Lesung schreibt sie
# als „___ [Kind: …]“ dahinter (D98); wer die Seite als Vorlage braucht — der
# Mentor beim Aufgabenbauen —, nimmt diese Fassung.
_PUPIL = re.compile(r"\s*\[Kind(?: gestrichen)?:[^\]]*\]")


def printed_only(text: str) -> str:
    return _PUPIL.sub("", text or "")


def pupil_only(text: str) -> list[str]:
    """Nur das, was das Kind eingetragen hat, in der Reihenfolge der Seite."""
    return [m.group(1).strip() for m in re.finditer(r"\[Kind:([^\]]*)\]", text or "")]
