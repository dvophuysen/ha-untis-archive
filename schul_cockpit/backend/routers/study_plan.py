"""Der Lern-Pflichtplan des Tages (D180). Eltern lesen mit und können ihn
anpassen (D214): weniger, mehr, einzelne Schritte streichen oder hinzufügen."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from .. import plan_adjust, request_cache, study_plan
from ..learning import InputModel, today_local
from ..auth import CurrentUser, get_current_user
from .learning import access

router = APIRouter()


@router.get("/accounts/{account_id}/study-plan/today")
def get_today(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    with request_cache.scope():
        return study_plan.today(account_id, user)


class AdjustIn(InputModel):
    day: date
    action: Literal["less", "more", "drop", "add", "reset"]
    key: str | None = None


def _allowed(account_id: int) -> list[dict]:
    return plan_adjust.days(account_id, today_local())


@router.get("/accounts/{account_id}/study-plan/adjust")
def get_adjust(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Die anpassbaren Tage mit Plan, Vorschlägen und Änderungen. Nur Eltern."""
    access(user, account_id, parent=True)
    with request_cache.scope():
        today = today_local()
        return {"days": [{**d, "day": d["day"].isoformat(), **plan_adjust.state(account_id, d["day"], today)}
                         for d in _allowed(account_id)]}


@router.post("/accounts/{account_id}/study-plan/adjust")
def post_adjust(account_id: int, body: AdjustIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, write=True, parent=True)
    allowed = {d["day"]: d for d in _allowed(account_id)}
    if body.day not in allowed:
        raise HTTPException(400, "Anpassen lässt sich nur der Plan von heute und vom nächsten Schultag.")
    if body.action in ("drop", "add") and not body.key:
        raise HTTPException(422, "Welcher Schritt?")
    with request_cache.scope():
        try:
            state = plan_adjust.change(account_id, body.day, today_local(), body.action, body.key, user.id)
        except LookupError as exc:
            raise HTTPException(409, str(exc)) from None
    return {**allowed[body.day], "day": body.day.isoformat(), **state}
