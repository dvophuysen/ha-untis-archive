"""db.tx bündelt Schreibzugriffe wirklich (Autocommit-Verbindung)."""
import sqlite3

import pytest

from schul_cockpit.backend import db


def _conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db", isolation_level=None)
    conn.execute("CREATE TABLE t(x INTEGER)")
    return conn


def test_rollback_on_error(tmp_path):
    conn = _conn(tmp_path)
    with pytest.raises(RuntimeError):
        with db.tx(conn):
            conn.execute("INSERT INTO t VALUES(1)")
            raise RuntimeError
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0


def test_commit(tmp_path):
    conn = _conn(tmp_path)
    with db.tx(conn):
        conn.execute("INSERT INTO t VALUES(1)")
        conn.execute("INSERT INTO t VALUES(2)")
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2


def test_nested_joins_outer(tmp_path):
    conn = _conn(tmp_path)
    conn.execute("BEGIN IMMEDIATE")
    with db.tx(conn):
        conn.execute("INSERT INTO t VALUES(1)")
    assert conn.in_transaction
    conn.execute("ROLLBACK")
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
