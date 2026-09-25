"""curl-Aufrufe mit geheimen Kopfzeilen, ohne dass die Geheimnisse in argv
stehen.

Kopfzeilen (Token, Leseschlüssel, Ingress-Sitzung als ``Cookie``) gehen per
``-H @-`` über stdin an curl. In der Prozessliste und in einem Traceback von
``CalledProcessError`` stehen damit nur URL und Optionen. Schlägt curl fehl,
wirft ``CurlError`` eine Meldung, aus der jedes übergebene Geheimnis
herausgeschnitten ist.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping, Sequence


class CurlError(OSError):
    """curl lief nicht durch; die Meldung enthält keine Geheimnisse."""


def _secrets(values: Sequence[str]) -> list[str]:
    """Die Werte selbst und ihre Teile („Bearer <token>“, „name=<wert>“),
    längste zuerst."""
    out = set()
    for value in values:
        if value:
            out.add(value)
            out.update(p for p in re.split(r"[\s=;,]+", value) if len(p) >= 6)
    return sorted(out, key=len, reverse=True)


def _scrub(text: str, secrets: Sequence[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, "***")
    return text


def curl(
    url: str,
    headers: Mapping[str, str],
    *,
    args: Sequence[str] = (),
    timeout: int = 30,
) -> str:
    """``curl -sS`` gegen ``url``; ``headers`` kommen über stdin.

    ``args`` sind weitere, nicht geheime Optionen (z.B. ``-X POST``).
    Rückgabe: stdout. Fehler: ``CurlError`` mit bereinigter Meldung.
    """
    for name, value in headers.items():
        if "\n" in name or "\r" in name or "\n" in value or "\r" in value:
            raise ValueError(f"Kopfzeile {name!r} enthält einen Zeilenumbruch")
    stdin = "".join(f"{name}: {value}\n" for name, value in headers.items())
    cmd = ["curl", "-sS", "-m", str(timeout), "-H", "@-", *args, url]
    secrets = _secrets(list(headers.values()))
    try:
        done = subprocess.run(cmd, input=stdin, capture_output=True, text=True,
                              errors="replace")
    except OSError as err:
        raise CurlError(f"curl nicht ausführbar: {err.strerror or err}") from None
    if done.returncode != 0:
        detail = _scrub((done.stderr or "").strip(), secrets)
        raise CurlError(f"curl {done.returncode}: {detail or 'ohne Meldung'}")
    return done.stdout
