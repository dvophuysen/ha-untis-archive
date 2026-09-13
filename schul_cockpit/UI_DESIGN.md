# Verbindliche UI-Regeln ab 0.33.0

Die App begleitet Kinder am Übergang zur weiterführenden Schule. Sie bietet Orientierung und fertige Checklisten, lässt Reihenfolge und freiwilliges Vorziehen aber beim Kind.

## Gemeinsame Darstellung

- Gleiche Aktion, gleiche Darstellung. 💬 markiert den Einstieg in ein Gespräch. Fachnamen und Fachsymbole kommen aus subjectStyle.js; technische Fach-IDs bleiben unverändert.
- Aufgaben: Haken links, Fach und vollständiger Auftrag in der Mitte, Fälligkeit rechts und Hilfe darunter. Auf schmalen Geräten eigene rechts ausgerichtete Aktionszeile. Keine Buttons im klickbaren Aufgabeninhalt verschachteln.
- Lernangebote: Fach klein, Thema stärker, ein direkt antippbarer Eintrag. LearningGoal.svelte ist der gemeinsame Baustein für Heute und Lernplan.
- Text nur für Auftrag, eindeutigen Status oder notwendige Entscheidung. Keine Bedienungsanleitung im Dashboard. Ausgaben sind Lesetext; Eingabefelder dienen Eingaben.
- Datum deutsch, kurze Dauer als Orientierung. Kein Rohdatum aus dem Backend als sichtbarer Text. Original-Aufgabentexte werden nicht automatisch umgeschrieben.
- Farbe braucht zusätzlich verständlichen Text. Grün: bestätigte Erledigung. Gelb: offene/zu prüfende Punkte. Rot: nachweisbar überfällige Aufgabe. Unbekannt: kein grüner Erfolg. Eine fehlende Bestätigung beweist kein tatsächliches Versäumnis.
- Petrol für Aktionen, Lavendel für Lernen, Blau für Unterricht; Statusfarben haben Vorrang vor dekorativen Flächen. Helle und dunkle Ansicht berücksichtigen.

## Ansichtsprüfung und Zuständigkeit

| Ansichten | Wesentliche Information / Umsetzung |
| --- | --- |
| Heute, Aufgaben | Offene Aufträge, Fristen und Hilfe; feste rechte Aktionskante. Erledigte separat, neu nach alt. |
| Plan, Lernmentor | Für heute und weitere Themen direkt wählbar. Alte Wochen-Textlisten und pädagogische Systemerklärungen entfernt. Freie Fachwahl bleibt. |
| Familie | Ein Tagesstatus pro Bereich, keine doppelte Aufgaben-/Feedbackliste. Fachfragen und Tests als Drilldown, Stundenplan sichtbar. |
| Fächer, Fachverlauf | Zusammengeführte Themen, einzelne Unterrichtsrückmeldungen im Detail. Noch keine vollständige Zusammenführung mit späteren Leistungsbelegen. |
| Stundenplan, Packen, Stundenkarte, Stundendetail | Zeiten, Raum, Lehrkraft, Ausfall/Vertretung und Rückmeldung. Fachmaterial einmal abhaken. Unterrichtstext in Karten nicht abschneiden. |
| Übungstests, Arbeiten | Thema/Termin/Start und eigene Antworten. Quelltermine deutsch; Lösungen bleiben im vorgesehenen Eltern-/Auswertungsbereich. |
| Ältere Lernverwaltung | Datumsanzeigen korrigiert. Verwaltungsdetails bleiben im separaten Bereich; weitere Vereinfachung sinnvoll. |
| Nachholen | Echte Abwesenheiten und nachzuholender Stoff. Verspätungen bleiben aus der Fehlstundenlogik ausgeschlossen. |
| Kurse, Änderungen, Einrichtung, Einstellungen | Separate Verwaltung. Bestätigungen für Löschen, Datenänderungen, KI-Kosten und Push bleiben am tatsächlichen Entscheidungspunkt. |

## Weitere Phasen

1. Gemeinsame Fachstatus-Auswertung aus Unterrichtsrückmeldungen und späteren Übungsbelegen. Keine alte Unsicherheit als ewiges Defizit darstellen.
2. Elterncockpit um belastbare Aufstau-/Belastungshinweise ergänzen, ohne aus Anzahl allein ein Problem zu behaupten. Tagescoach auf Basis der vorhandenen Checklisten.
3. Echte Geräteabnahme der optionalen Erinnerungen und kindliche Alltagserprobung. Danach optionale Erfolgsrückmeldung/Belohnung mit abgestimmten Regeln.

Abnahme: synthetische Browserkonten, Smartphone-/Tabletbreiten, keine horizontalen Überläufe, direkte Auswahl eines nicht für heute geplanten Themas, Ausrichtung der Aktionsspalte, bekannte/fehlende Daten und Fehlersituationen. Echte Nutzbarkeit durch die Kinder ist damit nicht pädagogisch nachgewiesen.

## Präzisierung iPhone, 13.09.2026 (0.33.1)

- Datum und Hilfe bleiben **auf jeder Breite vertikal** rechts ausgerichtet, auch unter 540 px. Die bisherige mobile horizontale Aktionszeile ist abgelöst. Keine separate volle Zeile unter dem Aufgabentext.
- Sichtbares Aufgaben-Häkchen 24 px innerhalb einer 44 × 44 px großen Schaltfläche. Normale Fristen sind ruhiger Text; Dringlichkeit erhält weiterhin eigenen sichtbaren Status.
- ActionLabel.svelte ist die gemeinsame Darstellung: Gespräch = einfarbige Sprechblase vor Text, ohne Zusatzpfeil; Seitenwechsel = einheitlicher Chevron nach Text. Fachsymbole bleiben beim Fach. Bereichsnavigation behält ihre festen Symbole; dekorative wechselnde Emojis in Aktionslinks entfallen. Aufklappen nutzt den Aufklappindikator, Speichern/Abhaken erhalten keinen Navigationspfeil.
- Heute und Lernzeilen verwenden kleinere Innenabstände. Vollständige Aufträge bleiben lesbar; keine automatische Textkürzung und keine kleineren Touch-Ziele.
- Fachübersicht als eigenes Folgepaket: [Grafische Fächerübersicht](konzept/FAECHERUEBERSICHT.md). Ein dokumentierter Entwurf ist kein implementierter Lernscore.

## Grafische Fächerliste 0.34.0

Das Folgepaket ist als erste testbare Fächerliste umgesetzt. Balken zeigen bestehende Themen-Selbsteinschätzungen, Mini-Verläufe tatsächliche Einzelrückmeldungen. Keine Gesamtbewertung behaupten. Themen und Handlungseinstiege sind im Drilldown. Die Elternstartseite übernimmt die Liste noch nicht.
