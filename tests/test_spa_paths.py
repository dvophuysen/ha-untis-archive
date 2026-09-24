"""Die Auslieferung des Frontends darf keine Datei außerhalb des
Frontend-Verzeichnisses herausgeben. Bis 1.13.10 lieferte der Catch-all über
den Direktport ohne Anmeldung jede Datei im Container aus, auch
/data/options.json mit den KI-Schlüsseln: `Path(frontend) / "/etc/x"` ist in
Python schlicht `/etc/x`, und „..“ wurde nicht geprüft."""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "schul_cockpit"


def test_frontend_file_stays_inside_the_frontend(tmp_path):
    sys.path.insert(0, str(ROOT))
    from backend.main import frontend_file

    front = tmp_path / "front"
    (front / "assets").mkdir(parents=True)
    (front / "index.html").write_text("<html>")
    (front / "assets" / "app.js").write_text("js")
    (tmp_path / "secret.txt").write_text("geheim")

    assert frontend_file(front, "index.html") == (front / "index.html").resolve()
    assert frontend_file(front, "assets/app.js") == (front / "assets" / "app.js").resolve()
    assert frontend_file(front, "../secret.txt") is None
    assert frontend_file(front, "assets/../../secret.txt") is None
    assert frontend_file(front, str(tmp_path / "secret.txt")) is None
    assert frontend_file(front, "/" + str(tmp_path / "secret.txt")) is None
    assert frontend_file(front, "assets") is None
    assert frontend_file(front, "") is None


def test_the_catch_all_answers_with_the_app_not_the_file(tmp_path):
    front = tmp_path / "front"
    front.mkdir()
    (front / "index.html").write_text("<html>app</html>")
    (tmp_path / "secret.txt").write_text("geheim")
    data = tmp_path / "data"
    data.mkdir()
    script = textwrap.dedent(f"""
        from fastapi.testclient import TestClient
        from backend.main import app
        c = TestClient(app)
        for path in ("/../secret.txt", "/..%2Fsecret.txt", "/%2E%2E/secret.txt",
                     "//{str(tmp_path / 'secret.txt').lstrip('/')}"):
            r = c.get(path)
            assert "geheim" not in r.text, path
        assert "app" in c.get("/index.html").text
        print("ok")
    """)
    env = {**os.environ, "WEBAPP_FRONTEND_DIR": str(front), "WEBAPP_DATA_DIR": str(data),
           "WEBAPP_HISTORY_DB": str(tmp_path / "history.db")}
    out = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "ok" in out.stdout, out.stderr[-2000:]
