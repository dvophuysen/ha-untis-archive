"""Weniger Schreibsperren bei Seitenaufrufen (D200): Anmeldung, Termine und
angenommene Themen schreiben nur, wenn sich etwas ändert."""
import sqlite3
import sys
from contextlib import closing
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env  # noqa: F401
from backend import db, exam_meta, lernstand, mentor_opening, pin_auth


def test_session_is_written_at_most_every_few_minutes_and_a_lock_does_not_fail_it(env):
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO users(ha_user_id,display_name,role,is_admin,first_seen_at,last_seen_at) VALUES('k','Kind','child',0,'t','t')")
        uid = c.execute("SELECT id FROM users WHERE ha_user_id='k'").fetchone()[0]
        token, _ = pin_auth.create_session(c, uid)
        first = c.execute("SELECT last_seen_at FROM sessions WHERE token=?", (token,)).fetchone()[0]
    with closing(db.webapp_conn()) as c, c:
        assert pin_auth.lookup_session(c, token) == uid
        assert c.execute("SELECT last_seen_at FROM sessions WHERE token=?", (token,)).fetchone()[0] == first, "frisch: kein Schreiben"
        old = (pin_auth._utc_now() - timedelta(minutes=pin_auth.SEEN_EVERY + 1)).isoformat()
        c.execute("UPDATE sessions SET last_seen_at=? WHERE token=?", (old, token))
        assert pin_auth.lookup_session(c, token) == uid
        assert c.execute("SELECT last_seen_at FROM sessions WHERE token=?", (token,)).fetchone()[0] > old
        c.execute("UPDATE sessions SET last_seen_at=? WHERE token=?", (old, token))
    # Ein anderer Schreiber hält die Datei: Die Anmeldung gilt trotzdem.
    blocker = sqlite3.connect(db.SETTINGS.webapp_db_path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        c = sqlite3.connect(db.SETTINGS.webapp_db_path, isolation_level=None, timeout=0.1)
        c.row_factory = sqlite3.Row
        assert pin_auth.lookup_session(c, token) == uid
        c.close()
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()


def test_exam_date_and_meta_are_not_rewritten_when_unchanged(env, monkeypatch):
    calls = []
    real = db.webapp_conn

    class Spy:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, sql, *a):
            if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "BEGIN")):
                calls.append(sql.split()[0])
            return self.conn.execute(sql, *a)

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def __enter__(self):
            self.conn.__enter__()
            return self

        def __exit__(self, *a):
            return self.conn.__exit__(*a)

    mentor_opening.remember_exam(1, "k1", "2026-10-01")
    exam_meta.remember(1, "k1", "Mathearbeit")
    monkeypatch.setattr(mentor_opening, "webapp_conn", lambda: Spy(real()))
    monkeypatch.setattr(exam_meta, "webapp_conn", lambda: Spy(real()))
    mentor_opening.remember_exam(1, "k1", "2026-10-01")
    exam_meta.remember(1, "k1", "Mathearbeit")
    assert calls == [], "unverändert: kein Schreibzugriff"
    mentor_opening.remember_exam(1, "k1", "2026-10-02")
    assert calls == ["INSERT"]


def test_assumed_topics_take_no_lock_when_nothing_changes(env):
    scope = {"topics": [{"title": "Brüche kürzen", "field": "Brüche", "lesson_ids": []}]}
    lernstand.ensure_assumed_topics(1, "k2", "Mathematik", scope)
    with closing(db.webapp_conn()) as c:
        assert [tuple(r) for r in c.execute("SELECT title,origin,stale FROM exam_topics WHERE exam_key='k2'")] == [("Brüche kürzen", "assumed", 0)]
        assert lernstand._assumed_ops(c, 1, "k2", "Mathematik", scope) == []
    # Ein anderer Schreiber hält die Datei: Ohne Änderung wartet die Seite nicht.
    blocker = sqlite3.connect(db.SETTINGS.webapp_db_path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        lernstand.ensure_assumed_topics(1, "k2", "Mathematik", scope)
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    # Neues Thema, weggefallenes Thema ohne Antworten.
    lernstand.ensure_assumed_topics(1, "k2", "Mathematik", {"topics": [{"title": "Brüche addieren", "lesson_ids": []}]})
    with closing(db.webapp_conn()) as c:
        assert [r[0] for r in c.execute("SELECT title FROM exam_topics WHERE exam_key='k2'")] == ["Brüche addieren"]
