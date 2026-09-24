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
- **Aufgaben** aus der HA-ToDo-Liste und eigene Einträge mit Titel,
  Fälligkeit und Notiz. Die Hausaufgabenansicht ist seit 0.56.0 eine
  Leseansicht mit Auftrag, Einstiegshilfe, Material und Hilfe-Chat; Typ,
  Aufwand und Teilaufgaben sind entfallen
  ([D44](konzept/ENTSCHEIDUNGEN.md))
- **Bidirektionaler Sync** mit der HA-ToDo-Liste pro Kind — die
  bestehende Untis→HA-Automation läuft unverändert weiter
- **Nachmittagsplaner** mit Zeitbudget: vor allem Pflicht-Aufgaben +
  Vorschläge, die ins Budget passen
- **Fach-Drilldown** mit Verständnis-Timeline und „Heute mündlich punkten"
- **Wochenmatrix** mit Farb-Heatmap der Check-ins

Seit 0.23.0 sind Lernbereich, Lernmentor, Materialablage, Klausurseite und
Vokabeltrainer dazugekommen. Bedienung: [DOCS.md](DOCS.md); Stand und
Entscheidungen: [konzept/README.md](konzept/README.md).

## Konfiguration nach Installation

1. Add-on starten und Ingress öffnen.
2. Der erste eingeloggte HA-User wird automatisch **Admin** und sieht
   den Setup-Screen: Andere HA-User den Rollen (Eltern / Kind) und
   Kindern zuordnen.
3. Pro Kind die bestehende HA-ToDo-Liste auswählen (z.B.
   `todo.anna_schule`). Der Sync läuft alle 2 Minuten automatisch.

## Datenablage

- `history.db` (Untis-Daten) wird **nur gelesen** unter
  `/config/untis_archive/history.db`.
- Eigene App-Daten (Check-ins, Tasks, User↔Kind-Mapping) leben in
  `/data/webapp.db` und sind automatisch im HA-Backup enthalten.
- Ist die KI eingerichtet, gehen Inhalte zur Auswertung an die konfigurierten Azure-AI-Foundry-Ressourcen: Fotos,
  PDFs und abgerufene Buchseiten zum Lesen, Unterrichts- und
  Hausaufgabentexte zur Themenauswertung und für Einstiegshilfen,
  Mentor-Gespräche samt dem nötigen Material und Sprachaufnahmen zur
  Transkription (Aufnahmen werden nicht gespeichert). Aufrufe über die
  Responses-Schnittstelle setzen `store: false` und legen beim Anbieter
  keine abrufbare Konversation an.
- Endpunkte und Schlüssel stehen nur in der Add-on-Konfiguration und werden
  ausschließlich serverseitig verwendet; sie gehen weder an den Browser noch
  in Logs oder den Lernexport.
- Termine und Buchseiten holt die App mit dem hinterlegten IServ-Zugang je
  Kind aus IServ.

## Optionen

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `log_level` | `info` | uvicorn / Backend Log-Level (`debug`–`error`) |
