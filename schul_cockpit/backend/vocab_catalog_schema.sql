-- Additive import workspace. Existing words and attempts are never deleted.
CREATE TABLE IF NOT EXISTS vocab_catalog_runs (
 id TEXT PRIMARY KEY, account_id INTEGER NOT NULL, subject TEXT NOT NULL,
 book_key TEXT NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL,
 digest TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
 report TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, activated_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_vocab_catalog_active
 ON vocab_catalog_runs(account_id,subject,book_key) WHERE status='active';
CREATE TABLE IF NOT EXISTS vocab_catalog_entries (
 run_id TEXT NOT NULL REFERENCES vocab_catalog_runs(id),
 occurrence INTEGER NOT NULL, word_id INTEGER NOT NULL REFERENCES vocab_words(id),
 PRIMARY KEY(run_id,occurrence)
);
CREATE TABLE IF NOT EXISTS vocab_learning_aliases (
 account_id INTEGER NOT NULL, word_id INTEGER NOT NULL REFERENCES vocab_words(id),
 canonical_id INTEGER NOT NULL REFERENCES vocab_words(id),
 PRIMARY KEY(account_id,word_id)
);
CREATE INDEX IF NOT EXISTS idx_vocab_learning_canonical ON vocab_learning_aliases(account_id,canonical_id);
CREATE TABLE IF NOT EXISTS vocab_page_reads (
 account_id INTEGER NOT NULL, material_id INTEGER NOT NULL,
 physical_page INTEGER NOT NULL, side TEXT NOT NULL, fingerprint TEXT NOT NULL,
 response TEXT NOT NULL, model TEXT NOT NULL, foundry TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(account_id,material_id,physical_page,side,fingerprint)
);
