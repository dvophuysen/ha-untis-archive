"""Admin-only data safety: status, download, restore."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from ..auth import CurrentUser, get_current_user, require_admin
import asyncio

from ..backup import backup_now, backup_state, make_combined_zip, restore_from_file, status
from ..db import history_conn
from ..supervisor_client import SupervisorError, get_supervisor
from ..webclip import build_webclip, external_url_or_none

router = APIRouter()


@router.get("/admin/backup/status")
async def backup_status(user: CurrentUser = Depends(get_current_user)) -> dict:
    require_admin(user)
    st = await asyncio.to_thread(status)
    # Welche HA-Backups gibt es, und welche davon enthalten dieses Add-on?
    # Das automatische HA-Backup sichert nur die dort gewählten Add-ons.
    state = {"last_ha_backup": None, "last_addon_backup": None, "last_addon_backup_name": None,
             "addon_backups": 0, "nightly": None, "supervisor_error": None}
    sup = get_supervisor()
    if sup.available:
        try:
            info = await sup.self_info()
            data = await sup.list_backups()
            state = {**state, **backup_state(data.get("backups", []) or [], info.get("slug") or "")}
        except SupervisorError as exc:
            state["supervisor_error"] = str(exc)
    else:
        state["supervisor_error"] = "Supervisor nicht erreichbar"
    return {**st, **state}


@router.post("/admin/backup/ha-now")
async def backup_ha_now(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Jetzt ein HA-Teil-Backup dieses Add-ons anlegen, wie es die Nacht tut."""
    require_admin(user)
    try:
        return await backup_now("manual")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sicherung nicht angelegt: {exc}") from None


@router.get("/admin/backup/download")
async def backup_download(user: CurrentUser = Depends(get_current_user)):
    require_admin(user)
    # Im Thread: Der Schnappschuss darf den Server nicht anhalten.
    archive = await asyncio.to_thread(make_combined_zip)
    fname = "schul-cockpit-backup-" + datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M") + ".zip"
    return FileResponse(
        archive,
        media_type="application/zip",
        filename=fname,
        background=BackgroundTask(lambda: archive.unlink(missing_ok=True)),
        headers={"Cache-Control": "no-store"},
    )


@router.post("/admin/backup/restore")
async def backup_restore(
    user: CurrentUser = Depends(get_current_user),
    file: UploadFile = File(...),
) -> dict:
    require_admin(user)
    fd, tmp = tempfile.mkstemp(prefix="sc-restore-", suffix=".db")
    try:
        with os.fdopen(fd, "wb") as f:
            while chunk := await file.read(1 << 20):
                f.write(chunk)
        from pathlib import Path
        try:
            info = restore_from_file(Path(tmp))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    finally:
        # restore_from_file moves the temp file into place on success; only
        # clean up if it's still around (validation failure path).
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {
        "ok": True,
        "restart_required": True,
        **info,
    }


@router.get("/admin/webclip")
async def webclip(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Unsigned .mobileconfig that installs a full-screen home-screen icon
    for this child — handy under Screen Time → App Limits (Always Allowed)."""
    require_admin(user)
    base = external_url_or_none()
    if not base:
        raise HTTPException(
            status_code=400,
            detail="Bitte zuerst die externe URL in den Add-on-Optionen setzen.",
        )
    conn = history_conn()
    try:
        row = conn.execute(
            "SELECT name FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="account not found")
    name = row["name"]
    data = build_webclip(account_id, name, base)
    safe = "".join(ch for ch in name if ch.isalnum()) or str(account_id)
    # iOS has no download manager — `Content-Disposition: attachment` makes
    # Safari render a blank page instead of triggering Settings.app. Serve
    # the profile inline so the system installer picks up the MIME type.
    return Response(
        content=data,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'inline; filename="schul-cockpit-{safe}.mobileconfig"',
            "Cache-Control": "no-store",
        },
    )
