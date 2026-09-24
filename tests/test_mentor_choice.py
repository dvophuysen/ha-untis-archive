"""Auswahlaufgaben im Mentor (D164): echte Ablenker, gemischt, von der App
ausgewertet, und eine gewählte Antwort zählt als erkannt, nie als beherrscht."""
import json
from contextlib import closing

from test_mentor import setup, start, reply, mock, send, TASK, B  # noqa: F401
from test_learning import child, env  # noqa: F401
from backend import db, learning_plan as lp
from backend.routers import mentor as m

OPTS = [{'text': 'etwas Gutes', 'richtig': True, 'denkfehler': ''},
        {'text': 'etwas gutes', 'richtig': False, 'denkfehler': 'Nach „etwas“ wird das Adjektiv zum Nomen.'},
        {'text': 'Etwas gutes', 'richtig': False, 'denkfehler': 'Groß wird das Nomen, nicht der Begleiter.'}]
CHOICE_TASK = {**TASK, 'prompt': 'Welche Schreibung stimmt?', 'optionen': OPTS, 'afb': 2}


def _stored(sid):
    with closing(db.webapp_conn()) as c:
        return json.loads(c.execute('SELECT current_task FROM mentor_sessions WHERE id=?', (sid,)).fetchone()[0] or 'null')


def _evidence():
    with closing(db.webapp_conn()) as c:
        return [dict(r) for r in c.execute('SELECT result,task_json FROM mentor_evidence ORDER BY id')]


def test_the_child_sees_the_options_but_not_which_is_right(setup):
    client, state, patch = setup; child(state)
    mock(patch, [reply(task=CHOICE_TASK)])
    s = send(client, start(client)).json()
    shown = s['task']['optionen']
    assert sorted(o['text'] for o in shown) == sorted(o['text'] for o in OPTS)
    assert 'richtig' not in json.dumps(shown) and 'denkfehler' not in json.dumps(shown)
    stored = _stored(s['id'])
    assert stored['form'] == 'auswahl' and stored['afb'] == 1


def test_a_wrong_choice_is_answered_without_the_model(setup):
    client, state, patch = setup; child(state)
    calls = []
    mock(patch, [reply(task=CHOICE_TASK)], calls)
    s = send(client, start(client)).json()
    wrong = next(o for o in _stored(s['id'])['optionen'] if not o['richtig'])
    index = _stored(s['id'])['optionen'].index(wrong)
    before = len(calls)
    r = send(client, s, kind='choice', text=wrong['text'], option=index)
    assert r.status_code == 200, r.text
    s = r.json()
    assert len(calls) == before, 'kein Modellaufruf für eine falsche Wahl'
    last = s['messages'][-1]
    assert wrong['denkfehler'] in last['text'] and last['payload']['assessment']['result'] == 'incorrect'
    assert next(o for o in s['task']['optionen'] if o['id'] == index)['aus']
    # Dieselbe Antwort zählt nicht zweimal.
    assert send(client, s, kind='choice', text=wrong['text'], option=index).status_code == 409


def test_a_right_choice_counts_as_recognized_and_asks_for_an_open_task(setup):
    client, state, patch = setup; child(state)
    contexts = []
    follow = {**TASK, 'prompt': 'Schreibe einen eigenen Satz mit einem nominalisierten Adjektiv.'}
    mock(patch, [reply(task=CHOICE_TASK), reply(task=follow)], contexts)
    s = send(client, start(client)).json()
    opts = _stored(s['id'])['optionen']
    index = next(i for i, o in enumerate(opts) if o['richtig'])
    r = send(client, s, kind='choice', text=opts[index]['text'], option=index)
    assert r.status_code == 200, r.text
    s = r.json()
    assert contexts[-1]['auswahl']['ergebnis'] == 'richtig'
    assert s['task']['prompt'] == follow['prompt'] and 'optionen' not in s['task']
    ev = _evidence()
    assert ev and ev[-1]['result'] == 'correct' and json.loads(ev[-1]['task_json'])['optionen']
    state_ = lp.replay([{**e, 'created_at': '2026-09-11T15:00:00', 'help_used': 0, 'variant_hash': 'x',
                         'rationale': ''} for e in ev])
    assert state_['level'] == 0 and state_['label'].startswith('Wiedererkannt')


def test_options_without_real_distractors_go_back_once(setup):
    client, state, patch = setup; child(state)
    only_right = {**CHOICE_TASK, 'optionen': [{'text': 'etwas Gutes', 'richtig': True, 'denkfehler': ''},
                                              {'text': 'etwas gutes', 'richtig': True, 'denkfehler': ''},
                                              {'text': 'ETWAS GUTES', 'richtig': False, 'denkfehler': ''}]}
    instructions = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        instructions.append(instruction)
        return json.dumps(reply(task=only_right if len(instructions) == 1 else CHOICE_TASK)), {}, 'fake'
    patch.setattr(m.ai, 'complete', complete)
    s = send(client, start(client))
    assert s.status_code == 200, s.text
    assert len(instructions) == 2 and 'genau eine' in instructions[1]


def test_chips_never_repeat_an_option():
    kept = m.safe_choices(['etwas gutes', 'Gib mir einen Tipp'], {'prompt': 'Welche?', 'optionen': OPTS})
    assert kept == ['Gib mir einen Tipp']


def test_a_recognized_answer_never_makes_a_topic_sit():
    from backend import lernstand
    rows = [dict(session_id=1, created_at='2026-09-11T15:00:00', result='correct', help_used=0, re_explained=0,
                 seconds=10, edits=0, afb=1, task_form='erkennen', task_kind=k) for k in ('Wähle', 'Erkenne', 'Bestimme')]
    assert lernstand.replay(rows)['stage'] == 'wackelt'
