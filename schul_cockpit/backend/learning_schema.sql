-- Learning data belongs to the app database and its existing backup/restore.
-- Namespaced migration: independent of concurrent calendar migrations.
CREATE TABLE IF NOT EXISTS learning_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    school_year TEXT NOT NULL,
    grade INTEGER NOT NULL CHECK(grade BETWEEN 1 AND 13),
    region TEXT NOT NULL DEFAULT '',
    school_type TEXT NOT NULL DEFAULT '',
    personal_goal TEXT NOT NULL DEFAULT '',
    daily_minutes INTEGER NOT NULL DEFAULT 15 CHECK(daily_minutes BETWEEN 0 AND 120),
    max_sessions INTEGER NOT NULL DEFAULT 2 CHECK(max_sessions BETWEEN 1 AND 5),
    study_days TEXT NOT NULL DEFAULT '[0,1,2,3,4]',
    ai_enabled INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(account_id, school_year)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_active_profile
    ON learning_profiles(account_id) WHERE active = 1;
CREATE TABLE IF NOT EXISTS learning_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES learning_profiles(id),
    subject TEXT NOT NULL,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    method TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    priority INTEGER NOT NULL DEFAULT 1,
    source_note TEXT NOT NULL DEFAULT '',
    target_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_topics_profile ON learning_topics(profile_id, status);
CREATE TABLE IF NOT EXISTS learning_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES learning_topics(id),
    title TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    content_text TEXT NOT NULL DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0,
    filename TEXT,
    mime_type TEXT,
    file_bytes BLOB,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_materials_topic ON learning_materials(topic_id);
CREATE TABLE IF NOT EXISTS learning_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES learning_topics(id),
    kind TEXT NOT NULL DEFAULT 'practice',
    afb INTEGER NOT NULL CHECK(afb BETWEEN 1 AND 3),
    operator TEXT NOT NULL,
    prompt TEXT NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    hint TEXT NOT NULL DEFAULT '',
    solution TEXT NOT NULL,
    criteria TEXT NOT NULL,
    minutes INTEGER NOT NULL DEFAULT 5 CHECK(minutes BETWEEN 1 AND 30),
    published INTEGER NOT NULL DEFAULT 0,
    origin TEXT NOT NULL DEFAULT 'manual',
    source_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_activities_topic ON learning_activities(topic_id, published);
CREATE TABLE IF NOT EXISTS learning_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL REFERENCES learning_activities(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    snapshot TEXT NOT NULL,
    answer TEXT,
    help_used INTEGER NOT NULL DEFAULT 0,
    outcome TEXT,
    difficulty TEXT,
    minutes INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_activity ON learning_sessions(activity_id, completed_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_one_open_session
    ON learning_sessions(activity_id, user_id) WHERE completed_at IS NULL;
CREATE TABLE IF NOT EXISTS learning_reviews (
    activity_id INTEGER PRIMARY KEY REFERENCES learning_activities(id),
    next_due TEXT NOT NULL,
    streak INTEGER NOT NULL DEFAULT 0,
    last_outcome TEXT NOT NULL,
    last_session_id INTEGER NOT NULL REFERENCES learning_sessions(id)
);

CREATE TABLE IF NOT EXISTS learning_ai_usage (
    account_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(account_id, day)
);
