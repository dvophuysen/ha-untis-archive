CREATE TABLE IF NOT EXISTS learning_discovery_settings (
 account_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS learning_discovery_items (
 account_id INTEGER NOT NULL, profile_id INTEGER NOT NULL, lesson_id INTEGER NOT NULL,
 fingerprint TEXT NOT NULL, topic_id INTEGER, note TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(account_id,profile_id,lesson_id)
);
CREATE TABLE IF NOT EXISTS learning_discovery_topics (
 topic_id INTEGER PRIMARY KEY, explanation TEXT NOT NULL, bridge TEXT NOT NULL,
 prerequisites TEXT NOT NULL, outlook TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learning_discovery_runs (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, created_at TEXT NOT NULL,
 lessons INTEGER NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL
);
