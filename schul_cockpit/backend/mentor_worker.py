"""Persistent, bounded work queue; page views never trigger archive-wide inference."""
import asyncio
import logging
from contextlib import closing
from datetime import datetime,timedelta
from .db import webapp_conn
from .learning import now_iso
from .routers.discovery import scan_account

log=logging.getLogger(__name__)

async def cycle():
    with closing(webapp_conn()) as c:
        accounts=[r[0] for r in c.execute('SELECT s.account_id FROM mentor_settings s JOIN learning_profiles p ON p.account_id=s.account_id WHERE s.enabled=1 AND s.background_enabled=1 AND p.active=1 AND p.ai_enabled=1')]
    for account in accounts:
        with closing(webapp_conn()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            c.execute("INSERT OR IGNORE INTO mentor_jobs(account_id,next_run,updated_at) VALUES(?,?,?)",(account,now_iso(),now_iso()))
            row=c.execute('SELECT * FROM mentor_jobs WHERE account_id=?',(account,)).fetchone()
            if row['next_run']>now_iso():continue
            c.execute("UPDATE mentor_jobs SET status='running',next_run=?,updated_at=? WHERE account_id=?",((datetime.fromisoformat(now_iso())+timedelta(minutes=10)).isoformat(),now_iso(),account))
        try:
            await scan_account(account)
            with closing(webapp_conn()) as c:c.execute("UPDATE mentor_jobs SET status='waiting',error=NULL,updated_at=? WHERE account_id=?",(now_iso(),account))
        except Exception as e:
            # Do not log prompts, child responses or provider error bodies.
            code=str(getattr(e,'status_code','internal'))
            with closing(webapp_conn()) as c:c.execute("UPDATE mentor_jobs SET status='deferred',error=?,updated_at=?,next_run=? WHERE account_id=?",(code,now_iso(),(datetime.fromisoformat(now_iso())+timedelta(hours=4)).isoformat(),account))
            log.info('Mentor background batch deferred (%s)',code)

async def background_loop():
    while True:
        await asyncio.sleep(60)
        try:await cycle()
        except Exception:log.warning('Mentor background cycle unavailable; retry at next interval')
