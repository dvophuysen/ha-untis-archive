"""Der HA-Kalender wird eine Minute gemerkt: Familienkarte, Erledigen und
Arbeiten fragen ihn kurz hintereinander."""
import asyncio

from backend import supervisor_client as sc


class _Resp:
    status_code = 200
    text = ""

    def json(self):
        return [{"summary": "Arbeit", "start": {"date": "2026-09-30"}}]


def test_calendar_events_are_cached_briefly(monkeypatch):
    calls = []

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None, params=None):
            calls.append(url)
            return _Resp()

    monkeypatch.setattr(sc.httpx, "AsyncClient", _Client)
    sc._CALENDAR_CACHE.clear()
    client = sc.SupervisorClient.__new__(sc.SupervisorClient)
    client._base = "http://supervisor/core/api"
    client._headers = lambda: {}
    first = asyncio.run(client.get_calendar_events("calendar.x", "a", "b"))
    first[0]["summary"] = "verändert"  # Aufrufer dürfen die Liste ändern
    second = asyncio.run(client.get_calendar_events("calendar.x", "a", "b"))
    assert len(calls) == 1 and second[0]["summary"] == "Arbeit"
    monkeypatch.setattr(sc, "CALENDAR_CACHE_SECONDS", 0)
    asyncio.run(client.get_calendar_events("calendar.x", "a", "b"))
    assert len(calls) == 2
