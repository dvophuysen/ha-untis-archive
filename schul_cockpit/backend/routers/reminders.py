"""Parent-controlled reminder time; child devices opt in separately."""
from contextlib import closing
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, StrictBool
from ..auth import CurrentUser, get_current_user
from .. import app_notify
from .. import reminders as r
from ..db import webapp_conn
from ..learning import InputModel
from .learning import access

router=APIRouter(prefix='/accounts/{account_id}/reminders')

class SettingsIn(InputModel):
    enabled: StrictBool
    remind_at: str | None = Field(default=None, pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
    # Die Morgenmitteilung trifft nur, wer am Abend nicht abgeschlossen hat.
    morning_enabled: StrictBool = False
    morning_at: str | None = Field(default=None, pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')

class TargetsIn(InputModel):
    services: list[str] = Field(default_factory=list, max_length=10)

@router.get('')
def get(account_id:int,user:CurrentUser=Depends(get_current_user)):
    access(user,account_id)
    with closing(webapp_conn()) as c:
        row=c.execute('SELECT enabled,remind_at,morning_enabled,morning_at FROM reminder_settings WHERE account_id=?',(account_id,)).fetchone()
        devices=c.execute("SELECT COUNT(DISTINCT p.id) FROM push_subscriptions p JOIN users u ON u.id=p.user_id JOIN user_account_links l ON l.user_id=u.id WHERE l.account_id=? AND l.can_edit=1 AND u.role='child' AND u.demo_mode=0",(account_id,)).fetchone()[0]
        latest=c.execute('SELECT status,created_at FROM reminder_deliveries WHERE account_id=? ORDER BY created_at DESC LIMIT 1',(account_id,)).fetchone()
    try:
        access(user,account_id,write=True,parent=True);can_manage=True
    except HTTPException:
        can_manage=False
    with closing(webapp_conn()) as c:
        app_latest=c.execute('SELECT service,status,created_at FROM reminder_app_deliveries WHERE account_id=? ORDER BY created_at DESC LIMIT 1',(account_id,)).fetchone()
    return dict(enabled=bool(row and row['enabled']),remind_at=row['remind_at'] if row else None,devices=devices,
                morning_enabled=bool(row['morning_enabled']) if row else False,
                morning_at=(row['morning_at'] if row else None) or r.DEFAULT_MORNING,
                can_manage=can_manage,last_delivery=dict(latest) if latest else None,
                app_targets=app_notify.targets(account_id),
                app_services=app_notify.services() if can_manage else [],
                last_app_delivery=dict(app_latest) if app_latest else None)

@router.put('')
def put(account_id:int,body:SettingsIn,user:CurrentUser=Depends(get_current_user)):
    access(user,account_id,write=True,parent=True)
    if body.enabled and (not body.remind_at or not '14:00' <= body.remind_at <= '21:00'):
        raise HTTPException(422,'Bitte eine Erinnerungszeit zwischen 14 und 21 Uhr wählen.')
    if body.morning_at and not '05:00' <= body.morning_at <= '09:00':
        raise HTTPException(422,'Bitte eine Morgenzeit zwischen 5 und 9 Uhr wählen.')
    with closing(webapp_conn()) as c:
        c.execute('INSERT INTO reminder_settings(account_id,enabled,remind_at,morning_enabled,morning_at) VALUES(?,?,?,?,?) '
                  'ON CONFLICT(account_id) DO UPDATE SET enabled=excluded.enabled,remind_at=excluded.remind_at,'
                  'morning_enabled=excluded.morning_enabled,morning_at=excluded.morning_at',
                  (account_id,int(body.enabled),body.remind_at,int(body.morning_enabled),body.morning_at))
    return get(account_id,user)

@router.put('/targets')
def targets(account_id:int,body:TargetsIn,user:CurrentUser=Depends(get_current_user)):
    """Which phones get the reminder. One entry per companion app."""
    access(user,account_id,write=True,parent=True)
    known=set(app_notify.services())
    unknown=[s for s in body.services if s not in known]
    if unknown:
        raise HTTPException(422,f"Unbekanntes Gerät: {', '.join(unknown[:3])}")
    app_notify.set_targets(account_id,body.services)
    return get(account_id,user)

@router.post('/test')
def test(account_id:int,user:CurrentUser=Depends(get_current_user)):
    """Send one real notification now, so delivery is proven before it matters."""
    access(user,account_id,write=True,parent=True)
    chosen=app_notify.targets(account_id)
    if not chosen:
        raise HTTPException(422,'Bitte zuerst ein Gerät auswählen.')
    url=app_notify.own_panel()
    result={s:app_notify.send(s,'Schul-Cockpit','Testnachricht. Tippe kurz darauf, dann öffnet sich dein Tag.',url) for s in chosen}
    return dict(sent=result,panel=url)
