from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import webapp_conn
from ..iserv_connector import IservLoginError, verify_iserv_login
from ..secret_store import decrypt_secret, encrypt_secret
from ..textbook_browser import TextbookScanError
from ..textbook_catalog import scan_account
from ..textbook_context import (browser_check_state, last_fetch, page_test_state, start_browser_check,
                                start_page_test)

router = APIRouter(prefix="/accounts/{account_id}/textbooks", tags=["textbooks"])


class CredentialsIn(BaseModel):
    portal_url: str = Field(min_length=8, max_length=300)
    username: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, max_length=500)


class CatalogSubjectIn(BaseModel):
    subject_name: str | None = Field(default=None, max_length=120)


class PageTestIn(BaseModel):
    page: int = Field(ge=1, le=2000)


def _require_parent(user: CurrentUser, account_id: int) -> None:
    assert_account_access(user, account_id)
    if user.role not in {"parent", "admin"} and not user.is_admin:
        raise HTTPException(status_code=403, detail="Nur in der Elternansicht verfügbar")


def _portal_url(raw: str) -> str:
    value = raw.strip()
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
    ):
        raise HTTPException(status_code=422, detail="Bitte eine sichere IServ-Adresse angeben")
    host = parsed.hostname.lower().rstrip(".")
    if host != "iserv.de" and not host.endswith("-iserv.de") and not host.endswith(".iserv.de"):
        raise HTTPException(status_code=422, detail="Die Adresse ist kein IServ-Portal")
    return urlunsplit(("https", host, "", "", ""))


def _public(row) -> dict:
    return {
        "configured": row is not None,
        "portal_url": row["portal_url"] if row else "https://beispiel-iserv.de",
        "username": row["username"] if row else "",
        "password_saved": row is not None,
        "verified_at": row["verified_at"] if row else None,
        "verification_status": row["verification_status"] if row else None,
        "updated_at": row["updated_at"] if row else None,
    }


@router.get("")
def get_credentials(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    _require_parent(user, account_id)
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT portal_url, username, verified_at, verification_status, updated_at "
            "FROM digital_textbook_credentials WHERE account_id=?", (account_id,)
        ).fetchone()
        return _public(row)
    finally:
        conn.close()


@router.put("")
def put_credentials(
    account_id: int,
    body: CredentialsIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_parent(user, account_id)
    portal = _portal_url(body.portal_url)
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="Bitte den Benutzernamen angeben")
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        existing = conn.execute(
            "SELECT password_ciphertext, created_at FROM digital_textbook_credentials WHERE account_id=?",
            (account_id,),
        ).fetchone()
        if body.password is None or body.password == "":
            if existing is None:
                raise HTTPException(status_code=422, detail="Bitte das Passwort angeben")
            ciphertext = existing["password_ciphertext"]
            created_at = existing["created_at"]
        else:
            ciphertext = encrypt_secret(body.password)
            created_at = existing["created_at"] if existing else now
        conn.execute(
            "INSERT INTO digital_textbook_credentials "
            "(account_id,portal_url,username,password_ciphertext,verified_at,verification_status,created_at,updated_at) "
            "VALUES(?,?,?,?,NULL,'pending',?,?) ON CONFLICT(account_id) DO UPDATE SET "
            "portal_url=excluded.portal_url, username=excluded.username, "
            "password_ciphertext=excluded.password_ciphertext, verified_at=NULL, "
            "verification_status='pending', updated_at=excluded.updated_at",
            (account_id, portal, username, ciphertext, created_at, now),
        )
        row = conn.execute(
            "SELECT portal_url, username, verified_at, verification_status, updated_at "
            "FROM digital_textbook_credentials WHERE account_id=?", (account_id,)
        ).fetchone()
        return _public(row)
    finally:
        conn.close()


@router.delete("", status_code=204)
def delete_credentials(account_id: int, user: CurrentUser = Depends(get_current_user)) -> Response:
    _require_parent(user, account_id)
    conn = webapp_conn()
    try:
        conn.execute("DELETE FROM digital_textbook_credentials WHERE account_id=?", (account_id,))
    finally:
        conn.close()
    return Response(status_code=204)


@router.post("/verify")
async def verify_credentials(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_parent(user, account_id)
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT portal_url,username,password_ciphertext FROM digital_textbook_credentials WHERE account_id=?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Noch kein Zugang gespeichert")
    try:
        password = decrypt_secret(row["password_ciphertext"])
        await verify_iserv_login(row["portal_url"], row["username"], password)
    except IservLoginError as exc:
        now = datetime.now(timezone.utc).isoformat()
        conn = webapp_conn()
        try:
            conn.execute(
                "UPDATE digital_textbook_credentials SET verified_at=NULL,verification_status='failed',updated_at=? WHERE account_id=?",
                (now, account_id),
            )
        finally:
            conn.close()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        password = ""
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        conn.execute(
            "UPDATE digital_textbook_credentials SET verified_at=?,verification_status='connected',updated_at=? WHERE account_id=?",
            (now, now, account_id),
        )
        row = conn.execute(
            "SELECT portal_url,username,verified_at,verification_status,updated_at FROM digital_textbook_credentials WHERE account_id=?",
            (account_id,),
        ).fetchone()
        return _public(row)
    finally:
        conn.close()


@router.get("/catalog")
def get_catalog(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    _require_parent(user, account_id)
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT id,title,provider,subject_name,discovered_at FROM digital_textbook_catalog WHERE account_id=? ORDER BY COALESCE(subject_name,'zz'),title",
            (account_id,),
        ).fetchall()
        status = conn.execute(
            "SELECT verification_status FROM digital_textbook_credentials WHERE account_id=?", (account_id,)
        ).fetchone()
        access_rows = {r["book_title"]: dict(r) for r in conn.execute(
            "SELECT book_title,status,page,printed_page,detail,checked_at,toc_state FROM digital_textbook_access WHERE account_id=?",
            (account_id,))}
        chapters = {r["book_title"]: r["n"] for r in conn.execute(
            "SELECT book_title, COUNT(*) AS n FROM book_chapters WHERE account_id=? GROUP BY book_title", (account_id,))}
        stored = {r["source_book"]: r["n"] for r in conn.execute(
            "SELECT source_book, COUNT(*) AS n FROM materials WHERE account_id=? AND origin='book_fetch' AND hidden=0 "
            "GROUP BY source_book", (account_id,))}
        books = []
        for r in rows:
            book = dict(r)
            book["access"] = access_rows.get(r["title"])
            book["pages_stored"] = stored.get(r["title"], 0)
            book["chapters"] = chapters.get(r["title"], 0)
            books.append(book)
        return {
            "status": status[0] if status else None,
            "books": books,
            "last_fetch": last_fetch(account_id),
        }
    finally:
        conn.close()


@router.post("/catalog/scan")
async def scan_catalog(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    _require_parent(user, account_id)
    try:
        await scan_account(account_id)
    except TextbookScanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return get_catalog(account_id, user)


@router.patch("/catalog/{book_id}")
def update_catalog_subject(
    account_id: int,
    book_id: int,
    body: CatalogSubjectIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_parent(user, account_id)
    subject = body.subject_name.strip() if body.subject_name else None
    conn = webapp_conn()
    try:
        changed = conn.execute(
            "UPDATE digital_textbook_catalog SET subject_name=? WHERE id=? AND account_id=?",
            (subject or None, book_id, account_id),
        ).rowcount
    finally:
        conn.close()
    if not changed:
        raise HTTPException(status_code=404, detail="Schulbuch nicht gefunden")
    return get_catalog(account_id, user)


@router.delete("/catalog/{book_id}", status_code=204)
def remove_catalog_entry(account_id: int, book_id: int, user: CurrentUser = Depends(get_current_user)) -> Response:
    """Einen Eintrag aus dem Regal nehmen, der kein Buch ist (etwa eine
    Schaltfläche des Einwilligungsdialogs). Ein echtes Buch kommt beim
    nächsten Scan wieder; gelesene Kapitel und Seiten bleiben."""
    _require_parent(user, account_id)
    conn = webapp_conn()
    try:
        row = conn.execute("SELECT title FROM digital_textbook_catalog WHERE id=? AND account_id=?",
                           (book_id, account_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
        conn.execute("DELETE FROM digital_textbook_catalog WHERE id=? AND account_id=?", (book_id, account_id))
        conn.execute("DELETE FROM digital_textbook_access WHERE account_id=? AND book_title=? AND NOT EXISTS "
                     "(SELECT 1 FROM book_chapters c WHERE c.account_id=? AND c.book_title=?)",
                     (account_id, row["title"], account_id, row["title"]))
        conn.commit()
    finally:
        conn.close()
    return Response(status_code=204)


@router.post("/catalog/{book_id}/page-test", status_code=202)
async def page_test(
    account_id: int,
    book_id: int,
    body: PageTestIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Start one real page fetch in the background.

    The fetch outlasts the 100 seconds the remote-access proxy allows a
    request, so the answer is "running" and GET on the same address tells how
    it went.
    """
    _require_parent(user, account_id)
    state = start_page_test(account_id, book_id, body.page)
    if state.get("status") == "unknown_book":
        raise HTTPException(status_code=404, detail="Schulbuch nicht gefunden")
    if state.get("status") == "not_configured":
        raise HTTPException(status_code=422, detail="Noch kein Zugang gespeichert")
    return state


@router.get("/catalog/{book_id}/page-test")
def page_test_result(
    account_id: int,
    book_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """The running or last finished page test of this book."""
    _require_parent(user, account_id)
    return page_test_state(account_id, book_id)


@router.post("/browser-check", status_code=202)
async def browser_check(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Start the browser probe: Chromium with several GPU settings on a page
    that says whether WebGL exists, plus what Chromium printed. Diagnosis for
    readers that draw with WebGL; touches no portal and no credential."""
    _require_parent(user, account_id)
    return start_browser_check(account_id)


@router.get("/browser-check")
def browser_check_result(account_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    _require_parent(user, account_id)
    return browser_check_state(account_id)
