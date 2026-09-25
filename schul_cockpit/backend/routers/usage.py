"""Nutzungsbericht für Eltern, Herzschlag des Frontends und Wochen-Feed für HA.

Der Bericht ist nur für Eltern (Nutzerentscheidung 24.09.2026). Der Feed
ist mit dem Mitteilungs-Token des Kontos geschützt und für eine
HA-Automation gedacht, die ihn an die Eltern schickt, nie an die Kinder.
"""
from __future__ import annotations

import logging
from contextlib import closing
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .. import app_notify, parent_report, usage_report
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..learning import today_local
from ..view_mode import acts_as_parent
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
    # Kind am Elterngerät zählt als Nutzung durch das Kind (D175, D183).
    actor = "parent" if acts_as_parent(user) else "child"
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
def usage_feed(account_id: int, token: str | None = Query(default=None), day: str | None = Query(default=None),
               x_notify_token: str | None = Header(default=None)) -> dict:
    """Der Wochenbericht als Text für eine HA-Automation an die Eltern. Das
    Token geht als Kopfzeile ``X-Notify-Token`` oder wie bisher als ?token=."""
    from .notify import given_token, token_matches
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT notify_token FROM account_settings WHERE account_id=?", (account_id,)).fetchone()
    if not row or not token_matches(row["notify_token"], given_token(token, x_notify_token)):
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


class ParentReportIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    at: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    targets: list[str] = Field(default_factory=list, max_length=10)


def _parent(user: CurrentUser) -> None:
    # Mitlesen und Kindmodus gelten als Kind (D183).
    from ..view_mode import acts_as_parent
    if not acts_as_parent(user):
        raise HTTPException(403, "Nur für Eltern")


@router.get("/parent-report")
def get_parent_report(user: CurrentUser = Depends(get_current_user)) -> dict:
    _parent(user)
    kids = parent_report.child_devices()
    return {**parent_report.config(),
            "devices": [{"service": s, "child_device": s in kids} for s in app_notify.services()]}


@router.put("/parent-report")
def put_parent_report(body: ParentReportIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    _parent(user)
    try:
        return parent_report.set_config(body.weekday, body.at, body.targets)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/parent-report/test")
def test_parent_report(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Sofort an die gewählten Geräte, ohne den Wochenversand zu verbrauchen."""
    _parent(user)
    from datetime import datetime
    return {"sent": parent_report.send_all(datetime.now(usage_report.TZ))}
