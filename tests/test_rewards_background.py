"""Belohnungsprüfung im Hintergrund: je Konto ein Lauf, kein Stau im Threadpool."""
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from backend import rewards


def test_bursts_are_coalesced_per_account(monkeypatch):
    recorded, checked = [], []
    gate = threading.Event()

    def slow_note(account_id, kind, ref, user, when=None, *, acting=None):
        checked.append((account_id, ref))
        gate.wait(2)  # die Tagesprüfung dauert

    monkeypatch.setattr(rewards, "note", slow_note)
    monkeypatch.setattr(rewards, "_record", lambda a, k, r, w: recorded.append((a, r)))
    monkeypatch.setattr(rewards, "_freeze_plan", lambda a, d: None)
    when = datetime(2026, 9, 28, 16, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    threads = [threading.Thread(target=rewards._note_now, args=(1, "vocab", i, None, when, False)) for i in range(20)]
    for t in threads:
        t.start()
    time.sleep(0.3)
    # Nur ein Thread arbeitet, die anderen sind sofort zurück.
    assert sum(t.is_alive() for t in threads) == 1
    gate.set()
    for t in threads:
        t.join(5)
    assert not any(t.is_alive() for t in threads)
    # Jedes Ereignis ist festgehalten, der Tag aber höchstens zweimal geprüft.
    assert len(checked) <= 2
    assert {r for _, r in recorded} | {r for _, r in checked} == set(range(20))
    assert not rewards._ACTIVE and not rewards._QUEUE


def test_a_failing_check_does_not_block_the_account(monkeypatch):
    calls = []

    def broken(account_id, kind, ref, user, when=None, *, acting=None):
        calls.append(ref)
        raise RuntimeError("kaputt")

    monkeypatch.setattr(rewards, "note", broken)
    when = datetime(2026, 9, 28, 16, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    rewards._note_now(2, None, None, None, when, False)
    rewards._note_now(2, None, None, None, when, False)
    assert len(calls) == 2 and 2 not in rewards._ACTIVE
