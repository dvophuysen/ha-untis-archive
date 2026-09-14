"""Real Chromium traversal for IServ → Eduplaces → Bildungslogin media shelf."""

from __future__ import annotations

import re
import asyncio
from dataclasses import dataclass
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
    r"direkt in alle digitale Bildungsmedien|Eduplaces|"
    r"ausgeblendete Titel|Medium entfernen|Medienregal aktualisieren)",
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
            records = []
            def collect_current_frame():
                return d.execute_script("""
                    const out=[]; const seen=new Set();
                    function walk(root) {
                      for (const e of root.querySelectorAll('*')) {
                        if (seen.has(e)) continue; seen.add(e);
                        const tag=e.tagName.toLowerCase();
                        const cls=typeof e.className==='string'?e.className:'';
                        const label=e.getAttribute('aria-label')||e.getAttribute('title')||'';
                        const image=tag==='img'?(e.alt||e.title||''):
                          [...e.querySelectorAll(':scope > img')].map(i=>i.alt||i.title||'').filter(Boolean).join(' ');
                        const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ').trim();
                        const card=/card|product|book|medium|media|cover|shelf/i.test(cls);
                        const interactive=['a','button'].includes(tag)||e.getAttribute('role')==='link'||e.getAttribute('role')==='button';
                        const bg=getComputedStyle(e).backgroundImage!=='none';
                        if (label||image||own||(card&&e.innerText)) out.push({
                          text:(own||(card||interactive?e.innerText:'')||'').trim(),
                          label,image,hasImage:tag==='img'||!!image||bg,isCard:card,
                          href:e.href||e.getAttribute('data-href')||null
                        });
                        if(e.shadowRoot) walk(e.shadowRoot);
                      }
                    } walk(document); return out;
                """)
            def visit(depth=0):
                records.extend(collect_current_frame())
                if depth >= 3:
                    return
                frames = d.find_elements(By.CSS_SELECTOR, "iframe,frame")
                for frame in frames:
                    try:
                        d.switch_to.frame(frame)
                        visit(depth + 1)
                    except Exception:
                        pass
                    finally:
                        d.switch_to.parent_frame()
            visit()
            return records

        def record_titles(records):
            values = []
            for record in records:
                for key in ("image", "label", "text"):
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


def _find_and_click_in_frames(driver, title: str, depth: int = 0) -> bool:
    folded = _clean(title).casefold()
    for element in driver.find_elements(By.CSS_SELECTOR, "a,button,[role='link'],[role='button'],img"):
        try:
            values = (element.text, element.get_attribute("aria-label"), element.get_attribute("title"), element.get_attribute("alt"))
            if any(folded in _clean(value or "").casefold() for value in values):
                target = element if element.tag_name != "img" else element.find_element(By.XPATH, "./ancestor::*[self::a or self::button or @role='link' or @role='button'][1]")
                driver.execute_script("arguments[0].click()", target)
                return True
        except Exception:
            continue
    if depth < 3:
        for frame in driver.find_elements(By.CSS_SELECTOR, "iframe,frame"):
            switched = False
            try:
                driver.switch_to.frame(frame)
                switched = True
                if _find_and_click_in_frames(driver, title, depth + 1):
                    return True
            except Exception:
                pass
            finally:
                if switched:
                    driver.switch_to.parent_frame()
    return False


def _page_control(driver, depth: int = 0):
    control = driver.execute_script("""
      function find(root) {
        for (const e of root.querySelectorAll('input,[role="spinbutton"],[contenteditable="true"]')) {
          const hint=((e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')+' '+(e.placeholder||'')).toLowerCase();
          if(hint.includes('seite')||hint.includes('page')||e.type==='number') return e;
        }
        for(const e of root.querySelectorAll('*')) if(e.shadowRoot){const x=find(e.shadowRoot);if(x)return x;}
        return null;
      } return find(document);
    """)
    if control or depth >= 3:
        return control
    for frame in driver.find_elements(By.CSS_SELECTOR, "iframe,frame"):
        switched = False
        try:
            driver.switch_to.frame(frame)
            switched = True
            control = _page_control(driver, depth + 1)
            if control:
                return control
        except Exception:
            pass
        finally:
            if switched and not control:
                driver.switch_to.parent_frame()
    return None


def _capture_pages_sync(portal_url: str, username: str, password: str, title: str, pages: list[int]):
    options = webdriver.ChromeOptions()
    options.binary_location = "/usr/bin/chromium-browser"
    for arg in ("--headless", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--window-size=1440,1100"):
        options.add_argument(arg)
    driver = webdriver.Chrome(options=options); driver.set_page_load_timeout(30)
    try:
        driver.get(portal_url.rstrip("/") + "/iserv/")
        driver.find_element(By.NAME, "_username").send_keys(username)
        driver.find_element(By.NAME, "_password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        WebDriverWait(driver, 15).until(lambda d: "/auth/login" not in d.current_url)
        driver.get(portal_url.rstrip("/") + "/iserv/eduplacesconnector/")
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        if not _click(driver, re.compile("Bildungslogin.*Medienregal|Medienregal", re.I)):
            raise TextbookScanError("Das Medienregal wurde nicht gefunden")
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        before = set(driver.window_handles); old_url = driver.current_url
        if not _find_and_click_in_frames(driver, title):
            raise TextbookScanError("Das zugeordnete Schulbuch wurde im Regal nicht gefunden")
        WebDriverWait(driver, 15).until(lambda d: len(d.window_handles) > len(before) or d.current_url != old_url)
        new_handles = [h for h in driver.window_handles if h not in before]
        if new_handles: driver.switch_to.window(new_handles[-1])
        result = []
        for page in pages:
            driver.switch_to.default_content()
            control = WebDriverWait(driver, 20).until(_page_control)
            control.click(); control.send_keys(Keys.CONTROL, "a"); control.send_keys(str(page), Keys.ENTER)
            WebDriverWait(driver, 12).until(lambda d: str(page) in ((control.get_attribute("value") or control.text or "")))
            result.append((page, driver.get_screenshot_as_png()))
        return result
    except TextbookScanError:
        raise
    except Exception as exc:
        raise TextbookScanError("Die angegebenen Buchseiten konnten nicht geöffnet werden") from exc
    finally:
        driver.quit()


async def capture_pages(portal_url: str, username: str, password: str, title: str, pages: list[int]):
    return await asyncio.to_thread(_capture_pages_sync, portal_url, username, password, title, pages)
