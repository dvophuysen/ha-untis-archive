# UNTIS Unterrichtsarchiv

Home-Assistant-Custom-Component, die WebUntis-Daten dauerhaft in eine lokale
SQLite-Datenbank archiviert: Stundenplan, Lehrstoff pro Stunde, Ausfälle und
Vertretungen, Hausaufgaben – inklusive Änderungs-Historie, wenn Lehrer
nachträglich Einträge anpassen.

Privates Projekt für mehrere Kinder/Accounts.

## Was du am Ende bekommst

Pro Kind / Account:

- **Kalender-Entity** mit allen Stunden, Lehrstoff steht im Termin-Text
- **Sensor** „Lehrstoff heute" (Anzahl + Liste als Attribut)
- **Sensor** „Hausaufgaben offen" (Anzahl + Liste als Attribut)
- **Sensor** „Versäumter Stoff" (zeigt verpassten Lehrstoff, wenn
  `input_boolean.kind_<name>_krank` aktiv ist)

Service `untis_archive.export_markdown` rendert das Archiv pro Fach als
Markdown nach `/config/untis_archive/docs/`.

Service `untis_archive.mark_lesson` erlaubt manuelle Korrekturen einer
Stunde (Lehrstoff nachtragen, „nur Aufsicht" markieren).

## Installation via HACS (empfohlen)

1. HACS öffnen → drei Punkte oben rechts → **Benutzerdefinierte Repositorys**.
2. URL `https://github.com/dvophuysen/ha-untis-archive` eintragen, Kategorie
   **Integration**, **Hinzufügen**.
3. Im HACS-Menü „UNTIS Archive" suchen → **Herunterladen**.
4. Home Assistant neu starten.
5. Einstellungen → **Geräte & Dienste** → **Integration hinzufügen** →
   „UNTIS Archive". Pro Kind einen Eintrag mit Server, Schulname,
   Benutzername und Passwort anlegen.

## Manuelle Installation

`custom_components/untis_archive/` aus diesem Repo nach
`<HA-Config>/custom_components/` kopieren, dann HA neu starten und wie
oben beschrieben einrichten.

## Datenablage

SQLite unter `/config/untis_archive/history.db` (im HA-Backup enthalten).
Stündlicher Pull, Fenster ±14 Tage, Änderungen werden als Snapshots
archiviert.

## Status

Frühphase. Funktioniert für „Direkter Login mit Benutzer/Kennwort" gegen
WebUntis-Standardinstanzen. SSO-Logins (Microsoft, IServ, Google) werden
nicht unterstützt.
