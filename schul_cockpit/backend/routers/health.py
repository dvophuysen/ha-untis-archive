from __future__ import annotations

from fastapi import APIRouter

from ..config import SETTINGS
from ..db import history_conn

router = APIRouter()


@router.get("/health")
def health() -> dict:
    info: dict = {
        "ok": True,
        "history_db": str(SETTINGS.history_db_path),
        "webapp_db": str(SETTINGS.webapp_db_path),
        "supervisor_token_present": bool(SETTINGS.supervisor_token),
    }
    try:
        conn = history_conn()
        try:
            accounts = conn.execute(
                "SELECT id, name FROM accounts ORDER BY id"
            ).fetchall()
            info["history_db_accessible"] = True
            info["accounts"] = [{"id": r["id"], "name": r["name"]} for r in accounts]
        finally:
            conn.close()
    except Exception as exc:
        info["history_db_accessible"] = False
        info["history_db_error"] = str(exc)
    return info
