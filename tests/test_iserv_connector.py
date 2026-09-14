from backend.iserv_connector import _LoginForm, _looks_like_login


def test_login_form_keeps_hidden_csrf_fields():
    parser = _LoginForm()
    parser.feed('''<form action="/iserv/auth/login_check" method="post">
      <input type="hidden" name="_csrf_token" value="token">
      <input name="_username"><input type="password" name="_password">
    </form>''')
    assert parser.action == "/iserv/auth/login_check"
    assert parser.fields == {"_csrf_token": "token", "_username": "", "_password": ""}


def test_login_page_detection():
    assert _looks_like_login("https://beispiel-iserv.de/iserv/auth/login", "")
    assert _looks_like_login("https://beispiel-iserv.de/iserv/", '<input name="_username"><input name="_password">')
    assert not _looks_like_login("https://beispiel-iserv.de/iserv/", "Willkommen")
