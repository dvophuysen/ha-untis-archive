"""Schul-Cockpit FastAPI app — served behind HA Ingress."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import from_ingress
from .config import SETTINGS
from .pin_auth import SESSION_COOKIE, SESSION_TTL_DAYS
from .db import init_webapp_db
from .history_schema import SchemaMismatch, assert_compatible
from .reconcile import reconcile_all
from .routers import (
    absences,
    afternoon,
    afternoon_check as afternoon_check_router,
    audit,
    auth_router,
    backup as backup_router,
    calendars as calendars_router,
    checkins,
    courses as courses_router,
    dashboard as dashboard_router,
    exams,
    health,
    learning,
    materials as materials_router,
    mentor,
    mentor_exams,
    discovery,

    read_access,
    kiosk as kiosk_router,
    me,
    notify,
    oral,
    plan as plan_router,
    packing as packing_router,
    reminders as reminders_router,
    search,
    settings_router,
    setup,
    subjects,
    tasks,
    textbooks,
    today,
    week,
    week_review as week_review_router,
    usage as usage_router,
    vocab as vocab_router,
)
from .sync_worker import background_sync_loop
from .mentor_worker import background_loop as mentor_loop
from .materials_worker import background_loop as materials_loop

logging.basicConfig(level=getattr(logging, SETTINGS.log_level.upper(), logging.INFO))
_LOGGER = logging.getLogger("schul_cockpit")

_SCHEMA_OK: bool = False
_SCHEMA_ERROR: str | None = None
_BG_TASK: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _SCHEMA_OK, _SCHEMA_ERROR, _BG_TASK
    init_webapp_db()
    try:
        assert_compatible(str(SETTINGS.history_db_path))
        _SCHEMA_OK = True
        _LOGGER.info("history.db schema compatible")
    except SchemaMismatch as exc:
        _SCHEMA_ERROR = str(exc)
        _LOGGER.error("history.db schema check failed: %s", exc)

    # Keep references to history.db durable (handles a full integration
    # re-setup that re-numbers account/lesson ids). Best-effort.
    if _SCHEMA_OK:
        reconcile_all()

    # Welches Deployment über welchen Zugang läuft, steht nur im Log: die
    # Zuordnung ist Add-on-Konfiguration und taucht in der App nicht auf (D87).
    try:
        from .ai_gateway import endpoint_overview
        _LOGGER.info("KI-Zugänge: %s", endpoint_overview())
    except Exception:
        _LOGGER.warning("KI-Zugänge konnten nicht ermittelt werden", exc_info=True)

    _BG_TASK = asyncio.create_task(background_sync_loop())
    mentor_task = asyncio.create_task(mentor_loop())
    materials_task = asyncio.create_task(materials_loop())
    from .textbook_catalog import scan_connected_accounts
    textbook_scan_task = asyncio.create_task(scan_connected_accounts())
    from .reminders import loop as reminder_loop
    reminder_task = asyncio.create_task(reminder_loop())
    from .backup import nightly_backup_loop
    backup_task = asyncio.create_task(nightly_backup_loop())
    from .source_collector import background_loop as sources_loop
    sources_task = asyncio.create_task(sources_loop())
    from .triggers import loop as triggers_loop
    triggers_task = asyncio.create_task(triggers_loop())
    # A process restart cannot leave a grading lease permanently stuck.
    from .db import webapp_conn
    with __import__("contextlib").closing(webapp_conn()) as c:
        c.execute("UPDATE mentor_exam_attempts SET status='submitted' WHERE status='grading'")
    _LOGGER.info("Background HA-todo sync loop started")
    try:
        yield
    finally:
        textbook_scan_task.cancel()
        try:
            await textbook_scan_task
        except asyncio.CancelledError:
            pass
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            pass
        sources_task.cancel()
        try:
            await sources_task
        except asyncio.CancelledError:
            pass
        triggers_task.cancel()
        try:
            await triggers_task
        except asyncio.CancelledError:
            pass
        mentor_task.cancel()
        try:
            await mentor_task
        except asyncio.CancelledError:
            pass
        materials_task.cancel()
        try:
            await materials_task
        except asyncio.CancelledError:
            pass
        if _BG_TASK:
            _BG_TASK.cancel()
            try:
                await _BG_TASK
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(title="Schul-Cockpit", lifespan=lifespan)


from . import view_mode as _view_mode  # noqa: E402

# Mitlesen, Kind am Elterngerät, Testmodus (D175).
app.middleware("http")(_view_mode.middleware)


@app.middleware("http")
async def slide_pin_cookie(request: Request, call_next):
    """Refresh the PIN session cookie on every successful authenticated
    request, so the kid stays logged in indefinitely as long as they keep
    using the app. Skipped when the request authenticated via Ingress
    headers (HA-internal access doesn't need our cookie), and skipped on
    the auth routes themselves — login/logout set their own cookies and
    must not be overwritten by stale incoming-cookie values."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store"
    if path.startswith("/api/auth/"):
        return response
    cookie = request.cookies.get(SESSION_COOKIE)
    used_pin = cookie and not (request.headers.get("x-remote-user-id") and from_ingress(request))
    if used_pin and 200 <= response.status_code < 400:
        is_https = (
            request.url.scheme == "https"
            or (request.headers.get("x-forwarded-proto") or "").lower() == "https"
        )
        response.set_cookie(
            SESSION_COOKIE,
            cookie,
            max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
            httponly=True,
            samesite="lax",
            path="/",
            secure=is_https,
        )
    return response


API = "/api"
app.include_router(health.router, prefix=API)
app.include_router(learning.router, prefix=API)
app.include_router(mentor.router, prefix=API)
app.include_router(vocab_router.router, prefix=API)
app.include_router(materials_router.router, prefix=API)
app.include_router(calendars_router.router, prefix=API)
app.include_router(mentor_exams.router, prefix=API)
app.include_router(discovery.router, prefix=API)

app.include_router(read_access.router, prefix=API)
app.include_router(auth_router.router, prefix=API)
app.include_router(me.router, prefix=API)
app.include_router(setup.router, prefix=API)
app.include_router(today.router, prefix=API)
app.include_router(week.router, prefix=API)
app.include_router(week_review_router.router, prefix=API)
app.include_router(usage_router.router, prefix=API)
app.include_router(subjects.router, prefix=API)
app.include_router(search.router, prefix=API)
app.include_router(oral.router, prefix=API)
app.include_router(absences.router, prefix=API)
app.include_router(checkins.router, prefix=API)
app.include_router(tasks.router, prefix=API)
app.include_router(afternoon.router, prefix=API)
app.include_router(settings_router.router, prefix=API)
app.include_router(textbooks.router, prefix=API)
app.include_router(audit.router, prefix=API)
app.include_router(reminders_router.router, prefix=API)
app.include_router(afternoon_check_router.router, prefix=API)
app.include_router(notify.router, prefix=API)
app.include_router(exams.router, prefix=API)
app.include_router(plan_router.router, prefix=API)
app.include_router(packing_router.router, prefix=API)
app.include_router(courses_router.router, prefix=API)
app.include_router(backup_router.router, prefix=API)
app.include_router(dashboard_router.router, prefix=API)
# Kiosk-Routen leben außerhalb von /api, weil sie ganze HTML-Seiten
# liefern (Login-Form, Dashboard) und vom SPA-Catchall unterschieden
# werden müssen.
app.include_router(kiosk_router.router)


@app.get("/api/schema-status")
def schema_status() -> dict:
    return {"ok": _SCHEMA_OK, "error": _SCHEMA_ERROR}


# Serve the built frontend (or a placeholder if not built yet).
_FRONTEND_DIR: Path | None = SETTINGS.frontend_dir
_PLACEHOLDER_HTML = (
    "<!doctype html><html lang='de'><meta charset='utf-8'>"
    "<title>Schul-Cockpit</title>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<body style='font-family:system-ui;padding:2rem;max-width:40rem;margin:auto'>"
    "<h1>Schul-Cockpit läuft</h1>"
    "<p>Backend ist erreichbar. Frontend-Build noch nicht vorhanden.</p>"
    "<p>API: <a href='./api/health'>/api/health</a> · "
    "<a href='./api/me'>/api/me</a></p>"
    "</body></html>"
)


# Files that must never be cached by Cloudflare or the browser, otherwise
# a stale service worker / index.html keeps serving old code forever. The
# hashed /assets/* bundles get the opposite treatment (immutable, 1 year).
_NO_CACHE = {"index.html", "sw.js", "manifest.webmanifest"}
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}
_IMMUTABLE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}

# iOS-Versions-Match im User-Agent — alles vor iOS 13 kann den modernen
# Svelte-Bundle (Optional Chaining, Nullish Coalescing, color-mix) nicht
# parsen. Diese Geräte schicken wir auf den server-gerenderten Kiosk.
import re as _re
_LEGACY_IOS_RE = _re.compile(r"CPU (?:iPhone )?OS (\d+)_")


def _is_legacy_browser(request: Request) -> bool:
    ua = request.headers.get("user-agent", "") or ""
    m = _LEGACY_IOS_RE.search(ua)
    return bool(m and int(m.group(1)) < 13)


def frontend_file(root: Path, full_path: str) -> Path | None:
    """Die Datei unterhalb des Frontend-Verzeichnisses, sonst None. Ein
    absoluter Pfad („//data/options.json") oder „..“ darf nie hinausführen:
    Über den Direktport ist diese Route ohne Anmeldung erreichbar."""
    if not full_path:
        return None
    base = root.resolve()
    try:
        target = (base / full_path.lstrip("/")).resolve()
    except (OSError, ValueError):
        return None
    if not target.is_relative_to(base) or not target.is_file():
        return None
    return target


if _FRONTEND_DIR and (_FRONTEND_DIR / "index.html").exists():
    if (_FRONTEND_DIR / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=_FRONTEND_DIR / "assets"),
            name="assets",
        )

    @app.get("/{full_path:path}")
    def spa(full_path: str, request: Request):
        target = frontend_file(_FRONTEND_DIR, full_path)
        if target is not None:
            name = target.name
            if name in _NO_CACHE:
                return FileResponse(target, headers=_NO_CACHE_HEADERS)
            if "/assets/" in f"/{full_path}":
                return FileResponse(target, headers=_IMMUTABLE_HEADERS)
            return FileResponse(target)
        # SPA fallback — moderne Browser kriegen index.html, altes
        # iOS-Safari schicken wir auf den server-gerenderten Kiosk,
        # damit das Küchen-iPad nicht auf einer leeren weißen Seite
        # landet.
        if _is_legacy_browser(request):
            from fastapi.responses import RedirectResponse
            return RedirectResponse("/kiosk", status_code=302)
        return FileResponse(
            _FRONTEND_DIR / "index.html", headers=_NO_CACHE_HEADERS
        )

else:
    from fastapi.responses import HTMLResponse, RedirectResponse as _RedirectResponse

    @app.get("/{full_path:path}")
    def placeholder(full_path: str, request: Request):  # noqa: ARG001
        if _is_legacy_browser(request):
            return _RedirectResponse("/kiosk", status_code=302)
        return HTMLResponse(_PLACEHOLDER_HTML)
