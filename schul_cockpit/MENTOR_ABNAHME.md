## Ergänzung 0.26.0: getrennte Demo und echter Kinderstand

38 automatisierte Tests für Lernraum und Mentor bestanden. Zusätzliche Integrationstests prüfen: Demo-Chats funktionieren bei absichtlich gesperrtem Echtkontext-Zugriff; keine echten Materialien/Verläufe im Prompt; keine Demo-Lernnachweise; reale, frühere Eltern-Test- und neue Demo-Verläufe getrennt; Kinder können weder Demo öffnen noch starten; freigegebene Demo-Klausuren bleiben unsichtbar; Eltern lesen tatsächliche Kinderantworten ohne Schreibzugriff auf Antworten, Abgabe, Auswertung, Fotos oder Zeitstand. Frontend-Produktionsbuild erfolgreich.

Die Migration ergänzt Kennzeichnungen, erhält vorhandene Daten und ordnet bestehende Klausurversuche anhand der Benutzerrolle konservativ als Eltern-Test bzw. Kinderversuch ein. Unbekannte Benutzer bleiben als Test markiert.

# Abnahme des Lernmentors

Stand: 12. September 2026. Release 0.25.3. Entwicklungsauftrag: [MASTERPLAN.md](MASTERPLAN.md). Bedienung und Grenzen: [MENTOR_BETRIEB.md](MENTOR_BETRIEB.md).

## Nachgewiesen

- 35 automatisierte Backendtests bestanden. Enthalten: Berechtigung und Kindtrennung, Eltern-Testmodus ohne Kinderbelege, fortsetzbare Gespräche, doppelte Anfragen, veraltete Quellen, Hilfen, Zeit-/Aufrufgrenzen, atomare Budgetreservierung, unklare Nutzung, Fotoverarbeitung, feste Klausurversuche, bearbeitbare Entwürfe, halbe Punkte und Lösungsschutz.
- Frontend-Produktionsbuild erfolgreich. Live-Oberfläche im authentifizierten Browser bedient und visuell geprüft.
- Tatsächliches Azure-Responses-Deployment gpt-5.6-sol erfolgreich aufgerufen. Verbrauchsdaten wurden mit konservativen Kostensätzen abgerechnet.
- 30 feste fachliche Fälle durchgeführt: 29 Klassifikationen entsprachen der vorab definierten Erwartung. Beim verbliebenen Fall wurde eine bloße Wunschäußerung ohne Begründung als incorrect statt partial eingeordnet; die Begründung erkannte das fehlende Argument zutreffend. Das ist eine Bewertungsgrenze, kein allgemeiner Genauigkeitswert.
- Eltern-Testdialog: umgangssprachliche Unsicherheit, Erklärung, kurze Antwort „kp“, Hinweis, eigener Lösungsversuch und neue Aufgabenvariante. Kein Lernbeleg für das Kind erzeugt. Pause/Fortsetzen und Erhalt über den App-Neustart geprüft. Abschluss ohne zusätzlichen Modellaufruf.
- Automatische Themenerschließung für beide Kinder aktiviert. Je ein erster Hintergrunddurchlauf erfolgreich gespeichert; persistente Folgeplanung nachgewiesen.
- Beide Lernrahmen eingerichtet; maximal zehn Minuten und eine Mentoreinheit pro Tag. Vorhandene Tagesplanung bleibt maßgeblich. Freiwilliges Wochenende ist derzeit eingeschaltet.

- Überarbeitete Deutschübung mit drei Themen und 15 Minuten erstellt, gespeichert und veröffentlicht. Elternversuch vollständig durchlaufen: 6/6 für eine richtige Antwort, 5/6 bei einem absichtlichen Großschreibfehler, 4/6 bei fehlender Erklärung. Alle drei Ergebnisse entsprachen den geprüften Kriterien. Themenüberblick und nächste Schritte in der Oberfläche verifiziert; keine Kinderbelege aus dem Elternversuch.
- Beim Abschluss der Live-Prüfung rund 0,93 Euro konservative Budgetanrechnung für beide Konten zusammen, einschließlich einer durch einen Neustart unterbrochenen und weiter reservierten Anfrage. Das ist keine Azure-Rechnung und kein laufend aktualisierter Wert.

## Im Live-Test korrigiert

Einträge ohne Fachzuordnung blockieren keine Vorschläge mehr. Neue Aufgaben stehen bei ihrer Mentornachricht. Erkannte Themenfelder werden nur bei unverändertem Unterrichtsbeleg wiederverwendet. Rückmeldungen tragen eine ausdrückliche Bedeutung; Groß-/Kleinschreibung von Fachnamen trennt Hausaufgaben und Unterricht nicht mehr. Klausurentwürfe sind vor Veröffentlichung bearbeitbar, danach unveränderlich. Neue Klausuraufträge sollen sich per Text, Tastaturdiktat oder Foto beantworten lassen.

## Aussagegrenzen

Dies ist eine erste produktive Umsetzung der Mentorgrundlage. Die Prüfungen belegen technische Abläufe und die genannten Modellbeispiele, keine allgemeine pädagogische Wirksamkeit oder bessere Noten. Echte Kinderantworten, verzögertes Erinnern, Übertragung und Frustration müssen im Alltag beobachtet werden. Eine Prüfung auf einem physischen iPhone samt nativer Diktierfunktion und typischen Handschriften steht noch aus. Eigenständige Audioverarbeitung, automatische Landeslehrplanbeschaffung und umfassende PDF-Erschließung gehören weiter zum Masterplan.

Der gemeinsame 50-Euro-Rahmen umfasst die Lernaufrufe dieser App nach konservativer Anrechnung, nicht fremde Azure-Dienste. Die eingebauten Kostensätze müssen vor dem 1. Dezember 2026 erneut geprüft werden.
