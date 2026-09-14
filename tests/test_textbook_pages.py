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
from backend.textbook_browser import PageShot, TextbookScanError


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
            " VALUES(1,'https://beispiel-iserv.de','kind_a',?,'catalog_ready','2026-09-01','2026-09-01')",
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


async def test_all_pages_delivered_are_reported_as_loaded(env, monkeypatch):
    seed()
    calls = []

    async def capture(portal, user, password, title, pages, launch_url=None):
        calls.append((title, list(pages), launch_url))
        return [PageShot(page, png(page)) for page in pages], ""

    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Politik", "Buch, S. 30-31 lesen")
    assert context["status"] == "loaded"
    assert context["pages"] == [30, 31] and context["delivered_pages"] == [30, 31]
    assert "missing_pages" not in context and parts and parts[0]["type"] == "image_url"
    assert calls == [("Politik & Co. Niedersachsen 8", [30, 31], "https://viewer.example/buch/42")]


async def test_known_pages_come_from_the_cache_without_a_second_browser_run(env, monkeypatch):
    seed()
    runs = []

    async def capture(portal, user, password, title, pages, launch_url=None):
        runs.append(list(pages))
        return [PageShot(page, png(page)) for page in pages], ""

    monkeypatch.setattr(ctx, "capture_pages", capture)
    await ctx.homework_page_images(1, "Politik", "Buch, S. 30-31 lesen")
    _, context = await ctx.homework_page_images(1, "Politik", "Buch, S. 30-32 lesen")
    assert context["status"] == "loaded"
    # Only the page that was missing gets fetched again.
    assert runs == [[30, 31], [32]]


async def test_unreachable_page_hands_over_the_open_view_instead_of_nothing(env, monkeypatch):
    seed()

    async def capture(portal, user, password, title, pages, launch_url=None):
        return [PageShot(None, png(7))], "Seitennavigation nicht gefunden"

    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Politik", "Aufgabe 1 auf S. 34")
    assert context["status"] == "open_page"
    assert context["missing_pages"] == [34] and "delivered_pages" not in context
    assert context["detail"] == "Seitennavigation nicht gefunden"
    assert len(parts) == 1


async def test_viewer_error_keeps_the_stage_for_the_parent_view(env, monkeypatch):
    seed()

    async def capture(portal, user, password, title, pages, launch_url=None):
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

    async def capture(portal, user, password, title, pages, launch_url=None):
        return [PageShot(30, png(30))], "Nicht alle Seiten erreichbar"

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

    async def capture(portal, user, password, title, pages, launch_url=None):
        return [PageShot(pages[0], png(34))], ""

    monkeypatch.setattr(ctx, "capture_pages", capture)
    app = FastAPI()
    app.include_router(textbooks.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    patch.setattr(textbooks, "webapp_conn", db.webapp_conn)
    with TestClient(app) as isolated:
        answer = isolated.post(
            f"/api/accounts/1/textbooks/catalog/{book_id}/page-test", json={"page": 34}
        )
        assert answer.status_code == 200
        body = answer.json()
        assert body["status"] == "loaded" and body["page"] == 34 and body["shown_page"] == 34
        assert body["image"].startswith("data:image/jpeg;base64,")
        assert "geheim" not in answer.text
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
