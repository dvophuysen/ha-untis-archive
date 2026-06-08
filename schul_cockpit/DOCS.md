# Schul-Cockpit — Installation & Nutzung

## Voraussetzungen

- **UNTIS Archive Integration** (`custom_components/untis_archive/`)
  ist installiert, eingerichtet und hat schon einmal gepollt
  (`history.db` muss existieren).
- Home Assistant OS oder Supervised (das Add-on nutzt Ingress und die
  Supervisor-API).
- Pro Kind eine **HA-ToDo-Liste** (z.B. via dem eingebauten
  `todo.local`-Helper) — die HA-Automation, die Untis-Hausaufgaben in
  diese Listen schreibt, läuft unverändert weiter.

## Installation

1. In HA → **Einstellungen → Add-ons → Add-on-Store** öffnen.
2. Oben rechts ⋮ → **Repositorien**.
3. Repo-URL `https://github.com/dvophuysen/ha-untis-archive` eintragen
   und hinzufügen.
4. Im Store taucht **„Schul-Cockpit"** auf → Installieren → Starten.
5. „Im Seitenleisten-Menü zeigen" aktivieren (optional, sehr bequem).

## Erster Login & Setup

- Der erste eingeloggte HA-User wird automatisch **Admin**.
- Auf dem Heute-Screen erscheint oben rechts ein ⚙️-Symbol → Setup.
- Pro HA-User: Rolle (Eltern / Kind / Admin) setzen und die zugehörigen
  Untis-Kinder per Klick zuordnen.
- Pro Kind: die HA-ToDo-Liste auswählen, die deine Untis-Automation
  füllt.

Andere Familienmitglieder müssen sich einmal eingeloggt haben, damit
sie im Setup-Screen auftauchen.

## Tägliche Nutzung

- **Heute**: Stundenplan + Check-ins (😀 / 😐 / 😟) pro Stunde, fällige
  Aufgaben on top.
- **Plan**: priorisierter Nachmittagsplan mit Zeitbudget. Schnellwahl
  30/45/60/90/120 Min, „📋"-Knopf kopiert die Liste als Markdown.
- **Aufgaben**: vollständige Liste, gruppiert nach Fälligkeit. Sub-Tasks,
  Aufwandsschätzung, Notizen pro Aufgabe.
- **Woche**: Heatmap der letzten/kommenden Woche, Farbe = Verständnis.
- **Fächer**: pro Fach die Lehrstoff-Timeline mit deinen Bewertungen +
  „Heute mündlich punkten"-Vorschläge.

## Sync mit HA-ToDo

- Läuft im Hintergrund alle 2 Min.
- Wird ein Task in der App abgehakt, wird der Eintrag in der HA-ToDo
  ebenfalls als erledigt markiert.
- Wird ein Eintrag in der HA-ToDo erledigt, übernimmt der nächste Sync
  das in die App.
- **Manuell angelegte Tasks** in der App (z.B. Klausurvorbereitungs-
  Lerneinheiten) gehen **nicht** in die HA-ToDo.

## Tagesbudget Lernzeit

Über das 🛠-Symbol oben rechts (pro Kind) lässt sich einstellen, wie
viele Minuten pro Tag standardmäßig zum Lernen zur Verfügung stehen
und welche Wochentage abweichen.

## Troubleshooting

- **„Bitte UNTIS-Archive-Integration aktualisieren"** im Add-on-Log:
  Das Add-on prüft beim Start, ob `history.db` alle erwarteten
  Spalten hat. Falls die Integration zu alt ist, kommt diese Meldung —
  in HACS aktualisieren.
- **Setup-Screen zeigt keine HA-User außer dir**: die anderen müssen
  sich einmal in der App eingeloggt haben.
- **Keine ToDo-Listen sichtbar**: das Add-on braucht
  `homeassistant_api: true` (ist in `config.yaml` gesetzt). Add-on
  neu starten.

## Datenschutz

- Alle Daten bleiben auf deiner HA-Instanz. Es gibt keine
  externen Verbindungen.
- Backups: `webapp.db` liegt in `/data/` und ist Teil jedes HA-Backups.
