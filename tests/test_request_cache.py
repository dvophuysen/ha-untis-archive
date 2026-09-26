"""Merkzettel je Aufruf: gemerkte Lesefunktionen rechnen einmal, Ergebnisse gehen
als Kopie hinaus, Schreiben verwirft, Verbindungen werden nur innerhalb des
Aufrufs wiederverwendet und nie geteilt."""
from contextlib import closing

from test_learning import env  # noqa: F401
from backend import db, request_cache


def test_memo_only_inside_scope_and_copies():
    calls = []

    @request_cache.memo
    def rows(a, b=0):
        calls.append((a, b))
        return [{"a": a, "b": b}]

    rows(1); rows(1)
    assert len(calls) == 2, "ohne scope wie bisher"
    with request_cache.scope():
        first = rows(1)
        first[0]["a"] = 99
        first.append("x")
        assert rows(1) == [{"a": 1, "b": 0}], "Aufrufer verändern nur ihre Kopie"
        rows(1, b=2)
        assert len(calls) == 4
        request_cache.forget()
        rows(1)
        assert len(calls) == 5, "nach einem Schreibzugriff neu gelesen"
    rows(1)
    assert len(calls) == 6, "nie über den Aufruf hinaus"


def test_errors_are_not_remembered():
    calls = []

    @request_cache.memo
    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("weg")
        return 1

    with request_cache.scope():
        try:
            flaky()
        except RuntimeError:
            pass
        assert flaky() == 1 and flaky() == 1 and len(calls) == 2


def test_connections_reused_within_scope_only(env):
    outside = db.webapp_conn()
    outside.close()
    assert db.webapp_conn() is not outside
    with request_cache.scope():
        with closing(db.webapp_conn()) as a:
            with closing(db.webapp_conn()) as b:
                assert a is not b, "nie zwei Nutzer derselben Verbindung"
        with closing(db.webapp_conn()) as c, c:
            assert c in (a, b)
            c.execute("INSERT INTO users(id,ha_user_id,role,display_name,first_seen_at,last_seen_at) "
                      "VALUES(90,'x','child','X','t','t')")
        assert db.webapp_conn().execute("SELECT COUNT(*) FROM users WHERE id=90").fetchone()[0] == 1
        # Mit offener Transaktion wird geschlossen und zurückgerollt, wie bisher.
        t = db.webapp_conn()
        t.execute("BEGIN IMMEDIATE")
        t.execute("DELETE FROM users WHERE id=90")
        t.close()
        with closing(db.webapp_conn()) as d:
            assert d is not t and d.execute("SELECT COUNT(*) FROM users WHERE id=90").fetchone()[0] == 1
        kept = request_cache.idle()
        assert kept
    for conn in kept:
        try:
            conn.execute("SELECT 1")
            raise AssertionError("am Ende des Aufrufs geschlossen")
        except Exception as exc:
            assert "closed" in str(exc)


def test_a_background_task_started_inside_does_not_inherit_the_scope(env):
    """asyncio kopiert den Kontext in jede neue Aufgabe. Läuft sie nach dem
    Aufruf weiter, darf sie weder eine dort geschlossene Verbindung bekommen
    noch aus dem Merkzettel des Aufrufs lesen."""
    import asyncio
    calls = []

    @request_cache.memo
    def rows():
        calls.append(1)
        return 1

    async def later(started):
        await started.wait()
        rows(); rows()
        with closing(db.webapp_conn()) as c:
            return c.execute("SELECT 1").fetchone()[0]

    async def main():
        started = asyncio.Event()
        with request_cache.scope():
            rows()
            with closing(db.webapp_conn()) as c:
                c.execute("SELECT 1")
            task = asyncio.get_running_loop().create_task(later(started))
        started.set()
        return await task

    assert asyncio.run(main()) == 1
    assert len(calls) == 3, "nach dem Aufruf ohne Merkzettel"
