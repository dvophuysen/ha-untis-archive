"""Seitenbilder in bestmöglicher Auflösung (D169): das Original behalten und je
Modell so schicken, dass jedes Detail ankommt."""
import asyncio
import base64
import io
import json

import httpx
from PIL import Image

from test_learning import env  # noqa: F401
from backend import ai_gateway as ai
from backend import material_analysis as analysis
from backend import originals


def photo(width, height, color="white"):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def dims(parts):
    return [Image.open(io.BytesIO(base64.b64decode(p["image_url"]["url"].split(",", 1)[1]))).size for p in parts]


def test_a_tile_model_gets_an_overview_and_native_resolution_crops():
    parts, counts = ai.page_images([Image.new("RGB", (3024, 4032))], "gpt-5-mini")
    sizes = dims(parts)
    assert counts == [5] and max(sizes[0]) <= 2048
    # Jeder Ausschnitt kommt unverkleinert an: kurze Seite höchstens 768, lange höchstens 2048.
    assert all(min(s) <= 768 and max(s) <= 2048 for s in sizes[1:])
    # Zusammen decken die Ausschnitte die ganze Höhe mit Überlappung ab.
    assert sum(h for _, h in sizes[1:]) > sizes[1][0] * 4 / 3
    assert all(p["image_url"]["detail"] == "high" for p in parts)
    # Ein kleines Bild kommt ohnehin unverkleinert an.
    assert ai.page_images([Image.new("RGB", (700, 900))], "gpt-5-mini")[1] == [1]
    # Viele Seiten: weniger Ausschnitte, nie mehr als die Obergrenze.
    many = ai.page_images([Image.new("RGB", (3024, 4032))] * 4, "gpt-5-mini")[1]
    assert sum(many) <= ai.MAX_PAGE_IMAGES


def test_a_newer_model_gets_the_original_as_one_image():
    parts, counts = ai.page_images([Image.new("RGB", (4032, 3024))], "gpt-5.6-terra")
    (width, height), = dims(parts)
    assert counts == [1] and parts[0]["image_url"]["detail"] == "auto"
    assert width * height <= ai.WHOLE_PIXELS and width > 3000
    assert [ai.vision_style(m) for m in ("gpt-5-mini", "gpt-5.1", "gpt-4o", "gpt-5.4-mini", "gpt-6-luna")] == \
        ["tile", "tile", "tile", "whole", "whole"]


def test_the_gateway_expands_pages_tells_the_model_and_books_realistically(monkeypatch):
    sent, booked = {}, {}
    monkeypatch.setattr(ai, "tier_for", lambda purpose, cfg=None, override=None: "klein")
    monkeypatch.setattr(ai, "settings_for", lambda tier: {"url": "https://x.example/openai/v1/responses", "key": "k",
                                                          "model": "gpt-5-mini", "deployment": "d"})
    monkeypatch.setattr(ai, "reserve", lambda account, purpose, sid, input_max, output_max, settings=None:
                        booked.setdefault("input", input_max) and "key")
    monkeypatch.setattr(ai, "settle", lambda key, result=None, error=None: None)

    class Client:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            sent.update(json)
            body = {"status": "completed", "usage": {"input_tokens": 10, "output_tokens": 1},
                    "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "{}"}]}]}
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(ai.httpx, "AsyncClient", Client)
    page = {"type": "image_url", "page": True, "image_url": {
        "url": "data:image/jpeg;base64," + base64.b64encode(photo(3024, 4032)).decode(), "detail": "high"}}
    asyncio.run(ai.complete(1, "background", "lies", {"hinweise": {}}, [page]))
    content = sent["input"][0]["content"]
    images = [c for c in content if c["type"] == "input_image"]
    note = json.loads(content[0]["text"])["bildaufbau"]
    assert len(images) == 5 and all(i["detail"] == "high" for i in images)
    assert "Bilder 2 bis 5" in note and "Ausschnitte" in note
    # Gebucht wird nach der Bildgröße, nicht pauschal 32.768 Token je Bild.
    assert booked["input"] < 5 * 32768


def test_originals_are_kept_without_metadata_and_preferred_for_reading(env):
    client, state, patch = env
    big = photo(4032, 3024, "gray")
    assert originals.keep("material", 1, 77, big)
    kept = originals.load("material", 1, 77)
    image = Image.open(io.BytesIO(kept))
    assert image.size == (4032, 3024) and not image.getexif()
    assert originals.best("material", 1, 77, b"kopie") == kept
    assert originals.best("material", 1, 78, b"kopie") == b"kopie"
    row = {"id": 77, "account_id": 1, "file_bytes": photo(1800, 1350), "mime_type": "image/jpeg", "content_text": ""}
    parts, _ = analysis._parts(row)
    assert parts[0]["page"] and dims(parts) == [(4032, 3024)]
    originals.drop("material", 1, 77)
    assert originals.load("material", 1, 77) is None
