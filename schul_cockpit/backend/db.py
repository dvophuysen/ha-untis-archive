"""Database connections + lightweight migrations.

- ``history.db`` (from the UNTIS Archive integration): read-only.
- ``webapp.db`` (this add-on's own data): read-write, in /data.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
import threading
from pathlib import Path

from .config import SETTINGS

_SCHEMA_FILE = Path(__file__).parent / "webapp_schema.sql"


# Idempotent post-base migrations. Each step is identified by `key`; once
# applied (key recorded in schema_meta), it is never re-run. Add new steps
# at the end; never edit or remove existing ones.
_MIGRATIONS: list[tuple[str, str]] = [
    (
        "001_users_demo_mode",
        "ALTER TABLE users ADD COLUMN demo_mode INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "002_users_demo_started_at",
        "ALTER TABLE users ADD COLUMN demo_started_at TEXT",
    ),
    (
        "003_audit_log",
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            account_id INTEGER,
            op_type TEXT NOT NULL,           -- 'insert' | 'update' | 'delete'
            target_kind TEXT NOT NULL,       -- 'task' | 'subitem' | 'checkin' | 'caught_up' | 'settings' | 'todo_list'
            target_id INTEGER,
            label TEXT,                      -- human-readable e.g. 'Mathe S.42 Nr.1-5 → erledigt'
            before_json TEXT,                -- snapshot before mutation, NULL for inserts
            after_json TEXT,                 -- snapshot after, NULL for deletes
            demo_mode INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            reverted_at TEXT                 -- set when this entry was undone
        )
        """,
    ),
    (
        "004_audit_log_user_idx",
        "CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_log(user_id, created_at)",
    ),
    # --- ID-stability hardening: keep the stable Untis identifiers next to
    # the internal history.db ids, so links survive even a full re-setup of
    # the UNTIS Archive integration (which would re-number lessons/accounts).
    (
        "005_checkins_untis_period_id",
        "ALTER TABLE lesson_checkins ADD COLUMN untis_period_id INTEGER",
    ),
    (
        "006_caught_up_untis_period_id",
        "ALTER TABLE caught_up ADD COLUMN untis_period_id INTEGER",
    ),
    (
        "007_tasks_untis_period_id",
        "ALTER TABLE tasks ADD COLUMN untis_period_id INTEGER",
    ),
    (
        "008_account_ref",
        """
        CREATE TABLE IF NOT EXISTS account_ref (
            entry_id TEXT PRIMARY KEY,       -- stable HA config entry id
            account_id INTEGER NOT NULL,     -- current history.db accounts.id
            name TEXT,
            updated_at TEXT
        )
        """,
    ),
    # --- PIN auth for direct (non-Ingress) access → installable PWA.
    ("009_users_pin_hash", "ALTER TABLE users ADD COLUMN pin_hash TEXT"),
    ("010_users_pin_salt", "ALTER TABLE users ADD COLUMN pin_salt TEXT"),
    (
        "011_users_pin_failed",
        "ALTER TABLE users ADD COLUMN pin_failed_attempts INTEGER NOT NULL DEFAULT 0",
    ),
    ("012_users_pin_locked_until", "ALTER TABLE users ADD COLUMN pin_locked_until TEXT"),
    (
        "013_sessions",
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """,
    ),
    (
        "014_sessions_user_idx",
        "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
    ),
    (
        "015_push_subscriptions",
        """
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            ua_label TEXT,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """,
    ),
    (
        "016_push_subs_user_idx",
        "CREATE INDEX IF NOT EXISTS idx_push_subs_user ON push_subscriptions(user_id)",
    ),
    (
        "017_account_settings_notify_token",
        "ALTER TABLE account_settings ADD COLUMN notify_token TEXT",
    ),
    (
        "018_account_settings_auto_budget",
        # When 1, the daily budget is derived live from the official
        # Niedersachsen Hausaufgaben-Erlass + the kid's current class
        # instead of the manual default_daily_budget_minutes field.
        "ALTER TABLE account_settings ADD COLUMN auto_budget INTEGER NOT NULL DEFAULT 1",
    ),
    (
        "019_account_settings_section_override",
        # Optional: force a school section (primar/sek1/sek2) if class-name
        # heuristics get it wrong (e.g. an exotic class label).
        "ALTER TABLE account_settings ADD COLUMN school_section_override TEXT",
    ),
    (
        "020_account_exam_calendars",
        """
        CREATE TABLE IF NOT EXISTS account_exam_calendars (
            account_id INTEGER PRIMARY KEY,
            ha_entity_id TEXT NOT NULL,        -- e.g. 'calendar.klausuren_anna'
            exclude_keywords TEXT,             -- comma-separated, case-insensitive
            updated_at TEXT NOT NULL
        )
        """,
    ),
    (
        "021_subject_aliases",
        """
        CREATE TABLE IF NOT EXISTS subject_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            alias TEXT NOT NULL,               -- lower-cased trigger word/phrase
            subject_name TEXT NOT NULL,        -- canonical subject it maps to
            subject_untis_id INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE(account_id, alias)
        )
        """,
    ),
    (
        "022_exam_overrides",
        """
        CREATE TABLE IF NOT EXISTS exam_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            source_key TEXT NOT NULL,          -- stable id of the calendar event
            decision TEXT NOT NULL,            -- 'assigned' | 'dismissed'
            subject_name TEXT,                 -- when assigned
            subject_untis_id INTEGER,
            updated_at TEXT NOT NULL,
            UNIQUE(account_id, source_key)
        )
        """,
    ),
    (
        "023_manual_exams",
        """
        CREATE TABLE IF NOT EXISTS manual_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            exam_date TEXT NOT NULL,           -- YYYY-MM-DD
            subject_name TEXT NOT NULL,
            subject_untis_id INTEGER,
            title TEXT,
            note TEXT,
            created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL
        )
        """,
    ),
    (
        "024_manual_exams_idx",
        "CREATE INDEX IF NOT EXISTS idx_manual_exams_acc ON manual_exams(account_id, exam_date)",
    ),
    (
        "025_exam_progress",
        """
        CREATE TABLE IF NOT EXISTS exam_progress (
            account_id INTEGER NOT NULL,
            exam_key TEXT NOT NULL,            -- calendar source_key or 'manual:<id>'
            learn_state INTEGER,               -- 0 nicht begonnen,1 viel offen,2 mittel,3 sicher
            learn_note TEXT,
            grade TEXT,                        -- legacy free text (kept, unused)
            updated_at TEXT NOT NULL,
            PRIMARY KEY (account_id, exam_key)
        )
        """,
    ),
    (
        "026_exam_progress_grade_points",
        # Canonical grade as KMK points 0..15 (15 = 1+, 0 = 6). Note vs.
        # points is a pure display choice per school section; storing points
        # keeps everything convertible for a later Notenausgleich.
        "ALTER TABLE exam_progress ADD COLUMN grade_points INTEGER",
    ),
    (
        "027_hidden_courses",
        """
        CREATE TABLE IF NOT EXISTS hidden_courses (
            account_id INTEGER NOT NULL,
            course_key TEXT NOT NULL,          -- '<subjectId>:<teacherId>' or 'n:<subj>|<teacher>'
            subject_untis_id INTEGER,
            subject_name TEXT,
            teacher_untis_id INTEGER,
            teacher_name TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (account_id, course_key)
        )
        """,
    ),
    # --- Check-ins gehören dem Kind, nicht dem eintragenden User. Vorher
    # war (account_id, lesson_id, user_id) unique, sodass Eltern und Kind
    # je eigene Check-in-Reihen hatten und einander nicht sahen. Jetzt eine
    # geteilte Reihe pro Stunde; user_id bleibt als "letzte:r Bearbeiter:in"
    # erhalten. Beim Dedupen gewinnt der neueste Eintrag.
    (
        "028_lesson_checkins_shared_per_account",
        """
        CREATE TABLE lesson_checkins_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            untis_period_id INTEGER,
            UNIQUE(account_id, lesson_id)
        );
        INSERT INTO lesson_checkins_new
            (id, account_id, lesson_id, user_id, rating, note,
             created_at, updated_at, untis_period_id)
        SELECT id, account_id, lesson_id, user_id, rating, note,
               created_at, updated_at, untis_period_id
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY account_id, lesson_id
                       ORDER BY updated_at DESC, id DESC
                   ) AS rn
            FROM lesson_checkins
        )
        WHERE rn = 1;
        DROP TABLE lesson_checkins;
        ALTER TABLE lesson_checkins_new RENAME TO lesson_checkins;
        CREATE INDEX IF NOT EXISTS idx_checkins_account_lesson
            ON lesson_checkins(account_id, lesson_id);
        """,
    ),
    (
        "029_caught_up_shared_per_account",
        """
        CREATE TABLE caught_up_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            caught_up_at TEXT NOT NULL,
            note TEXT,
            untis_period_id INTEGER,
            UNIQUE(account_id, lesson_id)
        );
        INSERT INTO caught_up_new
            (id, account_id, lesson_id, user_id, caught_up_at, note, untis_period_id)
        SELECT id, account_id, lesson_id, user_id, caught_up_at, note, untis_period_id
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY account_id, lesson_id
                       ORDER BY caught_up_at DESC, id DESC
                   ) AS rn
            FROM caught_up
        )
        WHERE rn = 1;
        DROP TABLE caught_up;
        ALTER TABLE caught_up_new RENAME TO caught_up;
        """,
    ),
]

_MIGRATIONS.append((
    "learning_001",
    (Path(__file__).parent / "learning_schema.sql").read_text(),
))


_MIGRATIONS.append(("push_002_drop_web_push", """
-- D65: Erinnerungen laufen über die Home-Assistant-App; der Web-Push-Weg
-- (Abonnements, VAPID-Schlüssel) ist entfernt. reminder_deliveries bleibt
-- als Verlauf stehen.
DROP TABLE IF EXISTS push_subscriptions;
DELETE FROM schema_meta WHERE key LIKE 'vapid:%';
"""))

_MIGRATIONS.append(("learning_002", (Path(__file__).parent / "discovery_schema.sql").read_text()))

_MIGRATIONS.append(("mentor_001", (Path(__file__).parent / "mentor_schema.sql").read_text()))

_MIGRATIONS.append(("mentor_002", (Path(__file__).parent / "mentor_demo_schema.sql").read_text()))

_MIGRATIONS.append(("mentor_003", (Path(__file__).parent / "exam_scope_schema.sql").read_text()))

_MIGRATIONS.append(("learning_plan_001", (Path(__file__).parent / "learning_plan_schema.sql").read_text()))

_MIGRATIONS.append(("lernstand_001", (Path(__file__).parent / "lernstand_schema.sql").read_text()))

_MIGRATIONS.append(("vocab_001", (Path(__file__).parent / "vocab_schema.sql").read_text()))

# Preserve every existing value and stable ID. A comment can now stand on its
# own; NULL is never interpreted as an understanding score.
_MIGRATIONS.append(("checkins_030_optional_rating", """
BEGIN IMMEDIATE;
CREATE TABLE lesson_checkins_optional (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    untis_period_id INTEGER,
    UNIQUE(account_id, lesson_id)
);
INSERT INTO lesson_checkins_optional
    (id, account_id, lesson_id, user_id, rating, note, created_at, updated_at, untis_period_id)
SELECT id, account_id, lesson_id, user_id, rating, note, created_at, updated_at, untis_period_id
FROM lesson_checkins;
DROP TABLE lesson_checkins;
ALTER TABLE lesson_checkins_optional RENAME TO lesson_checkins;
CREATE INDEX idx_checkins_account_lesson ON lesson_checkins(account_id, lesson_id);
INSERT INTO schema_meta(key, value) VALUES ('migration:checkins_030_optional_rating', '1');
COMMIT;
"""))

_MIGRATIONS.append(("packing_001", """
CREATE TABLE IF NOT EXISTS packing_items (
    account_id INTEGER NOT NULL,
    school_day TEXT NOT NULL,
    item_key TEXT NOT NULL,
    done INTEGER NOT NULL CHECK(done IN (0,1)),
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    confirmed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY(account_id, school_day, item_key)
);
"""))

_MIGRATIONS.append(("reminders_001", """
CREATE TABLE IF NOT EXISTS reminder_settings (
 account_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0, remind_at TEXT
);
CREATE TABLE IF NOT EXISTS reminder_deliveries (
 account_id INTEGER NOT NULL, school_day TEXT NOT NULL, subscription_id INTEGER NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT,
 PRIMARY KEY(account_id,school_day,subscription_id)
);
"""))

_MIGRATIONS.append(("digital_textbooks_001", """
CREATE TABLE IF NOT EXISTS digital_textbook_credentials (
 account_id INTEGER PRIMARY KEY,
 portal_url TEXT NOT NULL,
 username TEXT NOT NULL,
 password_ciphertext TEXT NOT NULL,
 verified_at TEXT,
 verification_status TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
"""))

_MIGRATIONS.append(("digital_textbooks_002_catalog", """
CREATE TABLE IF NOT EXISTS digital_textbook_catalog (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL,
 title TEXT NOT NULL,
 provider TEXT,
 launch_url TEXT,
 subject_name TEXT,
 discovered_at TEXT NOT NULL,
 UNIQUE(account_id,title)
);
CREATE INDEX IF NOT EXISTS idx_textbook_catalog_account ON digital_textbook_catalog(account_id,title);
"""))

_MIGRATIONS.append(("iserv_calendars_001", """
CREATE TABLE IF NOT EXISTS iserv_calendars (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL,
 url TEXT NOT NULL,
 name TEXT NOT NULL,
 color TEXT,
 role TEXT NOT NULL DEFAULT 'unused',
 last_seen TEXT,
 missing_since TEXT,
 created_at TEXT NOT NULL,
 UNIQUE(account_id,url)
);
CREATE INDEX IF NOT EXISTS idx_iserv_calendars_account ON iserv_calendars(account_id,role);
CREATE TABLE IF NOT EXISTS iserv_calendar_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL,
 calendar_id INTEGER NOT NULL REFERENCES iserv_calendars(id) ON DELETE CASCADE,
 uid TEXT NOT NULL DEFAULT '',
 summary TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '',
 location TEXT NOT NULL DEFAULT '',
 start_date TEXT NOT NULL,
 end_date TEXT NOT NULL,
 start_time TEXT,
 end_time TEXT,
 all_day INTEGER NOT NULL DEFAULT 0,
 fetched_at TEXT NOT NULL,
 UNIQUE(account_id,calendar_id,uid,start_date,start_time)
);
CREATE INDEX IF NOT EXISTS idx_iserv_events_window ON iserv_calendar_events(account_id,start_date);
CREATE TABLE IF NOT EXISTS iserv_calendar_sync (
 account_id INTEGER PRIMARY KEY,
 status TEXT NOT NULL DEFAULT 'pending',
 error TEXT,
 calendars INTEGER NOT NULL DEFAULT 0,
 events INTEGER NOT NULL DEFAULT 0,
 synced_at TEXT
);
"""))

_MIGRATIONS.append(("materials_001", """
CREATE TABLE IF NOT EXISTS materials (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL,
 kind TEXT NOT NULL DEFAULT 'other',
 subject_name TEXT,
 title TEXT NOT NULL DEFAULT '',
 summary TEXT NOT NULL DEFAULT '',
 content_text TEXT NOT NULL DEFAULT '',
 document_date TEXT,
 period_start TEXT,
 period_end TEXT,
 captured_at TEXT,
 created_by INTEGER,
 filename TEXT,
 mime_type TEXT,
 file_bytes BLOB,
 page_count INTEGER NOT NULL DEFAULT 0,
 verified INTEGER NOT NULL DEFAULT 0,
 contains_solutions INTEGER NOT NULL DEFAULT 0,
 hidden INTEGER NOT NULL DEFAULT 0,
 locked_fields TEXT NOT NULL DEFAULT '[]',
 analysis_state TEXT NOT NULL DEFAULT 'pending',
 analysis_model TEXT,
 analysis_version INTEGER NOT NULL DEFAULT 0,
 analyzed_at TEXT,
 analysis_error TEXT,
 confidence REAL,
 legacy_material_id INTEGER,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_materials_account ON materials(account_id,hidden,document_date);
CREATE INDEX IF NOT EXISTS idx_materials_subject ON materials(account_id,subject_name);
CREATE INDEX IF NOT EXISTS idx_materials_state ON materials(analysis_state,analysis_version);
CREATE TABLE IF NOT EXISTS material_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
 kind TEXT NOT NULL,
 target_id INTEGER NOT NULL,
 origin TEXT NOT NULL DEFAULT 'ai',
 created_at TEXT NOT NULL,
 UNIQUE(material_id,kind,target_id)
);
CREATE INDEX IF NOT EXISTS idx_material_links_target ON material_links(kind,target_id);
"""))

_MIGRATIONS.append(("materials_002_legacy", """
INSERT INTO materials(account_id,kind,subject_name,title,content_text,filename,mime_type,file_bytes,
 verified,analysis_state,analysis_version,locked_fields,legacy_material_id,created_at,updated_at)
SELECT p.account_id,
 CASE m.source_kind WHEN 'worksheet' THEN 'worksheet' WHEN 'book' THEN 'book_page'
  WHEN 'teacher' THEN 'assignment' WHEN 'own' THEN 'notes' ELSE 'other' END,
 t.subject, m.title, m.content_text, m.filename, m.mime_type, m.file_bytes,
 m.verified,
 CASE WHEN trim(m.content_text)!='' THEN 'ready' ELSE 'pending' END,
 0,
 CASE WHEN m.verified=1 AND trim(m.content_text)!='' THEN '["content_text","title"]' ELSE '[]' END,
 m.id, m.created_at, m.created_at
FROM learning_materials m
JOIN learning_topics t ON t.id=m.topic_id
JOIN learning_profiles p ON p.id=t.profile_id
WHERE NOT EXISTS (SELECT 1 FROM materials x WHERE x.legacy_material_id=m.id);
INSERT OR IGNORE INTO material_links(material_id,kind,target_id,origin,created_at)
SELECT n.id,'topic',m.topic_id,'mensch',n.created_at
FROM materials n JOIN learning_materials m ON m.id=n.legacy_material_id;
"""))

# Parents may write in a child's verlauf, so a message has to say who wrote it.
_MIGRATIONS.append(("mentor_message_author", "ALTER TABLE mentor_messages ADD COLUMN author TEXT"))

# Abgeschlossene Schuljahre verschwinden aus der Übersicht, bleiben aber lesbar.
_MIGRATIONS.append(("exam_archive_001", """
CREATE TABLE IF NOT EXISTS exam_archive (
 account_id INTEGER PRIMARY KEY,
 before_date TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
"""))

# Erinnerungen laufen über die Home-Assistant-App, nicht über Web-Push.
_MIGRATIONS.append(("reminder_app_targets_001", """
CREATE TABLE IF NOT EXISTS reminder_app_targets (
 account_id INTEGER NOT NULL, service TEXT NOT NULL, PRIMARY KEY(account_id,service)
);
CREATE TABLE IF NOT EXISTS reminder_app_deliveries (
 account_id INTEGER NOT NULL, school_day TEXT NOT NULL, service TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(account_id,school_day,service)
);
"""))

# Ein Eintrag ohne erkennbares Thema ist zweierlei: entweder ohne Lerninhalt
# oder inhaltlich, aber zu knapp beschrieben. Nur das Erste ist kein Lernziel.
_MIGRATIONS.append(("discovery_unclear_kind", "ALTER TABLE learning_discovery_items ADD COLUMN unclear_kind TEXT"))

# Ein Feld fasst Teilthemen eines Fachs zusammen, ohne sie zu ersetzen. Geübt
# und nachgewiesen werden weiter die Teile; das Feld ordnet sie nur.
_MIGRATIONS.append(("learning_fields_001", """
CREATE TABLE IF NOT EXISTS learning_fields (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 profile_id INTEGER NOT NULL,
 subject TEXT NOT NULL,
 title TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(profile_id,subject,title)
);
CREATE TABLE IF NOT EXISTS learning_field_runs (
 profile_id INTEGER NOT NULL, subject TEXT NOT NULL, ran_at TEXT NOT NULL,
 PRIMARY KEY(profile_id,subject)
);
"""))
_MIGRATIONS.append(("learning_fields_002", "ALTER TABLE learning_topics ADD COLUMN field_id INTEGER"))
_MIGRATIONS.append(("learning_fields_003", "ALTER TABLE learning_topics ADD COLUMN field_rank INTEGER NOT NULL DEFAULT 0"))

_MIGRATIONS.append(("digital_textbooks_003_pages", """
CREATE TABLE IF NOT EXISTS digital_textbook_pages (
 account_id INTEGER NOT NULL,
 book_id INTEGER NOT NULL,
 page INTEGER NOT NULL,
 image BLOB NOT NULL,
 captured_at TEXT NOT NULL,
 PRIMARY KEY(account_id,book_id,page)
);
CREATE TABLE IF NOT EXISTS digital_textbook_fetches (
 account_id INTEGER PRIMARY KEY,
 book_title TEXT,
 pages TEXT,
 status TEXT NOT NULL,
 stage TEXT,
 detail TEXT,
 delivered INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL
);
"""))

# Die App wusste bisher nur, ob gerade etwas offen ist, nicht ob ein Tag
# abgeschlossen wurde. Ohne diese Angabe trifft die Morgenmitteilung auch den,
# der alles erledigt hat, und die eigene Verlässlichkeit bleibt unzählbar.
_MIGRATIONS.append(("day_close_001", """
CREATE TABLE IF NOT EXISTS day_closures (
 account_id INTEGER NOT NULL, school_day TEXT NOT NULL,
 closed_at TEXT NOT NULL, closed_by TEXT NOT NULL,
 after_reminder INTEGER NOT NULL DEFAULT 0,
 open_homework INTEGER NOT NULL DEFAULT 0,
 open_material INTEGER NOT NULL DEFAULT 0,
 open_feedback INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(account_id,school_day)
);
CREATE TABLE IF NOT EXISTS morning_app_deliveries (
 account_id INTEGER NOT NULL, school_day TEXT NOT NULL, service TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(account_id,school_day,service)
);
"""))

_MIGRATIONS.append(("reminders_morning_at", "ALTER TABLE reminder_settings ADD COLUMN morning_at TEXT"))
_MIGRATIONS.append(("reminders_morning_enabled",
                    "ALTER TABLE reminder_settings ADD COLUMN morning_enabled INTEGER NOT NULL DEFAULT 0"))

# Eine Mitteilung um Viertel vor sieben wird verabredet, nicht ausgerollt. Wer
# schon eine Erinnerungszeit gesetzt hat, bekommt sie erst, wenn er sie
# einschaltet — sonst weckte die Auslieferung selbst das erste Mal.
_MIGRATIONS.append(("reminders_morning_off_until_agreed",
                    "UPDATE reminder_settings SET morning_enabled = 0"))

# Der Quellenbestand: Jede Stelle, die der Unterricht nennt, wird an ihren
# Untis-Eintrag gebunden und mit dem Material verknüpft, das sie belegt.
# Abgerufene Buchseiten sind Materialien wie ein Foto, nur mit Herkunft.
_MIGRATIONS.append(("sources_001", """
CREATE TABLE IF NOT EXISTS source_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL,
 entry_kind TEXT NOT NULL,
 entry_id INTEGER NOT NULL,
 entry_date TEXT NOT NULL,
 subject_name TEXT NOT NULL,
 part_label TEXT NOT NULL,
 part_kind TEXT NOT NULL,
 page INTEGER NOT NULL,
 quote TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending',
 detail TEXT,
 material_id INTEGER,
 book_title TEXT,
 attempts INTEGER NOT NULL DEFAULT 0,
 synced_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(account_id,entry_kind,entry_id,part_kind,part_label,page)
);
CREATE INDEX IF NOT EXISTS idx_source_links_account ON source_links(account_id,subject_name,page);
CREATE TABLE IF NOT EXISTS digital_textbook_access (
 account_id INTEGER NOT NULL,
 book_title TEXT NOT NULL,
 status TEXT NOT NULL,
 page INTEGER,
 printed_page INTEGER,
 detail TEXT,
 checked_at TEXT NOT NULL,
 PRIMARY KEY(account_id,book_title)
);
"""))
_MIGRATIONS.append(("materials_003_origin", "ALTER TABLE materials ADD COLUMN origin TEXT NOT NULL DEFAULT 'upload'"))
_MIGRATIONS.append(("materials_004_source_book", "ALTER TABLE materials ADD COLUMN source_book TEXT"))
_MIGRATIONS.append(("materials_005_source_page", "ALTER TABLE materials ADD COLUMN source_page INTEGER"))
_MIGRATIONS.append(("materials_006_printed_pages", "ALTER TABLE materials ADD COLUMN printed_pages TEXT"))
_MIGRATIONS.append(("materials_007_page_check", "ALTER TABLE materials ADD COLUMN page_check TEXT"))
_MIGRATIONS.append(("materials_008_fits_quote", "ALTER TABLE materials ADD COLUMN fits_quote TEXT"))
_MIGRATIONS.append(("materials_009_source_index",
                    "CREATE INDEX IF NOT EXISTS idx_materials_source ON materials(account_id,source_book,source_page)"))

# Die Struktur eines Buches aus seinem eigenen Inhaltsverzeichnis: Kapitel mit
# Seitenbereich, dazu Vokabel- und Grammatikanhänge, die zu einer Lektion
# gehören. Daraus die Kapitelregel: ein angeschnittenes Kapitel wird ganz
# geholt und gilt als kommender Klausurstoff (D39).
_MIGRATIONS.append(("book_chapters_001", """
CREATE TABLE IF NOT EXISTS book_chapters (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL,
 book_title TEXT NOT NULL,
 number TEXT NOT NULL DEFAULT '',
 title TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'chapter',
 level INTEGER NOT NULL DEFAULT 1,
 start_page INTEGER NOT NULL,
 end_page INTEGER,
 belongs_to TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_book_chapters_book ON book_chapters(account_id,book_title,start_page);
"""))
_MIGRATIONS.append(("textbook_access_toc_state", "ALTER TABLE digital_textbook_access ADD COLUMN toc_state TEXT"))
_MIGRATIONS.append(("textbook_access_toc_pages", "ALTER TABLE digital_textbook_access ADD COLUMN toc_pages TEXT"))
# 15 Euro im Monat für den Quellenbestand, innerhalb des Monatsrahmens: bei
# etwa fünf bis zehn Cent je gelesener Seite reicht das für den Erstlauf eines
# Schuljahresbeginns und danach für die tägliche Differenz.
_MIGRATIONS.append(("ai_config_sources_budget",
                    "ALTER TABLE mentor_ai_config ADD COLUMN sources_micro INTEGER NOT NULL DEFAULT 15000000"))
# Der Hintergrund-Rahmen (Fotos der Kinder, Themenfelder) stand ab Werk bei
# fünf Euro und war im September zu 4,35 Euro verbraucht, bevor das erste Foto
# des jüngeren Kindes gelesen war. Wo niemand den Wert angefasst hat, gelten
# zehn Euro; ein eigener Wert bleibt.
# Ein Foto, das jemand zu einer Stelle der Einkaufsliste macht, gehört zu
# dieser Stelle, auch wenn die Auswertung die Seitenzahl nicht liest.
_MIGRATIONS.append(("source_claims_001", """
CREATE TABLE IF NOT EXISTS source_claims (
 account_id INTEGER NOT NULL,
 subject_key TEXT NOT NULL,
 part_label TEXT NOT NULL,
 page INTEGER NOT NULL,
 material_id INTEGER NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(account_id,subject_key,part_label,page)
);
"""))
# Eine gelesene Buchseite kostet gemessen rund 13 Cent (die wortgetreue
# Abschrift ist der Preis). Für den Altstand eines Schuljahresbeginns, den der
# Nutzer sofort vollständig will, reichen 15 Euro nicht. Wo die Voreinstellung
# steht, gelten 30 Euro; ein eigener Wert bleibt.
_MIGRATIONS.append(("ai_config_sources_thirty",
                    "UPDATE mentor_ai_config SET sources_micro=30000000 WHERE sources_micro=15000000"))
_MIGRATIONS.append(("ai_config_background_ten",
                    "UPDATE mentor_ai_config SET background_micro=10000000 WHERE background_micro=5000000"))

# Stunden ohne Seitenangabe: Welches Kapitel behandelt diesen Stoff? Erst
# eine Regel (die Lektionsnummer im Text), dann das Modell mit dem
# Inhaltsverzeichnis. Eine Hypothese, als solche gekennzeichnet; auch ein
# „kein Kapitel" wird gespeichert, damit nicht jede Nacht neu gefragt wird.
# Die Einstiegshilfe zu einer Hausaufgabe: zwei, drei Sätze, worum es geht
# und womit man anfängt. Im Hintergrund erzeugt, sobald die Quellen da sind.
_MIGRATIONS.append(("tasks_intro_001", "ALTER TABLE tasks ADD COLUMN intro TEXT"))
_MIGRATIONS.append(("tasks_intro_002", "ALTER TABLE tasks ADD COLUMN intro_at TEXT"))

# Ein Foto oder Scan weiß, welche Seite welchen Buchteils es zeigt: aus der
# Einkaufsliste mitgegeben oder von der Auswertung abgelesen. Ohne das steht
# eine von Hand gescannte Seite 19 weiter auf der Liste. Der Buchteil zählt,
# weil Latein zwei Bücher hat (Textband, Begleitband) und Seite 13 in beiden.
_MIGRATIONS.append(("materials_010_source_label", "ALTER TABLE materials ADD COLUMN source_label TEXT"))
# Bücher, die nur auf Papier existieren, bekommen ihr Inhaltsverzeichnis aus
# Fotos; danach gilt für sie dieselbe Kapitelregel wie für digitale Bücher.
_MIGRATIONS.append(("paper_books_001", """
CREATE TABLE IF NOT EXISTS paper_books (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL,
 subject_name TEXT NOT NULL,
 part_label TEXT NOT NULL,
 title TEXT NOT NULL,
 toc_state TEXT,
 toc_pages INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL,
 UNIQUE(account_id,subject_name,part_label)
);
"""))
# Eine nummerierte Lektion ist ein Kapitel, auch wenn sie „Wortschatz" heißt.
# Die Tagesgrenze je Kind: zehn Euro für Üben und Fragen. Hintergrundarbeit
# der App zählt seit 0.58.1 nicht mehr dagegen.
_MIGRATIONS.append(("ai_config_daily_ten",
                    "ALTER TABLE mentor_ai_config ADD COLUMN daily_micro INTEGER NOT NULL DEFAULT 10000000"))
# Ein von Hand berichtigtes Kapitel überlebt jedes neue Lesen des Verzeichnisses.
_MIGRATIONS.append(("book_chapters_locked", "ALTER TABLE book_chapters ADD COLUMN locked INTEGER NOT NULL DEFAULT 0"))
# Das Modell fürs Abschreiben von Quellen und die Hintergrundauswertung; leer
# heißt Hauptmodell. Umgestellt wird nur nach Eichung an echten Seiten.
_MIGRATIONS.append(("ai_config_sources_model", "ALTER TABLE mentor_ai_config ADD COLUMN sources_model TEXT"))
_MIGRATIONS.append(("ai_config_opening_model", "ALTER TABLE mentor_ai_config ADD COLUMN opening_model TEXT"))
# Jedes Foto trägt einen Bildabdruck (Duplikate) und ein Schärfemaß.
_MIGRATIONS.append(("materials_011_phash", "ALTER TABLE materials ADD COLUMN phash TEXT"))
_MIGRATIONS.append(("materials_012_sharpness", "ALTER TABLE materials ADD COLUMN sharpness REAL"))
_MIGRATIONS.append(("book_chapters_numbered_units",
                    "UPDATE book_chapters SET kind='chapter' WHERE level=1 AND number!='' AND kind IN ('vocab','grammar')"))

_MIGRATIONS.append(("entry_chapters_001", """
CREATE TABLE IF NOT EXISTS entry_chapters (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL,
 entry_kind TEXT NOT NULL,
 entry_id INTEGER NOT NULL,
 entry_date TEXT NOT NULL,
 subject_name TEXT NOT NULL,
 book_title TEXT NOT NULL,
 chapter_id INTEGER,
 confidence REAL NOT NULL DEFAULT 0,
 origin TEXT NOT NULL,
 text_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(account_id,entry_kind,entry_id)
);
"""))


class _Conn(sqlite3.Connection):
    """Innerhalb eines ``request_cache.scope()`` schließt ``close()`` nicht,
    sondern legt die Verbindung für den nächsten ``webapp_conn()``/``history_conn()``
    desselben Aufrufs und Threads zurück; am Ende des Aufrufs werden alle
    geschlossen. Nie geteilt: Jede Verbindung hat höchstens einen Nutzer. Mit
    offener Transaktion wird wie bisher geschlossen (und damit zurückgerollt)."""

    pool_key: tuple | None = None

    def close(self) -> None:
        from .request_cache import idle
        free = idle()
        if free is not None and any(c is self for c in free):
            return  # schon zurückgelegt: zweites close()
        if free is not None and self.pool_key and self.pool_key[2] == threading.get_ident() and not self.in_transaction:
            free.append(self)
            return
        super().close()

    def discard(self) -> None:
        super().close()


def _reuse(key: tuple) -> sqlite3.Connection | None:
    from .request_cache import idle
    free = idle()
    for i, conn in enumerate(free or []):
        if conn.pool_key == key:
            del free[i]
            conn.row_factory = sqlite3.Row
            return conn
    return None


def history_conn() -> sqlite3.Connection:
    """Read-only connection to the UNTIS Archive's history.db."""
    key = ("history", str(SETTINGS.history_db_path), threading.get_ident())
    conn = _reuse(key)
    if conn is not None:
        return conn  # die Anwesenheitssicht liegt schon an
    uri = f"file:{SETTINGS.history_db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, isolation_level=None, factory=_Conn)
    conn.row_factory = sqlite3.Row
    from .attendance import install_attendance_view
    install_attendance_view(conn)
    conn.pool_key = key
    return conn


# Wartezeit auf einen anderen Schreiber, in Sekunden. Die Voreinstellung von
# fünf Sekunden reichte nicht: Während einer Sicherung, eines Sammellaufs
# oder einer Auswertung scheiterten Anfragen mit „database is locked".
BUSY_TIMEOUT = 30.0


def webapp_conn() -> sqlite3.Connection:
    """Read-write connection to the add-on's webapp.db."""
    key = ("webapp", str(SETTINGS.webapp_db_path), threading.get_ident())
    conn = _reuse(key)
    if conn is not None:
        return conn
    conn = sqlite3.connect(
        SETTINGS.webapp_db_path, isolation_level=None, timeout=BUSY_TIMEOUT, factory=_Conn
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.pool_key = key
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    """Echte Transaktion auf einer Autocommit-Verbindung.

    ``with conn:`` bündelt bei ``isolation_level=None`` nichts: ``commit()``
    und ``rollback()`` sind dort wirkungslos, jede Anweisung steht sofort.
    Wer mehrere Schreibzugriffe als Einheit braucht, nimmt diesen Block. Läuft
    schon eine Transaktion, schließt er sich ihr an und überlässt ihr das Ende.
    """
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    else:
        if conn.in_transaction:
            conn.execute("COMMIT")


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def split_statements(sql: str) -> list[str]:
    """Ein Skript in einzelne Anweisungen. Getrennt wird nur an einem
    Semikolon, nach dem ``sqlite3.complete_statement`` die Anweisung für
    vollständig hält: Semikolons in Zeichenketten, Kommentaren und
    Trigger-Rümpfen trennen nicht. Reine Kommentare fallen weg."""
    out: list[str] = []
    buf = ""
    for piece in sql.split(";"):
        buf += piece + ";"
        if sqlite3.complete_statement(buf):
            if _lead(buf):
                out.append(buf.strip())
            buf = ""
    if _lead(buf.rstrip(";")):
        out.append(buf.rstrip(";").strip())
    return out


def _lead(stmt: str) -> str:
    """Die Anweisung ohne führende Kommentare, groß geschrieben."""
    s = stmt
    while True:
        s = s.lstrip()
        if s.startswith("--"):
            nl = s.find("\n")
            s = "" if nl < 0 else s[nl + 1:]
        elif s.startswith("/*"):
            end = s.find("*/")
            s = "" if end < 0 else s[end + 2:]
        else:
            break
    s = s.strip().rstrip(";").strip()
    return s.upper()


_TX_CONTROL = ("BEGIN", "COMMIT", "END", "ROLLBACK")
# Diese Anweisungen wirken in einer Transaktion nicht oder scheitern dort
# (PRAGMA foreign_keys ist darin wirkungslos, journal_mode und VACUUM
# verweigern). Eine Migration mit ihnen läuft ohne umschließende Transaktion.
_NO_TX = ("PRAGMA", "VACUUM")


def _skippable(lead: str, exc: sqlite3.OperationalError) -> bool:
    """Nur die eine Anweisung überspringen, deren Ergebnis schon da ist:
    eine vorhandene Spalte bei ALTER TABLE … ADD, ein vorhandenes Objekt bei
    CREATE. Alles andere ist ein echter Fehler."""
    msg = str(exc).lower()
    if lead.startswith("ALTER TABLE") and " ADD" in lead and "duplicate column name" in msg:
        return True
    if lead.startswith("CREATE") and "already exists" in msg:
        return True
    return False


def _run_migration(conn: sqlite3.Connection, sql: str) -> None:
    for stmt in split_statements(sql):
        lead = _lead(stmt)
        if lead.startswith(_TX_CONTROL) and conn.in_transaction:
            continue  # die Migration bringt eigene Klammern mit, es gilt die äußere
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as exc:
            if not _skippable(lead, exc):
                raise


def _sha256_hex(value):
    import hashlib
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Jede noch offene Migration läuft in einer eigenen Transaktion samt
    Marker: Scheitert sie, bleibt nichts halb stehen und sie läuft beim
    nächsten Start neu. SQLite-DDL ist transaktional.

    Bis 1.31 lief jede Migration per executescript ohne Transaktion, und ein
    „duplicate column“ oder „already exists“ brach das Skript an dieser Stelle
    ab, setzte aber den Marker: Der Rest blieb für immer ungelaufen. Jetzt
    wird nur genau die Anweisung übersprungen, deren Ergebnis schon vorhanden
    ist. Bereits markierte Migrationen laufen wie bisher nie wieder."""
    # Für Migrationen, die Werte in Python umrechnen (Sitzungs-Token hashen).
    conn.create_function("sc_sha256", 1, _sha256_hex, deterministic=True)
    applied = {
        r[0]
        for r in conn.execute(
            "SELECT key FROM schema_meta WHERE key LIKE 'migration:%'"
        ).fetchall()
    }
    for key, sql in _MIGRATIONS:
        marker = f"migration:{key}"
        if marker in applied:
            continue
        if any(_lead(s).startswith(_NO_TX) for s in split_statements(sql)):
            _run_migration(conn, sql)
            conn.execute("INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, '1')", (marker,))
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            _run_migration(conn, sql)
            conn.execute("INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, '1')", (marker,))
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

# Der Moment nach dem Unterricht (VERANTWORTUNG.md Stufe 2, D69): eine
# Nachfrage kurz nach der letzten Stunde, Antwort ist Foto oder „nichts Neues“.
_MIGRATIONS.append(("afternoon_check_001", """
ALTER TABLE reminder_settings ADD COLUMN afternoon_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE reminder_settings ADD COLUMN afternoon_delay INTEGER NOT NULL DEFAULT 20;
CREATE TABLE IF NOT EXISTS afternoon_app_deliveries (
 account_id INTEGER NOT NULL, school_day TEXT NOT NULL, service TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(account_id,school_day,service)
);
CREATE TABLE IF NOT EXISTS afternoon_checks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 account_id INTEGER NOT NULL, school_day TEXT NOT NULL,
 answer TEXT NOT NULL,            -- 'photo' | 'nothing'
 material_id INTEGER, task_id INTEGER, user_id INTEGER,
 created_at TEXT NOT NULL, refined_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_afternoon_checks_day ON afternoon_checks(account_id,school_day);
"""))

# Das Ende einer Einheit ist ein Vorschlag, kein Abbruch (D73): merken, bei
# welchem Zug zuletzt vorgeschlagen wurde, damit nicht jede Antwort fragt.
_MIGRATIONS.append(("mentor_end_proposal_001",
                    "ALTER TABLE mentor_sessions ADD COLUMN end_proposed_turn INTEGER NOT NULL DEFAULT 0"))

# Reparatur zu 0.75.1: Materialien, deren leerer Text durch eine Korrektur
# gesperrt wurde, geben Text und Kurzbeschreibung frei und werden neu gelesen.
_MIGRATIONS.append(("materials_013_unlock_empty_text", """
UPDATE materials SET
 locked_fields=(SELECT COALESCE(json_group_array(value),'[]') FROM json_each(materials.locked_fields)
                WHERE value NOT IN ('content_text','summary')),
 analysis_state='pending', updated_at=strftime('%Y-%m-%dT%H:%M:%S','now')
WHERE content_text='' AND analysis_state='ready' AND hidden=0
  AND EXISTS (SELECT 1 FROM json_each(materials.locked_fields) WHERE value='content_text');
"""))

# Seitenart und Handschrift je Material (D77): Handschrift geht immer zum
# Gegenlesen, die Seitenart steuert später die Modellwahl.
_MIGRATIONS.append(("materials_014_page_type", """
ALTER TABLE materials ADD COLUMN page_type TEXT;
ALTER TABLE materials ADD COLUMN handwritten INTEGER NOT NULL DEFAULT 0;
"""))
# Gespräche auf den Geräten der Eltern waren als „Eltern“ markiert; sie gelten
# als Gespräche des Kindes (D82). Nur Demo-Gespräche bleiben Simulation.
_MIGRATIONS.append(("mentor_message_author_002",
                    "UPDATE mentor_messages SET author='kind' WHERE author='eltern' "
                    "AND session_id IN (SELECT id FROM mentor_sessions WHERE is_demo=0)"))
# Rolle einer Verknüpfung (D85): blatt (das Material ist das Arbeitsblatt des
# Eintrags), ergebnis (die Bearbeitung des Kindes dazu), stoff (Thema).
_MIGRATIONS.append(("material_links_002_relation", "ALTER TABLE material_links ADD COLUMN relation TEXT"))

# Der Abschnitt innerhalb einer Einheit, wie ihn die Vokabelliste selbst
# gliedert („Unidad 3 / Texto A"). Die Einheit ist das Standardbündel des
# Trainers, der Abschnitt eine Untergliederung zur Auswahl (D100).
_MIGRATIONS.append(("vocab_words_001_section", "ALTER TABLE vocab_words ADD COLUMN section TEXT NOT NULL DEFAULT ''"))

# Ob das Kind auf einer Seite selbst geschrieben hat, getrennt von der Frage, ob
# Handschrift zu lesen war: Arbeitshefte drucken Musterlösungen in Schreibschrift
# und verlangten dafür bisher ein Gegenlesen (D98).
_MIGRATIONS.append(("materials_016_pupil_entries", "ALTER TABLE materials ADD COLUMN pupil_entries INTEGER NOT NULL DEFAULT 0"))

# Das Anforderungsniveau und die Aufgabenform je Antwort. „Sitzt" verlangt, dass
# auch die schwierigeren Aufgaben richtig bearbeitet wurden (D97); ohne diese
# beiden Angaben ließ sich das aus den Antworten nicht ablesen.
_MIGRATIONS.append(("topic_answers_001_level", """
ALTER TABLE topic_answers ADD COLUMN afb INTEGER;
ALTER TABLE topic_answers ADD COLUMN task_form TEXT;
"""))

# Die Hintergrundauswertung (Unterrichtseinträge zu Themen ordnen) bekommt eine
# eigene Stufe, getrennt vom Abschreiben der Buchseiten (D94). Die Eichung vom
# 17.09. hat sie auf der niedrigen Stufe dreimal in Folge bei 11 von 12
# gleichen Zuordnungen gemessen, während die hohe Stufe gegen sich selbst
# zwischen 10 und 12 schwankte. Deshalb steht sie von Anfang an auf niedrig.
_MIGRATIONS.append(("mentor_ai_config_004_background", """
ALTER TABLE mentor_ai_config ADD COLUMN background_model TEXT;
UPDATE mentor_ai_config SET background_model='niedrig' WHERE id=1 AND background_model IS NULL;
"""))

# Die Vorsortierung der Auswertung für ein loses Blatt: welcher Eintrag am
# ehesten gemeint ist und warum (D85, Stufe 2). Ein Vorschlag, keine Bindung.
_MIGRATIONS.append(("materials_015_sheet_candidate", "ALTER TABLE materials ADD COLUMN sheet_hint TEXT"))

# Der Bestand einer Abfrage, von der App geführt statt vom Modell jede Runde
# neu geschrieben (D91). Vorher stand er im Fließtext von summary und ging
# über ein langes Gespräch verloren.
_MIGRATIONS.append(("mentor_sessions_004_quiz", "ALTER TABLE mentor_sessions ADD COLUMN quiz_json TEXT"))

# Welche Richtwerte ein Aufruf überschritten hat. Seit 0.84.0 sperrt keiner
# mehr, deshalb muss die Überschreitung nachlesbar sein statt als Fehler im
# Gesicht des Kindes zu landen (D89).
_MIGRATIONS.append(("mentor_ai_calls_001_over_budget", "ALTER TABLE mentor_ai_calls ADD COLUMN over_budget TEXT"))

# Die Elternwahl für Einstieg und Abschreiben hielt bisher einen Modellnamen.
# Seit 0.83.0 hält sie eine Stufe, damit ein Modellwechsel in der
# Add-on-Konfiguration die Auswahl nicht entwertet (D88). Namen, die zu keiner
# Stufe passen, werden geleert: Das heißt „wie das Hauptgespräch".
_MIGRATIONS.append(("mentor_ai_config_003_tiers", """
UPDATE mentor_ai_config SET sources_model=CASE
    WHEN sources_model LIKE '%-sol' THEN 'hoch'
    WHEN sources_model LIKE '%-terra' THEN 'mittel'
    WHEN sources_model LIKE '%-luna' THEN 'niedrig'
    WHEN sources_model IN ('hoch','mittel','niedrig') THEN sources_model
    ELSE NULL END,
  opening_model=CASE
    WHEN opening_model LIKE '%-sol' THEN 'hoch'
    WHEN opening_model LIKE '%-terra' THEN 'mittel'
    WHEN opening_model LIKE '%-luna' THEN 'niedrig'
    WHEN opening_model IN ('hoch','mittel','niedrig') THEN opening_model
    ELSE NULL END
WHERE id=1;
"""))


# Fehlversuche beim Lesen eines Inhaltsverzeichnisses. Ein „failed" war bisher
# endgültig: Ein einzelner Modellfehler hat die Kapitelregel für dieses Buch
# dauerhaft abgeschaltet. Spanisch stand deshalb seit Wochen ohne Kapitel da,
# obwohl das Buch eines hat (D101).
_MIGRATIONS.append(("textbook_access_toc_tries",
                    "ALTER TABLE digital_textbook_access ADD COLUMN toc_tries INTEGER NOT NULL DEFAULT 0"))


# Eigene Stufe fürs Lesen der Vokabellisten, getrennt vom übrigen Abschreiben.
# Leer heißt: es gilt die Stufe des Abschreibens (D103).
_MIGRATIONS.append(("ai_config_vocab_model", "ALTER TABLE mentor_ai_config ADD COLUMN vocab_model TEXT"))


# Nach welcher Suche ein „nicht gefunden" entstand. Werden mehr Seiten nach dem
# Inhaltsverzeichnis abgesucht als früher, bekommt das Buch eine zweite Chance:
# „Green Line 4 G9" galt als verzeichnislos, weil nur S. 2 bis 5 angesehen
# wurden (D111).
_MIGRATIONS.append(("textbook_access_toc_version",
                    "ALTER TABLE digital_textbook_access ADD COLUMN toc_version INTEGER NOT NULL DEFAULT 0"))


# Einmalige Reparatur: Seiten, deren Versuche nur deshalb aufgebraucht waren,
# weil eine Sitzung ihr Zeitbudget erreichte, bevor sie an die Reihe kamen. Sie
# wurden nie wieder geholt, standen aber weiter als offen in der Bilanz (D112).
_MIGRATIONS.append(("source_links_reset_attempts_d112",
                    "UPDATE source_links SET attempts=0 WHERE status='pending' AND attempts>0"))


# Einmalige Berichtigung: „TB" wurde überall als Textband gelesen, auch im
# Englischen, wo es Text Book heißt, also das Schulbuch. Nur Latein hat einen
# Textband; in jedem anderen Fach war die Zuordnung falsch (D114).
_NOT_LATIN = ("lower(COALESCE(subject_name,'')) NOT LIKE '%latein%' "
              "AND lower(COALESCE(subject_name,'')) NOT IN ('la','lat')")
_MIGRATIONS.append(("source_links_tb_is_textbook_d114",
                    f"UPDATE source_links SET part_label='Schulbuch' WHERE part_label='Textband' AND {_NOT_LATIN}"))
_MIGRATIONS.append(("materials_tb_is_textbook_d114",
                    f"UPDATE materials SET source_label='Schulbuch' WHERE source_label='Textband' AND {_NOT_LATIN}"))
_MIGRATIONS.append(("source_claims_tb_is_textbook_d114",
                    "UPDATE source_claims SET part_label='Schulbuch' WHERE part_label='Textband' "
                    "AND lower(COALESCE(subject_key,'')) NOT LIKE '%latein%' "
                    "AND lower(COALESCE(subject_key,'')) NOT IN ('la','lat')"))


# Dritte Ebene der Vokabelliste: ein Kasten mit eigener Überschrift innerhalb
# eines Abschnitts („School" in „The new boy"). Steht der Kasten direkt unter
# der Einheit, ist er selbst der Abschnitt (D116).
_MIGRATIONS.append(("vocab_words_002_box", "ALTER TABLE vocab_words ADD COLUMN box TEXT NOT NULL DEFAULT ''"))


# Gegengelesen wird nur noch, wo die Lesung selbst unsicher ist (D118). Die
# Zweifelsstellen stehen als JSON-Liste am Material.
_MIGRATIONS.append(("materials_001_doubts", "ALTER TABLE materials ADD COLUMN doubts TEXT NOT NULL DEFAULT ''"))
# Die bisherigen Bestätigungen der fraglichen Seiten gelten nicht mehr: Sie
# entstanden vor einer Textwand ohne Foto daneben, bei der der Überblick
# verlorenging. Nach dem Neulesen kommt nur zurück, was wirklich unsicher ist;
# Buchabrufe bleiben außen vor, die sind gedruckt und maschinell geholt.
_MIGRATIONS.append(("materials_002_reread_doubtful_d118",
                    "UPDATE materials SET verified=0 WHERE verified=1 AND COALESCE(origin,'')!='book_fetch' "
                    "AND (handwritten=1 OR pupil_entries=1 OR kind IN ('exam_notice','toc'))"))
# Die Überschriften einer Vokabelseite, getrennt von ihren Wörtern gelesen. Aus
# ihnen entsteht die Gliederung des ganzen Buchteils, nicht aus einer Seite (D139).
_MIGRATIONS.append(("vocab_003_headings", """
CREATE TABLE IF NOT EXISTS vocab_headings (
 material_id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, text_hash TEXT NOT NULL,
 heads TEXT NOT NULL DEFAULT '{}', error TEXT, updated_at TEXT NOT NULL
)"""))


_MIGRATIONS.append(("vocab_004_catalog", (Path(__file__).parent / "vocab_catalog_schema.sql").read_text()))
_MIGRATIONS.append(("vocab_005_attempt_scope", "ALTER TABLE vocab_attempts ADD COLUMN unit_scope TEXT;"))
_MIGRATIONS.append(("vocab_006_review", """
CREATE TABLE vocab_attempt_reviews (
 id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL REFERENCES vocab_attempts(id) ON DELETE CASCADE,
 excluded INTEGER NOT NULL, reason TEXT NOT NULL, reviewer_id INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX idx_vocab_attempt_reviews_attempt ON vocab_attempt_reviews(attempt_id,id);
"""))


def init_webapp_db() -> None:
    """Apply base schema + pending migrations (idempotent)."""
    schema_sql = _SCHEMA_FILE.read_text()
    conn = webapp_conn()
    try:
        # WAL: Leser sperren keine Schreiber und umgekehrt. Ohne WAL hielt
        # jeder längere Leser (Schnappschuss, Auswertung) alle Anfragen an,
        # denn jede Anfrage schreibt beim Anmelden „zuletzt gesehen".
        # Die Einstellung bleibt in der Datei erhalten.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(schema_sql)
        _apply_migrations(conn)
    finally:
        conn.close()

_MIGRATIONS.append(("vocab_007_assessment", """
CREATE TABLE vocab_answer_assessments (
 attempt_id INTEGER PRIMARY KEY REFERENCES vocab_attempts(id) ON DELETE CASCADE,
 protocol TEXT NOT NULL,
 decision TEXT NOT NULL,
 evidence_json TEXT NOT NULL
);
"""))

# Wie viel eines Aufrufs aus dem Cache kam und wie viel das Modell nachgedacht
# hat. Bis 1.13.14 wurde beides verworfen; ohne die Zahlen lässt sich nicht
# sagen, ob eine cachefreundliche Reihenfolge wirkt.
_MIGRATIONS.append(("mentor_ai_calls_002_cached", "ALTER TABLE mentor_ai_calls ADD COLUMN cached_tokens INTEGER"))
_MIGRATIONS.append(("mentor_ai_calls_003_reasoning", "ALTER TABLE mentor_ai_calls ADD COLUMN reasoning_tokens INTEGER"))

# Wie lange die App je Tag sichtbar war, getrennt nach Kind und Eltern, mit
# Sekunden je Ansicht. Nur Tagessummen, kein Klickprotokoll; nach 90 Tagen
# gelöscht. Grundlage des Nutzungsberichts für Eltern.
_MIGRATIONS.append(("usage_days_001", """
CREATE TABLE IF NOT EXISTS usage_days (
 account_id INTEGER NOT NULL, day TEXT NOT NULL, actor TEXT NOT NULL,
 first_at TEXT NOT NULL, last_at TEXT NOT NULL,
 opens INTEGER NOT NULL DEFAULT 0, active_seconds INTEGER NOT NULL DEFAULT 0,
 views_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(account_id, day, actor)
);
"""))

# Der Wochenbericht an die Eltern als Mitteilung: Zeit, Elterngeräte und je
# Woche, Kind und Gerät höchstens eine Zustellung (D161).
_MIGRATIONS.append(("parent_report_001", """
CREATE TABLE IF NOT EXISTS parent_report_config (
 id INTEGER PRIMARY KEY CHECK (id=1), weekday INTEGER NOT NULL DEFAULT 6, at TEXT NOT NULL DEFAULT '18:00'
);
CREATE TABLE IF NOT EXISTS parent_report_targets (service TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS parent_report_deliveries (
 week TEXT NOT NULL, account_id INTEGER NOT NULL, service TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(week, account_id, service)
);
"""))

# Wer bei einer Handlung angemeldet war. Der Nutzungsbericht trennt damit das
# eigene Gerät des Kindes vom Elterngerät; ältere Zeilen bleiben ohne Angabe.
_MIGRATIONS.append(("mentor_messages_user_001", "ALTER TABLE mentor_messages ADD COLUMN user_id INTEGER"))
_MIGRATIONS.append(("vocab_attempts_user_001", "ALTER TABLE vocab_attempts ADD COLUMN user_id INTEGER"))

# Serie, Abzeichen und Jahresmedaille (D172, D173). Gezählt wird ab dem ersten
# Aufruf (reward_config.start_day), nie rückwirkend.
_MIGRATIONS.append(("rewards_001", """
CREATE TABLE IF NOT EXISTS reward_config (id INTEGER PRIMARY KEY CHECK (id=1), start_day TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reward_settings (account_id INTEGER PRIMARY KEY, bonus_until TEXT NOT NULL DEFAULT '17:00');
CREATE TABLE IF NOT EXISTS reward_activity (account_id INTEGER NOT NULL, day TEXT NOT NULL, first_at TEXT NOT NULL,
 PRIMARY KEY(account_id, day));
CREATE TABLE IF NOT EXISTS reward_events (account_id INTEGER NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL,
 day TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(account_id, kind, ref));
CREATE TABLE IF NOT EXISTS reward_days (account_id INTEGER NOT NULL, school_day TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('full','rescued')), done_at TEXT NOT NULL, bonus INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(account_id, school_day));
CREATE TABLE IF NOT EXISTS reward_badges (account_id INTEGER NOT NULL, badge TEXT NOT NULL, level INTEGER NOT NULL,
 reached_at TEXT NOT NULL, PRIMARY KEY(account_id, badge, level));
"""))

# Gestaltung je Kind (D176): Farbe, Profilbild, Hell oder Dunkel, Dichte, Freude.
_MIGRATIONS.append(("profile_prefs_001", """
CREATE TABLE IF NOT EXISTS profile_prefs (
 account_id INTEGER PRIMARY KEY, color TEXT, avatar TEXT, theme TEXT, density TEXT, joy TEXT, updated_at TEXT NOT NULL
);
"""))

# Übungsarbeiten zu einer Arbeit (D178): Punkte je Aufgabe, Herkunft und Format
# stehen an der Antwort, damit Papier und Gespräch in dasselbe Raster zählen.
_MIGRATIONS.append(("practice_001", """
ALTER TABLE topic_answers ADD COLUMN points REAL;
ALTER TABLE topic_answers ADD COLUMN max_points REAL;
ALTER TABLE topic_answers ADD COLUMN source TEXT;
ALTER TABLE topic_answers ADD COLUMN paper_format TEXT;
ALTER TABLE topic_answers ADD COLUMN attempt_id INTEGER;
ALTER TABLE mentor_exams ADD COLUMN exam_key TEXT;
ALTER TABLE mentor_exams ADD COLUMN paper_format TEXT;
CREATE INDEX IF NOT EXISTS idx_mentor_exams_key ON mentor_exams(account_id, exam_key);
"""))

# Lern-Pflichtplan (D180): einmal je Tag und Kind berechnet und eingefroren,
# damit ein erledigter Schritt nicht sofort durch den nächsten ersetzt wird.
_MIGRATIONS.append(("study_plan_001", """
CREATE TABLE IF NOT EXISTS study_plan_days (
 account_id INTEGER NOT NULL, day TEXT NOT NULL, steps_json TEXT NOT NULL, computed_at TEXT NOT NULL,
 PRIMARY KEY(account_id, day)
);
"""))

# Vokabeltest auf Papier (D181): gedrucktes Blatt je Einheit, Seiten als Fotos,
# ein KI-Aufruf wertet jedes Wort. Richtig und falsch zählen im Trainer als
# Antwort mit Herkunft „paper“; unklar Gelesenes zählt nicht.
_MIGRATIONS.append(("vocab_paper_001", """
ALTER TABLE vocab_attempts ADD COLUMN source TEXT;
CREATE TABLE IF NOT EXISTS vocab_papers (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, subject TEXT NOT NULL, unit TEXT NOT NULL,
 unit_label TEXT NOT NULL DEFAULT '', section TEXT NOT NULL DEFAULT '', direction TEXT NOT NULL,
 items_json TEXT NOT NULL, user_id INTEGER, counts INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL DEFAULT 'active', result_json TEXT, created_at TEXT NOT NULL, graded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_vocab_papers_account ON vocab_papers(account_id, subject, id);
CREATE TABLE IF NOT EXISTS vocab_paper_pages (
 id INTEGER PRIMARY KEY, paper_id INTEGER NOT NULL REFERENCES vocab_papers(id) ON DELETE CASCADE,
 account_id INTEGER NOT NULL, file_bytes BLOB NOT NULL, created_at TEXT NOT NULL
);
"""))

# Archiv nach der Arbeit (D182): „Wieder aufnehmen“ merkt sich den Tag, damit
# eine ins Archiv gewanderte Einheit zurückkommt.
_MIGRATIONS.append(("learning_archive_001", "ALTER TABLE mentor_sessions ADD COLUMN unarchived_at TEXT"))

# Stand der Planlogik je festgehaltenem Tagesplan (D189).
_MIGRATIONS.append(("study_plan_002_version", "ALTER TABLE study_plan_days ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))

# Art und Hinweise einer Arbeit (D193): Sprechprüfung am Titel erkannt,
# Hinweise der Eltern frei dazu.
_MIGRATIONS.append(("exam_meta_001", """
CREATE TABLE IF NOT EXISTS exam_meta (
 account_id INTEGER NOT NULL, exam_key TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
 oral INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', note_updated_at TEXT,
 updated_at TEXT NOT NULL, PRIMARY KEY(account_id, exam_key)
);
"""))

# Sprechproben (D194): Bewertung je Probe, abgewählte Referenzen je Arbeit.
_MIGRATIONS.append(("oral_sims_001", """
ALTER TABLE exam_meta ADD COLUMN excluded_refs TEXT NOT NULL DEFAULT '[]';
CREATE TABLE IF NOT EXISTS oral_sims (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, exam_key TEXT NOT NULL, topic_id INTEGER, full INTEGER NOT NULL DEFAULT 0,
 session_id INTEGER, created_at TEXT NOT NULL, scores_json TEXT NOT NULL DEFAULT '[]', weak_json TEXT NOT NULL DEFAULT '[]',
 followups_json TEXT NOT NULL DEFAULT '[]', summary TEXT NOT NULL DEFAULT '', level_note TEXT NOT NULL DEFAULT '',
 reliable INTEGER NOT NULL DEFAULT 1, measures_json TEXT NOT NULL DEFAULT '{}', verdict TEXT, verdict_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_oral_sims_exam ON oral_sims(account_id, exam_key, id);
"""))

# Abbildungen aus abgelegten Seiten (D198): einmal je Seite im Hintergrund
# erkannt, mit Lage auf der Seite und Beschreibung.
_MIGRATIONS.append(("material_figures_001", """
CREATE TABLE IF NOT EXISTS material_figures (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
 idx INTEGER NOT NULL DEFAULT 0, kind TEXT NOT NULL, box_json TEXT NOT NULL, caption TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_material_figures_material ON material_figures(material_id);
CREATE TABLE IF NOT EXISTS material_figure_scans (
 material_id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, scanned_at TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, error TEXT
);
"""))

# Material je Arbeit (D199): von Eltern angeheftet.
_MIGRATIONS.append(("exam_meta_002_pinned", "ALTER TABLE exam_meta ADD COLUMN pinned_json TEXT NOT NULL DEFAULT '[]'"))

# „Nicht nötig“ (D196): eine fehlende Stelle, die ein Elternteil gestrichen hat.
# Für ein Blatt ohne Seite (page 0) gilt die Streichung bis `until`.
_MIGRATIONS.append(("source_dismissed_001", """
CREATE TABLE IF NOT EXISTS source_dismissed (
 account_id INTEGER NOT NULL, subject_key TEXT NOT NULL, part_label TEXT NOT NULL, page INTEGER NOT NULL,
 until TEXT NOT NULL DEFAULT '', dismissed_at TEXT NOT NULL, user_id INTEGER,
 PRIMARY KEY(account_id, subject_key, part_label, page)
);
"""))

# Auswertung einer Übungsarbeit angesehen (D201): „Heute“ meldet neue Auswertungen, bis das Kind sie öffnet.
_MIGRATIONS.append(("practice_result_seen_001", "ALTER TABLE mentor_exam_attempts ADD COLUMN result_seen_at TEXT"))

# Große Feier je Abzeichenstufe (D203): einmal gezeigt. Schon erreichte Stufen
# gelten als gefeiert, damit nach dem Update keine Flut an Feiern kommt.
_MIGRATIONS.append(("reward_badges_002_celebrated", """
ALTER TABLE reward_badges ADD COLUMN celebrated_at TEXT;
UPDATE reward_badges SET celebrated_at=reached_at;
"""))

# KI- und Materialpipeline: Wiederholungen mit Zähler statt ohne Ende, eine
# Lesung zugleich je Material. Je Spalte eine eigene Migration, damit eine
# schon vorhandene Spalte die übrigen nicht mitreißt.
_MIGRATIONS.append(("opt_ki_001_figure_attempts",
                    "ALTER TABLE material_figure_scans ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"))
_MIGRATIONS.append(("opt_ki_002_analysis_attempts",
                    "ALTER TABLE materials ADD COLUMN analysis_attempts INTEGER NOT NULL DEFAULT 0"))
_MIGRATIONS.append(("opt_ki_003_analysis_failed_at", "ALTER TABLE materials ADD COLUMN analysis_failed_at TEXT"))
_MIGRATIONS.append(("opt_ki_004_analysis_claimed_at", "ALTER TABLE materials ADD COLUMN analysis_claimed_at TEXT"))
# Bis 1.31.2 sperrte eine Abrechnung über der Reservierung alle KI-Aufrufe bis
# zur Elternbestätigung. Steht die Sperre nur deshalb, wird sie gelöst: Im
# Monat einer echten Anfangsbestätigung kann vor ihr kein Aufruf abgerechnet sein.
_MIGRATIONS.append(("opt_ki_005_overrun_unlock", """
UPDATE mentor_ai_config SET opening_confirmed=1
WHERE opening_confirmed=0 AND EXISTS (
 SELECT 1 FROM mentor_ai_calls c WHERE c.month=mentor_ai_config.opening_month
 AND c.status='settled' AND c.charged_micro>c.reserved_micro);
"""))

# Dedup-Schlüssel der HA-Aufgaben (opt_day): die Beschreibung, wie HA sie
# zuletzt geliefert hat. Nur der Abgleich schreibt sie; `notes` gehört dem
# Nutzer. Vorbelegt mit dem heutigen Text, der erste Abgleich zieht den
# HA-Stand nach. Zwei Schritte, damit die Vorbelegung auch läuft, wenn die
# Spalte schon existiert.
_MIGRATIONS.append(("opt_day_tasks_ha_description", "ALTER TABLE tasks ADD COLUMN ha_description TEXT"))
_MIGRATIONS.append(("opt_day_tasks_ha_description_fill",
                    "UPDATE tasks SET ha_description = notes "
                    "WHERE source = 'ha_todo' AND ha_uid IS NOT NULL AND ha_description IS NULL"))

# Papier-Vokabeltest (opt_day): Beginn der Auswertung. Eine Auswertung, die ein
# Neustart abgebrochen hat, hing sonst für immer auf „grading“.
_MIGRATIONS.append(("opt_day_vocab_papers_grading_started",
                    "ALTER TABLE vocab_papers ADD COLUMN grading_started_at TEXT"))

# Sitzungen nur noch als sha256(token): Eine Sicherung enthält keine
# übernehmbare Anmeldung. Bestehende Zeilen werden an Ort und Stelle
# umgerechnet, damit niemand abgemeldet wird; 64 Zeichen sind schon ein Hash.
_MIGRATIONS.append(("opt_core_001_session_token_hash",
                    "UPDATE sessions SET token = sc_sha256(token) WHERE length(token) != 64"))
# Zeit des letzten PIN-Fehlversuchs: Nach 24 Stunden ohne Fehlversuch beginnt
# die Zählung neu, statt dauerhaft bei der 24-Stunden-Sperre zu bleiben.
_MIGRATIONS.append(("opt_core_002_pin_failed_at", "ALTER TABLE users ADD COLUMN pin_failed_at TEXT"))
