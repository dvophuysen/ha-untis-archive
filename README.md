# UNTIS Unterrichtsarchiv

Home-Assistant-Custom-Component, die WebUntis-Daten dauerhaft in eine lokale
SQLite-Datenbank archiviert — angelegt für den langen Zeitraum bis zum
Abitur, mit vollständiger Änderungs-Historie und automatischer Verknüpfung
von Fehlzeiten mit den dadurch verpassten Stunden.

## Was archiviert wird

Pro Kind / Account, stündlich gepollt:

- **Stundenplan**: jede Stunde mit Fach, Lehrkraft, Raum, Klasse, Lehrstoff,
  Code (cancelled / irregular), Substitutionsdetails. Das vollständige
  Untis-Rohpayload landet zusätzlich als JSON in der Zeile (Forward-Compat).
- **Lehrstoff**: über `/api/public/period/info` nachgezogen, falls der
  Stundenplan-Endpoint das Feld leer liefert.
- **Vertretungen**: Original- und tatsächlicher Lehrer/Raum/Fach werden
  getrennt gespeichert (`teacher_orig_name`, `is_teacher_substituted`,
  analog für Raum und Fach).
- **Hausaufgaben** inkl. Fälligkeit und Erledigungs-Status.
- **Fehlzeiten** des gesamten laufenden Schuljahres mit Grund und
  Entschuldigungsstatus. Daraus wird pro Stunde abgeleitet, ob das Kind
  anwesend war (`was_absent` + `absence_reason`).
- **Stammdaten**: alle Lehrkräfte (Kürzel → Vorname Nachname),
  Klassenleitung der eigenen Klasse, Schuljahresgrenzen, Ferien.
- **Enrollment-Historie**: (Schuljahr × Klasse)-Verlauf inklusive
  Klassenwechsel und Sitzenbleiben.
- **Änderungs-Log**: jede semantische Änderung an einer Stunde wird in
  `lesson_snapshots` mit typisiertem Label gespeichert
  (`TEACHER_SUBSTITUTED`, `ROOM_CHANGED`, `CANCELLED`, `LSTEXT_ADDED`, …).
- **Late additions**: Stunden, die das Sekretariat nachträglich einträgt,
  werden mit `is_late_addition=1` markiert.

## Was du am Ende in HA siehst

Pro Kind / Account:

- **Kalender-Entity** mit allen Stunden, Lehrstoff im Termin-Text
- Sensor **„Lehrstoff heute"** — Anzahl + Liste mit Lehrer/Originallehrer/Raum
- Sensor **„Hausaufgaben offen"** — Anzahl + Fälligkeit
- Sensor **„Versäumter Stoff"** — automatisch via Fehlzeiten (kein manueller
  Toggle mehr nötig)
- Sensor **„Fehlzeiten Schuljahr"** — Gesamtzahl + unentschuldigte
- Sensor **„Stundenplan-Änderungen (7 Tage)"** — Anzahl + Liste
- Sensor **„Fach-Verlauf"** — Lehrstoff gruppiert pro Fach im Schuljahr,
  Datenquelle für das Klassenarbeits-Lernen im Dashboard

Optional gibt es ein vorgefertigtes Lovelace-Dashboard mit Kind-Umschaltung,
Monatskalender, Fehlzeiten-Auswertung und Pro-Fach-Lernverlauf:
[`docs/dashboard.md`](docs/dashboard.md).

Services:

- `untis_archive.refresh` — sofort pollen (optional pro Account)
- `untis_archive.export_markdown` — Archiv pro Fach als Markdown rendern
  unter `/config/untis_archive/docs/`
- `untis_archive.mark_lesson` — manuelle Korrektur einer Stunde

## Installation via HACS (empfohlen)

1. HACS öffnen → drei Punkte oben rechts → **Benutzerdefinierte Repositorys**.
2. URL `https://github.com/dvophuysen/ha-untis-archive` eintragen, Kategorie
   **Integration**, **Hinzufügen**.
3. Im HACS-Menü „UNTIS Archive" suchen → **Herunterladen**.
4. Home Assistant neu starten.
5. Einstellungen → **Geräte & Dienste** → **Integration hinzufügen** →
   „UNTIS Archive". Pro Kind einen Eintrag mit Server, Schulname (loginName!),
   Benutzername und Passwort anlegen.

Falls der Schulname unklar ist: auf https://webuntis.com nach der Schule
suchen — der **Login-Name** ist der mit Bindestrichen (z. B.
`gymnasium-am-wall`), NICHT der Anzeigename.

## Manuelle Installation

`custom_components/untis_archive/` aus diesem Repo nach
`<HA-Config>/custom_components/` kopieren, dann HA neu starten und wie
oben beschrieben einrichten.

## Datenablage

SQLite unter `/config/untis_archive/history.db` (im HA-Backup enthalten).
Tabellen: `accounts`, `lessons`, `lesson_snapshots`, `homework`,
`homework_snapshots`, `absences`, `enrollment`, `master_teachers`,
`master_klasse`, `master_schoolyear`, `master_holidays`.

Pull-Frequenz: stündlich. Stundenplan-Fenster: -5 / +9 Tage (Schul-Limit
via JSON-RPC). Fehlzeiten-Fenster: -400 / +30 Tage. Wenn der Untis-Server
keinen neuen Stundenplan-Import meldet (`getLatestImportTime` unverändert),
wird der teure Stundenplan-Pass übersprungen — Hausaufgaben und Fehlzeiten
werden weiter geholt.

## Standalone-Backfill

Für initialen Bulk-Import oder zum Debuggen ohne HA:

```bash
export UNTIS_SERVER=gymnasium-am-wall.webuntis.com
export UNTIS_SCHOOL=gymnasium-am-wall
export UNTIS_USER=...
export UNTIS_PASS=...
export DB_PATH=./history.db
python scripts/backfill.py
```

## Status

Funktioniert für „Direkter Login mit Benutzer/Kennwort" gegen
WebUntis-Standardinstanzen. SSO-Logins (Microsoft, IServ, Google) werden
nicht unterstützt. Klassenarbeiten / Noten / Klassenbucheinträge sind bei
manchen Schulen über die Schüler-Rolle nicht freigegeben (404 oder
„no right" — die Integration loggt das und arbeitet ohne diese Quellen
weiter).
