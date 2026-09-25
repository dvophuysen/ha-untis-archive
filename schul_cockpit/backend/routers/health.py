"""Erreichbarkeit des Backends.

Ohne Anmeldung nur, ob es läuft und die history.db lesbar ist. Bis 1.31
standen hier für jeden, der den Direktport erreicht, die Namen der Kinder,
ihre Konto-IDs, die Datenbankpfade und Fehlertexte. Die Details sieht nur
ein Admin (Ingress oder PIN-Anmeldung)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..auth import get_current_user
from ..config import SETTINGS
from ..db import history_conn

router = APIRouter()


def _is_admin(request: Request) -> bool:
    try:
        return get_current_user(request).is_admin
    except HTTPException:
        return False
    except Exception:
        return False  # die Prüfung darf nie am Anmeldeweg scheitern


@router.get("/health")
def health(request: Request) -> dict:
    info: dict = {"ok": True}
    accounts: list[dict] | None = None
    error: str | None = None
    try:
        conn = history_conn()
        try:
            accounts = [{"id": r["id"], "name": r["name"]}
                        for r in conn.execute("SELECT id, name FROM accounts ORDER BY id").fetchall()]
        finally:
            conn.close()
        info["history_db_accessible"] = True
    except Exception as exc:
        info["history_db_accessible"] = False
        error = str(exc)
    if not _is_admin(request):
        return info
    info.update({
        "history_db": str(SETTINGS.history_db_path),
        "webapp_db": str(SETTINGS.webapp_db_path),
        "supervisor_token_present": bool(SETTINGS.supervisor_token),
    })
    if accounts is not None:
        info["accounts"] = accounts
    if error is not None:
        info["history_db_error"] = error
    return info
