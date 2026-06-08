from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, get_current_user, linked_account_ids
from ..db import history_conn, webapp_conn

router = APIRouter()


@router.get("/me")
def get_me(user: CurrentUser = Depends(get_current_user)) -> dict:
    account_ids = sorted(linked_account_ids(user.id))
    accounts: list[dict] = []
    if account_ids:
        conn = history_conn()
        try:
            placeholder = ",".join("?" for _ in account_ids)
            rows = conn.execute(
                f"SELECT id, name FROM accounts WHERE id IN ({placeholder}) "
                "ORDER BY name",
                account_ids,
            ).fetchall()
            accounts = [{"id": r["id"], "name": r["name"]} for r in rows]
        finally:
            conn.close()

    setup_needed = False
    if user.is_admin:
        conn = webapp_conn()
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'pending'"
            ).fetchone()[0]
            linked = conn.execute(
                "SELECT COUNT(*) FROM user_account_links"
            ).fetchone()[0]
            setup_needed = pending > 0 or linked == 0
        finally:
            conn.close()

    return {
        "id": user.id,
        "ha_user_id": user.ha_user_id,
        "display_name": user.display_name,
        "role": user.role,
        "is_admin": user.is_admin,
        "accounts": accounts,
        "setup_needed": setup_needed,
    }
