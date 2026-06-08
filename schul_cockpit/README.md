# Schul-Cockpit

Mobile Schul-App für Kinder und Eltern, basierend auf der von der
[UNTIS Archive](../custom_components/untis_archive/) Integration
archivierten Datenbasis.

Läuft als **Home Assistant Add-on** (Supervisor-managed Docker-Container)
hinter HA Ingress. Jeder HA-User loggt sich mit seinem normalen HA-Account
ein und sieht — je nach Zuordnung im Setup — entweder nur sein eigenes
Kind oder als Elternteil mehrere.

## Was es kann (Phase 1)

- **Heute-Ansicht** mit dem Stundenplan des Tages, klar markierten
  Ausfällen/Vertretungen/Klausuren und 1-Klick-Verständnis-Check-ins
- **Eigenständiges Aufgaben-Management** mit Typen (HA / Klausur /
  Üben / Nachholen / Projekt), Aufwand in Minuten und Sub-Tasks
- **Bidirektionaler Sync** mit der HA-ToDo-Liste pro Kind — die
  bestehende Untis→HA-Automation läuft unverändert weiter
- **Nachmittagsplaner** mit Zeitbudget: vor allem Pflicht-Aufgaben +
  Vorschläge, die ins Budget passen
- **Fach-Drilldown** mit Verständnis-Timeline und „Heute mündlich punkten"
- **Wochenmatrix** mit Farb-Heatmap der Check-ins

## Konfiguration nach Installation

1. Add-on starten und Ingress öffnen.
2. Der erste eingeloggte HA-User wird automatisch **Admin** und sieht
   den Setup-Screen: Andere HA-User den Rollen (Eltern / Kind) und
   Kindern zuordnen.
3. Pro Kind die bestehende HA-ToDo-Liste auswählen (z.B.
   `todo.josia_schule`). Der Sync läuft alle 2 Minuten automatisch.

## Datenablage

- `history.db` (Untis-Daten) wird **nur gelesen** unter
  `/config/untis_archive/history.db`.
- Eigene App-Daten (Check-ins, Tasks, User↔Kind-Mapping) leben in
  `/data/webapp.db` und sind automatisch im HA-Backup enthalten.
- **Keine** Daten verlassen die HA-Instanz.

## Optionen

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `log_level` | `info` | uvicorn / Backend Log-Level (`debug`–`error`) |
