import subprocess
from unittest.mock import Mock

import pytest
from selenium.common.exceptions import StaleElementReferenceException

from backend import textbook_browser as browser


def test_book_target_shadow_card_and_original_title():
    script = '''
const assert = require('node:assert/strict');
function element(text='', attrs={}) {
  return {childNodes:[{nodeType:3,textContent:text}],
    getAttribute:k=>attrs[k]||null, getClientRects:()=>[{}],
    matches:()=>false, getRootNode:()=>({}), parentElement:null};
}
const wrong=element('Medium entfernen');
const title=element('Politik & Co. Niedersachsen 8');
const host=element(); host.matches=()=>true;
host.shadowRoot={querySelectorAll:()=>[title]};
title.getRootNode=()=>({host});
global.document={querySelectorAll:()=>[wrong,host]};
const locate=new Function(process.argv[1]);
assert.equal(locate('POLITIK & CO.  Niedersachsen 8'),host);
assert.equal(locate('Politik'),null);
host.matches=()=>false;
assert.equal(locate('Politik & Co. Niedersachsen 8'),title);
'''
    subprocess.run(['node', '-e', script, browser._BOOK_TARGET_SCRIPT], check=True)


def test_book_in_frame_restores_parent():
    driver = Mock()
    target = Mock()
    driver.execute_script.side_effect = [None, target]
    driver.find_elements.return_value = ['frame']
    assert browser._find_and_click_in_frames(driver, 'Originaltitel')
    target.click.assert_called_once()
    driver.switch_to.frame.assert_called_once_with('frame')
    driver.switch_to.parent_frame.assert_called_once()


def test_open_waits_for_late_card(monkeypatch):
    locate = Mock(side_effect=[False, True])
    monkeypatch.setattr(browser, '_find_and_click_in_frames', locate)
    driver = Mock()
    browser._open_book(driver, 'Originaltitel')
    assert locate.call_count == 2
    assert driver.switch_to.default_content.call_count == 2


def test_missing_card_reports_safe_error(monkeypatch):
    wait = Mock()
    wait.until.side_effect = browser.TimeoutException('private browser details')
    monkeypatch.setattr(browser, 'WebDriverWait', Mock(return_value=wait))
    with pytest.raises(browser.TextbookScanError, match='im Regal nicht gefunden') as error:
        browser._open_book(Mock(), 'Originaltitel')
    assert 'private' not in str(error.value)


def test_loose_title_match_keeps_a_bare_subject_out():
    script = '''
const assert = require('node:assert/strict');
function element(text='', attrs={}) {
  return {childNodes:[{nodeType:3,textContent:text}],
    getAttribute:k=>attrs[k]||null, getClientRects:()=>[{}],
    matches:()=>false, getRootNode:()=>({}), parentElement:null};
}
const shelf=element('Politik & Co. Niedersachsen 8 – BiBox');
global.document={querySelectorAll:()=>[shelf]};
const locate=new Function(process.argv[1]);
// A stored full title still matches when the shelf appends a product suffix.
assert.equal(locate('Politik & Co. Niedersachsen 8'),shelf);
// A bare subject stays too short to match anything loosely.
assert.equal(locate('Politik'),null);
'''
    subprocess.run(['node', '-e', script, browser._BOOK_TARGET_SCRIPT], check=True)


def test_shown_page_numbers_separate_spread_from_total():
    # "30 / 210" is page 30 of 210; "30-31" is one open double page.
    assert browser.shown_page_numbers('30 / 210') == [30]
    assert browser.shown_page_numbers('30-31') == [30, 31]
    assert browser.shown_page_numbers('| 12 |') == [12]
    assert browser.shown_page_numbers('', 'https://viewer.example/buch#/page/34') == [34]
    assert browser.shown_page_numbers('') == []


def test_page_navigation_tries_the_next_way_when_one_fails(monkeypatch):
    monkeypatch.setattr(browser, '_settle_reader', lambda d, **k: None)
    monkeypatch.setattr(browser, '_shown_pages', lambda d: [])
    monkeypatch.setattr(browser, '_field_goto', Mock(return_value=False))
    monkeypatch.setattr(browser, '_select_goto', Mock(side_effect=RuntimeError('kaputt')))
    button = Mock(return_value=True)
    monkeypatch.setattr(browser, '_button_goto', button)
    url = Mock(return_value=True)
    monkeypatch.setattr(browser, '_url_goto', url)
    assert browser._go_to_page(Mock(), 34) is True
    button.assert_called_once()
    url.assert_not_called()


def test_page_already_open_needs_no_navigation(monkeypatch):
    monkeypatch.setattr(browser, '_settle_reader', lambda d, **k: None)
    monkeypatch.setattr(browser, '_shown_pages', lambda d: [30, 31])
    field = Mock(return_value=True)
    monkeypatch.setattr(browser, '_field_goto', field)
    assert browser._go_to_page(Mock(), 31) is True
    field.assert_not_called()


def test_page_wait_survives_a_rerendered_control(monkeypatch):
    # The viewer replaces its controls on every page change; reading a kept
    # handle would raise instead of reporting the new page.
    answers = [StaleElementReferenceException('weg'), [34]]

    def shown(_driver):
        value = answers.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(browser, '_shown_pages', shown)
    monkeypatch.setattr(browser.time, 'sleep', lambda _s: None)
    assert browser._wait_for_page(Mock(), 34) is True


def test_open_book_falls_back_to_the_stored_launch_address(monkeypatch):
    wait = Mock()
    wait.until.side_effect = [browser.TimeoutException('nicht gefunden'), True]
    monkeypatch.setattr(browser, 'WebDriverWait', Mock(return_value=wait))
    driver = Mock()
    browser._open_book(driver, 'Originaltitel', 'https://viewer.example/buch/42')
    driver.get.assert_called_once_with('https://viewer.example/buch/42')


def test_missing_card_without_launch_address_names_the_stage(monkeypatch):
    wait = Mock()
    wait.until.side_effect = browser.TimeoutException('private browser details')
    monkeypatch.setattr(browser, 'WebDriverWait', Mock(return_value=wait))
    with pytest.raises(browser.TextbookScanError) as error:
        browser._open_book(Mock(), 'Originaltitel')
    assert error.value.stage == 'Buch öffnen'
    assert 'private' not in str(error.value)


def test_page_field_is_found_by_id_when_the_viewer_labels_nothing():
    # click & study renders <input type="text" id="selectPage"> with no
    # label, title or placeholder. The search box next to it must not win.
    script = '''
const assert = require('node:assert/strict');
function input(attrs) {
  return {getAttribute: k => (k in attrs ? attrs[k] : null),
    placeholder: attrs.placeholder || '', type: attrs.type || 'text',
    id: attrs.id || '', className: attrs.className || '',
    querySelectorAll: () => []};
}
const search = input({id:'searchInput', className:'form-control', placeholder:'Suchbegriff...'});
const pageField = input({id:'selectPage', className:'form-control'});
global.document = {querySelectorAll: sel => (sel.indexOf('input') === 0 ? [search, pageField] : [])};
const find = new Function(process.argv[1]);
assert.equal(find(), pageField);
global.document = {querySelectorAll: sel => (sel.indexOf('input') === 0 ? [search] : [])};
assert.equal(new Function(process.argv[1])(), null);
'''
    subprocess.run(['node', '-e', script, browser._PAGE_FIELD_SCRIPT], check=True)


def test_shown_page_reads_a_field_named_only_by_id():
    script = '''
const assert = require('node:assert/strict');
function input(attrs) {
  return {getAttribute: k => (k in attrs ? attrs[k] : null),
    placeholder: '', type: 'text', tagName: 'INPUT',
    id: attrs.id || '', className: '', value: attrs.value || '',
    childNodes: [], shadowRoot: null,
    querySelectorAll: () => []};
}
const pageField = input({id:'selectPage', value:'34'});
global.document = {querySelectorAll: sel => (sel.indexOf('input') === 0 ? [pageField] : [])};
assert.equal(new Function(process.argv[1])(), '34');
'''
    subprocess.run(['node', '-e', script, browser._SHOWN_PAGE_SCRIPT], check=True)


def test_page_field_found_next_to_labelled_blättern_buttons():
    # Cornelsen names the field with a generated React id and hashed classes,
    # so only the neighbouring buttons identify it.
    script = '''
const assert = require('node:assert/strict');
function make(tag, attrs, children) {
  const e = {tagName: tag, getAttribute: k => (k in attrs ? attrs[k] : null),
    id: attrs.id || '', className: attrs.className || '', placeholder: attrs.placeholder || '',
    getClientRects: () => [{}], parentElement: null, shadowRoot: null, childNodes: [],
    _children: children || []};
  e.querySelectorAll = sel => e._children.filter(c =>
    sel.indexOf('input') >= 0 ? c.tagName === 'input' : true);
  (children || []).forEach(c => { c.parentElement = e; });
  return e;
}
const search = make('input', {id: 'searchBox', type: 'text', placeholder: 'Suche'});
const pageField = make('input', {id: 'react-aria1:r3d:', type: 'text'});
const next = make('div', {role: 'button', 'aria-label': 'Nächste Seite'});
const toolbar = make('div', {}, [search, pageField, next]);
next.parentElement = toolbar;
global.document = {querySelectorAll: sel =>
  (sel.indexOf('input') === 0 ? [] : [toolbar, search, pageField, next])};
const found = new Function(process.argv[1])();
assert.equal(found, pageField);
'''
    subprocess.run(['node', '-e', script, browser._PAGE_NEIGHBOUR_SCRIPT], check=True)


def test_shown_page_reads_the_label_of_a_rendered_page():
    script = '''
const assert = require('node:assert/strict');
global.innerWidth = 1440; global.innerHeight = 1000;
function marked(label) {
  return {tagName: 'SECTION', getAttribute: k => (k === 'aria-label' ? label : null),
    id: '', className: '', childNodes: [], shadowRoot: null, value: '',
    getBoundingClientRect: () => ({width: 600, height: 900, top: 20, bottom: 920}),
    querySelectorAll: () => []};
}
const left = marked('Seite 12'), right = marked('Seite 13');
global.document = {querySelectorAll: sel =>
  (sel === '*' ? [left, right] : [])};
const shown = new Function(process.argv[1])();
assert.equal(shown, '12|13');
'''
    subprocess.run(['node', '-e', script, browser._SHOWN_PAGE_SCRIPT], check=True)


def test_advertising_dialog_is_closed_before_navigating(monkeypatch):
    closed = Mock()
    found = [closed, None]
    monkeypatch.setattr(browser, '_in_frames', Mock(side_effect=lambda d, s, *a: found.pop(0)))
    monkeypatch.setattr(browser.time, 'sleep', lambda _s: None)
    browser._dismiss_overlays(Mock())
    closed.click.assert_called_once()


def test_navigation_tries_the_neighbour_field_after_the_named_one(monkeypatch):
    monkeypatch.setattr(browser, '_settle_reader', lambda d, **k: None)
    monkeypatch.setattr(browser, '_shown_pages', lambda d: [])
    monkeypatch.setattr(browser, '_dismiss_overlays', lambda d, **k: None)
    monkeypatch.setattr(browser, '_field_goto', Mock(return_value=False))
    neighbour = Mock(return_value=True)
    monkeypatch.setattr(browser, '_neighbour_goto', neighbour)
    select = Mock(return_value=True)
    monkeypatch.setattr(browser, '_select_goto', select)
    assert browser._go_to_page(Mock(), 18) is True
    neighbour.assert_called_once()
    select.assert_not_called()


def test_thumbnail_strip_does_not_count_as_the_shown_page():
    # PSPDFKit labels every page, including the small previews. Only the
    # large page actually on screen may confirm a jump.
    script = '''
const assert = require('node:assert/strict');
global.innerWidth = 1440; global.innerHeight = 1000;
function area(label, rect) {
  return {tagName: 'SECTION', getAttribute: k => (k === 'aria-label' ? label : null),
    id: '', className: '', childNodes: [], shadowRoot: null, value: '',
    getBoundingClientRect: () => rect, querySelectorAll: () => []};
}
const shown = area('Seite 18', {width: 700, height: 900, top: 20, bottom: 920});
const thumb = area('Seite 4', {width: 90, height: 120, top: 40, bottom: 160});
const offscreen = area('Seite 99', {width: 700, height: 900, top: 2000, bottom: 2900});
global.document = {querySelectorAll: sel => (sel === '*' ? [shown, thumb, offscreen] : [])};
assert.equal(new Function(process.argv[1])(), '18');
'''
    subprocess.run(['node', '-e', script, browser._SHOWN_PAGE_SCRIPT], check=True)


def entering(monkeypatch, action, readable):
    action.tag_name = 'a'
    action.text = 'E-Book öffnen'
    action.get_attribute.return_value = 'https://viewer.example/reader'
    monkeypatch.setattr(browser, '_in_frames', Mock(return_value=action))
    monkeypatch.setattr(browser, '_dismiss_overlays', lambda d, **k: None)
    monkeypatch.setattr(browser, '_settle_reader', lambda d, **k: None)
    monkeypatch.setattr(browser, '_page_control', Mock(return_value=readable))
    monkeypatch.setattr(browser, '_shown_pages', Mock(return_value=[]))
    monkeypatch.setattr(browser, 'WebDriverWait', Mock(return_value=Mock()))


def test_start_page_is_followed_into_the_reader(monkeypatch):
    action = Mock()
    entering(monkeypatch, action, readable=Mock())
    driver = Mock()
    driver.current_url = 'https://viewer.example/start'
    note = []
    assert browser._enter_reader(driver, note=note) is True
    action.click.assert_called_once()
    assert note and note[0]['caption']


def test_reader_entry_happens_even_when_a_page_field_exists(monkeypatch):
    # Cornelsen keeps the reader in the document behind its welcome page, so
    # a findable page field must not suppress the entry click.
    action = Mock()
    entering(monkeypatch, action, readable=Mock())
    driver = Mock()
    driver.current_url = 'https://viewer.example/start'
    assert browser._enter_reader(driver) is True
    action.click.assert_called_once()


def test_an_entry_click_that_leads_nowhere_is_undone(monkeypatch):
    action = Mock()
    entering(monkeypatch, action, readable=None)
    driver = Mock()
    type(driver).current_url = property(lambda self: urls.pop(0))
    urls = ['https://viewer.example/start', 'https://viewer.example/', 'https://viewer.example/', 'https://viewer.example/start']
    note = []
    assert browser._enter_reader(driver, note=note) is False
    driver.back.assert_called_once()
    assert note[-1]['undone'] is True


def test_reader_entry_stops_when_no_entry_action_is_present(monkeypatch):
    monkeypatch.setattr(browser, '_in_frames', Mock(return_value=None))
    driver = Mock()
    driver.current_url = 'https://viewer.example/start'
    assert browser._enter_reader(driver) is False


def test_blocked_click_falls_back_to_driving_the_field(monkeypatch):
    cleared = Mock()
    monkeypatch.setattr(browser, '_dismiss_overlays', cleared)
    monkeypatch.setattr(browser, '_wait_for_page', lambda d, p, **k: True)
    driver = Mock()
    control = Mock()
    control.click.side_effect = browser.TimeoutException('abgefangen')
    assert browser._type_page(driver, control, 18) is True
    cleared.assert_called_once()
    # The overlay cannot swallow a value set on the field itself.
    driver.execute_script.assert_called_once_with(browser._SET_PAGE_SCRIPT, control, 18)


def test_dialog_caption_inside_a_nested_span_is_recognised():
    script = '''
const assert = require('node:assert/strict');
function button(inner) {
  return {childNodes: [], getAttribute: () => null, innerText: inner,
    getClientRects: () => [{}], querySelectorAll: () => []};
}
const close = button('Verstanden');
const dialog = {getClientRects: () => [{}], querySelectorAll: () => [close]};
global.document = {querySelectorAll: sel => (sel === '*' ? [] : [dialog])};
assert.equal(new Function(process.argv[1])(), close);
'''
    subprocess.run(['node', '-e', script, browser._DISMISS_SCRIPT], check=True)


def test_settle_waits_while_the_reader_is_still_blank(monkeypatch):
    driver = Mock()
    type(driver).current_url = property(lambda self: urls.pop(0))
    urls = ['about:blank', 'https://viewer.example/book/1', 'https://viewer.example/book/1']
    monkeypatch.setattr(browser, '_page_control', Mock(side_effect=[None, Mock()]))
    monkeypatch.setattr(browser, '_in_frames', Mock(return_value=None))
    monkeypatch.setattr(browser, '_shown_pages', Mock(return_value=[]))
    monkeypatch.setattr(browser.time, 'sleep', lambda _s: None)
    browser._settle_reader(driver, timeout=5)
    # about:blank is not mistaken for a loaded reader.
    assert browser._page_control.call_count == 2


def test_generic_open_captions_no_longer_enter_the_reader():
    script = '''
const assert = require('node:assert/strict');
function link(text, size, href) {
  return {tagName: 'A', childNodes: [{nodeType: 3, textContent: text}],
    getAttribute: k => (k === 'href' ? (href === undefined ? '/reader/1' : href) : null),
    getClientRects: () => [{}], querySelectorAll: () => [],
    getBoundingClientRect: () => ({width: size || 200, height: 40}),
    shadowRoot: null, innerText: text, _text: text};
}
function run(items) {
  global.document = {querySelectorAll: sel => (sel === '*' ? [] : items)};
  return new Function(process.argv[1])();
}
// A library tile or account menu entry must not be treated as the reader.
assert.equal(run([link('Öffnen')]), null);
assert.equal(run([link('Starten')]), null);
assert.equal(run([link('Lesen')]), null);
const real = link('Zum E-Book');
assert.equal(run([real]), real);
// Of a card and the button inside it, the button wins.
const card = link('E-Book öffnen', 900), button = link('E-Book öffnen', 220);
assert.equal(run([card, button]), button);
// A skip link pointing at the site root is never the entry, even though it
// is the smaller element and matches the caption.
const skip = link('Zum E-Book', 60, 'https://ebook.example/');
assert.equal(run([skip]), null);
const opens = link('E-Book öffnen', 400);
assert.equal(run([skip, opens]), opens);
'''
    subprocess.run(['node', '-e', script, browser._ENTER_READER_SCRIPT], check=True)
