"""School calendars read straight from IServ, with a role per calendar."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from .. import school_calendars as store
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..iserv_calendar import IservCalendarError
from ..learning import InputModel

router = APIRouter(prefix="/accounts/{account_id}/calendars", tags=["calendars"])


class RoleIn(InputModel):
    role: str = Field(max_length=10)


def _parent(user: CurrentUser, account_id: int) -> None:
    assert_account_access(user, account_id)
    if user.role not in {"parent", "admin"} and not user.is_admin:
        raise HTTPException(403, "Nur in der Elternansicht verfügbar")


@router.get("")
def index(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    _parent(user, account_id)
    return {
        "calendars": store.calendars(account_id),
        "roles": list(store.ROLES),
        "sync": store.state(account_id),
        "access_configured": store.credentials(account_id) is not None,
    }


@router.post("/sync")
async def refresh(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Rediscover the calendars and refresh the events of the used ones."""
    _parent(user, account_id)
    try:
        await store.sync(account_id)
    except IservCalendarError as exc:
        raise HTTPException(422, str(exc)) from None
    return index(account_id, user)


@router.put("/{calendar_id}/role")
def role(account_id: int, calendar_id: int, body: RoleIn,
         user: CurrentUser = Depends(get_current_user)) -> dict:
    _parent(user, account_id)
    try:
        changed = store.set_role(account_id, calendar_id, body.role)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if not changed:
        raise HTTPException(404, "Kalender nicht gefunden")
    return index(account_id, user)


@router.get("/events")
def events(account_id: int, start: str | None = None, end: str | None = None,
           role: str | None = "exam", user: CurrentUser = Depends(get_current_user)) -> dict:
    assert_account_access(user, account_id)
    today = date.today()
    return {"events": store.events(
        account_id,
        start or (today - timedelta(days=7)).isoformat(),
        end or (today + timedelta(days=120)).isoformat(),
        role=role or None)}
