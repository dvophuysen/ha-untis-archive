"""Nach der Schule: Foto oder „nichts Neues“. Eine Seite, zwei Möglichkeiten."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from .. import afternoon_check as check
from .. import material_analysis as analysis
from .. import materials as store
from ..auth import CurrentUser, get_current_user
from .learning import access

LOG = logging.getLogger("schul_cockpit.afternoon")
router = APIRouter(prefix="/accounts/{account_id}/afternoon-check")


async def _analyze(account_id: int, material_id: int) -> None:
    try:
        await analysis.analyze(account_id, material_id)
    except Exception:
        LOG.warning("Lesung des Fotos %s nach der Schule nicht möglich", material_id)


@router.get("")
def get(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    return check.state(account_id, check.now_local())


@router.post("/nothing")
def nothing(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, write=True)
    now = check.now_local()
    check.record(account_id, now.date().isoformat(), "nothing", user.id)
    return check.state(account_id, now)


@router.post("/photo")
async def photo(account_id: int, background: BackgroundTasks, file: UploadFile = File(...),
                user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, write=True)
    content = await file.read(store.MAX_FILE + 1)
    await file.close()
    if not content:
        raise HTTPException(422, "Die Datei ist leer.")
    if len(content) > store.MAX_FILE:
        raise HTTPException(413, "Die Datei ist größer als 12 MB.")
    mime = store.sniff(content)
    if not mime:
        raise HTTPException(415, "Bitte ein Foto (JPEG, PNG, WebP) oder ein PDF verwenden.")
    now = check.now_local()
    try:
        created = check.intake_photo(account_id, user.id, content, file.filename or "Foto", mime, now)
    except ValueError as exc:
        raise HTTPException(413, str(exc)) from None
    background.add_task(_analyze, account_id, created["material_id"])
    return {**created, "state": check.state(account_id, now)}
