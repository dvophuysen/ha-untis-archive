"""Real Chromium traversal for IServ → Eduplaces → Bildungslogin media shelf."""

from __future__ import annotations

import os
import re
import time
import asyncio
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import Select, WebDriverWait


class TextbookScanError(RuntimeError):
    def __init__(self, message: str, stage: str | None = None):
        super().__init__(message)
        self.stage = stage


_CHROMIUM = "/usr/bin/chromium-browser"
_CHROMEDRIVER = "/usr/bin/chromedriver"


def _driver(*extra_args: str) -> webdriver.Chrome:
    """Headless Chromium on the driver shipped in the image. Without the
    explicit service, Selenium Manager first tries to download one and fails
    on aarch64 before falling back."""
    options = webdriver.ChromeOptions()
    options.binary_location = _CHROMIUM
    for arg in ("--headless", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", *extra_args):
        options.add_argument(arg)
    options.add_argument("--lang=de-DE")
    service = Service(executable_path=_CHROMEDRIVER) if os.path.exists(_CHROMEDRIVER) else None
    driver = webdriver.Chrome(options=options, service=service) if service else webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


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
    driver = _driver()
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


_BOOK_TARGET_SCRIPT = r"""
const normalize = s => (s || '').normalize('NFKC').replace(/\s+/g, ' ').trim().toLocaleLowerCase('de');
const wanted = normalize(arguments[0]);
// A shelf entry may carry a suffix ("… – BiBox") or drop one, so allow a
// contained match, but only for titles long enough to be unambiguous.
const loose = wanted.length >= 12;
const exact = [];
const partial = [];
function walk(root) {
  for (const e of root.querySelectorAll('*')) {
    const own = [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ');
    const labels = [own, e.getAttribute('aria-label'), e.getAttribute('title'), e.getAttribute('alt')];
    if (e.getClientRects().length) {
      if (labels.some(s => normalize(s) === wanted)) exact.push(e);
      else if (loose && labels.some(s => {
        const v = normalize(s);
        return v.length >= 12 && (v.startsWith(wanted) || wanted.startsWith(v));
      })) partial.push(e);
    }
    if (e.shadowRoot) walk(e.shadowRoot);
  }
}
walk(document);
for (const e of exact.concat(partial)) {
  let p = e;
  while (p) {
    if (p.matches('a,button,[role="link"],[role="button"],[tabindex="0"]')) return p;
    p = p.parentElement || p.getRootNode().host;
  }
  // Product cards often use a click listener on a plain div. A real click
  // on the exact title bubbles to that listener without guessing a link.
  return e;
}
return null;
"""


def _find_and_click_in_frames(driver, title: str, depth: int = 0) -> bool:
    target = driver.execute_script(_BOOK_TARGET_SCRIPT, title)
    if target is not None:
        target.click()
        return True
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


def _open_book(driver, title: str, launch_url: str | None = None):
    def ready(d):
        d.switch_to.default_content()
        return _find_and_click_in_frames(d, title)
    try:
        WebDriverWait(driver, 25).until(ready)
    except TimeoutException as exc:
        # The stored launch address is the shelf's own link for this book and
        # stays usable when the cover itself is not clickable any more.
        if launch_url and launch_url.startswith("https://"):
            driver.get(launch_url)
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return
        raise TextbookScanError(
            "Das zugeordnete Schulbuch wurde im Regal nicht gefunden", "Buch öffnen"
        ) from exc


def _in_frames(driver, script, *args, depth: int = 0):
    """First hit of a locator script, leaving the driver in the frame that has it."""
    found = driver.execute_script(script, *args)
    if found or depth >= 3:
        return found
    for frame in driver.find_elements(By.CSS_SELECTOR, "iframe,frame"):
        switched = False
        try:
            driver.switch_to.frame(frame)
            switched = True
            found = _in_frames(driver, script, *args, depth=depth + 1)
            if found:
                return found
        except Exception:
            found = None
        finally:
            if switched and not found:
                driver.switch_to.parent_frame()
    return None


_PAGE_FIELD_SCRIPT = """
  function find(root) {
    for (const e of root.querySelectorAll('input,[role="spinbutton"],[contenteditable="true"]')) {
      const hint=((e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')+' '+(e.placeholder||'')
        +' '+(e.id||'')+' '+(typeof e.className==='string'?e.className:'')+' '+(e.getAttribute('name')||'')).toLowerCase();
      // click & study names its field only by id (#selectPage): no label, no
      // placeholder, type="text". Id, class and name therefore count as hints.
      if(hint.includes('seite')||hint.includes('page')||e.type==='number') return e;
    }
    for(const e of root.querySelectorAll('*')) if(e.shadowRoot){const x=find(e.shadowRoot);if(x)return x;}
    return null;
  } return find(document);
"""

_PAGE_SELECT_SCRIPT = r"""
const wanted=String(arguments[0]);
const strip=s=>(s||'').replace(/\s+/g,' ').trim().replace(/^(S\.?|Seite|Page)\s*/i,'');
function find(root){
  for(const e of root.querySelectorAll('select')){
    for(const o of e.options) if(strip(o.textContent)===wanted) return e;
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot){const x=find(e.shadowRoot);if(x)return x;}
  return null;
} return find(document);
"""

_PAGE_BUTTON_SCRIPT = r"""
const wanted=String(arguments[0]);
const strip=s=>(s||'').replace(/\s+/g,' ').trim().replace(/^(S\.?|Seite|Page)\s*/i,'');
function find(root){
  for(const e of root.querySelectorAll('a,button,[role="link"],[role="button"],li,td')){
    const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ');
    const labels=[own,e.getAttribute('aria-label'),e.getAttribute('title')];
    if(labels.some(s=>strip(s)===wanted) && e.getClientRects().length) return e;
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot){const x=find(e.shadowRoot);if(x)return x;}
  return null;
} return find(document);
"""

_DISMISS_SCRIPT = r"""
// Publishers greet the reader with advertising and cookie dialogs. Their
// backdrop swallows every click on the page navigation behind it.
const CLOSE=/(schlie(ß|ss)en|close|ausblenden|nicht mehr anzeigen|verstanden|akzeptieren|zustimmen)/i;
function look(root){
  for(const d of root.querySelectorAll('[role="dialog"],[role="alertdialog"],.modal,cdk-dialog-container,mat-dialog-container')){
    if(!d.getClientRects().length) continue;
    for(const b of d.querySelectorAll('button,a,[role="button"]')){
      const own=[...b.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ');
      const name=((b.getAttribute('aria-label')||'')+' '+(b.getAttribute('title')||'')+' '+own).replace(/\s+/g,' ').trim();
      if(CLOSE.test(name)&&b.getClientRects().length) return b;
    }
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot){const x=look(e.shadowRoot);if(x)return x;}
  return null;
}
return look(document);
"""

_PAGE_NEIGHBOUR_SCRIPT = r"""
// Cornelsen names its page field with a generated React id and hashed
// classes, but the buttons beside it say "Vorherige Seite" / "Nächste
// Seite". The field in that same control group is the one we need.
const NAV=/(n(ä|ae)chste seite|weiterbl(ä|ae)ttern|next page|vorherige seite|zur(ü|ue)ckbl(ä|ae)ttern|previous page)/i;
const SEARCH=/(such|search|filter)/i;
function name(e){return ((e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')).replace(/\s+/g,' ').trim();}
function look(root){
  for(const nav of root.querySelectorAll('a,button,div,span,[role="button"],[role="link"]')){
    if(!NAV.test(name(nav))) continue;
    let up=nav;
    for(let step=0;step<4&&up;step++){
      for(const field of up.querySelectorAll('input,[contenteditable="true"]')){
        const kind=(field.getAttribute('type')||'text').toLowerCase();
        if(['checkbox','radio','search','hidden','button','submit'].includes(kind)) continue;
        const hint=((field.id||'')+' '+(typeof field.className==='string'?field.className:'')+' '+(field.placeholder||'')).toLowerCase();
        if(SEARCH.test(hint)) continue;
        if(field.getClientRects().length) return field;
      }
      up=up.parentElement;
    }
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot){const x=look(e.shadowRoot);if(x)return x;}
  return null;
}
return look(document);
"""

_SHOWN_PAGE_SCRIPT = r"""
const out=[];
function look(root){
  for(const e of root.querySelectorAll('input,select,[role="spinbutton"],[contenteditable="true"]')){
    const hint=((e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')+' '+(e.placeholder||'')
      +' '+(e.id||'')+' '+(typeof e.className==='string'?e.className:'')+' '+(e.getAttribute('name')||'')).toLowerCase();
    if(hint.includes('seite')||hint.includes('page')||e.type==='number'||e.tagName==='SELECT')
      out.push((e.value||e.textContent||'').trim());
  }
  for(const e of root.querySelectorAll('*')){
    const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ').trim();
    if(own && /^(S\.?|Seite|Page)?\s*\d{1,4}\s*(\/|von|of|-|–)\s*\d{1,4}$/i.test(own)) out.push(own);
    // Rendered page areas carry their number as a label, one per open page.
    const marked=((e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')).trim();
    const page=marked.match(/(?:Seite|Page)\s+(\d{1,4})/i);
    if(page) out.push(page[1]);
    if(e.shadowRoot) look(e.shadowRoot);
  }
}
look(document); return out.join('|');
"""

_VIEWER_AREA_SCRIPT = """
let best=null, area=0;
function look(root){
  for(const e of root.querySelectorAll('canvas,img,svg,object,embed,[class*="page"],[class*="seite"],[class*="spread"],[class*="viewer"],[class*="reader"]')){
    const r=e.getBoundingClientRect();
    const a=r.width*r.height;
    if(a>area && r.width>=innerWidth*0.35 && r.height>=innerHeight*0.35){best=e;area=a;}
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot) look(e.shadowRoot);
}
look(document); return best;
"""

_PAGE_IN_URL = re.compile(r"(?i)((?:seite|page|pg|p)[/=_-])(\d{1,4})")
# "30 / 210" names the current page and the total; "30-31" is one spread.
_SPREAD = re.compile(r"(\d{1,4})\s*[-–]\s*(\d{1,4})")


def shown_page_numbers(text: str, url: str = "") -> list[int]:
    """Page numbers a viewer currently claims to display."""
    numbers: list[int] = []
    for chunk in (text or "").split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        spread = _SPREAD.search(chunk)
        if spread:
            numbers.extend(int(x) for x in spread.groups())
            continue
        found = re.findall(r"\d{1,4}", chunk)
        if found:
            numbers.append(int(found[0]))
    match = _PAGE_IN_URL.search(url or "")
    if match:
        numbers.append(int(match.group(2)))
    return numbers


def _shown_pages(driver) -> list[int]:
    parts: list[str] = []

    def collect(depth: int = 0) -> None:
        try:
            parts.append(driver.execute_script(_SHOWN_PAGE_SCRIPT) or "")
        except Exception:
            return
        if depth >= 3:
            return
        for frame in driver.find_elements(By.CSS_SELECTOR, "iframe,frame"):
            switched = False
            try:
                driver.switch_to.frame(frame)
                switched = True
                collect(depth + 1)
            except Exception:
                pass
            finally:
                if switched:
                    driver.switch_to.parent_frame()

    driver.switch_to.default_content()
    collect()
    url = driver.current_url
    driver.switch_to.default_content()
    return shown_page_numbers("|".join(parts), url)


def _wait_for_page(driver, page: int, timeout: float = 12.0) -> bool:
    """Poll the viewer's own page display. Elements are re-read every time,
    because a page change re-renders and invalidates the previous handles."""
    end = time.monotonic() + timeout
    while True:
        try:
            if page in _shown_pages(driver):
                return True
        except Exception:
            pass
        if time.monotonic() >= end:
            return False
        time.sleep(0.5)


def _page_control(driver):
    return _in_frames(driver, _PAGE_FIELD_SCRIPT)


def _dismiss_overlays(driver, rounds: int = 3) -> None:
    """Close advertising and cookie dialogs that swallow clicks."""
    for _ in range(rounds):
        driver.switch_to.default_content()
        try:
            button = _in_frames(driver, _DISMISS_SCRIPT)
            if button is None:
                return
            button.click()
            time.sleep(0.4)
        except Exception:
            return
    driver.switch_to.default_content()


def _type_page(driver, control, page: int) -> bool:
    control.click()
    control.send_keys(Keys.CONTROL, "a")
    control.send_keys(str(page), Keys.ENTER)
    return _wait_for_page(driver, page)


def _field_goto(driver, page: int) -> bool:
    control = _page_control(driver)
    if control is None:
        return False
    return _type_page(driver, control, page)


def _neighbour_goto(driver, page: int) -> bool:
    control = _in_frames(driver, _PAGE_NEIGHBOUR_SCRIPT)
    if control is None:
        return False
    return _type_page(driver, control, page)


def _select_goto(driver, page: int) -> bool:
    control = _in_frames(driver, _PAGE_SELECT_SCRIPT, str(page))
    if control is None:
        return False
    for option in Select(control).options:
        if re.sub(r"^(S\.?|Seite|Page)\s*", "", (option.text or "").strip(), flags=re.I) == str(page):
            option.click()
            return _wait_for_page(driver, page)
    return False


def _button_goto(driver, page: int) -> bool:
    control = _in_frames(driver, _PAGE_BUTTON_SCRIPT, str(page))
    if control is None:
        return False
    control.click()
    # Only count it when the viewer confirms the page; a bare click could just
    # as well have opened a chapter, and a wrong page is worse than none.
    return _wait_for_page(driver, page)


def _url_goto(driver, page: int) -> bool:
    driver.switch_to.default_content()
    url = driver.current_url
    target = _PAGE_IN_URL.sub(lambda m: m.group(1) + str(page), url, count=1)
    if target == url:
        return False
    try:
        driver.get(target)
    except TimeoutException:
        # A single-page app can keep the load flag open long after the route
        # has changed. Judge by what the viewer shows, not by the flag.
        pass
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass
    _dismiss_overlays(driver)
    return _wait_for_page(driver, page)


def _go_to_page(driver, page: int) -> bool:
    driver.switch_to.default_content()
    if page in _shown_pages(driver):
        return True
    _dismiss_overlays(driver)
    for strategy in (_field_goto, _neighbour_goto, _select_goto, _button_goto, _url_goto):
        driver.switch_to.default_content()
        try:
            if strategy(driver, page):
                return True
        except Exception:
            continue
    return False


def _viewer_shot(driver) -> bytes:
    """The book area alone if the viewer exposes one, otherwise the window."""
    driver.switch_to.default_content()
    try:
        area = _in_frames(driver, _VIEWER_AREA_SCRIPT)
        if area is not None:
            shot = area.screenshot_as_png
            if shot:
                return shot
    except Exception:
        pass
    driver.switch_to.default_content()
    return driver.get_screenshot_as_png()


def _stable_shot(driver, tries: int = 4, pause: float = 0.7) -> bytes:
    """Canvas viewers keep drawing after the page number changes."""
    shot = _viewer_shot(driver)
    for _ in range(tries):
        time.sleep(pause)
        again = _viewer_shot(driver)
        if again == shot:
            return again
        shot = again
    return shot


_CONTROL_SURVEY_SCRIPT = r"""
const out=[];
const cut=(s,n)=>((s||'').replace(/\s+/g,' ').trim().slice(0,n));
const TEXTY=new Set(['A','BUTTON','SUMMARY','OPTION']);
const ROLES=['button','link','menuitem','tab','option','spinbutton'];
function look(root){
  for(const e of root.querySelectorAll('a,button,input,select,textarea,summary,[role],[contenteditable],[tabindex]')){
    if(out.length>=150) return;
    const r=e.getBoundingClientRect();
    const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ');
    const role=e.getAttribute('role')||'';
    out.push({
      tag:e.tagName.toLowerCase(), type:cut(e.getAttribute('type'),20), role:cut(role,20),
      label:cut(e.getAttribute('aria-label'),60), title:cut(e.getAttribute('title'),60),
      placeholder:cut(e.getAttribute('placeholder'),40), name:cut(e.getAttribute('name'),40),
      id:cut(e.id,40), cls:cut(typeof e.className==='string'?e.className:'',60),
      text:(TEXTY.has(e.tagName)||ROLES.includes(role))?cut(own,40):'',
      value:(e.tagName==='INPUT'||e.tagName==='SELECT')?cut(e.value,20):'',
      visible:r.width>0&&r.height>0
    });
    if(e.shadowRoot) look(e.shadowRoot);
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot) look(e.shadowRoot);
}
look(document);
return {url:location.pathname+location.hash, title:cut(document.title,80), controls:out};
"""

# Viewer addresses can carry a session token. Long opaque runs are dropped;
# short, telling parts such as "#/page/12" survive.
_OPAQUE = re.compile(r"[A-Za-z0-9_-]{24,}")
_SURVEY_FIELDS = ("label", "title", "placeholder", "name", "text", "id", "cls", "value")


def _survey(driver) -> dict:
    """Control metadata of the open viewer for the parent-facing page test.

    Deliberately no running text from the book: only labels of operating
    elements, and button captions cut to 40 characters.
    """
    controls: list[dict] = []
    documents: list[dict] = []

    def visit(depth: int = 0) -> None:
        try:
            data = driver.execute_script(_CONTROL_SURVEY_SCRIPT) or {}
        except Exception:
            return
        for control in data.get("controls", []):
            control["frame"] = depth
            if any(control.get(field) for field in _SURVEY_FIELDS):
                controls.append(control)
        documents.append({
            "frame": depth,
            "url": _OPAQUE.sub("…", data.get("url") or ""),
            "title": data.get("title") or "",
        })
        if depth >= 3 or len(controls) >= 200:
            return
        for frame in driver.find_elements(By.CSS_SELECTOR, "iframe,frame"):
            switched = False
            try:
                driver.switch_to.frame(frame)
                switched = True
                visit(depth + 1)
            except Exception:
                pass
            finally:
                if switched:
                    driver.switch_to.parent_frame()

    driver.switch_to.default_content()
    visit()
    driver.switch_to.default_content()
    return {"controls": controls[:200], "documents": documents}


@dataclass(frozen=True)
class PageShot:
    page: int | None  # None: the book is open, but this page was not reachable
    image: bytes


@dataclass
class CaptureResult:
    shots: list[PageShot] = field(default_factory=list)
    note: str = ""
    controls: list[dict] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)
    window_image: bytes | None = None


def _capture_pages_sync(
    portal_url: str,
    username: str,
    password: str,
    title: str,
    pages: list[int],
    launch_url: str | None = None,
    survey: bool = False,
    budget: float = 240.0,
) -> CaptureResult:
    driver = _driver("--window-size=1440,1100")
    deadline = time.monotonic() + budget
    stage = "IServ-Anmeldung"
    try:
        driver.get(portal_url.rstrip("/") + "/iserv/")
        driver.find_element(By.NAME, "_username").send_keys(username)
        driver.find_element(By.NAME, "_password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        WebDriverWait(driver, 15).until(lambda d: "/auth/login" not in d.current_url)
        stage = "Eduplaces öffnen"
        driver.get(portal_url.rstrip("/") + "/iserv/eduplacesconnector/")
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        if not _click(driver, re.compile("Bildungslogin.*Medienregal|Medienregal", re.I)):
            raise TextbookScanError("Das Medienregal wurde nicht gefunden", stage)
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        stage = "Buch öffnen"
        before = set(driver.window_handles)
        old_url = driver.current_url
        _open_book(driver, title, launch_url)

        def viewer_started(d):
            if len(d.window_handles) > len(before) or d.current_url != old_url:
                return True
            d.switch_to.default_content()
            return bool(_page_control(d))

        WebDriverWait(driver, 30).until(viewer_started)
        new_handles = [h for h in driver.window_handles if h not in before]
        if new_handles:
            driver.switch_to.window(new_handles[-1])
        _dismiss_overlays(driver)
        stage = "Seitennavigation finden"
        shots: list[PageShot] = []
        note = ""
        for page in pages:
            if time.monotonic() > deadline:
                note = "Zeitbudget erreicht"
                break
            if not _go_to_page(driver, page):
                continue
            stage = f"Seite {page} lesen"
            shots.append(PageShot(page, _stable_shot(driver)))
        if not shots:
            # The book is open. Hand over what it shows rather than nothing;
            # the mentor is told that the page could not be confirmed.
            note = note or "Seitennavigation nicht gefunden"
            driver.switch_to.default_content()
            shots.append(PageShot(None, _stable_shot(driver)))
        elif len(shots) < len(pages) and not note:
            note = "Nicht alle Seiten erreichbar"
        result = CaptureResult(shots=shots, note=note)
        if survey:
            seen = _survey(driver)
            result.controls = seen["controls"]
            result.documents = seen["documents"]
            driver.switch_to.default_content()
            result.window_image = driver.get_screenshot_as_png()
        return result
    except TextbookScanError:
        raise
    except Exception as exc:
        raise TextbookScanError(
            f"Die angegebenen Buchseiten konnten nicht geöffnet werden ({stage})", stage
        ) from exc
    finally:
        driver.quit()


async def capture_pages(
    portal_url: str,
    username: str,
    password: str,
    title: str,
    pages: list[int],
    launch_url: str | None = None,
    survey: bool = False,
) -> CaptureResult:
    return await asyncio.to_thread(
        _capture_pages_sync, portal_url, username, password, title, pages, launch_url, survey
    )
