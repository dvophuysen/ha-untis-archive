# Installation

Voraussetzung: Home Assistant OS / Container / Supervised, Version 2024.11
oder neuer (wie in `hacs.json`).

## Via HACS (empfohlen)

1. HACS öffnen → drei Punkte oben rechts → **Benutzerdefinierte Repositorys**.
2. URL `https://github.com/dvophuysen/ha-untis-archive` eintragen,
   Kategorie **Integration**, **Hinzufügen**.
3. „UNTIS Archive" im HACS-Menü öffnen → **Herunterladen**.
4. Home Assistant neu starten.
5. Einstellungen → Geräte & Dienste → Integration hinzufügen →
   „UNTIS Archive".

## Manuelle Installation

Verzeichnis `custom_components/untis_archive/` aus diesem Repo nach

```
<HA-Config>/custom_components/untis_archive/
```

kopieren. Bei HA OS ist `<HA-Config>` üblicherweise `/config` — per
SSH-Add-on oder File-Editor erreichbar. Danach HA neu starten und die
Integration unter Geräte & Dienste hinzufügen.

## Pro Kind einen Eintrag anlegen

| Feld | Beispiel |
|---|---|
| Anzeigename | "Anna" |
| Server | `beispiel-gymnasium.webuntis.com` |
| Schulname | `beispiel-gymnasium` (loginName mit Bindestrichen, NICHT der Anzeigename) |
| Benutzer / Passwort | Zugangsdaten des Kindes |
| Schüler-ID | leer lassen — Auto-Discovery über `personId` aus der Session. Gesetzt gilt sie als Schüler-Element (Typ 5) für Stundenplan, Lehrstoff und Fehlzeiten |

Wenn die Login-Validierung fehlschlägt, zeigt das Formular die Untis-
Original-Fehlermeldung an (z. B. „invalid schoolname" → bitte den
LoginName statt des Anzeigenamens eintragen).

## Was direkt nach Setup passiert

- Erster Pull stößt sofort an: Stundenplan im Fenster −5 / +9 Tage,
  Lehrstoff per period/info, Hausaufgaben, Fehlzeiten des laufenden
  Schuljahres, Stammdaten (Lehrkräfte, eigene Klasse, Ferien).
- SQLite-DB unter `/config/untis_archive/history.db`. Wird Teil der
  normalen HA-Backups.
- Stündlicher Pull danach. Wenn `getLatestImportTime` unverändert ist,
  wird der teure Stundenplan-Pass übersprungen. Lehrstoff für Stunden der
  letzten fünf Tage, der noch fehlt, wird trotzdem bei jedem Pull
  nachgefragt (höchstens 40 Stunden je Pull), weil ein Klassenbucheintrag
  den Zeitstempel nicht ändert.
- Die Datenbank ist auf HA-Sicherungen vorbereitet: Vor jeder Sicherung
  wird das WAL in `history.db` geschrieben.

## Sensoren und Kalender

Nach erfolgreichem Setup tauchen pro Kind sieben Sensoren und zwei Kalender
auf. HA bildet die Entity-ID beim ersten Einrichten aus dem Anzeigenamen;
so heißen sie bei einer neuen Einrichtung:

- `sensor.untis_archive_<name>_lehrstoff_heute`
- `sensor.untis_archive_<name>_hausaufgaben_offen`
- `sensor.untis_archive_<name>_versaumter_stoff`
- `sensor.untis_archive_<name>_fehlzeiten_schuljahr`
- `sensor.untis_archive_<name>_stundenplan_anderungen_7_tage`
- `sensor.untis_archive_<name>_fach_verlauf`
- `sensor.untis_archive_<name>_krankheitsperioden`
- `calendar.untis_archive_<name>_stundenplan` — jede Stunde als Termin
- `calendar.untis_archive_<name>_ereignisse` — Fehlzeiten und Klassenarbeiten

Früher eingerichtete Installationen behalten ihre IDs (z.B.
`..._versaeumter_stoff`); maßgeblich ist, was unter Einstellungen →
Geräte & Dienste → UNTIS Archive steht. Die Entitäten lesen aus der
lokalen Datenbank und bleiben verfügbar, auch wenn WebUntis gerade nicht
erreichbar ist.

## Services

- `untis_archive.refresh` — sofort pollen, optional `account: "Anna"`
- `untis_archive.export_markdown` — pro Fach eine Markdown-Datei nach
  `/config/untis_archive/docs/<kind>/<fach>.md`
- `untis_archive.mark_lesson` — manuelle Korrektur einer einzelnen Stunde
