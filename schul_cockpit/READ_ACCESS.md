# Dauerhafter Nur-Lese-Zugang zum Schul-Cockpit

Ab Version 0.23.3. Dieser Zugang wurde vom Eigentümer für wiederkehrende Datenanalysen ausdrücklich angefordert. Eine neue Unterhaltung erbt nicht automatisch einen Browser-Cookie, benötigt mit dieser Schnittstelle aber keine PIN-Sitzung.

## Autorisierung und Speicherung

Home-Assistant-App-Optionen:

- `learning_read_token`: zufälliger dedizierter Schlüssel, mindestens 32 Zeichen; im Optionsschema als Passwort markiert. Nicht ins Repository, in Berichte oder in Chatantworten schreiben. Wird nicht an KI-Modelle geschickt.
- `learning_read_accounts`: explizite kommaseparierte Archiv-Konto-IDs, z. B. `1,2`. Keine automatische Freigabe neu angelegter Kinder.

Der Schlüssel wird in der bestehenden HA-App-Konfiguration gespeichert, bleibt über Neustarts/Updates erhalten und ist mit HA-Backups zu schützen. Passwortfeld bedeutet maskierte Darstellung, kein Versprechen zusätzlicher Verschlüsselung im Supervisor. Leeren/Wechseln des Schlüssels oder Änderung der Kontoliste mit anschließendem App-Neustart widerruft/ändert den Zugang.

Der Dienst kann ausschließlich festgelegte Daten lesen. Er kann weder Aufgaben ändern noch SQL ausführen, keine Benutzer-/PIN-/Sitzungstabellen lesen und keine Azure- oder Benachrichtigungsschlüssel abrufen. SQLite wird mit `mode=ro` und `query_only=ON` geöffnet. Rohdaten-Payloads und Binärdateien werden nicht ausgegeben. Der Schlüssel ist kein PIN- oder Administratorkonto und funktioniert nicht als Anmeldung an normalen schreibenden App-Routen.

## Abruf mit bestehender Home-Assistant-Verbindung

1. Über `ha_get_app(source="installed")` die Schul-Cockpit-App ermitteln, danach Details dieser App lesen. Slug nicht aus anderen Installationen übernehmen.
2. Aus `structuredContent.addon.options` ausschließlich `learning_read_token` intern übernehmen. Optionsobjekt, Token und andere vorhandene Zugangsdaten niemals ausgeben. `learning_read_accounts` enthält den freigegebenen Umfang. Wenn Toolausgabe oder Zugangsdaten nicht verfügbar sind: keine Identität vortäuschen oder Zugriffsschutz umgehen.
3. Über `ha_manage_app` mit `slug`, `method="GET"`, `path="/api/integration/learning"` und `request_headers={"X-Learning-Read-Key": token}` das authentifizierte Manifest lesen. Nicht den Token als URL-Parameter senden.
4. Datensätze über dieselbe Verbindung abrufen; zunächst `accounts`, dann nach Bedarf `master_schoolyear`, `lessons`, `homework`, `lesson_checkins`, `caught_up`, `tasks`, `hidden_courses` usw. Namen der Kinder über `accounts` prüfen, keine Konto-ID aus dem Gedächtnis voraussetzen.

Die bestehenden Berechtigungen des HA-Plugins bleiben Voraussetzung. Dieser Zugang erweitert nicht die Verfügbarkeit des Plugins in einer Session. Bei direkter externer Nutzung ausschließlich die bestehende HTTPS-Adresse verwenden; keine neue Portfreigabe nötig. Der Supervisor-Proxy verwendet den bestehenden internen App-Zugriff.

## API

`GET /api/integration/learning` liefert Version, Kontofreigabe, feste Datensätze und die Bedeutung ihrer Filter.

`GET /api/integration/learning/{dataset}?account_id=1&limit=100&after=0`

- `account_id` erforderlich und auf konfigurierte IDs begrenzt.
- `limit`: 1–250, Standard 100. Kleine Seiten vermeiden abgeschnittene Toolantworten.
- `after`: letzter `_cursor` aus der vorherigen Seite. Weiterblättern, solange `has_more=true`; dann `next_after` verwenden. Filter beim Weiterblättern unverändert lassen.
- `start`, `end`: inklusive ISO-Daten, bezogen auf `date_basis` im Manifest. Beispiel Unterricht: `lessons?account_id=1&start=2026-08-01&end=2026-09-12`.
- `updated_since`: ISO-Zeitstempel, nur bei vorhandenem `modified_basis`. Inklusive Grenze. Bei inkrementellen Abrufen kleine Überlappung und Deduplizierung verwenden.
- Nicht unterstützte Filter werden mit 422 zurückgewiesen. Unbekannte Datensätze: 404. Nicht freigegebene Kinder: 403. Fehlender/falscher Schlüssel: 401. Deaktivierter Zugang oder nicht lesbare Quelle: 503.
- `available=false` bedeutet Tabelle in dieser Version nicht vorhanden. `missing_columns` nennt bekannte, aber in dieser Datenbankversion nicht vorhandene Spalten. Beides darf nicht als belegtes „keine Daten“ interpretiert werden.

Abfragen sind pro Seite konsistente Lese-Transaktionen, aber kein gemeinsamer Snapshot über beide Datenbanken oder alle Seiten. Während längerer Exporte können Änderungen eintreffen. Löschungen lassen sich nicht über `updated_since` erkennen; dafür regelmäßig vollständig abgleichen. Rohe Datensatz-IDs sind nur innerhalb der jeweiligen Tabelle eindeutig.

## Zusammensetzen für Schuljahresanalysen

1. Jahresgrenzen aus `master_schoolyear` lesen, gegen tatsächliche Unterrichtsdaten prüfen. `master_schoolyear.startDate` beschreibt die Jahresgrenze, nicht notwendigerweise den ersten Unterricht nach Ferien.
2. `lessons` nach Zeitraum abrufen. `code=cancelled`, Aufsichten und persönliche `hidden_courses` vor Summenbildung berücksichtigen. Manuelle Stoffkorrekturen haben Vorrang vor `lstext`.
3. `lesson_checkins` und `caught_up` für das Kind lesen und über `lesson_id` mit den ausgewählten Stunden verbinden. Die Datumsfilter dieser Tabellen beziehen sich auf Bearbeitung, nicht auf das Datum der Unterrichtsstunde; deshalb nicht allein damit das Unterrichtsschuljahr eingrenzen.
4. `homework.untis_lesson_id` ist ein Untis-Bezug, nicht automatisch der lokale Schlüssel `lessons.id`. Nur bei nachgewiesener Semantik verknüpfen, andernfalls Fach-/Datumsnähe als vermutete Zuordnung kennzeichnen. `tasks.lesson_id` ist ein separater expliziter App-Bezug.
5. `tasks.status`, Teilaufgaben und Zeitprotokolle vom Archivfeld `homework.completed` getrennt halten; Synchronisationsstatus ist kein sicherer Kompetenznachweis.
6. Fehlzeiten als Zeitintervalle mit `start_time`/`end_time` der Stunden überschneiden. Eine 2-Minuten-Verspätung ist nicht eine vollständig versäumte Stunde. Feiertage und Kursbelegung berücksichtigen.
7. Lernversuche bleiben Selbsteinschätzungen, sofern kein unabhängiger Leistungsnachweis vorliegt. Hinweise und Musterlösungen im Snapshot beeinflussen die Aussagekraft.
8. Kalenderkonfiguration, manuelle Prüfungen und Overrides mit aktuellen HA-Kalenderereignissen zusammenführen. Hinweise in Aufgaben/Unterricht können Prüfungen nennen, die noch in keinem Kalender stehen.

## Betrieb und Prüfung

- Rückgaben: `Cache-Control: private, no-store`; Service Worker speichert diese Routen nicht.
- Automatisierte Tests prüfen Zugang deaktiviert, falschen Schlüssel, Kontogrenze, Schreibverbot, Ausschluss von Geheimnissen, Datums-/Änderungsfilter, Pagination und Schlüsselwechsel.
- Installation erfordert keine Migration der Schülerdaten. Bestehende PIN-Anmeldung und Azure-Konfiguration bleiben erhalten.
- Ein Neustart mit gespeichertem Schlüssel und ein anschließender authentifizierter Abruf dienen als Persistenzprüfung. Eine spätere Session liest diese Anleitung und die konfigurierte Verbindung erneut ein.
