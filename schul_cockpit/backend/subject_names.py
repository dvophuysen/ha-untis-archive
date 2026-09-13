"""Account-scoped, exact subject aliases; never infer a subject from free text."""
import json
import sqlite3
import unicodedata
from contextlib import closing
from .db import history_conn, webapp_conn


def key(value):
    return unicodedata.normalize('NFKC',str(value or '')).strip().casefold()


def label(value):
    value=str(value or '').strip()
    if key(value)=='werte und normen':return 'Werte und Normen'
    return value.lower().capitalize() if value.isupper() else value


class SubjectCatalog:
    def __init__(self, account):
        self.aliases={};self.ids={}
        with closing(history_conn()) as c:
            cols={r[1] for r in c.execute('PRAGMA table_info(lessons)')}
            if not {'account_id','subject_name'} <= cols:return
            fields=['subject_name']+[x for x in ['subject_untis_id','payload_json'] if x in cols]
            rows=[dict(r) for r in c.execute('SELECT '+','.join(fields)+' FROM lessons WHERE account_id=?'+(' ORDER BY date' if 'date' in cols else ''),(account,))]
        # Full subject names win over shortcuts. Latest spelling is canonical.
        for r in rows:
            name=str(r['subject_name'] or '').strip()
            if not name:continue
            self.aliases[key(name)]=dict(name=name,label=label(name),id=r.get('subject_untis_id'))
            if r.get('subject_untis_id') is not None:self.ids[r['subject_untis_id']]=self.aliases[key(name)]
        exact=set(self.aliases)
        from .exams import _SYNONYMS
        def alias(short,target):
            k=key(short)
            if not k or k in exact:return
            if k in self.aliases and self.aliases[k] != target:self.aliases[k]=None
            else:self.aliases[k]=target
        for r in rows:
            target=self.aliases.get(key(r['subject_name']))
            if not target:continue
            for short in _SYNONYMS.get(key(target['name']),[]):alias(short,target)
            try:
                for su in json.loads(r.get('payload_json') or '{}').get('su',[]):
                    if isinstance(su,dict):alias(su.get('name'),target)
            except (ValueError,TypeError,AttributeError):pass
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
