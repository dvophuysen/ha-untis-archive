"""Art und Hinweise einer Arbeit (D193).

Eine Sprechprüfung ist keine schriftliche Arbeit über den Unterrichtsstoff: Sie
wird am Titel aus dem Klausurplan erkannt, geübt wird im Gespräch statt auf
Papier. Die Hinweise schreiben Eltern frei dazu (etwa worüber gesprochen wird);
Kinder lesen sie, der Lernbegleiter bekommt sie mit.
"""
from __future__ import annotations

import json
import re
from contextlib import closing

from .db import webapp_conn
from .learning import now_iso

ORAL = re.compile(r"sprechpr(ü|ue)fung|m(ü|ue)ndlich|pr(ä|ae)sentation|speaking|oral exam", re.I)
NOTE_MAX = 2000


def is_oral_title(title: str | None) -> bool:
    return bool(ORAL.search(title or ""))


def remember(account_id: int, exam_key: str, title: str | None) -> None:
    """Titel und Art merken, damit Plan und Lernbegleiter sie ohne Kalender kennen."""
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT INTO exam_meta(account_id,exam_key,title,oral,updated_at) VALUES(?,?,?,?,?) "
                  "ON CONFLICT(account_id,exam_key) DO UPDATE SET title=excluded.title,oral=excluded.oral "
                  "WHERE exam_meta.title IS NOT excluded.title OR exam_meta.oral IS NOT excluded.oral",
                  (account_id, exam_key, title or "", int(is_oral_title(title)), now_iso()))


def get(account_id: int, exam_key: str) -> dict:
    try:
        with closing(webapp_conn()) as c:
            row = c.execute("SELECT title,oral,note,note_updated_at FROM exam_meta WHERE account_id=? AND exam_key=?",
                            (account_id, exam_key)).fetchone()
    except Exception:
        return {"oral": False, "note": "", "note_updated_at": None}
    if not row:
        return {"oral": False, "note": "", "note_updated_at": None}
    return {"oral": bool(row[1]), "note": row[2] or "", "note_updated_at": row[3]}


def oral(account_id: int, exam_key: str) -> bool:
    return get(account_id, exam_key)["oral"]


def set_note(account_id: int, exam_key: str, note: str) -> dict:
    note = (note or "").strip()[:NOTE_MAX]
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT INTO exam_meta(account_id,exam_key,note,note_updated_at,updated_at) VALUES(?,?,?,?,?) "
                  "ON CONFLICT(account_id,exam_key) DO UPDATE SET note=excluded.note,note_updated_at=excluded.note_updated_at",
                  (account_id, exam_key, note, now_iso(), now_iso()))
    return get(account_id, exam_key)


def excluded_refs(account_id: int, exam_key: str) -> list[str]:
    """Abgewählte Referenzen der Sprechprobe (D194); voreingestellt zählt alles."""
    try:
        with closing(webapp_conn()) as c:
            row = c.execute("SELECT excluded_refs FROM exam_meta WHERE account_id=? AND exam_key=?", (account_id, exam_key)).fetchone()
        return json.loads(row[0] or "[]") if row else []
    except Exception:
        return []


def set_excluded_refs(account_id: int, exam_key: str, keys: list[str]) -> None:
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT INTO exam_meta(account_id,exam_key,excluded_refs,updated_at) VALUES(?,?,?,?) "
                  "ON CONFLICT(account_id,exam_key) DO UPDATE SET excluded_refs=excluded.excluded_refs",
                  (account_id, exam_key, json.dumps(sorted(set(keys))[:200]), now_iso()))
