"""Real Chromium traversal for IServ → Eduplaces → Bildungslogin media shelf."""

from __future__ import annotations

import re
import asyncio
from dataclasses import dataclass
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait


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
_GENERIC_LABELS = re.compile(
    r"^(Schulbuch|Mathematik|Deutsch|Englisch|Naturwissenschaften|"
    r"Mathematik und Naturwissenschaften|BiBox|BILDUNGSLOGIN(?: Medienregal)?|"
    r"Medienregal|Startseite|Profil|Abmelden|Menü)$",
    re.I,
)
_GENERIC_PHRASES = re.compile(
    r"(digitale(?:s)? Unterrichtssystem|digitale Schulbücher und Lernkurse|"
    r"direkt in alle digitale Bildungsmedien|Eduplaces)",
    re.I,
)


def _clean(value: str) -> str:
    return " ".join(value.split()).strip()


def select_book_titles(texts: list[str]) -> list[str]:
    """Keep meaningful shelf titles and remove nested-card duplicates."""
    candidates = []
    for raw in texts:
        value = _clean(raw)
        if (
            4 <= len(value) <= 180
            and not _GENERIC_LABELS.fullmatch(value)
            and not _GENERIC_PHRASES.search(value)
            and _BOOK_WORDS.search(value)
        ):
            candidates.append(value)
    unique: list[str] = []
    for value in sorted(set(candidates), key=lambda s: (len(s), s.casefold())):
        if not any(old.casefold() in value.casefold() for old in unique):
            unique.append(value)
    return unique


def _click(driver: webdriver.Chrome, pattern: re.Pattern, timeout: int = 10) -> bool:
    before = set(driver.window_handles)
    for element in driver.find_elements(By.CSS_SELECTOR, "a,button,[role='link'],[role='button']"):
        try:
            if element.is_displayed() and pattern.search(_clean(element.text or "")):
                driver.execute_script("arguments[0].click()", element)
                WebDriverWait(driver, timeout).until(
                    lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
                )
                new_handles = [handle for handle in driver.window_handles if handle not in before]
                if new_handles:
                    driver.switch_to.window(new_handles[-1])
                return True
        except Exception:
            continue
    return False


def _scan_shelf_sync(portal_url: str, username: str, password: str) -> list[ShelfBook]:
    options = webdriver.ChromeOptions()
    options.binary_location = "/usr/bin/chromium-browser"
    for arg in ("--headless", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"):
        options.add_argument(arg)
    options.add_argument("--lang=de-DE")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    try:
        driver.get(portal_url.rstrip("/") + "/iserv/")
        driver.find_element(By.NAME, "_username").send_keys(username)
        driver.find_element(By.NAME, "_password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        try:
            WebDriverWait(driver, 15).until(lambda d: "/auth/login" not in d.current_url)
        except TimeoutException:
            if "/auth/login" in driver.current_url:
                raise TextbookScanError("IServ-Anmeldung fehlgeschlagen")

        driver.get(portal_url.rstrip("/") + "/iserv/eduplacesconnector/")
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        if not _click(driver, re.compile("Bildungslogin.*Medienregal|Medienregal", re.I)):
            raise TextbookScanError("Das Bildungslogin-Medienregal wurde nicht gefunden")
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")

        def read_records(d):
            return d.execute_script(
                "return [...document.querySelectorAll("
                "'a,button,[role=link],[role=button],article,"
                "[class*=card],[class*=Card],[class*=product],[class*=Product],"
                "[class*=book],[class*=Book],[class*=media],[class*=Media]')]"
                ".map(e => ({"
                "text:(e.innerText||e.textContent||'').trim(),"
                "label:e.getAttribute('aria-label')||e.getAttribute('title')||'',"
                "image:[...e.querySelectorAll('img')].map(i=>i.alt||i.title||'').filter(Boolean).join(' '),"
                "hasImage:!!e.querySelector('img')||getComputedStyle(e).backgroundImage!=='none',"
                "isCard:/card|product|book|media/i.test(e.className||''),href:e.href||null}))"
            )

        def record_titles(records):
            values = []
            for record in records:
                for key in ("text", "label", "image"):
                    value = _clean(record.get(key) or "")
                    if (
                        5 <= len(value) <= 180
                        and not _GENERIC_LABELS.fullmatch(value)
                        and not _GENERIC_PHRASES.search(value)
                        and (
                            _BOOK_WORDS.search(value)
                            or record.get("hasImage")
                            or record.get("isCard")
                        )
                    ):
                        values.append(value)
                        break
            return select_book_titles(values) or sorted(set(values), key=str.casefold)

        WebDriverWait(driver, 15).until(
            lambda d: bool(record_titles(read_records(d)))
        )
        records = read_records(driver)
        titles = record_titles(records)
        books: list[ShelfBook] = []
        for title in titles:
            match = next((
                r for r in records
                if title in {_clean(r.get(key) or "") for key in ("text", "label", "image")}
            ), None)
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
        driver.quit()


async def scan_shelf(portal_url: str, username: str, password: str) -> list[ShelfBook]:
    return await asyncio.to_thread(_scan_shelf_sync, portal_url, username, password)
