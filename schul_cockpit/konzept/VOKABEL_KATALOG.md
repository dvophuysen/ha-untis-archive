# Geprüfte Buchbestände

## Vertrag

Der aktive Trainerbestand und ein neuer Import sind getrennt. Ein GET startet
keine Modelllesung und schreibt keine Kapitelzuordnungen. Vor einer Aktivierung
werden die Original-Hashes, der lückenlose geprüfte Seitenbereich, der
Seitenbeginn, alle Überschriften und Kastenenden sowie die Lernwort-Zuordnung
erneut geprüft. Ein Fehler rollt die Aktivierung vollständig zurück.

`vocab_sequence.py` verarbeitet physische Seiten aufsteigend. Laufköpfe öffnen
keine Einheiten. Eine Lücke verwirft den geerbten Kontext. Kastenenden beenden
auch die Unterabschnitte des Kastens. Gleichlautende Überschriften sind eigene
Vorkommen mit eindeutigen IDs. Strukturelle Konsistenz ist kein Beweis für
korrekt abgeschriebene Wörter: Quellenabgleich ist eine separate Bedingung.

## Modellgrenze

`vocab_mini.py` akzeptiert ausschließlich `gpt-5-mini` auf Foundry `2`.
Jede physische Seite wird in zwei überlappenden, ausreichend großen Ausschnitten
gelesen. Der Cache berücksichtigt Originalbytes, Ausschnitt, Protokoll, Prompt
und Modellkonfiguration. Rohantworten bleiben in `vocab_page_reads`; sie werden
nicht direkt zu Lernwörtern. Seitenzahlen des Betrachters gelten nicht als
gedruckte Seitenzahlen. Der Quellenabgleich muss auch Auslassungen, zusätzliche
Wörter, Bedeutungen, Reihenfolge und Überschriften prüfen. Eine Selbsteinschätzung
des Modells oder die Übereinstimmung zweier Modellantworten genügt nicht.

## Datenmodell und Lernstand

`vocab_catalog_runs` enthält unveränderliche, versionierte Buchbestände mit
Quellenverweisen, Gliederungsbaum und Fundstellen. `vocab_catalog_entries`
verknüpft jede Fundstelle mit einer bisherigen oder neu ergänzten Wort-ID.
`vocab_learning_aliases` verknüpft identische gedruckte Wörter innerhalb von
Kind und Sprache. Diakritika, Partikeln und Satzzeichen werden dabei erhalten;
unscharfe Präfixvergleiche sind ausgeschlossen. Gedruckte Bedeutungen werden
vereinigt. Verschiedene geschriebene Formen bleiben verschiedene Lernziele.

Alle alten `vocab_words`-Zeilen und alle `vocab_attempts` bleiben erhalten.
Gemeinsame Lernstände entstehen durch geordnetes Abspielen der verknüpften
Versuche, ohne die Versuche umzuschreiben. Nicht zugeordnete, bereits geübte
Wörter verhindern die Aktivierung. Die Prüfsumme des gesamten Lernverlaufs wird
vor und nach der Transaktion verglichen. Alte Buchbestände werden archiviert.

## Eltern-API

Unter `/api/accounts/{account_id}/learning/vocab/{subject}`:

- `POST /catalog-capture`, Body `{"pages":[186]}`: digitale Quellen zusätzlich
  in einem verborgenen Prüfbestand ablegen, ohne alte Originale zu ersetzen.
  `GET /catalog-capture` liefert den Auftragsstatus.
- `POST /catalog-read`, Body mit `start_page` und `pages` aus `material_id`,
  `number`, `side` (`full`, `left`, `right`): lückenloser Mini-Leselauf.
  `GET /catalog-read` liefert den Auftragsstatus; keine Aktivierung.
- `POST /catalogs`, Body `{"payload": ...}`: separaten Prüfbestand anlegen.
  Das Format ist in den Katalogtests dokumentiert. Ein Quellenreview enthält
  `method=source_visual_review`, `reviewer`, `row_count` und den SHA-256 des
  kanonischen JSON aus `rows`, `boundaries`, `begins`. Dies ist eine explizite
  Quellenprüfung durch den Reviewprozess, kein KI-Konfidenzwert.
- `POST /catalogs/{run_id}/activate`, Body `{"digest":"..."}`: exakt den zuvor
  geprüften Bestand transaktional aktivieren.
- `GET /word-list?unit=...&section=...`: eindeutige Wörter in Buchreihenfolge.

Aufträge überleben Prozessneustarts derzeit nicht als laufende Jobs; bereits
gespeicherte Seitenlesungen und Prüfbestände bleiben erhalten. Nach Neustart
darf ein Leselauf erneut gestartet werden: gleiche Seiten werden wiederverwendet.
Eine abgebrochene Quellenaufnahme kann bereits einzelne zusätzliche Aufnahmen
gespeichert haben; vor Wiederholung den Bestand prüfen.

## Prüfungen

`test_vocab_sequence.py` prüft Seitenübergänge und Hierarchien.
`test_vocab_catalog.py` prüft Isolation, Historienerhalt, Duplikate, Buchreihenfolge,
Quellenänderungen, Kontogrenzen, Elternrechte und zusätzliche Quellenaufnahmen.
`test_vocab_mini.py` prüft Modell-/Foundry-Bindung, Bild-Cache, Reihenfolge und
Kontogrenzen. Echte Buchseiten und Lernverläufe gehören niemals ins öffentliche
Repository. Buchbezogene Qualitätsmessungen werden privat separat aufbewahrt.
