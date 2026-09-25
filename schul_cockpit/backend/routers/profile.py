"""Gestaltung je Kind (D176): gilt auf jedem Gerät, auf dem das Kind die App öffnet."""
from contextlib import closing
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field

from ..auth import CurrentUser, get_current_user
from ..db import webapp_conn
from ..learning import InputModel, now_iso
from .learning import access

router = APIRouter()

COLORS = ("petrol", "kobalt", "glut", "beere", "wald", "lila", "ozean", "sonne", "graphit", "koralle", "moos", "nacht")
DEFAULTS = {"color": "petrol", "avatar": "", "theme": "system", "density": "normal", "joy": "konfetti"}


class ProfileIn(InputModel):
    color: Literal[COLORS] | None = None  # type: ignore[valid-type]
    # Leer heißt Initialen; sonst ein einzelnes Emoji.
    avatar: str | None = Field(default=None, max_length=16)
    theme: Literal["system", "light", "dark"] | None = None
    density: Literal["normal", "compact"] | None = None
    joy: Literal["konfetti", "ring", "still"] | None = None


def read(account_id: int) -> dict:
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT * FROM profile_prefs WHERE account_id=?", (account_id,)).fetchone()
    out = dict(DEFAULTS)
    if row:
        out.update({k: row[k] for k in DEFAULTS if row[k] is not None})
    return out


@router.get("/accounts/{account_id}/profile")
def get_profile(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id)
    return read(account_id)


@router.put("/accounts/{account_id}/profile")
def put_profile(account_id: int, body: ProfileIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, write=True)
    values = {**read(account_id), **{k: v for k, v in body.model_dump().items() if v is not None}}
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT INTO profile_prefs(account_id,color,avatar,theme,density,joy,updated_at) VALUES(?,?,?,?,?,?,?) "
                  "ON CONFLICT(account_id) DO UPDATE SET color=excluded.color, avatar=excluded.avatar, theme=excluded.theme, "
                  "density=excluded.density, joy=excluded.joy, updated_at=excluded.updated_at",
                  (account_id, values["color"], values["avatar"], values["theme"], values["density"], values["joy"], now_iso()))
    return values
