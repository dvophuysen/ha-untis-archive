"""Eine hohe Heftseite geht in Streifen zum Modell, jeder unverkleinert (D168)."""
import io

from PIL import Image

from backend import ai_gateway as ai
from backend import material_analysis as analysis


def photo(width, height):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


def sizes(blobs):
    return [Image.open(io.BytesIO(b)).size for b in blobs]


def test_a_tall_page_becomes_overlapping_strips_that_keep_their_resolution():
    parts = sizes(analysis.strips(photo(1286, 1800)))
    assert len(parts) == 3 and all(w == 1286 and h <= 768 for w, h in parts)
    # Überlappung: zusammen länger als die Seite, keine Zeile fällt zwischen zwei Streifen.
    assert sum(h for _, h in parts) > 1800
    landscape = sizes(analysis.strips(photo(1800, 1286)))
    assert len(landscape) == 2 and all(h <= 768 for _, h in landscape)
    assert len(analysis.strips(photo(700, 900))) == 1
    assert len(analysis.strips(photo(1286, 4000))) == analysis.MAX_STRIPS


def test_the_reading_gets_the_strips_and_is_told_so(monkeypatch):
    seen = {}

    async def complete(account_id, purpose, instruction, context, images, **kw):
        seen.update(purpose=purpose, context=context, images=images)
        return analysis.Insight(kind="book_page", title="S. 104", confidence=0.9).model_dump_json(), {}, "k"

    monkeypatch.setattr(ai, "complete", complete)
    monkeypatch.setattr(analysis, "_context", lambda conn, account_id, row: {"hinweise": {}})
    row = {"file_bytes": photo(1286, 1800), "mime_type": "image/jpeg", "content_text": "", "kind": "book_page",
           "origin": "upload", "source_label": None}
    import asyncio
    asyncio.run(analysis.extract(1, row))
    assert len(seen["images"]) == 3 and "Streifen" in seen["context"]["ansicht"]
    assert ai.MAX_IMAGES.get(seen["purpose"], 2) >= 3
