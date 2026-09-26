# Vokabeltrainer: faire Bewertung und sichtbarer Fortschritt

## Vorbereitete Änderung, noch nicht produktiv freigegeben

- Richtige Antworten zählen unabhängig von ihrer Dauer. Seit 1.38.0 (D212) trägt jedes Wort eine Haltbarkeit in Tagen: auf Anhieb richtig heißt „sitzt“ (vorläufig sicher, drei Tage), jede richtige Antwort mit Abstand verlängert die Haltbarkeit (voll ×2,5 erst zum Termin), ab zwei Wochen heißt das Wort „gefestigt“. Eine falsche Antwort kürzt sie und setzt auf „wackelt“, bis das Wort wieder richtig kommt. Die Stufe sinkt nicht allein durch Zeitablauf; die Zeit macht ein Wort nur wieder fällig. Der Stand vom 25.09.2026 gilt als Startwert.
- Technische Transkriptionswartezeit wird in der neuen Oberfläche aus der Zeitmessung herausgerechnet. Ältere Sekundenwerte werden nicht rückwirkend geschätzt. Bestehende Versuche bleiben erhalten; ihre korrekten Ergebnisse werden nach der faireren Regel neu zusammengefasst.
- Rot: mindestens ein bewerteter Versuch, bisher kein richtiger. Gelb: schon richtig, aber noch nicht ausreichend bestätigt oder zuletzt wieder falsch. Grün: sitzt/gefestigt. Grau: noch kein bewerteter Versuch.
- Bedeutung und Schreibweise bleiben getrennt. Balken haben zusätzlich Textwerte; Farbe ist nicht die einzige Information.
- Gesamtübersicht pro Sprache: nur begonnene Einheiten, darin alle Lernwörter; gleiche Wort-ID zählt einmal. Hierarchie: Einheit, Abschnitt, Unterabschnitt/Kasten.
- Neue Versuche speichern die ausgewählte Einheit. Ein geübtes Wort, das später erneut vorkommt, markiert dadurch nicht automatisch spätere Einheiten als begonnen. Bei alten Versuchen ohne Auswahl ist nur eine eindeutige Wortzuordnung als Beginn ableitbar; mehrdeutige alte Zuordnungen werden nicht geraten. Eine reine Einheit mit solchen Altversuchen kann daher zunächst aus der Gesamtübersicht fehlen; ihre Wortstände bleiben sichtbar.

## Verbindlich vorgemerkt: Verlauf und Elternübersicht

- Tages-/Wochenverlauf: Anzahl sicherer, unsicherer, bisher nur falscher und neuer Wörter; zusätzlich tatsächlich geübte und neu gesicherte Wörter.
- Lernen, erneute Unsicherheit und bloß fällige Wiederholung unterscheiden. Eine fällige Wiederholung ist kein belegtes Verlernen.
- Bezugsmenge sichtbar halten: begonnene Einheiten, neu hinzugekommene Einheiten und Quellenänderungen. Eine größere Bezugsmenge darf nicht als Wissensverlust erscheinen.
- Drilldown vom Elternüberblick pro Kind/Sprache bis Kapitel und Abschnitt; dieselben Definitionen für Kinder und Eltern.
- Bewertungsänderungen als eigenes Ereignis markieren. Eine nachträglich fairere Berechnung darf nicht als zusätzlicher Lernerfolg an diesem Tag erscheinen.
- Für belastbare historische Diagramme zunächst Katalog-/Bewertungsversion und Neubewertungen nachvollziehbar speichern. Vorher keine irreführende rekonstruierte Erfolgskurve anzeigen.
- Spätere Übertragung auf andere Trainings ausdrücklich nach dem Vokabeltrainer.

## Nächste Qualitätsstufe: semantische Bewertung

Exakte Buchantworten und geprüfte Alternativen unmittelbar akzeptieren. Sonstige Bedeutungsantworten mit Mini in Foundry 2 prüfen: gleichwertig / Rückfrage / falsch. Auch unsichere positive Zeichenähnlichkeitstreffer prüfen. Keine schlechte Wertung bei technischen Fehlern. Buchangabe durch die App aus der Quelle ergänzen, nicht vom Modell erfinden lassen. Rechtschreibstufe bleibt getrennt.

Noch erforderlich: unabhängige Prüffälle, mehrdeutige Eigennamen und Teilantworten, Laufzeitmessung pro Antwort, Fehlerbehandlung, überprüfbare Neubewertung alter Fehlentscheidungen. Die erste kleine Kalibrierung ist kein Freigabenachweis.

Grammatikmuster benötigen einen eigenen Lernmodus. Unverständliche Transkripte vor einer Wissensbewertung bestätigen oder wiederholen lassen. Eine Selbstbestätigung darf nicht beliebige semantisch falsche Antworten automatisch richtig machen.

## Betrieb

Während einer laufenden Lernsitzung keine Installation und kein Neustart. Vor Veröffentlichung: Regressionstests, Frontend-Build und Zeitmessung mit simulierten langen Providerantworten. Lernhistorie nicht löschen oder durch Testläufe verändern.
