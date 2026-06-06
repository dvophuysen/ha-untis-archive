# Dashboard "Schul-Cockpit"

Spezialisiertes Lovelace-Dashboard für zwei Kinder mit drei Hauptseiten
und einem zentralen Kind-Umschalter:

1. **Übersicht** – Monatskalender mit dem kompletten Stundenplan
   (Vergangenheit + nächste Tage), Fehltagen und Klassenarbeiten in
   einer Ansicht. Termin anklicken öffnet die Untis-typische
   Detailansicht (Lehrstoff, Lehrer / Originallehrer, Raum,
   Vertretungs-Hinweis, Fehlgrund).
2. **Fächer** – Fach auswählen, chronologische Lehrstoff-Historie mit
   Markierung von Vertretungs- und Ausfall-Stunden.
3. **Krankheits-Ausfälle** – Pro Krankheits-Periode der versäumte
   Stoff, gruppiert nach Fach.

Hausaufgaben tauchen im Dashboard bewusst nicht auf — der `completed`-
Status aus Untis ist nicht zuverlässig, eine eigene Todo-Synchronisation
übernimmt das.

Die Dashboard-Definition liegt im Repo unter
`dashboards/schul-cockpit.yaml`.

## Voraussetzung: Integration v0.4.0 oder neuer

Das Dashboard nutzt Entities, die erst ab **v0.4.0** dieser Integration
erzeugt werden:

- `calendar.untis_archive_<kind>_ereignisse`
- `sensor.untis_archive_<kind>_fach_verlauf`
- `sensor.untis_archive_<kind>_krankheitsperioden`

Wenn HACS noch v0.2.3 (oder älter) anzeigt: HACS → UNTIS Archive →
„Neu downloaden" → die aktuellste Version wählen. Anschließend Home
Assistant neu starten. Im Entwicklertools → Zustände nach `untis_archive`
filtern, dort müssen die genannten Entities auftauchen.

## 1. HACS Frontend-Karten installieren

HACS → Frontend, dann installieren:

- `atomic-calendar-revive` – Monatskalender, kann beide Untis-Kalender
  (Stundenplan + Ereignisse) gleichzeitig anzeigen.
- `mushroom` – Karten für den Kind-Umschalter und Fach-Auswahl.

Nach der Installation: Browser-Cache leeren (Lovelace lädt das
Custom-Card-JavaScript).

## 2. Sensoren und Kalender prüfen

Pro Kind erzeugt die Integration zwei Calendar-Entities und sechs
Sensoren (Beispiel für Anzeigename `Josia`, Device-Slug
`untis_archive_josia`):

| Entity-ID | Inhalt |
|---|---|
| `calendar.untis_archive_josia_stundenplan` | Stundenplan mit Lehrstoff im Termin |
| `calendar.untis_archive_josia_ereignisse` | Fehltage (ganztägig) + Klassenarbeiten |
| `sensor.untis_archive_josia_fach_verlauf` | Lehrstoff-Historie gruppiert pro Fach |
| `sensor.untis_archive_josia_krankheitsperioden` | Krankheits-Perioden mit versäumtem Stoff |
| `sensor.untis_archive_josia_versaeumter_stoff` | Versäumter Stoff letzte 14 Tage |
| `sensor.untis_archive_josia_fehlzeiten_schuljahr` | Fehlzeiten-Zähler |
| `sensor.untis_archive_josia_stundenplan_aenderungen` | Vertretungs-/Ausfall-Zähler |
| `sensor.untis_archive_josia_lehrstoff_heute` | Lehrstoff der heutigen Stunden |

Heißen die Untis-Config-Entries anders, in `schul-cockpit.yaml` die
Slugs `untis_archive_josia` / `untis_archive_noah` durch deine
ersetzen (Entwicklertools → Zustände, nach `untis_archive` filtern).

## 3. Helper anlegen

Einstellungen → Geräte & Dienste → **Helfer** → Helfer hinzufügen →
**Dropdown**:

- Name: `Schul-Cockpit – Kind`
  Entity-ID: `input_select.schul_cockpit_kind`
  Optionen: `Josia`, `Noah` — exakt wie die Anzeigenamen der
  Untis-Konten.
- Name: `Schul-Cockpit – Fach`
  Entity-ID: `input_select.schul_cockpit_fach`
  Optionen: zunächst irgendetwas (z. B. `–`); wird durch die
  Automation unten automatisch passend zum aktuellen Kind befüllt.

## 4. Automation: Fach-Liste pro Kind nachladen

Sobald das Kind gewechselt wird, sollen die Optionen von
`input_select.schul_cockpit_fach` auf die tatsächlich vorhandenen
Fächer des Kindes umschalten.

Einstellungen → Automationen → ☰ → YAML-Editor:

```yaml
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
`/config/dashboards/schul-cockpit.yaml` kopieren. Anschließend
Einstellungen → Hardware → Dienste → Konfiguration neu laden →
**Lovelace-Dashboards**, oder Home Assistant einmal neu starten.

## 6. Verifikation

- Sidebar zeigt „Schul-Cockpit" – Dashboard öffnet sich ohne Fehler.
- Oben in jeder View stehen zwei große Mushroom-Karten „Josia" / „Noah";
  Antippen wechselt das Kind, die aktive Karte ist farbig hervorgehoben.
- **Übersicht**: Monatskalender rendert. Sichtbar sind
  - normale Stunden,
  - ❌ Ausfälle (Titel-Präfix),
  - ↺ Vertretungen,
  - 🤒 versäumte Stunden (Krankheit),
  - rote ganztägige Balken auf Krankheitstagen,
  - 📝 Klassenarbeiten (sofern die Schule sie in der Untis-API
    ausliefert – bei GaW noch nicht beobachtet, der Code zieht sie
    automatisch, sobald sie auftauchen).

  Termin anklicken → Detail-Popup mit Lehrstoff, Lehrer (inkl.
  Originallehrer bei Vertretung), Raum und Fehlgrund.
- **Fächer**: Mushroom-Karte „Fach wählen" antippen → input_select
  öffnet sich, alle Fächer des aktuellen Kindes sind dort. Auswahl
  rendert chronologische Stoff-Liste, neueste zuerst, mit
  Vertretungs-/Ausfall-/Versäumt-Markern.
- **Krankheits-Ausfälle**: Pro Krankheits-Periode (Datumsbereich) ein
  Block mit Entschuldigungs-Status, Grund, Anzahl versäumter Stunden
  und der Stoff-Liste gruppiert nach Fach.

## 7. Bekannte Grenzen

- **Stundenplan-Fenster:** Untis liefert je nach Schule nur ein
  begrenztes Vergangenheits-/Zukunftsfenster (bei GaW −5/+9 Tage). Das
  Archiv akkumuliert ab dem Tag der Installation; Tage davor bleiben
  im Monatskalender leer.
- **Fehlzeiten-Fenster:** −400/+30 Tage. Reicht für die
  Schuljahr-Übersicht.
- **Klassenarbeiten**: Werden aus `lessons.period_info_json.exam`
  defensiv extrahiert. Wenn die Schule den `exam`-Block nicht
  ausliefert, sind im Ereignis-Kalender einfach keine 📝-Einträge
  sichtbar — Stundenplan und Fehltage funktionieren trotzdem.
- **Hausaufgaben**: Bewusst nicht im Dashboard. Untis markiert
  Hausaufgaben praktisch nie als `completed=1`, deshalb sind die Zähler
  irreführend. Stattdessen läuft die Todo-Synchronisation außerhalb
  dieses Dashboards.
