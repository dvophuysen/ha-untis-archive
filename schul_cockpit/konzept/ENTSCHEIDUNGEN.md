# Entscheidungen und Grenzen

Stand: 13.09.2026. „Beschlossen“ bedeutet Produktanforderung, nicht implementiert. Herkunft: Produktabstimmung. Diese Fassung dokumentiert allgemeine Anforderungen ohne persönliche Gesprächsinhalte.

| ID | Datum | Status | Entscheidung und Begründung |
|---|---|---|---|
| D01 | bis 12.09.2026 | Beschlossen | Vorhandenes Schul-Cockpit weiterentwickeln; langfristig alle Fächer und Jahrgänge unterstützen. |
| D02 | bis 12.09.2026 | Beschlossen | iPhone zuerst; größere Ansicht nachrangig. Fachliche Qualität hat Vorrang. |
| D03 | bis 12.09.2026 | Beschlossen | Text, Spracheingabe und Fotos ermöglichen; Mentor darf mit Text und Schnellauswahlen antworten. |
| D04 | bis 12.09.2026 | Beschlossen | Eltern können unverfälschten Kinderstand ansehen und getrennt im Demo-Modus testen. Tests sind keine Kinderleistungen. |
| D05 | bis 12.09.2026 | Beschlossen | Dynamischer Lernumfang entsprechend Aufgaben, Terminen, Bedarf und Tagesbelastung; keine starre Minutenpflicht. |
| D06 | bis 12.09.2026 | Beschlossen | Unterrichtshistorie für Themen und Übungsklausuren nutzen; eigene Themen ergänzbar; Papier/Foto, Online-Bewertung und Selbstkontrolle berücksichtigen. |
| D07 | 13.09.2026 | Beschlossen | Vorhandene Verständnis-Emojis und Vertretungs-/Aufsichtslogik erhalten; keine zweite tägliche Rückmelderoutine. |
| D08 | 13.09.2026 | Beschlossen | Bestehende Elternübersicht für den Gesamtstand ausbauen. Erziehungsberechtigte werden rollenbasiert und ohne vorgegebene Zuständigkeit berücksichtigt. |
| D09 | 13.09.2026 | Verworfen | Kein spezieller „Mit Eltern besprechen“-Workflow, keine Hilfewunsch-Inbox und keine Übernahme-/Terminverwaltung zwischen Eltern und Kind. Nicht Teil des Produktumfangs: Fokus auf Lernbegleitung und Überblick statt Verwaltung privater Kommunikation. |
| D10 | 13.09.2026 | Beschlossen | Einfachster Einstieg; Analysen UND Handlungsempfehlungen aufklappbar, nicht als lange Startseitenabsätze. Gleiches Prinzip für Eltern und Kinder. |
| D11 | 13.09.2026 | Zielrichtung gesetzt | Übersicht über Fächer, Stärken, Schwachstellen und Entwicklung. Stärkeorientierte Sortierung gewünscht; genaue Zustände, Formel, Trends und Umgang mit Gleichständen sind noch nicht beschlossen. |
| D12 | 13.09.2026 | Zielrichtung gesetzt | Tiefenanalyse darf KI-gestützt Zusammenhänge erklären; keine bloßen Pseudostatistiken. Ausgestaltung und Validierung noch offen. |
| D13 | 13.09.2026 | Zielrichtung gesetzt | Gemeinsam oder außerhalb der App geleistete Übungen samt Aufwand und optionalen Notizen/Fotos berücksichtigen. Genaue Eingabemaske noch offen. |
| D14 | 13.09.2026 | Beschlossen | Vision, Ideen, Entscheidungen und tatsächliche Umsetzung dauerhaft getrennt dokumentieren. |

## Kosten und Bereitstellung

KI-Kosten müssen konfigurierbar begrenzt und nachvollziehbar sein. Konkrete Geldbeträge, Konten, Endpunkte und Bereitstellungspräferenzen gehören in die private Betriebskonfiguration. Vor Änderungen technische Budgetgrenzen prüfen. Zugangsdaten gehören nicht in die Dokumentation.

## Nicht als beschlossen behandeln

Exakte Vier-Tab-Navigation, 0–100-Score, konkrete Tages-/Wochenprämien, Streaks, Sammelwelten, zwei Pushs täglich, feste Pilotdauer und genaue Analysemodelle waren Assistentenvorschläge oder lose Überlegungen. Keine dieser Details ist durch allgemeine Zustimmung zum Gesamtziel automatisch freigegeben.

## Materialien

D18 · 14.09.2026 · Beschlossen: Kinder dürfen jederzeit und unbegrenzt eigene Materialien einsenden. Die Nutzung soll ausdrücklich gefördert werden, weil abgelegte Blätter, Hefte und Scans die Grundlage für belastbare Wissensstände und Zusammenhänge sind. Herkunft: Produktabstimmung.

D19 · 14.09.2026 · Beschlossen: Die KI-Auswertung eines Materials startet sofort nach dem Upload im Hintergrund; niemand wartet darauf. Zusätzlich läuft nachts eine Aktualisierung für noch nicht oder fehlgeschlagen ausgewertete Materialien, für veraltete Auswertungsstände und für inzwischen auflösbare Fach- oder Themenbezüge. Kein vollständiger Neudurchlauf über den Bestand, weil er Kosten ohne Erkenntnisgewinn erzeugt. Herkunft: Produktabstimmung.

D20 · 14.09.2026 · Beschlossen: Die Elternprüfung bleibt erhalten, wechselt aber die Rolle. Sie sperrt den Zugang nicht mehr, sondern dient der Korrektur von Fehlerkennungen und halbfertigen Einträgen der Kinder. Ein neues Material ist sofort Quelle. Herkunft: Produktabstimmung. Ausgestaltung in [Materialablage](MATERIALIEN.md); ob Lösungsblätter und geschriebene Arbeiten davon ausgenommen bleiben, ist noch offen.

D21 · 14.09.2026 · Beschlossen: Keine Freigabehürde für Lösungsblätter, bearbeitete eigene Aufgaben oder zurückgegebene Klassenarbeiten. Begründung des Nutzers: Der Mentor sagt Lösungen nicht vor, sondern führt mit Fragen zum eigenen Nachdenken, und selbst hochgeladene Lösungen kennt das Kind bereits. Das Kennzeichen für enthaltene Lösungen bleibt als Hinweis an den Mentor erhalten, nicht als Sperre. Herkunft: Produktabstimmung, nach Hinweis des Assistenten auf das Risiko.

## Kalender

D22 · 14.09.2026 · Beschlossen: Schultermine werden direkt aus IServ gelesen, nicht über abonnierte Home-Assistant-Kalender. Begründung: IServ liefert in Klausur-Terminen `TZID=+02:00` statt eines Zeitzonennamens, woran HAs `remote_calendar` die gesamte Datei verwirft (`setup_retry`, Entität `unavailable`); die Kalender werden zudem jedes Schuljahr neu erzeugt, und Klausuren verteilen sich auf mehrere Kalender. Eine feste Kalender- oder Entitätskennung ist deshalb keine tragfähige Quelle. Herkunft: Produktabstimmung.

D23 · 14.09.2026 · Beschlossen: Ein Zugang je Kind für IServ, gemeinsam für Schulbücher und Kalender, benannt als „IServ-Zugang" statt „Schulbuch-Zugang". Mehrere Kalender je Kind sind der Normalfall; ihre Rolle (Klausuren, Unterrichtstermine, Sonstiges) wird je Kalender festgelegt und überlebt den jährlichen Neuaufbau, weil nicht auf eine Kennung, sondern auf die wiedererkannte Sammlung abgestellt wird. Herkunft: Produktabstimmung.

D26 · 14.09.2026 · Befund, noch keine Entscheidung: Über CalDAV sind alle acht erreichbaren Sammlungen leer — Klassen- und Kurskalender, „Alle Schüler", der öffentliche Schulkalender und der persönliche Kalender des Kindes. Die Sammlungen existieren und antworten mit 207, enthalten aber keine einzige Datei. Die abonnierten Klausur-Feeds in Home Assistant liefern dagegen nachweislich Termine; sie scheitern allein an `TZID=+02:00`. Die Klausurtermine liegen demnach nicht im Kalendermodul, sondern in einer eigenen Quelle je Kind. Offen: Einlesen dieser ICS-Adresse durch die App, mit derselben Zeitzonen-Korrektur wie bisher. Die CalDAV-Anbindung bleibt bestehen, sobald die Schule ihre Kalender füllt.

## Gemeinsam lernen

D24 · 14.09.2026 · Beschlossen: Ein von den Eltern begonnenes Gespräch über echte Aufgaben ist ein Gespräch des Kindes. Es erscheint auf seinem Gerät und lässt sich dort fortsetzen; Eltern dürfen in laufenden Kinderverläufen mitschreiben. Getrennt gehalten wird allein der Demo-Modus mit erfundenen Beispieldaten. Wer nur ausprobiert hat, kennzeichnet das Gespräch danach als Testlauf; dann verlässt es Lernstand und Kinderansicht. Jede Nachricht hält fest, ob Kind oder Eltern sie geschrieben haben. Ergänzt D04: „Tests sind keine Kinderleistungen" gilt weiter, „von Eltern gestartet" begründet aber keinen Test mehr. Begründung des Nutzers: gemeinsames Arbeiten an einem Gerät und Weiterreichen des Geräts sind der Normalfall. Herkunft: Produktabstimmung.

D25 · 14.09.2026 · Beschlossen: Hausaufgabenhilfe kennt weder Zeit- noch Zugfenster. Sie endet, wenn die Aufgabe verstanden ist, nie weil ein Übungsfenster abgelaufen wäre. Je Aufgabe existiert genau ein Verlauf, den jede Unterbrechung überdauert und den Kind wie Eltern wieder öffnen. Auch abgeschlossene Übungsgespräche lassen sich fortsetzen; für sie gilt der Tagesrahmen weiter. Begründung des Nutzers: eine Hausaufgabe ist keine Tages-Check-Aufgabe. Herkunft: Fehlermeldung aus dem Betrieb.

## Veröffentlichung

D15 · 13.09.2026 · Beschlossen: Allgemein formulierte Produktkonzepte dürfen im Projekt-Repository dauerhaft gespeichert werden. Persönliche Lernbefunde, Namen, Familienangaben und Betriebsgeheimnisse bleiben außerhalb dieser Fassung.

D16 · 13.09.2026 · Beschlossen: Fälligkeit rechts über Hilfe auch auf dem iPhone. Kleinere visuelle Dichte und konsistente Aktionssymbole; identische Aktion erhält identische Darstellung.

D17 · 13.09.2026 · Zielrichtung präzisiert: Fächerübersicht als kompakte status-sortierte Grafik mit sichtbarer Entwicklung und Details erst nach Antippen. Balken oder Sterne als mögliche Darstellung; exakte Bewertung weiterhin offen. Ausarbeitung in FAECHERUEBERSICHT.md. Elternstartseite: ganze Liste, Auszug oder Verzicht erst später entscheiden.
