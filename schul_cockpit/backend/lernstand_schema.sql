-- Lernstand: die Themen einer Arbeit (aus der offiziellen Themenliste der
-- Lehrkraft) und je Thema die Stufe: neu, angefangen, wackelt, sitzt, gefestigt.
CREATE TABLE IF NOT EXISTS exam_topics (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, subject TEXT NOT NULL,
 exam_key TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0,
 title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
 places_json TEXT NOT NULL DEFAULT '[]',
 origin TEXT NOT NULL DEFAULT 'notice', notice_id INTEGER, notice_hash TEXT NOT NULL DEFAULT '',
 stale INTEGER NOT NULL DEFAULT 0,
 stage TEXT NOT NULL DEFAULT 'neu', reason TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
 self_view TEXT, sat_at TEXT, checks INTEGER NOT NULL DEFAULT 0, next_check TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(account_id, exam_key, title)
);
CREATE INDEX IF NOT EXISTS idx_exam_topics_exam ON exam_topics(account_id, exam_key, position);
-- Jede bewertete Antwort in einer Einheit zu einem Thema, mit den Signalen,
-- aus denen die Stufe abgelesen wird. seconds: Zeit von Aufgabe bis Antwort;
-- edits: Löschungen beim Tippen; re_explained: der Mentor musste dasselbe
-- ein zweites Mal anders erklären.
CREATE TABLE IF NOT EXISTS topic_answers (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL,
 topic_id INTEGER NOT NULL REFERENCES exam_topics(id) ON DELETE CASCADE,
 session_id INTEGER NOT NULL, message_id INTEGER, task_kind TEXT NOT NULL DEFAULT '',
 result TEXT NOT NULL, help_used INTEGER NOT NULL DEFAULT 0, seconds INTEGER, edits INTEGER,
 re_explained INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_topic_answers_topic ON topic_answers(topic_id, created_at);
-- Jeder Stufenwechsel mit Grund; steuert die nächste Einheit und bleibt nachlesbar.
CREATE TABLE IF NOT EXISTS topic_events (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL,
 topic_id INTEGER NOT NULL REFERENCES exam_topics(id) ON DELETE CASCADE,
 session_id INTEGER, stage_before TEXT NOT NULL, stage_after TEXT NOT NULL,
 reason TEXT NOT NULL, created_at TEXT NOT NULL
);
ALTER TABLE mentor_sessions ADD COLUMN topic_id INTEGER;
