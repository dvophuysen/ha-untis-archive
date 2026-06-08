from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..audit import is_demo, log as audit_log, snapshot_task
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..sync_worker import sync_account

router = APIRouter()

VALID_TYPES = {"homework", "exam_prep", "catch_up", "practice", "project"}
VALID_STATUS = {"open", "in_progress", "done", "skipped"}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    task_type: str = "homework"
    estimated_minutes: int | None = Field(default=None, ge=0)
    due_date: str | None = None
    due_time: str | None = None
    subject_untis_id: int | None = None
    subject_name: str | None = None
    lesson_id: int | None = None
    notes: str | None = None
    subitems: list[str] | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    task_type: str | None = None
    status: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=0)
    due_date: str | None = None
    due_time: str | None = None
    subject_untis_id: int | None = None
    subject_name: str | None = None
    notes: str | None = None


class SubitemIn(BaseModel):
    title: str = Field(min_length=1)


class SubitemPatch(BaseModel):
    title: str | None = None
    done: bool | None = None
    position: int | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_task(row) -> dict:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "ha_uid": row["ha_uid"],
        "title": row["title"],
        "subject_untis_id": row["subject_untis_id"],
        "subject_name": row["subject_name"],
        "task_type": row["task_type"],
        "status": row["status"],
        "estimated_minutes": row["estimated_minutes"],
        "due_date": row["due_date"],
        "due_time": row["due_time"],
        "lesson_id": row["lesson_id"],
        "notes": row["notes"],
        "source": row["source"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    }


@router.get("/accounts/{account_id}/tasks")
def list_tasks(
    account_id: int,
    status: str | None = Query(default=None),
    only_open: bool = Query(default=False),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    if status and status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="invalid status")
    sql = "SELECT * FROM tasks WHERE account_id = ?"
    params: list = [account_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    elif only_open:
        sql += " AND status IN ('open', 'in_progress')"
    sql += " ORDER BY (due_date IS NULL), due_date, due_time, id"
    conn = webapp_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        tasks = [_row_to_task(r) for r in rows]
        ids = [t["id"] for t in tasks]
        sub_map: dict[int, list[dict]] = {}
        if ids:
            placeholder = ",".join("?" for _ in ids)
            for r in conn.execute(
                f"SELECT id, task_id, title, done, position FROM task_subitems "
                f"WHERE task_id IN ({placeholder}) ORDER BY position, id",
                ids,
            ).fetchall():
                sub_map.setdefault(r["task_id"], []).append(
                    {"id": r["id"], "title": r["title"], "done": bool(r["done"]), "position": r["position"]}
                )
        for t in tasks:
            t["subitems"] = sub_map.get(t["id"], [])
    finally:
        conn.close()
    return {"tasks": tasks}


@router.post("/accounts/{account_id}/tasks", status_code=201)
def create_task(
    account_id: int,
    body: TaskCreate,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    if body.task_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="invalid task_type")
    now = _now()
    # If linked to a lesson, store the stable Untis period id too.
    period_id = None
    if body.lesson_id is not None:
        hconn = history_conn()
        try:
            r = hconn.execute(
                "SELECT untis_period_id FROM lessons WHERE id = ? AND account_id = ?",
                (body.lesson_id, account_id),
            ).fetchone()
            period_id = r["untis_period_id"] if r else None
        finally:
            hconn.close()
    conn = webapp_conn()
    try:
        cur = conn.execute(
            "INSERT INTO tasks "
            "(account_id, ha_uid, title, subject_untis_id, subject_name, "
            " task_type, status, estimated_minutes, due_date, due_time, "
            " lesson_id, untis_period_id, notes, source, created_by_user_id, "
            " created_at, updated_at) "
            "VALUES (?, NULL, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?)",
            (
                account_id,
                body.title,
                body.subject_untis_id,
                body.subject_name,
                body.task_type,
                body.estimated_minutes,
                body.due_date,
                body.due_time,
                body.lesson_id,
                period_id,
                body.notes,
                user.id,
                now,
                now,
            ),
        )
        task_id = cur.lastrowid
        if body.subitems:
            for i, st in enumerate(body.subitems):
                conn.execute(
                    "INSERT INTO task_subitems (task_id, title, done, position) "
                    "VALUES (?, ?, 0, ?)",
                    (task_id, st, i),
                )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        after = dict(row)
        audit_log(
            conn,
            user_id=user.id,
            account_id=account_id,
            op_type="insert",
            target_kind="task",
            target_id=task_id,
            label=f"Aufgabe angelegt: {body.title}",
            after=after,
        )
        return _row_to_task(row)
    finally:
        conn.close()


@router.patch("/tasks/{task_id}")
async def patch_task(
    task_id: int,
    body: TaskPatch,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    if body.task_type is not None and body.task_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="invalid task_type")
    if body.status is not None and body.status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="invalid status")

    now = _now()
    conn = webapp_conn()
    try:
        existing = conn.execute(
            "SELECT id, account_id, status, source FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="task not found")
        assert_account_access(user, existing["account_id"])

        before = snapshot_task(conn, task_id)
        is_ha_task = existing["source"] == "ha_todo"

        # For Untis-sourced tasks, title and due date/time are owned by Untis
        # and must not be overwritten from the app — the next sync would
        # re-assert them anyway, so we reject silently here.
        ha_locked = {"title", "due_date", "due_time"} if is_ha_task else set()

        fields = []
        params: list = []
        for col in (
            "title", "task_type", "status", "estimated_minutes",
            "due_date", "due_time", "subject_untis_id", "subject_name", "notes",
        ):
            if col in ha_locked:
                continue
            val = getattr(body, col)
            if val is not None:
                fields.append(f"{col} = ?")
                params.append(val)

        if body.status == "done" and existing["status"] != "done":
            fields.append("completed_at = ?")
            params.append(now)
        elif body.status is not None and body.status != "done" and existing["status"] == "done":
            fields.append("completed_at = NULL")

        if not fields:
            return {"ok": True, "no_change": True}

        fields.append("updated_at = ?")
        params.append(now)
        params.append(task_id)
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", params)
        account_id = existing["account_id"]
        after = snapshot_task(conn, task_id)
        label = f"Aufgabe geändert: {after.get('title') if after else ''}"
        if body.status is not None and body.status != existing["status"]:
            label = f"{after.get('title')}: {existing['status']} → {body.status}"
        audit_log(
            conn,
            user_id=user.id,
            account_id=account_id,
            op_type="update",
            target_kind="task",
            target_id=task_id,
            label=label,
            before=before,
            after=after,
        )
        demo = is_demo(conn, user.id)
    finally:
        conn.close()

    # In demo mode, never push changes back to HA — keeps the kid's real list clean.
    if is_ha_task and body.status is not None and not demo:
        try:
            await sync_account(account_id)
        except Exception:
            pass

    return {"ok": True}


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    conn = webapp_conn()
    try:
        existing = conn.execute(
            "SELECT account_id, source FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="task not found")
        assert_account_access(user, existing["account_id"])
        if existing["source"] == "ha_todo":
            raise HTTPException(
                status_code=400,
                detail="HA-stämmige Tasks können nicht aus der App gelöscht werden; "
                       "bitte in HA-ToDo-Liste löschen",
            )
        before = snapshot_task(conn, task_id)
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        audit_log(
            conn,
            user_id=user.id,
            account_id=existing["account_id"],
            op_type="delete",
            target_kind="task",
            target_id=task_id,
            label=f"Aufgabe gelöscht: {before.get('title') if before else ''}",
            before=before,
        )
    finally:
        conn.close()
    return {"ok": True}


@router.post("/tasks/{task_id}/subitems", status_code=201)
def add_subitem(
    task_id: int,
    body: SubitemIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    conn = webapp_conn()
    try:
        task = conn.execute(
            "SELECT account_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        assert_account_access(user, task["account_id"])
        pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM task_subitems WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO task_subitems (task_id, title, done, position) "
            "VALUES (?, ?, 0, ?)",
            (task_id, body.title, pos),
        )
        return {"id": cur.lastrowid, "title": body.title, "done": False, "position": pos}
    finally:
        conn.close()


@router.patch("/subitems/{subitem_id}")
def patch_subitem(
    subitem_id: int,
    body: SubitemPatch,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT s.id, t.account_id FROM task_subitems s "
            "JOIN tasks t ON t.id = s.task_id WHERE s.id = ?",
            (subitem_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="subitem not found")
        assert_account_access(user, row["account_id"])

        fields = []
        params: list = []
        if body.title is not None:
            fields.append("title = ?")
            params.append(body.title)
        if body.done is not None:
            fields.append("done = ?")
            params.append(1 if body.done else 0)
        if body.position is not None:
            fields.append("position = ?")
            params.append(body.position)
        if fields:
            params.append(subitem_id)
            conn.execute(
                f"UPDATE task_subitems SET {', '.join(fields)} WHERE id = ?", params
            )
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/subitems/{subitem_id}")
def delete_subitem(
    subitem_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT s.id, t.account_id FROM task_subitems s "
            "JOIN tasks t ON t.id = s.task_id WHERE s.id = ?",
            (subitem_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="subitem not found")
        assert_account_access(user, row["account_id"])
        conn.execute("DELETE FROM task_subitems WHERE id = ?", (subitem_id,))
    finally:
        conn.close()
    return {"ok": True}


@router.post("/tasks/{task_id}/timer/start")
def timer_start(
    task_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    conn = webapp_conn()
    try:
        task = conn.execute(
            "SELECT account_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        assert_account_access(user, task["account_id"])
        open_session = conn.execute(
            "SELECT id FROM task_time_log "
            "WHERE task_id = ? AND user_id = ? AND ended_at IS NULL",
            (task_id, user.id),
        ).fetchone()
        if open_session:
            raise HTTPException(status_code=409, detail="Timer läuft bereits")
        cur = conn.execute(
            "INSERT INTO task_time_log (task_id, user_id, started_at) VALUES (?, ?, ?)",
            (task_id, user.id, _now()),
        )
        now = _now()
        conn.execute(
            "UPDATE tasks SET status = CASE WHEN status = 'open' THEN 'in_progress' ELSE status END, "
            "updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        return {"session_id": cur.lastrowid, "started_at": now}
    finally:
        conn.close()


@router.post("/tasks/{task_id}/timer/stop")
def timer_stop(
    task_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    conn = webapp_conn()
    try:
        task = conn.execute(
            "SELECT account_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        assert_account_access(user, task["account_id"])
        open_row = conn.execute(
            "SELECT id, started_at FROM task_time_log "
            "WHERE task_id = ? AND user_id = ? AND ended_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (task_id, user.id),
        ).fetchone()
        if open_row is None:
            raise HTTPException(status_code=404, detail="Kein laufender Timer")
        ended_at = _now()
        started_at = datetime.fromisoformat(open_row["started_at"])
        ended_dt = datetime.fromisoformat(ended_at)
        minutes = max(0, int((ended_dt - started_at).total_seconds() // 60))
        conn.execute(
            "UPDATE task_time_log SET ended_at = ?, minutes = ? WHERE id = ?",
            (ended_at, minutes, open_row["id"]),
        )
        return {"session_id": open_row["id"], "minutes": minutes}
    finally:
        conn.close()


@router.post("/accounts/{account_id}/sync-ha-todos")
async def manual_sync(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    await sync_account(account_id)
    return {"ok": True}
