# Offene Ansätze und zu entscheidende Fragen

Stand: 16.09.2026. Backlog zur gemeinsamen Klärung, kein verbindlicher Bauauftrag für alle Einträge.

## Vorgeschlagen am 17.09.2026 aus der Eichung

- Gebaut in 0.77.0 (D79): Plausibilitätsprüfung handschriftlicher Themenlisten: Seitenangaben des Zettels gegen die Stellen halten, die Unterricht und Hausaufgaben desselben Fachs seit der letzten Arbeit nennen; Abweichungen in der Gegenlese-Karte benennen („S. 70, 71 kommen im Unterricht nicht vor; gemeint S. 10, 11?“). Anlass: Jede Lesung las die handschriftliche 1 eines Kindes als 7 (D78).
- Gebaut in 0.78.0 (D81): Vorschlag der Prüfung mit einem Tipp übernehmen, je Seitenangabe als Ganzes.
- Seitenart als Steuerung der Modellwahl erst, wenn je Seitenart eine Messung mit Zahlen- und Zeilenvergleich vorliegt (D75, D77).
- Kontrollieren (0.78.0, D80) nach der ersten echten Kontrolle eichen: Lesbarkeit der Kinderhandschrift, Urteilsqualität je Aufgabe, ob das Modell trotz Verbot Ergebnisse nennt.

## Zurückgestellt am 16.09.2026 (D67)

- Gruppierung der Lerneinheiten nach Feld, Schuljahresgrenze 1. August, Doppelstunden als eine Behandlung, gemischte Einträge; Entwurf in [LERNEINHEITEN.md](LERNEINHEITEN.md). Offene Frage: Ist ein Oberthema selbst übbar?
- Abschreibmodell umstellen (D54): Eichung ist gebaut, das günstigere Modell nie aktiviert. Kostenhebel, Entscheidung der Eltern nach Eichung an echten Seiten.
- Kostensätze der Modelle laufen am 01.12.2026 ab; danach sperrt `ai_gateway` unbekannte Namen. Vorher prüfen und mit Datum neu hinterlegen.
- Sensor „Hausaufgaben offen“ der Integration widerspricht den Todo-Listen (Untis `completed` unzuverlässig). Entweder aus dem Todo-Abgleich speisen oder umbenennen.
- Vokabeltrainer: Kartenfoto für Stufe 2, Formen-Trainer Latein, Spanisch-Wortseiten als Material.
- Klausurseite: Fahrplan mit Tagen, Übungsfenster 60 Tage gegen „seit Ankündigung“, Weg von der Arbeit zur Materialablage.
- Materialablage Stufe 5: Chatanhänge übernehmen, Suche, Aufbewahrungsdauer, Benachrichtigung über neues Material.

## Fachübersicht und Analyse

- Verständliche Zustände statt einer 0–100-Zahl: seit 0.73.0 die fünf Stufen des Lernstands je Fach (D71). Offen: ob Übungsthemen aus dem Unterricht ohne Themenliste mitzählen sollen.
- Lernstand, subjektives Erleben und Organisation getrennt erfassen. Gewissenhaftes Abhaken darf kein Verständnis ersetzen.
- Fachzeile: Fach, knapper Zustand, Trend. Detail: Gelungenes, Offenes, nächster Schritt. Tiefe: KI-Einordnung und Belege.
- KI-Analysen anhand relevanter Datenänderungen zwischenspeichern; beim Öffnen nicht jedes Mal neu erzeugen. Modellwahl, Kostenobergrenzen und Aktualitätsanzeige definieren.
- Trends nur bei hinreichend vergleichbaren Aufgaben, Hilfen und Themen; neue schwierige Themen nicht als pauschale Verschlechterung des Kindes missdeuten.

## Oberfläche und Organisation

- Vorschlag: Heute, Plan, Lernen, Mehr; Elternübersicht als eigener Einstieg erhalten. Noch keine festgelegte Navigation.
- Ausführlichen Plan nicht gleichzeitig in Plan und Lernen wiederholen; beim Mentor nur Kontext der gewählten Aktion.
- Packliste in vorhandene Vorschau integrieren; Standardmaterial je Fach plus konkrete Sondermaterialien. Noch keine automatische Ableitung unbekannter Schulvorgaben.
- Außerhalb der App geübt: Thema, ungefähre Dauer, Unterstützungsart, optionale Unterlagen; KI-Zuordnung bestätigen lassen. Aufwand anrechnen, Können separat prüfen.

## Motivation

Ausgearbeiteter Entwurf: [Verantwortung übernehmen statt erinnert werden](VERANTWORTUNG.md).
Enthält Forschungsstand, Leitlinien und vier Vorschläge (Tagesabschluss mit Wenn-Dann-Plan,
sichtbare eigene Verlässlichkeit, verabredete Stufen der Übergabe, Wochenrückblick statt
täglicher Nachfrage) samt Reihenfolge und offenen Fragen. Noch nicht beschlossen.

Gamification bleibt offen. Kandidaten: sichtbare fachliche Fortschritte, dauerhafte Gestaltungselemente, Wochenmarkierungen und verlässlicher Tagesabschluss. Nicht beschlossen: Punkte, Streaks, Belohnungstausch und Sammelwelt. Nachtfristen, Verlustdruck und Bildschirmzeitmaximierung passen nicht zur Vision.

Erinnerungszeitpunkt und Häufigkeit mit den Nutzenden erproben; keine pauschal festgelegte Pushquote. Eine erledigte Handlung darf nicht erneut angemahnt werden. Bestehende HA-Automationen vor Ergänzungen prüfen.

## Zuschnitt der Lerneinheiten

Prüfbericht und Entwurf: [Zuschnitt und Reihenfolge der Lerneinheiten](LERNEINHEITEN.md).
Enthält die Durchsicht von 81 tatsächlich entstandenen Themen, sechs belegte Schwächen
und Vorschläge zu Gruppierung nach Fach, Reihenfolge ältestes offenes Thema zuerst,
nächtlicher Konsolidierung, Schuljahresgrenze und Doppelstunden. Der schwerwiegendste
Punkt ist behoben: Einträge, welche die Auswertung als organisatorisch eingestuft hatte,
erschienen trotzdem als Übungsaufgabe.

## Evaluation

Seit 0.74.0 gibt es den Wochenrückblick für Eltern (D72) als Ausgangslage. Vorgeschlagen bleibt: begrenzter Pilot mit verständlichen Beobachtungskriterien und gemeinsamer Rückschau. Dauer und Fächer offen. Interesse, Organisationszuverlässigkeit, selbstständige Leistung und Belastung getrennt betrachten. Kein automatischer Wirkungsnachweis und keine automatische Nachhilfeentscheidung.

## Quellen für die Einordnung, nicht als Beweis des Gesamtprodukts

- [EEF: selbstreguliertes Lernen](https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/metacognition)
- [Gamification-Metaanalyse 2024](https://link.springer.com/article/10.1007/s11423-023-10337-7)
- [Belohnungen und intrinsische Motivation](https://pubmed.ncbi.nlm.nih.gov/10589297/)
- [Duolingo: Streak-Experiment](https://blog.duolingo.com/improving-the-streak/) – Anbieterexperiment zur Nutzung, kein Nachweis nachhaltigen Lernens unserer Kinder.

## Materialien

- Material entsteht heute an drei Stellen ohne Verbindung: Chatanhang, Lernmaterial am Thema und Buchseiten aus dem Medienregal. Arbeitshefte, Blätter, eigene Mitschriften, digitale Hefte als PDF, bearbeitete Lösungen und zurückgegebene Arbeiten haben keinen gemeinsamen Ort.
- Der vorhandene Weg zum Ablegen ist für Kinder nicht erreichbar und für Eltern vierfach verschachtelt. Text muss von Hand eingetippt werden, sonst nutzt ihn weder Mentor noch Übungsklausur.
- Entwurf einer zentralen Ablage mit automatischer Einordnung: [Materialablage](MATERIALIEN.md). Enthält Datenmodell, Materialarten, Datumslogik, Neuauswertung, Schutz vor durchgereichten Lösungen sowie offene Fragen. Noch nicht beschlossen.

## Konkretisierter Folgeentwurf 13.09.2026

[Grafische Fächerübersicht](FAECHERUEBERSICHT.md): kompakte Balken, Mini-Verlauf und Drilldown. Darstellungs- und Bewertungsdetails dort ausdrücklich als Vorschläge markiert. Noch keine produktive Score-/Trendberechnung, Elternintegration zurückgestellt.
