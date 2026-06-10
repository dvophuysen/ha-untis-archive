-- Schul-Cockpit app database. Lives in the add-on /data volume.
-- Untis archive data is NEVER written here; we only read history.db.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ha_user_id TEXT UNIQUE NOT NULL,        -- from Ingress header X-Remote-User-Id
    display_name TEXT,                      -- from X-Remote-User-Name
    role TEXT NOT NULL DEFAULT 'pending',   -- 'admin' | 'parent' | 'child' | 'pending'
    is_admin INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

-- Links a user to one or more Untis accounts (children) from history.db.
-- A child sees only its own account_id. A parent can be linked to several.
CREATE TABLE IF NOT EXISTS user_account_links (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL,
    can_edit INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, account_id)
);

CREATE TABLE IF NOT EXISTS account_todo_lists (
    account_id INTEGER PRIMARY KEY,
    ha_entity_id TEXT NOT NULL,              -- e.g. 'todo.josia_schule'
    display_name TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_settings (
    account_id INTEGER PRIMARY KEY,
    default_daily_budget_minutes INTEGER NOT NULL DEFAULT 60,
    -- JSON object, keys mon/tue/wed/thu/fri/sat/sun, values minutes.
    -- Missing keys fall back to default_daily_budget_minutes.
    budget_overrides_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Check-ins gehören dem Kind (account), nicht dem eintragenden User.
-- Eltern und Kind sehen denselben Check-in; user_id ist nur die zuletzt
-- bearbeitende Person (für das Audit-Log).
CREATE TABLE IF NOT EXISTS lesson_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL,              -- references lessons.id in history.db
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL,                 -- 1=worried, 2=neutral, 3=happy
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, lesson_id)
);
CREATE INDEX IF NOT EXISTS idx_checkins_account_lesson
    ON lesson_checkins(account_id, lesson_id);

CREATE TABLE IF NOT EXISTS caught_up (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    caught_up_at TEXT NOT NULL,
    note TEXT,
    UNIQUE(account_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    ha_uid TEXT,                             -- NULL for manually created tasks
    title TEXT NOT NULL,
    subject_untis_id INTEGER,
    subject_name TEXT,
    task_type TEXT NOT NULL DEFAULT 'homework',
        -- 'homework'|'exam_prep'|'catch_up'|'practice'|'project'
    status TEXT NOT NULL DEFAULT 'open',
        -- 'open'|'in_progress'|'done'|'skipped'
    estimated_minutes INTEGER,
    due_date TEXT,                           -- YYYY-MM-DD
    due_time TEXT,                           -- HH:MM
    lesson_id INTEGER,                       -- optional link into history.db
    notes TEXT,
    source TEXT NOT NULL,                    -- 'ha_todo'|'manual'|'untis_exam'
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    ha_last_synced_at TEXT,
    UNIQUE(account_id, ha_uid)
);
CREATE INDEX IF NOT EXISTS idx_tasks_account_status
    ON tasks(account_id, status, due_date);

CREATE TABLE IF NOT EXISTS task_subitems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_time_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    minutes INTEGER
);
