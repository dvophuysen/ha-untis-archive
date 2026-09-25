"""Read and confirm a school bag checklist without inventing special materials."""
from contextlib import closing
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, StrictBool
from ..audit import log as audit_log
from ..auth import CurrentUser, get_current_user
from ..db import webapp_conn
from ..learning import InputModel, today_local, now_iso
from ..packing import packing_plan, view
from .learning import access

router = APIRouter()

class PackingIn(InputModel):
    item_key: str = Field(min_length=1, max_length=100)
    done: StrictBool
    revision: int = Field(ge=0)
    plan_key: str = Field(min_length=64, max_length=64)


def check_day(day):
    if not -30 <= (day - today_local()).days <= 30:
        raise HTTPException(422, 'Bitte einen Schultag innerhalb der nächsten oder letzten 30 Tage wählen.')


def can_write(user, account_id):
    try:
        access(user, account_id, write=True)
        return True
    except HTTPException:
        return False


@router.get('/accounts/{account_id}/packing/{school_day}')
def get_packing(account_id: int, school_day: date, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id)
    check_day(school_day)
    items, fingerprint, schedule = packing_plan(account_id, school_day)
    with closing(webapp_conn()) as conn:
        result = view(account_id, school_day, items, fingerprint, conn, schedule)
    return dict(**result, can_write=can_write(user, account_id))


@router.put('/accounts/{account_id}/packing/{school_day}')
def put_packing(account_id: int, school_day: date, body: PackingIn, user: CurrentUser = Depends(get_current_user)):
    access(user, account_id, write=True)
    check_day(school_day)
    items, fingerprint, schedule = packing_plan(account_id, school_day)
    if body.plan_key != fingerprint or body.item_key not in {i['key'] for i in items}:
        raise HTTPException(409, 'Der Stundenplan hat sich geändert. Bitte die Packliste neu laden.')
    with closing(webapp_conn()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT done, revision FROM packing_items WHERE account_id=? AND school_day=? AND item_key=?',
                           (account_id, school_day.isoformat(), body.item_key)).fetchone()
        revision = row['revision'] if row else 0
        if body.revision != revision:
            raise HTTPException(409, 'Dieser Punkt wurde inzwischen geändert. Bitte die Packliste neu laden.')
        # Repeated confirmation does not manufacture another success or timestamp.
        if row is None or bool(row['done']) != body.done:
            before = dict(conn.execute('SELECT * FROM packing_items WHERE account_id=? AND school_day=? AND item_key=?',
                                       (account_id, school_day.isoformat(), body.item_key)).fetchone() or {}) or None
            conn.execute('INSERT INTO packing_items(account_id,school_day,item_key,done,revision,updated_at,confirmed_by) VALUES(?,?,?,?,?,?,?) '
                         'ON CONFLICT(account_id,school_day,item_key) DO UPDATE SET done=excluded.done,revision=excluded.revision,updated_at=excluded.updated_at,confirmed_by=excluded.confirmed_by',
                         (account_id, school_day.isoformat(), body.item_key, int(body.done), revision + 1, now_iso(), user.id))
            after = dict(conn.execute('SELECT * FROM packing_items WHERE account_id=? AND school_day=? AND item_key=?',
                                      (account_id, school_day.isoformat(), body.item_key)).fetchone())
            # Protokoll wie bei Aufgaben: Der Testmodus nimmt es beim Beenden zurück (D175).
            audit_log(conn, user_id=user.id, account_id=account_id, op_type='update' if before else 'insert',
                      target_kind='packing', target_id=None,
                      label=f"Tasche {school_day.isoformat()}: {body.item_key} {'drin' if body.done else 'raus'}",
                      before=before, after=after)
        result = view(account_id, school_day, items, fingerprint, conn, schedule)
    return dict(**result, can_write=True)
