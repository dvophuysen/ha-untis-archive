from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .db import webapp_conn
from .secret_store import decrypt_secret
from .textbook_browser import ShelfBook, TextbookScanError, scan_shelf

_LOGGER = logging.getLogger("schul_cockpit.textbooks")

_SUBJECTS = (
    ("mathematik", ("mathematik", "mathe", "neue wege")),
    ("englisch", ("green line", "englisch")),
    ("deutsch", ("deutschbuch", "deutsch")),
    ("geschichte", ("geschichte und geschehen", "geschichte")),
    ("physik", ("universum physik", "physik")),
    ("chemie", ("fokus chemie", "chemie")),
    ("politik", ("politik & co", "politik")),
    ("erdkunde", ("diercke", "erdkunde")),
    ("spanisch", ("apúntate", "apuntate", "spanisch")),
)


def infer_subject(title: str) -> str | None:
    folded = title.casefold()
    return next((subject for subject, words in _SUBJECTS if any(w in folded for w in words)), None)


async def scan_account(account_id: int) -> list[ShelfBook]:
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT portal_url,username,password_ciphertext FROM digital_textbook_credentials WHERE account_id=?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise TextbookScanError("Noch kein Zugang gespeichert")
    password = decrypt_secret(row["password_ciphertext"])
    try:
        books = await scan_shelf(row["portal_url"], row["username"], password)
    finally:
        password = ""
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        conn.execute("DELETE FROM digital_textbook_catalog WHERE account_id=?", (account_id,))
        for book in books:
            conn.execute(
                "INSERT INTO digital_textbook_catalog(account_id,title,provider,launch_url,subject_name,discovered_at) VALUES(?,?,?,?,?,?)",
                (account_id, book.title, book.provider, book.launch_url, infer_subject(book.title), now),
            )
        conn.execute(
            "UPDATE digital_textbook_credentials SET verification_status='catalog_ready',updated_at=? WHERE account_id=?",
            (now, account_id),
        )
    finally:
        conn.close()
    return books


async def scan_connected_accounts() -> None:
    await asyncio.sleep(8)
    conn = webapp_conn()
    try:
        ids = [r[0] for r in conn.execute(
            "SELECT c.account_id FROM digital_textbook_credentials c "
            "WHERE c.verification_status IN ('connected','scan_failed') "
            "OR EXISTS (SELECT 1 FROM digital_textbook_catalog b WHERE b.account_id=c.account_id "
            "AND (b.title='Mathematik und Naturwissenschaften' "
            "OR b.title LIKE 'BiBox%digital%Unterrichtssystem%'))"
        ).fetchall()]
    finally:
        conn.close()
    for account_id in ids:
        try:
            books = await scan_account(account_id)
            _LOGGER.info("digital textbook shelf ready for account %s (%s books)", account_id, len(books))
        except Exception as exc:
            conn = webapp_conn()
            try:
                conn.execute(
                    "UPDATE digital_textbook_credentials SET verification_status='scan_failed' WHERE account_id=?",
                    (account_id,),
                )
            finally:
                conn.close()
            _LOGGER.warning("digital textbook shelf scan failed for account %s: %s", account_id, type(exc).__name__)
