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
    created_at TEXT NOT NULL
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
    FOREIGN KEY(lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
);

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
)

HOMEWORK_TRACKED_FIELDS = (
    "untis_lesson_id",
    "subject_untis_id",
    "subject_name",
    "text",
    "assigned_date",
    "due_date",
    "completed",
)


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
        with self._tx() as cur:
            cur.executescript(SCHEMA)

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

    # ---- lessons --------------------------------------------------------

    def upsert_lesson(self, account_id: int, lesson: dict[str, Any]) -> LessonUpsertResult:
        now = _now()
        with self._tx() as cur:
            cur.execute(
                """SELECT * FROM lessons
                   WHERE account_id=? AND untis_period_id=?""",
                (account_id, lesson["untis_period_id"]),
            )
            existing = cur.fetchone()
            if existing is None:
                cur.execute(
                    """INSERT INTO lessons
                       (account_id, untis_period_id, date, start_time, end_time,
                        subject_untis_id, subject_name, teacher_untis_id, teacher_name,
                        room, code, lstext, subst_text, info, is_supervision_guess,
                        first_seen_at, last_updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        account_id,
                        lesson["untis_period_id"],
                        lesson["date"],
                        lesson["start_time"],
                        lesson["end_time"],
                        lesson.get("subject_untis_id"),
                        lesson.get("subject_name"),
                        lesson.get("teacher_untis_id"),
                        lesson.get("teacher_name"),
                        lesson.get("room"),
                        lesson.get("code") or "",
                        lesson.get("lstext") or "",
                        lesson.get("subst_text") or "",
                        lesson.get("info") or "",
                        1 if lesson.get("is_supervision_guess") else 0,
                        now,
                        now,
                    ),
                )
                return LessonUpsertResult("inserted", int(cur.lastrowid), {})

            diff: dict[str, tuple[Any, Any]] = {}
            for field in LESSON_TRACKED_FIELDS:
                old = existing[field]
                new = lesson.get(field) if field not in ("date", "start_time", "end_time") else lesson[field]
                if field in ("lstext", "subst_text", "info", "code"):
                    new = new or ""
                if old != new:
                    diff[field] = (old, new)

            if not diff:
                return LessonUpsertResult("unchanged", int(existing["id"]), {})

            cur.execute(
                """INSERT INTO lesson_snapshots
                   (lesson_id, captured_at, payload_json, diff_json)
                   VALUES (?, ?, ?, ?)""",
                (
                    int(existing["id"]),
                    now,
                    json.dumps({k: existing[k] for k in existing.keys()}, default=str),
                    json.dumps(diff, default=str),
                ),
            )
            cur.execute(
                """UPDATE lessons SET
                       date=?, start_time=?, end_time=?,
                       subject_untis_id=?, subject_name=?,
                       teacher_untis_id=?, teacher_name=?,
                       room=?, code=?, lstext=?, subst_text=?, info=?,
                       is_supervision_guess=?, last_updated_at=?
                   WHERE id=?""",
                (
                    lesson["date"],
                    lesson["start_time"],
                    lesson["end_time"],
                    lesson.get("subject_untis_id"),
                    lesson.get("subject_name"),
                    lesson.get("teacher_untis_id"),
                    lesson.get("teacher_name"),
                    lesson.get("room"),
                    lesson.get("code") or "",
                    lesson.get("lstext") or "",
                    lesson.get("subst_text") or "",
                    lesson.get("info") or "",
                    1 if lesson.get("is_supervision_guess") else 0,
                    now,
                    int(existing["id"]),
                ),
            )
            return LessonUpsertResult("updated", int(existing["id"]), diff)

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
                        assigned_date, due_date, completed,
                        first_seen_at, last_updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                       last_updated_at=?
                   WHERE id=?""",
                (
                    hw.get("untis_lesson_id"),
                    hw.get("subject_untis_id"),
                    hw.get("subject_name"),
                    hw.get("text") or "",
                    hw.get("assigned_date"),
                    hw.get("due_date"),
                    1 if hw.get("completed") else 0,
                    now,
                    int(existing["id"]),
                ),
            )
            return "updated"

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

    WebUntis extended timetable entries have lists for ``su`` (subjects),
    ``te`` (teachers), ``kl`` (klassen), ``ro`` (rooms). We collapse each
    to its first element for storage.
    """
    def first(name: str) -> dict[str, Any] | None:
        items = raw.get(name) or []
        return items[0] if items else None

    subj = first("su") or {}
    teacher = first("te") or {}
    room = first("ro") or {}

    code = raw.get("code") or ""
    lstext = (raw.get("lstext") or "").strip()
    is_supervision_guess = bool(code == "irregular" and not lstext)

    return {
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
        "lstext": lstext,
        "subst_text": (raw.get("substText") or "").strip(),
        "info": (raw.get("info") or "").strip(),
        "is_supervision_guess": is_supervision_guess,
    }


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
    }


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
