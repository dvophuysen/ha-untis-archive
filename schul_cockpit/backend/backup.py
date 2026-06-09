"""Backup / restore of the add-on's webapp.db (admin only).

The DB runs in WAL mode, so a naive file copy can be inconsistent. We use
SQLite's online backup API after a FULL checkpoint to produce a coherent
single-file snapshot. Restore validates the uploaded file's schema before
replacing the live DB, and keeps the previous DB as a .bak so the
operation is reversible.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path

from .config import SETTINGS
from .db import webapp_conn

# Tables we expect in a valid webapp.db (subset is enough to reject a
# foreign file; we don't pin exact columns so older/newer backups still
# restore and then get migrated forward on next start).
EXPECTED_WEBAPP_TABLES = {
    "schema_meta",
    "users",
    "user_account_links",
    "tasks",
    "lesson_checkins",
    "caught_up",
    "account_settings",
}

_KEEP_BAKS = 3


def _count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def status() -> dict:
    db_path = SETTINGS.webapp_db_path
    size = db_path.stat().st_size if db_path.exists() else 0
    conn = webapp_conn()
    try:
        counts = {
            "tasks": _count(conn, "tasks"),
            "checkins": _count(conn, "lesson_checkins"),
            "caught_up": _count(conn, "caught_up"),
            "manual_exams": _count(conn, "manual_exams"),
            "exam_progress": _count(conn, "exam_progress"),
            "users": _count(conn, "users"),
            "hidden_courses": _count(conn, "hidden_courses"),
        }
    finally:
        conn.close()
    return {"db_size_bytes": size, "counts": counts}


def _snapshot_db(conn: sqlite3.Connection) -> Path:
    fd, tmp = tempfile.mkstemp(prefix="sc-snap-", suffix=".db")
    os.close(fd)
    dest = sqlite3.connect(tmp)
    try:
        conn.backup(dest)  # online backup API → coherent snapshot
    finally:
        dest.close()
    return Path(tmp)


def make_snapshot() -> Path:
    """Consistent copy of webapp.db (caller deletes)."""
    src = webapp_conn()
    try:
        src.execute("PRAGMA wal_checkpoint(FULL)")
        return _snapshot_db(src)
    finally:
        src.close()


def _snapshot_history() -> Path | None:
    """Consistent read-only copy of history.db (the UNTIS archive), if it
    exists. The integration owns it live; the online backup API copies it
    coherently without locking writers out."""
    hp = SETTINGS.history_db_path
    if not hp.exists():
        return None
    conn = sqlite3.connect(f"file:{hp}?mode=ro", uri=True)
    try:
        return _snapshot_db(conn)
    finally:
        conn.close()


def make_combined_zip() -> Path:
    """One archive holding BOTH databases + a manifest. They are
    interdependent (webapp.db references history.db ids), so we capture
    them together at one point in time."""
    web = make_snapshot()
    hist = _snapshot_history()
    st = status()
    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "contains": ["webapp.db"] + (["history.db"] if hist else []),
        "webapp_counts": st["counts"],
        "note": (
            "Restore: webapp.db kann das Add-on direkt zurückspielen. "
            "history.db bitte über HA-Backup-Restore wiederherstellen "
            "(die UNTIS-Integration hält sie im Betrieb geöffnet)."
        ),
    }
    fd, zpath = tempfile.mkstemp(prefix="sc-backup-", suffix=".zip")
    os.close(fd)
    try:
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(web, "webapp.db")
            if hist:
                zf.write(hist, "history.db")
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    finally:
        web.unlink(missing_ok=True)
        if hist:
            hist.unlink(missing_ok=True)
    return Path(zpath)


def validate_db_file(path: Path) -> tuple[bool, str]:
    """Check the uploaded file is a SQLite DB with our expected tables."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return False, f"Keine gültige Datenbank: {exc}"
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        tables = {r[0] for r in rows}
    except sqlite3.DatabaseError as exc:
        return False, f"Datei ist keine SQLite-Datenbank: {exc}"
    finally:
        conn.close()
    missing = EXPECTED_WEBAPP_TABLES - tables
    if missing:
        return False, f"Backup passt nicht (fehlende Tabellen: {sorted(missing)})"
    return True, "ok"


def _extract_webapp_db(uploaded: Path) -> Path:
    """Accept either a combined .zip (use its webapp.db) or a raw .db."""
    if zipfile.is_zipfile(uploaded):
        with zipfile.ZipFile(uploaded) as zf:
            names = zf.namelist()
            if "webapp.db" not in names:
                raise ValueError("ZIP enthält keine webapp.db")
            fd, tmp = tempfile.mkstemp(prefix="sc-restore-web-", suffix=".db")
            os.close(fd)
            with zf.open("webapp.db") as src, open(tmp, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            return Path(tmp)
    return uploaded


def restore_from_file(uploaded: Path) -> dict:
    """Replace the live webapp.db from the uploaded file (raw .db or the
    webapp.db inside a combined .zip). Keeps a .bak of the old one. history.db
    is NOT restored here (config is read-only + the integration owns it live)."""
    webapp_src = _extract_webapp_db(uploaded)
    had_history = zipfile.is_zipfile(uploaded) and "history.db" in zipfile.ZipFile(uploaded).namelist()

    ok, msg = validate_db_file(webapp_src)
    if not ok:
        raise ValueError(msg)

    db_path = SETTINGS.webapp_db_path
    data_dir = db_path.parent
    ts = time.strftime("%Y%m%d-%H%M%S")

    # Checkpoint + close any WAL side files so the swap is clean.
    try:
        c = sqlite3.connect(db_path)
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        c.close()
    except sqlite3.Error:
        pass

    bak = data_dir / f"webapp.db.bak-{ts}"
    if db_path.exists():
        os.replace(db_path, bak)
    # Remove stale WAL/SHM of the old DB if present.
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            try:
                side.unlink()
            except OSError:
                pass

    # Move the validated webapp.db into place.
    os.replace(webapp_src, db_path)

    _prune_baks(data_dir)
    return {
        "backup_kept_as": bak.name,
        "history_db_in_archive": had_history,
        "history_restore_hint": (
            "Das Archiv enthielt auch history.db. Diese wird hier NICHT "
            "wiederhergestellt — bitte über ein HA-Backup-Restore einspielen."
            if had_history else None
        ),
    }


def _prune_baks(data_dir: Path) -> None:
    baks = sorted(data_dir.glob("webapp.db.bak-*"), reverse=True)
    for old in baks[_KEEP_BAKS:]:
        try:
            old.unlink()
        except OSError:
            pass
