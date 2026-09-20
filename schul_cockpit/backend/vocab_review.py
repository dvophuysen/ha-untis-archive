"""Parent-reviewed exclusion; original attempts are never rewritten."""
import hashlib
import json
from contextlib import closing
from fastapi import HTTPException
from .db import webapp_conn
from .learning import now_iso


def selection(c, account, subject, ids):
    rows = [dict(r) for r in c.execute(
        'SELECT a.*,w.foreign_word,COALESCE((SELECT excluded FROM vocab_attempt_reviews r WHERE r.attempt_id=a.id ORDER BY r.id DESC LIMIT 1),0) excluded '
        'FROM vocab_attempts a JOIN vocab_words w ON w.id=a.word_id '
        f'WHERE a.account_id=? AND w.account_id=? AND lower(w.subject)=lower(?) AND a.id IN ({",".join("?" for _ in ids)}) ORDER BY a.id',
        (account, account, subject, *ids))]
    if len(rows) != len(set(ids)):
        raise HTTPException(422, 'Mindestens ein Versuch gehört nicht zu diesem Kind und Fach.')
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return rows, digest


def review(account, subject, ids, reason, excluded, reviewer, digest=None):
    with closing(webapp_conn()) as c, c:
        c.execute('BEGIN IMMEDIATE')
        rows, current = selection(c, account, subject, ids)
        if digest is None:
            return {'attempts': rows, 'digest': current}
        if digest != current:
            raise HTTPException(409, 'Die Auswahl wurde verändert. Bitte erneut prüfen.')
        for row in rows:
            if bool(row['excluded']) != excluded:
                c.execute('INSERT INTO vocab_attempt_reviews(attempt_id,excluded,reason,reviewer_id,created_at) VALUES(?,?,?,?,?)',
                          (row['id'], int(excluded), reason.strip(), reviewer, now_iso()))
        return {'reviewed': len(rows), 'excluded': excluded, 'original_attempts_preserved': True}
