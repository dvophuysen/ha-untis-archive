"""Regression test for the cross-instance SQLite lock fix.

Reproduces the original failure: two ``UntisStorage`` instances pointing
at the same DB file simultaneously hammer the master-table upserts.
Before the fix this raises ``sqlite3.OperationalError: database is
locked``; after the fix it completes cleanly.

Run with::

    pytest tests/test_storage_concurrent.py
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

# Load storage.py directly so the test does not pull in
# custom_components/untis_archive/__init__.py, which depends on
# voluptuous and the rest of the Home Assistant runtime.
_STORAGE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "untis_archive"
    / "storage.py"
)
_spec = importlib.util.spec_from_file_location("untis_archive_storage", _STORAGE_PATH)
assert _spec is not None and _spec.loader is not None
_storage_mod = importlib.util.module_from_spec(_spec)
# Register before exec_module — @dataclass(slots=True) introspects
# sys.modules[cls.__module__] during class construction.
sys.modules[_spec.name] = _storage_mod
_spec.loader.exec_module(_storage_mod)
UntisStorage = _storage_mod.UntisStorage


def _own_klasse_payload(klasse_id: int) -> dict:
    return {
        "id": klasse_id,
        "name": f"K{klasse_id}",
        "longName": f"Klasse {klasse_id}",
        "active": True,
        "teacher1": 1,
        "teacher2": None,
    }


def _teacher_payload(teacher_id: int) -> dict:
    return {
        "id": teacher_id,
        "name": f"T{teacher_id}",
        "foreName": "First",
        "longName": f"Teacher {teacher_id}",
        "title": "",
        "active": True,
    }


def _run_burst(store: UntisStorage, account_id: int, n: int) -> None:
    for i in range(n):
        store.upsert_own_klasse(
            account_id,
            [_own_klasse_payload(account_id * 10 + (i % 3))],
            account_id * 10 + (i % 3),
        )
        store.upsert_teachers(
            account_id,
            [_teacher_payload(account_id * 100 + j) for j in range(5)],
        )


def test_concurrent_master_upserts_do_not_deadlock(tmp_path: Path) -> None:
    """Two storage instances on the same DB must serialise writes."""
    db_path = tmp_path / "history.db"

    store_a = UntisStorage(db_path)
    store_b = UntisStorage(db_path)

    account_a = store_a.ensure_account(
        entry_id="a", name="Josia", server="s", school="x",
        username="ju", student_id=1, student_type=5,
    )
    account_b = store_b.ensure_account(
        entry_id="b", name="Noah", server="s", school="x",
        username="nu", student_id=2, student_type=5,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_run_burst, store_a, account_a, 20),
            pool.submit(_run_burst, store_b, account_b, 20),
        ]
        for fut in as_completed(futures):
            # Re-raises any sqlite3.OperationalError("database is locked").
            fut.result()

    store_a.close()
    store_b.close()


def test_failed_begin_does_not_mask_original_error(tmp_path: Path) -> None:
    """If BEGIN itself fails, the rollback path must not raise."""
    db_path = tmp_path / "history.db"
    store = UntisStorage(db_path)
    # Force a transient sqlite3 error inside _tx by closing the
    # connection before the next write — we expect a clean propagation,
    # not a secondary "no transaction is active" exception.
    store._conn.close()  # noqa: SLF001
    with pytest.raises(sqlite3.ProgrammingError):
        store.ensure_account(
            entry_id="c", name="x", server="s", school="x",
            username="u", student_id=None, student_type=None,
        )
