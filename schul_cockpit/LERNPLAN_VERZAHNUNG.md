# Gemeinsamer Lernplan statt paralleler Vorschlagslisten

Stand: 12.09.2026. Konzeptionelle Ergänzung zum Masterplan nach Prüfung von Josias Live-Ansicht und des Codes. **Die nachfolgende gemeinsame Planung ist noch nicht implementiert.** Version 0.27.0 ergänzt Themenauswahl aus dem Unterricht sowie Druck- und Selbstkontrollfunktionen für Übungsklausuren; sie löst die hier beschriebenen Integrationslücken noch nicht.

## Ziel

Ein Kind soll an einer einzigen Stelle erkennen: Was mache ich heute, weshalb gerade das, wie lange dauert es ungefähr, und wann ist genug? Nach einer Übung muss dieselbe Stelle zeigen, was bearbeitet wurde, was weiterhin offen ist und wann ein kurzer erneuter Versuch sinnvoll ist. Eltern sehen denselben fachlichen Stand mit zusätzlicher Erklärung der Planung. Historische Selbsteinschätzungen bleiben erhalten; sie werden durch spätere Beobachtungen ergänzt.

Planung, Nachhilfe und Fortschrittsanzeige sind verschiedene Ansichten desselben Lernprozesses. Der Mentor führt eine begrenzte Lernaktion aus. Er erstellt keinen konkurrierenden Tagesplan im Chat. Fachübergreifende Organisation und wiederkehrende Termine benötigen normalerweise keinen Modellaufruf.

## Tatsächlich beobachteter Stand bei Josia

Der Plan zeigt am Samstag gleichzeitig „Frei – Pause heute“ und unter „Sollte heute“ fünf offene Fehlstunden sowie Deutsch und Englisch mit jeweils vier unsicheren Rückmeldungen. Daneben stehen Mathematik-Hausaufgaben für Dienstag, zwölf unregelmäßige englische Verben für Mittwoch und eine Geschichtsaufgabe für Freitag. Die Zahlen im Plan sind die Angaben der App, keine neu diagnostizierten Defizite.

Ein Klick auf Deutsch führt zur allgemeinen Fächeransicht. Diese zeigt vor der nächsten Stunde unter anderem:

| Fach | Angezeigter Stoff | Nächste Stunde laut Ansicht |
|---|---|---|
| Deutsch | Zerlegen und verlängern; nominalisierte Adjektive nach Indefinitpronomen; Rechtschreibestrategien | Montag, 14.09., 11:35 |
| Mathematik | Gemischte Zahlen und deren Addition | Dienstag, 15.09., 07:50 |
| Englisch | Irregular verbs/Bildbeschreibung; Simple-Past-Formen von „to be“ | Mittwoch, 16.09., 07:50 |
| Latein | Subjekt/Prädikat, a-/o-Deklination; organisatorischer Text im selben Eintrag | Montag, 14.09., 09:45 |

Mehrere Einträge zu Latein, Kunst und Englisch erscheinen doppelt. Das können Teilstunden derselben Doppelstunde sein; daraus dürfen nicht automatisch doppelte Lernbedarfe werden. Weitsprung steht wegen der nächsten Sportstunde ganz oben. Eine bevorstehende Stunde allein entscheidet aber nicht, welche häusliche Lernaktion sinnvoll oder überhaupt am Bildschirm übbar ist.

Im Code sind die Unterschiede nachvollziehbar:

- `routers/plan.py`: Ein Fach erscheint bei mindestens drei schwachen Rückmeldungen innerhalb des betrachteten Vierwochenfensters; maximal drei „Sollte“-Hinweise. „Frei“ richtet sich ohne Klausur-Endspurt nach anstehenden Pflichtaufgaben, nicht nach allen Lernhinweisen. Deshalb entsteht die sichtbare widersprüchliche Aussage.
- `routers/oral.py`: schwache Rückmeldungen aus sechs Wochen, höchstens drei Einträge pro Fach, sortiert nach nächster Unterrichtsstunde. Keine Auswertung des Mentor-Fortschritts.
- `routers/afternoon.py`: eigener Zeitrahmen mit Hausaufgaben und weiteren Lernideen. Andere Filter und Sortierregeln als Plan und Mentor.
- `mentor_context.py`: berücksichtigt Unterricht, Rückmeldungen, Hausaufgaben, Fehlzeiten, Themenvorschläge und bestehende Mentor-Wiederholungen. Die Auswahl ist eine Liste von Vorschlägen, kein vollständiger Wochenplan. Auch gut bewertete Themen kommen als Kandidaten infrage; eine garantierte regelmäßige Abdeckung besteht damit noch nicht.
- Neuer Mentor: setzt eine Wiederholung nach einer ausgewerteten Antwort derzeit im Wesentlichen auf zwei oder sieben Tage. Die Abstände wachsen nicht fortlaufend mit einer stabilen Erfolgsserie.
- Älterer Lernraum: besitzt bereits eine eigene Folge von 2, 7, 14 und 30 Tagen, basiert dabei auf expliziter Selbsteinschätzung. Diese Daten und die KI-Evidenz des Mentors sind noch kein gemeinsamer Wiederholungsstand.

Ein abgeschlossenes Mentorgespräch entfernt deshalb aktuell keinen Unsicherheitshinweis aus dem Plan. Das Ende eines Chats wäre dafür ohnehin kein ausreichender Beleg. Entscheidend sind die Zuordnung zum ursprünglichen Lernanlass und die Ergebnisse zu den betroffenen Fähigkeiten.

## Wissenschaftliche Grundlage und ihre Grenzen

Zeitlich verteiltes Wiederholen, aktives Abrufen und erklärende Fragen sind sinnvolle Grundlagen. Der IES-Praxisleitfaden empfiehlt außerdem den Wechsel zwischen nachvollziehbaren Lösungsbeispielen und eigenen Lösungsversuchen. Abrufen bedeutet: erst eine eigene Antwort versuchen, danach mit Lösung oder Rückmeldung vergleichen; bloßes Wiederlesen prüft nicht dasselbe. Diese Empfehlungen begründen die Methodenauswahl, nicht die Wirksamkeit unserer konkreten App. [IES: Organizing Instruction and Study to Improve Student Learning](https://ies.ed.gov/ncee/wwc/practiceguide/1)

Planen, das eigene Vorgehen beobachten und das Ergebnis überprüfen sollen ausdrücklich am jeweiligen Fachinhalt gelernt werden. Die App sollte diese Entscheidungen allmählich verständlich machen und dem Kind zunehmend überlassen. [EEF: Metacognition and Self-Regulated Learning, zweite Ausgabe 2025](https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/metacognition)

Das Karteikastenprinzip ist eine verständliche Bedienidee: Schwieriges kommt früher wieder, zuverlässig Abrufbares später. Daraus folgt aber keine für jedes Kind und jede Aufgabe wissenschaftlich vorgeschriebene Folge „2–5–14 Tage“. Die unten genannten Intervalle sind transparente Startregeln unseres Designs und müssen anhand echter späterer Ergebnisse überprüft werden. Weder Selbsteinschätzung noch KI-Bewertung gelten als unfehlbar.

## Welche Informationen zusammengehören

Vier Dinge bleiben getrennt, sind aber ausdrücklich miteinander verknüpft:

1. **Ursprünglicher Anlass:** Unterrichtsrückmeldung, Fehlzeit, Hausaufgabe, eigene Frage oder späterer Fehler. Beispiel: Am 9. September wurde die Nominalisierung als teilweise verstanden bewertet.
2. **Konkretes Lernziel:** etwa „Nach etwas/viel/wenig ein nominalisiertes Adjektiv erkennen und die Schreibung begründen“. Eine Unterrichtsstunde kann mehrere Ziele enthalten; mehrere Stunden können dasselbe Ziel betreffen.
3. **Lernaktion und Ergebnis:** Erklärung, Kurzcheck, eigene Lösung, Foto, Selbsteinschätzung nach der Hilfe. Hilfe, bekannte Musterlösung und unabhängiger Versuch werden unterschieden.
4. **Nächster Schritt:** erneut erklären, fehlendes Originalmaterial besorgen, später selbstständig prüfen oder erst nach längerem Abstand auffrischen.

Stabile IDs für Kind, Fach, Lernziel, Unterrichtsquelle, Planaktion und Lernversuch verhindern, dass dieselbe Unklarheit nur wegen einer anderen Formulierung erneut entsteht. KI-Themengruppen sind Vorschläge für die Zuordnung; die Übereinstimmung einer Überschrift allein genügt nicht zur Gleichsetzung zweier Fähigkeiten. Eindeutige Doppelstunden können zusammengefasst werden, ihre ursprünglichen Quellen bleiben sichtbar.

## Was nach dem Üben im Plan sichtbar werden soll

Ein Planpunkt erhält zwei getrennte Anzeigen: **Bearbeitung** und **fachlicher Stand**.

| Ereignis | Bearbeitung | Fachlicher Stand und Folge |
|---|---|---|
| Gespräch begonnen | Angefangen | Ausgangsfrage bleibt offen |
| Erklärung mit Papa oder Mentor | Heute bearbeitet | Mit Unterstützung verstanden; Kurzcheck ausstehend |
| Eine Aufgabe gelingt unmittelbar nach Erklärung | Heute bearbeitet | Im Anschluss gelungen; noch kein Abstandsnachweis |
| Neue Aufgabe später ohne Hilfe richtig | Für heute erledigt | Selbstständig gezeigt; nächster Termin sichtbar |
| Teilproblem weiterhin falsch | Teilweise bearbeitet | Genau dieses Teilproblem offen, anderes nicht erneut vollständig üben |
| Mehrere passende Aufgaben an getrennten Tagen gelingen | Für heute erledigt | Wiederholungsabstand wächst |
| Material fehlt oder KI kann Antwort nicht sicher beurteilen | Bearbeitung dokumentiert | Ungeklärt; kein erfundener Fehler und kein falsches „erledigt“ |

Die frühere Rückmeldung bleibt beispielsweise als „am 9.9. unsicher“ erhalten. Daneben steht später „am 14.9. selbstständig erklärt – erneuter Kurzcheck am …“. Nachgeholte Fehlstunden bedeuten organisatorisch bearbeiteten Stoff; daraus folgt nicht automatisch, dass jede enthaltene Fähigkeit gefestigt ist. Eine Eltern-Testsession und eine Demo erzeugen keines dieser Kinderergebnisse.

## Wiederholungslogik als gemeinsame Funktion

Pro Lernziel wird ein gemeinsamer Wiederholungsstand geführt; Mentor, Lernkarten, Hausaufgabenprüfungen und Übungsklausuren liefern Ereignisse dazu. Unterschiedliche Aufgabenversionen desselben Ziels bleiben erkennbar.

Ein verständlicher Start wäre die Folge **2, 7, 14, 30 und 60 Tage** nach passenden Erfolgen. Das baut auf der bereits vorhandenen Folge auf und ergänzt einen längeren Abstand. Die tatsächliche Einplanung berücksichtigt erlaubte Lerntage, Zeitrahmen und bevorstehende Prüfungen.

- Richtige, selbstständige Antwort an einem späteren Tag: Abstand erhöhen. Die Entscheidung und der nächste Termin werden angezeigt.
- Richtige Antwort nach Hinweis oder bekannter Lösung: als unterstützten Erfolg festhalten; bald erneut prüfen, nicht sofort hochstufen.
- Fehler oder Stocken: Hilfe/Erklärung und eine überschaubare neue Variante, dann eher am nächsten geeigneten Tag wiederholen. Kein endloses Wiederholen derselben Frage bis zum richtigen Wortlaut.
- Unklare Auswertung: keine automatische Rückstufung; Antwort oder Material klären.
- Mehrere Antworten am selben Tag erzeugen keine Serie langfristiger Beherrschung. Fehlversuche setzen auch nicht den gesamten bisherigen Lernverlauf auf null.
- Krankheit, ein ausgelassener Lerntag oder Ferien sind keine falsche Antwort. Überfällige Termine werden neu verteilt, ohne einen ständig wachsenden Pflichtberg zu erzeugen.
- Nach einer Klausur bleibt das Wissen im Wiederholungsbestand. Klausurergebnisse aktualisieren nur tatsächlich geprüfte und zugeordnete Lernziele.

Für neu behandelte und positiv bewertete Themen gibt es ebenfalls erste spätere Kurzchecks. Ein „verstanden“-Klick erzeugt keine Beherrschungsstufe. Die Planung reserviert regelmäßig Zeit für solche bisher ungeprüften Themen, damit nur unsichere Themen nicht dauerhaft alle anderen verdrängen.

## Lernkarten sind eine Form der Aufgabe

Nicht aus jeder Stunde und jedem Satz automatisch Karten herstellen. Zunächst kleine fachliche Ziele aus dem Stoff ableiten. Karten können beim Formulieren helfen, dürfen aber nicht selbst eine große Zusatzhausaufgabe werden.

| Inhalt | Passende kurze Übungsform |
|---|---|
| Konkrete Vokabeln | Wort abrufen; Übersetzungsrichtung und Verwendung wechseln; originale Schulliste nutzen |
| Grammatik | Eigenen Beispielsatz bilden oder eine Schreibweise begründen |
| Mathematik | Kurze neue Aufgabe, Fehler finden oder erklären, warum ein Verfahren passt |
| Geschichte/Naturwissenschaften | Ursache und Folge erläutern, Abläufe ordnen, Modelle vergleichen |
| Sport/Kunst | Passende praktische Handlung oder Reflexion; kein Textquiz als Ersatz für motorisches Können |

Die App variiert die Aufgabe zum selben Lernziel. Ein wiedererkannter Satz oder eine auswendig gelernte Musterlösung soll nicht mit übertragbarem Können verwechselt werden. Ein eigenes Beispiel des Kindes ist oft aufschlussreicher als die Antwort „Ja, verstanden“.

## Ein sichtbarer Tages- und Wochenplan

**Plan** wird die zentrale organisatorische Ansicht. Sie zeigt heute verbindlich vereinbarte kleine Aktionen und eine anpassbare Vorschau für sieben Tage. Eine Vorschau ist kein starres Versprechen darüber, wie die nächste Woche verlaufen wird.

Jede Aktion zeigt Fach, konkretes Ziel, ungefähre Minuten, Auswahlgrund, Herkunft, letzten Stand und direkte Schaltfläche zum passenden Mentor-Schritt. Beispiel für die spätere Anzeige: „Deutsch · Nominalisierung · 8 Minuten · letzte Rückmeldung teilweise verstanden; nächste Stunde Montag“. Diese Darstellung ist hier eine Designspezifikation, noch keine tatsächlich erzeugte Wochenplanung.

Ein einzelner vereinbarter Zehnminutenblock kann einen zweiminütigen Wiederholungscheck und eine achtminütige Klärung enthalten. Das ist ein Planungsbeispiel, keine zusätzliche Zeitvorgabe für die Kinder. Hausaufgaben, Nachhilfe, Kurzchecks und freiwillige Vorschau dürfen nicht jeweils einen separaten vollständigen Tagesrahmen beanspruchen. Bereits erledigte Arbeit wird genau einmal berücksichtigt. Wenn eine Hausaufgabe dasselbe Lernziel sinnvoll prüft, kann sie eine zusätzliche Übung ersetzen.

Die Priorisierung beachtet fällige Pflichtaufgaben, verbleibende Zeit, nächste Unterrichtsstunde, belegte Schwierigkeiten, fällige Wiederholungen und noch ungeprüfte Themen. Akute Voraussetzungen für die nächste Stunde erhalten Gewicht, können aber nicht automatisch alle anderen Fächer verdrängen. Ein kurzer freiwilliger Ausblick kommt erst nach sinnvoller Entlastung. Bei einem vollen Tag werden weitere Aufgaben verschoben und der Grund erklärt. „Keine Pflichtaufgaben heute“ und „freiwilliger Kurzcheck verfügbar“ sind verschiedene Aussagen; „Frei“ und „Sollte heute lernen“ dürfen nicht widersprüchlich nebeneinanderstehen.

Für Kinder genügt zunächst „Heute insgesamt … Minuten“ plus wenige Aktionen. Eltern können die Wochenvorschau, bewusste Verschiebungen und offene Punkte einsehen. Nach einer Übung steht direkt dort beispielsweise: „Heute bearbeitet; die Begründung sitzt noch nicht – nächster Schritt …“. Eine vorgeschlagene Zeit ist ein Richtwert mit verlässlichem Ende, keine Aufforderung, bis zum Erfolg unbegrenzt weiterzumachen.

## Technischer Umbau und Reihenfolge

1. **Gemeinsames fachliches Zustandsmodell und Quellenzuordnung.** Bestehende Check-ins, `caught_up`, alte selbst bewertete Lernversuche und neue Mentor-Evidenz vorsichtig zuordnen. Kein rückwirkendes Hochstufen alter Selbsteinschätzungen zu unabhängigem Können. Unklare Zuordnungen bleiben ausdrücklich ungeklärt.
2. **Ein gemeinsamer Planungsdienst und ein Zeitkonto.** Plan, Nachmittagsplaner, Fächer-Vorbereitung und Mentor verwenden dieselben Planaktionen. Direkter Einstieg mit Lernziel und ursprünglichem Anlass; gleichartige Empfehlungen werden zusammengeführt. Veraltete Planversionen werden nach aktuellen Hausaufgaben und Unterrichtsdaten überprüft.
3. **Eine gemeinsame Wiederholungsfunktion.** Regeln versioniert und nachvollziehbar; Ereignisse verändern den zuständigen Lernzielzustand und lösen eine begrenzte Neuplanung aus. Positive und negative Rückmeldungen bleiben getrennt von objektiveren Aufgabenbelegen.
4. **Tages-/Wochenoberfläche und Rückweg nach dem Üben.** Minuten, Gründe, nächster Termin und offene Teilprobleme sichtbar; Nachholen und fachliches Festigen getrennt. Die aktuelle „Erledigte anzeigen“-Funktion für Aufgaben reicht dafür nicht.
5. **Wirksamkeit beobachten.** Spätere neue Aufgaben ohne Hilfe, tatsächliche Lernzeit, offene Anliegen, Fachabdeckung und empfundene Belastung betrachten. Mehr Chats oder höhere KI-Punkte allein sind kein Erfolgskriterium.

Datenquellen und Lernversuche bleiben dauerhaft dokumentiert. Die KI wird für fachliche Gruppierung, Diagnosefragen, Erklärungen, Aufgabenvarianten und vorsichtige Bewertung verwendet. Prioritäten, Termine, Budget, Historienverknüpfung und Fortschrittsanzeige bleiben möglichst deterministisch. Vorhandene Gruppen und Aufgaben werden wiederverwendet. Der gemeinsame Familienrahmen von 50 Euro bleibt bestehen; eine verpasste Wiederholung löst keinen automatischen Modellaufruf aus.

## Abnahmekriterien für die nächste Umsetzung

- Derselbe konkrete Anlass erscheint in Plan, Fächeransicht und Mentor mit derselben Zuordnung und demselben aktuellen Stand.
- Eine echte passende Übung ergänzt den Anlass; ein bloß beendeter Chat, eine Demo oder eine Eltern-Testantwort tut das nicht.
- Wiederholungstermin, Hilfe und Begründung der Priorität sind sichtbar. Eine nachträglich korrigierte KI-Einschätzung korrigiert auch die weitere Planung.
- Spätere Wiederholungen wachsen bei passenden Erfolgen; Fehler führen zu gezielter Hilfe statt unbegrenztem Drill. Die Regeln gelten fachübergreifend für passende Aufgabenformen.
- Der Tagesrahmen wird nicht mehrfach ausgeschöpft. „Frei“, Pflichtaufgaben und freiwillige Lernvorschläge widersprechen sich nicht.
- Positiv bewerteter Unterricht erhält begrenzte spätere Checks; Fehlzeiten und unklare Quellen werden nicht als festgestellte Wissenslücken ausgegeben.
- Überfällige Aktionen werden verständlich verschoben; das Kind und seine Eltern sehen, was weiterhin offen ist und warum.
