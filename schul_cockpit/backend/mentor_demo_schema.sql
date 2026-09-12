ALTER TABLE mentor_sessions ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0;
ALTER TABLE mentor_exams ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0;
ALTER TABLE mentor_exam_attempts ADD COLUMN is_test INTEGER NOT NULL DEFAULT 1;
UPDATE mentor_exam_attempts SET is_test=0 WHERE user_id IN (SELECT id FROM users WHERE role='child' AND is_admin=0);
CREATE INDEX mentor_sessions_modes ON mentor_sessions(account_id,is_demo,is_test,updated_at);
