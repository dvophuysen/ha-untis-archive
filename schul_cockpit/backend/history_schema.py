"""Schema contract: what the app expects from `history.db`.

If the UNTIS Archive integration installed in HA is older than the app
expects, the app refuses to start with a clear message so the user can
update the integration.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class TableSpec:
    name: str
    required_columns: frozenset[str]


# Only the tables/columns the app actually reads. Keep this list minimal so
# adding fields to the integration doesn't accidentally tighten the contract.
REQUIRED_TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        "accounts",
        frozenset({"id", "name", "school", "username"}),
    ),
    TableSpec(
        "lessons",
        frozenset({
            "id",
            "account_id",
            "untis_period_id",
            "date",
            "start_time",
            "end_time",
            "subject_untis_id",
            "subject_name",
            "teacher_name",
            "room",
            "code",
            "lstext",
            "subst_text",
            "info",
            "was_absent",
            "absence_reason",
            "is_late_addition",
            "teacher_orig_name",
            "room_orig",
            "subject_orig_name",
            "is_teacher_substituted",
            "is_room_substituted",
            "is_subject_substituted",
            "period_info_json",
        }),
    ),
    TableSpec(
        "homework",
        frozenset({
            "id",
            "account_id",
            "subject_untis_id",
            "subject_name",
            "text",
            "assigned_date",
            "due_date",
            "completed",
        }),
    ),
    TableSpec(
        "absences",
        frozenset({
            "id",
            "account_id",
            "start_date",
            "end_date",
            "reason",
            "is_excused",
        }),
    ),
)


class SchemaMismatch(RuntimeError):
    """Raised when history.db is missing tables or columns the app needs."""


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def assert_compatible(history_db_path: str) -> None:
    """Validate the contract. Raises SchemaMismatch on incompatibility."""
    uri = f"file:{history_db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as exc:
        raise SchemaMismatch(
            f"Konnte history.db nicht öffnen ({history_db_path}). "
            "Ist die UNTIS-Archive-Integration installiert und hat schon einmal gepollt? "
            f"Originalfehler: {exc}"
        ) from exc

    try:
        missing: list[str] = []
        for spec in REQUIRED_TABLES:
            if not _table_exists(conn, spec.name):
                missing.append(f"Tabelle '{spec.name}' fehlt")
                continue
            cols = _table_columns(conn, spec.name)
            missing_cols = spec.required_columns - cols
            if missing_cols:
                missing.append(
                    f"Tabelle '{spec.name}' fehlen Spalten: {sorted(missing_cols)}"
                )
        if missing:
            raise SchemaMismatch(
                "history.db ist nicht kompatibel mit dieser Add-on-Version. "
                "Bitte UNTIS-Archive-Integration aktualisieren. Details: "
                + "; ".join(missing)
            )
    finally:
        conn.close()
