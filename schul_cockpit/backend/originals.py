"""Die Originalfotos (D169).

Bis 1.14.5 blieb von einem Foto nur eine Kopie mit höchstens 1800 Pixeln; das
Original war beim Hochladen verloren. Für Handschrift, Graphen, Schaltskizzen
oder Noten zählt aber jedes Detail. Das Original liegt deshalb als Datei neben
der Datenbank, nicht in ihr: `/data/originals/<art>/<konto>/<id>.jpg`. Es wird
einmal neu geschrieben, aufrecht gedreht und ohne Metadaten, also auch ohne
den Aufnahmeort des Handys, und höchstens 6000 Pixel groß (mehr nimmt kein
Modell). Angezeigt wird weiter die kleine Kopie; das Original geht nur an die
Auswertung.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from . import db

LOG = logging.getLogger(__name__)
MAX_SIDE = 6000
MAX_PIXELS = 50_000_000
KINDS = ("material", "attachment", "exam_photo")


def _path(kind: str, account_id: int, item_id: int) -> Path:
    if kind not in KINDS:
        raise ValueError("Unbekannte Art")
    return db.SETTINGS.webapp_db_path.parent / "originals" / kind / str(int(account_id)) / f"{int(item_id)}.jpg"


def keep(kind: str, account_id: int, item_id: int, blob: bytes) -> bool:
    """Das Original ablegen. Ein Fehler hier darf kein Hochladen scheitern
    lassen: Dann bleibt es bei der Kopie wie bisher."""
    try:
        from PIL import Image, ImageOps
        image = Image.open(io.BytesIO(blob))
        if image.width * image.height > MAX_PIXELS:
            return False
        image.load()
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=92)
        path = _path(kind, account_id, item_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(out.getvalue())
        return True
    except Exception:
        LOG.warning("Original (%s %s) nicht abgelegt", kind, item_id, exc_info=True)
        return False


def load(kind: str, account_id: int, item_id: int) -> bytes | None:
    try:
        path = _path(kind, account_id, item_id)
        return path.read_bytes() if path.is_file() else None
    except (OSError, ValueError):
        return None


def best(kind: str, account_id: int, item_id: int, copy: bytes | None) -> bytes | None:
    """Das Original, wenn es eines gibt, sonst die gespeicherte Kopie."""
    return load(kind, account_id, item_id) or copy


def drop(kind: str, account_id: int, item_id: int) -> None:
    try:
        _path(kind, account_id, item_id).unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
