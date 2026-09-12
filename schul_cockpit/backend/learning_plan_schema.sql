-- Shared source links and daily reservations; existing evidence remains authoritative.
CREATE TABLE IF NOT EXISTS learning_plan_links (
 account_id INTEGER NOT NULL, goal_key TEXT NOT NULL,
 skill_id INTEGER NOT NULL REFERENCES mentor_skills(id),
 PRIMARY KEY(account_id,goal_key,skill_id)
);
CREATE TABLE IF NOT EXISTS learning_plan_blocks (
 account_id INTEGER NOT NULL, day TEXT NOT NULL, session_id INTEGER NOT NULL REFERENCES mentor_sessions(id),
 goal_key TEXT NOT NULL, minutes INTEGER NOT NULL,
 PRIMARY KEY(account_id,day,session_id)
);
CREATE TABLE IF NOT EXISTS learning_skill_state (
 skill_id INTEGER PRIMARY KEY REFERENCES mentor_skills(id), account_id INTEGER NOT NULL,
 level INTEGER NOT NULL, label TEXT NOT NULL, due_date TEXT, last_day TEXT,
 rationale TEXT NOT NULL, rule_version TEXT NOT NULL DEFAULT '1'
);
CREATE TABLE IF NOT EXISTS learning_day_preferences (
 account_id INTEGER NOT NULL, day TEXT NOT NULL, load TEXT NOT NULL DEFAULT 'normal',
 updated_at TEXT NOT NULL, PRIMARY KEY(account_id,day)
);
