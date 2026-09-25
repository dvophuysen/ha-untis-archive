"""Neueinrichtung der UNTIS-Integration mit neu vergebenen Konto-IDs: Alle
Tabellen mit account_id ziehen mit, in einer Transaktion. Bis 1.31 stand eine
feste Liste im Code, in der unter anderem Vokabeln, Material, Belohnungen und
Antworten fehlten."""
import sqlite3
from types import SimpleNamespace

import pytest

from backend import db, reconcile

TABLES = ("vocab_attempts", "reward_events", "materials", "topic_answers", "usage_days")


def _history(path, rows):
    with sqlite3.connect(path) as c:
        c.execute("DROP TABLE IF EXISTS accounts")
        c.execute("CREATE TABLE accounts(id INTEGER PRIMARY KEY, entry_id TEXT, name TEXT)")
        c.executemany("INSERT INTO accounts VALUES (?,?,?)", rows)
        c.execute("CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY, account_id INTEGER, untis_period_id INTEGER)")


def _row(c, table, account_id):
    """Eine Zeile mit allen Pflichtspalten; Texte tragen die Herkunft (-1, -2)."""
    cols, params = ["account_id"], [account_id]
    for cid, name, ctype, notnull, default, pk in c.execute(f"PRAGMA table_info({table})"):
        if name == "account_id" or (name == "id" and pk):
            continue
        if (notnull and default is None) or pk:
            numeric = any(t in ctype.upper() for t in ("INT", "REAL"))
            cols.append(name)
            params.append(account_id * 100 + cid if numeric else f"{name}-{account_id}")
    c.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", params)


def _accounts(c, table):
    return sorted(r[0] for r in c.execute(f"SELECT account_id FROM {table}"))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SETTINGS", SimpleNamespace(webapp_db_path=tmp_path / "webapp.db",
                                                        history_db_path=tmp_path / "history.db"))
    db.init_webapp_db()
    _history(tmp_path / "history.db", [(1, "entry-a", "A"), (2, "entry-b", "B")])
    reconcile.reconcile_all()
    with db.webapp_conn() as c:
        c.execute("PRAGMA foreign_keys = OFF")  # Testzeilen ohne Elternzeilen
        for acc in (1, 2):
            for table in TABLES:
                _row(c, table, acc)
            c.execute("INSERT INTO profile_prefs(account_id, color, updated_at) VALUES (?, ?, 'x')", (acc, f"farbe-{acc}"))
    return tmp_path


def test_every_account_table_is_found_and_the_mapping_itself_is_left_out(env):
    with db.webapp_conn() as c:
        tables = reconcile.account_tables(c)
    for t in TABLES + ("tasks", "user_account_links", "profile_prefs"):
        assert t in tables
    assert "account_ref" not in tables


def test_swapped_account_ids_move_all_rows_together(env):
    _history(env / "history.db", [(2, "entry-a", "A"), (1, "entry-b", "B")])
    reconcile.reconcile_all()
    with db.webapp_conn() as c:
        assert dict(c.execute("SELECT color, account_id FROM profile_prefs").fetchall()) == {"farbe-1": 2, "farbe-2": 1}
        # Zuerst für Konto 1 angelegt, also id 1 → jetzt Konto 2.
        assert dict(c.execute("SELECT id, account_id FROM materials").fetchall()) == {1: 2, 2: 1}
        for table in TABLES:
            assert _accounts(c, table) == [1, 2], table
        assert dict(c.execute("SELECT entry_id, account_id FROM account_ref").fetchall()) == {"entry-a": 2, "entry-b": 1}


def test_a_conflict_rolls_everything_back_and_is_retried_next_start(env):
    # Altbestand: Konto 3 hat schon Einstellungen, jetzt soll Konto 1 zu 3 werden.
    with db.webapp_conn() as c:
        c.execute("INSERT INTO profile_prefs(account_id, color, updated_at) VALUES (3, 'alt', 'x')")
    _history(env / "history.db", [(3, "entry-a", "A"), (2, "entry-b", "B")])
    reconcile.reconcile_all()  # scheitert am PRIMARY KEY, nicht fatal
    with db.webapp_conn() as c:
        assert dict(c.execute("SELECT entry_id, account_id FROM account_ref").fetchall()) == {"entry-a": 1, "entry-b": 2}
        colors = dict(c.execute("SELECT account_id, color FROM profile_prefs").fetchall())
        assert colors == {1: "farbe-1", 2: "farbe-2", 3: "alt"}, "nichts halb umgezogen"
        assert _accounts(c, "vocab_attempts") == [1, 2]
        assert not c.in_transaction
