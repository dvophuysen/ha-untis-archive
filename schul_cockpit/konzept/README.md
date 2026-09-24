# Konzept und Projektgedächtnis

Stand: 24.09.2026, live 1.13.16. Einziger maßgeblicher Einstieg für die fachliche und produktbezogene Weiterentwicklung des Schul-Cockpits.

## Lesereihenfolge für jede Fortsetzung

1. [Vision](VISION.md): Warum das Produkt existiert und woran wir Erfolg messen.
2. [Entscheidungen](ENTSCHEIDUNGEN.md): ausdrücklich gesetzte Anforderungen, Grenzen und verworfene Ansätze.
3. [Offene Ansätze](IDEEN.md): Vorschläge und Fragen; keine automatisch freigegebene Umsetzung.
4. [Umsetzungsstand](UMSETZUNGSSTAND.md): belegter Bestand, bekannte Lücken; oben der Überblick seit 1.5.0.
5. [Übergabe](UEBERGABE.md): was live läuft, was offen ist, Arbeitsweise.
6. Die Arbeitspakete unten, soweit das Thema sie berührt.
7. Erst danach betroffene Implementierung und Live-Zustand prüfen.

## Verbindlichkeit und Fortschreibung

Aktuelle ausdrückliche Nutzeranweisungen haben Vorrang. Innerhalb der Dokumente gelten die datierten Entscheidungen vor älteren Konzeptentwürfen. Vision ist das Ziel, nicht die Behauptung fertiger Funktionen. Ein Vorschlag des Assistenten wird durch bloßes Aufschreiben nicht zur Nutzerentscheidung.

Bei neuen Entscheidungen: Kennung, Datum, Herkunft und Begründung ergänzen; abgelöste Entscheidung markieren statt stillschweigend löschen. Neue Ideen nur in IDEEN.md sammeln. Nach Umsetzung UMSETZUNGSSTAND.md mit Release/Commit und Prüfbeleg aktualisieren. Änderungen gemeinsam mit dem betroffenen Code versionieren. Keine PINs, API-Schlüssel, Unterrichtsunterlagen oder persönlichen Lerndiagnosen in dieses öffentliche Repository schreiben.

Eine neue Session muss diese Dateien ausdrücklich lesen. Ihre Speicherung garantiert keinen automatischen Kontextabruf durch jedes Chat-System. Einstiegssatz: „Arbeite im Repository dvophuysen/ha-untis-archive weiter; lies zuerst schul_cockpit/konzept/README.md und die dort verlinkten Dokumente.“

## Laufende Arbeitspakete

- [Quellen](QUELLEN.md): der Quellenbestand. Welche Buchstelle hinter einer Aufgabe steht, wie sie eingesammelt, abgelegt und geprüft wird, was eingescannt werden muss. Enthält belegte Befunde zum Seitenabruf aus dem Medienregal und den Stand der Pakete 1 bis 3.
- [Verantwortung](VERANTWORTUNG.md): Erinnerungen, abgeleiteter Tagesabschluss, Morgen-Rückfall.
- [Lerneinheiten](LERNEINHEITEN.md): wie Übungsthemen entstehen und gruppiert werden.
- [Materialien](MATERIALIEN.md): zentrale Materialablage, Materialarten, Neuauswertung.
- [Arbeitsblätter](ARBEITSBLAETTER.md): Blätter ohne Nummer und ihr Bezug zu Aufgaben und Stunden.
- [Vokabel-Katalog](VOKABEL_KATALOG.md): geprüfte Buchbestände für den Vokabeltrainer (D152, D153).
- [Vokabeltrainer: faire Bewertung und Fortschritt](../../docs/vocabulary-learning-quality.md) und [Bedeutungsprüfung](../../docs/vocabulary-answer-quality.md) (D155 bis D157).

## Arbeitsweise

Vor jeder Änderung liegen drei Dinge vor: was das Problem ist, was gebaut würde, und woran man merkt, ob es hilft. Der Nutzer entscheidet; gebaut wird nur, was auf der Liste steht. Reine Diagnose — Daten lesen, messen, nachsehen — braucht keine Rückfrage. Siehe D36.

## Technische Referenzen

- [Changelog](../CHANGELOG.md), [Installation und Nutzung](../DOCS.md), [Lesezugang](../READ_ACCESS.md), [UI-Gestaltung](../UI_DESIGN.md).
- Archiviert, mit Stand um 0.28: [Lernplan-Verzahnung](archiv/LERNPLAN_VERZAHNUNG.md) (gemeinsamer Planungsdienst `learning_plan.py` und Wiederholungen), [Mentor-Betrieb](archiv/MENTOR_BETRIEB.md), [Mentor-Abnahme](archiv/MENTOR_ABNAHME.md).

Diese Dateien dokumentieren Produktentscheidungen. Sie ersetzen weder Zugriffsrechte noch technische Freigaben und behaupten keine laufende Hintergrundarbeit.

## Archiv

[archiv/](archiv/) enthält die abgelösten Konzepte: Masterplan, Lernkonzept, Mentor-Konzept, Mentor-Betrieb, Mentor-Abnahme, Lernplan-Verzahnung, Fächerübersicht und Mentor-Einstieg. Sie sind historischer Stand und gelten nicht mehr; wo sie Entscheidungen oder dieser Seite widersprechen, gelten diese. Noch Gültiges daraus steht in [Vision](VISION.md) („Erfolg messen“) und [Umsetzungsstand](UMSETZUNGSSTAND.md).

## Öffentliche Fassung

Diese Dokumente beschreiben allgemeine Produktanforderungen und technische Prüfergebnisse. Sie enthalten keine individuellen Lernverläufe, Namen von Kindern, privaten Familienangaben oder konkreten Budget- und Zugangsdaten. Private Projektnotizen sind kein Bestandteil dieser Veröffentlichung.
