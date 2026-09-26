#!/usr/bin/env python3
"""Eichung des Vokabelmodells (D212) an echten Verläufen.

Liest über die Ingress-Sitzung und den Lesezugang (READ_ACCESS.md) die
Vokabelantworten der freigegebenen Kinder und rechnet mit dem Modell aus
``vocab.replay`` je Kind:

- Tageslast: Übungstage, Antworten und verschiedene Wörter je Übungstag;
- Treffer beim ersten Versuch und nach einer Pause (ab 12 Stunden);
- Stufen heute und wie viele sichere Wörter seit wann fällig sind (Rückstau);
- Haltbarkeiten der sicheren Wörter (Median, Viertel).

Hilft bei der Frage, ob Pensum (15 ohne Test) und Faktoren (×2,5 / ×0,25)
zum Stoff passen: Wächst der Rückstau Woche für Woche, ist das Pensum zu klein
oder die Wiederholung zu häufig; fällt die Trefferquote nach Pausen unter
etwa 70 %, wächst die Haltbarkeit zu schnell.

    python3 scripts/vocab_calibration.py            # alle freigegebenen Kinder
    python3 scripts/vocab_calibration.py --since 2026-09-26

Braucht HA_URL und HA_TOKEN. Gibt keine Namen, Wörter oder Schlüssel aus.
"""
import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from ha_activity import SLUG, supervisor
from secret_curl import curl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "schul_cockpit"))


def fetch(base: str, headers: dict, dataset: str, account: str) -> list[dict]:
    rows, after = [], 0
    while True:
        data = json.loads(curl(f"{base}{dataset}?account_id={account}&limit=250&after={after}", headers))
        if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
            raise RuntimeError(f"Konto {account}: {dataset} nicht lesbar")
        rows += data["rows"]
        if not data.get("has_more"):
            return rows
        after = data["next_after"]


def report(account: str, attempts: list[dict], since: str, today: date) -> None:
    from backend import vocab
    attempts = sorted((a for a in attempts if a["stage"] == 1), key=lambda a: (a["created_at"], a["id"]))
    seq = defaultdict(list)
    for a in attempts:
        seq[a["word_id"]].append(a)
    days = Counter(a["created_at"][:10] for a in attempts if a["created_at"][:10] >= since)
    words_per_day = Counter()
    for day in days:
        words_per_day[day] = len({a["word_id"] for a in attempts if a["created_at"][:10] == day})
    first = [s[0]["result"] == "correct" for s in seq.values() if s[0]["created_at"][:10] >= since]
    after_pause = []
    for s in seq.values():
        for prev, cur in zip(s, s[1:]):
            gap = (datetime.fromisoformat(cur["created_at"]) - datetime.fromisoformat(prev["created_at"])).total_seconds()
            if gap >= 12 * 3600 and cur["created_at"][:10] >= since and cur["result"] != "unclear":
                after_pause.append(cur["result"] == "correct")
    states = [vocab.replay(s) for s in seq.values()]
    stages = Counter(st["stage"] for st in states)
    overdue = Counter()
    for st in states:
        if st["stage"] in ("sitzt", "gefestigt") and st["due"] and st["due"] <= today.isoformat():
            late = (today - date.fromisoformat(st["due"])).days
            overdue["heute" if late == 0 else "1–6 Tage" if late < 7 else "ab 7 Tagen"] += 1
    holds = sorted(st["hold"] for st in states if st["stage"] in ("sitzt", "gefestigt"))
    pct = lambda xs: f"{100 * sum(xs) / len(xs):.0f} % von {len(xs)}" if xs else "–"
    print(f"Konto {account} (seit {since})")
    print(f"  Übungstage {len(days)}, Antworten je Übungstag {statistics.median(days.values()) if days else 0:.0f}, "
          f"Wörter je Übungstag {statistics.median(words_per_day.values()) if words_per_day else 0:.0f}")
    print(f"  Treffer beim ersten Versuch {pct(first)}, nach einer Pause {pct(after_pause)}")
    print(f"  Stufen {dict(stages)}; wackelnd {sum(st['relearn'] for st in states)}")
    print(f"  Sichere Wörter fällig: {dict(overdue) or 'keine'}")
    if holds:
        q = statistics.quantiles(holds, n=4) if len(holds) > 1 else [holds[0]] * 3
        print(f"  Haltbarkeit der sicheren Wörter (Tage): Viertel {q[0]:.1f}, Median {q[1]:.1f}, Dreiviertel {q[2]:.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Eichung des Vokabelmodells (D212)")
    parser.add_argument("--since", default="2026-09-26", help="Beginn der Auswertung (ISO-Datum)")
    args = parser.parse_args()
    info = supervisor(f"/addons/{SLUG}/info")
    key = (info.get("options") or {}).get("learning_read_token") or ""
    accounts = [a.strip() for a in str((info.get("options") or {}).get("learning_read_accounts") or "").split(",") if a.strip()]
    if not key or not accounts:
        print("Lesezugang nicht eingerichtet.", file=sys.stderr)
        return 2
    session = supervisor("/ingress/session", "post")["session"]
    base = os.environ["HA_URL"] + info["ingress_url"] + "api/integration/learning/"
    headers = {"Cookie": f"ingress_session={session}", "X-Learning-Read-Key": key}
    for account in accounts:
        report(account, fetch(base, headers, "vocab_attempts", account), args.since, date.today())
    return 0


if __name__ == "__main__":
    sys.exit(main())
