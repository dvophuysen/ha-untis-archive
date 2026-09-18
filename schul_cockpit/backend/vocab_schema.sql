-- Vokabeltrainer: Wörter aus den Originalseiten (Begleitband, Schulbuch), je
-- Wort zwei Stufen: 1 Bedeutung (gesprochen), 2 Schreibweise (getippt, nur in
-- die Fremdsprache). Die Stufe je Wort wird aus den Versuchen abgelesen.
CREATE TABLE IF NOT EXISTS vocab_words (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, subject TEXT NOT NULL,
 material_id INTEGER NOT NULL, source_label TEXT NOT NULL DEFAULT '', page INTEGER,
 unit TEXT NOT NULL DEFAULT '', section TEXT NOT NULL DEFAULT '', box TEXT NOT NULL DEFAULT '',
 position INTEGER NOT NULL DEFAULT 0,
 foreign_word TEXT NOT NULL, plain TEXT NOT NULL, meanings_json TEXT NOT NULL DEFAULT '[]',
 grammar TEXT NOT NULL DEFAULT '', forms_json TEXT NOT NULL DEFAULT '{}', example TEXT NOT NULL DEFAULT '',
 hidden INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
 UNIQUE(account_id, material_id, foreign_word)
);
CREATE INDEX IF NOT EXISTS idx_vocab_words_unit ON vocab_words(account_id, subject, unit, position);
CREATE TABLE IF NOT EXISTS vocab_attempts (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL,
 word_id INTEGER NOT NULL REFERENCES vocab_words(id) ON DELETE CASCADE,
 stage INTEGER NOT NULL, direction TEXT NOT NULL, answer TEXT NOT NULL DEFAULT '',
 result TEXT NOT NULL, spoken INTEGER NOT NULL DEFAULT 0, seconds INTEGER, edits INTEGER,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vocab_attempts_word ON vocab_attempts(word_id, stage, created_at);
-- Welche Seiten schon in Wörter zerlegt sind (je Auswertungsstand der Seite).
CREATE TABLE IF NOT EXISTS vocab_extractions (
 material_id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, text_hash TEXT NOT NULL,
 words INTEGER NOT NULL DEFAULT 0, error TEXT, updated_at TEXT NOT NULL
);
