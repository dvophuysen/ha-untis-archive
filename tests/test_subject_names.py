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
