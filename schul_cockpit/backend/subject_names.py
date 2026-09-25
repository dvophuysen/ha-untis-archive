"""Account-scoped, exact subject aliases; never infer a subject from free text."""
import copy
import json
import sqlite3
import threading
import time
import unicodedata
from contextlib import closing
from .config import SETTINGS
from .db import history_conn, webapp_conn


def key(value):
    return unicodedata.normalize('NFKC',str(value or '')).strip().casefold()


def label(value):
    value=str(value or '').strip()
    if key(value)=='werte und normen':return 'Werte und Normen'
    return value.lower().capitalize() if value.isupper() else value


# Der aus den Stunden abgeleitete Teil je Konto, kurz gemerkt: Fast jede Seite
# baut einen Katalog, oft mehrmals je Aufruf, und die Stunden ändern sich nur
# mit dem Abgleich. Die Prüfsumme erkennt neue oder gelöschte Stunden sofort,
# eine Umbenennung spätestens nach CACHE_SECONDS.
CACHE_SECONDS=120
_CACHE={}
_LOCK=threading.Lock()


def _from_lessons(account):
    aliases={};ids={}
    with closing(history_conn()) as c:
        cols={r[1] for r in c.execute('PRAGMA table_info(lessons)')}
        if not {'account_id','subject_name'} <= cols:return aliases,ids
        stamp=tuple(c.execute('SELECT COUNT(*),MAX(rowid) FROM lessons WHERE account_id=?',(account,)).fetchone())
        slot=(str(SETTINGS.history_db_path),account)
        with _LOCK:
            hit=_CACHE.get(slot)
        if hit and hit[0]==stamp and time.monotonic()-hit[1]<CACHE_SECONDS:
            return copy.deepcopy(hit[2])
        # Je Schreibweise, Kennung und Kurzname nur eine Zeile statt aller
        # Stunden des Schuljahrs samt Rohdaten: Das Ergebnis ist dasselbe,
        # weil nur die jüngste Schreibweise und die Menge der Kurznamen zählen.
        ident='subject_untis_id' if 'subject_untis_id' in cols else 'NULL'
        su=("CASE WHEN json_valid(payload_json) THEN json_extract(payload_json,'$.su') END"
            if 'payload_json' in cols else 'NULL')
        last='MAX(date)' if 'date' in cols else 'MAX(rowid)'
        rows=[dict(r) for r in c.execute(
            f'SELECT subject_name,{ident} AS subject_untis_id,{su} AS su,{last} AS seen FROM lessons '
            f'WHERE account_id=? GROUP BY subject_name,{ident},{su} ORDER BY seen',(account,))]
    # Full subject names win over shortcuts. Latest spelling is canonical.
    for r in rows:
        name=str(r['subject_name'] or '').strip()
        if not name:continue
        aliases[key(name)]=dict(name=name,label=label(name),id=r.get('subject_untis_id'))
        if r.get('subject_untis_id') is not None:ids[r['subject_untis_id']]=aliases[key(name)]
    exact=set(aliases)
    from .exams import _SYNONYMS
    def alias(short,target):
        k=key(short)
        if not k or k in exact:return
        if k in aliases and aliases[k] != target:aliases[k]=None
        else:aliases[k]=target
    for r in rows:
        target=aliases.get(key(r['subject_name']))
        if not target:continue
        for short in _SYNONYMS.get(key(target['name']),[]):alias(short,target)
        try:
            for su in json.loads(r.get('su') or '[]'):
                if isinstance(su,dict):alias(su.get('name'),target)
        except (ValueError,TypeError,AttributeError):pass
    with _LOCK:
        _CACHE[slot]=(stamp,time.monotonic(),copy.deepcopy((aliases,ids)))
    return aliases,ids


class SubjectCatalog:
    def __init__(self, account):
        self.aliases,self.ids=_from_lessons(account)
        # Eigene Zuordnungen der Eltern gelten sofort, deshalb nie gemerkt.
        with closing(webapp_conn()) as c:
            for r in c.execute('SELECT alias,subject_name,subject_untis_id FROM subject_aliases WHERE account_id=?',(account,)):
                target=self.ids.get(r['subject_untis_id']) or self.aliases.get(key(r['subject_name']))
                if target:self.aliases[key(r['alias'])]=target

    def resolve(self, value, sid=None):
        return self.ids.get(sid) or self.aliases.get(key(value))

    def task(self, row):
        result=dict(row)
        target=self.resolve(result.get('subject_name'),result.get('subject_untis_id'))
        title=self.resolve(result.get('title'))
        target=target or title
        if target:
            result['subject_name']=target['name']
            result['subject_untis_id']=target['id']
            if title and key(title['name'])==key(target['name']):result['title']=target['label']
        return result

    def choices(self, lessons, tasks):
        names={}
        for r in lessons:
            value=r.get('subject_name')
            if value:
                target=self.resolve(value,r.get('subject_untis_id'))
                names[key(target['name'] if target else value)]=target['label'] if target else label(value)
        for r in tasks:
            value=r.get('subject_name')
            target=self.resolve(value,r.get('subject_untis_id')) or self.resolve(r.get('title'))
            if target:names[key(target['name'])]=target['label']
            elif value:names[key(value)]=label(value)
        return sorted(names.values(),key=key)
