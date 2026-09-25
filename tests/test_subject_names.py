import json
import sqlite3
from test_learning import env
from backend import db
from backend.subject_names import SubjectCatalog


def test_account_aliases_case_duplicates_and_task_titles(env):
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute('CREATE TABLE lessons(account_id INTEGER,subject_untis_id INTEGER,subject_name TEXT,date TEXT,payload_json TEXT)')
        c.executemany('INSERT INTO lessons VALUES(?,?,?,?,?)',[(1,7,'POLITIK','2026-09-10',json.dumps({'su':[{'name':'PO'}]})),(1,8,'MATHEMATIK','2026-09-10','{}'),(2,9,'Anderes Fach','2026-09-10',json.dumps({'su':[{'name':'PO'}]}))])
    catalog=SubjectCatalog(1)
    tasks=[{'id':i,'title':n} for i,n in enumerate(['PO','Po','Politik','POLITIK','Mathematik','Freier Arbeitsauftrag'])]
    assert catalog.choices([{'subject_name':'POLITIK'}],tasks)==['Mathematik','Politik']
    assert all(catalog.task(t)['title']=='Politik' for t in tasks[:4])
    assert catalog.task({'title':'Unbekannt','notes':'Politik besprechen'})=={'title':'Unbekannt','notes':'Politik besprechen'}
    assert catalog.resolve('PO')['id']==7
    assert SubjectCatalog(2).resolve('PO')['id']==9
    assert catalog.task({'title':'Aufgabe 4','subject_name':'Po'})['title']=='Aufgabe 4'


def _reference(account):
    """Der bisherige Aufbau über alle Stunden, zum Vergleich."""
    from backend.subject_names import key, label
    from backend.exams import _SYNONYMS
    aliases, ids = {}, {}
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute('SELECT subject_name,subject_untis_id,payload_json FROM lessons WHERE account_id=? ORDER BY date', (account,))]
    for r in rows:
        name = str(r['subject_name'] or '').strip()
        if not name:
            continue
        aliases[key(name)] = dict(name=name, label=label(name), id=r.get('subject_untis_id'))
        if r.get('subject_untis_id') is not None:
            ids[r['subject_untis_id']] = aliases[key(name)]
    exact = set(aliases)

    def alias(short, target):
        k = key(short)
        if not k or k in exact:
            return
        if k in aliases and aliases[k] != target:
            aliases[k] = None
        else:
            aliases[k] = target
    for r in rows:
        target = aliases.get(key(r['subject_name']))
        if not target:
            continue
        for short in _SYNONYMS.get(key(target['name']), []):
            alias(short, target)
        try:
            for su in json.loads(r.get('payload_json') or '{}').get('su', []):
                if isinstance(su, dict):
                    alias(su.get('name'), target)
        except (ValueError, TypeError, AttributeError):
            pass
    return aliases, ids


def test_grouped_catalog_matches_full_scan(env):
    rows = []
    # Umbenennung im Lauf des Jahres, geteilte Kurznamen, kaputte Rohdaten.
    for day in range(1, 29):
        d = f'2026-09-{day:02d}'
        rows += [(1, 7, 'POLITIK' if day < 15 else 'Politik-Wirtschaft', d, json.dumps({'su': [{'name': 'PO'}]})),
                 (1, 8, 'MATHEMATIK', d, json.dumps({'su': [{'name': 'MA'}, {'name': 'M'}]})),
                 (1, 9, 'Physik', d, json.dumps({'su': [{'name': 'PH'}, {'name': 'M'}]})),
                 (1, 10, 'Englisch', d, 'kein json'),
                 (1, 11, 'Latein', d, json.dumps([1, 2])),
                 (1, None, 'Sport', d, json.dumps({'su': 'SP'})),
                 (1, 12, '', d, '{}')]
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute('CREATE TABLE lessons(account_id INTEGER,subject_untis_id INTEGER,subject_name TEXT,date TEXT,payload_json TEXT)')
        c.executemany('INSERT INTO lessons VALUES(?,?,?,?,?)', rows)
    catalog = SubjectCatalog(1)
    aliases, ids = _reference(1)
    assert catalog.aliases == aliases
    assert catalog.ids == ids
    assert catalog.resolve('M') is None  # zwei Fächer teilen den Kurznamen
