"""Database connections.

- ``history.db`` (from the UNTIS Archive integration): read-only.
- ``webapp.db`` (this add-on's own data): read-write, in /data.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import SETTINGS

_SCHEMA_FILE = Path(__file__).parent / "webapp_schema.sql"


def history_conn() -> sqlite3.Connection:
    """Read-only connection to the UNTIS Archive's history.db."""
    uri = f"file:{SETTINGS.history_db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def webapp_conn() -> sqlite3.Connection:
    """Read-write connection to the add-on's webapp.db."""
    conn = sqlite3.connect(SETTINGS.webapp_db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_webapp_db() -> None:
    """Apply schema (idempotent)."""
    schema_sql = _SCHEMA_FILE.read_text()
    conn = webapp_conn()
    try:
        conn.executescript(schema_sql)
    finally:
        conn.close()
