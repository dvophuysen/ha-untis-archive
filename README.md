# UNTIS Unterrichtsarchiv

Home-Assistant-Custom-Component, die WebUntis-Daten dauerhaft in eine lokale
SQLite-Datenbank archiviert: Stundenplan, Lehrstoff pro Stunde, Ausfälle und
Vertretungen, Hausaufgaben – inklusive Änderungs-Historie, wenn Lehrer
nachträglich Einträge anpassen.

Privates Projekt für mehrere Kinder/Accounts. Nicht für HACS generalisiert.

## Status

Frühphase. Phase A (API-Client + Standalone-Probe-Skript) wird gerade
implementiert.

## Schnellstart (Phase-A-Test, ohne Home Assistant)

```bash
export UNTIS_SERVER=herakles.webuntis.com
export UNTIS_SCHOOL="Name der Schule"
export UNTIS_USER=...
export UNTIS_PASS=...
# optional, falls Auto-Discovery fehlschlägt:
# export UNTIS_STUDENT_ID=12345

python scripts/api_probe.py
```

Erfolgreich, wenn die JSON-Ausgabe für mindestens eine Stunde ein
befülltes `lstext`-Feld zeigt und für mindestens eine Hausaufgabe ein
befülltes `text`-Feld.

## Installation in Home Assistant

Siehe [`docs/installation.md`](docs/installation.md).

## Lizenz

Privat – keine Lizenz vergeben.
