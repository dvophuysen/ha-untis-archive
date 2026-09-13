# Belegter Stand und nächste Arbeit

Stand: 13.09.2026. Codebasis: Release 0.28.1, GitHub-Commit 16a7c44c2c2fb41ad5ea55a0f4643fd336a05330. Konzeptfortschreibung ändert keine laufende App.

## Vorhanden

- Direkte Stundenbewertung mit drei Emojis; zusätzliche Aufsichtsmarkierung bei Vertretung. Abwesenheit/Ausfall in der Oberfläche gesondert behandelt.
- Hausaufgaben mit Erledigung und Teilaufgaben, Unterrichtsvorschau, Elternübersicht mit Mitlernen, Klausuren und Feedbacklücken.
- Gemeinsamer Lernplan für Plan, Nachmittagsplanung, Fächervorbereitung und Mentor; Tagesbelastung und Sieben-Tage-Vorschau.
- Mentorverläufe, Aufgabenbelege und Wiederholungszustände; Trennung zwischen Hilfe, Selbstbericht und selbstständiger Leistung sowie Demo/Kinderstand.
- Übungsklausuren mit Unterrichtsthemengruppierung, Ergänzung eigener Themen, Druck-, Online-, Foto- und Selbstkontrollpfaden im Code. Nicht alle Wege sind Ende-zu-Ende live abgenommen.
- Web-Push-Anmeldungen/Testfunktion und HA-Nachrichtenvorlagen vorhanden. Aktive Zustellung und Zeitsteuerung nicht aus bloßer Codeexistenz ableiten.

## Prüfbelege und Grenzen

51 automatisierte Lern-/Mentor-/Plantests sowie Frontend-Produktionsbuild für 0.28.1 bestanden. Live sichtbar geprüft: korrigierte Fachrotation in Wochenvorschau, aktualisierte nächste Unterrichtstermine und Kennzeichnung angerechneter Zeit ohne falsche Überlastungsmeldung. Die HA-Versionabfrage beim letzten Nachtest schlug fehl; die neue Oberfläche wurde direkt geprüft.

Geschichts-Demo: neun erfundene Stunden und drei Hausaufgaben ergeben drei auswählbare Themenbereiche. Klausurentwurf wurde erzeugt; sechs Aufgaben erschienen für 15 Minuten zu umfangreich. Nicht freigegeben. Zeitkalibrierung und kompletter Druck-/Foto-/Bewertungsdurchlauf bleiben offen. Tests ersetzen keine pädagogische Wirksamkeitsmessung.

## Durch Codeprüfung belegte Lücken

1. `routers/dashboard.py`: Mitlernen wertet 21 Tage alte Check-ins aus, ab drei Rückmeldungen und 30 Prozent gelb/rot; spätere Mentorfortschritte fehlen in dieser Berechnung. „Alles im grünen Bereich“ ist daher zu weitgehend.
2. `LessonCard.svelte` und `LessonDetail.svelte`: Notiz ohne Emoji setzt automatisch Bewertung 2. Organisatorische Kommentare können Unsicherheit vortäuschen.
3. `routers/notify.py`: identischer accountweiter Stand wird je verknüpftem Benutzer geliefert und im Nachrichtenvorschlag aufsummiert. Potenziell vervielfachte Zahl fehlender Rückmeldungen; tatsächliche HA-Nutzung dieser Vorlage noch prüfen.
4. Sieben Hauptziele für Kinder, zusätzlich Elternübersicht; ausführlicher Plan auch im Mentor. Informationsdichte und doppelte Wege bereinigen.
5. Keine integrierte kompakte Fachübersicht mit belegtem Trend und aufklappbarer KI-Tiefenanalyse.
6. Keine eigenständige strukturierte Erfassung externer Übungseinheiten; keine gespeicherte Material-Packliste im geprüften Stand.

## Vorgeschlagene Reihenfolge – noch keine fertigen Funktionen

1. Bestehende Daten-/Anzeigewidersprüche korrigieren und vorhandene Rückmeldewege erhalten.
2. Regeln und repräsentative Fälle für Fachzustand, Trend und unbekannten Stand festlegen. Kompakte Oberfläche daran entwerfen; keine scheinpräzise Gesamtnote.
3. Fachübersicht und konsistente Elternansicht auf gemeinsamem Datenbestand umsetzen, Details nur aufklappbar.
4. KI-Tiefenanalyse mit Quellen, Aktualitätsstand und begrenzten Kosten ergänzen; gespeicherte Analysen wiederverwenden.
5. Externe Übungen und Packbestätigung schlank in bestehende Fach-/Tagesansichten einfügen.
6. Klausurumfang kalibrieren und ausstehende Arbeitswege live prüfen.
7. Mit den Nutzenden Alltagstauglichkeit und Fortschritt beobachten; erst danach offene Gamification-Varianten auswählen.

Bei jeder Fortsetzung Remote-Stand, lokale Änderungen und Live-Version neu prüfen. Bereits gefundene Fehler nicht als behoben ausgeben, solange Codeänderung und Prüfung fehlen.
