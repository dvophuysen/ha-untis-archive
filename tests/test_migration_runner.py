"""Migrationen laufen je in einer Transaktion samt Marker. Bis 1.31 ließ ein
„duplicate column“ den Rest eines Skripts für immer ungelaufen, und ein Fehler
mittendrin hinterließ halbe Schemata."""
import sqlite3
from types import SimpleNamespace

import pytest

from backend import db


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SETTINGS", SimpleNamespace(webapp_db_path=tmp_path / "webapp.db",
                                                        history_db_path=tmp_path / "h.db"))
    return tmp_path


def _conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db", isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT)")
    return c


def _markers(c):
    return {r[0] for r in c.execute("SELECT key FROM schema_meta")}


def test_fresh_database_gets_every_marker_and_a_second_start_changes_nothing(fresh):
    db.init_webapp_db()
    with db.webapp_conn() as c:
        markers = {r[0] for r in c.execute("SELECT key FROM schema_meta WHERE key LIKE 'migration:%'")}
        schema = c.execute("SELECT group_concat(sql, ';') FROM sqlite_master").fetchone()[0]
    assert markers == {f"migration:{k}" for k, _ in db._MIGRATIONS}
    db.init_webapp_db()
    with db.webapp_conn() as c:
        assert c.execute("SELECT group_concat(sql, ';') FROM sqlite_master").fetchone()[0] == schema


def test_marked_migrations_never_run_again(tmp_path, monkeypatch):
    c = _conn(tmp_path)
    c.execute("INSERT INTO schema_meta VALUES('migration:m1','1')")
    monkeypatch.setattr(db, "_MIGRATIONS", [("m1", "CREATE TABLE should_not_exist(x)")])
    db._apply_migrations(c)
    assert c.execute("SELECT 1 FROM sqlite_master WHERE name='should_not_exist'").fetchone() is None


def test_half_applied_migration_is_completed_statement_by_statement(tmp_path, monkeypatch):
    c = _conn(tmp_path)
    # Halbzustand: die erste Spalte kam schon, die zweite und der Index nicht.
    c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, a TEXT)")
    monkeypatch.setattr(db, "_MIGRATIONS", [("m1", """
        ALTER TABLE t ADD COLUMN a TEXT;
        ALTER TABLE t ADD COLUMN b TEXT;
        CREATE INDEX idx_t_b ON t(b);
    """)])
    db._apply_migrations(c)
    assert {r[1] for r in c.execute("PRAGMA table_info(t)")} == {"id", "a", "b"}
    assert c.execute("SELECT 1 FROM sqlite_master WHERE name='idx_t_b'").fetchone()
    assert "migration:m1" in _markers(c)


def test_a_failing_migration_leaves_nothing_behind_and_no_marker(tmp_path, monkeypatch):
    c = _conn(tmp_path)
    c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
    monkeypatch.setattr(db, "_MIGRATIONS", [("m1", """
        ALTER TABLE t ADD COLUMN a TEXT;
        CREATE TABLE side(x);
        INSERT INTO missing_table VALUES (1);
    """)])
    with pytest.raises(sqlite3.OperationalError):
        db._apply_migrations(c)
    assert {r[1] for r in c.execute("PRAGMA table_info(t)")} == {"id"}
    assert c.execute("SELECT 1 FROM sqlite_master WHERE name='side'").fetchone() is None
    assert "migration:m1" not in _markers(c)
    assert not c.in_transaction


def test_only_the_statement_whose_result_exists_is_skipped(tmp_path, monkeypatch):
    c = _conn(tmp_path)
    c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, a TEXT)")
    # Ein anderer Fehler in einer ALTER-Anweisung wird nicht verschluckt.
    monkeypatch.setattr(db, "_MIGRATIONS", [("m1", "ALTER TABLE nope ADD COLUMN a TEXT")])
    with pytest.raises(sqlite3.OperationalError):
        db._apply_migrations(c)
    monkeypatch.setattr(db, "_MIGRATIONS", [("m2", "CREATE TABLE t(id); INSERT INTO t(id) VALUES (7)")])
    db._apply_migrations(c)
    assert c.execute("SELECT id FROM t").fetchone()[0] == 7


def test_splitting_respects_strings_comments_and_triggers():
    sql = """
    -- Kommentar; mit Semikolon
    CREATE TABLE a(x TEXT DEFAULT 'eins; zwei');
    /* Block; Kommentar */
    CREATE TRIGGER tr AFTER INSERT ON a BEGIN
      UPDATE a SET x = 'drei;' WHERE rowid = new.rowid;
    END;
    INSERT INTO a VALUES ('vier;fünf')
    """
    parts = db.split_statements(sql)
    assert len(parts) == 3
    c = sqlite3.connect(":memory:")
    for p in parts:
        c.execute(p)
    assert c.execute("SELECT x FROM a").fetchone()[0] == "drei;"


def test_own_begin_commit_inside_a_migration_is_absorbed(tmp_path, monkeypatch):
    c = _conn(tmp_path)
    monkeypatch.setattr(db, "_MIGRATIONS", [("m1", """
        BEGIN IMMEDIATE;
        CREATE TABLE t(x);
        INSERT INTO schema_meta(key, value) VALUES ('migration:m1', '1');
        COMMIT;
    """)])
    db._apply_migrations(c)
    assert "migration:m1" in _markers(c) and not c.in_transaction


def test_pragma_migrations_run_outside_a_transaction(tmp_path, monkeypatch):
    c = _conn(tmp_path)
    c.execute("PRAGMA foreign_keys = ON")
    # In einer Transaktion wäre PRAGMA foreign_keys wirkungslos.
    monkeypatch.setattr(db, "_MIGRATIONS", [("m1", "PRAGMA foreign_keys = OFF")])
    db._apply_migrations(c)
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 0
    assert "migration:m1" in _markers(c)
