# UNTIS Archive — Datenzugriff für Drittsysteme

Diese Integration archiviert WebUntis-Daten dauerhaft in einer lokalen
SQLite-Datenbank innerhalb von Home Assistant. Dieses Dokument beschreibt,
wie ein externes System (Reporting, App, Skript, anderes Smart-Home) an die
Daten kommt — sowohl direkt aus der DB als auch über Home Assistant.

---

## 1. Zugriffswege im Überblick

| Weg | Eignung | Echtzeit | Historie |
|---|---|---|---|
| **SQLite direkt** | Reporting, Analyse, Bulk-Export | nahezu (stündlicher Pull) | vollständig |
| **HA REST API** (`/api/states/...`) | aktuelle Tageswerte, Dashboards | ja | nur „heute"/aktuelle Fenster |
| **HA WebSocket** | Live-Push bei Sensor-Änderung | ja | nein |

Für ein Archiv-Drittsystem ist der **direkte SQLite-Zugriff** der richtige Weg.
Die anderen beiden sind für Live-Anzeige gedacht.

---

## 2. Direkter SQLite-Zugriff

### Speicherort

```
<HA-Config>/untis_archive/history.db
```

Bei Home Assistant OS: `/config/untis_archive/history.db`. Die Datei läuft
im **WAL-Modus** (`journal_mode=WAL`), d. h. Lesezugriffe sind gefahrlos
auch während die Integration schreibt. Es gibt begleitende `-wal`/`-shm`-
Dateien — nicht separat kopieren; für eine konsistente Kopie
`VACUUM INTO` oder die SQLite-Backup-API verwenden.

### Nur-Lesen-Empfehlung

Drittsysteme sollten die DB **read-only** öffnen, um der Integration nicht
in die Quere zu kommen:

```
sqlite3 'file:/config/untis_archive/history.db?mode=ro&immutable=0' 
```

oder in Python:

```python
import sqlite3
conn = sqlite3.connect(
    "file:/config/untis_archive/history.db?mode=ro",
    uri=True, check_same_thread=False,
)
conn.row_factory = sqlite3.Row
```

### Mehrere Kinder

Alle Kinder/Accounts teilen sich **eine** DB, getrennt über `account_id`.
Die Zuordnung steht in der Tabelle `accounts`. Immer nach `account_id`
filtern bzw. joinen.

---

## 3. Datenmodell-Konventionen

- **Datumsfelder** (`date`, `start_date`, `due_date`, `startDate`, …):
  ISO-String `YYYY-MM-DD`.
- **Uhrzeiten** (`start_time`, `end_time`): Integer im WebUntis-Format `HHMM`
  (z. B. `750` = 07:50, `1545` = 15:45). Minuten: `t % 100`, Stunde: `t // 100`.
- **Zeitstempel** (`first_seen_at`, `last_updated_at`, `captured_at`):
  ISO-8601 UTC mit Offset, Sekundengenauigkeit (`2026-06-05T12:38:59+00:00`).
- **Booleans**: Integer `0`/`1`.
- **`*_json`-Spalten**: JSON-String. `payload_json` enthält immer die
  **vollständige Roh-Antwort** von WebUntis für diese Zeile — falls ein
  Feld nicht als eigene Spalte modelliert ist, steht es dort drin.
- **Lehrer-Kürzel vs. Name**: Im Stundenplan steht `teacher_name` als
  Nachname; bei Vertretungen steht in `teacher_orig_name` das **Kürzel**
  des ursprünglichen Lehrers. Die Auflösung Kürzel → Vorname/Nachname
  liefert `master_teachers` (siehe §5).

---

## 4. Tabellen (Kerndaten)

### `accounts` — ein Eintrag pro Kind
| Spalte | Typ | Bedeutung |
|---|---|---|
| `id` | INT PK | account_id, überall als Fremdschlüssel |
| `name` | TEXT | Anzeigename (z. B. „Josia") |
| `server` | TEXT | WebUntis-Server |
| `school` | TEXT | Schul-Login-Name |
| `username` | TEXT | Untis-Benutzer |
| `student_id`, `student_type` | INT | Untis-Personen-ID/-Typ (kann NULL = Auto-Discovery) |
| `created_at` | TEXT | Anlagezeitpunkt |
| `last_pull_completed_at` | TEXT | letzter vollständiger Pull |

### `lessons` — Unterrichtsstunden (Kern-Tabelle)
Eindeutig über `(account_id, untis_period_id)`.

| Spalte | Bedeutung |
|---|---|
| `untis_period_id` | Untis-Perioden-ID (stabiler Schlüssel der Stunde) |
| `date` | Datum `YYYY-MM-DD` |
| `start_time`, `end_time` | `HHMM` |
| `subject_untis_id`, `subject_name` | Fach (ID + Langname) |
| `teacher_untis_id`, `teacher_name` | tatsächliche Lehrkraft |
| `room` | Raum |
| `code` | `''` = regulär, `'cancelled'` = Ausfall, `'irregular'` = unregelmäßig/Vertretung |
| `lstext` | **Lehrstoff** (Unterrichtsinhalt) |
| `subst_text` | Vertretungstext von Untis |
| `info` | Info-Text |
| `was_absent` | `1` = Kind war in dieser Stunde laut Fehlzeiten abwesend |
| `absence_reason` | Grund der Abwesenheit (falls `was_absent=1`) |
| `is_late_addition` | `1` = Stunde wurde **nachträglich** in den Plan eingefügt |
| `teacher_orig_untis_id`, `teacher_orig_name` | ursprüngliche Lehrkraft bei Vertretung (Name = **Kürzel**) |
| `subject_orig_*`, `room_orig` | analog für Fach/Raum |
| `is_teacher_substituted` | `1` = Lehrervertretung |
| `is_room_substituted` | `1` = Raumänderung |
| `is_subject_substituted` | `1` = Fachänderung |
| `lsnumber` | Untis-Lesson-Number |
| `student_group` | Kursgruppe (`sg`) |
| `activity_type` | z. B. „Unterricht" |
| `bk_text`, `bk_remark` | Buchungstext/-bemerkung |
| `teachers_json`, `classes_json`, `subjects_json`, `rooms_json` | Volllisten als JSON, **nur gesetzt wenn mehr als ein Element** (parallele Kurse, Mehrfachklassen). Bei Einzelwerten NULL → dann die Skalar-Spalten nutzen. |
| `payload_json` | komplette Roh-Stundenplan-Antwort |
| `period_info_json` | komplette `period/info`-Antwort (enthält u. a. `lessonTopic`, `exam` (Klassenarbeiten), `attachments`, `roomSubstitutions`) |
| `lstext_manual_override`, `supervision_manual_override` | manuelle Korrekturen via HA-Service; falls gesetzt, haben Vorrang vor den Untis-Werten |
| `first_seen_at`, `last_updated_at` | Audit |

> **Klassenarbeiten / Prüfungen** sind (sofern die Schule sie pflegt) im
> `period_info_json` unter `data.blocks[*][*].exam` enthalten — derzeit
> nicht in eigene Spalten normalisiert.

### `lesson_snapshots` — Änderungs-Historie der Stunden
Jede *semantische* Änderung an einer Stunde erzeugt eine Zeile.

| Spalte | Bedeutung |
|---|---|
| `lesson_id` | FK auf `lessons.id` |
| `captured_at` | Zeitpunkt der erkannten Änderung |
| `payload_json` | **vorheriger** Zeilenzustand (vor der Änderung) |
| `diff_json` | `{spalte: [alt, neu], …}` |
| `change_types_json` | JSON-Array von Labels (siehe unten) |

**Change-Type-Labels**: `TEACHER_CHANGED`, `TEACHER_SUBSTITUTED`,
`ROOM_CHANGED`, `ROOM_SUBSTITUTED`, `SUBJECT_CHANGED`, `SUBJECT_SUBSTITUTED`,
`CANCELLED`, `UNCANCELLED`, `IRREGULAR`, `RESCHEDULED`, `LSTEXT_ADDED`,
`LSTEXT_REMOVED`, `LSTEXT_CHANGED`, `SUBST_TEXT_CHANGED`, `INFO_CHANGED`,
`OTHER`.

### `homework` — Hausaufgaben
Eindeutig über `(account_id, untis_homework_id)`.

| Spalte | Bedeutung |
|---|---|
| `untis_lesson_id` | zugehörige Lesson (Untis) |
| `subject_untis_id`, `subject_name` | Fach |
| `text` | Aufgabentext |
| `assigned_date` | gestellt am `YYYY-MM-DD` |
| `due_date` | fällig am `YYYY-MM-DD` |
| `completed` | `1` = erledigt |
| `payload_json` | Roh-Antwort |

`homework_snapshots` = Änderungs-Historie analog zu `lesson_snapshots`
(Felder `homework_id`, `captured_at`, `payload_json`, `diff_json`).

### `absences` — Fehlzeiten (gesamtes Schuljahr)
Eindeutig über `(account_id, untis_absence_id)`. Nur **aktueller Stand**
(keine Snapshots — `last_updated_at` zeigt die letzte Änderung).

| Spalte | Bedeutung |
|---|---|
| `start_date`, `end_date` | `YYYY-MM-DD` |
| `start_time`, `end_time` | `HHMM` |
| `reason_id`, `reason` | Abwesenheitsgrund |
| `text` | Freitext |
| `excuse_status` | Entschuldigungsstatus-Text |
| `is_excused` | `1` = entschuldigt, `0` = offen/unentschuldigt |
| `created_user`, `updated_user` | erfassende Lehrkraft |
| `payload_json` | Roh-Antwort (enthält u. a. Untis-`lastUpdate`) |

---

## 5. Stammdaten-Tabellen

Spaltennamen spiegeln die WebUntis-JSON-Felder 1:1 (camelCase). Diese
Tabellen sind **append-only** — alte Einträge bleiben für historische
Auflösung erhalten (`last_updated_at` = zuletzt aktiv in der API gesehen).

### `master_teachers` — alle Lehrkräfte der Schule
Schlüssel `(account_id, id)`. **Wichtig für Kürzel-Auflösung.**

| Spalte | Bedeutung |
|---|---|
| `id` | Untis-Lehrer-ID |
| `name` | Kürzel (z. B. „BRU") |
| `foreName` | Vorname |
| `longName` | Nachname |
| `title` | Titel |
| `active` | aktiv `0/1` |
| `dids_json` | Abteilungs-IDs als JSON |

### `master_klasse` — eigene Klasse(n) des Kindes
Schlüssel `(account_id, id)`.

| Spalte | Bedeutung |
|---|---|
| `id` | Untis-Klassen-ID |
| `name`, `longName` | Klassenbezeichnung (z. B. „5E") |
| `teacher1`, `teacher2` | Untis-Lehrer-IDs der Klassenleitung → join auf `master_teachers.id` |

### `master_schoolyear` — Schuljahre
`id`, `name` (z. B. „2025/2026"), `startDate`, `endDate`.

### `master_holidays` — Ferien/Feiertage
`id`, `name`, `longName`, `startDate`, `endDate`.

### `enrollment` — Schullaufbahn (Schuljahr × Klasse)
Schlüssel `(account_id, schoolyear_id, klasse_id)`. Bildet ab:
- normaler Aufstieg (5E → 6E → …)
- Klassenwechsel mitten im Jahr (mehrere `klasse_id` pro `schoolyear_id`)
- Wiederholung einer Stufe (selbe `klasse_id` unter neuer `schoolyear_id`)

Join: `schoolyear_id` → `master_schoolyear.id`, `klasse_id` → `master_klasse.id`.

---

## 6. Beispiel-Abfragen (SQL)

```sql
-- account_id eines Kindes
SELECT id, name FROM accounts;

-- Stundenplan eines Tages mit aufgelöstem Lehrernamen
SELECT l.start_time, l.end_time, l.subject_name, l.room,
       l.code, l.lstext,
       COALESCE(t.title || ' ', '') || COALESCE(t.foreName || ' ', '') || t.longName AS lehrer,
       l.was_absent, l.absence_reason
FROM lessons l
LEFT JOIN master_teachers t
       ON t.account_id = l.account_id AND t.id = l.teacher_untis_id
WHERE l.account_id = ? AND l.date = '2026-06-05'
ORDER BY l.start_time;

-- Vertretungen / Ausfälle der nächsten 7 Tage
SELECT date, start_time, subject_name, code,
       teacher_name, teacher_orig_name, room, room_orig
FROM lessons
WHERE account_id = ?
  AND date BETWEEN date('now') AND date('now','+7 day')
  AND (code = 'cancelled' OR is_teacher_substituted = 1 OR is_room_substituted = 1)
ORDER BY date, start_time;

-- Offene Hausaufgaben, nach Fälligkeit
SELECT subject_name, text, due_date
FROM homework
WHERE account_id = ? AND completed = 0
ORDER BY due_date;

-- Lehrstoff, den das Kind krankheitsbedingt verpasst hat
SELECT date, subject_name, lstext, absence_reason
FROM lessons
WHERE account_id = ? AND was_absent = 1 AND lstext <> ''
ORDER BY date DESC;

-- Fehlzeiten-Bilanz des laufenden Schuljahrs
SELECT COUNT(*) AS gesamt,
       SUM(CASE WHEN is_excused = 0 THEN 1 ELSE 0 END) AS unentschuldigt
FROM absences a
JOIN master_schoolyear sy
     ON sy.account_id = a.account_id
WHERE a.account_id = ?
  AND a.start_date BETWEEN sy.startDate AND sy.endDate;

-- Änderungs-Feed der letzten 7 Tage
SELECT s.captured_at, l.date, l.start_time, l.subject_name, s.change_types_json
FROM lesson_snapshots s
JOIN lessons l ON l.id = s.lesson_id
WHERE l.account_id = ?
  AND s.captured_at >= datetime('now','-7 day')
ORDER BY s.captured_at DESC;

-- Klassenleitung der aktuellen Klasse
SELECT k.name AS klasse,
       t.foreName || ' ' || t.longName AS klassenlehrer
FROM master_klasse k
JOIN master_teachers t
     ON t.account_id = k.account_id AND t.id IN (k.teacher1, k.teacher2)
WHERE k.account_id = ?;
```

---

## 7. Zugriff über Home Assistant (für Live-Werte)

Falls kein DB-Zugriff möglich ist, liefern die Sensoren die wichtigsten
Tageswerte. Pro Kind (`<name>` = slugifizierter Anzeigename):

| Entity | State | Wichtige Attribute |
|---|---|---|
| `sensor.untis_archive_<name>_lehrstoff_heute` | Anzahl heutiger Stunden mit Lehrstoff | `items[]` (subject, start, teacher, teacher_orig, room, code, was_absent, lstext) |
| `sensor.untis_archive_<name>_hausaufgaben_offen` | Anzahl offener HA | `items[]` (subject, text, due_date, assigned_date) |
| `sensor.untis_archive_<name>_versaeumter_stoff` | Anzahl verpasster Stunden (14 Tage) | `items[]` (date, subject, teacher, absence_reason, lstext) |
| `sensor.untis_archive_<name>_fehlzeiten_schuljahr` | Anzahl Fehlzeiten im Schuljahr | `unexcused_count`, `items[]` |
| `sensor.untis_archive_<name>_stundenplan_aenderungen` | Anzahl Änderungen (7 Tage) | `items[]` (date, subject, teacher/orig, room/orig, change_types) |
| `calendar.untis_archive_<name>` | Kalender mit allen Stunden | Lehrstoff im Termin-Text |

### REST

```
GET http://<ha-host>:8123/api/states/sensor.untis_archive_josia_lehrstoff_heute
Authorization: Bearer <Long-Lived-Access-Token>
```

Liefert State + `attributes` (inkl. `items`-Liste) als JSON. Token unter
HA-Profil → „Long-Lived Access Tokens" erzeugen.

### WebSocket

Für Push bei Änderungen: `subscribe_events` mit `event_type: state_changed`
und auf die obigen Entity-IDs filtern. Siehe
https://developers.home-assistant.io/docs/api/websocket.

---

## 8. Pull-Verhalten / Aktualität

- Pull-Intervall: **stündlich**.
- Stundenplan-Fenster: ca. **−5 bis +9 Tage** (durch die Schul-API begrenzt).
- Fehlzeiten-Fenster: **−400 bis +30 Tage**.
- Wenn der Untis-Server keinen neuen Stundenplan-Import meldet, wird der
  Stundenplan-Pass übersprungen (Hausaufgaben/Fehlzeiten laufen trotzdem).
- Sofort-Abruf manuell auslösbar via HA-Service `untis_archive.refresh`
  (optional `account: "<Anzeigename>"`).

> **Wichtig zur Datenvollständigkeit:** Die WebUntis-API gibt nur das enge
> Fenster um „heute" zurück. Das langfristige Archiv entsteht **kumulativ**
> durch die stündlichen Pulls. Daten außerhalb des Live-Fensters existieren
> nur, soweit die Integration sie bereits eingesammelt hat.

---

## 9. Stabilität der Schnittstelle

- **Skalar-Spalten** (Tabellen-Layout in §4/§5) sind stabil; neue Spalten
  können additiv hinzukommen, bestehende werden nicht umbenannt.
- **`payload_json`/`period_info_json`** spiegeln das WebUntis-Rohformat und
  können sich ändern, wenn WebUntis sein API-Format ändert.
- Für robuste Drittsysteme: bevorzugt die normalisierten Skalar-Spalten
  lesen, `payload_json` nur als Fallback für nicht-modellierte Felder.
