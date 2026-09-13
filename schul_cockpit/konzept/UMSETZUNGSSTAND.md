# Optionale Erinnerungssicherung 0.30.0

Ein täglicher gebündelter Tagescheck für offene Aufgaben mit Fälligkeit bis morgen, noch nicht bestätigtes Fachmaterial für morgen und fehlende Rückmeldung zu beendeten heutigen Stunden. Kein KI-Aufruf, keine Ableitung eines tatsächlichen Versäumnisses aus fehlendem Häkchen. Standard aus; Eltern wählen ausdrücklich eine Zeit zwischen 14 und 21 Uhr (Europe/Berlin). Versand nur im folgenden 30-Minuten-Fenster. Kinder melden Geräte selbst an; Eltern erhalten keine automatischen Eskalationen.

Persistente Reservierung vor Versand verhindert Doppelversand nach Neustarts. Bei unklarem/fehlgeschlagenem Versand kein automatisches Wiederholen am selben Tag; Status sichtbar, Testweg vorhanden. Push-TTL 30 Minuten. Providerannahme ist kein Empfangsnachweis. Daten und Empfänger werden vor Versand erneut geprüft. Ungültige Geräte (404/410) werden entfernt; Transporttimeout zehn Sekunden. Neue Geräte werden nur für unterstützte HTTPS-Pushdienste registriert. Account-Reconciliation bezieht Packlisten und Erinnerungen ein.

Service Worker ergänzt Push-/Klickhandler mit auf die App begrenzten Links. Alle privaten API-Aufrufe umgehen seinen Cache; API-Antworten erhalten no-store. Alte Cacheversion wird bei Aktivierung gelöscht. Offline wird für diese Daten ein Fehler statt eines alten Erledigungsstands gezeigt.

Prüfung: 71 Python-Tests aus Lern-/Mentor-/Plan-/Pack-/Integritäts- und Erinnerungsbereichen (70 gemeinsam, zusätzliche Account-Neuzuordnung separat); Service-Worker-Ereignistest für Anzeige, fehlerhafte Payload, sichere Links und API-Cacheausschluss; bestehende Browserabläufe plus Eltern-Zeitwahl und Kinder-Leseansicht; Produktionsbuild. Reale Registrierung/Zustellung auf Kindergeräten noch nicht abgenommen, keine echte Nachricht versendet, keine Uhrzeit eingeschaltet.

Nutzung: Einstellungen → Erinnerungen. Im Elternkonto Zeit speichern/einschalten; im Kinderkonto auf dem betreffenden Gerät anmelden und Testnachricht prüfen. Auf iOS/iPadOS als Home-Screen-Web-App und nach ausdrücklichem Tippen auf Anmeldung; siehe [WebKit-Dokumentation](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/). Ruhe-/Fokus-Einstellungen können die Anzeige beeinflussen. Fehlende Empfangsbestätigung wird nicht als Kinderfehler interpretiert.

Weiter: echte Geräteabnahme und Alltagserfahrung; danach bedarfsgerechte zusätzliche Zeitfenster, Mentor-Coaching und faire optionale Erfolgsrückmeldung. Aktuell eine tägliche Fangleine, kein vollständiges Mehrphasen-Reminder-System.

---

# Materialcheck im Stundenplan 0.29.4

Packen zeigt den vollständigen nächsten Schultag in chronologischer Reihenfolge einschließlich Ausfällen, Anfang/Ende, Raum- und Lehrerwechseln. Beim ersten stattfindenden Vorkommen jedes Fachs steht ein Material-Häkchen, danach kein weiteres für dasselbe Fach. Doppelstunden bleiben als Zeiten sichtbar. Ausgefallene/abwesende Stunden erzeugen kein Material-Häkchen. Ausgeblendete Kurse bleiben ausgeblendet.

Allgemeine Packpunkte Mäppchen und Trinken entfernt; alte gespeicherte Fachschlüssel bleiben gültig. Alte allgemeine Bestätigungen werden nicht mehr gezählt. Morgens derselbe Stundenplan für heute, nächster Schultag weiterhin vollständig sichtbar. Keine getrennten doppelten Vorschau-Karten.

Hausaufgabenabschluss verkürzt und mit Party-Emoji gestaltet. Fehler beim Laden zeigen weiter einen Fehler statt falscher Entwarnung. Keine variable KI-Textgenerierung nötig.

Prüfung: sechs Packlisten-API-Tests, Produktionsbuild und Tagesdashboard-Browserablauf mit synthetischen Daten. Doppelstunden mit einem Häkchen, sichtbarer Ausfall/Raumwechsel, Speicherung/Fehler, Abend-Morgen-Erhalt und 320/390/768 Pixel geprüft. Darstellung geprüft; Testsystem hat weiterhin unvollständige Emoji-Schriften. Live-Installation separat bestätigen.

---

# Gemeinsame Farb- und Navigationsgestaltung 0.29.3

Petrol als Handlungsfarbe; Mint für Packen/freies Üben, Blau für Schule, Lavendel für Lernvorschläge. Farben dienen Orientierung, nicht einer neuen Leistungsbewertung. Heller und dunkler Modus verwenden abgestimmte Flächen. Hauptnavigation und Lernreiter kombinieren Emoji und Text; aktive Zustände zusätzlich per Fläche/Schrift und zugänglichen Attributen.

Kinder sehen im Mentor kompakte aktuelle Empfehlungen statt der vollständigen zweiten Wochenplanung. Freie Wahl und Aufgaben bleiben sichtbar, Detailplanung bleibt erreichbar. Fokusdarstellung und reduzierte Bewegung ergänzt.

Prüfung: Produktionsbuild und vorhandene Browserabläufe für Tagesdashboard, Packen, Kinderwahl/Übungstests, Elternfreigabe und Löschung erfolgreich; 320/390/768 Pixel ohne horizontales Überlaufen. Helle/dunkle Screenshots geprüft. Test-Chromium hat keine vollständigen Emoji-Schriften; tatsächliche Apple-Emoji-Darstellung nicht damit abgenommen. Backend unverändert. Bestehende Barrierefreiheitshinweise nicht vollständig bereinigt.

---

# Freies Üben und gezielte Verlaufskorrektur 0.29.2

Freie Fachwahl steht direkt vor den Vorschlägen. Offene Hausaufgaben sind als Übungsanlass auswählbar; ein Kalendereintrag ist keine Voraussetzung. Kinder können Fach, Themen und Dauer eines Übungstests selbst wählen. Bestehende Konto-/Schreibrechte, KI-Freischaltung und Kostenkontrolle bleiben wirksam. Kinderentwürfe werden direkt als nutzbare, noch nicht elterngeprüfte KI-Übungen gespeichert. Elternprüfung und isolierte Demo bleiben erhalten. Bestehende Elternentwürfe benötigen die sichtbare Freigabe, damit Kinder sie sehen.

Eltern-Löschweg: Lernen → Gespräche → Einheit öffnen → Diese Einheit entfernen → Einheit endgültig löschen. Version und laufende Bearbeitung werden vor der Transaktion geprüft. Nachrichten, Anhänge, Belege und Planzeit werden entfernt; betroffene Lernstände und Wiederholungen aus verbleibenden Belegen neu berechnet. Kostenbuchungen bleiben erhalten. Keine pauschale Löschung anderer Übungen.

Prüfung: 63 Python-Tests aus Lernraum, Mentor, Lernplan, Packliste und Rückmeldeintegrität; Produktionsbuild; Browserfälle mit synthetischen Kinder-/Elternkonten für freie Fachwahl, Hausaufgaben-Übungstest, verborgene Lösungen, Eltern-Leseansicht/Freigabe und erfolgreiche/fehlgeschlagene Löschung. Tagesdashboard-Browserprüfung ebenfalls bestanden. Kein vollständiger Live-Schreibtest in echten Kinderkonten; vorhandener Integrationszugang ist nur lesbar.

---

# Gespeicherte Packcheckliste 0.29.1

Direkt sichtbare Checkliste im Tagesdashboard, morgens für den aktuellen und danach für den nächsten Schultag. Bestätigungen bleiben pro Konto und Datum erhalten. Ausfall, Abwesenheit und ausgeblendete Kurse werden berücksichtigt; unbekannte Unterrichtsdaten werden nicht als vollständige Packliste ausgegeben. Materialien bleiben allgemein, etwa Sportzeug und Fachunterlagen. Konkrete Sondermaterialien aus Unterrichtsnotizen werden noch nicht ausgewertet.

Additive Datenbankmigration; stabile Materialschlüssel bewahren Bestätigungen bei Raum- und Zeitänderungen. Neue Fächer öffnen nur neue Punkte. Schreibrechte, Demo-Schutz, Versionskonflikte und Quellenänderungen werden serverseitig geprüft. Elternbestätigungen speichern die tatsächliche Benutzerkennung; aus Häkchen wird keine eigenständige Leistung des Kindes abgeleitet.

Prüfung: 60 Python-Tests, vier JavaScript-Tests, Produktionsbuild sowie Browserprüfung mit synthetischen Daten für Speicherfehler, Neuladen und 320/390/768 Pixel. Bestehende Svelte-Barrierefreiheitshinweise bleiben; kein Nachweis für echte Geräte oder Push-Zustellung. Live-Installation wird separat dokumentiert.

Nächstes Paket: konfigurierbare, gebündelte Erinnerungen anhand tatsächlich offener Aufgaben und Packpunkte. Zeitfenster und Geräte vor Aktivierung konkret abstimmen. Mentor-Checklisten, gemeinsame Fachauswertung, Elternübersicht und optionale Erfolgsrückmeldungen bleiben weitere Phasen.

---

# Tagesdashboard 0.29.0

Erster Umsetzungsschritt des UI-Redesigns: direkt sichtbare Tagesaufgaben und Lernvorschläge, offene Rückmeldungen mit erreichbarem Verlauf, allgemeine nächste Schulvorschau und reduzierte Hauptnavigation. Vorhandene Direktlinks bleiben erhalten. Elternstart anhand der Rolle statt nur der Kontenzahl.

Prüfung: 55 bestehende Python-Tests; vier neue JavaScript-Tests für Tagesaufteilung und Datumsgrenzen; Browserprüfung am Produktionsbuild mit synthetischen Daten für erfolgreiche/fehlgeschlagene Speicherung, sichtbare Aufgabenbereiche und 320/390/768 Pixel. Helle und dunkle Screenshots geprüft. Bestehende Svelte-Barrierefreiheitshinweise bleiben. Echter iPhone-/PWA-Betrieb und Zustellung von Push wurden damit nicht geprüft.

Packbestätigungen, Reminder-Zeitsteuerung, Belohnungen, vollständige Zusammenführung der Fachbewertung und weitere Mentorinteraktion sind Folgepakete. Kein vollständiger Abschluss der Gesamtvision. Veröffentlichung und Live-Version werden separat dokumentiert.

---

# Korrekturpaket 0.28.2

Stand: 13.09.2026. Ausgangspunkt: Remote 58cf623, laufende App 0.28.1 über Supervisor und Health-API bestätigt. Zunächst geprüfter Code; Veröffentlichung und Live-Abnahme separat nachtragen.

- Kommentar ohne Emoji erzeugt keine Bewertung. Transaktionale Migration erhält alte Werte, IDs, Zeitstempel und stabile Unterrichtsbezüge. Keine rückwirkende Interpretation alter Kommentare.
- Verständnisstatistik zählt nur 1–3; Aufsicht und Kommentare sind ausgeschlossen. Notizen ohne Bewertung bleiben als Rückmeldelücke sichtbar.
- Erinnerungszahl ist accountweit. Bestehende Benutzerfelder bleiben kompatibel. In durchsuchbaren HA-Automationen und Skripten kein Treffer für `checkin_reminder` oder `unrated_lessons_today`; keine Zustellwirkung nachgewiesen, keine Nachricht versendet.
- Elternansicht begrenzt ihre Aussage auf Unterrichtsrückmeldungen. Spätere Mentorfortschritte einzubeziehen bleibt Aufgabe der gemeinsamen Fachauswertung.
- 55 Lern-/Mentor-/Plan-/Integritätstests bestanden. Produktionsbuild erfolgreich mit bestehenden Svelte-Barrierefreiheitshinweisen. Neue Version noch nicht live geprüft.

Vor Installation einen Wiederherstellungspunkt der App-Daten vorhalten. Alter Code allein ist nach neuen NULL-Bewertungen kein vollständiger Rückweg. Wiederherstellung alter App-Daten würde spätere Eingaben verlieren; bevorzugt vorwärts korrigieren. Migration lokal auf Datenerhalt und wiederholten Start geprüft.

Nächster Produktschritt: Fachzustände und iPhone-Vorschau mit repräsentativen Fällen ausarbeiten. Bewertungs-/Trendregeln vor produktiver Nutzung entscheiden.

---

## Historischer Stand

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
