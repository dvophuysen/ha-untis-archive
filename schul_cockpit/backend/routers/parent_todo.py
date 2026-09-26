"""„Erledigen“: offene Punkte für Eltern, je Kind gruppiert (D183)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import parent_todo, request_cache
from ..auth import CurrentUser, get_current_user, linked_account_ids
from ..learning import today_local
from ..view_mode import acts_as_parent

router = APIRouter()


@router.get("/parent/todo")
async def todo(user: CurrentUser = Depends(get_current_user)) -> dict:
    # Nur in der eigenen Elternansicht; beim Mitlesen und im Kindmodus nicht.
    if not acts_as_parent(user):
        raise HTTPException(403, "Nur für Eltern")
    with request_cache.scope():
        return await parent_todo.collect(user, sorted(linked_account_ids(user.id)), today_local())
