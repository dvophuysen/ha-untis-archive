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
