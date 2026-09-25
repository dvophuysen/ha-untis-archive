"""Read-only mastery summaries. Unique words, only started units in totals."""
from .request_cache import memo


def summarize(words, stage='s1'):
    result = dict(wrong=0, uncertain=0, secure=0, new=0, total=0)
    for word in {w['id']: w for w in words}.values():
        state = word['state'][stage]
        if state['stage'] == 'neu':
            key = 'new'
        elif state['stage'] in ('sitzt', 'gefestigt'):
            key = 'secure'
        elif state.get('correct_count', 0) == 0 and state.get('wrong_count', 0):
            key = 'wrong'
        else:
            key = 'uncertain'
        result[key] += 1
        result['total'] += 1
    return result


def _subset(account_id, subject, cards, unit, section='', box=''):
    """Die Karten eines Abschnitts oder Kastens aus den schon gelesenen Karten der
    Einheit, genau so ausgewählt wie ``vocab.cards`` es mit ``section``/``box``
    täte (alter Vokabelweg). Spart je Abschnitt und Kasten das erneute Lesen aller Wörter und
    Antworten; die Seite „Vokabeln“ hatte davon Dutzende je Aufruf."""
    parts = _parts(account_id, subject)
    return [w for w in cards
            if (not section.strip() or parts.get(w['id'], ('', ''))[0] == section.strip())
            and (not box.strip() or parts.get(w['id'], ('', ''))[1] == box.strip())]


@memo
def _parts(account_id, subject):
    from contextlib import closing
    from .db import webapp_conn
    with closing(webapp_conn()) as c:
        return {r[0]: ((r[1] or '').strip(), (r[2] or '').strip()) for r in c.execute(
            "SELECT id,section,box FROM vocab_words WHERE account_id=? AND lower(subject)=lower(?) AND hidden=0",
            (account_id, subject))}


def annotate(account_id, subject, units):
    from . import vocab
    started_words = {}
    started_units = 0
    selections = {u['unit']: vocab.cards(account_id, subject, u['unit'], 1, 'from', 100000) for u in units}
    # Karten des geprüften Bestands tragen ihre Zugehörigkeiten mit (vocab_catalog.cards).
    catalog = any('memberships' in w for words in selections.values() for w in words)
    membership_count = {}
    for words in selections.values():
        for wid in {w['id'] for w in words}:
            membership_count[wid] = membership_count.get(wid, 0) + 1
    for unit in units:
        words = selections[unit['unit']]
        unit['progress'] = summarize(words)
        unit['writing_progress'] = summarize(words, 's2')
        # Attempted in either direction/stage means this unit has been started.
        unit['started'] = any(unit['unit'] in w['state'][s].get('unit_scopes', []) or
                              (membership_count[w['id']] == 1 and w['state'][s].get('unscoped', False))
                              for w in words for s in ('s1', 's2'))
        if unit['started']:
            started_units += 1
            started_words.update({w['id']: w for w in words})
        for part in unit.get('sections', []):
            if catalog:
                selected = [w for w in words if any((part['section'] or unit['unit']) in m['nodes'] and unit['unit'] in m['nodes']
                                                    for m in w.get('memberships', []))]
            else:
                selected = _subset(account_id, subject, words, unit['unit'], part['section'])
            part['progress'] = summarize(selected)
            part['writing_progress'] = summarize(selected, 's2')
            for box in part.get('boxes', []):
                # Der geprüfte Bestand kennt keine Kästen: dort wie bisher der Abschnitt.
                selected = selected if catalog else _subset(account_id, subject, words, unit['unit'], part['section'], box['box'])
                box['progress'] = summarize(selected)
                box['writing_progress'] = summarize(selected, 's2')
    return {'started_units': started_units, 'total_units': len(units),
            'progress': summarize(started_words.values()),
            'writing_progress': summarize(started_words.values(), 's2')}
