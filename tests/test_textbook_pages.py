"""Page delivery for the homework mentor: cache, status and reported stage."""

from contextlib import closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_learning import env  # noqa: F401  (fixture)
from backend import db, textbook_context as ctx
from backend.auth import get_current_user
from backend.routers import textbooks
from backend.secret_store import encrypt_secret
from backend.textbook_browser import CaptureResult, PageShot, TextbookScanError


def seed(title="Politik & Co. Niedersachsen 8", subject="Politik"):
    with closing(db.webapp_conn()) as conn:
        conn.execute(
            "INSERT INTO digital_textbook_catalog(account_id,title,provider,launch_url,subject_name,discovered_at)"
            " VALUES(1,?,?,?,?,'2026-09-01T00:00:00+00:00')",
            (title, "bibox.de", "https://viewer.example/buch/42", subject.lower()),
        )
        conn.execute(
            "INSERT INTO digital_textbook_credentials"
            "(account_id,portal_url,username,password_ciphertext,verification_status,created_at,updated_at)"
            " VALUES(1,'https://gaw-iserv.de','noah',?,'catalog_ready','2026-09-01','2026-09-01')",
            (encrypt_secret("geheim"),),
        )
        return conn.execute("SELECT id FROM digital_textbook_catalog WHERE account_id=1").fetchone()[0]


def png(marker):
    # Smallest thing Pillow accepts, distinguishable per page.
    from PIL import Image
    import io
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (marker, marker, marker)).save(out, "PNG")
    return out.getvalue()


def outcome(isolated, book_id, page, timeout=10.0):
    """Start the parent page test and poll until it is done."""
    import time
    started = isolated.post(f"/api/accounts/1/textbooks/catalog/{book_id}/page-test", json={"page": page})
    assert started.status_code == 202 and started.json()["state"] == "running"
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        state = isolated.get(f"/api/accounts/1/textbooks/catalog/{book_id}/page-test").json()
        if state["state"] == "done":
            return state["result"]
        time.sleep(0.05)
    raise AssertionError("page test never finished")


async def test_all_pages_delivered_are_reported_as_loaded(env, monkeypatch):
    seed()
    calls = []

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        calls.append((title, list(pages), launch_url))
        return CaptureResult(shots=[PageShot(page, png(page)) for page in pages])

    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Politik", "Buch, S. 30-31 lesen")
    assert context["status"] == "loaded"
    assert context["pages"] == [30, 31] and context["delivered_pages"] == [30, 31]
    assert "missing_pages" not in context and parts and parts[0]["type"] == "image_url"
    assert calls == [("Politik & Co. Niedersachsen 8", [30, 31], "https://viewer.example/buch/42")]


async def test_known_pages_come_from_the_cache_without_a_second_browser_run(env, monkeypatch):
    seed()
    runs = []

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        runs.append(list(pages))
        return CaptureResult(shots=[PageShot(page, png(page)) for page in pages])

    monkeypatch.setattr(ctx, "capture_pages", capture)
    await ctx.homework_page_images(1, "Politik", "Buch, S. 30-31 lesen")
    _, context = await ctx.homework_page_images(1, "Politik", "Buch, S. 30-32 lesen")
    assert context["status"] == "loaded"
    # Only the page that was missing gets fetched again.
    assert runs == [[30, 31], [32]]


async def test_unreachable_page_hands_over_the_open_view_instead_of_nothing(env, monkeypatch):
    seed()

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        return CaptureResult(shots=[PageShot(None, png(7))], note="Seitennavigation nicht gefunden")

    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Politik", "Aufgabe 1 auf S. 34")
    assert context["status"] == "open_page"
    assert context["missing_pages"] == [34] and "delivered_pages" not in context
    assert context["detail"] == "Seitennavigation nicht gefunden"
    assert len(parts) == 1


async def test_viewer_error_keeps_the_stage_for_the_parent_view(env, monkeypatch):
    seed()

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        raise TextbookScanError(
            "Die angegebenen Buchseiten konnten nicht geöffnet werden (Buch öffnen)", "Buch öffnen"
        )

    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Politik", "Lies S. 34")
    assert parts == [] and context["status"] == "viewer_error"
    assert context["stage"] == "Buch öffnen"
    recorded = ctx.last_fetch(1)
    assert recorded["status"] == "viewer_error" and recorded["stage"] == "Buch öffnen"
    assert recorded["pages"] == [34] and recorded["delivered"] == 0


async def test_partial_delivery_names_the_missing_pages(env, monkeypatch):
    seed()

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        return CaptureResult(shots=[PageShot(30, png(30))], note="Nicht alle Seiten erreichbar")

    monkeypatch.setattr(ctx, "capture_pages", capture)
    _, context = await ctx.homework_page_images(1, "Politik", "Buch, S. 30-32")
    assert context["status"] == "partial"
    assert context["delivered_pages"] == [30] and context["missing_pages"] == [31, 32]


async def test_without_a_matching_book_nothing_is_fetched(env, monkeypatch):
    seed(subject="Politik")

    async def capture(*args, **kwargs):
        raise AssertionError("must not start a browser")

    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Mathematik", "Buch, S. 30")
    assert parts == [] and context["status"] == "not_configured"


def test_parent_page_test_reports_the_stage_and_a_preview(env, monkeypatch):
    client, state, patch = env
    book_id = seed()

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        assert survey is True, "the parent page test always collects diagnostics"
        return CaptureResult(
            shots=[PageShot(pages[0], png(34))],
            controls=[{"tag": "button", "label": "Nächste Seite", "visible": True, "frame": 1}],
            documents=[{"frame": 1, "url": "/reader#/page/1", "title": "click & study"}],
            window_image=png(9),
        )

    monkeypatch.setattr(ctx, "capture_pages", capture)
    app = FastAPI()
    app.include_router(textbooks.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    patch.setattr(textbooks, "webapp_conn", db.webapp_conn)
    with TestClient(app) as isolated:
        body = outcome(isolated, book_id, 34)
        assert body["status"] == "loaded" and body["page"] == 34 and body["shown_page"] == 34
        assert body["image"].startswith("data:image/jpeg;base64,")
        assert body["window_image"].startswith("data:image/jpeg;base64,")
        assert body["controls"] == [
            {"tag": "button", "label": "Nächste Seite", "visible": True, "frame": 1}
        ]
        assert body["documents"][0]["url"] == "/reader#/page/1"
        assert "geheim" not in str(body)
        catalog = isolated.get("/api/accounts/1/textbooks/catalog").json()
        assert catalog["last_fetch"]["status"] == "loaded"
        assert catalog["last_fetch"]["pages"] == [34]


def test_page_test_rejects_a_book_of_another_child(env):
    client, state, patch = env
    seed()
    with closing(db.webapp_conn()) as conn:
        conn.execute(
            "INSERT INTO digital_textbook_catalog(account_id,title,provider,launch_url,subject_name,discovered_at)"
            " VALUES(2,'Fremdes Buch',NULL,NULL,'politik','2026-09-01T00:00:00+00:00')"
        )
        other = conn.execute("SELECT id FROM digital_textbook_catalog WHERE account_id=2").fetchone()[0]
    app = FastAPI()
    app.include_router(textbooks.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    patch.setattr(textbooks, "webapp_conn", db.webapp_conn)
    with TestClient(app) as isolated:
        assert isolated.post(
            f"/api/accounts/1/textbooks/catalog/{other}/page-test", json={"page": 12}
        ).status_code == 404


async def test_an_unexpected_failure_does_not_break_the_conversation(env, monkeypatch):
    seed()

    async def capture(*args, **kwargs):
        raise ValueError("kaputter Treiber")

    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Politik", "Lies S. 34")
    assert parts == [] and context["status"] == "viewer_error"
    assert context["stage"] == "Seitenabruf"
    # Only the error class travels on, never the message or any credential.
    assert context["detail"] == "ValueError" and "Treiber" not in str(context)


def test_an_empty_viewer_shell_is_recognised_as_blank():
    """Toolbar and icons alone are not a book page. Calibrated on real
    captures: an empty BiBox shell has about 1 % foreground, a page 30 %."""
    from PIL import Image, ImageDraw
    import io
    from backend.textbook_browser import looks_blank

    shell = Image.new("RGB", (1400, 930), (245, 245, 245))
    draw = ImageDraw.Draw(shell)
    for x in range(20, 1380, 140):  # a row of small toolbar icons
        draw.rectangle((x, 880, x + 24, 904), fill=(40, 60, 80))
    out = io.BytesIO(); shell.save(out, "PNG")
    assert looks_blank(out.getvalue())

    page = shell.copy()
    draw = ImageDraw.Draw(page)
    for y in range(80, 820, 22):  # lines of text
        draw.rectangle((120, y, 1280, y + 9), fill=(30, 30, 30))
    out = io.BytesIO(); page.save(out, "PNG")
    assert not looks_blank(out.getvalue())
    assert looks_blank(b"kein Bild") is False


def test_page_test_passes_the_viewer_diagnostics_through(env, monkeypatch):
    client, state, patch = env
    book_id = seed()

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        return CaptureResult(
            shots=[PageShot(pages[0], png(34))],
            diagnostics={"blank_first": True, "blank_after_wait": True, "waited": 15.2, "webgl": False,
                         "failed": [{"url": "bibox2.westermann.de/v2/…/image", "status": 0}],
                         "page_areas": [{"label": "Seite 18", "w": 0, "h": 0}],
                         "console": [{"level": "SEVERE", "text": "WebGL unavailable"}]},
        )

    monkeypatch.setattr(ctx, "capture_pages", capture)
    app = FastAPI()
    app.include_router(textbooks.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    patch.setattr(textbooks, "webapp_conn", db.webapp_conn)
    with TestClient(app) as isolated:
        body = outcome(isolated, book_id, 18)
    assert body["diagnostics"]["blank_after_wait"] is True
    assert body["diagnostics"]["page_areas"][0]["label"] == "Seite 18"
    assert body["diagnostics"]["console"][0]["level"] == "SEVERE"


def test_a_failed_run_still_reports_where_it_stopped(env, monkeypatch):
    """The Politik book fails before any page: the parents should still see
    the shelf the browser was looking at."""
    client, state, patch = env
    book_id = seed()

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        exc = TextbookScanError("Das Medienregal wurde nicht gefunden", "Eduplaces öffnen")
        exc.survey = CaptureResult(
            controls=[{"tag": "a", "text": "click & study", "visible": True, "frame": 0}],
            documents=[{"frame": 0, "url": "/iserv/eduplacesconnector/", "title": "Eduplaces"}],
            window_image=png(7), diagnostics={"stage": "Eduplaces öffnen", "console": []},
        )
        raise exc

    monkeypatch.setattr(ctx, "capture_pages", capture)
    app = FastAPI()
    app.include_router(textbooks.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    patch.setattr(textbooks, "webapp_conn", db.webapp_conn)
    with TestClient(app) as isolated:
        body = outcome(isolated, book_id, 30)
    assert body["status"] == "viewer_error" and body["stage"] == "Eduplaces öffnen"
    assert body["controls"][0]["text"] == "click & study"
    assert body["window_image"].startswith("data:image/jpeg;base64,")
    assert body["diagnostics"]["stage"] == "Eduplaces öffnen"


def test_a_second_page_test_waits_for_the_running_one(env, monkeypatch):
    """One browser per book at a time; a second click reports the running job."""
    import asyncio
    client, state, patch = env
    book_id = seed()
    gate = {"release": None}

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False):
        while not gate["release"]:
            await asyncio.sleep(0.01)
        return CaptureResult(shots=[PageShot(pages[0], png(12))])

    monkeypatch.setattr(ctx, "capture_pages", capture)
    app = FastAPI()
    app.include_router(textbooks.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    patch.setattr(textbooks, "webapp_conn", db.webapp_conn)
    with TestClient(app) as isolated:
        first = isolated.post(f"/api/accounts/1/textbooks/catalog/{book_id}/page-test", json={"page": 12}).json()
        second = isolated.post(f"/api/accounts/1/textbooks/catalog/{book_id}/page-test", json={"page": 99}).json()
        assert first["state"] == "running" and second["page"] == 12, "the running job is reported, not a new one"
        assert isolated.get(f"/api/accounts/1/textbooks/catalog/{book_id}/page-test").json()["state"] == "running"
        gate["release"] = True
        body = None
        import time
        end = time.monotonic() + 5
        while time.monotonic() < end:
            got = isolated.get(f"/api/accounts/1/textbooks/catalog/{book_id}/page-test").json()
            if got["state"] == "done":
                body = got["result"]
                break
            time.sleep(0.05)
        assert body and body["status"] == "loaded" and body["page"] == 12


def test_the_browser_check_runs_in_the_background_and_reports_each_variant(env, monkeypatch):
    client, state, patch = env
    from backend import textbook_browser as browser

    def probe(seconds=40.0):
        return {"version": "Chromium 126", "variants": [
            {"variant": "ohne GPU", "result": "RESULT webgl=false", "seconds": 1.2, "stderr": []},
            {"variant": "SwiftShader", "result": "Zeitlimit", "seconds": 40.0, "stderr": ["gpu_process_host.cc: GPU process exited"]},
        ]}

    monkeypatch.setattr(browser, "probe_browser", probe)
    app = FastAPI()
    app.include_router(textbooks.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    patch.setattr(textbooks, "webapp_conn", db.webapp_conn)
    import time
    with TestClient(app) as isolated:
        assert isolated.post("/api/accounts/1/textbooks/browser-check").status_code == 202
        end = time.monotonic() + 5
        got = None
        while time.monotonic() < end:
            got = isolated.get("/api/accounts/1/textbooks/browser-check").json()
            if got["state"] == "done":
                break
            time.sleep(0.05)
    assert got["state"] == "done"
    assert [v["variant"] for v in got["result"]["variants"]] == ["ohne GPU", "SwiftShader"]
    assert got["result"]["variants"][1]["result"] == "Zeitlimit"
