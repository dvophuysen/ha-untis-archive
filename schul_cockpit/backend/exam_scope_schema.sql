CREATE TABLE IF NOT EXISTS mentor_scope_plans (
 account_id INTEGER NOT NULL, cache_key TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0,
 source_json TEXT NOT NULL, result_json TEXT, updated_at TEXT NOT NULL,
 PRIMARY KEY(account_id,cache_key)
);

CREATE TABLE IF NOT EXISTS mentor_exam_exposures (
 account_id INTEGER NOT NULL, exam_id INTEGER NOT NULL REFERENCES mentor_exams(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(account_id,exam_id,user_id)
);
