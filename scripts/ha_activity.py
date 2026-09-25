#!/usr/bin/env python3
"""Ist gerade jemand im Schul-Cockpit? Vor jedem Add-on-Update abfragen.

Liest über die Ingress-Sitzung und den Lesezugang (READ_ACCESS.md) die
Nutzungstage von heute: Die App meldet sich jede Minute, solange sie offen ist
(`usage_days.last_at`). Ausgabe je Konto und Rolle, wie lange das her ist.
Rückgabewert 1, wenn in den letzten --minutes Minuten ein Kind aktiv war.
Eltern werden angezeigt, halten ein Update aber nicht auf (Wunsch des Nutzers
vom 25.09.2026; die Nutzungstage unterscheiden Elternzugänge nicht).

    python3 scripts/ha_activity.py            # Standard: 10 Minuten
    python3 scripts/ha_activity.py --minutes 5

Braucht HA_URL und HA_TOKEN. Der Leseschlüssel wird nur intern verwendet und
nie ausgegeben.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SLUG = "e54108c7_schul_cockpit"


def supervisor(endpoint: str, method: str = "get") -> dict:
    out = subprocess.run(["node", str(ROOT / "ha_supervisor.mjs"), endpoint, method],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=10)
    args = parser.parse_args()
    info = supervisor(f"/addons/{SLUG}/info")
    key = (info.get("options") or {}).get("learning_read_token") or ""
    accounts = [a.strip() for a in str((info.get("options") or {}).get("learning_read_accounts") or "").split(",") if a.strip()]
    if not key or not accounts:
        print("Lesezugang nicht eingerichtet (learning_read_token / learning_read_accounts).")
        return 2
    session = supervisor("/ingress/session", "post")["session"]
    base = os.environ["HA_URL"] + info["ingress_url"] + "api/integration/learning/usage_days"
    today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    now = datetime.now(timezone.utc)
    busy = False
    for account in accounts:
        raw = subprocess.run(["curl", "-sS", "-b", f"ingress_session={session}", "-H", f"X-Learning-Read-Key: {key}",
                              f"{base}?account_id={account}&start={today}&end={today}"],
                             capture_output=True, text=True, check=True).stdout
        rows = json.loads(raw).get("rows", [])
        if not rows:
            print(f"Konto {account}: heute noch nicht geöffnet")
        for row in rows:
            ago = (now - datetime.fromisoformat(row["last_at"])).total_seconds() / 60
            active = ago <= args.minutes
            who = "Kind" if row["actor"] == "child" else "Eltern"
            busy = busy or (active and who == "Kind")
            print(f"Konto {account}, {who}: zuletzt vor {ago:.0f} Min."
                  f"{' – AKTIV' if active else ''} (heute {round((row['active_seconds'] or 0) / 60)} Min.)")
    print("Ein Kind ist gerade in der App." if busy else f"In den letzten {args.minutes} Minuten war kein Kind in der App.")
    return 1 if busy else 0


if __name__ == "__main__":
    sys.exit(main())
