"""Opt-in, one bundled safety-net reminder per child/device/day.

Delivery goes through the Home Assistant companion app; see app_notify for why
web push is not the way on these devices.
"""
import asyncio
import logging
from contextlib import closing
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from . import app_notify, day_close
from .db import webapp_conn
from .packing import packing_plan, view

LOG = logging.getLogger('schul_cockpit.reminders')
ZONE = ZoneInfo('Europe/Berlin')
DEFAULT_MORNING = '06:45'


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
    return dict(homework=homework, material=len(items)-bag['confirmed_count'], feedback=feedback,
                photos=photo_count(account, now))


# Der Tagesstand wird jede Minute gelesen; die Arbeiten der nächsten zwei Wochen
# ändern sich nicht minütlich. Zehn Minuten Vorrat je Kind.
_PHOTOS: dict[int, tuple[datetime, int]] = {}


def photo_count(account, now):
    """Vor einer Arbeit: Heftseiten, die der Unterricht nennt und die weder
    digital noch fotografiert vorliegen. Nur die Zahl; die Karte sagt, welche."""
    cached = _PHOTOS.get(account)
    if cached and (now - cached[0]).total_seconds() < 600:
        return cached[1]
    photos = 0
    try:
        from .exams import resolve_exams
        from .sources import photo_requests
        exams = asyncio.run(resolve_exams(account, days_ahead=14)).get('exams', [])
        photos = len(photo_requests(account, exams, now.date().isoformat()))
    except Exception:
        LOG.debug('Fotowünsche für Konto %s nicht bestimmbar', account)
    _PHOTOS[account] = (now, photos)
    return photos


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
    if counts.get('photos'): parts.append('Heftseiten für die Arbeit')
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


def morning_wording(counts):
    """Kurz vor dem Aufbruch zählt nur, was noch ins Haus oder in die Tasche geht."""
    parts = []
    if counts['homework']: parts.append('Hausaufgaben')
    if counts['material']: parts.append('Schultasche')
    return ' · '.join(parts)


def morning_fallback(setting, now):
    """Die zweite Mitteilung trifft nur den, der gestern Abend nicht abgeschlossen hat.

    Ohne diese Bedingung wäre sie nach drei Tagen nur noch Lärm — auch für den,
    der alles erledigt hat. Rückmeldungen zu Stunden bleiben außen vor; sie
    ändern morgens nichts mehr.
    """
    account = setting['account_id']
    if not setting.get('morning_enabled', 1):
        return 0
    if not due(setting.get('morning_at') or DEFAULT_MORNING, now):
        return 0
    today = now.date()
    if not packing_plan(account, today)[2]:
        return 0
    yesterday = (today - timedelta(days=1)).isoformat()
    if day_close.closure(account, yesterday):
        return 0
    counts = snapshot(account, now)
    if not (counts['homework'] or counts['material']):
        return 0
    sent, url = 0, app_notify.own_panel()
    for service in app_notify.targets(account):
        with closing(webapp_conn()) as c, c:
            c.execute('BEGIN IMMEDIATE')
            claimed = c.execute(
                "INSERT OR IGNORE INTO morning_app_deliveries(account_id,school_day,service,status,created_at) "
                "VALUES(?,?,?,'claimed',?)", (account, today.isoformat(), service, now.isoformat())).rowcount
        if not claimed:
            continue
        ok = app_notify.send(service, 'Vor dem Aufbruch',
                             f'Noch offen: {morning_wording(counts)}', url)
        with closing(webapp_conn()) as c, c:
            c.execute('UPDATE morning_app_deliveries SET status=? WHERE account_id=? AND school_day=? AND service=?',
                      ('accepted' if ok else 'failed', account, today.isoformat(), service))
        sent += int(ok)
    return sent


def run_once(now=None):
    fixed_clock = now
    now = (now or datetime.now(ZONE)).astimezone(ZONE)
    with closing(webapp_conn()) as c:
        settings = [dict(r) for r in c.execute('SELECT * FROM reminder_settings WHERE enabled=1')]
    for setting in settings:
        account = setting['account_id']
        try:
            morning_fallback(setting, now)
        except Exception:
            LOG.warning('Morgenmitteilung nicht möglich für Konto %s', account, exc_info=True)
        try:
            # Der Abend gilt als erledigt, sobald nichts mehr offen ist — ohne
            # dass jemand etwas bestätigen muss. Deshalb wird jede Runde
            # nachgesehen, nicht nur zur Erinnerungszeit.
            day_close.record_if_clear(account, now.date().isoformat(), snapshot(account, now), now)
        except Exception:
            LOG.warning('Tagesstand nicht lesbar für Konto %s', account, exc_info=True)
        if not due(setting['remind_at'], now):
            continue
        try:
            counts = snapshot(account, now)
            if not any(counts.values()):
                continue
            send_to_app(account, counts, now.date().isoformat(), now)
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
