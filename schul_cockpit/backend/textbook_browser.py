"""Real Chromium traversal for IServ → Eduplaces → Bildungslogin media shelf."""

from __future__ import annotations

import io
import logging
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

_LOGGER = logging.getLogger("schul_cockpit.textbooks")


class TextbookScanError(RuntimeError):
    def __init__(self, message: str, stage: str | None = None):
        super().__init__(message)
        self.stage = stage


_CHROMIUM = "/usr/bin/chromium-browser"
_CHROMEDRIVER = "/usr/bin/chromedriver"


def browser_arguments(*extra_args: str, software_webgl: bool = True) -> list[str]:
    """Flags for the headless browser.

    The BiBox reader draws its pages with WebGL. With --disable-gpu, WebGL is
    gone entirely: the reader keeps toolbar and page counter, shows a white
    void and reports "CanvasRenderer is not yet implemented". Alpine's
    Chromium carries no SwiftShader, so software WebGL comes from Mesa's
    Lavapipe through ANGLE's Vulkan backend; software drivers are on the GPU
    blocklist and need --ignore-gpu-blocklist.
    """
    gpu = (["--use-gl=angle", "--use-angle=vulkan", "--ignore-gpu-blocklist"]
           if software_webgl else ["--disable-gpu"])
    return ["--headless", "--no-sandbox", "--disable-dev-shm-usage", *gpu, "--lang=de-DE", *extra_args]


def _start(arguments: list[str]) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.binary_location = _CHROMIUM
    for arg in arguments:
        options.add_argument(arg)
    # Console errors are the only place a reader says why it draws nothing.
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    service = Service(executable_path=_CHROMEDRIVER) if os.path.exists(_CHROMEDRIVER) else None
    driver = webdriver.Chrome(options=options, service=service) if service else webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


# Whether the browser came up with software WebGL in this process. A failed
# start costs two minutes of waiting on the driver, so a failure is remembered,
# but only for an hour: until 1.31.2 one bad start (a busy machine, a crashed
# driver) kept every WebGL reader blank until the add-on restarted.
_SOFTWARE_WEBGL_WORKS: bool | None = None
_SOFTWARE_WEBGL_FAILED_AT: float | None = None
SOFTWARE_WEBGL_RETRY = 3600.0


def _try_software_webgl() -> bool:
    if _SOFTWARE_WEBGL_WORKS is not False:
        return True
    return _SOFTWARE_WEBGL_FAILED_AT is not None and time.monotonic() - _SOFTWARE_WEBGL_FAILED_AT >= SOFTWARE_WEBGL_RETRY


def _driver(*extra_args: str) -> webdriver.Chrome:
    """Headless Chromium on the driver shipped in the image. Without the
    explicit service, Selenium Manager first tries to download one and fails
    on aarch64 before falling back.

    Software WebGL first; if the browser does not come up that way, once more
    without a GPU, so the readers that never needed WebGL keep working.
    """
    global _SOFTWARE_WEBGL_WORKS, _SOFTWARE_WEBGL_FAILED_AT
    if _try_software_webgl():
        started = time.monotonic()
        try:
            driver = _start(browser_arguments(*extra_args))
            _SOFTWARE_WEBGL_WORKS = True
            _LOGGER.info("textbook browser up after %.1fs (software WebGL)", time.monotonic() - started)
            return driver
        except Exception as exc:
            _SOFTWARE_WEBGL_WORKS = False
            _SOFTWARE_WEBGL_FAILED_AT = time.monotonic()
            _LOGGER.warning("textbook browser start with software WebGL failed after %.1fs: %s; "
                            "running without GPU, next try in an hour", time.monotonic() - started, type(exc).__name__)
    started = time.monotonic()
    driver = _start(browser_arguments(*extra_args, software_webgl=False))
    _LOGGER.info("textbook browser up after %.1fs (no GPU)", time.monotonic() - started)
    return driver


def _quit(driver) -> None:
    started = time.monotonic()
    try:
        driver.quit()
        _LOGGER.info("textbook browser closed after %.1fs", time.monotonic() - started)
    except Exception as exc:
        _LOGGER.warning("textbook browser close failed after %.1fs: %s", time.monotonic() - started, type(exc).__name__)


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
# Der Verlag fragt beim ersten Öffnen nach einer Einwilligung zur
# Datenübertragung. Seine Schaltflächen sind keine Bücher, und die App
# stimmt nicht an Stelle der Eltern zu: Der Dialog wird gemeldet, nicht
# weggeklickt.
_CONSENT_PHRASES = re.compile(
    r"^(Abbrechen|Weiter zur App|Welche Daten werden übertragen\??|Zustimmen|Ablehnen|Akzeptieren|"
    r"Einwilligen|Alle akzeptieren|Nur notwendige|Datenschutzerklärung)$", re.I
)
_GENERIC_PHRASES = re.compile(
    r"(digitale(?:s)? Unterrichtssystem|digitale Schulbücher und Lernkurse|"
    r"direkt in alle digitale Bildungsmedien|Eduplaces|"
    r"ausgeblendete Titel|Medium entfernen|Medienregal aktualisieren|Weiter zur App|Welche Daten werden übertragen)",
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

        def consent_dialog(records) -> bool:
            return any(_CONSENT_PHRASES.fullmatch(_clean(r.get("text") or r.get("label") or "")) for r in records)

        try:
            WebDriverWait(driver, 15).until(
                lambda d: bool(record_titles(read_records(d)))
            )
        except TimeoutException:
            if consent_dialog(read_records(driver)):
                raise TextbookScanError(
                    "Der Verlag fragt nach einer Einwilligung zur Datenübertragung. Bitte das Medienregal einmal "
                    "selbst im Browser öffnen und die Frage beantworten; danach den Regal-Scan wiederholen.")
            raise
        records = read_records(driver)
        titles = [t for t in record_titles(records) if not _CONSENT_PHRASES.fullmatch(t)]
        if not titles and consent_dialog(records):
            raise TextbookScanError(
                "Der Verlag fragt nach einer Einwilligung zur Datenübertragung. Bitte das Medienregal einmal "
                "selbst im Browser öffnen und die Frage beantworten; danach den Regal-Scan wiederholen.")
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
        _quit(driver)


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
const PAGER=/(page|pager|pagination|seite|blaettern|blättern)/i;
function inPager(e){
  let up=e;
  for(let step=0;step<3&&up;step++){
    const role=up.getAttribute('role')||'';
    const cls=typeof up.className==='string'?up.className:'';
    if(['toolbar','navigation','group'].includes(role)||PAGER.test(cls)) return true;
    up=up.parentElement;
  }
  return false;
}
function find(root){
  for(const e of root.querySelectorAll('a,button,[role="link"],[role="button"],li,td')){
    const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ');
    const labels=[own,e.getAttribute('aria-label'),e.getAttribute('title')];
    // A chapter entry reading "18" would jump somewhere else entirely.
    if(labels.some(s=>strip(s)===wanted) && e.getClientRects().length && inPager(e)) return e;
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot){const x=find(e.shadowRoot);if(x)return x;}
  return null;
} return find(document);
"""

_DISMISS_SCRIPT = r"""
// Publishers greet the reader with advertising and cookie dialogs. Their
// backdrop swallows every click on the page navigation behind it.
const CLOSE=/^(schlie(ß|ss)en|close|ok|verstanden|alle akzeptieren|akzeptieren|zustimmen)$/i;
function look(root){
  for(const d of root.querySelectorAll('[role="dialog"],[role="alertdialog"],.modal,cdk-dialog-container,mat-dialog-container')){
    if(!d.getClientRects().length) continue;
    for(const b of d.querySelectorAll('button,a,[role="button"]')){
      const own=[...b.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ');
      const names=[b.getAttribute('aria-label'),b.getAttribute('title'),own,(b.innerText||'').slice(0,40)];
      if(names.some(s=>CLOSE.test((s||'').replace(/\s+/g,' ').trim()))&&b.getClientRects().length) return b;
    }
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot){const x=look(e.shadowRoot);if(x)return x;}
  return null;
}
return look(document);
"""

_OPEN_DIALOG_SCRIPT = """
function look(root){
  for(const d of root.querySelectorAll('[role="dialog"],[role="alertdialog"],.modal,cdk-dialog-container,mat-dialog-container')){
    if(d.getClientRects().length) return true;
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot){if(look(e.shadowRoot))return true;}
  return false;
} return look(document);
"""

_ENTER_READER_SCRIPT = r"""
// Cornelsen lands on a start page; the reader is one click further in.
// Only unmistakable phrases. A bare "Öffnen", "Lesen" or "Starten" also
// sits on library tiles and account menus and led out of the book.
const ENTER=/^(zum e-?\s?book|zum buch|buch (ö|oe)ffnen|e-?\s?book (ö|oe)ffnen|jetzt lesen|weiterlesen|lesen starten)$/i;
const hits=[];
function look(root){
  for(const e of root.querySelectorAll('a,button,[role="button"],[role="link"]')){
    // A skip link named "Zum E-Book" points at the site root and throws the
    // reader away. Only a link that goes somewhere can be the entry.
    if(e.tagName==='A'){
      const href=e.getAttribute('href')||'';
      if(href===''||href==='/'||href==='#'||/^https?:\/\/[^/]+\/?$/.test(href)) continue;
    }
    const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ');
    const names=[e.getAttribute('aria-label'),e.getAttribute('title'),own,(e.innerText||'').slice(0,40)]
      .map(s=>(s||'').replace(/\s+/g,' ').trim());
    if(names.some(s=>ENTER.test(s))&&e.getClientRects().length)
      hits.push({el:e, opens:names.some(s=>/(ö|oe)ffnen|lesen/i.test(s))});
  }
  for(const e of root.querySelectorAll('*')) if(e.shadowRoot) look(e.shadowRoot);
}
look(document);
// "E-Book öffnen" beats a bare "Zum E-Book"; among equals the smallest wins,
// which is the button rather than the card around it.
let best=null, rank=[9,Infinity];
for(const hit of hits){
  const r=hit.el.getBoundingClientRect();
  const score=[hit.opens?0:1,(r.width||0)*(r.height||0)];
  if(score[0]<rank[0]||(score[0]===rank[0]&&score[1]<rank[1])){best=hit.el;rank=score;}
}
return best;
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
    // Rendered page areas carry their number as a label. A thumbnail strip
    // labels every page of the book, so only large, on-screen areas count.
    for(const marked of [e.getAttribute('aria-label'),e.getAttribute('title')]){
      const page=(marked||'').match(/(?:Seite|Page)\s+(\d{1,4})/i);
      if(!page) continue;
      const r=e.getBoundingClientRect();
      if(r.width>=innerWidth*0.15&&r.height>=innerHeight*0.3&&r.bottom>0&&r.top<innerHeight) out.push(page[1]);
      break;
    }
    if(e.shadowRoot) look(e.shadowRoot);
  }
}
look(document); return out.join('|');
"""

_PAGE_RECT_SCRIPT = r"""
// Union of the page areas actually on screen. Thumbnails carry the same
// labels, so only areas of a readable size count.
let box=null;
function grow(r){
  if(r.width<innerWidth*0.15||r.height<innerHeight*0.3) return;
  if(r.bottom<=0||r.top>=innerHeight||r.right<=0||r.left>=innerWidth) return;
  box=box?{left:Math.min(box.left,r.left),top:Math.min(box.top,r.top),
           right:Math.max(box.right,r.right),bottom:Math.max(box.bottom,r.bottom)}
         :{left:r.left,top:r.top,right:r.right,bottom:r.bottom};
}
function look(root){
  for(const e of root.querySelectorAll('*')){
    for(const marked of [e.getAttribute('aria-label'),e.getAttribute('title')]){
      if(/(?:Seite|Page)\s+\d{1,4}/i.test(marked||'')){grow(e.getBoundingClientRect());break;}
    }
    if(e.shadowRoot) look(e.shadowRoot);
  }
}
look(document);
if(!box) return null;
return {left:Math.max(0,Math.floor(box.left)),top:Math.max(0,Math.floor(box.top)),
        right:Math.min(innerWidth,Math.ceil(box.right)),bottom:Math.min(innerHeight,Math.ceil(box.bottom)),
        ratio:window.devicePixelRatio||1};
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
                break
            button.click()
            time.sleep(0.4)
        except Exception:
            break
    driver.switch_to.default_content()
    # Not every dialog offers a caption we can recognise. Escape closes the
    # well-behaved ones and costs nothing when no dialog is open.
    try:
        if _in_frames(driver, _OPEN_DIALOG_SCRIPT):
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.4)
    except Exception:
        pass
    driver.switch_to.default_content()


def _settle_reader(driver, timeout: float = 30.0) -> None:
    """Wait until the reader has booted.

    Acting while a publisher app is still loading clicked whatever happened
    to be on screen — in one case all the way back to the login page.
    """
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        driver.switch_to.default_content()
        try:
            if not driver.current_url.startswith("about:"):
                if _page_control(driver) or _in_frames(driver, _PAGE_NEIGHBOUR_SCRIPT):
                    driver.switch_to.default_content()
                    return
                driver.switch_to.default_content()
                if _shown_pages(driver):
                    return
        except Exception:
            pass
        time.sleep(1.0)
    driver.switch_to.default_content()


def _enter_reader(driver, rounds: int = 1, note: list | None = None) -> bool:
    """Follow a start page into the reader.

    Cornelsen keeps the reader in the document while still showing its
    welcome page, so the presence of a page field proves nothing: the field
    can be driven while the screenshot still shows the start page. Only the
    entry action itself decides, and its captions never appear in a reader.
    """
    entered = False
    for _ in range(rounds):
        driver.switch_to.default_content()
        before = driver.current_url
        try:
            action = _in_frames(driver, _ENTER_READER_SCRIPT)
            if action is None:
                break
            if note is not None:
                note.append({
                    "tag": action.tag_name,
                    "caption": _clean(action.text or action.get_attribute("aria-label") or "")[:60],
                    "href": _OPAQUE.sub("…", (action.get_attribute("href") or "").split("?")[0])[:120],
                    "from": _OPAQUE.sub("…", before.split("?")[0]),
                })
            action.click()
        except Exception:
            break
        try:
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass
        _dismiss_overlays(driver)
        _settle_reader(driver, timeout=20)
        driver.switch_to.default_content()
        readable = bool(_page_control(driver) or _shown_pages(driver))
        driver.switch_to.default_content()
        if not readable and driver.current_url != before:
            # The click led somewhere unusable. Go back rather than leave the
            # capture stranded on an empty route.
            try:
                driver.back()
                _settle_reader(driver, timeout=20)
            except Exception:
                pass
            if note is not None:
                note.append({"undone": True, "to": _OPAQUE.sub("…", driver.current_url.split("?")[0])})
            break
        entered = True
    driver.switch_to.default_content()
    return entered


_SET_PAGE_SCRIPT = """
const el=arguments[0], value=String(arguments[1]);
const proto=el.tagName==='INPUT'?window.HTMLInputElement.prototype:window.HTMLTextAreaElement.prototype;
const setter=Object.getOwnPropertyDescriptor(proto,'value');
if(setter&&setter.set) setter.set.call(el,value); else el.value=value;
el.dispatchEvent(new Event('input',{bubbles:true}));
el.dispatchEvent(new Event('change',{bubbles:true}));
for(const type of ['keydown','keypress','keyup'])
  el.dispatchEvent(new KeyboardEvent(type,{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
// Some readers only commit the number once the field loses focus.
el.dispatchEvent(new Event('blur',{bubbles:false}));
el.dispatchEvent(new Event('focusout',{bubbles:true}));
if(el.blur) el.blur();
"""


def _type_page(driver, control, page: int) -> bool:
    """Put a page number into a viewer's field, whatever it takes to stick."""
    try:
        control.click()
        control.send_keys(Keys.CONTROL, "a")
        control.send_keys(str(page), Keys.ENTER)
        if _wait_for_page(driver, page):
            return True
        # Enter alone is not always the commit; leaving the field can be.
        control.send_keys(Keys.TAB)
        if _wait_for_page(driver, page, timeout=6):
            return True
    except Exception:
        # A dialog caught the click. Clear what we can and carry on below.
        _dismiss_overlays(driver)
    try:
        # Setting the value on the field itself reaches readers that ignore
        # synthetic typing, and no overlay can swallow it.
        driver.execute_script(_SET_PAGE_SCRIPT, control, page)
    except Exception:
        return False
    return _wait_for_page(driver, page, timeout=10)


def _field_goto(driver, page: int) -> bool | None:
    control = _page_control(driver)
    if control is None:
        return None
    return _type_page(driver, control, page)


def _neighbour_goto(driver, page: int) -> bool | None:
    control = _in_frames(driver, _PAGE_NEIGHBOUR_SCRIPT)
    if control is None:
        return None
    return _type_page(driver, control, page)


def _select_goto(driver, page: int) -> bool | None:
    control = _in_frames(driver, _PAGE_SELECT_SCRIPT, str(page))
    if control is None:
        return None
    for option in Select(control).options:
        if re.sub(r"^(S\.?|Seite|Page)\s*", "", (option.text or "").strip(), flags=re.I) == str(page):
            option.click()
            return _wait_for_page(driver, page)
    return False


def _button_goto(driver, page: int) -> bool | None:
    control = _in_frames(driver, _PAGE_BUTTON_SCRIPT, str(page))
    if control is None:
        return None
    control.click()
    # Only count it when the viewer confirms the page; a bare click could just
    # as well have opened a chapter, and a wrong page is worse than none.
    return _wait_for_page(driver, page)


def _url_goto(driver, page: int) -> bool | None:
    driver.switch_to.default_content()
    url = driver.current_url
    target = _PAGE_IN_URL.sub(lambda m: m.group(1) + str(page), url, count=1)
    if target == url:
        return None
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
    return _wait_for_page(driver, page, timeout=30)


def _go_to_page(driver, page: int, trace: list | None = None) -> bool:
    """Try every known way to reach a page, recording what each one did."""
    _settle_reader(driver, timeout=20)
    driver.switch_to.default_content()
    shown = _shown_pages(driver)
    if page in shown:
        if trace is not None:
            trace.append({"page": page, "strategy": "bereits offen", "confirmed": True, "shown": shown})
        return True
    _dismiss_overlays(driver)
    for strategy in (_field_goto, _neighbour_goto, _select_goto, _button_goto, _url_goto):
        driver.switch_to.default_content()
        name = getattr(strategy, "__name__", "unbekannt")
        step = {"page": page, "strategy": name.strip("_").replace("_goto", "")}
        outcome = None
        try:
            outcome = strategy(driver, page)
        except Exception as exc:
            step["error"] = type(exc).__name__
        step["found"] = outcome is not None
        step["confirmed"] = outcome is True
        if trace is not None:
            try:
                step["shown"] = _shown_pages(driver)
                step["url"] = _OPAQUE.sub("…", driver.current_url.split("?")[0])
            except Exception:
                pass
            trace.append(step)
        if step["confirmed"]:
            return True
    return False


def _crop(blob: bytes, rect: dict) -> bytes:
    from PIL import Image

    ratio = rect.get("ratio") or 1
    box = tuple(int(rect[key] * ratio) for key in ("left", "top", "right", "bottom"))
    image = Image.open(io.BytesIO(blob))
    box = (max(0, box[0]), max(0, box[1]), min(image.width, box[2]), min(image.height, box[3]))
    if box[2] - box[0] < 80 or box[3] - box[1] < 80:
        return blob
    out = io.BytesIO()
    image.crop(box).save(out, "PNG")
    return out.getvalue()


def _viewer_shot(driver) -> bytes:
    """The book pages alone if the viewer marks them, otherwise the window."""
    driver.switch_to.default_content()
    try:
        rect = driver.execute_script(_PAGE_RECT_SCRIPT)
        if rect:
            return _crop(driver.get_screenshot_as_png(), rect)
    except Exception:
        pass
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
      text:(TEXTY.has(e.tagName)||ROLES.includes(role))?(cut(own,40)||cut(e.innerText,40)):'',
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


_PAGE_AREA_DIAG_SCRIPT = r"""
// What sits inside the areas a reader labels as pages. A BiBox reader kept
// "Seite 18" and "Seite 19" in the document with no size at all, so the
// geometry and the children tell whether content was ever drawn.
const out=[];
const short=s=>(s||'').replace(/[A-Za-z0-9_-]{24,}/g,'…').slice(0,120);
function look(root){
  for(const e of root.querySelectorAll('*')){
    if(out.length>=8) return;
    const marked=(e.getAttribute('aria-label')||e.getAttribute('title')||'');
    if(/^(Seite|Page)\s+\d{1,4}$/i.test(marked.trim())){
      const r=e.getBoundingClientRect();
      const kids=[];
      for(const k of e.querySelectorAll('img,canvas,svg,iframe,object,video,picture')){
        if(kids.length>=6) break;
        const kr=k.getBoundingClientRect();
        const item={tag:k.tagName.toLowerCase(),w:Math.round(kr.width),h:Math.round(kr.height)};
        if(k.tagName==='IMG'){item.complete=k.complete;item.natural=k.naturalWidth+'x'+k.naturalHeight;
          try{item.src=short(new URL(k.currentSrc||k.src||'',location.href).pathname);}catch(_){}}
        if(k.tagName==='CANVAS'){item.canvas=k.width+'x'+k.height;}
        kids.push(item);
      }
      const style=getComputedStyle(e);
      out.push({label:marked.trim(),tag:e.tagName.toLowerCase(),w:Math.round(r.width),h:Math.round(r.height),
        top:Math.round(r.top),left:Math.round(r.left),children:e.children.length,descendants:e.querySelectorAll('*').length,
        text:(e.innerText||'').replace(/\s+/g,' ').trim().length,display:style.display,visibility:style.visibility,
        opacity:style.opacity,media:kids});
    }
    if(e.shadowRoot) look(e.shadowRoot);
  }
}
look(document); return out;
"""

_RESOURCE_DIAG_SCRIPT = r"""
// Requests the reader made and what became of them. responseStatus is 0 for
// blocked and cross-origin-opaque answers, which is a finding in itself.
const short=s=>(s||'').replace(/[A-Za-z0-9_-]{24,}/g,'…');
const entries=performance.getEntriesByType('resource');
const failed=[];const kinds={};
for(const e of entries){
  kinds[e.initiatorType]=(kinds[e.initiatorType]||0)+1;
  const status=('responseStatus' in e)?e.responseStatus:null;
  const empty=e.transferSize===0&&e.decodedBodySize===0;
  if((status!==null&&status>=400)||(status===0&&empty)){
    if(failed.length>=25) continue;
    let path='';try{const u=new URL(e.name);path=u.host+short(u.pathname).slice(0,100);}catch(_){path=short(e.name).slice(0,100);}
    failed.push({url:path,status:status,type:e.initiatorType,ms:Math.round(e.duration)});
  }
}
let webgl=false,webgl2=false;
try{const c=document.createElement('canvas');webgl=!!(c.getContext('webgl')||c.getContext('experimental-webgl'));webgl2=!!c.getContext('webgl2');}catch(_){}
return {total:entries.length,kinds:kinds,failed:failed,webgl:webgl,webgl2:webgl2,
  viewport:innerWidth+'x'+innerHeight,ratio:devicePixelRatio,visibility:document.visibilityState,
  canvases:document.querySelectorAll('canvas').length,images:document.images.length,
  worker:'serviceWorker' in navigator?(navigator.serviceWorker.controller?'active':'none'):'unsupported'};
"""


def looks_blank(blob: bytes, threshold: float = 0.04) -> bool:
    """Is there anything on this image apart from the background?

    A BiBox reader reported `loaded` and delivered an empty shell: toolbar,
    icons, page counter, no book. Measured on real captures: the empty shell
    has about 1 % of its pixels off the background colour, a book page 30 %,
    a window with a book in it 10 %.
    """
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(blob)).convert("L")
        image.thumbnail((240, 240))
        pixels = list(image.getdata())
    except Exception:
        return False
    if not pixels:
        return True
    ordered = sorted(pixels)
    median = ordered[len(ordered) // 2]
    busy = sum(1 for value in pixels if abs(value - median) > 24)
    return busy / len(pixels) < threshold


def _console(driver) -> list[dict]:
    """Console warnings and errors, tokens cut out, oldest first."""
    try:
        lines = driver.get_log("browser")
    except Exception:
        return []
    kept = []
    for line in lines:
        level = str(line.get("level") or "")
        if level not in ("SEVERE", "WARNING"):
            continue
        kept.append({"level": level, "text": _OPAQUE.sub("…", str(line.get("message") or ""))[:240]})
    return kept[-30:]


def _diagnostics(driver) -> dict:
    """Why a reader shows what it shows: page areas, failed requests, console."""
    found: dict = {}
    driver.switch_to.default_content()
    try:
        found.update(driver.execute_script(_RESOURCE_DIAG_SCRIPT) or {})
    except Exception as exc:
        found["resources_error"] = type(exc).__name__
    try:
        found["page_areas"] = _in_frames(driver, _PAGE_AREA_DIAG_SCRIPT) or []
    except Exception as exc:
        found["page_areas_error"] = type(exc).__name__
    driver.switch_to.default_content()
    found["console"] = _console(driver)
    return found


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
    attempts: list[dict] = field(default_factory=list)
    entry: list[dict] = field(default_factory=list)
    window_image: bytes | None = None
    diagnostics: dict = field(default_factory=dict)


def _wait_for_content(driver, shot: bytes, timeout: float = 15.0, pause: float = 3.0) -> tuple[bytes, dict]:
    """Give a reader that drew nothing yet more time, and say what happened."""
    report = {"blank_first": looks_blank(shot), "waited": 0.0}
    if not report["blank_first"]:
        return shot, report
    end = time.monotonic() + timeout
    started = time.monotonic()
    while time.monotonic() < end:
        time.sleep(pause)
        again = _viewer_shot(driver)
        if not looks_blank(again):
            shot = again
            break
    report["waited"] = round(time.monotonic() - started, 1)
    report["blank_after_wait"] = looks_blank(shot)
    return shot, report


def _open_shelf(driver, portal_url: str, rounds: int = 3) -> bool:
    """From the IServ connector page into the Bildungslogin shelf.

    The connector draws its tiles after the document reports complete. Two
    of three Politik fetches failed here with "Medienregal nicht gefunden"
    while the next one sailed through, so the tile is given time and the page
    a second load before giving up.
    """
    for attempt in range(rounds):
        driver.get(portal_url.rstrip("/") + "/iserv/eduplacesconnector/")
        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass
        end = time.monotonic() + 8.0
        while True:
            if _click(driver, re.compile("Bildungslogin.*Medienregal|Medienregal", re.I)):
                try:
                    WebDriverWait(driver, 20).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except TimeoutException:
                    pass
                return True
            if time.monotonic() >= end:
                break
            time.sleep(1.0)
        if attempt + 1 < rounds:
            time.sleep(2.0)
    return False


def _attach_survey(exc: TextbookScanError, driver, stage: str) -> None:
    """Even a failed run should show the parents where it stopped."""
    try:
        seen = _survey(driver)
        driver.switch_to.default_content()
        exc.survey = CaptureResult(  # type: ignore[attr-defined]
            controls=seen["controls"], documents=seen["documents"],
            window_image=driver.get_screenshot_as_png(),
            diagnostics={"stage": stage, **_diagnostics(driver)},
        )
    except Exception:
        pass


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
    # Gerätefaktor 2: Eine Doppelseite hat sonst rund 650 Pixel je Seite und
    # ist im Bestand unscharf. Die Seitenbereiche werden mit dem Faktor
    # zugeschnitten, das Bild ist also doppelt so fein bei gleichem Fenster.
    # Ein großes Fenster statt eines Gerätefaktors: Der Faktor kam weder über
    # das Flag noch über DevTools im Screenshot an (gemessen: 1308 Pixel je
    # Doppelseite). Im doppelt so großen Fenster zeichnet der Betrachter die
    # Seiten selbst größer; 2600 Pixel Fensterbreite brachten 1970 Pixel je
    # Doppelseite, 3000 bringen rund 2300.
    driver = _driver("--window-size=3000,2100")
    deadline = time.monotonic() + budget
    stage = "IServ-Anmeldung"
    try:
        driver.get(portal_url.rstrip("/") + "/iserv/")
        driver.find_element(By.NAME, "_username").send_keys(username)
        driver.find_element(By.NAME, "_password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        WebDriverWait(driver, 15).until(lambda d: "/auth/login" not in d.current_url)
        stage = "Eduplaces öffnen"
        if not _open_shelf(driver, portal_url):
            raise TextbookScanError("Das Medienregal wurde nicht gefunden", stage)
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
        _settle_reader(driver)
        _dismiss_overlays(driver)
        entry: list[dict] = []
        _enter_reader(driver, note=entry)
        stage = "Seitennavigation finden"
        shots: list[PageShot] = []
        note = ""
        content: dict = {}
        trace: list[dict] | None = [] if survey else None
        for page in pages:
            if time.monotonic() > deadline:
                note = "Zeitbudget erreicht"
                break
            if not _go_to_page(driver, page, trace):
                continue
            stage = f"Seite {page} lesen"
            image = _stable_shot(driver)
            if looks_blank(image):
                # A WebGL reader draws after the page number has changed, and
                # an empty screen is "stable" at once. Give it time before
                # believing it, and remember what came of it.
                image, content = _wait_for_content(driver, image)
            shots.append(PageShot(page, image))
        if not shots:
            # The book is open. Hand over what it shows rather than nothing;
            # the mentor is told that the page could not be confirmed.
            note = note or "Seitennavigation nicht gefunden"
            driver.switch_to.default_content()
            shots.append(PageShot(None, _stable_shot(driver)))
        elif len(shots) < len(pages) and not note:
            note = "Nicht alle Seiten erreichbar"
        result = CaptureResult(shots=shots, note=note, attempts=trace or [], entry=entry)
        _LOGGER.info("textbook capture done: %s of %s pages after %.0fs%s", sum(1 for s in shots if s.page is not None),
                     len(pages), time.monotonic() - (deadline - budget), f" ({note})" if note else "")
        if survey:
            seen = _survey(driver)
            result.controls = seen["controls"]
            result.documents = seen["documents"]
            driver.switch_to.default_content()
            result.window_image = driver.get_screenshot_as_png()
            result.diagnostics = {**content, **_diagnostics(driver)}
        return result
    except TextbookScanError as exc:
        if survey:
            _attach_survey(exc, driver, stage)
        raise
    except Exception as exc:
        wrapped = TextbookScanError(
            f"Die angegebenen Buchseiten konnten nicht geöffnet werden ({stage})", stage
        )
        if survey:
            _attach_survey(wrapped, driver, stage)
        raise wrapped from exc
    finally:
        _quit(driver)


async def capture_pages(
    portal_url: str,
    username: str,
    password: str,
    title: str,
    pages: list[int],
    launch_url: str | None = None,
    survey: bool = False,
    budget: float = 240.0,
) -> CaptureResult:
    return await asyncio.to_thread(
        _capture_pages_sync, portal_url, username, password, title, pages, launch_url, survey, budget
    )


# --- Browser probe -----------------------------------------------------------
# Starts Chromium itself, without Selenium, on a page that reports whether
# WebGL exists, and keeps its stderr: that is where Chromium says why a GPU
# process does not come up. Used by the parent-facing browser check only.

_PROBE_PAGE = """<!doctype html><body><script>
const c=document.createElement("canvas");
const g=c.getContext("webgl")||c.getContext("experimental-webgl");const g2=c.getContext("webgl2");
let r="";try{const d=g&&g.getExtension("WEBGL_debug_renderer_info");r=g&&d?g.getParameter(d.UNMASKED_RENDERER_WEBGL):""}catch(e){}
document.body.textContent="RESULT webgl="+!!g+" webgl2="+!!g2+" renderer="+r;
</script></body>"""

# Alpine's Chromium has no SwiftShader driver (no libvk_swiftshader.so), so
# the "swiftshader" ANGLE backend cannot initialise. The image therefore
# carries Mesa: Lavapipe as a software Vulkan driver, llvmpipe for GL.
PROBE_VARIANTS: dict[str, list[str]] = {
    "ohne GPU": ["--disable-gpu"],
    "ANGLE auf Vulkan (Lavapipe)": ["--use-gl=angle", "--use-angle=vulkan", "--ignore-gpu-blocklist"],
    "ANGLE auf Vulkan mit Vulkan-Compositing": ["--use-gl=angle", "--use-angle=vulkan", "--ignore-gpu-blocklist",
                                               "--enable-features=Vulkan"],
    "ANGLE auf GL (llvmpipe)": ["--use-gl=angle", "--use-angle=gl", "--ignore-gpu-blocklist"],
    "natives EGL": ["--use-gl=egl", "--ignore-gpu-blocklist"],
    "SwiftShader": ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
}


def probe_browser(seconds: float = 40.0) -> dict:
    """Run every variant once, with a hard time limit, and report what
    Chromium printed. Nothing here touches a portal or a credential."""
    import glob
    import subprocess
    import tempfile

    report: dict = {"binary": _CHROMIUM, "variants": []}
    try:
        report["version"] = subprocess.run([_CHROMIUM, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as exc:
        report["version"] = type(exc).__name__
    report["gl_libraries"] = sorted(os.path.basename(p) for p in glob.glob("/usr/lib/chromium/*.so*")
                                    if re.search(r"(swiftshader|EGL|GLES|vulkan|angle)", p, re.I))
    report["vulkan_drivers"] = sorted(os.path.basename(p) for p in glob.glob("/usr/share/vulkan/icd.d/*.json"))
    report["dri_drivers"] = sorted(os.path.basename(p) for p in glob.glob("/usr/lib/dri/*.so"))
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as handle:
        handle.write(_PROBE_PAGE)
        page = handle.name
    try:
        for name, flags in PROBE_VARIANTS.items():
            entry: dict = {"variant": name, "flags": flags}
            started = time.monotonic()
            try:
                done = subprocess.run(
                    [_CHROMIUM, "--headless", "--no-sandbox", "--disable-dev-shm-usage", *flags,
                     "--dump-dom", f"file://{page}"],
                    capture_output=True, text=True, timeout=seconds)
                entry["returncode"] = done.returncode
                found = re.search(r"RESULT [^<\n]*", done.stdout or "")
                entry["result"] = found.group(0) if found else "kein Ergebnis"
                lines = [_OPAQUE.sub("…", line.strip())[:220] for line in (done.stderr or "").splitlines() if line.strip()]
                entry["stderr"] = lines[-25:]
            except subprocess.TimeoutExpired as exc:
                entry["result"] = "Zeitlimit"
                lines = [_OPAQUE.sub("…", line.strip())[:220] for line in ((exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")).splitlines() if line.strip()]
                entry["stderr"] = lines[-25:]
            except Exception as exc:
                entry["result"] = type(exc).__name__
            entry["seconds"] = round(time.monotonic() - started, 1)
            report["variants"].append(entry)
    finally:
        try:
            os.unlink(page)
        except OSError:
            pass
    return report
