# Entscheidungen und Grenzen

Stand: 15.09.2026. „Beschlossen“ bedeutet Produktanforderung, nicht implementiert. Herkunft: Produktabstimmung. Diese Fassung dokumentiert allgemeine Anforderungen ohne persönliche Gesprächsinhalte.

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

D26 · 14.09.2026 · Beschlossen: Die Klausurtermine stehen nicht in einem Kalender, sondern im Klausurplan — einem Zusatz („Plugin“) des IServ-Kalendermoduls. CalDAV zeigt Zusätze grundsätzlich nicht, deshalb sind alle acht erreichbaren Sammlungen das ganze Schuljahr über leer. Gelesen wird die Quellenliste des Kalendermoduls; die Zusätze werden wie Kalender geführt und bekommen eine Rolle. Der Klausurplan zählt ohne Nachfrage als Klausurquelle, Ferien und Feiertage sowie gestellte Aufgaben als sonstige Termine. Die Kalendersammlungen bleiben angebunden, falls die Schule sie später füllt. Herkunft: eigenständige Untersuchung des Portals im Browser.

D27 · 14.09.2026 · Beschlossen: Für die Kalender-Schnittstelle von IServ genügt die einfache Anmeldung nicht; sie antwortet nur der laufenden Seite und lehnt alles andere mit 401 ab. Der günstige Weg wird zuerst versucht, den Rest holt der Browser, der ohnehin für die Schulbücher da ist. Der Abgleich läuft zusätzlich nächtlich, weil Klausurtermine sich im Schuljahr verschieben.

## Gemeinsam lernen

D24 · 14.09.2026 · Beschlossen: Ein von den Eltern begonnenes Gespräch über echte Aufgaben ist ein Gespräch des Kindes. Es erscheint auf seinem Gerät und lässt sich dort fortsetzen; Eltern dürfen in laufenden Kinderverläufen mitschreiben. Getrennt gehalten wird allein der Demo-Modus mit erfundenen Beispieldaten. Wer nur ausprobiert hat, kennzeichnet das Gespräch danach als Testlauf; dann verlässt es Lernstand und Kinderansicht. Jede Nachricht hält fest, ob Kind oder Eltern sie geschrieben haben. Ergänzt D04: „Tests sind keine Kinderleistungen" gilt weiter, „von Eltern gestartet" begründet aber keinen Test mehr. Begründung des Nutzers: gemeinsames Arbeiten an einem Gerät und Weiterreichen des Geräts sind der Normalfall. Herkunft: Produktabstimmung.

D25 · 14.09.2026 · Beschlossen: Hausaufgabenhilfe kennt weder Zeit- noch Zugfenster. Sie endet, wenn die Aufgabe verstanden ist, nie weil ein Übungsfenster abgelaufen wäre. Je Aufgabe existiert genau ein Verlauf, den jede Unterbrechung überdauert und den Kind wie Eltern wieder öffnen. Auch abgeschlossene Übungsgespräche lassen sich fortsetzen; für sie gilt der Tagesrahmen weiter. Begründung des Nutzers: eine Hausaufgabe ist keine Tages-Check-Aufgabe. Herkunft: Fehlermeldung aus dem Betrieb.

## Veröffentlichung

D15 · 13.09.2026 · Beschlossen: Allgemein formulierte Produktkonzepte dürfen im Projekt-Repository dauerhaft gespeichert werden. Persönliche Lernbefunde, Namen, Familienangaben und Betriebsgeheimnisse bleiben außerhalb dieser Fassung.

D16 · 13.09.2026 · Beschlossen: Fälligkeit rechts über Hilfe auch auf dem iPhone. Kleinere visuelle Dichte und konsistente Aktionssymbole; identische Aktion erhält identische Darstellung.

D17 · 13.09.2026 · Zielrichtung präzisiert: Fächerübersicht als kompakte status-sortierte Grafik mit sichtbarer Entwicklung und Details erst nach Antippen. Balken oder Sterne als mögliche Darstellung; exakte Bewertung weiterhin offen. Ausarbeitung in FAECHERUEBERSICHT.md. Elternstartseite: ganze Liste, Auszug oder Verzicht erst später entscheiden.

## Quellen und Material

D28 · 15.09.2026 · Beschlossen: Die Buchstelle hinter einer Aufgabe wird aus Stunden- und Hausaufgabentexten gelesen, nicht erfragt. Als Seite gilt nur eine ausdrückliche Angabe (`S.`, `Seite`, `p.`, `pp.`, `página`); Aufgabennummern sind keine Seiten. Der zuletzt genannte Buchteil gilt über den Satz hinaus weiter. Steht nirgends ein Buchteil, heißt die Quelle „Unbekannt“ — geraten wird keiner. Herkunft: Produktabstimmung, belegt an 27 von 36 beziehungsweise 14 von 30 Hausaufgaben mit Buchangabe. Ausgestaltung in [Quellen](QUELLEN.md).

D29 · 15.09.2026 · Beschlossen: Die Materialseite führt eine Einkaufsliste der Quellen, die der Unterricht nennt und die weder digital abrufbar noch fotografiert sind, je Fach aufklappbar, mit Zitat und Datum. Sie zeigt nur an; angefordert oder abgerufen wird nichts. Herkunft: ausdrücklicher Nutzerwunsch nach einer zentralen Übersicht für einen Sammelauftrag zum Scannen.

D30 · 15.09.2026 · Beschlossen (gebaut in 0.53.0): Fehlt zu einer Seitenangabe der Buchteil, gilt zunächst die Annahme Schulbuch. Sie ist eine Hypothese, die der Seiteninhalt bestätigen oder widerlegen muss, mit vier Ergebnissen: belegt, plausibel, passt nicht, nicht prüfbar. Eingefordert werden nur die letzten beiden. Maßgeblich ist die gedruckte Seitenzahl auf dem Bild, nicht die Angabe der Schnittstelle: Bei acht Abrufen wich die gelieferte Seite dreimal von der bestellten ab, ohne dass die Schnittstelle das meldete. Ebenso muss geprüft werden, ob überhaupt Buchinhalt auf dem Bild ist; ein Betrachter meldet `loaded` und liefert eine leere Seite. Herkunft: Vorschlag des Nutzers, an der laufenden Instanz nachgewiesen. Gebaut in 0.53.0: die Materialauswertung liest die gedruckte Seitenzahl und die Passung zum Zitat, der Sammellauf bestellt bei Versatz einmal nach.

D31 · 15.09.2026 · Beschlossen (gebaut in 0.53.0): Ein Treffer im Buchkatalog ist kein Zugriff. Der Abruf wird je Buch einmal nachgewiesen, bevor die Quellenbilanz seine Seiten als vorhanden verbucht. Zwei von acht Büchern eines Kontos sind nicht abrufbar, eines mit Betrachterfehler, eines mit leerer Seite trotz Erfolgsmeldung. Herkunft: eigene Prüfung. Korrigiert eine zu optimistische Annahme in 0.52.0. Gebaut in 0.53.0 (`digital_textbook_access`); die zwei damals nicht abrufbaren Bücher liefern seit 0.52.6 (D40).

D37 · 15.09.2026 · Beschlossen: Der Mentor arbeitet am Originalmaterial oder gar nicht, und das Material liegt bereit, bevor jemand es braucht. Jede Quelle, die Untis nennt, in Stundenbeschreibung oder Hausaufgabe, wird eingesammelt: digital aus dem Medienregal, sonst als Scan oder Foto. Zwei Läufe am Tag, um 14 Uhr nach Unterrichtsschluss und nachts; der erste Lauf füllt den Bestand seit Schuljahresbeginn, danach nur die Differenz. Begründung des Nutzers: Für Klausuren braucht es ohnehin das vollständige Material des Zeitraums, und Hausaufgabenhilfe darf nicht auf den Buchabruf warten. Herkunft: Produktabstimmung. Umgesetzt in 0.53.0 als Quellenbestand.

D38 · 15.09.2026 · Beschlossen: Jeder Untis-Eintrag mit erkannter Quelle bekommt eine Verknüpfung zu einem Material (`source_links`). Abgerufene Buchseiten sind Materialien wie ein Foto, mit Herkunft, Buch und Seite, und durchlaufen dieselbe Auswertung. Wo keine Quelle genannt ist, wird später im Inhaltsverzeichnis des Buches nach dem Abschnitt gesucht (Paket 3). Herkunft: Produktabstimmung.

D39 · 15.09.2026 · Beschlossen (gebaut in 0.54.0): Gesamtkontext statt Kleckerkram. Wird ein Kapitel angeschnitten, gilt das ganze Kapitel als kommender Klausurstoff und wird vollständig geholt; bei Sprachen gehören Vokabelteil und Grammatikzusammenfassung der Lektion dazu. Der Mentor bettet Erklärungen in diesen Gesamtkontext ein. Begründung des Nutzers: Klassenarbeiten fassen Gesamtthemen zusammen; Mehrfachaufrufe und Einzelabrufe sind Aufwand und Fehlerquelle. Herkunft: Produktabstimmung. Gebaut in 0.54.0: Inhaltsverzeichnis je Buch (`book_chapters`), Kapitelregel im Sammellauf, Kapitel im Klausurstoff und im Mentor-Kontext.

D40 · 15.09.2026 · Beschlossen: Die BiBox-Bücher (Westermann) zeichnen mit WebGL. Das Alpine-Chromium des Add-ons hat keinen SwiftShader; das Image trägt deshalb Mesa mit Lavapipe und llvmpipe, und WebGL läuft über ANGLE auf Vulkan. Belegt durch die Browser-Sonde 0.52.5 („CanvasRenderer is not yet implemented", fehlende Vulkan-Erweiterung, GPU-Prozess in Startschleife) und die lesbaren Seiten in 0.52.6. Herkunft: eigene Untersuchung nach Nutzerhinweis, dass das Buch erreichbar sein müsse. Damit sind alle neun Bücher des Kontos mit Regal abrufbar.

## Verantwortung und Erinnerungen

D32 · 15.09.2026 · Verworfen: Ein Knopf „Tag abschließen“ unter der Abendkarte. Begründung des Nutzers: „Die Kinder machen keinen Abschluss. Sie lassen einfach Dinge offen. Oder sie haben sie halt erledigt.“ Ein Knopf, den niemand drückt, liefert kein Signal; einer, den man gedankenlos drückt, ein falsches. In 0.51.0 gebaut, in 0.51.2 wieder entfernt, bevor ihn jemand zu sehen bekam.

D33 · 15.09.2026 · Beschlossen: Der erledigte Abend wird abgeleitet statt abgefragt. Er gilt als erledigt, sobald keine Aufgabe mehr fällig, die Tasche für morgen bestätigt und die Stunden zurückgemeldet sind — dieselben drei Zahlen, über die auch die Erinnerung entscheidet. Festgehalten wird der Zeitpunkt und ob die Erinnerung da schon draußen war; läuft später etwas nach, bleibt der Moment stehen. Angezeigt wird dazu nichts. Herkunft: Produktabstimmung nach D32.

D34 · 15.09.2026 · Beschlossen: Selbstständig heißt, dass vor der Erinnerung alles erledigt war. Gezählt werden nur Abende vor einem Schultag; ein Sonntagabend gehört zur Woche des Montags, den er vorbereitet. Keine Serie, kein Nullpunkt. Ob und wie die Zahl den Kindern gezeigt wird, ist offen und wird verabredet, nicht gebaut.

D35 · 15.09.2026 · Beschlossen: Die Morgenmitteilung ist ab Werk aus und wird in den Eltern-Einstellungen eingeschaltet. Begründung: Eingeschaltet wäre sie am Morgen nach dem Update erstmals um Viertel vor sieben losgegangen, unangekündigt. Eine Mitteilung zu dieser Uhrzeit wird verabredet, nicht ausgeliefert. Herkunft: eigene Korrektur vor der Auslieferung.

D36 · 15.09.2026 · Beschlossen: Arbeitsweise für die Fortsetzung. Vor jeder Änderung liegen drei Dinge vor: was das Problem ist, was gebaut würde, und woran man merkt, ob es hilft. Der Nutzer entscheidet; gebaut wird nur, was auf der Liste steht. Reine Diagnose — Daten lesen, messen, nachsehen — braucht keine Rückfrage. Herkunft: Nutzerhinweis nach D32: „bevor du wirklich irgendwie was komplett Neues erfindest, erst mit mir abstimmen.“

D41 · 15.09.2026 · Beschlossen: Der Quellenbestand hat einen eigenen KI-Rahmen (`sources_micro`, Voreinstellung 15 Euro im Monat) innerhalb des Monatsrahmens, getrennt vom Hintergrund-Rahmen für die Auswertung der Kinderfotos. Begründung: Der erste Sammellauf traf auf einen Hintergrund-Rahmen von 5 Euro, der im laufenden Monat schon zu 4,35 Euro verbraucht war; keine der zwölf geholten Seiten wurde gelesen. Ohne eigenen Rahmen verdrängt der Bestand die Fotos oder umgekehrt. Kosten bleiben begrenzt und in der Kostenübersicht sichtbar. Herkunft: eigene Entscheidung im Rahmen der freien Hand, dem Nutzer berichtet.

D42 · 15.09.2026 · Beschlossen (gebaut in 0.55.0): Stunden ohne Seitenangabe werden ihrem Kapitel zugeordnet, erst über eine Lektionsnummer im Text, sonst durch das Modell mit dem Inhaltsverzeichnis, je Buch ein Aufruf für alle neuen Texte. Das Ergebnis ist eine Hypothese und wird so gezeigt („aus dem Stundenthema erschlossen“); das Kapitel wird trotzdem eingesammelt, weil der Mentor den Gesamtkontext braucht. Fachgewohnheit: Nennt eine Lehrkraft in mindestens drei ausdrücklichen Angaben zu vier Fünfteln denselben Buchteil, gilt er für ihre Stellen ohne Buchteil. Herkunft: D38 und Nutzerhinweis vom 15.09.2026.

D43 · 15.09.2026 · Beschlossen (gebaut in 0.55.0): Die Aufforderung zum Fotografieren steht in der Abendkarte und wird in der abendlichen Mitteilung als offener Punkt genannt, nur bei einer Arbeit in den nächsten vierzehn Tagen, höchstens drei Bitten, jede mit Heft, Seite und Unterrichtszitat. Ohne Arbeit wird nichts eingefordert; die Liste bleibt auf der Materialseite. Die Grenzen stammen aus der Abstimmung vom 15.09.2026 (kein Nachlaufdruck).
