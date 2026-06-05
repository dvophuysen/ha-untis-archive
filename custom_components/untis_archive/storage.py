"""SQLite persistence layer for the UNTIS archive.

One database file per HA instance, all child accounts share it (separated
by ``account_id``). Lives at ``/config/untis_archive/history.db`` so it is
included automatically in HA backups.

All writes happen via the synchronous ``sqlite3`` module wrapped with
``hass.async_add_executor_job`` from the coordinator.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

_LOGGER = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    server TEXT NOT NULL,
    school TEXT NOT NULL,
    username TEXT NOT NULL,
    student_id INTEGER,
    student_type INTEGER,
    created_at TEXT NOT NULL,
    -- Set after the first successful pull cycle. Until then,
    -- late-addition detection is suppressed (the initial backfill
    -- inserts everything in arbitrary order).
    last_pull_completed_at TEXT
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    untis_id INTEGER NOT NULL,
    name TEXT,
    longname TEXT,
    UNIQUE(account_id, untis_id),
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    untis_id INTEGER NOT NULL,
    name TEXT,
    longname TEXT,
    UNIQUE(account_id, untis_id),
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    untis_period_id INTEGER NOT NULL,
    date TEXT NOT NULL,                -- ISO YYYY-MM-DD
    start_time INTEGER NOT NULL,       -- HHMM
    end_time INTEGER NOT NULL,
    subject_untis_id INTEGER,
    subject_name TEXT,
    teacher_untis_id INTEGER,
    teacher_name TEXT,
    room TEXT,
    code TEXT,                         -- '', 'cancelled', 'irregular'
    lstext TEXT,                       -- Lehrstoff body
    subst_text TEXT,
    info TEXT,
    is_supervision_guess INTEGER NOT NULL DEFAULT 0,
    supervision_manual_override INTEGER,
    lstext_manual_override TEXT,
    was_absent INTEGER NOT NULL DEFAULT 0,
    absence_reason TEXT,
    -- Set to 1 when this lesson first appeared AFTER the account had
    -- already pulled past it (i.e. retroactively added to the timetable).
    is_late_addition INTEGER NOT NULL DEFAULT 0,
    -- Substitution detail: orgid/orgname per category if Untis flagged a change.
    subject_orig_untis_id INTEGER,
    subject_orig_name TEXT,
    teacher_orig_untis_id INTEGER,
    teacher_orig_name TEXT,
    room_orig TEXT,
    is_teacher_substituted INTEGER NOT NULL DEFAULT 0,
    is_room_substituted INTEGER NOT NULL DEFAULT 0,
    is_subject_substituted INTEGER NOT NULL DEFAULT 0,
    -- Additional descriptors from the timetable response.
    lsnumber INTEGER,
    student_group TEXT,                -- WebUntis 'sg' field
    activity_type TEXT,
    bk_text TEXT,                      -- 'bkText' (booking text)
    bk_remark TEXT,                    -- 'bkRemark'
    -- When a period has multiple teachers / classes / subjects / rooms,
    -- we keep the first one in the columns above and the full lists here.
    teachers_json TEXT,
    classes_json TEXT,
    subjects_json TEXT,
    rooms_json TEXT,
    -- Full raw timetable entry as returned by WebUntis, for forward-
    -- compatibility (any field we have not modeled is still archived).
    payload_json TEXT,
    -- Full raw /api/public/period/info payload (covers lessonTopic,
    -- periodInfo, exam, attachments, roomSubstitutions, ...).
    period_info_json TEXT,
    first_seen_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    UNIQUE(account_id, untis_period_id),
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_lessons_account_date ON lessons(account_id, date);

CREATE TABLE IF NOT EXISTS lesson_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER NOT NULL,
    captured_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    diff_json TEXT NOT NULL,
    -- Human-readable list of change types (e.g. ["TEACHER_SUBSTITUTED",
    -- "ROOM_CHANGED", "LSTEXT_ADDED"]). Lets downstream queries filter
    -- the event log without reparsing diffs.
    change_types_json TEXT,
    FOREIGN KEY(lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_lesson_snapshots_lesson ON lesson_snapshots(lesson_id, captured_at);

CREATE TABLE IF NOT EXISTS homework (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    untis_homework_id INTEGER NOT NULL,
    untis_lesson_id INTEGER,
    subject_untis_id INTEGER,
    subject_name TEXT,
    text TEXT,
    assigned_date TEXT,
    due_date TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT,
    first_seen_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    UNIQUE(account_id, untis_homework_id),
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS homework_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    homework_id INTEGER NOT NULL,
    captured_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    diff_json TEXT NOT NULL,
    FOREIGN KEY(homework_id) REFERENCES homework(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS absences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    untis_absence_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,           -- ISO YYYY-MM-DD
    end_date TEXT NOT NULL,
    start_time INTEGER NOT NULL,        -- HHMM
    end_time INTEGER NOT NULL,
    reason_id INTEGER,
    reason TEXT,
    text TEXT,
    excuse_status TEXT,
    is_excused INTEGER NOT NULL DEFAULT 0,
    created_user TEXT,
    updated_user TEXT,
    payload_json TEXT,
    first_seen_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    UNIQUE(account_id, untis_absence_id),
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_absences_account_date
    ON absences(account_id, start_date, end_date);
"""


LESSON_TRACKED_FIELDS = (
    "subject_untis_id",
    "subject_name",
    "teacher_untis_id",
    "teacher_name",
    "room",
    "code",
    "lstext",
    "subst_text",
    "info",
    "start_time",
    "end_time",
    "date",
    "subject_orig_untis_id",
    "subject_orig_name",
    "teacher_orig_untis_id",
    "teacher_orig_name",
    "room_orig",
    "is_teacher_substituted",
    "is_room_substituted",
    "is_subject_substituted",
    "lsnumber",
    "student_group",
    "activity_type",
    "bk_text",
    "bk_remark",
    "teachers_json",
    "classes_json",
    "subjects_json",
    "rooms_json",
)
# payload_json and period_info_json are written on every upsert but NOT
# diffed: they are always-on archival fields whose pure presence (or
# JSON key reordering) would otherwise create noisy "OTHER" snapshots.
# Their content is still captured inside the snapshot's payload_json
# (the prior row state) when any semantic field actually changes.

# Fields that we treat as "string, empty == not-set" when diffing, so that
# a None -> "" transition does not show up as a fake change.
_LESSON_TEXTUAL_FIELDS = frozenset(
    {"lstext", "subst_text", "info", "code", "bk_text", "bk_remark"}
)

HOMEWORK_TRACKED_FIELDS = (
    "untis_lesson_id",
    "subject_untis_id",
    "subject_name",
    "text",
    "assigned_date",
    "due_date",
    "completed",
    "payload_json",
)


def _classify_lesson_changes(
    diff: dict[str, tuple[Any, Any]],
    *,
    existing_first_seen: str | None,
    new_date: str,
) -> list[str]:
    """Map a field-level diff into high-level change labels for the log."""
    labels: list[str] = []
    if "code" in diff:
        old_code, new_code = diff["code"]
        if new_code == "cancelled":
            labels.append("CANCELLED")
        elif old_code == "cancelled":
            labels.append("UNCANCELLED")
        elif new_code == "irregular":
            labels.append("IRREGULAR")
    if "teacher_untis_id" in diff or "teacher_name" in diff:
        labels.append("TEACHER_CHANGED")
    if diff.get("is_teacher_substituted", (0, 0))[1]:
        labels.append("TEACHER_SUBSTITUTED")
    if "room" in diff or "room_orig" in diff:
        labels.append("ROOM_CHANGED")
    if diff.get("is_room_substituted", (0, 0))[1]:
        labels.append("ROOM_SUBSTITUTED")
    if "subject_untis_id" in diff or "subject_name" in diff:
        labels.append("SUBJECT_CHANGED")
    if diff.get("is_subject_substituted", (0, 0))[1]:
        labels.append("SUBJECT_SUBSTITUTED")
    if "date" in diff or "start_time" in diff or "end_time" in diff:
        labels.append("RESCHEDULED")
    if "lstext" in diff:
        old, new = diff["lstext"]
        if not (old or "").strip() and (new or "").strip():
            labels.append("LSTEXT_ADDED")
        elif (old or "").strip() and not (new or "").strip():
            labels.append("LSTEXT_REMOVED")
        else:
            labels.append("LSTEXT_CHANGED")
    if "subst_text" in diff:
        labels.append("SUBST_TEXT_CHANGED")
    if "info" in diff:
        labels.append("INFO_CHANGED")
    # If nothing semantic was caught but something did change, mark it
    # generically so the snapshot is still searchable.
    if not labels:
        labels.append("OTHER")
    return labels


@dataclass(slots=True)
class LessonUpsertResult:
    action: str  # "inserted" | "updated" | "unchanged"
    lesson_id: int
    diff: dict[str, tuple[Any, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class UntisStorage:
    """Synchronous SQLite wrapper. Call from executor thread."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._conn = _connect(db_path)
        # executescript runs its own COMMIT, so do schema and migrations
        # outside our BEGIN/COMMIT wrapper.
        self._conn.executescript(SCHEMA)
        # SQLite has no IF NOT EXISTS for ADD COLUMN, so migrate idempotently
        # by checking PRAGMA table_info. Every column added after the
        # initial release goes through this list.
        _MIGRATIONS: dict[str, list[tuple[str, str]]] = {
            "lessons": [
                ("was_absent", "INTEGER NOT NULL DEFAULT 0"),
                ("absence_reason", "TEXT"),
                ("is_late_addition", "INTEGER NOT NULL DEFAULT 0"),
                ("subject_orig_untis_id", "INTEGER"),
                ("subject_orig_name", "TEXT"),
                ("teacher_orig_untis_id", "INTEGER"),
                ("teacher_orig_name", "TEXT"),
                ("room_orig", "TEXT"),
                ("is_teacher_substituted", "INTEGER NOT NULL DEFAULT 0"),
                ("is_room_substituted", "INTEGER NOT NULL DEFAULT 0"),
                ("is_subject_substituted", "INTEGER NOT NULL DEFAULT 0"),
                ("lsnumber", "INTEGER"),
                ("student_group", "TEXT"),
                ("activity_type", "TEXT"),
                ("bk_text", "TEXT"),
                ("bk_remark", "TEXT"),
                ("teachers_json", "TEXT"),
                ("classes_json", "TEXT"),
                ("subjects_json", "TEXT"),
                ("rooms_json", "TEXT"),
                ("payload_json", "TEXT"),
                ("period_info_json", "TEXT"),
            ],
            "lesson_snapshots": [
                ("change_types_json", "TEXT"),
            ],
            "homework": [
                ("payload_json", "TEXT"),
            ],
            "absences": [
                ("payload_json", "TEXT"),
            ],
            "accounts": [
                ("last_pull_completed_at", "TEXT"),
            ],
        }
        for table, cols in _MIGRATIONS.items():
            existing = {
                row["name"]
                for row in self._conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }
            for name, decl in cols:
                if name not in existing:
                    self._conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {decl}"
                    )

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        cur.execute("BEGIN")
        try:
            yield cur
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        finally:
            cur.close()

    # ---- accounts -------------------------------------------------------

    def ensure_account(
        self,
        *,
        entry_id: str,
        name: str,
        server: str,
        school: str,
        username: str,
        student_id: int | None,
        student_type: int | None,
    ) -> int:
        with self._tx() as cur:
            cur.execute(
                "SELECT id FROM accounts WHERE entry_id = ?",
                (entry_id,),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    """UPDATE accounts
                       SET name=?, server=?, school=?, username=?,
                           student_id=?, student_type=?
                       WHERE id=?""",
                    (name, server, school, username, student_id, student_type, row["id"]),
                )
                return int(row["id"])
            cur.execute(
                """INSERT INTO accounts
                   (entry_id, name, server, school, username,
                    student_id, student_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry_id, name, server, school, username, student_id, student_type, _now()),
            )
            return int(cur.lastrowid)

    def mark_pull_complete(self, account_id: int) -> None:
        """Stamp the account as having completed at least one full pull.
        Enables retroactive-change detection for subsequent cycles.
        """
        with self._tx() as cur:
            cur.execute(
                "UPDATE accounts SET last_pull_completed_at=? WHERE id=?",
                (_now(), account_id),
            )

    # ---- lessons --------------------------------------------------------

    # Every normalized lesson column we write on insert / update. Kept in
    # one list so the INSERT, UPDATE and tracked-diff stay in sync.
    _LESSON_WRITE_COLS: tuple[str, ...] = (
        "date",
        "start_time",
        "end_time",
        "subject_untis_id",
        "subject_name",
        "teacher_untis_id",
        "teacher_name",
        "room",
        "code",
        "lstext",
        "subst_text",
        "info",
        "is_supervision_guess",
        "subject_orig_untis_id",
        "subject_orig_name",
        "teacher_orig_untis_id",
        "teacher_orig_name",
        "room_orig",
        "is_teacher_substituted",
        "is_room_substituted",
        "is_subject_substituted",
        "lsnumber",
        "student_group",
        "activity_type",
        "bk_text",
        "bk_remark",
        "teachers_json",
        "classes_json",
        "subjects_json",
        "rooms_json",
        "payload_json",
        "period_info_json",
    )

    def _lesson_value(self, lesson: dict[str, Any], col: str) -> Any:
        """Normalize a write value: textual fields default to empty string,
        booleans to 0/1, the rest pass through as-is.
        """
        v = lesson.get(col)
        if col in _LESSON_TEXTUAL_FIELDS:
            return v or ""
        if col in (
            "is_supervision_guess",
            "is_teacher_substituted",
            "is_room_substituted",
            "is_subject_substituted",
        ):
            return 1 if v else 0
        return v

    def upsert_lesson(self, account_id: int, lesson: dict[str, Any]) -> LessonUpsertResult:
        now = _now()
        with self._tx() as cur:
            cur.execute(
                """SELECT * FROM lessons
                   WHERE account_id=? AND untis_period_id=?""",
                (account_id, lesson["untis_period_id"]),
            )
            existing = cur.fetchone()
            # Only write columns the caller explicitly provided. That way
            # a follow-up pull that only carries period/info (lstext +
            # period_info_json) doesn't blank out fields the original
            # timetable pass had populated.
            cols = tuple(c for c in self._LESSON_WRITE_COLS if c in lesson)
            values = [self._lesson_value(lesson, c) for c in cols]

            if existing is None:
                # Detect retroactive additions: only fires after the
                # account has completed at least one full pull cycle.
                # During the first backfill, lessons arrive in arbitrary
                # order — comparing against MAX(date) would falsely flag
                # the first-inserted row of an old date as 'late'.
                cur.execute(
                    "SELECT last_pull_completed_at FROM accounts WHERE id=?",
                    (account_id,),
                )
                acc = cur.fetchone()
                already_pulled = bool(acc and acc["last_pull_completed_at"])
                is_late = 0
                if already_pulled:
                    cur.execute(
                        """SELECT 1 FROM lessons
                           WHERE account_id=? AND date > ? LIMIT 1""",
                        (account_id, lesson["date"]),
                    )
                    is_late = 1 if cur.fetchone() is not None else 0

                all_cols = ("account_id", "untis_period_id", *cols,
                            "is_late_addition",
                            "first_seen_at", "last_updated_at")
                placeholders = ", ".join(["?"] * len(all_cols))
                cur.execute(
                    f"INSERT INTO lessons ({', '.join(all_cols)}) "
                    f"VALUES ({placeholders})",
                    (account_id, lesson["untis_period_id"], *values,
                     is_late, now, now),
                )
                return LessonUpsertResult("inserted", int(cur.lastrowid), {})

            # Diff into two buckets:
            # - semantic_diff: tracked fields → drives the snapshot/change log
            # - any_diff: ANY provided column that differs → drives the UPDATE
            # That way an archival-only update (e.g. period_info_json finally
            # arriving in pass 2) is persisted without polluting the change
            # log with synthetic entries.
            tracked = set(LESSON_TRACKED_FIELDS)
            semantic_diff: dict[str, tuple[Any, Any]] = {}
            any_diff = False
            for field in cols:
                old = existing[field]
                new = self._lesson_value(lesson, field)
                if old != new:
                    any_diff = True
                    if field in tracked:
                        semantic_diff[field] = (old, new)

            if not any_diff:
                return LessonUpsertResult("unchanged", int(existing["id"]), {})

            if semantic_diff:
                change_types = _classify_lesson_changes(
                    semantic_diff,
                    existing_first_seen=existing["first_seen_at"],
                    new_date=lesson["date"],
                )
                cur.execute(
                    """INSERT INTO lesson_snapshots
                       (lesson_id, captured_at, payload_json, diff_json,
                        change_types_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        int(existing["id"]),
                        now,
                        json.dumps(
                            {k: existing[k] for k in existing.keys()},
                            default=str,
                        ),
                        json.dumps(semantic_diff, default=str),
                        json.dumps(change_types),
                    ),
                )
            set_clause = ", ".join(f"{c}=?" for c in cols)
            cur.execute(
                f"UPDATE lessons SET {set_clause}, last_updated_at=? WHERE id=?",
                (*values, now, int(existing["id"])),
            )
            return LessonUpsertResult("updated", int(existing["id"]), semantic_diff)

    # ---- homework -------------------------------------------------------

    def upsert_homework(self, account_id: int, hw: dict[str, Any]) -> str:
        now = _now()
        with self._tx() as cur:
            cur.execute(
                """SELECT * FROM homework
                   WHERE account_id=? AND untis_homework_id=?""",
                (account_id, hw["untis_homework_id"]),
            )
            existing = cur.fetchone()
            if existing is None:
                cur.execute(
                    """INSERT INTO homework
                       (account_id, untis_homework_id, untis_lesson_id,
                        subject_untis_id, subject_name, text,
                        assigned_date, due_date, completed, payload_json,
                        first_seen_at, last_updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        account_id,
                        hw["untis_homework_id"],
                        hw.get("untis_lesson_id"),
                        hw.get("subject_untis_id"),
                        hw.get("subject_name"),
                        hw.get("text") or "",
                        hw.get("assigned_date"),
                        hw.get("due_date"),
                        1 if hw.get("completed") else 0,
                        hw.get("payload_json"),
                        now,
                        now,
                    ),
                )
                return "inserted"

            diff: dict[str, tuple[Any, Any]] = {}
            for field in HOMEWORK_TRACKED_FIELDS:
                old = existing[field]
                new = hw.get(field)
                if field == "completed":
                    new = 1 if new else 0
                if field == "text":
                    new = new or ""
                if old != new:
                    diff[field] = (old, new)

            if not diff:
                return "unchanged"

            cur.execute(
                """INSERT INTO homework_snapshots
                   (homework_id, captured_at, payload_json, diff_json)
                   VALUES (?, ?, ?, ?)""",
                (
                    int(existing["id"]),
                    now,
                    json.dumps({k: existing[k] for k in existing.keys()}, default=str),
                    json.dumps(diff, default=str),
                ),
            )
            cur.execute(
                """UPDATE homework SET
                       untis_lesson_id=?, subject_untis_id=?, subject_name=?,
                       text=?, assigned_date=?, due_date=?, completed=?,
                       payload_json=?, last_updated_at=?
                   WHERE id=?""",
                (
                    hw.get("untis_lesson_id"),
                    hw.get("subject_untis_id"),
                    hw.get("subject_name"),
                    hw.get("text") or "",
                    hw.get("assigned_date"),
                    hw.get("due_date"),
                    1 if hw.get("completed") else 0,
                    hw.get("payload_json"),
                    now,
                    int(existing["id"]),
                ),
            )
            return "updated"

    # ---- absences -------------------------------------------------------

    def upsert_absence(self, account_id: int, absence: dict[str, Any]) -> str:
        now = _now()
        with self._tx() as cur:
            cur.execute(
                """SELECT id FROM absences
                   WHERE account_id=? AND untis_absence_id=?""",
                (account_id, absence["untis_absence_id"]),
            )
            existing = cur.fetchone()
            if existing is None:
                cur.execute(
                    """INSERT INTO absences
                       (account_id, untis_absence_id, start_date, end_date,
                        start_time, end_time, reason_id, reason, text,
                        excuse_status, is_excused, created_user, updated_user,
                        payload_json, first_seen_at, last_updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        account_id,
                        absence["untis_absence_id"],
                        absence["start_date"],
                        absence["end_date"],
                        absence["start_time"],
                        absence["end_time"],
                        absence.get("reason_id"),
                        absence.get("reason"),
                        absence.get("text"),
                        absence.get("excuse_status"),
                        1 if absence.get("is_excused") else 0,
                        absence.get("created_user"),
                        absence.get("updated_user"),
                        absence.get("payload_json"),
                        now,
                        now,
                    ),
                )
                return "inserted"
            cur.execute(
                """UPDATE absences SET
                       start_date=?, end_date=?, start_time=?, end_time=?,
                       reason_id=?, reason=?, text=?, excuse_status=?,
                       is_excused=?, created_user=?, updated_user=?,
                       payload_json=?, last_updated_at=?
                   WHERE id=?""",
                (
                    absence["start_date"],
                    absence["end_date"],
                    absence["start_time"],
                    absence["end_time"],
                    absence.get("reason_id"),
                    absence.get("reason"),
                    absence.get("text"),
                    absence.get("excuse_status"),
                    1 if absence.get("is_excused") else 0,
                    absence.get("created_user"),
                    absence.get("updated_user"),
                    absence.get("payload_json"),
                    now,
                    int(existing["id"]),
                ),
            )
            return "updated"

    def recompute_attendance(
        self, account_id: int, start_day: str, end_day: str
    ) -> int:
        """Mark every lesson in [start_day, end_day] as absent if it overlaps
        an absence record. Returns the number of lessons flagged absent.

        Overlap rule: lesson.date is within [absence.start_date, end_date]
        and lesson's HHMM interval [start_time, end_time) intersects
        [absence.start_time, absence.end_time).
        """
        with self._tx() as cur:
            # Clear flags in range first so removed absences propagate.
            cur.execute(
                """UPDATE lessons
                   SET was_absent=0, absence_reason=NULL
                   WHERE account_id=? AND date BETWEEN ? AND ?""",
                (account_id, start_day, end_day),
            )
            cur.execute(
                """UPDATE lessons AS l
                   SET was_absent = 1,
                       absence_reason = (
                         SELECT COALESCE(a.reason, '')
                         FROM absences a
                         WHERE a.account_id = l.account_id
                           AND l.date BETWEEN a.start_date AND a.end_date
                           AND l.start_time < a.end_time
                           AND l.end_time   > a.start_time
                         ORDER BY a.start_time
                         LIMIT 1
                       )
                   WHERE l.account_id = ?
                     AND l.date BETWEEN ? AND ?
                     AND EXISTS (
                       SELECT 1 FROM absences a
                       WHERE a.account_id = l.account_id
                         AND l.date BETWEEN a.start_date AND a.end_date
                         AND l.start_time < a.end_time
                         AND l.end_time   > a.start_time
                     )""",
                (account_id, start_day, end_day),
            )
            return cur.rowcount

    # ---- read helpers ---------------------------------------------------

    def lessons_for_day(self, account_id: int, day: str) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """SELECT * FROM lessons
               WHERE account_id=? AND date=?
               ORDER BY start_time""",
            (account_id, day),
        )
        return [dict(row) for row in cur.fetchall()]

    def lessons_between(
        self, account_id: int, start_day: str, end_day: str
    ) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """SELECT * FROM lessons
               WHERE account_id=? AND date BETWEEN ? AND ?
               ORDER BY date, start_time""",
            (account_id, start_day, end_day),
        )
        return [dict(row) for row in cur.fetchall()]

    def open_homework(self, account_id: int) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """SELECT * FROM homework
               WHERE account_id=? AND completed=0
               ORDER BY due_date""",
            (account_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def missed_lessons(
        self, account_id: int, start_day: str, end_day: str
    ) -> list[dict[str, Any]]:
        """Lessons in [start_day, end_day] the kid was actually absent for."""
        cur = self._conn.execute(
            """SELECT * FROM lessons
               WHERE account_id=? AND date BETWEEN ? AND ?
                 AND was_absent=1
                 AND (code IS NULL OR code != 'cancelled')
               ORDER BY date, start_time""",
            (account_id, start_day, end_day),
        )
        return [dict(row) for row in cur.fetchall()]

    def absences_between(
        self, account_id: int, start_day: str, end_day: str
    ) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """SELECT * FROM absences
               WHERE account_id=?
                 AND start_date <= ? AND end_date >= ?
               ORDER BY start_date DESC, start_time DESC""",
            (account_id, end_day, start_day),
        )
        return [dict(row) for row in cur.fetchall()]

    def recent_lesson_changes(
        self, account_id: int, since_iso: str
    ) -> list[dict[str, Any]]:
        """Snapshots captured at-or-after ``since_iso`` for this account,
        joined with the lesson they belong to. Newest first.
        """
        cur = self._conn.execute(
            """SELECT s.captured_at, s.change_types_json, s.diff_json,
                      l.date, l.start_time, l.subject_name, l.teacher_name,
                      l.teacher_orig_name, l.room, l.room_orig, l.code
               FROM lesson_snapshots s
               JOIN lessons l ON l.id = s.lesson_id
               WHERE l.account_id=? AND s.captured_at >= ?
               ORDER BY s.captured_at DESC""",
            (account_id, since_iso),
        )
        return [dict(row) for row in cur.fetchall()]

    def lessons_missing_lstext(
        self, account_id: int, start_day: str, end_day: str
    ) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """SELECT * FROM lessons
               WHERE account_id=? AND date BETWEEN ? AND ?
                 AND (code IS NULL OR code != 'cancelled')
                 AND (lstext IS NULL OR lstext = '')
                 AND (lstext_manual_override IS NULL OR lstext_manual_override = '')
               ORDER BY date, start_time""",
            (account_id, start_day, end_day),
        )
        return [dict(row) for row in cur.fetchall()]

    # ---- manual overrides ----------------------------------------------

    def mark_lesson(
        self,
        lesson_id: int,
        *,
        lstext: str | None = None,
        is_supervision: bool | None = None,
    ) -> None:
        now = _now()
        with self._tx() as cur:
            updates: list[str] = []
            params: list[Any] = []
            if lstext is not None:
                updates.append("lstext_manual_override = ?")
                params.append(lstext)
            if is_supervision is not None:
                updates.append("supervision_manual_override = ?")
                params.append(1 if is_supervision else 0)
            if not updates:
                return
            updates.append("last_updated_at = ?")
            params.append(now)
            params.append(lesson_id)
            cur.execute(
                f"UPDATE lessons SET {', '.join(updates)} WHERE id = ?",
                params,
            )


def parse_untis_date(untis_int: int) -> str:
    """20250605 -> '2025-06-05'."""
    s = str(int(untis_int))
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def to_iso_date(value: Any) -> str | None:
    """Accept WebUntis int date, ISO string, or None."""
    if value is None:
        return None
    if isinstance(value, int):
        return parse_untis_date(value)
    s = str(value)
    if s.isdigit() and len(s) == 8:
        return parse_untis_date(int(s))
    return s


def normalize_period(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a getTimetable entry to the storage dict shape.

    Collapses the first element of each list (``su``/``te``/``kl``/``ro``)
    into scalar columns for fast queries, but ALSO archives:
    - the raw payload as JSON (``payload_json``)
    - the full lists as JSON when they have more than one entry
    - the per-element ``orgid``/``orgname`` Untis attaches when a teacher,
      subject or room is being substituted — that is the only signal Untis
      gives us to detect Vertretungen.
    """
    teachers = list(raw.get("te") or [])
    subjects = list(raw.get("su") or [])
    klassen = list(raw.get("kl") or [])
    rooms = list(raw.get("ro") or [])

    subj = subjects[0] if subjects else {}
    teacher = teachers[0] if teachers else {}
    room = rooms[0] if rooms else {}

    def _orig_id(item: dict[str, Any]) -> int | None:
        v = item.get("orgid")
        return int(v) if isinstance(v, int) and v else None

    def _orig_name(item: dict[str, Any]) -> str | None:
        v = item.get("orgname")
        return v if isinstance(v, str) and v else None

    teacher_orig_id = _orig_id(teacher)
    teacher_orig_name = _orig_name(teacher)
    subject_orig_id = _orig_id(subj)
    subject_orig_name = _orig_name(subj)
    room_orig = _orig_name(room) or (
        room.get("orgname") if isinstance(room, dict) else None
    )

    code = raw.get("code") or ""
    lstext_raw = (raw.get("lstext") or "").strip()
    is_supervision_guess = bool(code == "irregular" and not lstext_raw)

    out: dict[str, Any] = {
        "untis_period_id": int(raw["id"]),
        "date": parse_untis_date(raw["date"]),
        "start_time": int(raw["startTime"]),
        "end_time": int(raw["endTime"]),
        "subject_untis_id": subj.get("id"),
        "subject_name": subj.get("longname") or subj.get("name"),
        "teacher_untis_id": teacher.get("id"),
        "teacher_name": teacher.get("longname") or teacher.get("name"),
        "room": room.get("name") or room.get("longname"),
        "code": code,
        "subst_text": (raw.get("substText") or "").strip(),
        "info": (raw.get("info") or "").strip(),
        "is_supervision_guess": is_supervision_guess,
        # Substitution detail
        "subject_orig_untis_id": subject_orig_id,
        "subject_orig_name": subject_orig_name,
        "teacher_orig_untis_id": teacher_orig_id,
        "teacher_orig_name": teacher_orig_name,
        "room_orig": room_orig,
        "is_teacher_substituted": bool(teacher_orig_id or teacher_orig_name),
        "is_room_substituted": bool(room_orig),
        "is_subject_substituted": bool(subject_orig_id or subject_orig_name),
        # Misc descriptors
        "lsnumber": raw.get("lsnumber"),
        "student_group": raw.get("sg"),
        "activity_type": raw.get("activityType"),
        "bk_text": (raw.get("bkText") or "").strip() or None,
        "bk_remark": (raw.get("bkRemark") or "").strip() or None,
        # Full lists archived as JSON when there is more than one entry;
        # for single-element periods we keep these null to avoid noise.
        "teachers_json": json.dumps(teachers, ensure_ascii=False) if len(teachers) > 1 else None,
        "classes_json": json.dumps(klassen, ensure_ascii=False) if len(klassen) > 1 else None,
        "subjects_json": json.dumps(subjects, ensure_ascii=False) if len(subjects) > 1 else None,
        "rooms_json": json.dumps(rooms, ensure_ascii=False) if len(rooms) > 1 else None,
        # Raw archival — covers any field we have not modeled.
        "payload_json": json.dumps(raw, ensure_ascii=False, default=str),
    }
    # Only carry lstext through when the timetable response actually
    # provided one. Most WebUntis instances (incl. GaW) leave it empty
    # here and only fill it via /api/public/period/info, which the
    # coordinator hits in a second pass.
    if lstext_raw:
        out["lstext"] = lstext_raw
    return out


def normalize_homework(raw: dict[str, Any], lessons_lookup: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Map a /api/homeworks/lessons entry to the storage dict shape.

    ``raw`` is a single homework dict; ``lessons_lookup`` is the
    ``lessons`` dict from the same response keyed by ``lessonId`` so we
    can resolve subject information.
    """
    lesson_info = lessons_lookup.get(int(raw.get("lessonId", 0))) or {}
    subj = (lesson_info.get("subject") or {}) if isinstance(lesson_info, dict) else {}
    return {
        "untis_homework_id": int(raw["id"]),
        "untis_lesson_id": raw.get("lessonId"),
        "subject_untis_id": subj.get("id") if isinstance(subj, dict) else None,
        "subject_name": subj.get("name") if isinstance(subj, dict) else None,
        "text": (raw.get("text") or "").strip(),
        "assigned_date": to_iso_date(raw.get("date")),
        "due_date": to_iso_date(raw.get("dueDate")),
        "completed": bool(raw.get("completed")),
        "payload_json": json.dumps(raw, ensure_ascii=False, default=str),
    }


def normalize_absence(raw: dict[str, Any]) -> dict[str, Any]:
    """Map an /api/classreg/absences/students entry to the storage shape."""
    excuse = raw.get("excuse") or {}
    excuse_status = ""
    is_excused = False
    if isinstance(excuse, dict):
        excuse_status = (
            excuse.get("excuseStatusName")
            or excuse.get("statusName")
            or excuse.get("status")
            or ""
        )
        # When excuseStatus has any non-empty payload, Untis treats the
        # absence as excused. Real records observed: empty dict {} = open,
        # populated dict = excused.
        is_excused = bool(excuse)
    return {
        "untis_absence_id": int(raw["id"]),
        "start_date": parse_untis_date(raw["startDate"]),
        "end_date": parse_untis_date(raw["endDate"]),
        "start_time": int(raw["startTime"]),
        "end_time": int(raw["endTime"]),
        "reason_id": raw.get("reasonId"),
        "reason": (raw.get("reason") or "").strip() or None,
        "text": (raw.get("text") or "").strip() or None,
        "excuse_status": excuse_status or None,
        "is_excused": is_excused,
        "created_user": raw.get("createdUser"),
        "updated_user": raw.get("updatedUser"),
        "payload_json": json.dumps(raw, ensure_ascii=False, default=str),
    }


def collect_absences(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield normalized absence dicts from the raw REST payload."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if data is None:
        data = payload if isinstance(payload, dict) else {}
    for entry in data.get("absences") or []:
        if isinstance(entry, dict) and "id" in entry:
            yield normalize_absence(entry)


def collect_homework(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield normalized homework dicts from the raw REST payload.

    The endpoint returns ``{"data": {"homeworks": [...], "lessons": [...]}}``
    (shape observed in real installs). Be defensive about the wrapper.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if data is None:
        data = payload if isinstance(payload, dict) else {}
    raw_hws = data.get("homeworks") or []
    raw_lessons = data.get("lessons") or []
    lessons_lookup: dict[int, dict[str, Any]] = {}
    for ls in raw_lessons:
        if isinstance(ls, dict) and "id" in ls:
            lessons_lookup[int(ls["id"])] = ls
    for hw in raw_hws:
        if isinstance(hw, dict) and "id" in hw:
            yield normalize_homework(hw, lessons_lookup)
