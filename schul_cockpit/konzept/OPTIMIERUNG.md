# Konzept: Fehlerbehebung und Optimierung

Stand 25.09.2026, Schul-Cockpit 1.31.1, Komponente untis_archive 0.5.4.
Grundlage ist ein reines Lese-Review des ganzen Repos in sechs Bereichen
(Backend-Kern, KI- und Materialpipeline, Lernen/Mentor/Arbeiten,
Vokabeln/Belohnungen/Tagesablauf, HA-Komponente mit CI und Skripten,
Frontend). Die Tests waren dabei grün: 861 Backend-Tests, 14 Frontend-Unit-Tests,
12 von 13 Browser-Tests (`subjects_browser.cjs` rot, war schon bekannt).

Befunde mit „(nachgeprüft)“ habe ich selbst im Code bestätigt. Die übrigen
haben die Prüfer am Code und an den Aufrufern belegt, drei davon (Kiosk-Cookie,
Migrationen, `with conn:`) zusätzlich mit einer Wegwerf-Datenbank nachgestellt.
Einen Weg, auf dem ein Kind Daten eines anderen Kindes sieht, gibt es nach
dem Review nicht. SQL-Injection und Pfad-Traversal waren ebenfalls ohne Befund.

## 1. Die Ursachen hinter den meisten Fehlern

Viele Einzelbefunde gehen auf sieben Grundmuster zurück. Wer diese behebt,
räumt die Einzelfälle mit ab und verhindert neue.

**U1 Scheinbare Transaktionen.** `webapp_conn()` öffnet mit
`isolation_level=None`. Damit ist `with closing(webapp_conn()) as c, c:` an
111 Stellen keine Einheit: `commit()` und `rollback()` tun nichts. Scheitert
der zweite Schreibzugriff, bleibt der erste stehen. Betroffen sind unter
anderem Sync, Konto-Abgleich, Abzeichenpflege, Papier-Vokabeltest,
Quellenverknüpfung und Kapitelstruktur.

**U2 Drei Zeitbasen.** `learning.today_local()` (Berlin), `date.today()` und
`datetime.now()` (Containerzeit, rund 30 Stellen), SQLite `date('now')` (UTC)
und UTC-Zeitstempel in `tasks.completed_at` und `materials.created_at`, die
per `substr(...,1,10)` als lokales Datum gelesen werden. Zwischen 0 und 2 Uhr
landen Dinge am falschen Tag oder in der falschen Woche.

**U3 Blockierender Event-Loop.** Uvicorn läuft mit einem Worker. Viele
`async def`-Endpunkte machen schwere synchrone SQLite-, PIL- oder
`subprocess`-Arbeit (Mentor-Zug, Dashboard, Vokabelantwort mit
`rewards.note`, `pdftoppm` bis 120 s, Restore). Solange das läuft, steht die
App für alle Geräte.

**U4 Hintergrundjobs ohne Zustand.** Materialauswertung, Abbildungen,
Sammellauf und Papiertest haben keinen atomaren „in Arbeit“-Anspruch, keinen
dauerhaften Versuchszähler und keine Ablaufzeit. Folgen: doppelt bezahlte
Lesungen, Endlosschleifen, hängende Zustände nach einem Neustart.

**U5 Rechteprüfung verstreut.** Es gibt `assert_account_access`,
`learning.access(write=, parent=)`, `acts_as_parent`, `user.role=='child'`
und `is_admin` nebeneinander. Einige Router prüfen die rohe Rolle statt der
Geräterolle (D183), einige Schreibpfade prüfen weder Schreibrecht noch
Testmodus. `can_edit` wird nirgends gesetzt.

**U6 Gleiche Regel mehrfach gebaut.** „Nächster Schultag“ steht siebenmal im
Code, „Stunde vorbei“ viermal, der Schuljahresbeginn viermal, die
Wiederholungsintervalle dreimal. Die Varianten unterscheiden sich im Detail
(Ferien, Ausfall, ausgeblendete Kurse). Ferien zählen in Lernplan und Kompass
als Schultage.

**U7 Lesepfade, die schreiben.** `rewards.summary`, `learning_plan.catalogue`,
`GET /materials/sources` und das Dashboard (startet sogar KI-Aufrufe) schreiben
beim Lesen. Das kostet Zeit, erzeugt Sperren (D200) und macht Rennen möglich.

## 2. Bugs nach Priorität

### P0: Datenverlust, Kosten, Sicherheit (zuerst)

| Nr. | Befund | Stelle | Fix |
|---|---|---|---|
| K1 | Konto-Abgleich nummeriert nur 49 von 81 Tabellen mit `account_id` um. Vokabelstand, Serien, Abzeichen, Materialien, `topic_answers` und `exam_topics` bleiben bei vertauschten IDs beim falschen Kind. Kein Test, keine Transaktion. (nachgeprüft) | `reconcile.py:32-63` | Tabellen aus `sqlite_master`/`PRAGMA table_info` bestimmen, alles in einem `BEGIN IMMEDIATE`, Test `test_reconcile.py` |
| K2 | Nächtlicher Kalenderabgleich löscht den Klausurplan, wenn IServ einmal mit Fehler antwortet: fehlende Antwort wird zu `[]`, `_store_events` leert das Fenster −30/+400 Tage. (nachgeprüft) | `school_calendars.py:133-160`, `iserv_portal.py:377-389` | Fehlt die Antwort, nicht speichern und Lauf als „partial“ protokollieren |
| K3 | Abbildungserkennung bezahlt dieselbe Seite alle 10 Minuten neu: eine unvollständige Antwort kommt als `HTTPException(502)`, wird nicht erfasst, `cycle()` bricht ab und nimmt beim nächsten Lauf wieder dieselbe neueste Seite. Bis zu 144 Aufrufe am Tag. (nachgeprüft) | `page_figures.py:83-126` | Jeden Fehler nach dem Aufruf mit Zähler in `material_figure_scans` festhalten, nach N Versuchen zurückstellen |
| K4 | Keine Sperre bei der Materialauswertung: Nachtlauf, Sammellauf, `retry_failed`, Upload-Task und „Neu auswerten“ lesen dieselbe Seite parallel und bezahlen doppelt. | `material_analysis.py:564-589`, `materials_worker.py`, `source_collector.py`, `triggers.py` | Atomarer Anspruch per `UPDATE … WHERE analysis_state IN (…)` mit `rowcount`, Ablauf nach N Minuten |
| K5 | Dauerhaft unlesbare Seiten werden jede Nacht und nach jedem Neustart erneut bezahlt, `_RETRIES` liegt nur im Speicher. Gleiches Muster bei `prepare_intros`, `map_entries`, Discovery. | `materials_worker.due()`, `triggers.py:87-121` | Persistenter Versuchszähler mit wachsender Pause und Endgültig-Grenze |
| K6 | Migrationslauf verschluckt halb eingespielte Migrationen: `executescript` ohne Transaktion, „duplicate column“ wird ignoriert, der Marker gesetzt, die restlichen Anweisungen laufen nie. Bei Migration 028 droht eine leere `lesson_checkins`. (nachgeprüft) | `db.py:858-881` | Jede Migration als eine Transaktion inklusive Marker, Anweisungen einzeln, „Spalte existiert“ gezielt über `_column_exists` |
| K7 | `/api/health` gibt ohne Anmeldung Kindernamen, Konto-IDs, DB-Pfade und Fehlertexte aus, über den Direktport also ins Internet. (nachgeprüft) | `routers/health.py` | Öffentlich nur `{"ok": true}`, Details hinter Admin oder Read-Key |
| K8 | Kiosk-Login wird sofort wieder überschrieben: die Middleware hängt an die 303-Antwort von `/kiosk/login` ein zweites `Set-Cookie` mit dem alten Wert. Nach einem PIN-Reset hängt das Küchen-iPad in einer Anmeldeschleife, ein Kindwechsel am Kiosk bleibt beim alten Kind. (nachgeprüft) | `main.py:184-214` | Nur auf `/api/`-Pfade anwenden, nur wenn die Anfrage per PIN-Session angemeldet war und die Antwort kein eigenes Cookie setzt |
| K9 | PIN ändern lässt alle alten Sitzungen gültig (365 Tage, gleitend). Eine verratene PIN zu ändern hilft nicht. (nachgeprüft) | `pin_auth.py:48-56` | In `set_pin` die Sitzungen des Nutzers löschen |
| K10 | Aussperren über den Direktport: `/api/auth/users` listet alle Nutzer mit PIN, der Fehlerzähler fällt nie zurück, ab der vierten Sperre gilt 24 h. Fünf Anfragen am Tag sperren ein Kind dauerhaft aus. | `pin_auth.py:88-138`, `routers/auth_router.py` | Sperre je Nutzer und Client-IP, Zähler verfällt, globales Login-Limit, Eltern-Reset hebt Sperre auf |
| K11 | Tests des Mentors verfälschen den Lernstand: „War nur ein Test“ und Löschen einer Sitzung lassen `topic_answers` stehen. Stufe „sitzt“, Raster und erledigte Planschritte bleiben. (nachgeprüft) | `routers/mentor.py` (`counts`, `delete_session`), `lernstand.answers_of` | Antworten der Sitzung ungültig markieren oder löschen, danach `lernstand.refresh`; alternativ JOIN auf `mentor_sessions.is_test=0` |

### P1: Falsches Verhalten im Alltag

| Nr. | Befund | Stelle | Fix |
|---|---|---|---|
| A1 | HA-Sync bildet den Dedup-Schlüssel aus den ganzen Notizen, die das Kind bearbeiten kann. Nach einer Notizänderung und neuer UID wird eine offene Aufgabe samt Unterpunkten gelöscht oder eine erledigte kommt als offene Kopie zurück. (nachgeprüft) | `sync_worker.py:40-50`, `routers/tasks.py:247-256` | Eigene Spalte `dedup_key`, nur vom Sync geschrieben |
| A2 | „Erledigt“ aus HA wird nur für `open` übernommen. Mit gestartetem Timer (`in_progress`) bleibt die Aufgabe für immer offen, der Tag wird nie „geschafft“. (nachgeprüft) | `sync_worker.py:195-205` | Jeden Status außer `done` behandeln wie `open` |
| A3 | Tagesabschluss, Morgen- und Nachmittagsmitteilung laufen nur für Konten mit eingeschalteter Abend-Erinnerung. (nachgeprüft) | `reminders.py:158` | Alle Konten mit Einstellungen durchlaufen, jede Mitteilung an ihrem eigenen Schalter prüfen |
| A4 | Tagesabschluss zählt fehlende Heftseiten-Fotos mit. Fehlt für eine Arbeit in 14 Tagen ein Foto, schließt kein Abend; Wochenrückblick meldet „0 von 5 Abenden“. (nachgeprüft) | `reminders.py:40`, `day_close.py:52` | `photos` nicht an `record_if_clear` übergeben |
| A5 | „Geschafft“ wird nur bei Aktionen des Kindes oder beim Öffnen der Seiten geprüft. Erledigen Eltern oder HA-Sync den letzten Punkt und öffnet niemand die App, reißt die Serie. | `rewards.py:132-148` | `evaluate()` in der Minutenschleife von `reminders.run_once` |
| A6 | Lesefehler nehmen Abzeichen zurück; beim nächsten Aufruf werden sie neu angelegt und ein zweites Mal gefeiert. | `rewards.py:97-107, 360-364`, `reward_extras.py:158-170` | „unbekannt“ von 0 unterscheiden, bei Quellenausfall nichts zurücknehmen |
| A7 | Beim Kindwechsel in der Elternansicht bleiben Daten des vorigen Kindes stehen. Kommt die Antwort zu Kind A spät, stehen deren IServ-Portal und Benutzername im Formular von Kind B, „Speichern“ schreibt sie auf B. Betrifft Einstellungen, Kurse, Klausuren, Arbeiten einrichten. (nachgeprüft) | `App.svelte:323-357`, `Settings.svelte:22-37`, `Klausuren.svelte`, `Courses.svelte`, `ExamSetup.svelte` | `{#key appState.activeAccountId}` wie bei Materialien und Vokabeln, dazu Schutz gegen veraltete Antworten |
| A8 | Kontext-Hash im Mentor enthält Analysezustand und andere Sitzungen. Fotografiert das Kind und sendet sofort, ändert die Hintergrundauswertung den Hash während des Zugs: 409, bezahlter Aufruf verworfen. | `mentor_context.py:226-227`, `routers/mentor.py:1624` | Nur stabile, fachlich relevante Teile hashen |
| A9 | Mentor-Kontext wächst über die 48-KB-Grenze. Gekürzt werden nur die Stunden; Nachrichten, Lösung (doppelt als Seite und Volltext), eingebundene Seiten und Quiz nicht. Danach scheitert jeder Zug mit 413. Gleiches in der Sprechprobe. | `routers/mentor.py:1540`, `oral_exam.py:317-349` | Kürzen nach Priorität mit Gesamtbudget inklusive Anweisung |
| A10 | Sperre von 120 s ist kürzer als ein möglicher Zug (zwei Versuche à 90 s plus 429-Wartezeit plus Buchseiten). Zweiter Tipp startet einen parallelen bezahlten Aufruf. | `routers/mentor.py:1409-1411` | Schwelle aus der maximalen Laufzeit ableiten, `asyncio.Lock` je Sitzung |
| A11 | Mentor-Zug startet synchron Chromium (bis 240 s, HA-Proxy bricht nach 100 s ab), ohne Negativ-Cache bei jeder Nachricht erneut. | `routers/mentor.py:1550`, `textbook_context.py:145-161` | Im Chat nur aus dem Bestand, fehlende Seiten an den Sammellauf geben |
| A12 | `help_count` gilt je Sitzung statt je Aufgabe; zusammen mit `condition()` (Kurzantworten wie „12“ gelten als einsilbig, ab 19 Uhr immer „spät“) bekommt das Modell abends fast immer „es fällt dem Kind schwer“. | `routers/mentor.py:1116-1133, 1687` | Zähler je Aufgabe, nur echte Ausweichantworten zählen, Uhrzeit-Schwelle prüfen |
| A13 | Ferien zählen im Lernplan und Kompass als Lerntage; bei einer Arbeit nach den Herbstferien ist die Tagesquote zu niedrig und „Auf Kurs“ falsch. | `study_plan.py:281-287`, `learning_compass.py:103-109` | Gemeinsame Schultag-Funktion mit `master_holidays` |
| A14 | Übungsklausur im Kindmodus am Elterngerät schreibt keine Nachweise, weil `user.role=='child'` statt Geräterolle geprüft wird. Gleiches Muster an weiteren Stellen. (nachgeprüft) | `routers/mentor_exams.py:302,331`, `:111`, `routers/learning.finish_session`, `practice._writable` | `acting_child`/`acts_as_parent` verwenden |
| A15 | Doppelseiten: `printed_pages` ist JSON, wird aber an zwei Stellen per `split(",")` zerlegt; die zweite Seite passt nie zu einer Hausaufgabe. (nachgeprüft) | `sources.py:641, 708` | Gemeinsamer Helfer mit `json.loads` |
| A16 | Abrufversuche für Buchseiten werden nie zurückgesetzt; ein Sitzungsfehler verbraucht die Versuche aller Seiten der Bestellung. Scheitert WebGL einmal, bleibt der Browser bis zum Neustart ohne GPU. | `source_collector.py:338, 447-452`, `textbook_browser.py:65-91` | Sitzungsfehler nicht je Seite zählen, Versuche nach Zeit zurücksetzen |
| A17 | Kapitel-IDs wechseln bei jedem Neulesen des Inhaltsverzeichnisses; Kapitelzuordnungen verwaisen still. | `book_structure.py:224, 717` | Upsert nach (Nummer, Ebene, Titel) oder Zuordnungen neu berechnen |
| A18 | Erste Lesestufe ist fest `klein`. Ist `klein` nicht eingerichtet (Standard in `config.yaml`), scheitert jede Materiallesung mit 503; die Elternwahl der Stufe wirkt dort nie. (nachgeprüft, live vermutlich eingerichtet) | `material_analysis.py:493, 541` | Stufe aus `tier_for` ableiten oder zurückfallen |
| A19 | Gescannte PDFs lesen bei jeder Neuauswertung ihre alte Modelllesung statt der Seiten; nur Seiten 1 und 2 werden gelesen. | `material_analysis.py:267` | Digitalen PDF-Text getrennt speichern |
| A20 | Kostenrahmen: eine einzige Überschreitung sperrt die ganze KI für alle Kinder bis zur Elternbestätigung; `opening_micro` wird beim Monatswechsel nicht zurückgesetzt; Hochrechnung am Monatsersten etwa siebenfach. | `ai_gateway.py:118-129, 285-311` | Überschreitung melden statt sperren, Monatswerte zurücksetzen, Fenster auf den Monat begrenzen |
| A21 | Jede angemeldete Anfrage schreibt `users.last_seen_at` und wartet bei einem laufenden Schreiber bis 30 s; über die PIN endet das mit 500. (nachgeprüft) | `auth.py:112-141` | Nur alle paar Minuten schreiben, kurzer Timeout, Fehler abfangen |
| A22 | Restore tauscht die Datenbank im laufenden Betrieb, Hintergrundschleifen schreiben in die umbenannte Datei, Arbeit blockiert den Event-Loop. | `backup.py:183-230`, `routers/backup.py` | Datei als „restore-pending“ ablegen, Add-on neu starten, beim Start tauschen |

### P1 in der HA-Komponente

| Nr. | Befund | Stelle | Fix |
|---|---|---|---|
| H1 | Lehrstoff wird nur nachgeholt, wenn WebUntis einen neuen Stundenplan-Import meldet. Einträge im Klassenbuch ändern den Zeitstempel nicht; Stunden fallen nach fünf Tagen ohne Lehrstoff aus dem Fenster. `lessons_missing_lstext` existiert, wird aber nie aufgerufen. | `coordinator.py:132-224`, `storage.py:1276` | Bei jedem Pull Stunden ohne Lehrstoff der letzten fünf Tage abfragen |
| H2 | Aus dem Stundenplan entfernte Stunden bleiben als Geisterstunden stehen (nur Upserts). | `coordinator.py:162-181`, `storage.py:861-957` | Nach erfolgreichem Abruf nicht mehr gelieferte Perioden im gelieferten Fenster als entfernt markieren |
| H3 | Gelöschte Fehlzeiten bleiben für immer, `was_absent` bleibt falsch. Der Kommentar „removed absences propagate“ stimmt nicht. | `storage.py:1043-1123` | Nicht mehr gelieferte Fehlzeiten im Fenster löschen oder markieren |
| H4 | Ein fehlerhafter Hausaufgaben- oder Fehlzeiten-Datensatz (`lessonId: null`) bricht den ganzen Pull ab, jedes Mal, alle Entities unavailable. | `coordinator.py:233, 255`, `storage.py:1433, 1477` | Normalisierung je Eintrag abfangen, `int(raw.get("lessonId") or 0)` |
| H5 | Sensor „Hausaufgaben offen“ wächst ohne Grenze, weil Untis `completed` praktisch nie setzt. | `storage.py:1176-1186` | Datumsgrenze oder Verschwinden-Erkennung |
| H6 | `is_late_addition` markiert fast jede neue Stunde der nächsten Woche als „nachträglich“. Das Add-on liest das Feld. | `storage.py:890-896` | `date < heute` |
| H7 | `async_shutdown` ohne `super()`: nach dem Entladen kann noch ein Refresh laufen und mit „storage not initialised“ scheitern. | `coordinator.py:91-94` | `await super().async_shutdown()` |
| H8 | Neu angelegte Integration bekommt ein neues Konto; die Historie hängt verwaist am alten (Schlüssel ist `entry_id`). Kein Reconfigure-Flow. | `storage.py:560-582`, `config_flow.py` | Rückfall auf (Server, Schule, Nutzer), normalisiert, `async_step_reconfigure` |

### P2: Kleinere Fehler

Diese Punkte sind echt, aber begrenzt in der Wirkung. Sie laufen im jeweiligen
Paket mit.

- Belohnungen lassen sich per API hochtreiben: Tasche ±30 Tage abhaken, Aufgaben anlegen und löschen, künftige Stunden vorab bewerten, „Weiß ich nicht“ bei Vokabeln zählt als Antwort und fürs Tagespensum (`routers/packing.py:22-79`, `tasks.py:213`, `routers/checkins.py:47-91`, `routers/vocab.py:204`). Das ist auch eine fachliche Frage, siehe Abschnitt 4.
- Familienkarte (`/api/dashboard`) und Kiosk prüfen keine Elternrolle; ein Kind mit PIN sieht „Beobachten“ und „späte Nutzung“.
- Aufgaben-Endpunkte umgehen Testmodus und Schreibrecht; ein Kind kann per API `skipped` setzen, das für „geschafft“ zählt.
- Schreibrechte in `routers/exams.py`, `courses.py`, `practice.py` (`reopen_for_grading`, `resolve_review`) ohne `write=True`; ein Kind kann `grade_points` setzen.
- Audit-Revert überschreibt neuere Änderungen blind und löscht bei geteilten Check-ins die Elterndaten (`routers/audit.py:89-189`).
- Session-Tokens liegen im Klartext in der DB und damit im Backup-ZIP (`pin_auth.py:141-159`).
- Notify- und Nutzungs-Token stehen im Query-String und damit im Access-Log der Add-on-Logs.
- Race bei der Neuanlage von Ingress-Nutzern: zwei Erstnutzer werden beide Admin (`auth.py:99-108`).
- Datei-Download mit Umlaut- oder Halbgeviertstrich im Namen endet mit 500 (`routers/materials.py:432`).
- `materials.remove` löscht Verknüpfungen vor der Kontoprüfung (`materials.py:659`).
- Papier-Vokabeltest bleibt nach einem Neustart für immer auf „grading“; Schlussblock nicht atomar, doppeltes Zählen möglich (`routers/vocab_daily.py:325-378`).
- Chip „Noch weitersprechen“ zählt in der Sprechprobe als Antwort des Kindes; `safe_choices` verwirft Navigations-Chips bei kurzen Antwortoptionen.
- Buchseiten 5 und 6 gelten als geliefert, der Mentor bekommt aber nur 1 bis 4 (`textbook_context.py:136-171`).
- Suche findet großgeschriebene Umlaute nicht, `%` und `_` werden nicht maskiert (`routers/search.py`).
- `history_schema` fängt „file is not a database“ nicht; das Add-on startet in Schleife neu.
- Frontend: Logout setzt `activeAccountId` nicht zurück („nicht verlinkt“ für das nächste Kind), Lazy-Seiten sterben nach einem Update, der Service Worker lädt beim ersten Besuch neu und cached unter Ingress nichts, `sendBeacon` rechnet Kindzeit den Eltern zu, Materialien verliert beim 4-s-Polling die Paginierung, die Familienkarte zeigt bei parallelen Stunden nur eine (Kopie von `dayStrip.js` ohne den D184-Fix).
- Skripte: `ha_activity.py` und `calibration_report.py` können bei einem curl-Fehler den Read-Key und die Ingress-Sitzung im Traceback ausgeben; `ha_activity.py` meldet 2 bei fehlendem Zugang und 1 bei jedem Absturz, was sich als „Kind aktiv“ liest.
- CI: `release.yml` interpoliert `inputs.version` direkt ins Shell-Skript und hängt nicht an den Tests; Frontend-Unit- und Browser-Tests laufen nicht in der CI; `parent_shell_browser.cjs` prüft die Fehlerliste vor dem Kindmodus-Teil und besteht trotz Seitenfehlern.

## 3. Unreife Stellen, die ich überarbeiten würde

**Große Module mit verdrehten Abhängigkeiten.** `routers/mentor.py` hat
1837 Zeilen, davon etwa 25 KB Prompt-Text und `_turn` als Zustandsmaschine
mit rund 250 Zeilen. Fachmodule importieren Router (`learning_compass` →
`routers.mentor`, `lernstand` → `routers.exams`, `study_plan` →
`routers.practice`). Ebenso groß: `vocab.py` (1646), `sources.py` (1518),
`textbook_browser.py` (1425, Verlagsheuristiken mit Inline-JS), `db.py`
(1264, zu 90 % Migrationen). Die IServ-Anmeldung steht sechsmal im Code.

**Vier Beherrschungsmodelle auf denselben Antworten.** `lernstand.replay`
(Stufen), `practice.row_of` (Raster), `learning_plan.replay` (Fähigkeiten),
`learning.next_review`. Der Kompass kann „sitzt“ und eine unsichere Zelle
gleichzeitig zeigen. Dazu zwei Planer nebeneinander (`learning_plan.build`
und `study_plan`); eine freiwillige Einheit kann die reguläre sperren.

**Wiederholungslogik der Vokabeln (D155).** „Sitzt“ braucht zwei richtige
Antworten ohne Abstand; `rank()` stellt das eben richtige Wort wieder nach
vorn, eine Einheit ist so in Minuten „sitzt“. Gefestigte Wörter werden nie
wieder fällig.

**Teure Anfragen.** N+1 in `vocab_progress` (je Einheit, Abschnitt und
Kasten ein `cards()`), `SubjectCatalog` liest je Instanz alle Stunden mit
`payload_json`, `mc.snapshot` liest ein Schuljahr und wird je Mentor-Zug
zweimal gebaut, `learning_plan.catalogue` schreibt je Fähigkeit.
`request_cache.scope()` greift nur an drei Stellen.

**KI-Aufrufe.** Das Schema wird nur als Text angehängt; Structured Outputs
würden die meisten Validierungsfehler verhindern. Dieselbe Seite geht für
Lesung, Abbildungen und Vokabeln getrennt ans Modell. `httpx.ConnectTimeout`
wird nicht wie `ConnectError` behandelt, „uncertain“-Reservierungen werden
nie abgeglichen, `RATES` weicht von der kommentierten Rechenregel ab.
Mehrere Chromium-Instanzen können gleichzeitig starten (OOM-Gefahr).

**Speicher.** Dateien als BLOB in `webapp.db` (170 MB), PNG-Screenshots in
`digital_textbook_pages`, Originalfotos außerhalb des Kontingents und ohne
Aufräumen, `audit_log` und `lesson_snapshots` ohne Löschfrist.

**Frontend.** Kein zentraler Umgang mit 401 und Timeouts im API-Client, kein
`svelte-check`/ESLint, sehr lange Zeilen in den Mentor-Komponenten,
Modals ohne Fokusführung, Lernen und Übersicht werden nicht lazy geladen.

**HA-Komponente.** Etwa 100 sequentielle `period/info`-Abrufe je Pull ohne
Drosselung, jede Zeile eine eigene Transaktion; alle Entities werden bei
WebUntis-Wartung unavailable, obwohl sie aus der lokalen DB lesen; kein
`diagnostics.py`, kein `backup.py` für die WAL-Datenbank, `hass.data` statt
`runtime_data`; Übersetzungen greifen nie, weil `_attr_name` gesetzt ist.

## 4. Entscheidungen, die bei dir liegen

1. **Belohnungsregeln gegen Hochtreiben:** Tasche nur für den nächsten
   Schultag am Vortag oder am Tag selbst, „Notiert“ nur für bestehende
   Aufgaben, Rückmeldungen nur für beendete Stunden, „Weiß ich nicht“ zählt
   nicht fürs Pensum und nicht für „Wortschatz“. Empfehlung: alle vier so
   umsetzen, bisher gesammelte Ereignisse nicht rückwirkend ändern.
2. **Vokabeln (D155):** zweiter Treffer zählt erst in einer neuen Sitzung
   oder nach einigen Stunden, gefestigte Wörter kommen nach 3/7/21/60 Tagen
   wieder. Empfehlung: ja, weil „sitzt“ heute nach Minuten erreicht wird.
3. **Kostenrahmen:** Überschreitung nur melden statt die KI zu sperren.
   Empfehlung: melden, Sperre nur bei Überschreiten der Monatsgrenze.
4. **Restore:** künftig mit automatischem Neustart des Add-ons. Empfehlung: ja.
5. **Kiosk und Familienkarte nur für Eltern.** Empfehlung: ja, das Kind hat
   eigene Seiten.
6. **Sessions nach PIN-Änderung:** alle Geräte abmelden (Kind muss auf dem
   iPad neu eingeben). Empfehlung: ja.

## 5. Umsetzung in Paketen

Jedes Paket ist ein eigenes Release mit Tests, Changelog, D-Nummer und
Versionssprung, eingespielt nur ohne laufende Lernsitzung (`ha_activity.py`).
Die Reihenfolge folgt Schaden und Risiko.

**Paket 1: Datenverlust und Kosten stoppen (1.31.2).**
K2, K3, K4, K5, K6, K11, A1, A2, A15. Kleine, lokale Fixes mit je einem
Test, der den Fehler zuerst rot zeigt. K1 (Konto-Abgleich) kommt dazu, weil
er zwar selten, dann aber schwer wirkt. Aufwand etwa ein Arbeitstag.

**Paket 2: Sicherheit (1.31.3).**
K7, K8, K9, K10, dazu Token-Hashing der Sessions, Token aus dem
Query-String, Race bei der Nutzeranlage, Rechte bei Kiosk und Familienkarte
(nach Entscheidung 5 und 6). Skripte: Schlüssel nie in argv oder Tracebacks.

**Paket 3: Grundlagen im Backend (1.32.0).**
Die Ursachen U1, U2, U5, U6 zentral lösen:
- `db.tx(conn)` als Kontextmanager mit `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK`, Mehrfach-Schreibblöcke umstellen, ein Test oder Lint gegen das nackte `with c:` bei mehreren Schreibzugriffen.
- Modul `clock.py`: `today()`, `now()`, `to_local_date(ts)`; alle `date.today()`, `datetime.now()` und `date('now')` ersetzen, gespeicherte UTC-Zeitstempel beim Lesen umrechnen. Die Uhr wird in Tests injizierbar.
- Modul `schoolday.py`: nächster Schultag, Stunde vorbei, Schultage bis Datum mit Ferien, Schuljahresbeginn. Behebt A13 mit.
- Eine Dependency `require_account(write=, parent=)` für alle Router, Geräterolle statt roher Rolle. Behebt A14 und die P2-Rechtepunkte mit. `TEST_BLOCKED` von Sperrliste auf Freigabeliste umdrehen.
- A21 (last_seen_at), A3, A4, A5, A6.

**Paket 4: Mentor robust (1.32.1).**
A8 bis A12: stabiler Kontext-Hash, Kontextbudget nach Priorität, Sperre
nach Laufzeit mit Lock je Sitzung, kein Chromium im Chat, Hilfezähler je
Aufgabe. Danach `routers/mentor.py` aufteilen in `mentor_prompts.py`,
`mentor_turn.py` (Service) und einen Materialien-Router, und die
Router-Importe aus Fachmodulen auflösen.

**Paket 5: Tempo (1.32.2).**
U3 und U7: schwere synchrone Arbeit aus `async def` in `def` oder
`asyncio.to_thread`, `pdftoppm` als asynchroner Prozess, Belohnungen als
Hintergrundaufgabe nach der Vokabelantwort. Lesepfade schreiben nicht mehr
(`rewards.summary`, `learning_plan.catalogue`, `GET /materials/sources`,
Dashboard ohne KI-Aufrufe im Mitlese- und Testmodus). N+1 in
`vocab_progress`, `SubjectCatalog` schmal und gecacht, `request_cache.scope()`
in den teuren Routern. Vorher und nachher messen (D200).

**Paket 6: HA-Komponente (0.6.0).**
H1 bis H8, dazu `backup.py` mit WAL-Checkpoint, `diagnostics.py`,
`runtime_data`, Entities bleiben bei WebUntis-Ausfall verfügbar,
Lehrstoff-Abruf nur für Stunden ohne gespeicherten Lehrstoff. Tests für die
Pull-Pipeline mit einem Fake-Client. Braucht einen HA-Neustart durch dich.

**Paket 7: Frontend (mit Paket 3 oder 5).**
A7 zuerst (Kindwechsel), dann Logout-Zurücksetzen, Lazy-Reload nach
Update, Service Worker, `sendBeacon`, Polling in Materialien,
Familienkarte auf `dayStrip.js`. API-Client mit Timeout und 401-Hook.
`svelte-check` in die CI.

**Paket 8: CI und Tests.**
`release.yml` an die Tests koppeln und `inputs.version` über `env:`
übergeben; Frontend-Unit-Tests und Browser-Tests in `tests.yml`;
`subjects_browser.cjs` und `parent_shell_browser.cjs` reparieren;
`pytest-homeassistant-custom-component` pinnen; ruff in die CI. Kann jederzeit
parallel laufen.

**Später, nach Beobachtung:** Vokabel-Wiederholung nach Entscheidung 2,
ein gemeinsames Beherrschungsmodell statt vier, ein Planer statt zwei,
Structured Outputs und eine gemeinsame Bildlesung für Text, Abbildungen und
Vokabeln (spart Kosten, braucht Eichung nach D129), Dateien aus der DB auf
die Platte, Migrationen als nummerierte Dateien mit `PRAGMA user_version`.
Das sind Umbauten mit Wirkung auf den Lernstand und die Kosten; sie brauchen
jeweils einen eigenen Entwurf.

## 6. Umsetzungsstand (26.09.2026, Schul-Cockpit 1.32.0, untis_archive 0.6.0, D207)

Umgesetzt: alle P0-Befunde (K1 bis K11), alle P1-Befunde (A1 bis A22, H1 bis H8), der größte Teil von P2, die Pakete 1, 2, 4, 6, 7 und 8 sowie aus Paket 3 und 5 der Transaktionshelfer `db.tx`, das Modul `schoolday.py` für Schultage mit Ferien, die Rechteprüfung mit Geräterolle in Lernen, Arbeiten und Aufgaben, die Datumsgrenzen nach deutscher Zeit an den gefundenen Stellen und die Tempo-Punkte (Fächerkatalog, Vokabel-Fortschritt, Lernplan liest ohne Schreiben, Kompass/Arbeiten/Fotos/PDF im Threadpool, Belohnungsprüfung nach der Antwort, Startbundle 92 auf 52 kB gzip).

Bewusst offen:
- Vokabel-Wiederholung mit zeitlichem Abstand (Entscheidung 2): verändert den Lernstand der Kinder, braucht einen eigenen Entwurf.
- Ein gemeinsames Beherrschungsmodell statt vier, ein Planer statt zwei, Aufteilen von `routers/mentor.py`, `vocab.py`, `sources.py`, `textbook_browser.py`.
- Structured Outputs und eine gemeinsame Bildlesung (braucht Eichung nach D129).
- Dateien aus der Datenbank auf die Platte, Migrationen als nummerierte Dateien.
- Ein zentrales `clock.py`: die gefundenen Datumsfehler sind behoben, aber `date.today()` steht noch an Stellen, die nicht falsch rechnen, solange der Supervisor `TZ` setzt.
- Geisterstunden (`lessons.removed_at`) filtert nur die Komponente; im Add-on noch nicht, weil Check-ins an `lessons.id` hängen.
- `vocab_pensum.school_days` kennt die Ferien noch nicht (kann `schoolday.project` übernehmen), `routers/plan.py` baut den Plan noch synchron.
- Noten eintragen dürfen Kinder weiterhin, weil die Oberfläche es ihnen anbietet; soll das nur für Eltern gelten, zuerst die Oberfläche ändern.
