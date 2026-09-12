"""Canonical daily and weekly plan, shared with the mentor."""
import asyncio
from fastapi import APIRouter, Depends
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..exams import resolve_exams
from .. import learning_plan as lp
router=APIRouter()
@router.get('/accounts/{account_id}/plan')
async def plan(account_id:int,user:CurrentUser=Depends(get_current_user)):
    assert_account_access(user,account_id)
    warnings=[]
    try:
        result=await asyncio.wait_for(resolve_exams(account_id,days_ahead=28),timeout=8)
        exams=result.get('exams',[])
        if result.get('calendar_error'):warnings.append('Klausurenkalender nicht vollständig lesbar.')
    except Exception:
        exams=[];warnings.append('Klausurentermine derzeit nicht prüfbar.')
    result=lp.build(account_id,exams)
    result['errors']+=warnings
    return result

from typing import Literal
from ..learning import InputModel,now_iso,today_local
from ..db import webapp_conn
from contextlib import closing
from .learning import access
class DayIn(InputModel):
    load:Literal['busy','normal','room']='normal'
@router.put('/accounts/{account_id}/plan/day')
async def change_day(account_id:int,body:DayIn,user:CurrentUser=Depends(get_current_user)):
    access(user,account_id,write=True)
    with closing(webapp_conn()) as c:
        c.execute('INSERT INTO learning_day_preferences VALUES(?,?,?,?) ON CONFLICT(account_id,day) DO UPDATE SET load=excluded.load,updated_at=excluded.updated_at',(account_id,lp.today_local().isoformat(),body.load,now_iso()))
    return await plan(account_id,user)
