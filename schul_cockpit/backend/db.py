"""Database connections + lightweight migrations.

- ``history.db`` (from the UNTIS Archive integration): read-only.
- ``webapp.db`` (this add-on's own data): read-write, in /data.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import SETTINGS

_SCHEMA_FILE = Path(__file__).parent / "webapp_schema.sql"


# Idempotent post-base migrations. Each step is identified by `key`; once
# applied (key recorded in schema_meta), it is never re-run. Add new steps
# at the end; never edit or remove existing ones.
_MIGRATIONS: list[tuple[str, str]] = [
    (
        "001_users_demo_mode",
        "ALTER TABLE users ADD COLUMN demo_mode INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "002_users_demo_started_at",
        "ALTER TABLE users ADD COLUMN demo_started_at TEXT",
    ),
    (
        "003_audit_log",
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            account_id INTEGER,
            op_type TEXT NOT NULL,           -- 'insert' | 'update' | 'delete'
            target_kind TEXT NOT NULL,       -- 'task' | 'subitem' | 'checkin' | 'caught_up' | 'settings' | 'todo_list'
            target_id INTEGER,
            label TEXT,                      -- human-readable e.g. 'Mathe S.42 Nr.1-5 → erledigt'
            before_json TEXT,                -- snapshot before mutation, NULL for inserts
            after_json TEXT,                 -- snapshot after, NULL for deletes
            demo_mode INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            reverted_at TEXT                 -- set when this entry was undone
        )
        """,
    ),
    (
        "004_audit_log_user_idx",
        "CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_log(user_id, created_at)",
    ),
    # --- ID-stability hardening: keep the stable Untis identifiers next to
    # the internal history.db ids, so links survive even a full re-setup of
    # the UNTIS Archive integration (which would re-number lessons/accounts).
    (
        "005_checkins_untis_period_id",
        "ALTER TABLE lesson_checkins ADD COLUMN untis_period_id INTEGER",
    ),
    (
        "006_caught_up_untis_period_id",
        "ALTER TABLE caught_up ADD COLUMN untis_period_id INTEGER",
    ),
    (
        "007_tasks_untis_period_id",
        "ALTER TABLE tasks ADD COLUMN untis_period_id INTEGER",
    ),
    (
        "008_account_ref",
        """
        CREATE TABLE IF NOT EXISTS account_ref (
            entry_id TEXT PRIMARY KEY,       -- stable HA config entry id
            account_id INTEGER NOT NULL,     -- current history.db accounts.id
            name TEXT,
            updated_at TEXT
        )
        """,
    ),
    # --- PIN auth for direct (non-Ingress) access → installable PWA.
    ("009_users_pin_hash", "ALTER TABLE users ADD COLUMN pin_hash TEXT"),
    ("010_users_pin_salt", "ALTER TABLE users ADD COLUMN pin_salt TEXT"),
    (
        "011_users_pin_failed",
        "ALTER TABLE users ADD COLUMN pin_failed_attempts INTEGER NOT NULL DEFAULT 0",
    ),
    ("012_users_pin_locked_until", "ALTER TABLE users ADD COLUMN pin_locked_until TEXT"),
    (
        "013_sessions",
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """,
    ),
    (
        "014_sessions_user_idx",
        "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
    ),
    (
        "015_push_subscriptions",
        """
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            ua_label TEXT,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """,
    ),
    (
        "016_push_subs_user_idx",
        "CREATE INDEX IF NOT EXISTS idx_push_subs_user ON push_subscriptions(user_id)",
    ),
    (
        "017_account_settings_notify_token",
        "ALTER TABLE account_settings ADD COLUMN notify_token TEXT",
    ),
    (
        "018_account_settings_auto_budget",
        # When 1, the daily budget is derived live from the official
        # Niedersachsen Hausaufgaben-Erlass + the kid's current class
        # instead of the manual default_daily_budget_minutes field.
        "ALTER TABLE account_settings ADD COLUMN auto_budget INTEGER NOT NULL DEFAULT 1",
    ),
    (
        "019_account_settings_section_override",
        # Optional: force a school section (primar/sek1/sek2) if class-name
        # heuristics get it wrong (e.g. an exotic class label).
        "ALTER TABLE account_settings ADD COLUMN school_section_override TEXT",
    ),
    (
        "020_account_exam_calendars",
        """
        CREATE TABLE IF NOT EXISTS account_exam_calendars (
            account_id INTEGER PRIMARY KEY,
            ha_entity_id TEXT NOT NULL,        -- e.g. 'calendar.klausuren_noah'
            exclude_keywords TEXT,             -- comma-separated, case-insensitive
            updated_at TEXT NOT NULL
        )
        """,
    ),
    (
        "021_subject_aliases",
        """
        CREATE TABLE IF NOT EXISTS subject_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            alias TEXT NOT NULL,               -- lower-cased trigger word/phrase
            subject_name TEXT NOT NULL,        -- canonical subject it maps to
            subject_untis_id INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE(account_id, alias)
        )
        """,
    ),
    (
        "022_exam_overrides",
        """
        CREATE TABLE IF NOT EXISTS exam_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            source_key TEXT NOT NULL,          -- stable id of the calendar event
            decision TEXT NOT NULL,            -- 'assigned' | 'dismissed'
            subject_name TEXT,                 -- when assigned
            subject_untis_id INTEGER,
            updated_at TEXT NOT NULL,
            UNIQUE(account_id, source_key)
        )
        """,
    ),
    (
        "023_manual_exams",
        """
        CREATE TABLE IF NOT EXISTS manual_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            exam_date TEXT NOT NULL,           -- YYYY-MM-DD
            subject_name TEXT NOT NULL,
            subject_untis_id INTEGER,
            title TEXT,
            note TEXT,
            created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL
        )
        """,
    ),
    (
        "024_manual_exams_idx",
        "CREATE INDEX IF NOT EXISTS idx_manual_exams_acc ON manual_exams(account_id, exam_date)",
    ),
    (
        "025_exam_progress",
        """
        CREATE TABLE IF NOT EXISTS exam_progress (
            account_id INTEGER NOT NULL,
            exam_key TEXT NOT NULL,            -- calendar source_key or 'manual:<id>'
            learn_state INTEGER,               -- 0 nicht begonnen,1 viel offen,2 mittel,3 sicher
            learn_note TEXT,
            grade TEXT,                        -- legacy free text (kept, unused)
            updated_at TEXT NOT NULL,
            PRIMARY KEY (account_id, exam_key)
        )
        """,
    ),
    (
        "026_exam_progress_grade_points",
        # Canonical grade as KMK points 0..15 (15 = 1+, 0 = 6). Note vs.
        # points is a pure display choice per school section; storing points
        # keeps everything convertible for a later Notenausgleich.
        "ALTER TABLE exam_progress ADD COLUMN grade_points INTEGER",
    ),
    (
        "027_hidden_courses",
        """
        CREATE TABLE IF NOT EXISTS hidden_courses (
            account_id INTEGER NOT NULL,
            course_key TEXT NOT NULL,          -- '<subjectId>:<teacherId>' or 'n:<subj>|<teacher>'
            subject_untis_id INTEGER,
            subject_name TEXT,
            teacher_untis_id INTEGER,
            teacher_name TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (account_id, course_key)
        )
        """,
    ),
    # --- Check-ins gehören dem Kind, nicht dem eintragenden User. Vorher
    # war (account_id, lesson_id, user_id) unique, sodass Eltern und Kind
    # je eigene Check-in-Reihen hatten und einander nicht sahen. Jetzt eine
    # geteilte Reihe pro Stunde; user_id bleibt als "letzte:r Bearbeiter:in"
    # erhalten. Beim Dedupen gewinnt der neueste Eintrag.
    (
        "028_lesson_checkins_shared_per_account",
        """
        CREATE TABLE lesson_checkins_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            untis_period_id INTEGER,
            UNIQUE(account_id, lesson_id)
        );
        INSERT INTO lesson_checkins_new
            (id, account_id, lesson_id, user_id, rating, note,
             created_at, updated_at, untis_period_id)
        SELECT id, account_id, lesson_id, user_id, rating, note,
               created_at, updated_at, untis_period_id
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY account_id, lesson_id
                       ORDER BY updated_at DESC, id DESC
                   ) AS rn
            FROM lesson_checkins
        )
        WHERE rn = 1;
        DROP TABLE lesson_checkins;
        ALTER TABLE lesson_checkins_new RENAME TO lesson_checkins;
        CREATE INDEX IF NOT EXISTS idx_checkins_account_lesson
            ON lesson_checkins(account_id, lesson_id);
        """,
    ),
    (
        "029_caught_up_shared_per_account",
        """
        CREATE TABLE caught_up_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            caught_up_at TEXT NOT NULL,
            note TEXT,
            untis_period_id INTEGER,
            UNIQUE(account_id, lesson_id)
        );
        INSERT INTO caught_up_new
            (id, account_id, lesson_id, user_id, caught_up_at, note, untis_period_id)
        SELECT id, account_id, lesson_id, user_id, caught_up_at, note, untis_period_id
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY account_id, lesson_id
                       ORDER BY caught_up_at DESC, id DESC
                   ) AS rn
            FROM caught_up
        )
        WHERE rn = 1;
        DROP TABLE caught_up;
        ALTER TABLE caught_up_new RENAME TO caught_up;
        """,
    ),
]


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


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    applied = {
        r[0]
        for r in conn.execute(
            "SELECT key FROM schema_meta WHERE key LIKE 'migration:%'"
        ).fetchall()
    }
    for key, sql in _MIGRATIONS:
        marker = f"migration:{key}"
        if marker in applied:
            continue
        # ALTER TABLE ADD COLUMN raises if the column already exists (e.g. on
        # databases where the migration was applied by another process). Skip
        # silently in that case.
        try:
            conn.executescript(sql)
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if "duplicate column name" not in msg and "already exists" not in msg:
                raise
        conn.execute(
            "INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, '1')",
            (marker,),
        )


def init_webapp_db() -> None:
    """Apply base schema + pending migrations (idempotent)."""
    schema_sql = _SCHEMA_FILE.read_text()
    conn = webapp_conn()
    try:
        conn.executescript(schema_sql)
        _apply_migrations(conn)
    finally:
        conn.close()
