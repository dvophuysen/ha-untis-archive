import subprocess
from unittest.mock import Mock

import pytest
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
