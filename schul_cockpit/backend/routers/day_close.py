"""Ein Knopf, ein Eintrag: der Tag ist durchgegangen."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, get_current_user
from .. import day_close
from ..reminders import ZONE, snapshot
from .learning import access

router = APIRouter(prefix="/accounts/{account_id}/day-close")


def _open_counts(account_id: int, now: datetime) -> dict:
    try:
        return snapshot(account_id, now)
    except Exception:
        # Lieber ohne Zählung abschließen als den Knopf sperren, weil der
        # Stundenplan gerade nicht erreichbar ist.
        return {"homework": 0, "material": 0, "feedback": 0}


def _state(account_id: int, now: datetime) -> dict:
    # Derselbe Tagesbegriff wie in der Tagesansicht; die Uhrzeit des Eintrags
    # bleibt in der Zeitzone, in der auch die Mitteilungen laufen.
    today = date.today()
    return {
        "day": today.isoformat(),
        "closed": day_close.closure(account_id, today.isoformat()),
        "reliability": day_close.reliability(account_id, today),
    }


@router.get("")
def get(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    return _state(account_id, datetime.now(ZONE))


@router.post("")
def post(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Wer abschließt, steht mit im Eintrag — das Kind selbst ist das Ziel."""
    access(user, account_id, write=True)
    now = datetime.now(ZONE)
    by = day_close.BY_PARENT if user.role == "parent" else day_close.BY_CHILD
    day_close.close(account_id, date.today().isoformat(), by, _open_counts(account_id, now), now)
    return _state(account_id, now)
