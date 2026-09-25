"""Der Lern-Pflichtplan des Tages (D180). Eltern lesen nur mit."""
from fastapi import APIRouter, Depends

from .. import study_plan
from ..auth import CurrentUser, get_current_user
from .learning import access

router = APIRouter()


@router.get("/accounts/{account_id}/study-plan/today")
def get_today(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    return study_plan.today(account_id, user)
