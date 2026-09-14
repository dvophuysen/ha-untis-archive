"""School calendars read straight from IServ, with a role per calendar."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from .. import school_calendars as store
from ..auth import CurrentUser, assert_account_access, get_current_user
from .. import iserv_calendar, iserv_portal
from ..iserv_calendar import IservCalendarError
from ..iserv_connector import IservLoginError
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


@router.get("/{calendar_id}/inspect")
async def inspect(account_id: int, calendar_id: int,
                  user: CurrentUser = Depends(get_current_user)) -> dict:
    """Why a calendar stays empty: accepted query, entries sent, entries kept."""
    _parent(user, account_id)
    row = store.credentials(account_id)
    entry = next((c for c in store.calendars(account_id) if c["id"] == calendar_id), None)
    if row is None or entry is None:
        raise HTTPException(404, "Kalender oder Zugang nicht gefunden")
    from ..secret_store import decrypt_secret

    password = decrypt_secret(row["password_ciphertext"])
    today = date.today()
    try:
        result = await iserv_calendar.inspect(
            row["portal_url"], row["username"], password, entry["url"],
            today - timedelta(days=store.PAST_DAYS), today + timedelta(days=store.AHEAD_DAYS))
    except IservCalendarError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        password = ""
    return {"name": entry["name"], "rolle": entry["role"], **result}


def _credentials(account_id: int):
    row = store.credentials(account_id)
    if row is None:
        raise HTTPException(404, "Noch kein IServ-Zugang gespeichert")
    from ..secret_store import decrypt_secret

    return row, decrypt_secret(row["password_ciphertext"])


@router.get("/portal")
async def portal(account_id: int, browser: bool = False, paths: str | None = None,
                 user: CurrentUser = Depends(get_current_user)) -> dict:
    """Which modules of the IServ portal carry dates, and what they offer."""
    _parent(user, account_id)
    row, password = _credentials(account_id)
    wanted = tuple(p.strip() for p in (paths or "").split(",") if p.strip()) or iserv_portal.SEEDS
    try:
        if browser:
            return await iserv_portal.browse(row["portal_url"], row["username"], password, wanted)
        return await iserv_portal.survey(row["portal_url"], row["username"], password)
    except IservLoginError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        password = ""


@router.get("/portal/read")
async def portal_read(account_id: int, paths: str,
                      user: CurrentUser = Depends(get_current_user)) -> dict:
    """What the portal's own data addresses answer, from the logged-in page."""
    _parent(user, account_id)
    row, password = _credentials(account_id)
    wanted = tuple(p.strip() for p in paths.split(",") if p.strip())[:8]
    if not wanted:
        raise HTTPException(422, "Keine Adresse angegeben")
    try:
        return {"antworten": await iserv_portal.read(
            row["portal_url"], row["username"], password, wanted)}
    except IservLoginError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        password = ""


@router.get("/probe")
async def probe(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Structure of the CalDAV account, to see where shared calendars sit."""
    _parent(user, account_id)
    row = store.credentials(account_id)
    if row is None:
        raise HTTPException(404, "Noch kein IServ-Zugang gespeichert")
    from ..secret_store import decrypt_secret

    password = decrypt_secret(row["password_ciphertext"])
    try:
        return await iserv_calendar.probe(row["portal_url"], row["username"], password)
    except IservCalendarError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        password = ""
