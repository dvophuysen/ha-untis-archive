> Ergänzung vom 12.09.2026: [Gemeinsamer Lernplan und Wiederholungen](LERNPLAN_VERZAHNUNG.md). Gemeinsame Planung ab 0.28.0 umgesetzt; Abdeckung und Grenzen stehen im verlinkten Dokument.

# Schulmentor für die Kinder der Familie

## Zielbild, Bedienkonzept und verbindlicher Entwicklungsplan

**Stand:** 12. September 2026 · **Version:** 1.1 · **Status:** ausgearbeiteter Entscheidungsentwurf, einschließlich des nachgereichten Kostenrahmens; keine Behauptung bereits verfügbarer Funktionen.

Dieser Plan führt die bisherigen Überlegungen zusammen. Er dient als gemeinsame Grundlage vor weiterer Funktionsentwicklung. Bestehende Konzeptdateien dokumentieren frühere Entwurfsstände; bei späterer Übernahme ins Repository muss dieser Plan als maßgebliche Fortschreibung verlinkt werden. Die folgenden Architekturentscheidungen sind Vorschläge, soweit sie nicht ausdrücklich als bereits vereinbart gekennzeichnet sind.

## 1. Der Auftrag in einer Seite

**Wir entwickeln einen verlässlichen Lernbegleiter, der Unterricht, Aufgaben und Lernerfahrungen zusammenführt, verständliche nächste Schritte anbietet und Kinder zunehmend befähigt, ohne fremde Steuerung zu lernen.** Eltern gewinnen Überblick und werden von wiederkehrender Organisation entlastet. Die Kinder erleben mehr Verständnis, Zutrauen und Einfluss auf ihr Lernen.

Der Erfolg besteht gleichzeitig in dauerhaftem Können, wachsender Selbstständigkeit und einem verträglichen Familienalltag. Mehr richtige Antworten während eines KI-Gesprächs reichen dafür nicht. Mehr Chatnachrichten, Bildschirmzeit, Scans oder erledigte Übungen sind keine Erfolgsziele.

**Bereits vereinbart:** iPhone zuerst; keine größere Oberfläche als Voraussetzung. Eingabe per Text, Sprache und Foto; Mentorantworten hauptsächlich als Text, ergänzt durch Schnellauswahlen. Alle Fächer und künftigen Jahrgänge gehören zum langfristigen Umfang. Bestehendes Schul-Cockpit, Home Assistant und Azure-Anbindung bilden die Ausgangsbasis. Gesprächsverläufe und Arbeitsstände sollen über Sitzungen hinweg nutzbar bleiben. Dennis hat 50 Euro Tokenverbrauch als angemessenen Rahmen genannt. Für diesen Plan wird das als **50 Euro pro Kalendermonat für beide Kinder zusammen** konkretisiert; die Begrenzung ist noch nicht technisch aktiviert.

**Vorgeschlagene Leitentscheidungen:**

1. Ein gemeinsamer Lernbereich mit wenigen Einstiegen und aufgabengerechten Ansichten. Der Chat erklärt und begleitet; Rechnen, Lesen, Schreiben und eine Übungsklausur erhalten jeweils geeigneten Arbeitsraum.
2. Lernstand entsteht aus nachvollziehbaren Beobachtungen. Selbsteinschätzung, Hausaufgabenerledigung und eigenständiges Können bleiben getrennt.
3. Zeitrahmen, Themenabdeckung, aktuelle Daten und Kosten werden durch die Anwendung gesteuert. Das Modell arbeitet innerhalb dieses Rahmens.
4. Jeder Lernablauf endet sinnvoll: mit einem Ergebnis, einer konkreten offenen Frage oder einer Pause. Ein schwieriger Punkt darf den Gesamtplan nicht unbemerkt verdrängen.
5. Fachliche Qualität wird für Aufgabentypen schrittweise nachgewiesen. Eine gemeinsame Architektur für alle Fächer bedeutet nicht, dass jede Bewertungsart sofort gleich gut automatisiert ist.
6. Der erste Ausbau liefert einen vollständigen, überprüfbaren Lernkreislauf. Weitere Funktionen bauen auf dessen bewährten Bestandteilen auf.

**Entscheidungsregel bei Zielkonflikten:** Fachliche Richtigkeit und nachvollziehbare Daten sind Freigabevoraussetzungen. Innerhalb des vereinbarten Zeit- und Kostenrahmens wird der erwartete Lernnutzen erhöht. Steigender Frust oder mehr elterliche Verwaltungsarbeit sind ein Anlass zur Anpassung, auch wenn die Zahl bearbeiteter Aufgaben steigt.

## 2. Pädagogisches Ziel und wissenschaftliche Grundlage

Das System ergänzt individuelle Erklärung, Übungsfeedback und Organisation, die im Klassenunterricht nicht jederzeit möglich sind. Aus Unterrichtsdaten lassen sich keine pauschalen Urteile über die Qualität einer Lehrkraft ableiten. Sozialer Ärger, Müdigkeit und fachliche Schwierigkeiten erfordern unterschiedliche Antworten.

Die Forschung liefert Prinzipien, aber keinen Wirksamkeitsnachweis für unser noch zu entwickelndes Gesamtprodukt:

| Grundlage | Befund beziehungsweise Orientierung | Unsere daraus abgeleitete Gestaltungsentscheidung |
|---|---|---|
| [IES/WWC: Organizing Instruction and Study](https://ies.ed.gov/ncee/wwc/PracticeGuide/1) | Der Leitfaden empfiehlt unter anderem verteiltes Lernen, aktives Abrufen, das Wechseln zwischen ausgearbeiteten Beispielen und eigener Problemlösung sowie erklärende Fragen. Die Evidenzstärke unterscheidet sich je Empfehlung. | Erklären, selbst versuchen und später erneut anwenden gehören zusammen. Die konkreten Abstände werden anhand des Verlaufs angepasst. |
| [EEF: Metacognition and Self-Regulated Learning, zweite Ausgabe 2025](https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/metacognition) | Strategien zum Planen, Überprüfen und Auswerten sollten ausdrücklich und eingebettet in fachliches Lernen vermittelt werden. | Der Mentor macht Entscheidungen an einer echten Aufgabe nachvollziehbar und übergibt sie schrittweise an das Kind. |
| [Ryan und Deci, 2020: Motivation und Selbstbestimmung](https://selfdeterminationtheory.org/wp-content/uploads/2020/04/2020_RyanDeci_CEP_PrePrint.pdf) | Die Forschungsübersicht behandelt Autonomie, Kompetenzerleben und soziale Verbundenheit. Autonomieunterstützung und klare Struktur können zusammenwirken. | Sinnvolle Wahlmöglichkeiten, verständliche Ziele und konkrete Rückmeldung. Auch selbst akzeptierte, zunächst wenig spannende Aufgaben gehören zum Lernen. |
| [Bastani und Kollegen, PNAS 2025](https://pubmed.ncbi.nlm.nih.gov/40560616/) | Ein Feldexperiment im Mathematikunterricht zeigt: Gute Leistungen mit KI-Unterstützung können mit schwächerer späterer Eigenleistung einhergehen. Die Gestaltung der Hilfe machte einen Unterschied. | Leistungen mit Hilfe und spätere Leistungen ohne Hilfe werden getrennt erfasst. Das Ergebnis lässt sich nicht pauschal auf alle Fächer oder unseren Mentor übertragen. |

Die folgenden Zeitwerte, UI-Regeln, Kostenregeln und Freigabekriterien sind **eigene, überprüfbare Produktentscheidungen**, keine wissenschaftlichen Konstanten.

Verständnis kann Freude ermöglichen; Freude darf trotzdem keine Leistungspflicht werden. Auch ein Kind, das heute keine Lust hat, darf eine kurze, machbare Aufgabe erledigen und anschließend aufhören. Ebenso darf es bei echtem Interesse innerhalb des Familienrahmens weiterforschen. Das langfristige Ziel umfasst Interesse und Neugier, aber auch die Fähigkeit, erforderliche Arbeit selbstbestimmt zu bewältigen.

## 3. Was die Kinder auf dem iPhone erleben

### Ein vertrauter Einstieg, unterschiedliche Arbeitsformen

Die Startansicht beantwortet: **Was ist heute sinnvoll? Warum gerade das? Wie lange ungefähr?** Vorgeschlagen wird eine Hauptaktion mit einer Alternative. Der bestehende Hausaufgabenplan wird einbezogen; Lernzeit wird nicht doppelt verplant.

Beispieltext, kein aktueller persönlicher Befund:

> Heute: etwa 8 Minuten Deutsch. Bei der Großschreibung hattest du eine Frage. Wir schauen an einem Beispiel, was schon klappt.
>
> **Loslegen** · **Eigene Aufgabe zeigen**

Weitere Einstiege: offene Arbeit fortsetzen, für eine Arbeit vorbereiten, ein Fach/Thema auswählen. Eine vollständige Themenliste ist erreichbar, aber keine Pflicht vor jeder Sitzung. Elternverwaltung erscheint in einer gesonderten Ansicht.

| Tätigkeit | Oberfläche innerhalb desselben Lernbereichs |
|---|---|
| Erzählen oder etwas fragen | Kurzer Dialog; Textfeld, Mikrofon und kontextbezogene Auswahl |
| Eine Aufgabe verstehen | Aufgabe bleibt sichtbar; darunter jeweils ein nächster Schritt |
| Rechnen oder skizzieren | Papier verwenden, Foto zuordnen; Ergebnis und Rechenweg getrennt betrachten |
| Einen Text untersuchen | Quelle und Antwortbereich umschaltbar, markierbare Stelle, gespeicherter Entwurf |
| Einen längeren Text schreiben | Eigener Editor mit Gliederungshilfe und automatischem Speichern; Gespräch einklappbar |
| Wiederholen | Kurze Aufgabenfolge, eigenes Abrufen vor Lösungseinblendung |
| Übungsklausur | Aufgabenübersicht, einzelne Aufgaben, Markierung für später, Abgabe und anschließende Auswertung |

Damit ist ein längerer Aufsatz technisch auf dem iPhone bearbeitbar. Ob das angenehm ist, prüfen wir mit den Kindern. Papier und Foto gehören gleichwertig zum Ablauf; eine iPad-Version ist keine Voraussetzung. Hörverstehen benötigt geeignetes Audiomaterial, Aussprachebeurteilung tatsächliches Audio und praktische Leistungen gegebenenfalls eine menschliche Beobachtung. Ein Textchat kann diese Nachweise nicht ersetzen.

### Gesprächsregeln

- Ein gedanklicher Schritt und höchstens eine neue Frage je Antwort. Kurze Absätze; längere Erklärungen auf Wunsch schrittweise öffnen.
- Umgangssprache, Abkürzungen und halbe Sätze akzeptieren. Keine künstliche Jugendsprache, keine Lobautomatik.
- „kp“ führt zu einem kleineren Einstieg, etwa „Beispiel zeigen?“; nicht zu einer Forderung nach besserer Formulierung.
- Unsicherheit in der Deutung kenntlich machen: „Meinst du das Thema von heute?“ Bei unwichtigen Unklarheiten sinnvoll fortfahren.
- „Anders erklären“, „Weiß nicht“, „Pause“ und „Ich glaube, das stimmt nicht“ bleiben leicht erreichbar.
- Bei unbekanntem Stoff darf der Mentor direkt erklären. Das Kind muss nicht mehrfach erfolglos raten.
- Aus Frust entsteht keine automatische Zusatzarbeit. Bei einem Gespräch über Ärger wird zunächst geklärt, ob Zuhören oder Aufgabenhilfe gewünscht ist.

**Sprachweg:** Zunächst wird Betriebssystem-Diktat im Textfeld als einfacher Einstieg nutzbar gemacht. Ein eigenes Mikrofon benötigt separat geprüfte Aufnahme und Transkription. Erkanntes Gesprochenes bleibt vor dem Senden korrigierbar. Bei unsicheren fachlichen Begriffen fragt der Mentor kurz nach. Rohaufnahmen werden standardmäßig nach erfolgreicher Übertragung und kurzer Korrekturmöglichkeit verworfen; Transkript und Lernantwort bleiben erhalten. Wenn Audio selbst Lernmaterial ist, etwa für Sprechübungen, wird es ausdrücklich als solches gespeichert. Sprachausgabe des Mentors gehört nicht zum ersten Ausbauschritt.

**Bedienabnahme als Entwurf:** Kernwege bei 360–430 CSS-Pixel Breite, Bildschirmtastatur und größerer Schrift nutzbar; Bedienelemente mindestens 44 × 44 CSS-Pixel; kein horizontales Scrollen für die Hauptaktionen. Eine Sitzung lässt sich vom Lernstart aus mit höchstens zwei bewussten Auswahlaktionen beginnen. Fotos sind vergrößerbar. Aufnahme-, Lade- und Speicherzustand sind eindeutig. Wiederholtes Antippen löst keine doppelte Aktion aus.

## 4. Die verbindlichen Anwendungsszenarien

Diese Szenarien sind zugleich der fachliche Umfang des Zielbilds und die Grundlage der späteren Abnahme. Dialogbeispiele werden vor der Implementierung anhand dieser Fälle durchgespielt.

| Fall | Erwarteter Ablauf | Woran wir Erfolg erkennen |
|---|---|---|
| A: „Ich weiß nicht, wo anfangen“ | Aktuelle Pflichten und verfügbaren Rahmen prüfen, einen begründeten nächsten Schritt anbieten. | Kein Themenformular nötig; ein verständliches Ziel und ein Ende stehen fest. |
| B: „Deutsch ist blöd“, danach „kp“ | Kurz anerkennen, Unterrichtsthema als Vermutung anbieten, kleines Beispiel oder eigene Aufgabe zur Wahl stellen. | Hilfe auch ohne präzise Problembeschreibung; kein Verhör. |
| C: „Alles verstanden“ | Gelegentlich eine passende neue Aufgabe ohne Lösung anbieten. | Selbsteinschätzung wird respektiert und um einen Lernbeleg ergänzt. |
| D: Krankheit und Nachholen | Tatsächlich betroffene Unterrichtszeiten, Inhalte, Material und bereits erledigtes Nachholen verbinden. | Zwei Minuten Verspätung werden nicht als ganze Fehlstunde behandelt; nachgeholte Arbeit bleibt erledigt. |
| E: Aufgabenfoto | Lesbarkeit und Aufgabenbezug prüfen; vorhandene Arbeit erkennen; den nächsten sinnvollen Hinweis anbieten. | Unleserliche Handschrift wird nicht als fachlicher Fehler bewertet. |
| F: Neue Daten während des Gesprächs | Vor der nächsten Planentscheidung Änderungen übernehmen. | Eine inzwischen erledigte Hausaufgabe wird nicht erneut eingeplant. |
| G: Morgen weitermachen | Ziel, letzten Versuch, Hilfen und offene Frage laden; neueren Unterricht mit einbeziehen. | Kontinuität ohne erneutes Erzählen und ohne überholte To-do-Liste. |
| H: Vorbereitung auf eine Arbeit | Stoffumfang klären, Themenmatrix erstellen, Stichproben verteilen, Zeit priorisieren. | Auch bislang unbearbeitete Themen bleiben sichtbar. |
| I: Längere Übungsklausur | Geprüfte Fassung starten, Antworten speichern, Unterbrechung erlauben, vollständig auswerten. | Keine Aufgabenänderung während des Versuchs; Lösungen bleiben bis zur Abgabe verborgen. |
| J: Ein Thema klappt weiterhin nicht | Darstellung wechseln, Voraussetzung kurz prüfen oder konkrete Frage für einen Menschen festhalten. | Das Zeitbudget endet verlässlich; keine endlose Erklärschleife. |
| K: KI fällt aus oder Budget ist verbraucht | Gespeicherte Aufgaben und Arbeitsstände weiter anbieten; neue Auswertung ehrlich vertagen. | Kein Datenverlust, keine erfundene Bewertung, kein überraschender Kaufdialog beim Kind. |
| L: Neues Schuljahr, neues Fach | Neue Unterrichtszuordnung, vorhandene Fähigkeiten und Materialien mit Herkunft erhalten. | Kein verlorenes Lernwissen und keine ungeprüfte Übernahme alter Prüfungsvorgaben. |

## 5. Ein verlässliches Bild von Stoff und Können

### Quellen und Gewichtung

Die Datenlage wird zuerst fachlich bereinigt: persönliche Kursauswahl, ausgefallene Stunden, manuelle Korrekturen, reale Schuljahresgrenzen und zeitliche Überschneidung mit Fehlzeiten. Bei Hausaufgaben wird ein bestätigter Stundenbezug genutzt; reine Fach- und Datumsnähe bleibt eine vermutete Zuordnung. Lokale Datenbank-IDs und UNTIS-IDs sind nicht austauschbar.

Ein Thema über mehrere Wochen liefert einen Hinweis auf den Unterrichtsschwerpunkt. Wiederholte Organisationseinträge und doppelte Datenlieferungen dürfen dessen Gewicht nicht erhöhen. Die Zahl der Unterrichtsstunden beweist weder das Können des Kindes noch die spätere Punkteverteilung einer Klausur.

Für den verbindlichen Stoffumfang haben Lehrkraftvorgaben, aktuelle Aufgaben und zugehöriges Schulmaterial Vorrang. Allgemeine Quellen ergänzen Erklärungen und Beispiele. Landeslehrpläne liefern Rahmen und mögliche Verbindungen; eine Unterrichtsreihenfolge wird dadurch nicht sicher vorhergesagt. Konkrete Vokabeln, Textstellen und Arbeitsblattaufträge benötigen ihre tatsächliche Quelle. Digitale Buchlizenzen sind hilfreich, aber kein bereits eingerichteter automatischer Buchzugriff.

### Lernstand mit nachvollziehbarer Herkunft

| Information | Zulässige Aussage |
|---|---|
| Unterrichtseintrag | „Wurde behandelt“ |
| Rückmeldung des Kindes | „Fühlt sich sicher/unsicher“ |
| Erledigte Hausaufgabe | „Als erledigt dokumentiert“ |
| Lösung mit Hinweis | „Gelang mit dieser Unterstützung“ |
| Neue Aufgabe ohne Hinweis | „Bei dieser Aufgabe selbstständig gezeigt“ |
| Neue Aufgabe nach zeitlichem Abstand | „Nach einer Pause erneut gezeigt“ |
| Andere Anwendungssituation | „In diesem weiteren Kontext angewendet“ |

Fähigkeiten sind kleine, überprüfbare Ziele innerhalb eines Themas. Jede Beobachtung hält Aufgabe und Version, Antwort, Kriterien, Hilfen, Zeitpunkt und Unsicherheit fest. Eine Beherrschungsanzeige benötigt mehrere passende Belege und einen späteren Abruf; die genaue Regel ist je Aufgabenfamilie festzulegen. Fehlende Beobachtung bedeutet „noch nicht geprüft“. Aus ausbleibender App-Nutzung entsteht keine Abwertung.

Eine falsche Bewertung kann korrigiert werden. Davon abhängige Anzeigen, Zusammenfassungen und Wiederholungen werden neu berechnet. Es gibt keine dauerhaft festgeschriebene Zuschreibung „schlecht in Mathe“.

### Unterschiedliche Fächer, gemeinsame Grundstruktur

Wortschatz benötigt Abruf und Verwendung; Verfahren benötigen Rechenweg und Verfahrenswahl; Naturwissenschaften benötigen Modelle, Zusammenhänge und begründete Vorhersagen; Textfächer benötigen Quellenverständnis, Argumentation und sprachliche Ausarbeitung. Praktische Aufgaben benötigen passende Ergebnisdokumentation. Ein Fach kann mehrere dieser Lernhandlungen enthalten.

Anforderungsbereiche I–III werden am gesamten Auftrag und den Unterrichtsvoraussetzungen beurteilt. Ein Operator allein ist keine sichere Zuordnung. Fach- und schulstufengerechte Vorgaben werden hinterlegt; Abitur-Operatoren werden nicht ungeprüft auf Jahrgang 6 übertragen. [Offizielle niedersächsische Ausgangsseite zu Operatoren](https://bildungsportal-niedersachsen.de/allgemeinbildung/zentrale-arbeiten/operatoren-zentrale-pruefungsfaecher-ab-2024).

## 6. Planung mit einem verlässlichen Ende

Es gibt drei Planungshorizonte: langfristige Fähigkeiten und Voraussetzungen, Wochen-/Prüfungsvorbereitung und die einzelne Sitzung. Die konkrete Auswahl berücksichtigt Dringlichkeit, beobachtete Schwierigkeiten, fällige Wiederholungen, bisherige Fachabdeckung, Interesse und tatsächlich verfügbare Zeit.

Der Planer führt auch Themen ohne negative Rückmeldung gelegentlich zu einer Stichprobe. Er verwaltet wenige ausgewählte Wiederholungen; versäumte Lerntage erzeugen keinen immer größer werdenden Stapel. Akute Aufgaben dürfen andere Fächer nicht unbegrenzt verdrängen. Eine Vorschau orientiert kurz über mögliche nächste Zusammenhänge und wird als Vorschlag gekennzeichnet.

**Vorgeschlagener Start für kurze Sitzungen:** ein Lernziel, ungefähr 8–12 Minuten innerhalb der ohnehin vorgesehenen Lernzeit. Nach zwei erfolglosen Erklärvarianten prüft der Mentor kurz eine Voraussetzung oder hält die Schwierigkeit fest. Dieser Wert begrenzt Erklärschleifen, nicht die Anzahl aller Nachrichten. Das Kind darf jederzeit pausieren; Vertiefung wird als bewusste Erweiterung mit erneut geprüftem Rahmen angeboten. Längere Klausuren erhalten von Beginn an einen eigenen vereinbarten Zeitrahmen.

Eine Tagesplanung berücksichtigt Hausaufgaben, bereits aufgewendete Zeit und Erholung. Geschätzte Minuten sind keine sekundengenaue Verpflichtung. Wenn die Planung nicht aufgeht, wird sie angepasst; das Kind wird nicht für eine falsche Schätzung verantwortlich gemacht.

## 7. Gedächtnis, Aktualität und technische Verantwortung

**Empfehlung: die bestehende Anwendung modular erweitern.** Für zwei Kinder benötigen wir zunächst keine eigene Plattform aus vielen Diensten. SQLite, die bestehende API, die mobile Oberfläche und ein dauerhaft arbeitender Hintergrundprozess können die erste belastbare Ausbaustufe tragen. Eine gesonderte Vektordatenbank wird erst erwogen, wenn eine gemessene Suchschwäche sie rechtfertigt.

| Modul | Verantwortung | Einsatz des Modells |
|---|---|---|
| Datenübernahme | Aktualisieren, normalisieren, Änderungen und Quellenstatus festhalten | Normalerweise keiner |
| Themen- und Materialspeicher | Quellen, Seiten, Versionen, Fähigkeiten und Beziehungen verwalten | Begrenzte Zuordnungs-/Erschließungsvorschläge |
| Lernbelege | Versuche, Hilfen, Kriterien und Korrekturen speichern | Begründete Bewertung, soweit verlässlich möglich |
| Planer | Zeit, Prioritäten, Wiederholungen und Themenabdeckung | Optionaler Vorschlag, keine alleinige Entscheidung |
| Sitzungssteuerung | Lernphase, zulässige nächste Aktionen, Pausen und Abschluss | Kurzer strukturierter Vorschlag für die nächste Antwort |
| Klausurverwaltung | Umfang, feste Fassungen, Antworten, Abgabe und Gesamtauswertung | Begrenzte Erstellung und Auswertung |
| KI-Zugang und Verbrauchsbuch | Modellzugriff, Kostenreservierung, Limits, Fehler und Wiederholungen | Jeder kostenpflichtige Aufruf läuft ausschließlich hierdurch |

### Dauerhafte Daten

Ergänzt werden konzeptionell: Fähigkeiten und Beziehungen, Quellenversionen, Aufgabenfamilien und Varianten, unverwechselbare Versuche, Lernbelege, Planversionen, Mentorsitzungen mit Nachrichten, Klausurversionen und -versuche, Hintergrundaufträge sowie Verbrauchsbuchungen. Vorhandene Datensätze werden zugeordnet; bisherige Selbsteinschätzungen werden nicht rückwirkend zu objektiven Lernbelegen umgedeutet.

Jede Sitzung speichert Ziel, Phase, aktuell bearbeitete Aufgabe, bereits gegebene Hilfen, offene Punkte und einen kompakten Zwischenstand. Nachrichten bleiben als Referenz erhalten. Fachliche Erinnerungen verweisen auf ihre ursprüngliche Quelle. Zusammenfassungen helfen beim Finden; sie ersetzen die Originalbelege nicht.

Vor einer fachlich relevanten Modellanfrage wird ein begrenztes Kontextpaket gebildet: aktueller Auftrag, letzte Gesprächsschritte, passende Erinnerungen und Quellenausschnitte sowie Änderungen an relevanten Aufgaben und Terminen. Auswahl und Quellenversionen werden protokolliert. Mehrere Jahre Gesprächshistorie werden nicht vollständig erneut übertragen.

### Aktualität ohne ständigen Neuanfang

Eigene Aufgabenänderungen invalidieren unmittelbar die betroffene Planung. Externe Änderungen werden nach erfolgreicher Synchronisierung wirksam; Aktualisierungszeit und Fehler bleiben sichtbar. Vor einer neuen Planung wird der aktuelle Zustand gelesen. Archiv und App-Datenbank bilden derzeit keinen gemeinsamen atomaren Snapshot; Kontextpakete halten daher Herkunft und Lesestand fest und prüfen wichtige Änderungen erneut.

Ein Modellaufruf erhält eine Plan-/Zustandsversion. Ist diese bei Rückkehr überholt, darf sein Ergebnis nicht stillschweigend eine neue Planung überschreiben. Eine noch passende Erklärung kann erhalten bleiben; veraltete Organisationsentscheidungen werden verworfen oder neu berechnet. Dafür ist keine automatische Wiederholung des ganzen Dialogs nötig.

Ein echtes Hintergrundverfahren übernimmt neue/geänderte Daten unabhängig davon, ob Eltern die Seite öffnen. Aufträge werden persistent gespeichert, zusammengefasst, nach Neustart fortgesetzt und anhand stabiler Schlüssel vor doppelter Verarbeitung geschützt. Regelmäßiger vollständiger Abgleich erfasst auch Löschungen, die ein bloßer Änderungszeitstempel übersieht.

### Grenzen zwischen Modell und Anwendung

Das Modell liefert nur definierte Aktionen und referenzierte Inhalte. Die Anwendung prüft Kindzuordnung, Aufgabenbezug, Lernphase, Quellen, Budget und erlaubte Zustandsänderungen. Hochgeladene Materialien gelten als Inhalt, nicht als Anweisungen an das System. Zugangsdaten bleiben außerhalb des Modellkontexts. Lösungsteile einer Prüfungssimulation werden vor Abgabe nicht an den Kinder-Client ausgeliefert.

Kinder sollen wissen, welche Gespräche gespeichert werden und was Eltern einsehen können. Die Elternübersicht zeigt standardmäßig Lernfortschritt und konkrete Hilfebedarfe; der Verlauf bleibt für autorisierte Rückfragen erreichbar. Korrektur, Export und Löschung müssen auch Zusammenfassungen und abgeleitete Erinnerungen berücksichtigen. Der Mentor verspricht kein geheimes Gespräch, während Eltern technisch Einsicht haben.

## 8. Materialien und längere Übungsklausuren

Material wird möglichst dort erfasst, wo es gebraucht wird: Foto an einer Hausaufgabe, Screenshot im Gespräch, Scan bei der Prüfungsvorbereitung. Fach, Datum und möglicher Aufgabenbezug werden vorgeschlagen. Nur Unklarheiten führen zu Rückfragen. Eltern sollen keine umfangreiche Materialkartei von Hand pflegen müssen.

Das Original bleibt erhalten. Texterkennung, Seitenauszüge und Zuordnungen sind versionierte Ableitungen. Dieselbe unveränderte Seite wird nicht bei jedem Gespräch neu erschlossen. Unsichere OCR, fehlende Seiten und widersprüchliche Aufgabenstellungen bleiben offen, bis sie geklärt sind. Öffentliches Material wird mit genauer Fundstelle gespeichert. Eine falsche Aufgabenquelle muss austauschbar sein, ohne bereits eingereichte Arbeiten zu verändern.

**Klausurablauf:**

1. Anlass und Stoffumfang bestimmen: bestätigte Lehrkraftvorgaben von aus Unterricht abgeleiteten Annahmen trennen.
2. Themenmatrix erstellen: Fähigkeiten, Aufgabentypen, Anforderungsbereiche, Zeit und Punkte. Fehlende Bereiche sichtbar machen.
3. Aus geprüften Aufgabenfamilien zusammenstellen, fehlende Aufgaben begrenzt erzeugen. Lösungen und Kriterien separat vorbereiten.
4. Lösbarkeit, Angaben, Punkteaddition, zeitliche Plausibilität und fachliche Passung prüfen. Ein zweiter Modellaufruf allein gilt nicht als unabhängiger Richtigkeitsnachweis. Rechenprüfer, Quellenabgleich oder menschliche Prüfung ergänzen ihn nach Bedarf.
5. Fassung fixieren. Im Übungsmodus Hilfen mitführen; in der Simulation inhaltliche Hilfe und Lösungen bis zur Abgabe sperren. Ein Wechsel zur Hilfe ist möglich, beendet aber die Vergleichbarkeit als vollständig unbeeinflusste Simulation und wird dokumentiert.
6. Antworten fortlaufend speichern; Pause und Gerätewechsel erlauben. Aktive Bearbeitungszeit und Pausen unterscheiden. Eine unterbrochene Simulation bleibt als solche erkennbar.
7. Nach Abgabe abschnittsweise nach Kriterien auswerten. Unleserliche oder mehrdeutige Antworten zur Klärung markieren, alternative richtige Lösungen zulassen.
8. Übergreifend auswerten: fachliche Bereiche, Aufgabenverständnis, Begründung, Zeit und Hilfen. Daraus wenige nächste Schritte ableiten.

Neue Daten verändern eine gestartete Klausur nicht. Erweist sich eine Aufgabe als fehlerhaft, wird sie im Versuch gekennzeichnet und von der Bewertung ausgeschlossen oder transparent korrigiert. Betroffene Lernbelege werden revidiert. Bei offenen Antworten bleiben Punkte begründete Einschätzungen mit Korrekturmöglichkeit; eine Schulnote benötigt zusätzlich den tatsächlichen Bewertungsmaßstab.

## 9. Verbrauch begrenzen, bevor Geld ausgegeben wird

Das heutige Limit von zwölf KI-Entwurfsanfragen pro Kind und Tag ist nur eine grobe Aufrufgrenze. Live-Code begrenzt damit nicht verlässlich alle Eingabe-, Ausgabe-, Bild- und künftigen Audiokosten. Dialoge, Materialerschließung und Klausuren brauchen ein gemeinsames Verbrauchsbuch.

### Verbindliche Regeln des Zielentwurfs

- **50 Euro pro Kalendermonat für den Mentor insgesamt**, Warnschwelle bei 40 Euro. Der Plan rechnet auch kostenpflichtige Materialerschließung, Bewertung und gegebenenfalls Spracherkennung in diesen Rahmen ein. Die 50 Euro sind eine Obergrenze, kein Verbrauchsziel. Andere Anwendungen in der Subscription sind nicht Teil dieser App-Grenze.
- Ergänzend Tages- und Sitzungslimits, abgeleitet aus Messungen. Als anfängliche Planungsregel dürfen automatische Hintergrundarbeiten höchstens 5 Euro des Monatsrahmens beanspruchen; dieser Betrag liegt innerhalb der 50 Euro. Unverarbeitete Altmaterialien werden gegebenenfalls über mehrere Zeitfenster verteilt. Eine faire Aufteilung verhindert, dass ein Kind den gesamten verfügbaren Rahmen verbraucht; feste gleiche Verbrauchsquoten sind keine pädagogische Vorgabe.
- Vor jedem Aufruf werden maximal erwartbare Kosten konservativ reserviert. Parallel laufende Aufträge teilen dieselbe transaktionale Budgetprüfung.
- Eingabeumfang, Ausgabelimit, Zahl der Aufrufe und gegebenenfalls Audio-/Bildumfang werden begrenzt. Kein Modell entscheidet selbstständig über unbeschränkte Folgeaufrufe.
- Tatsächliche Nutzung wird nachgeführt, einschließlich fehlgeschlagener oder abgebrochener Anfragen, soweit sie berechnet wurden. Bei unklarem Timeout bleibt die Reservierung zunächst stehen. Keine blinde Wiederholung, die doppelt kosten könnte.
- Höchstens eine ausdrücklich budgetierte automatische Reparatur bei ungültiger Modellantwort; danach geordneter Abbruch oder gespeicherte Alternative.
- Hintergrundauswertungen werden nur für neue oder veränderte Inhalte ausgelöst, mit Inhaltsfingerabdruck und wiederverwendbaren Ergebnissen. Öffnen einer Seite verursacht keine vollständige Neuanalyse.
- Bei knappem Budget werden neue Hintergrundarbeiten zuerst vertagt. Ein Abschluss wird soweit möglich vorab reserviert; andernfalls erzeugt die Anwendung einen sachlichen Abschluss aus bereits gespeicherten Ergebnissen ohne neuen Modellaufruf.
- Ohne verifizierte beziehungsweise konservativ konfigurierte Kostensätze gibt es keine ehrliche Eurogarantie. Kostenpflichtige automatische Abläufe werden dann nicht neu freigegeben. Ein App-Limit begrenzt nur diese Anwendung, nicht sämtliche anderen Ausgaben der Azure-Subscription.

Die Modellrollen werden nach gemessener fachlicher Qualität, Latenz und Kosten besetzt. Die vorhandenen Deploymentnamen allein belegen weder Fähigkeit noch Preisvorteil. Routineplanung, Auswahlklicks, Fortschrittsanzeige und gespeicherte Wiederholungen benötigen häufig keinen Modellaufruf. Ein aufwendigeres Modell kann für anspruchsvolle Aufgaben sinnvoll sein; jeder Wechsel bleibt begrenzt und messbar.

### Kostenplanung ohne erfundene Preiszusage

Für jede Modell-/Dienstversion werden gültige Preise und Abrechnungseinheiten mit Datum hinterlegt. Die Kostenbasis muss mit der Azure-Abrechnung vergleichbar sein; bei anderer Preiswährung oder zusätzlichen Abgaben werden Umrechnung und Reserve ausdrücklich berücksichtigt. Die Kalkulation addiert disjunkte Eingabe-, gegebenenfalls Cache-, Ausgabe- und weitere Dienstkosten. Reasoning- oder Bildanteile werden entsprechend der tatsächlichen Abrechnung berücksichtigt und nicht doppelt gezählt. Bereits im laufenden Monat entstandene Mentor-Kosten werden bei Aktivierung abgeglichen, statt das Budget unbemerkt bei null neu zu beginnen.

**Reines Rechenbeispiel für den Mengenansatz:** Zwei Kinder mit je 20 kurzen Sitzungen im Monat ergeben 40 Sitzungen. Bei sechs Modellantworten mit durchschnittlich 3.000 Eingabe- und 400 berechneten Ausgabetokens pro Sitzungsschritt wären das insgesamt 720.000 Eingabe- und 96.000 Ausgabetokens. Dazu kämen Materialerschließung, Klausuren, gegebenenfalls Sprache und Fehlerreserven. Diese Zahlen sind Annahmen zur Planung, keine Messung und kein Ausgabelimit für die konkreten Modelle.

Vor einem Pilot wird derselbe Satz kurzer Dialoge, Fotos und Klausuraufgaben mit den verfügbaren Deployments gemessen. Daraus entstehen drei konkrete Nutzungsrechnungen: normale Schulwoche, Prüfungswoche und einmaliges Erschließen älterer Materialien. Der Entwurf muss zeigen, dass die vorgesehene Nutzung einschließlich Reserve in den 50-Euro-Rahmen passt. Ist das nicht der Fall, werden Kontextumfang, Wiederverwendung, Hintergrundumfang und Modellzuordnung angepasst. Fachliche Qualitätsanforderungen werden nicht stillschweigend abgesenkt. Dieser Planungsschritt verändert noch keine Azure- oder App-Konfiguration.

## 10. Erfolg messen, ohne eine zweite Belastung zu schaffen

| Ziel | Wenige passende Beobachtungen | Fehlinterpretation vermeiden |
|---|---|---|
| Dauerhaftes Können | Neue Aufgaben nach etwa einer und später mehreren Wochen, Hilfebedarf und Erklärung des Vorgehens | Identische Aufgaben oder unmittelbar wiederholte Musterlösung reichen nicht. |
| Selbstorganisation | Zahl notwendiger Erinnerungen, selbst gewählte sinnvolle nächste Schritte, weniger vergessene Pflichten | App-Aktivität ist kein Selbstständigkeitsnachweis. |
| Familienentlastung | Kurzer wöchentlicher Rückblick: Verwaltungszeit, wiederkehrender Streit, konkrete Hilfebedarfe | Keine tägliche Pflichtumfrage oder Bewertung der Kinder. |
| Zutrauen und Motivation | Freiwillige Rückmeldung: verständlicher, machbarer, eher bereit anzufangen | Klicks, Lobreaktionen oder Chatlänge messen keine intrinsische Motivation. |
| Vorbereitung | Abdeckung bestätigter Themen, Ergebnisse ohne Hilfe, später tatsächliche Lehrerkommentare | Fehlende Prüfungsdaten bedeuten nicht „sicher vorbereitet“. |
| Betrieb | Kosten je nützlicher Sitzung, Latenz, Fehlbewertungen, verlorene/doppelte Antworten | Ein billiger, fachlich falscher Ablauf ist kein Effizienzgewinn. |

Vorgeschlagener Familienversuch: kurze Ausgangsbeobachtung, dann vier Wochen begrenzte Nutzung; spätere Abrufaufgaben reichen über dieses Fenster hinaus. Beide Kinder werden mit ihrem eigenen Ausgangsstand betrachtet. Zwei Kinder und wechselnder Unterricht erlauben keine belastbare kausale Wirkungsstudie. Wir suchen nachvollziehbare Hinweise und prüfen alternative Erklärungen wie neue Lehrkraftvorgaben, leichtere Aufgaben oder elterliche Zusatzhilfe.

Die Elternansicht liefert eine knappe Wochenübersicht mit wenigen Aussagen: Was gelingt besser? Was ist unklar? Wo ist menschliche Hilfe sinnvoll? Was wurde vertagt, und warum? Quellen lassen sich bei Bedarf öffnen. Steigt die Belastung über mehrere Rückmeldungen oder bleibt ein erheblicher Bewertungsfehler ungeklärt, wird der betroffene Ablauf reduziert beziehungsweise pausiert.

Der eingerichtete Lesezugang ermöglicht ergänzende Analysen durch Codex. Laufende automatische Überprüfung muss in der Anwendung beziehungsweise ihrem Hintergrundprozess implementiert werden; sie entsteht nicht dadurch, dass ein Chat geöffnet bleibt.

## 11. Bestandsabgleich vom 12. September 2026

Dieser Abgleich beruht auf den vorhandenen Konzepten und dem geprüften Code. Der zuletzt live bestätigte Stand ist 0.23.3. In diesem Planungsschritt wurden keine neuen Live-Lernleistungen ausgewertet und keine Azure-Testanfragen ausgelöst.

| Bereich | Vorhanden | Für das Ziel noch erforderlich |
|---|---|---|
| Datenzugang | Dauerhafter, kontobegrenzter Lesezugang; Unterricht, Rückmeldungen, Aufgaben und weitere Datensätze erreichbar | Fachlich normalisierte Änderungsverarbeitung, konsistente Ableitungen, Hintergrundabgleich |
| Lernraum | Schuljahresprofile, Themen, Materialien, Übungen, Hilfen, Selbsteinschätzung und Zeitbudget | Kinderführung, fachliche Lernbelege, Fähigkeiten über Aufgabenvarianten hinweg |
| Wiederholung | Intervalle bezogen auf konkrete Aufgaben | Fähigkeiten, neue Varianten, fachübergreifende Abdeckung |
| Themenentdeckung | Lokal vorbereitet, noch nicht ausgerollt; begrenzte inkrementelle Auswertung | Fachlicher Datenabgleich und Qualitätstest; Aufnahme in gemeinsame Job-/Kostensteuerung |
| Mentor | Noch kein adaptiver, dauerhaft geführter Dialog | Nachrichten, Arbeitsstand, Kontextbildung, Gesprächsregeln, Zustandssteuerung |
| Sprache | Kein eigener geprüfter Aufnahme-/Transkriptionsablauf | Diktat als Einstieg testen; eigenen Sprachweg nach Bedarf und Kostenprüfung ergänzen |
| Klausuren | Kalender und Lernaufgaben als Ausgangsbasis | Themenmatrix, feste Klausurfassungen, Prüfungsmodus, Gesamtauswertung |
| KI | Azure-Endpunktadapter, Entwurfsfreigabe, Aufrufgrenze | Verifizierte reale Modellqualität, einheitliches Nutzungs-/Kostenbuch, harte Ausgabegrenzen |

Die lokal vorbereitete Themenentdeckung wird nicht allein deshalb ausgeliefert, weil sie bereits programmiert ist. Sie muss sich in diesen Gesamtplan einordnen. Vor Entwicklungsbeginn werden der produktive Stand mit Lesezugang und die lokale Vorarbeit kontrolliert zusammengeführt; bestehende Kalenderarbeiten bleiben berücksichtigt.

## 12. Umsetzungsfolge und Freigabekriterien

Die Reihenfolge trennt früh klärbare Architekturfragen von Fragen, die nur durch Nutzung beantwortet werden können. Die Ausbauschritte sind bewusst begrenzt. Eine neue Idee wird zunächst gegen Ziel und Abnahmekriterien geprüft und erhält einen Platz im Plan, statt spontan in die laufende Umsetzung zu wandern.

| Schritt | Konkretes Ergebnis | Voraussetzung für den nächsten Schritt |
|---|---|---|
| 0: Ziel- und Entwurfsfreigabe | Dieser Masterplan, Szenarien A–L und prototypisch durchgespielte Bildschirm-/Dialogabläufe | Dennis bestätigt die tragenden Entscheidungen; entscheidende Widersprüche sind geklärt. Beide Kinder beurteilen einen kurzen Ablauf jeweils selbst. |
| 1: Fundament | Zusammengeführter Code, saubere Datenbezüge, Fähigkeiten/Lernbelege, Kontextversionen, Job- und Verbrauchsbuch | Keine Verwechslung von Kindern/IDs; Kostenprüfung auch bei Parallelität und Neustart; Änderungen und Korrekturen nachvollziehbar. |
| 2: Vollständiger kurzer Mentorablauf | Einstieg, gezielte Hilfe, eigene neue Antwort, begründeter Abschluss und späterer Abruf; Text, Schnellauswahl, Foto | Drei unterschiedliche Lernhandlungen funktionieren: mathematisches Verfahren, sprachliche Regel und quellenbezogene Erklärung. Gemeinsame Engine, keine drei Sonderlösungen. |
| 3: Alltag über Fächer hinweg | Ereignisgestützte Aktualisierung, Nachholen, Wiederholungsrotation, Fortsetzen, Elternübersicht; bei Bedarf eigener Sprachweg | Szenarien A–G sowie J–L auf echten, korrekt zugeordneten Daten bestanden; kurze Nutzung bleibt verständlich und tragbar. |
| 4: Prüfungsvorbereitung | Themenmatrix, ausgewogene Vorbereitung, feste Übungsklausur, Unterbrechung und Auswertung | Szenarien H und I bestanden; Aufgabenqualität und Bewertung für verwendete Aufgabentypen geprüft. |
| 5: Mehr fachliche Tiefe | Weitere Aufgabenfamilien, schuljahresübergreifende Verbindungen, differenzierte Fachmethoden | Je Familie fachliche Beispiele, Gegenbeispiele und dokumentierte Grenzen; Wirksamkeits-/Kostenmessung bleibt im Rahmen. |

**Vor jeder Freigabe verpflichtende Prüfungen:** keine falsche Kindzuordnung; keine als richtig freigegebene bekannte falsche Musterlösung im Abnahmesatz; keine ungeprüfte Beherrschungsbehauptung; keine verlorenen Antworten bei Neustart; kein doppelter Auftrag durch mehrfaches Antippen; keine Fortsetzung über das reservierte Budget; keine Lösungsauslieferung vor Abgabe einer Simulation. Ein fehlerfreier begrenzter Abnahmesatz beweist keine generelle Fehlerfreiheit.

Für die fachliche Abnahme wird vor Modellvergleich ein fester Satz von zunächst 30 repräsentativen Fällen erstellt, zehn je erster Lernhandlung. Er enthält richtige und alternative Antworten, typische Fehler, falsche Begründungen trotz richtigem Ergebnis, unleserliche Eingaben und verweigerte/knappe Antworten. Erwartete Bewertungen und Hilfen werden vorab festgelegt und stichprobenartig menschlich geprüft. Modell-/Promptänderungen werden daran verglichen. Fachlich erhebliche Fehler sperren die betroffene Aufgabenfamilie; geringe stilistische Mängel werden dokumentiert, ohne endlose Perfektionsschleifen auszulösen.

**Nach dem Plan verbleibende konkrete Entscheidungen:** Feinheiten der Darstellung nach einem kurzen Test mit jedem Kind; Freigabe zusätzlicher Bewertungsarten nach fachlichem Nachweis. Der finanzielle Entwurf steht mit 50 Euro pro Monat; Modellzuordnung und technische Teilgrenzen werden innerhalb dieses Rahmens anhand der Verbrauchsmessung festgelegt. Die übrigen hier vorgeschlagenen Architekturentscheidungen kann Dennis als zusammenhängenden Entwurf bestätigen. Er muss keine Liste technischer Einzelentscheidungen abarbeiten.

Der nächste Umsetzungsschritt beginnt auf Basis dieses abgestimmten Entwurfs. Die laufende Anwendung wurde für die Erstellung dieses Dokuments nicht verändert.
