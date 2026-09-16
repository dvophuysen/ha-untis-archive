"""Anstöße: Verarbeitung nach Änderung, nicht nach Uhrzeit."""
import sys
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, seed, child, P, path  # noqa: F401
from backend import db, triggers


@pytest.fixture(autouse=True)
def clean():
    triggers._PENDING.clear(); triggers._LAST.clear(); triggers._SEEN.clear(); triggers._RETRIES.clear()
    yield
    triggers._PENDING.clear(); triggers._LAST.clear(); triggers._SEEN.clear(); triggers._RETRIES.clear()


def test_requests_collect_once_after_the_quiet_period(monkeypatch):
    runs = []

    async def collect(account_id):
        runs.append(account_id)
        return {"fetched": 1, "stored": 1, "verified": 0, "links": 3}
    monkeypatch.setattr("backend.source_collector.collect", collect)
    triggers.request(1, "neues Material")
    triggers.request(1, "neues Material")
    triggers.request(1, "neue Aufgaben")
    assert triggers.state(1)["pending"]["reasons"] == ["neues Material", "neue Aufgaben"]
    import asyncio
    # Noch in der Sammelfrist: nichts läuft.
    assert asyncio.run(triggers.run_pending(datetime.now())) == []
    done = asyncio.run(triggers.run_pending(datetime.now() + timedelta(seconds=triggers.DEBOUNCE + 1)))
    assert runs == [1] and done[0]["reasons"] == ["neues Material", "neue Aufgaben"] and done[0]["result"]["stored"] == 1
    assert triggers.state(1)["pending"] is None and triggers.state(1)["last"]["result"]["links"] == 3


def test_untis_watcher_notices_new_places_but_not_the_first_look(monkeypatch):
    texts = {"v": "Mathe S. 12"}
    monkeypatch.setattr("backend.source_collector.accounts_with_books", lambda: [1])
    monkeypatch.setattr("backend.sources.mentions", lambda account_id: ([{"kind": "lesson", "id": 1, "text": texts["v"]}], "2026-08-01"))
    assert triggers.watch_untis() == [] and 1 not in triggers._PENDING
    assert triggers.watch_untis() == []
    texts["v"] = "Mathe S. 12 und S. 14"
    assert triggers.watch_untis() == [1] and triggers.state(1)["pending"]["reasons"] == ["neue Untis-Einträge"]


def test_failed_analyses_are_retried_after_a_while_and_only_three_times(env, monkeypatch):
    client, state, patch = env
    seed(client, ai_enabled=True)
    old = (datetime.fromisoformat("2026-09-11T15:00:00+02:00") - timedelta(hours=1)).isoformat()
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,analysis_state,analysis_error,created_at,updated_at) "
                  "VALUES(1,'book_page','LATEIN','S. 22','failed','OperationalError',?,?)", (old, old))
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,analysis_state,created_at,updated_at) "
                  "VALUES(1,'book_page','LATEIN','frisch','failed','2026-09-11T14:55:00+02:00','2026-09-11T14:55:00+02:00')")
        mid = c.execute("SELECT id FROM materials WHERE title='S. 22'").fetchone()[0]
    monkeypatch.setattr(triggers, "now_iso", lambda: "2026-09-11T15:00:00+02:00")
    assert triggers.failed_materials() == [(1, mid)]
    attempts = []

    async def analyze(account_id, material_id):
        attempts.append(material_id)
        return False
    monkeypatch.setattr("backend.material_analysis.analyze", analyze)
    import asyncio
    for _ in range(5):
        asyncio.run(triggers.retry_failed())
    assert attempts == [mid] * triggers.RETRY_MAX
