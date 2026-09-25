"""Abbildungen aus abgelegten Seiten (D198).

Jede Bildseite (Buchseite, Arbeitsblatt, Heft, Zettel) wird einmal im
Hintergrund angesehen: Welche Bilder, Zeichnungen, Schaltpläne, Diagramme,
Karten stehen darauf, wo genau (Anteile der Seite) und was zeigen sie. Mit
diesem Verzeichnis kann der Lernbegleiter eine Abbildung in eine Aufgabe
nehmen, die Übungsarbeit sie drucken und die Sprechprobe ein Bild zur
Bildbeschreibung zeigen. Das Kind sieht den Ausschnitt, das Modell bekommt
ihn beim Auswerten als Bild und die Beschreibung als Text.
"""
from __future__ import annotations

import base64
import io
import json
import logging
from contextlib import closing
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .db import webapp_conn
from .learning import now_iso

LOG = logging.getLogger("schul_cockpit.page_figures")

KINDS = ("foto", "zeichnung", "schaltplan", "diagramm", "karte", "tabelle", "skizze", "comic")
PICTURE_KINDS = ("foto", "zeichnung", "comic", "karte")  # taugen für eine Bildbeschreibung
PAGE_KINDS = ("book_page", "worksheet", "workbook", "exam_notice", "other")
PER_CYCLE = 12
MIN_SIDE = 0.06  # kleinere Kästen sind Symbole, keine Abbildung


class Found(BaseModel):
    kind: Literal["foto", "zeichnung", "schaltplan", "diagramm", "karte", "tabelle", "skizze", "comic"]
    box: list[float] = Field(min_length=4, max_length=4)
    caption: str = Field(default="", max_length=120)
    description: str = Field(min_length=3, max_length=600)


class Scan(BaseModel):
    figures: list[Found] = Field(default_factory=list, max_length=8)


INSTRUCTION = (
    "Du siehst eine abfotografierte Schulbuchseite oder ein Arbeitsblatt. Liste die Abbildungen darauf: Fotos, "
    "Zeichnungen, Comics, Schaltpläne, Diagramme, Karten, Skizzen, Tabellen mit Bildcharakter. Kein Fließtext, keine "
    "Überschriften, keine Symbole oder Icons. Für jede Abbildung: kind, box als [links, oben, rechts, unten] in Anteilen "
    "der Seite von 0 bis 1 (eng um die Abbildung, ohne Seitenrand), caption (Bildunterschrift oder Nummer, wenn "
    "vorhanden, sonst leer) und description: was genau zu sehen ist, sachlich und vollständig genug, dass jemand ohne "
    "das Bild eine Aufgabe dazu stellen kann (Personen, Handlung, Ort; bei Schaltplänen jedes Bauteil und wie es "
    "geschaltet ist, in Reihe oder parallel, wo die Messgeräte sitzen; bei Diagrammen Achsen und Verlauf). Nichts "
    "erfinden, was nicht zu sehen ist. Ohne Abbildung: figures leer. Nur JSON im Schema: ")


def _valid_box(box: list[float]) -> list[float] | None:
    x0, y0, x1, y1 = (max(0.0, min(1.0, float(v))) for v in box)
    if x1 - x0 < MIN_SIDE or y1 - y0 < MIN_SIDE:
        return None
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def _page_label(row) -> str:
    label = (row["source_label"] or row["title"] or "Seite").strip()
    return f"{label} S. {row['source_page']}" if row["source_page"] else label


async def index(account_id: int, material_id: int) -> int:
    """Eine Seite ansehen und ihre Abbildungen ablegen. Gibt die Anzahl zurück."""
    from . import ai_gateway as ai
    from .materials import image_for_reading
    photo = image_for_reading(account_id, material_id)
    if not photo:
        _mark(account_id, material_id, 0, "kein Bild")
        return 0
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT subject_name,source_label,source_page,title FROM materials WHERE id=? AND account_id=?",
                        (material_id, account_id)).fetchone()
    if not row:
        return 0
    images = [{"type": "image_url", "page": True,
               "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(photo).decode(), "detail": "high"}}]
    try:
        raw, _, _ = await ai.complete(account_id, "background", INSTRUCTION + json.dumps(Scan.model_json_schema()),
                                      {"fach": row["subject_name"], "seite": _page_label(row)}, images, max_output=2500)
        scan = Scan.model_validate_json(raw)
    except (ValidationError, ValueError) as e:
        _mark(account_id, material_id, 0, f"unlesbar: {str(e)[:80]}")
        return 0
    kept = [(f, b) for f in scan.figures if (b := _valid_box(f.box))]
    with closing(webapp_conn()) as c, c:
        c.execute("DELETE FROM material_figures WHERE material_id=? AND account_id=?", (material_id, account_id))
        for i, (f, box) in enumerate(kept):
            c.execute("INSERT INTO material_figures(account_id,material_id,idx,kind,box_json,caption,description,created_at) "
                      "VALUES(?,?,?,?,?,?,?,?)", (account_id, material_id, i, f.kind, json.dumps(box), f.caption.strip(),
                                                  f.description.strip(), now_iso()))
    _mark(account_id, material_id, len(kept), None)
    return len(kept)


def _mark(account_id: int, material_id: int, count: int, error: str | None) -> None:
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT INTO material_figure_scans(material_id,account_id,scanned_at,count,error) VALUES(?,?,?,?,?) "
                  "ON CONFLICT(material_id) DO UPDATE SET scanned_at=excluded.scanned_at,count=excluded.count,error=excluded.error",
                  (material_id, account_id, now_iso(), count, error))


def pending(limit: int = PER_CYCLE) -> list[tuple[int, int]]:
    """Bildseiten ohne Verzeichnis, neueste zuerst; Fächer mit naher Arbeit vorn wäre schön, jüngste reicht."""
    marks = ",".join("?" * len(PAGE_KINDS))
    with closing(webapp_conn()) as c:
        return [(r[0], r[1]) for r in c.execute(
            f"SELECT m.account_id,m.id FROM materials m LEFT JOIN material_figure_scans s ON s.material_id=m.id "
            f"WHERE s.material_id IS NULL AND m.hidden=0 AND m.mime_type LIKE 'image/%' AND m.kind IN ({marks}) "
            f"ORDER BY m.id DESC LIMIT ?", (*PAGE_KINDS, limit))]


async def cycle(limit: int = PER_CYCLE) -> int:
    done = 0
    for account_id, material_id in pending(limit):
        try:
            done += await index(account_id, material_id) >= 0
        except Exception:
            LOG.info("Abbildungen von Material %s verschoben", material_id, exc_info=True)
            break  # etwa Rahmen aufgebraucht: später weiter
    return done


# ------------------------------------------------------------------ Lesen

def _rows(account_id: int, where: str, args: tuple) -> list[dict]:
    with closing(webapp_conn()) as c:
        return [dict(r) for r in c.execute(
            "SELECT f.id,f.material_id,f.kind,f.box_json,f.caption,f.description,m.source_label,m.source_page,m.title,m.subject_name "
            f"FROM material_figures f JOIN materials m ON m.id=f.material_id WHERE f.account_id=? AND m.hidden=0 AND {where} "
            "ORDER BY m.source_page,f.material_id,f.idx", (account_id, *args))]


def public(r: dict) -> dict:
    return {"id": r["id"], "material_id": r["material_id"], "kind": r["kind"], "caption": r["caption"],
            "beschreibung": r["description"], "seite": _page_label(r)}


def get(account_id: int, figure_id: int) -> dict | None:
    rows = _rows(account_id, "f.id=?", (figure_id,))
    return public(rows[0]) if rows else None


def for_materials(account_id: int, material_ids: list[int], kinds: tuple[str, ...] | None = None, limit: int = 12) -> list[dict]:
    if not material_ids:
        return []
    marks = ",".join("?" * len(material_ids))
    rows = _rows(account_id, f"f.material_id IN ({marks})", tuple(material_ids))
    return [public(r) for r in rows if not kinds or r["kind"] in kinds][:limit]


def for_subject(account_id: int, subject: str, kinds: tuple[str, ...] | None = None, limit: int = 12,
                prefer: list[int] | None = None) -> list[dict]:
    rows = [public(r) for r in _rows(account_id, "lower(m.subject_name)=lower(?)", (subject,)) if not kinds or r["kind"] in kinds]
    first = set(prefer or [])
    rows.sort(key=lambda f: (f["material_id"] not in first,))
    return rows[:limit]


def for_places(account_id: int, subject: str, places: list[dict], limit: int = 8) -> list[dict]:
    """Die Abbildungen der Seiten eines Themas (genannte Stellen, dann das Kapitel)."""
    from .lernstand import _matching_rows, chapter_pages_of
    try:
        hits = _matching_rows(account_id, subject, places)
        ids = [h["id"] for h in hits if h.get("id")]
        ids += [r["id"] for r in chapter_pages_of(account_id, subject, hits) if r.get("id") and r["id"] not in ids]
    except Exception:
        LOG.debug("Seiten zu den Stellen nicht bestimmbar", exc_info=True)
        return []
    return for_materials(account_id, ids, limit=limit)


def crop(account_id: int, figure_id: int, max_side: int = 1400) -> bytes | None:
    """Der Ausschnitt als JPEG, mit etwas Rand."""
    from PIL import Image
    from .materials import image_for_reading
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT material_id,box_json FROM material_figures WHERE id=? AND account_id=?", (figure_id, account_id)).fetchone()
    if not row:
        return None
    photo = image_for_reading(account_id, row["material_id"])
    if not photo:
        return None
    img = Image.open(io.BytesIO(photo))
    img = img.convert("RGB")
    w, h = img.size
    x0, y0, x1, y1 = json.loads(row["box_json"])
    pad = 0.015
    box = (int(max(0, x0 - pad) * w), int(max(0, y0 - pad) * h), int(min(1, x1 + pad) * w), int(min(1, y1 + pad) * h))
    part = img.crop(box)
    part.thumbnail((max_side, max_side))
    out = io.BytesIO()
    part.save(out, format="JPEG", quality=85)
    return out.getvalue()


def image_part(account_id: int, figure_id: int) -> dict | None:
    """Der Ausschnitt als Bildteil für einen Modellaufruf."""
    data = crop(account_id, figure_id)
    if not data:
        return None
    return {"type": "image_url", "page": True, "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(data).decode(), "detail": "high"}}


def data_uri(account_id: int, figure_id: int) -> str | None:
    data = crop(account_id, figure_id, 1000)
    return "data:image/jpeg;base64," + base64.b64encode(data).decode() if data else None
