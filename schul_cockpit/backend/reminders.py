"""Opt-in, one bundled safety-net reminder per child/device/day.

Delivery goes through the Home Assistant companion app; see app_notify for why
web push is not the way on these devices.
"""
import asyncio
import logging
from contextlib import closing
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from . import afternoon_check, app_notify, day_close
from .db import webapp_conn
from .packing import packing_plan, view

LOG = logging.getLogger('schul_cockpit.reminders')
ZONE = ZoneInfo('Europe/Berlin')
DEFAULT_MORNING = '06:45'


def snapshot(account, now, morning=False, photos=True):
    """Do not infer physical omissions or generate material requirements.

    Abends zählt die Tasche und die Aufgaben für morgen, morgens vor dem
    Aufbruch die für heute: die Tasche von gestern Abend. ``photos=False``
    lässt die Heftseiten aus (0), etwa für den Tagesabschluss, der sie nicht
    zählt; ihr Lesen fragt den Arbeitenkalender ab."""
    target = now.date() if morning else now.date() + timedelta(days=1)
    items, fingerprint, schedule = packing_plan(account, target)
    with closing(webapp_conn()) as c:
        bag = view(account, target, items, fingerprint, c, schedule)
        homework = c.execute("SELECT COUNT(*) FROM tasks WHERE account_id=? AND status IN ('open','in_progress') "
                             "AND due_date IS NOT NULL AND due_date<=?", (account, target.isoformat())).fetchone()[0]
    # Alle offenen Rückmeldungen, auch vergessene der Vortage (D210).
    from .rewards import feedback_backlog, feedback_count
    feedback = feedback_count(feedback_backlog(account, now.date(), now))
    return dict(homework=homework, material=len(items)-bag['confirmed_count'], feedback=feedback,
                photos=photo_count(account, now) if photos else 0)


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
    # Nur an Tagen mit Unterricht: Fällt alles aus, gibt es keine Fachliste.
    if not packing_plan(account, today)[0]:
        return 0
    yesterday = (today - timedelta(days=1)).isoformat()
    if day_close.closure(account, yesterday):
        return 0
    counts = snapshot(account, now, morning=True)
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


# Ein Konto ohne Einstellungszeile: alle Mitteilungen aus, nur der Tagesstand
# wird mitgeschrieben.
_ALL_OFF = dict(enabled=0, remind_at=None, morning_enabled=0, morning_at=None,
                afternoon_enabled=0, afternoon_delay=20)


def _settings():
    """Jedes Konto mit seinen Schaltern. Bis 1.31 liefen nur Konten mit
    eingeschalteter Abend-Erinnerung; Tagesabschluss, Morgen- und
    Nachmittagsmitteilung fielen für alle anderen still aus."""
    with closing(webapp_conn()) as c:
        found = {r['account_id']: dict(r) for r in c.execute('SELECT * FROM reminder_settings')}
    try:
        from .parent_report import accounts
        for account, _name in accounts():
            found.setdefault(account, dict(_ALL_OFF, account_id=account))
    except Exception:
        LOG.debug('Kontenliste nicht lesbar, nur Konten mit Einstellungen', exc_info=True)
    return [found[k] for k in sorted(found)]


# Geschafft-Prüfung ohne Handlung des Kindes (Eltern oder HA erledigen den
# letzten Punkt): alle fünf Minuten je Konto, nicht jede Minute.
REWARD_EVERY = timedelta(minutes=5)
_REWARD_CHECKED: dict[int, datetime] = {}


def check_rewards(account, now):
    """Den Tag prüfen, wenn niemand die App öffnet. Vergibt nichts, was die
    Prüfung bei einer Handlung des Kindes nicht auch vergäbe: Ohne eigene
    Handlung des Kindes an dem Tag zählt kein Tag (rewards.evaluate). Der
    Zeitpunkt für „Frühstarter“ ist der der Prüfung, also nie früher als der
    Moment, in dem wirklich alles erledigt war."""
    last = _REWARD_CHECKED.get(account)
    if last is not None and timedelta(0) <= now - last < REWARD_EVERY:
        return False
    _REWARD_CHECKED[account] = now
    today = now.date()
    with closing(webapp_conn()) as c:
        # Heute schon geschafft, oder in zwei Wochen keine Handlung: nichts zu tun.
        if c.execute('SELECT 1 FROM reward_days WHERE account_id=? AND school_day=?',
                     (account, today.isoformat())).fetchone():
            return False
        if not c.execute('SELECT 1 FROM reward_activity WHERE account_id=? AND day>=? LIMIT 1',
                         (account, (today - timedelta(days=14)).isoformat())).fetchone():
            return False
    from . import request_cache, rewards
    with request_cache.scope():
        rewards.evaluate(account, now)
    return True


def run_once(now=None):
    now = (now or datetime.now(ZONE)).astimezone(ZONE)
    for setting in _settings():
        account = setting['account_id']
        try:
            morning_fallback(setting, now)
        except Exception:
            LOG.warning('Morgenmitteilung nicht möglich für Konto %s', account, exc_info=True)
        try:
            afternoon_check.notify(setting, now)
        except Exception:
            LOG.warning('Nachmittagsfrage nicht möglich für Konto %s', account, exc_info=True)
        try:
            # Der Abend gilt als erledigt, sobald nichts mehr offen ist — ohne
            # dass jemand etwas bestätigen muss. Deshalb wird jede Runde
            # nachgesehen, nicht nur zur Erinnerungszeit. Die Heftseiten zählen
            # dafür nicht (day_close.CLOSING_COUNTS) und werden nicht gelesen.
            day_close.record_if_clear(account, now.date().isoformat(), snapshot(account, now, False, False), now)
        except Exception:
            LOG.warning('Tagesstand nicht lesbar für Konto %s', account, exc_info=True)
        try:
            check_rewards(account, now)
        except Exception:
            LOG.warning('Belohnung nicht prüfbar für Konto %s', account, exc_info=True)
        # Die Abend-Erinnerung hängt an ihrem eigenen Schalter.
        if not setting.get('enabled'):
            continue
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


def run_parent_report(now=None):
    """Der Wochenbericht an die Eltern hängt an derselben Minutenschleife."""
    from . import parent_report
    try:
        parent_report.run_once((now or datetime.now(ZONE)).astimezone(ZONE))
    except Exception:
        LOG.warning('Wochenbericht an die Eltern nicht möglich', exc_info=True)


async def loop():
    while True:
        try:
            await asyncio.to_thread(run_once)
            await asyncio.to_thread(run_parent_report)
        except Exception:
            LOG.exception('Reminder loop failed')
        await asyncio.sleep(60)
