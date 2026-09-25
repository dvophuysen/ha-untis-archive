"""Serie, Abzeichen und Jahresmedaille (D172, D173)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from .. import rewards
from ..auth import CurrentUser, get_current_user
from ..learning import InputModel
from .learning import access

router = APIRouter()


class RewardSettingsIn(InputModel):
    bonus_until: str = Field(pattern=r"^\d{1,2}:\d{2}$")


@router.get("/accounts/{account_id}/rewards")
def get_rewards(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    return rewards.summary(account_id)


@router.put("/accounts/{account_id}/rewards/settings")
def put_settings(account_id: int, body: RewardSettingsIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    # Die Bonuszeit legen die Eltern fest.
    access(user, account_id, write=True, parent=True)
    try:
        return {"bonus_until": rewards.set_bonus_until(account_id, body.bonus_until)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
