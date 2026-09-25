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
    oral = int(is_oral_title(title))
    with closing(webapp_conn()) as c, c:
        known = c.execute("SELECT title,oral FROM exam_meta WHERE account_id=? AND exam_key=?", (account_id, exam_key)).fetchone()
        if known and known[0] == (title or "") and known[1] == oral:
            return  # nichts Neues: keine Schreibsperre (D200)
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


# ------------------------------------------------------------------ Material je Arbeit (D199)

PIN_KINDS = ("book_page", "worksheet", "workbook", "other", "exam_notice")


def pinned(account_id: int, exam_key: str) -> list[int]:
    """Von Eltern an die Arbeit angeheftetes Material zum Üben."""
    try:
        with closing(webapp_conn()) as c:
            row = c.execute("SELECT pinned_json FROM exam_meta WHERE account_id=? AND exam_key=?", (account_id, exam_key)).fetchone()
        return [int(x) for x in json.loads(row[0] or "[]")] if row else []
    except Exception:
        return []


def set_pinned(account_id: int, exam_key: str, ids: list[int]) -> None:
    with closing(webapp_conn()) as c, c:
        own = {r[0] for r in c.execute(f"SELECT id FROM materials WHERE account_id=? AND id IN ({','.join('?' * len(ids)) or 'NULL'})",
                                       (account_id, *ids))} if ids else set()
        keep = [i for i in dict.fromkeys(ids) if i in own][:40]
        c.execute("INSERT INTO exam_meta(account_id,exam_key,pinned_json,updated_at) VALUES(?,?,?,?) "
                  "ON CONFLICT(account_id,exam_key) DO UPDATE SET pinned_json=excluded.pinned_json",
                  (account_id, exam_key, json.dumps(keep), now_iso()))


def material_choices(account_id: int, exam_key: str, subject: str | None, limit: int = 40) -> list[dict]:
    """Das abgelegte Material des Fachs zum Anheften, Angeheftetes zuerst, sonst das Jüngste."""
    if not subject:
        return []
    on = pinned(account_id, exam_key)
    marks = ",".join("?" * len(PIN_KINDS))
    with closing(webapp_conn()) as c:
        rows = [dict(r) for r in c.execute(
            f"SELECT id,kind,title,source_label,source_page,mime_type,COALESCE(document_date,substr(created_at,1,10)) AS day "
            f"FROM materials WHERE account_id=? AND hidden=0 AND lower(subject_name)=lower(?) AND kind IN ({marks}) "
            f"ORDER BY day DESC,id DESC LIMIT 200", (account_id, subject, *PIN_KINDS))]
    rows.sort(key=lambda r: r["id"] not in on)
    out = []
    for r in rows[:limit]:
        label = (r["source_label"] or "").strip()
        where = f"{label} S. {r['source_page']}" if label and r["source_page"] else (r["title"] or label or "Material")
        out.append({"id": r["id"], "label": where, "title": r["title"] or "", "kind": r["kind"], "day": r["day"],
                    "image": (r["mime_type"] or "").startswith("image/"), "pinned": r["id"] in on})
    return out


def pinned_context(account_id: int, exam_key: str, budget: int = 4000) -> list[dict]:
    """Text des angehefteten Materials für Lernbegleiter und Übungsarbeit."""
    ids = pinned(account_id, exam_key)
    if not ids:
        return []
    from .materials import printed_only
    with closing(webapp_conn()) as c:
        rows = {r["id"]: dict(r) for r in c.execute(
            f"SELECT id,title,source_label,source_page,content_text,summary FROM materials WHERE account_id=? AND id IN ({','.join('?' * len(ids))})",
            (account_id, *ids))}
    out, used = [], 0
    for i in ids:
        r = rows.get(i)
        if not r:
            continue
        text = printed_only(r["content_text"] or r["summary"] or "").strip()[: max(0, budget - used)]
        used += len(text)
        label = (r["source_label"] or "").strip()
        out.append({"material": f"{label} S. {r['source_page']}" if label and r["source_page"] else (r["title"] or "Material"),
                    "text": text})
        if used >= budget:
            break
    return out
