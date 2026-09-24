"""Nutzungsbericht für Eltern, Herzschlag des Frontends und Wochen-Feed für HA.

Der Bericht ist nur für Eltern (Nutzerentscheidung 24.09.2026). Der Feed
ist mit dem Mitteilungs-Token des Kontos geschützt und für eine
HA-Automation gedacht, die ihn an die Eltern schickt, nie an die Kinder.
"""
from __future__ import annotations

import logging
import secrets
from contextlib import closing
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .. import usage_report
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..learning import today_local
from .learning import access

LOG = logging.getLogger("schul_cockpit.usage")
router = APIRouter()
_PURGED: dict[str, str] = {}


class PingIn(BaseModel):
    account_id: int
    view: str = Field(default="", max_length=40)
    seconds: int = Field(default=0, ge=0, le=600)
    open: bool = False


def _day(value: str | None) -> date:
    if not value:
        return today_local()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Datum als JJJJ-MM-TT angeben.") from None


@router.get("/accounts/{account_id}/usage-week")
def usage_week(account_id: int, day: str | None = Query(default=None),
               user: CurrentUser = Depends(get_current_user)) -> dict:
    access(user, account_id, parent=True)
    return usage_report.week(account_id, _day(day))


@router.post("/usage/ping", status_code=204, response_class=Response)
def ping(body: PingIn, user: CurrentUser = Depends(get_current_user)):
    if user.role == "pending":
        return Response(status_code=204)
    assert_account_access(user, body.account_id)
    actor = "parent" if (user.is_admin or user.role == "parent") else "child"
    usage_report.record_ping(body.account_id, actor, body.view, body.seconds, body.open)
    today = today_local().isoformat()
    if _PURGED.get("day") != today:
        _PURGED["day"] = today
        try:
            usage_report.purge()
        except Exception:
            LOG.warning("Alte Nutzungstage nicht gelöscht", exc_info=True)
    return Response(status_code=204)


@router.get("/notify/{account_id}/usage-week")
def usage_feed(account_id: int, token: str = Query(...), day: str | None = Query(default=None)) -> dict:
    """Der Wochenbericht als Text für eine HA-Automation an die Eltern."""
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT notify_token FROM account_settings WHERE account_id=?", (account_id,)).fetchone()
    if not row or not row["notify_token"] or not secrets.compare_digest(row["notify_token"], token):
        raise HTTPException(401, "invalid token")
    report = usage_report.week(account_id, _day(day))
    hconn = history_conn()
    try:
        account = hconn.execute("SELECT name FROM accounts WHERE id=?", (account_id,)).fetchone()
    finally:
        hconn.close()
    name = account["name"] if account else f"Konto {account_id}"
    lines = list(report["lines"])
    for w in report["warnings"]:
        lines.append(f"Auffällig: {w['title']}. {w['evidence']} Mögliche Deutung: {w['meaning']} "
                     f"Nicht sichtbar: {w['unseen']}")
    return {"title": f"Schul-Cockpit: Woche {report['week']['label']} – {name}",
            "headline": report["headline"], "text": "\n".join(lines),
            "warnings": len(report["warnings"]), "week": report["week"]}
