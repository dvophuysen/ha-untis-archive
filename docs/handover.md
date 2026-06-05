# Session-Übergabe — UNTIS Archive

Stand: nach Commit `c059f79` auf Branch `claude/dreamy-curie-7iRxG`.
Manifest-Version `0.2.0`.

## Worum es geht

Home-Assistant-Custom-Component, die WebUntis-Daten für mehrere Kinder
dauerhaft in lokaler SQLite archiviert — angelegt für die Zeit bis zum
Abitur. Pull stündlich, alle Felder die Untis ausgibt landen in der DB,
Änderungen werden als typisierte Snapshots protokolliert.

## Stand der Datensammlung (FERTIG)

Schema sauber, Pull-Pipeline verifiziert. Tabellen:

| Tabelle | Inhalt |
|---|---|
| `accounts` | Config-Eintrag pro Kind + Pull-Marker (`last_pull_completed_at`, `latest_import_time`) |
| `lessons` | Stunden mit Substitutionsdetail (orgid/orgname), `was_absent`, `is_late_addition`, voll `payload_json` + `period_info_json` |
| `lesson_snapshots` | Change-Log mit typisierten Labels (`TEACHER_SUBSTITUTED`, `ROOM_CHANGED`, `CANCELLED`, `LSTEXT_ADDED`, …) |
| `homework` + `homework_snapshots` | HA inkl. Change-Log |
| `absences` | Fehlzeiten, nur aktueller Stand (lastUpdate steckt im payload_json) |
| `enrollment` | (Kind × Schuljahr × Klasse)-Historie, deckt Klassenwechsel und Sitzenbleiben ab |
| `master_teachers` | Kürzel → Vorname Nachname Titel, akkumuliert (kein Delete) |
| `master_klasse` | Eigene Klasse(n) historisch |
| `master_schoolyear` | Schuljahre, akkumuliert |
| `master_holidays` | Ferien/Feiertage, akkumuliert |

Spaltennamen in `master_*`-Tabellen spiegeln Untis-JSON 1:1 (camelCase).

## Verifiziert

Gegen Josia (`josia.vanophuysen`, Klasse 5E, GaW) end-to-end getestet:

- 72 Stunden im Fenster −5/+9 Tage (Schul-Limit der JSON-RPC-API)
- 28 Lehrstoff-Einträge per period/info nachgezogen, 67 mit vollem `period_info_json`
- 15 Vertretungen via `orgname` korrekt erkannt
- 5 Ausfälle, 22 mehrklassige Stunden
- 9 Hausaufgaben, 15 Fehlzeiten (alle entschuldigt)
- 4 Stunden automatisch als `was_absent=1` markiert für den Krankheitstag 03.06.
- 3 Pulls in Folge: Snapshot-Count stabil bei 28, `latest_import_time`
  überspringt 2./3. Pull den Stundenplan-Pass komplett
- Late-Addition-Simulation (Stunde löschen, Pull) flaggt korrekt

Backfill-Script `scripts/backfill.py` baut die DB außerhalb von HA mit
denselben Modulen. Test-Creds via `PWD_JOSIA` aus dem Container-Env.

## Noch offen / nicht erledigt

1. **Test gegen Noah** (`noah.van.ophuysen`, andere Stufe?) — `PWD_NOAH`
   war im letzten Session-Container nicht gesetzt. In der neuen Session
   sollte das funktionieren. Probe-Script: `/tmp/probe_noah.py` aus der
   Vorsession ist weg, aber das Muster ist `scripts/backfill.py` mit
   `UNTIS_USER=noah.van.ophuysen` und `UNTIS_PASS="$PWD_NOAH"`. Nützlich
   um zu prüfen, ob das Schema bei einer anderen Klasse/Stufe ebenfalls
   trägt (z. B. Kursstufe mit Wahlkursen statt Klassenverband).
2. **Live-Deployment in HA** — Repo ist HACS-ready, aber noch nicht in
   der laufenden HA-Instanz des Users installiert. Schritte:
   - HACS → Custom Repositories → `https://github.com/dvophuysen/ha-untis-archive` als Integration hinzufügen
   - „UNTIS Archive" installieren, HA neu starten
   - Pro Kind einen Config-Eintrag (Server `gymnasium-am-wall.webuntis.com`, Schule `gymnasium-am-wall`)
3. **Git-Tag `v0.2.0`** lokal angelegt, Push wurde vom Sandbox-Proxy
   geblockt (403). In neuer Session ggf. via `mcp__github__*`-Tools
   nachholen — oder einfach Branch-Install in HACS reicht.

## Was als nächstes ansteht: Aufbereitung / Analyse / Darstellung

Das war die Vereinbarung mit dem User: Daten sind durch, jetzt Dashboards.
Mögliche Bausteine:

- **Tagesübersicht pro Kind** (heute / morgen): welche Stunden, welcher
  Lehrer (mit Vor+Nachnamen via `master_teachers`-Join), welcher Raum,
  Vertretungs-Indikatoren, Lehrstoff falls vorhanden
- **Hausaufgaben-Liste** sortiert nach Fälligkeit, mit Fach und Lehrer
- **Wochen-Stundenplan** als Grid (Lovelace `custom:flex-table` oder
  Markdown-Card mit Template), Vertretungen farblich
- **Fehlzeiten-Auswertung**: Übersicht pro Schuljahr aus `absences` +
  `master_schoolyear`, mit unentschuldigt rot
- **„Versäumter Stoff"-Karte**: aus `lessons WHERE was_absent=1` der
  letzten N Tage
- **Änderungs-Feed**: `lesson_snapshots` der letzten 7 Tage als Timeline
  („Mathe Mi morgen fällt aus", „Deutsch Vertretung durch Garrido")
- **Markdown-Export pro Fach** existiert als Service
  (`untis_archive.export_markdown`) — ggf. mit Datums-Filtern erweitern

Sensoren liefern viele Daten schon als Attribute. Lovelace-Templates
greifen direkt darauf zu. Für komplexere Auswertungen ist SQLite via
SQL-Sensor-Integration (`platform: sql` in HA) der direkte Weg — der
User hat das in seiner HA schon laufen.

## Wichtige Pfade und Befehle

```
# Repository
/home/user/ha-untis-archive   (lokal im Sandbox-Container)
github.com/dvophuysen/ha-untis-archive  (Remote, Branch claude/dreamy-curie-7iRxG)

# Test-DB lokal aufbauen
rm -f data/history.db
UNTIS_SERVER=gymnasium-am-wall.webuntis.com \
UNTIS_SCHOOL=gymnasium-am-wall \
UNTIS_USER=josia.vanophuysen \
UNTIS_PASS="$PWD_JOSIA" \
python scripts/backfill.py

# DB inspizieren
python -c "import sqlite3; c=sqlite3.connect('data/history.db'); [print(r) for r in c.execute('SELECT * FROM lessons LIMIT 3')]"
```

## Schul-spezifische Eigenheiten (GaW)

- **Stundenplan-Fenster**: hart begrenzt auf −5 / +9 Tage über JSON-RPC.
  Wider gefragt: Server schneidet still ab. Außerhalb: Fehler `-7004`.
- **Lehrstoff** kommt NICHT im timetable-Response, sondern erst per
  `/api/public/period/info` → `data.blocks[*][*].lessonTopic.text`.
- **Vertretungen**: nur erkennbar über `orgid`/`orgname` pro Element
  (`te`, `su`, `ro`). Kein eigener Substitutions-Endpoint freigegeben.
- **404-Endpoints** (Schule hat das Modul nicht für Schüler freigegeben):
  Noten, Klassenbuch-Bemerkungen, Sprechstunden, Messages, Elternbriefe,
  Umfragen. Code loggt warning und arbeitet ohne diese Quellen weiter.
- **Klassenarbeiten** sind im `exam`-Feld von period/info enthalten —
  bei Josia im aktuellen Fenster keine. Wenn welche kommen, landen sie
  automatisch im `period_info_json`. Eigene `exams`-Tabelle wäre eine
  spätere Erweiterung, falls die UI das braucht.

## Bekannte Bugs / TODOs

- Keine. Drei Pulls in Folge produzieren keine Phantom-Snapshots.

## Architektur-Entscheidungen die der User explizit getroffen hat

1. **1:1 Spiegelung der Untis-Felder** in der DB statt eigener
   Normalisierung. Untis-Field-Namen bleiben in `master_*`-Tabellen
   sichtbar (camelCase). UI macht das Pretty-Printing (Tooltip auf Kürzel,
   Vorname-Auflösung beim Hover usw.).
2. **Master-Tabellen append-only** — Lehrer der wegzieht bleibt für
   historische Auflösung erhalten.
3. **Kein `master_snapshots`** — KL-Wechsel mitten im Jahr: aktueller
   Stand reicht, weil die Lessons selbst den tatsächlichen Lehrer pro
   Datum führen.
4. **Kein `absence_snapshots`** — bei Fehlzeiten ist nur der aktuelle
   Stand relevant; `lastUpdate` aus dem Payload reicht als Audit-Spur.
5. **Stundenplan: −5/+9 Tage**, Fehlzeiten: −400/+30 Tage. Nicht weiter.

## Kontakt-Punkte für die nächste Session

- User-E-Mail: `dennis.vanophuysen@basys-brinova.de`
- Branch-Konvention vom Harness: `claude/<dreamy-curie-7iRxG>` ist das
  Arbeits-Branch dieser Sessions-Familie. PRs noch keine.
- `PWD_JOSIA` / `PWD_NOAH` sind als Container-Env-Vars für Tests gedacht.
