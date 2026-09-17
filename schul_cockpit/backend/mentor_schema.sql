CREATE TABLE IF NOT EXISTS mentor_settings (
 account_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
 background_enabled INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mentor_ai_config (
 id INTEGER PRIMARY KEY CHECK(id=1), monthly_micro INTEGER NOT NULL DEFAULT 50000000,
 warning_micro INTEGER NOT NULL DEFAULT 40000000, background_micro INTEGER NOT NULL DEFAULT 5000000,
 opening_month TEXT NOT NULL, opening_micro INTEGER NOT NULL DEFAULT 0,
 opening_confirmed INTEGER NOT NULL DEFAULT 0, background_model TEXT DEFAULT 'niedrig', updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mentor_ai_calls (
 id TEXT PRIMARY KEY, account_id INTEGER NOT NULL, session_id INTEGER, purpose TEXT NOT NULL,
 month TEXT NOT NULL, day TEXT NOT NULL, model TEXT NOT NULL,
 status TEXT NOT NULL, reserved_micro INTEGER NOT NULL, charged_micro INTEGER NOT NULL DEFAULT 0,
 input_tokens INTEGER, output_tokens INTEGER, input_rate REAL NOT NULL, output_rate REAL NOT NULL,
 created_at TEXT NOT NULL, finished_at TEXT, error TEXT, over_budget TEXT
);
CREATE INDEX IF NOT EXISTS idx_mentor_ai_month ON mentor_ai_calls(month,account_id,status);
CREATE TABLE IF NOT EXISTS mentor_skills (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, subject TEXT NOT NULL, title TEXT NOT NULL,
 objective TEXT NOT NULL, source_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, UNIQUE(account_id,subject,title)
);
CREATE TABLE IF NOT EXISTS mentor_sessions (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, user_id INTEGER NOT NULL, skill_id INTEGER,
 subject TEXT NOT NULL, goal TEXT NOT NULL, is_test INTEGER NOT NULL DEFAULT 0, phase TEXT NOT NULL DEFAULT 'orient',
 status TEXT NOT NULL DEFAULT 'active', version INTEGER NOT NULL DEFAULT 0,
 max_minutes INTEGER NOT NULL DEFAULT 10, elapsed_seconds INTEGER NOT NULL DEFAULT 0,
 active_since TEXT, turns INTEGER NOT NULL DEFAULT 0, help_count INTEGER NOT NULL DEFAULT 0,
 current_task TEXT, task_help INTEGER NOT NULL DEFAULT 0, task_started_at TEXT,
 summary TEXT NOT NULL DEFAULT '', source_json TEXT NOT NULL DEFAULT '{}',
 context_hash TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 pending_key TEXT, pending_since TEXT, quiz_json TEXT, FOREIGN KEY(skill_id) REFERENCES mentor_skills(id)
);
CREATE INDEX IF NOT EXISTS idx_mentor_sessions_account ON mentor_sessions(account_id,updated_at);
CREATE TABLE IF NOT EXISTS mentor_messages (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, session_id INTEGER NOT NULL REFERENCES mentor_sessions(id) ON DELETE CASCADE,
 request_key TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL, UNIQUE(session_id,request_key,role)
);
CREATE TABLE IF NOT EXISTS mentor_evidence (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, skill_id INTEGER NOT NULL REFERENCES mentor_skills(id),
 session_id INTEGER REFERENCES mentor_sessions(id), exam_attempt_id INTEGER, message_id INTEGER,
 task_json TEXT NOT NULL, answer TEXT NOT NULL, result TEXT NOT NULL,
 rationale TEXT NOT NULL, help_used INTEGER NOT NULL, source TEXT NOT NULL DEFAULT 'ai_assessment',
 variant_hash TEXT NOT NULL, invalidated INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, UNIQUE(session_id,message_id), UNIQUE(exam_attempt_id,variant_hash)
);
CREATE INDEX IF NOT EXISTS idx_mentor_evidence_skill ON mentor_evidence(account_id,skill_id,created_at);
CREATE TABLE IF NOT EXISTS mentor_reviews (
 skill_id INTEGER PRIMARY KEY REFERENCES mentor_skills(id), account_id INTEGER NOT NULL,
 due_date TEXT NOT NULL, last_evidence_id INTEGER NOT NULL REFERENCES mentor_evidence(id), updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mentor_attachments (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, session_id INTEGER NOT NULL REFERENCES mentor_sessions(id) ON DELETE CASCADE,
 mime_type TEXT NOT NULL, file_bytes BLOB NOT NULL, sha256 TEXT NOT NULL,
 transcript TEXT, created_at TEXT NOT NULL, UNIQUE(session_id,sha256)
);
CREATE TABLE IF NOT EXISTS mentor_jobs (
 account_id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
 next_run TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT
);
CREATE TABLE IF NOT EXISTS mentor_exams (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, title TEXT NOT NULL, subject TEXT NOT NULL,
 scope_json TEXT NOT NULL, tasks_json TEXT NOT NULL, minutes INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, published_at TEXT
);
CREATE TABLE IF NOT EXISTS mentor_exam_attempts (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, exam_id INTEGER NOT NULL REFERENCES mentor_exams(id),
 user_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'active', answers_json TEXT NOT NULL DEFAULT '{}',
 snapshot TEXT NOT NULL, feedback_json TEXT, version INTEGER NOT NULL DEFAULT 0,
 elapsed_seconds INTEGER NOT NULL DEFAULT 0, active_since TEXT, started_at TEXT NOT NULL,
 submitted_at TEXT, UNIQUE(exam_id,user_id)
);

CREATE TABLE IF NOT EXISTS mentor_exam_photos (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, attempt_id INTEGER NOT NULL REFERENCES mentor_exam_attempts(id),
 question_index INTEGER NOT NULL, mime_type TEXT NOT NULL, file_bytes BLOB NOT NULL, sha256 TEXT NOT NULL,
 transcript TEXT, created_at TEXT NOT NULL, UNIQUE(attempt_id,question_index,sha256)
);
CREATE TABLE IF NOT EXISTS mentor_quality_runs (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, model TEXT NOT NULL, fingerprint TEXT NOT NULL,
 batch INTEGER NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(account_id,model,fingerprint,batch)
);
