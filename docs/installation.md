# Installation

Voraussetzung: Home Assistant OS / Container / Supervised, Version 2024.6
oder neuer.

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
| Anzeigename | "Josia" |
| Server | `gymnasium-am-wall.webuntis.com` |
| Schulname | `gymnasium-am-wall` (loginName mit Bindestrichen, NICHT der Anzeigename) |
| Benutzer / Passwort | Zugangsdaten des Kindes |
| Schüler-ID | leer lassen — Auto-Discovery über `personId` aus der Session |

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
  wird der teure Stundenplan-Pass übersprungen.

## Sensoren

Nach erfolgreichem Setup tauchen pro Kind diese Sensoren auf:

- `sensor.untis_archive_<name>_lehrstoff_heute`
- `sensor.untis_archive_<name>_hausaufgaben_offen`
- `sensor.untis_archive_<name>_versaeumter_stoff`
- `sensor.untis_archive_<name>_fehlzeiten_schuljahr`
- `sensor.untis_archive_<name>_stundenplan_aenderungen`

Plus eine Calendar-Entity mit allen Stunden.

## Services

- `untis_archive.refresh` — sofort pollen, optional `account: "Josia"`
- `untis_archive.export_markdown` — pro Fach eine Markdown-Datei nach
  `/config/untis_archive/docs/<kind>/<fach>.md`
- `untis_archive.mark_lesson` — manuelle Korrektur einer einzelnen Stunde
