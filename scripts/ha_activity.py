#!/usr/bin/env python3
"""Ist gerade jemand im Schul-Cockpit? Vor jedem Add-on-Update abfragen.

Liest über die Ingress-Sitzung und den Lesezugang (READ_ACCESS.md) die
Nutzungstage von heute: Die App meldet sich jede Minute, solange sie offen ist
(`usage_days.last_at`). Ausgabe je Konto und Rolle, wie lange das her ist.
Eltern werden angezeigt, halten ein Update aber nicht auf (Wunsch des Nutzers
vom 25.09.2026; die Nutzungstage unterscheiden Elternzugänge nicht).

Rückgabewerte:
    0  frei: in den letzten --minutes Minuten war kein Kind in der App
    1  ein Kind ist aktiv: mit dem Update warten
    2  Prüfung nicht möglich (Zugang fehlt, Netz, unerwartete Antwort):
       Ergebnis unbekannt, nicht als „frei“ werten

    python3 scripts/ha_activity.py            # Standard: 10 Minuten
    python3 scripts/ha_activity.py --minutes 5

Braucht HA_URL und HA_TOKEN. Der Leseschlüssel und die Ingress-Sitzung gehen
über stdin an curl, stehen also weder in der Prozessliste noch in einer
Fehlermeldung.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from secret_curl import curl

ROOT = Path(__file__).resolve().parent
SLUG = "e54108c7_schul_cockpit"

FREE, CHILD_ACTIVE, UNKNOWN = 0, 1, 2


def supervisor(endpoint: str, method: str = "get") -> dict:
    done = subprocess.run(["node", str(ROOT / "ha_supervisor.mjs"), endpoint, method],
                          capture_output=True, text=True)
    if done.returncode != 0:
        # stderr des Skripts enthält keine Geheimnisse; stdout (Antwort) schon.
        raise RuntimeError(f"Supervisor {endpoint}: {done.stderr.strip() or done.returncode}")
    return json.loads(done.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ist gerade ein Kind im Schul-Cockpit?",
        epilog="Rückgabe: 0 frei, 1 Kind aktiv (warten), 2 Prüfung nicht möglich.",
    )
    parser.add_argument("--minutes", type=int, default=10)
    args = parser.parse_args()
    try:
        return check(args.minutes)
    except Exception as err:  # noqa: BLE001
        # Jede Ausnahme heißt: unbekannt. Nie 1 (sähe aus wie „Kind aktiv“)
        # und nie 0 (sähe aus wie „frei“). Meldung ohne Traceback, damit
        # kein Schlüssel und keine Sitzung darin landen.
        print(f"Prüfung nicht möglich: {type(err).__name__}: {err}", file=sys.stderr)
        return UNKNOWN


def check(minutes: int) -> int:
    info = supervisor(f"/addons/{SLUG}/info")
    key = (info.get("options") or {}).get("learning_read_token") or ""
    accounts = [a.strip() for a in str((info.get("options") or {}).get("learning_read_accounts") or "").split(",") if a.strip()]
    if not key or not accounts:
        print("Lesezugang nicht eingerichtet (learning_read_token / learning_read_accounts).")
        return UNKNOWN
    session = supervisor("/ingress/session", "post")["session"]
    base = os.environ["HA_URL"] + info["ingress_url"] + "api/integration/learning/usage_days"
    today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    now = datetime.now(timezone.utc)
    busy = False
    for account in accounts:
        raw = curl(f"{base}?account_id={account}&start={today}&end={today}",
                   {"Cookie": f"ingress_session={session}", "X-Learning-Read-Key": key})
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
            # Z.B. 401 bei abgelaufener Sitzung: kein „heute nicht geöffnet“.
            raise RuntimeError(f"Konto {account}: Antwort ohne Nutzungstage")
        rows = data["rows"]
        if not rows:
            print(f"Konto {account}: heute noch nicht geöffnet")
        for row in rows:
            ago = (now - datetime.fromisoformat(row["last_at"])).total_seconds() / 60
            active = ago <= minutes
            who = "Kind" if row["actor"] == "child" else "Eltern"
            busy = busy or (active and who == "Kind")
            print(f"Konto {account}, {who}: zuletzt vor {ago:.0f} Min."
                  f"{' – AKTIV' if active else ''} (heute {round((row['active_seconds'] or 0) / 60)} Min.)")
    print("Ein Kind ist gerade in der App." if busy else f"In den letzten {minutes} Minuten war kein Kind in der App.")
    return CHILD_ACTIVE if busy else FREE


if __name__ == "__main__":
    sys.exit(main())
