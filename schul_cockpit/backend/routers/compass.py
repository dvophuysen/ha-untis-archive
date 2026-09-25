"""Lernen als Kompass (D186): ein schlanker Aufruf für die Lernseite des Kindes."""
from fastapi import APIRouter, Depends

from .. import learning_compass
from ..auth import CurrentUser, get_current_user
from .learning import access

router = APIRouter()


@router.get("/accounts/{account_id}/learning/compass")
async def get_compass(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    return await learning_compass.build(account_id, user)
