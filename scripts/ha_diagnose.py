#!/usr/bin/env python3
"""Diagnose der Hausaufgaben-Pipeline gegen die laufende HA-Instanz.

Prüft über die HA-REST-API die drei Stufen, auf denen Hausaufgaben
verloren gehen können:

1. Integration → Sensor: stehen die Aufgaben in
   ``sensor.untis_archive_*_hausaufgaben_offen`` (items[])?
2. Automation → Todo-Liste: stehen sie in der Liste — und mit welchem
   Status? Ein ``completed``, das niemand gesetzt hat, ist die
   Handschrift des Titel-Bugs aus Schul-Cockpit < 0.22.1.
3. Abgleich: Sensor-Einträge mit Fälligkeit >= heute, zu denen kein
   offenes Todo-Item passt, werden einzeln gemeldet.

Zusätzlich werden untis-bezogene Zeilen aus dem HA-Fehlerlog gezeigt.

Zugang:
    HA_URL    z.B. https://xyz.ui.nabu.casa (ohne Slash am Ende)
    HA_TOKEN  Long-lived Access Token (HA-Profil → Sicherheit)

Aufruf:
    python3 scripts/ha_diagnose.py               # alle Kinder / Listen
    python3 scripts/ha_diagnose.py todo.<liste>  # nur diese Todo-Liste
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date

BASE = (os.environ.get("HA_URL") or "").rstrip("/")
TOKEN = os.environ.get("HA_TOKEN") or ""

_TAG_RE = re.compile(r"\[([A-Za-zÄÖÜäöüß]{1,5}\d+)\]")


def _call(path: str, payload: dict | None = None) -> object:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
    try:
        return json.loads(body)
    except ValueError:
        return body


def _norm(text: str | None) -> str:
    """Text für den Abgleich normalisieren (Tags raus, Whitespace, Case)."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def main() -> int:
    if not BASE or not TOKEN:
        print("HA_URL und HA_TOKEN müssen gesetzt sein, z.B.:")
        print("  export HA_URL=https://xyz.ui.nabu.casa")
        print("  export HA_TOKEN=<long-lived access token>")
        return 2

    only_list = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        alive = _call("/api/")
    except (urllib.error.URLError, OSError) as err:
        print(f"HA nicht erreichbar unter {BASE}: {err}")
        return 1
    print(f"API erreichbar: {alive.get('message') if isinstance(alive, dict) else alive}")

    states = _call("/api/states")
    if not isinstance(states, list):
        print(f"GET /api/states lieferte kein JSON-Array: {str(states)[:200]}")
        return 1

    hw_sensors = [
        s for s in states
        if isinstance(s, dict) and "hausaufgaben_offen" in s.get("entity_id", "")
    ]
    todo_entities = [
        s["entity_id"] for s in states
        if isinstance(s, dict) and s.get("entity_id", "").startswith("todo.")
    ]
    if only_list:
        todo_entities = [e for e in todo_entities if e == only_list]

    # -- Stufe 1: Sensor / Integration ---------------------------------
    print("\n== Stufe 1: Hausaufgaben laut Integration (Sensor) ==")
    sensor_items: list[dict] = []
    if not hw_sensors:
        print("Kein hausaufgaben_offen-Sensor gefunden — Integration prüfen!")
    for s in hw_sensors:
        items = (s.get("attributes") or {}).get("items") or []
        print(f"\n{s['entity_id']}: state={s.get('state')} "
              f"(letztes Update {s.get('last_updated', '?')[:19]})")
        for h in items:
            sensor_items.append(h)
            print(f"  - [{h.get('id', '—')}] {h.get('subject')}: {h.get('text')!r} "
                  f"fällig {h.get('due_date')} (vergeben {h.get('assigned_date')})")

    # -- Stufe 2: Todo-Listen -------------------------------------------
    print("\n== Stufe 2: Inhalt der Todo-Listen ==")
    todo_items: list[dict] = []
    for entity in todo_entities:
        resp = _call(
            "/api/services/todo/get_items?return_response",
            {"entity_id": entity},
        )
        bucket = {}
        if isinstance(resp, dict):
            bucket = (resp.get("service_response") or {}).get(entity) or {}
        items = bucket.get("items") or []
        print(f"\n{entity}: {len(items)} Einträge")
        for it in items:
            todo_items.append(it)
            print(f"  - {it.get('status'):>12}  {it.get('summary')!r} "
                  f"fällig {it.get('due', '—')} uid={it.get('uid')}")
            if it.get("description"):
                print(f"                 notes: {it['description']!r}")

    # -- Stufe 3: Abgleich Sensor vs. Liste -----------------------------
    print("\n== Stufe 3: Abgleich (fällige Sensor-Einträge vs. Liste) ==")
    today = date.today().isoformat()
    open_norm = {_norm(i.get("description")) for i in todo_items
                 if i.get("status") != "completed"}
    completed_norm = {_norm(i.get("description")) for i in todo_items
                      if i.get("status") == "completed"}
    problems = 0
    for h in sensor_items:
        if (h.get("due_date") or "") < today:
            continue
        key = _norm(h.get("text"))
        if not key:
            continue
        if any(key in n for n in open_norm):
            continue
        problems += 1
        if any(key in n for n in completed_norm):
            print(f"  ⚠ als ERLEDIGT in der Liste, obwohl fällig: "
                  f"{h.get('subject')}: {h.get('text')!r} ({h.get('due_date')})")
        else:
            print(f"  ✗ FEHLT komplett in der Liste: "
                  f"{h.get('subject')}: {h.get('text')!r} ({h.get('due_date')})")
    if problems == 0:
        print("  Keine Abweichung: alle fälligen Aufgaben stehen offen in der Liste.")

    # -- Fehlerlog -------------------------------------------------------
    print("\n== HA-Fehlerlog (untis-bezogene Zeilen) ==")
    try:
        log = _call("/api/error_log")
    except (urllib.error.URLError, OSError) as err:
        log = f"(nicht lesbar: {err})"
    if isinstance(log, str):
        lines = [ln for ln in log.splitlines() if "untis" in ln.lower()]
        for ln in lines[-20:]:
            print(f"  {ln}")
        if not lines:
            print("  keine untis-bezogenen Einträge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
