"""Wochenrückblick: dieselben Zahlen für Kind und Eltern, ohne Modellaufruf."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from .. import week_review
from ..auth import CurrentUser, get_current_user
from .learning import access

router = APIRouter(prefix="/accounts/{account_id}/week-review")


def today_local() -> date:
    return date.today()


@router.get("")
async def get(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    return await week_review.review(account_id, today_local())
