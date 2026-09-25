#!/usr/bin/env python3
"""Nachkalibrieren vorbereiten (D181): Rasterstand vor einer Arbeit gegen die
tatsächliche Note.

Je Arbeit, deren Termin vorbei ist, stellt der Bericht den Rasterstand am Tag
vor dem Termin (Themen auf Zielniveau, sichere Zellen in I und II, berechnet
mit ``backend.practice`` wie in der App) der eingetragenen Note gegenüber
(``exam_progress.grade`` und ``grade_points``). An der Logik in practice.py
ändert der Bericht nichts; er liefert nur die Zahlen, an denen die Grenzen
(80 % sicher, 60 % fast, vier Aufgaben) später geprüft werden.

Stand 1.22: Der Lesezugang (READ_ACCESS.md) liefert ``exam_progress``, aber
noch nicht ``exam_topics``, ``topic_answers`` und ``exam_dates``. Fehlt einer
dieser Datensätze, gibt der Bericht nur die Noten aus und nennt die fehlenden
Datensätze; er rechnet dann kein Raster und behauptet keinen Zusammenhang.

    python3 scripts/calibration_report.py

Braucht HA_URL und HA_TOKEN (wie ha_activity.py). Der Leseschlüssel wird nur
intern verwendet und nie ausgegeben.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "schul_cockpit"))
SLUG = "e54108c7_schul_cockpit"
NEEDED = ("exam_topics", "topic_answers", "exam_dates")


def supervisor(endpoint: str, method: str = "get") -> dict:
    out = subprocess.run(["node", str(ROOT / "ha_supervisor.mjs"), endpoint, method],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


class Reader:
    def __init__(self) -> None:
        info = supervisor(f"/addons/{SLUG}/info")
        options = info.get("options") or {}
        self.key = options.get("learning_read_token") or ""
        self.accounts = [a.strip() for a in str(options.get("learning_read_accounts") or "").split(",") if a.strip()]
        self.session = supervisor("/ingress/session", "post")["session"] if self.key else ""
        self.base = os.environ["HA_URL"] + info["ingress_url"] + "api/integration/learning"

    def get(self, path: str) -> dict:
        raw = subprocess.run(["curl", "-sS", "-b", f"ingress_session={self.session}", "-H", f"X-Learning-Read-Key: {self.key}",
                              f"{self.base}{path}"], capture_output=True, text=True, check=True).stdout
        try:
            return json.loads(raw)
        except ValueError:
            return {"detail": raw[:200]}

    def manifest(self) -> set[str]:
        data = self.get("")
        return set(data.get("datasets") or {}) if isinstance(data.get("datasets"), dict) else {
            d.get("name") for d in data.get("datasets") or [] if isinstance(d, dict)}

    def rows(self, dataset: str, account: str) -> list[dict] | None:
        """Alle Zeilen eines Datensatzes; None, wenn er nicht geliefert wird."""
        out, after = [], 0
        while True:
            page = self.get(f"/{dataset}?account_id={account}&limit=250&after={after}")
            if "rows" not in page or page.get("available") is False:
                return None
            out += page["rows"]
            if not page.get("has_more"):
                return out
            after = page["next_after"]


def raster_before(topics: list[dict], answers: list[dict], day: str) -> dict:
    from backend import practice as pr
    from backend.lernstand import is_vocab_topic
    rows = []
    for t in topics:
        if t.get("stale") or is_vocab_topic(t):
            continue
        mine = [a for a in answers if a["topic_id"] == t["id"] and a["created_at"][:10] < day]
        rows.append(pr.row_of(sorted(mine, key=lambda a: (a["created_at"], a.get("id", 0)))))
    cells = [r["cells"][k] for r in rows for k in ("1", "2")]
    return {"topics": len(rows), "ready": sum(r["ready"] for r in rows),
            "sure_cells": sum(pr.is_sure(c) for c in cells), "cells": len(cells),
            "tasks": sum(c["tasks"] for c in cells)}


def main() -> int:
    if not os.environ.get("HA_URL") or not os.environ.get("HA_TOKEN"):
        print("HA_URL und HA_TOKEN fehlen.")
        return 2
    reader = Reader()
    if not reader.key or not reader.accounts:
        print("Lesezugang nicht eingerichtet (learning_read_token / learning_read_accounts).")
        return 2
    offered = reader.manifest()
    missing = [d for d in NEEDED if d not in offered]
    if missing:
        print("Hinweis: Der Lesezugang liefert noch nicht " + ", ".join(missing) + ".")
        print("Ohne Themen, Antworten und Termine lässt sich der Rasterstand vor einer Arbeit nicht berechnen;")
        print("dafür müssten diese Tabellen in routers/read_access.py freigegeben werden. Es folgen nur die Noten.\n")
    today = date.today().isoformat()
    for account in reader.accounts:
        progress = reader.rows("exam_progress", account) or []
        graded = [p for p in progress if p.get("grade_points") is not None or p.get("grade")]
        print(f"Konto {account}: {len(graded)} Arbeiten mit Note")
        if missing:
            for p in graded:
                print(f"  {p['exam_key']}: Note {p.get('grade') or '–'} ({p.get('grade_points')} Punkte)")
            continue
        topics = reader.rows("exam_topics", account) or []
        answers = reader.rows("topic_answers", account) or []
        dates = {d["exam_key"]: d["exam_date"] for d in reader.rows("exam_dates", account) or []}
        for p in graded:
            day = dates.get(p["exam_key"])
            if not day or day[:10] > today:
                print(f"  {p['exam_key']}: Termin unbekannt oder noch nicht vorbei")
                continue
            r = raster_before([t for t in topics if t["exam_key"] == p["exam_key"]], answers, day[:10])
            print(f"  {p['exam_key']} ({day[:10]}): {r['ready']}/{r['topics']} Themen auf Zielniveau, "
                  f"{r['sure_cells']}/{r['cells']} Zellen I/II sicher, {r['tasks']} Aufgaben · "
                  f"Note {p.get('grade') or '–'} ({p.get('grade_points')} Punkte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
