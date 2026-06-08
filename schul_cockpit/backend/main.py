"""Schul-Cockpit FastAPI app — served behind HA Ingress."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import SETTINGS
from .db import init_webapp_db
from .history_schema import SchemaMismatch, assert_compatible
from .routers import (
    afternoon,
    audit,
    checkins,
    health,
    me,
    oral,
    search,
    settings_router,
    setup,
    subjects,
    tasks,
    today,
    week,
)
from .sync_worker import background_sync_loop

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

    _BG_TASK = asyncio.create_task(background_sync_loop())
    _LOGGER.info("Background HA-todo sync loop started")
    try:
        yield
    finally:
        if _BG_TASK:
            _BG_TASK.cancel()
            try:
                await _BG_TASK
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(title="Schul-Cockpit", lifespan=lifespan)

API = "/api"
app.include_router(health.router, prefix=API)
app.include_router(me.router, prefix=API)
app.include_router(setup.router, prefix=API)
app.include_router(today.router, prefix=API)
app.include_router(week.router, prefix=API)
app.include_router(subjects.router, prefix=API)
app.include_router(search.router, prefix=API)
app.include_router(oral.router, prefix=API)
app.include_router(checkins.router, prefix=API)
app.include_router(tasks.router, prefix=API)
app.include_router(afternoon.router, prefix=API)
app.include_router(settings_router.router, prefix=API)
app.include_router(audit.router, prefix=API)


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


if _FRONTEND_DIR and (_FRONTEND_DIR / "index.html").exists():
    if (_FRONTEND_DIR / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=_FRONTEND_DIR / "assets"),
            name="assets",
        )

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        target = _FRONTEND_DIR / full_path
        if full_path and target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(_FRONTEND_DIR / "index.html")

else:
    from fastapi.responses import HTMLResponse

    @app.get("/{full_path:path}")
    def placeholder(full_path: str):  # noqa: ARG001
        return HTMLResponse(_PLACEHOLDER_HTML)
