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
    demo_mode = False
    open_audit_count = 0
    conn = webapp_conn()
    try:
        demo_row = conn.execute(
            "SELECT demo_mode FROM users WHERE id = ?", (user.id,)
        ).fetchone()
        demo_mode = bool(demo_row and demo_row["demo_mode"])
        open_audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE user_id = ? AND reverted_at IS NULL",
            (user.id,),
        ).fetchone()[0]
        if user.is_admin:
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
        "demo_mode": demo_mode,
        "open_audit_count": open_audit_count,
    }
