"""Date-scoped packing confirmations based only on known timetable subjects."""
from contextlib import closing
from hashlib import sha256
import json
import sqlite3
import unicodedata

from fastapi import HTTPException
from .db import history_conn
from .courses import hidden_keys, lesson_is_hidden
from .queries import lessons_for_date


def packing_plan(account_id, day):
    try:
        with closing(history_conn()) as conn:
            lessons = lessons_for_date(conn, account_id, day.isoformat())
        hidden = hidden_keys(account_id)
        lessons = [l for l in lessons if not lesson_is_hidden(l, hidden)]
    except sqlite3.Error as exc:
        raise HTTPException(503, 'Der Stundenplan ist gerade nicht verfügbar. Deine Packliste bleibt gespeichert.') from exc
    items, schedule, seen = [], [], set()
    # Preserve chronological lessons, including cancellations and substitution details.
    for lesson in lessons:
        row = dict(lesson, material_key=None, material_checkbox=False)
        if not lesson.get('is_cancelled') and not lesson.get('was_absent'):
            name = (lesson.get('subject_name') or lesson.get('subject_short') or '').strip()
            normalized = unicodedata.normalize('NFKC', name).casefold()
            if not normalized:
                key, label = 'subject:unknown', 'Unbekanntes Fach'
            elif normalized in {'sport', 'sp', 'spo', 'sport / bewegung'}:
                key, label = 'subject:sport', name
            else:
                key = 'subject:' + sha256(normalized.encode()).hexdigest()[:24]
                label = name
            row['material_key'] = key
            if key not in seen:
                items.append(dict(key=key, label=label))
                row['material_checkbox'] = True
                seen.add(key)
        schedule.append(row)
    fingerprint = sha256(json.dumps(sorted((i['key'], i['label']) for i in items), ensure_ascii=False).encode()).hexdigest()
    return items, fingerprint, schedule


def view(account_id, day, items, fingerprint, conn, schedule):
    states = {r['item_key']: dict(r) for r in conn.execute(
        'SELECT item_key, done, revision, updated_at, confirmed_by FROM packing_items WHERE account_id=? AND school_day=?',
        (account_id, day.isoformat()))}
    result = [dict(**item, done=bool(states.get(item['key'], {}).get('done', False)),
                   revision=states.get(item['key'], {}).get('revision', 0),
                   updated_at=states.get(item['key'], {}).get('updated_at'),
                   confirmed_by=states.get(item['key'], {}).get('confirmed_by')) for item in items]
    complete = bool(result) and all(i['done'] for i in result)
    return dict(account_id=account_id, school_day=day.isoformat(), plan_key=fingerprint, items=result, schedule=schedule,
                status='packed' if complete else 'open' if result else 'no_lessons',
                confirmed_count=sum(i['done'] for i in result))
