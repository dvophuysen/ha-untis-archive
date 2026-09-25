"""Diagnose-Skripte: Geheimnisse (HA-Token, Leseschlüssel, Ingress-Sitzung)
stehen nicht in argv und nicht in Fehlermeldungen; ha_activity.py meldet
0 frei, 1 Kind aktiv, 2 Prüfung nicht möglich."""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

secret_curl = importlib.import_module("secret_curl")

SECRET = "geheim-4711"


def test_headers_go_through_stdin(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"], seen["input"] = cmd, kwargs.get("input")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = secret_curl.curl("https://ha.example/api", {"X-Learning-Read-Key": SECRET,
                                                     "Cookie": f"ingress_session={SECRET}"},
                           args=["-X", "POST"])
    assert out == "ok"
    assert not any(SECRET in part for part in seen["cmd"])
    assert "@-" in seen["cmd"] and "-X" in seen["cmd"]
    assert f"X-Learning-Read-Key: {SECRET}\n" in seen["input"]


def test_failure_message_is_scrubbed(monkeypatch):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=22, stdout="", stderr=f"curl: bad header {SECRET}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(secret_curl.CurlError) as info:
        secret_curl.curl("https://ha.example/api", {"Authorization": f"Bearer {SECRET}"})
    assert SECRET not in str(info.value)
    assert info.value.__cause__ is None and info.value.__context__ is None


def test_header_injection_is_refused():
    with pytest.raises(ValueError):
        secret_curl.curl("https://ha.example/api", {"X": "a\nEvil: 1"})


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl fehlt")
def test_real_curl_sends_the_headers(monkeypatch):
    got = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            got.update(self.headers)
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    try:
        out = secret_curl.curl(f"http://127.0.0.1:{server.server_port}/x",
                               {"X-Learning-Read-Key": SECRET, "Cookie": "ingress_session=s1"})
    finally:
        server.shutdown()
    assert json.loads(out) == {"ok": True}
    assert got["X-Learning-Read-Key"] == SECRET
    assert got["Cookie"] == "ingress_session=s1"


# ---- ha_activity.py --------------------------------------------------------

@pytest.fixture
def activity(monkeypatch):
    mod = importlib.import_module("ha_activity")
    monkeypatch.setenv("HA_URL", "https://ha.example")
    monkeypatch.setattr(sys, "argv", ["ha_activity.py"])

    def supervisor(endpoint, method="get"):
        if endpoint.endswith("/info"):
            return {"options": {"learning_read_token": SECRET, "learning_read_accounts": "1"},
                    "ingress_url": "/api/hassio_ingress/abc/"}
        return {"session": SECRET}

    monkeypatch.setattr(mod, "supervisor", supervisor)
    return mod


def _usage(minutes_ago: int, actor: str = "child") -> str:
    last = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return json.dumps({"rows": [{"last_at": last, "actor": actor, "active_seconds": 60}]})


def test_activity_child_active_is_1(activity, monkeypatch):
    monkeypatch.setattr(activity, "curl", lambda url, headers: _usage(2))
    assert activity.main() == 1


def test_activity_free_is_0(activity, monkeypatch):
    monkeypatch.setattr(activity, "curl", lambda url, headers: _usage(30))
    assert activity.main() == 0
    monkeypatch.setattr(activity, "curl", lambda url, headers: _usage(1, "parent"))
    assert activity.main() == 0


@pytest.mark.parametrize("answer", ['{"detail": "Unauthorized"}', "<html>", "[]"])
def test_activity_unclear_answer_is_2(activity, monkeypatch, capsys, answer):
    monkeypatch.setattr(activity, "curl", lambda url, headers: answer)
    assert activity.main() == 2
    assert SECRET not in capsys.readouterr().err


def test_activity_any_exception_is_2(activity, monkeypatch, capsys):
    def broken(url, headers):
        raise secret_curl.CurlError("curl 7: keine Verbindung")

    monkeypatch.setattr(activity, "curl", broken)
    assert activity.main() == 2

    def no_supervisor(endpoint, method="get"):
        raise RuntimeError("Supervisor /addons/x/info: websocket error")

    monkeypatch.setattr(activity, "supervisor", no_supervisor)
    assert activity.main() == 2
    assert SECRET not in capsys.readouterr().err


# ---- ha_diagnose.py / api_probe.py -----------------------------------------

def test_diagnose_prints_items_without_status(monkeypatch, capsys):
    mod = importlib.import_module("ha_diagnose")
    monkeypatch.setattr(mod, "BASE", "https://ha.example")
    monkeypatch.setattr(mod, "TOKEN", SECRET)
    monkeypatch.setattr(sys, "argv", ["ha_diagnose.py"])

    def call(path, payload=None):
        if path == "/api/":
            return {"message": "API running."}
        if path == "/api/states":
            return [{"entity_id": "todo.hausaufgaben"}]
        if path.startswith("/api/services/todo/get_items"):
            return {"service_response": {"todo.hausaufgaben": {"items": [
                {"summary": "Ohne Status", "uid": "1"}]}}}
        return ""

    monkeypatch.setattr(mod, "_call", call)
    assert mod.main() == 0
    assert "Ohne Status" in capsys.readouterr().out


def test_diagnose_curl_fallback_keeps_token_out_of_argv(monkeypatch):
    mod = importlib.import_module("ha_diagnose")
    monkeypatch.setattr(mod, "TOKEN", SECRET)
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"], seen["input"] = cmd, kwargs.get("input")
        return SimpleNamespace(returncode=0, stdout='{"a": 1}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert mod._call_curl("/api/x", {"entity_id": "todo.y"}) == {"a": 1}
    assert not any(SECRET in part for part in seen["cmd"])
    assert f"Authorization: Bearer {SECRET}" in seen["input"]


def test_addon_log_curl_fallback_keeps_token_out_of_argv(monkeypatch):
    mod = importlib.import_module("ha_addon_log")
    monkeypatch.setattr(mod, "TOKEN", SECRET)
    monkeypatch.setattr(mod, "BASE", "https://ha.example")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"], seen["input"] = cmd, kwargs.get("input")
        return SimpleNamespace(returncode=0, stdout="zeile 1\nzeile 2\n200", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert mod.fetch_curl("slug", 50) == "zeile 1\nzeile 2"
    assert not any(SECRET in part for part in seen["cmd"])
    assert "Range: entries=:-50:" in seen["input"]


def test_api_probe_masks_the_session_id():
    text = (SCRIPTS / "api_probe.py").read_text(encoding="utf-8")
    assert '"session_id": "***"' in text
    assert "json.dumps(session.__dict__" not in text
