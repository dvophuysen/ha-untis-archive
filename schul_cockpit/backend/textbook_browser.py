"""Real Chromium traversal for IServ → Eduplaces → Bildungslogin media shelf."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from playwright.async_api import Page, async_playwright


class TextbookScanError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShelfBook:
    title: str
    provider: str | None = None
    launch_url: str | None = None


_BOOK_WORDS = re.compile(
    r"(BiBox|Mathematik|Deutschbuch|Green Line|Geschichte und Geschehen|"
    r"Universum Physik|Fokus Chemie|Politik\s*&\s*Co|Diercke|Apúntate)", re.I
)


def _clean(value: str) -> str:
    return " ".join(value.split()).strip()


def select_book_titles(texts: list[str]) -> list[str]:
    """Keep meaningful shelf titles and remove nested-card duplicates."""
    candidates = []
    for raw in texts:
        value = _clean(raw)
        if 4 <= len(value) <= 180 and _BOOK_WORDS.search(value):
            candidates.append(value)
    unique: list[str] = []
    for value in sorted(set(candidates), key=lambda s: (len(s), s.casefold())):
        if not any(old.casefold() in value.casefold() for old in unique):
            unique.append(value)
    return unique


async def _click(page: Page, pattern: re.Pattern, timeout: int = 8_000) -> bool:
    for role in ("link", "button"):
        locator = page.get_by_role(role, name=pattern).first
        try:
            if await locator.count() and await locator.is_visible():
                before = len(page.context.pages)
                await locator.click(timeout=timeout)
                await asyncio.sleep(1)
                target = page.context.pages[-1] if len(page.context.pages) > before else page
                await target.wait_for_load_state("domcontentloaded", timeout=timeout)
                return True
        except Exception:
            continue
    return False


async def scan_shelf(portal_url: str, username: str, password: str) -> list[ShelfBook]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser.new_context(locale="de-DE")
        try:
            page = await context.new_page()
            await page.goto(portal_url.rstrip("/") + "/iserv/", wait_until="domcontentloaded", timeout=30_000)
            await page.locator('input[name="_username"]').fill(username)
            await page.locator('input[name="_password"]').fill(password)
            await page.locator('button[type="submit"]').click()
            await page.wait_for_load_state("domcontentloaded")
            if "/auth/login" in page.url:
                raise TextbookScanError("IServ-Anmeldung fehlgeschlagen")

            await page.goto(portal_url.rstrip("/") + "/iserv/eduplacesconnector/", wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(1)
            await _click(page, re.compile("Eduplaces", re.I))
            await asyncio.sleep(2)
            page = context.pages[-1]
            await _click(page, re.compile("Bildungslogin.*Medienregal|Medienregal", re.I))
            await asyncio.sleep(3)
            page = context.pages[-1]

            records = await page.locator("a,button,[role=link],[role=button],article").evaluate_all(
                "els => els.map(e => ({text:(e.innerText||e.textContent||'').trim(), href:e.href||null}))"
            )
            titles = select_book_titles([r.get("text") or "" for r in records])
            books: list[ShelfBook] = []
            for title in titles:
                match = next((r for r in records if _clean(r.get("text") or "") == title), None)
                href = match.get("href") if match else None
                provider = urlsplit(href).hostname if href else None
                books.append(ShelfBook(title=title, provider=provider, launch_url=href))
            if not books:
                raise TextbookScanError("Das Medienregal wurde geöffnet, aber keine Bücher wurden erkannt")
            return books
        except TextbookScanError:
            raise
        except Exception as exc:
            raise TextbookScanError("Das Medienregal konnte nicht automatisch gelesen werden") from exc
        finally:
            await context.close()
            await browser.close()
