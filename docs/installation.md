# Installation

Voraussetzung: Home Assistant OS / Container / Supervised, Version 2024.x
oder neuer.

## 1. Dateien kopieren

Kopiere das Verzeichnis `custom_components/untis_archive/` aus diesem Repo
nach:

```
<HA-Config>/custom_components/untis_archive/
```

Bei HA OS ist `<HA-Config>` üblicherweise `/config`. Per SSH-Add-on oder
File-Editor erreichbar.

## 2. Home Assistant neu starten

Einstellungen → System → Neustart.

## 3. Integration hinzufügen

Einstellungen → Geräte & Dienste → Integration hinzufügen → „UNTIS Archive".

Pro Kind einen Eintrag anlegen. Felder:

- **Anzeigename**: z. B. „Lena"
- **Server**: z. B. `herakles.webuntis.com`
- **Schulname**: exakt wie auf untis.com
- **Benutzer / Passwort**: Zugangsdaten des Kindes
- **Student-ID** (optional): nur falls die Auto-Discovery fehlschlägt.

## 4. Daten

Die SQLite-DB liegt unter `/config/untis_archive/history.db`. Sie ist Teil
der normalen HA-Backups.

Stündlich wird ein Fenster von ±14 Tagen abgefragt; Änderungen werden als
Snapshots in `lesson_snapshots` / `homework_snapshots` archiviert.
