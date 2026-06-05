# Dashboard "Schul-Cockpit"

Spezialisiertes Lovelace-Dashboard für zwei Kinder mit Kind-Umschaltung,
Monatskalender, Fehlzeiten-Auswertung, Pro-Fach-Lernverlauf,
Vertretungs-Timeline und Hausaufgaben-Inbox.

Die Dashboard-Definition liegt in `dashboards/schul-cockpit.yaml` im
Repo. Bei HACS-Installation kommt sie nicht automatisch in deine HA –
du registrierst die Datei einmal in `configuration.yaml`.

## 1. HACS Frontend-Karten installieren

HACS → Frontend → Custom Repositories oder Suche, dann installieren:

- `atomic-calendar-revive` – Monatskalender mit Terminvorschau
- `mushroom` – Chips für die Kind-/Fach-Umschaltung
- `apexcharts-card` – Fehltage pro Monat als Balkendiagramm
- `auto-entities` – (optional, falls du dynamische Listen erweitern willst)

Nach der Installation: einmal Browser-Cache leeren (Lovelace lädt
Custom-Card-JS).

## 2. Sensoren prüfen

Pro Kind gibt es seit Version 0.3.0 sechs Sensoren plus einen Kalender.
Beispiel für Anzeigename `Josia` (Device-Slug `untis_archive_josia`):

| Entity-ID | Inhalt |
|---|---|
| `calendar.untis_archive_josia_stundenplan` | Stundenplan-Kalender |
| `sensor.untis_archive_josia_lehrstoff_heute` | Heutige Stunden mit Lehrstoff |
| `sensor.untis_archive_josia_hausaufgaben_offen` | Offene Hausaufgaben |
| `sensor.untis_archive_josia_versaeumter_stoff` | Versäumter Stoff (14 Tage) |
| `sensor.untis_archive_josia_fehlzeiten_schuljahr` | Fehlzeiten im Schuljahr (mit `unexcused_count`) |
| `sensor.untis_archive_josia_stundenplan_aenderungen` | Vertretungen/Ausfälle/Lehrstoff-Updates (7 Tage) |
| `sensor.untis_archive_josia_fach_verlauf` | Lehrstoff-Verlauf gruppiert pro Fach |

Heißen deine Config-Entries anders, ersetze in `schul-cockpit.yaml`
`untis_archive_josia` / `untis_archive_noah` durch die tatsächlichen
Slugs (Entwicklertools → Zustände, nach `untis_archive` filtern).

## 3. Helper anlegen

Einstellungen → Geräte & Dienste → **Helfer** → Helfer hinzufügen →
**Dropdown**:

- Name: `Schul-Cockpit – Kind`
  Entity-ID: `input_select.schul_cockpit_kind`
  Optionen: `Josia`, `Noah` (genau wie die Untis-Anzeigenamen)
- Name: `Schul-Cockpit – Fach`
  Entity-ID: `input_select.schul_cockpit_fach`
  Optionen: zunächst irgendetwas (z. B. `–`); wird durch die Automation
  unten dynamisch befüllt.

## 4. Automation: Fach-Liste pro Kind nachladen

Wenn das Kind gewechselt wird, sollen die Optionen von
`input_select.schul_cockpit_fach` auf die Fächer des Kindes umschalten:

```yaml
# Einstellungen → Automationen → YAML-Editor
alias: Schul-Cockpit – Fachliste pflegen
trigger:
  - platform: state
    entity_id: input_select.schul_cockpit_kind
  - platform: state
    entity_id:
      - sensor.untis_archive_josia_fach_verlauf
      - sensor.untis_archive_noah_fach_verlauf
    attribute: subject_list
  - platform: homeassistant
    event: start
action:
  - variables:
      sensor: >-
        sensor.untis_archive_{{
          states('input_select.schul_cockpit_kind') | lower
        }}_fach_verlauf
      faecher: "{{ state_attr(sensor, 'subject_list') or [] }}"
  - service: input_select.set_options
    target:
      entity_id: input_select.schul_cockpit_fach
    data:
      options: "{{ faecher if faecher | count > 0 else ['–'] }}"
mode: restart
```

## 5. Dashboard in `configuration.yaml` einhängen

```yaml
lovelace:
  mode: storage
  dashboards:
    schul-cockpit:
      mode: yaml
      title: Schul-Cockpit
      icon: mdi:school
      show_in_sidebar: true
      filename: dashboards/schul-cockpit.yaml
```

Datei `dashboards/schul-cockpit.yaml` aus diesem Repo nach
`/config/dashboards/schul-cockpit.yaml` kopieren. Home Assistant einmal
neu starten oder `Einstellungen → Hardware → Dienste → Konfiguration
neu laden → Lovelace-Dashboards`.

## 6. Verifikation

- Sidebar zeigt „Schul-Cockpit" – Dashboard öffnet sich ohne Fehler.
- Kind-Chip oben wechselt zwischen Josia und Noah.
- View „Übersicht" zeigt KPIs (Fehlzeiten, HA offen, Änderungen 7T) und
  die heutigen Stunden mit Vertretungs-Badges (❌ Ausfall, ↺ Vertretung,
  ⚠️ versäumt).
- View „Monatskalender" rendert atomic-calendar-revive im Monatsmodus.
- View „Fehlzeiten" zeigt das Balkendiagramm + Tabelle aller
  Schuljahres-Fehlzeiten + gruppierten versäumten Stoff.
- View „Klassenarbeit lernen": Fach-Chip auswählen → chronologische
  Lehrstoff-Liste (neueste zuerst). Button „Als Markdown exportieren"
  ruft `untis_archive.export_markdown` mit dem aktuell gewählten Fach.
- View „Änderungen": Vertretungen/Ausfälle/Raumwechsel gruppiert nach
  Tag, jeweils mit Change-Type-Labels.
- View „Hausaufgaben": beide Kinder nebeneinander, überfällige Einträge
  mit 🔴 markiert.

## 7. Bekannte Grenzen

- **Stundenplan-Fenster:** Untis liefert je nach Schule nur ein
  beschränktes Vergangenheits-/Zukunftsfenster (bei GaW −5/+9 Tage). Das
  Archiv akkumuliert ab dem Tag der Installation, ältere Tage davor
  bleiben im Monatskalender leer.
- **Fehlzeiten-Fenster:** −400/+30 Tage. Reicht für die Schuljahr-
  Übersicht aus.
- **Klassenarbeiten-Liste:** noch nicht eingebaut. Sobald die Schule
  `exam`-Einträge in der Untis-API freigibt, kann eine zusätzliche View
  ergänzt werden – die Rohdaten sind in `lessons.period_info_json`
  bereits archiviert.
- **Markdown-Export-Button** ist in der Lovelace-Action eingebunden,
  aber Lovelace evaluiert das `[[ ]]`-Template-Syntax nur in einigen
  Card-Typen zuverlässig. Falls der `subject`-Parameter nicht
  übernommen wird, ruf den Service `untis_archive.export_markdown` mit
  `account: Josia, subject: <Fach>` direkt aus den Entwicklertools auf.
