"""Opt-in, one bundled safety-net reminder per child/device/day.

Delivery goes through the Home Assistant companion app; see app_notify for why
web push is not the way on these devices.
"""
import asyncio
import logging
from contextlib import closing
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from . import app_notify
from .db import webapp_conn
from .packing import packing_plan, view
from .webpush_setup import send_push

LOG = logging.getLogger('schul_cockpit.reminders')
ZONE = ZoneInfo('Europe/Berlin')


def snapshot(account, now):
    """Do not infer physical omissions or generate material requirements."""
    tomorrow = now.date() + timedelta(days=1)
    items, fingerprint, schedule = packing_plan(account, tomorrow)
    _, _, today_schedule = packing_plan(account, now.date())
    with closing(webapp_conn()) as c:
        bag = view(account, tomorrow, items, fingerprint, c, schedule)
        homework = c.execute("SELECT COUNT(*) FROM tasks WHERE account_id=? AND status!='done' AND due_date IS NOT NULL AND due_date<=?", (account, tomorrow.isoformat())).fetchone()[0]
        ratings = {r['lesson_id'] for r in c.execute('SELECT lesson_id FROM lesson_checkins WHERE account_id=? AND rating IS NOT NULL', (account,))}
    feedback = 0
    for lesson in today_schedule:
        end = lesson.get('end_hhmm')
        if (end and end <= now.strftime('%H:%M') and not lesson.get('is_cancelled')
                and not lesson.get('was_absent') and lesson.get('id') not in ratings):
            feedback += 1
    return dict(homework=homework, material=len(items)-bag['confirmed_count'], feedback=feedback)


def due(time_of_day, now):
    if not time_of_day:
        return False
    hour, minute = map(int, time_of_day.split(':'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # No catching up hours later after downtime or during the night.
    return 0 <= (now-target).total_seconds() < 1800


def wording(counts):
    """What is open, in the order it has to be dealt with tonight."""
    parts = []
    if counts['homework']: parts.append('Hausaufgaben')
    if counts['material']: parts.append('Schultasche')
    if counts['feedback']: parts.append('Rückmeldungen')
    return ' · '.join(parts)


def send_to_app(account, counts, day, now):
    """One notification per target and day. Tapping it opens the day view."""
    sent = 0
    url = app_notify.own_panel()
    for service in app_notify.targets(account):
        with closing(webapp_conn()) as c, c:
            c.execute('BEGIN IMMEDIATE')
            claimed = c.execute(
                "INSERT OR IGNORE INTO reminder_app_deliveries(account_id,school_day,service,status,created_at) "
                "VALUES(?,?,?,'claimed',?)", (account, day, service, now.isoformat())).rowcount
        if not claimed:
            continue
        ok = app_notify.send(service, 'Kurzer Blick auf morgen',
                             f'Noch offen: {wording(counts)}', url)
        with closing(webapp_conn()) as c, c:
            c.execute('UPDATE reminder_app_deliveries SET status=? WHERE account_id=? AND school_day=? AND service=?',
                      ('accepted' if ok else 'failed', account, day, service))
        sent += int(ok)
    return sent


def run_once(now=None):
    fixed_clock = now
    now = (now or datetime.now(ZONE)).astimezone(ZONE)
    with closing(webapp_conn()) as c:
        settings = [dict(r) for r in c.execute('SELECT * FROM reminder_settings WHERE enabled=1')]
    for setting in settings:
        if not due(setting['remind_at'], now):
            continue
        account = setting['account_id']
        try:
            counts = snapshot(account, now)
            if not any(counts.values()):
                continue
            send_to_app(account, counts, now.date().isoformat(), now)
            with closing(webapp_conn()) as c:
                subs = [dict(r) for r in c.execute("SELECT DISTINCT p.* FROM push_subscriptions p JOIN users u ON u.id=p.user_id JOIN user_account_links l ON l.user_id=u.id WHERE l.account_id=? AND l.can_edit=1 AND u.role='child' AND u.demo_mode=0", (account,))]
            for sub in subs:
                # Recheck obligations/settings after any previous device took time.
                current_time = fixed_clock.astimezone(ZONE) if fixed_clock is not None else datetime.now(ZONE)
                counts = snapshot(account, current_time)
                if not any(counts.values()):
                    break
                stamp = now.isoformat()
                with closing(webapp_conn()) as c, c:
                    c.execute('BEGIN IMMEDIATE')
                    enabled = c.execute('SELECT enabled,remind_at FROM reminder_settings WHERE account_id=?', (account,)).fetchone()
                    if not enabled or not enabled['enabled'] or not due(enabled['remind_at'], current_time):
                        break
                    recipient = c.execute("SELECT 1 FROM push_subscriptions p JOIN users u ON u.id=p.user_id JOIN user_account_links l ON l.user_id=u.id WHERE p.id=? AND p.user_id=? AND l.account_id=? AND l.can_edit=1 AND u.role='child' AND u.demo_mode=0", (sub['id'],sub['user_id'],account)).fetchone()
                    if not recipient:
                        continue
                    claimed = c.execute("INSERT OR IGNORE INTO reminder_deliveries(account_id,school_day,subscription_id,status,created_at) VALUES(?,?,?,'claimed',?)", (account, now.date().isoformat(), sub['id'], stamp)).rowcount
                if not claimed:
                    continue
                parts = []
                if counts['homework']: parts.append('Hausaufgaben abhaken')
                if counts['material']: parts.append('Fachmaterial prüfen')
                if counts['feedback']: parts.append('Stunden zurückmelden')
                # Generic content is appropriate for a locked screen.
                payload = dict(title='Noch ein kurzer Tagescheck 🔔', body=' · '.join(parts),
                               url=f'./?acc={account}#/today', tag=f'day-check-{account}')
                try:
                    ok, status = send_push(dict(endpoint=sub['endpoint'], keys=dict(p256dh=sub['p256dh'], auth=sub['auth'])), payload, ttl=1800)
                except Exception:
                    ok, status = False, None
                    LOG.warning('Reminder transport failed for account %s', account)
                with closing(webapp_conn()) as c:
                    c.execute('UPDATE reminder_deliveries SET status=?,finished_at=? WHERE account_id=? AND school_day=? AND subscription_id=?', ('accepted' if ok else 'failed', datetime.now(ZONE).isoformat(), account, now.date().isoformat(), sub['id']))
                    if status in (404,410):
                        c.execute('DELETE FROM push_subscriptions WHERE id=?', (sub['id'],))
        except Exception:
            # No false successful reminder when source data cannot be read.
            LOG.warning('Reminder check unavailable for account %s', account, exc_info=True)


async def loop():
    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception:
            LOG.exception('Reminder loop failed')
        await asyncio.sleep(60)
