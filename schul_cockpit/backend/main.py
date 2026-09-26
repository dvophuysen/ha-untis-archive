"""Schul-Cockpit FastAPI app — served behind HA Ingress."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
    parent_todo as parent_todo_router,
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
    rewards as rewards_router,
    profile as profile_router,
    practice as practice_router,
    study_plan as study_plan_router,
    compass as compass_router,
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
    vocab_daily as vocab_daily_router,
)
from .sync_worker import background_sync_loop
from .mentor_worker import background_loop as mentor_loop
from .materials_worker import background_loop as materials_loop

logging.basicConfig(level=getattr(logging, SETTINGS.log_level.upper(), logging.INFO))
_LOGGER = logging.getLogger("schul_cockpit")

import re as _re_mask  # noqa: E402

_TOKEN_IN_QUERY = _re_mask.compile(r"([?&]token=)[^&\s\"]*", _re_mask.IGNORECASE)


class MaskQueryTokens(logging.Filter):
    """Mitteilungs-Token aus dem Zugriffslog von uvicorn tilgen. HA-Automationen
    rufen /api/notify/… mit ?token= auf; das Add-on-Log zeigt jede Zeile im
    HA-Protokoll. Das Log selbst bleibt, es dient der Diagnose."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.args, tuple) and record.args:
                record.args = tuple(
                    _TOKEN_IN_QUERY.sub(r"\1***", a) if isinstance(a, str) else a for a in record.args)
            if isinstance(record.msg, str) and "token=" in record.msg.lower():
                record.msg = _TOKEN_IN_QUERY.sub(r"\1***", record.msg)
        except Exception:
            pass
        return True


# uvicorn richtet seine Logger ein, bevor es die App lädt; ein Filter am Logger
# bleibt danach bestehen.
logging.getLogger("uvicorn.access").addFilter(MaskQueryTokens())

_SCHEMA_OK: bool = False
_SCHEMA_ERROR: str | None = None
_BG_TASK: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _SCHEMA_OK, _SCHEMA_ERROR, _BG_TASK
    # Ein eingespieltes Backup wird vor dem ersten Öffnen der Datenbank
    # getauscht, nie im laufenden Betrieb (siehe backup.apply_pending_restore).
    from .backup import apply_pending_restore
    apply_pending_restore()
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

    from .textbook_catalog import scan_connected_accounts
    from .reminders import loop as reminder_loop
    from .backup import nightly_backup_loop
    from .source_collector import background_loop as sources_loop
    from .triggers import loop as triggers_loop
    _BG_TASK = _start("sync", background_sync_loop())
    tasks = [
        _BG_TASK,
        _start("mentor", mentor_loop()),
        _start("materials", materials_loop()),
        # Läuft einmal durch und endet dann regulär.
        _start("textbook_scan", scan_connected_accounts(), once=True),
        _start("reminders", reminder_loop()),
        _start("backup", nightly_backup_loop()),
        _start("sources", sources_loop()),
        _start("triggers", triggers_loop()),
        # Offene Übungsarbeiten ohne Prüfvermerk nachprüfen (D217).
        _start("paper_check", _paper_check(), once=True),
    ]
    # A process restart cannot leave a grading lease permanently stuck.
    from .db import webapp_conn
    with __import__("contextlib").closing(webapp_conn()) as c:
        c.execute("UPDATE mentor_exam_attempts SET status='submitted' WHERE status='grading'")
    # Unsicher gelesene Auswertungen zählen nie (D202): ältere einmal zurückstellen.
    try:
        from .routers.practice import hold_uncertain
        held = hold_uncertain()
        if held:
            _LOGGER.info("%s Übungsarbeit(en) mit unsicherer Auswertung zur Prüfung zurückgestellt", held)
    except Exception:
        _LOGGER.warning("Unsichere Auswertungen nicht geprüft", exc_info=True)
    _LOGGER.info("Background HA-todo sync loop started")
    try:
        yield
    finally:
        await _stop(tasks)


async def _paper_check() -> None:
    from .solution_check import recheck_open
    await recheck_open()


def _start(name: str, coro, *, once: bool = False) -> asyncio.Task:
    """Hintergrundschleife starten. Endet sie unerwartet, steht es im Log;
    bis 1.31 verschwand eine abgestürzte Schleife still."""
    task = asyncio.create_task(coro, name=f"sc:{name}")

    def done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            _LOGGER.error("Hintergrundaufgabe %s abgebrochen", name, exc_info=exc)
        elif not once:
            _LOGGER.warning("Hintergrundaufgabe %s hat unerwartet geendet", name)

    task.add_done_callback(done)
    return task


async def _stop(tasks: list[asyncio.Task]) -> None:
    """Alle Schleifen beenden. Bis 1.31 wurde jede einzeln abgewartet, und
    eine Schleife, die mit einem anderen Fehler endete, brach das
    Herunterfahren für alle folgenden ab."""
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Schul-Cockpit", lifespan=lifespan)


from . import view_mode as _view_mode  # noqa: E402

# Mitlesen, Kind am Elterngerät, Testmodus (D175).
app.middleware("http")(_view_mode.middleware)

# Ladezeiten messen statt schätzen: Jede Antwort trägt ihre Dauer im Kopf
# Server-Timing (sichtbar in den Entwicklerwerkzeugen), und was länger als
# SLOW_MS braucht, steht mit Pfad (ohne Query, also ohne Token) im Add-on-Log
# unter „langsam:“; ha_addon_log.py --grep langsam wertet es aus.
SLOW_MS = 500


@app.middleware("http")
async def measure(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - started) * 1000
    response.headers["Server-Timing"] = f"app;dur={ms:.0f}"
    if ms >= SLOW_MS and request.url.path.startswith("/api/"):
        _LOGGER.info("langsam: %s %s %.0f ms (%s)", request.method, request.url.path, ms, response.status_code)
    return response


# Pfade, die ihr Cookie selbst setzen oder löschen (Anmelden, Abmelden).
_OWN_COOKIE_PATHS = ("/api/auth/", "/kiosk/login")


def _sets_session_cookie(response) -> bool:
    prefix = f"{SESSION_COOKIE}="
    return any(v.lstrip().startswith(prefix) for v in response.headers.getlist("set-cookie"))


@app.middleware("http")
async def slide_pin_cookie(request: Request, call_next):
    """Refresh the PIN session cookie on every successful authenticated
    request, so the kid stays logged in indefinitely as long as they keep
    using the app.

    Verlängert wird nur, was tatsächlich per PIN-Sitzung angemeldet war
    (``request.state.auth_source`` aus auth.get_current_user, das auch der
    Kiosk benutzt), und nur mit genau dem Token, das dabei gegolten hat. Bis
    1.31 hängte die Middleware das eingehende Cookie an jede Antwort, auch an
    POST /kiosk/login: Ein altes, ungültiges Cookie überschrieb dort das
    frisch gesetzte, und die Anmeldung am Küchen-iPad lief ins Leere."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store"
    if path.startswith(_OWN_COOKIE_PATHS):
        return response
    state = request.state
    token = getattr(state, "pin_token", None) if getattr(state, "auth_source", None) == "pin" else None
    if token and 200 <= response.status_code < 400 and not _sets_session_cookie(response):
        is_https = (
            request.url.scheme == "https"
            or (request.headers.get("x-forwarded-proto") or "").lower() == "https"
        )
        response.set_cookie(
            SESSION_COOKIE,
            token,
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
app.include_router(compass_router.router, prefix=API)
app.include_router(vocab_router.router, prefix=API)
app.include_router(vocab_daily_router.router, prefix=API)
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
app.include_router(parent_todo_router.router, prefix=API)
app.include_router(rewards_router.router, prefix=API)
app.include_router(profile_router.router, prefix=API)
app.include_router(practice_router.router, prefix=API)
app.include_router(study_plan_router.router, prefix=API)
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


def _is_api(full_path: str) -> bool:
    """Unbekannte /api-Pfade bekommen 404 statt der App: Bis 1.31 antwortete
    ein Tippfehler im Pfad mit index.html und Status 200, und das Frontend
    scheiterte am JSON statt am Status. Die Seiten der App liegen hinter #/…"""
    return full_path == "api" or full_path.startswith("api/")


def _api_not_found():
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "Not Found"}, status_code=404, headers={"Cache-Control": "private, no-store"})


if _FRONTEND_DIR and (_FRONTEND_DIR / "index.html").exists():
    if (_FRONTEND_DIR / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=_FRONTEND_DIR / "assets"),
            name="assets",
        )

    @app.get("/{full_path:path}")
    def spa(full_path: str, request: Request):
        if _is_api(full_path):
            return _api_not_found()
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
        if _is_api(full_path):
            return _api_not_found()
        if _is_legacy_browser(request):
            return _RedirectResponse("/kiosk", status_code=302)
        return HTMLResponse(_PLACEHOLDER_HTML)
