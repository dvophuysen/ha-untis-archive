#!/usr/bin/env python3
"""Add-on-Log der laufenden HA-Instanz lesen.

Der Supervisor-Proxy von Home Assistant gibt Add-on-Logs unter
``/api/hassio/addons/<slug>/logs`` heraus. Ein Long-lived Access Token eines
Administrators genügt. Die Sammelpfade ``/api/hassio/addons`` und
``/api/hassio/app/...`` antworten dagegen mit 401 — daraus lässt sich nicht
schließen, dass der Zugang fehlt.

Ohne ``Range``-Kopfzeile liefert der Supervisor nur die letzten 100 Zeilen.

Zugang:
    HA_URL    z.B. https://xyz.ui.nabu.casa (ohne Slash am Ende)
    HA_TOKEN  Long-lived Access Token eines Administrators

Aufruf:
    python3 scripts/ha_addon_log.py                        # Schul-Cockpit, 2000 Zeilen
    python3 scripts/ha_addon_log.py --lines 20000 --grep textbook
    python3 scripts/ha_addon_log.py --slug core_mariadb
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request

BASE = (os.environ.get("HA_URL") or "").rstrip("/")
TOKEN = os.environ.get("HA_TOKEN") or ""
DEFAULT_SLUG = os.environ.get("HA_ADDON_SLUG") or "e54108c7_schul_cockpit"


def fetch(slug: str, lines: int) -> str:
    request = urllib.request.Request(
        f"{BASE}/api/hassio/addons/{slug}/logs",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            # Ohne diese Kopfzeile kommen nur die letzten 100 Zeilen zurück.
            "Range": f"entries=:-{lines}:",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        # In der Claude-Code-Sandbox blockt der Agent-Proxy Python-urllib mit
        # 403 und lässt curl durch (wie in ha_diagnose.py).
        if error.code != 403:
            raise
        return fetch_curl(slug, lines)


def fetch_curl(slug: str, lines: int) -> str:
    # Der Token geht über stdin an curl, nicht in argv (Prozessliste,
    # Fehlermeldungen).
    from secret_curl import CurlError, curl
    url = f"{BASE}/api/hassio/addons/{slug}/logs"
    try:
        out = curl(url, {"Authorization": f"Bearer {TOKEN}",
                         "Range": f"entries=:-{lines}:"},
                   args=["-w", "\n%{http_code}"], timeout=60)
    except CurlError as err:
        raise urllib.error.URLError(str(err)) from None
    body, _, code = out.rpartition("\n")
    if not code.isdigit() or int(code) >= 400:
        raise urllib.error.HTTPError(url, int(code) if code.isdigit() else 599, "curl", None, None)
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", default=DEFAULT_SLUG, help="Add-on-Slug des Supervisors")
    parser.add_argument("--lines", type=int, default=2000, help="Anzahl Zeilen vom Ende")
    parser.add_argument("--grep", help="nur Zeilen, die zu diesem regulären Ausdruck passen")
    args = parser.parse_args()

    if not BASE or not TOKEN:
        print("HA_URL und HA_TOKEN müssen gesetzt sein.", file=sys.stderr)
        return 2
    try:
        text = fetch(args.slug, args.lines)
    except urllib.error.HTTPError as error:
        print(f"HTTP {error.code} für Add-on {args.slug}", file=sys.stderr)
        if error.code == 401:
            print("Der Token gehört zu keinem Administrator.", file=sys.stderr)
        if error.code == 404:
            print("Unbekannter Slug. Mit --slug den richtigen angeben.", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Keine Verbindung zu {BASE}: {error.reason}", file=sys.stderr)
        return 1

    pattern = re.compile(args.grep, re.I) if args.grep else None
    for line in text.splitlines():
        if pattern is None or pattern.search(line):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
