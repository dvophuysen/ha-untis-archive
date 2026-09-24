> Archiviert am 24.09.2026. Historischer Stand, gilt nicht mehr. Maßgeblich sind [konzept/README.md](../README.md) und die dort verlinkten Dokumente.

> Maßgebliche Zielbeschreibung: [abgestimmter Masterplan](MASTERPLAN.md). Implementierter Stand und Grenzen: [Mentor 0.25.0](MENTOR_BETRIEB.md). Der folgende Text dokumentiert die frühere Architekturvorarbeit.

# Lernmentor: Fähigkeiten erkennen, verstehen und dauerhaft verbinden

Stand: 12. September 2026. Architekturentwurf; ausdrücklich kein Nachweis bereits implementierter Funktionen.

## Ziel und Verantwortung

Die Kinder erhalten kurze, altersgerechte Lernbegleitung auf dem iPhone. Sie müssen eine Wissenslücke nicht selbst benennen können. Der Mentor hilft beim Verstehen, überprüft eigenständiges Anwenden, fördert Selbstorganisation und bereitet auf die Beteiligung im Unterricht vor. Noten sind ein ergänzendes Ergebnis. Lernzeit und Zufriedenheit sind gleichberechtigte Erfolgskriterien.

Ein Klassenunterricht kann nicht jederzeit individuelles Vorwissen, Tempo, Erklärungsbedarf und persönliche Rückmeldungen berücksichtigen. Daraus folgt keine pauschale Diagnose pädagogischer Defizite einer Lehrkraft. Der Mentor ergänzt Erklärungen und Übungsgelegenheiten. Er soll Beschwerden ernst nehmen, ohne Partei gegen Lehrkräfte zu ergreifen. Bei sozialen Problemen, Müdigkeit oder Belastung ist zusätzliche Fachübung nicht automatisch die passende Antwort.

## Stand der Software

- Live zuletzt bestätigt: 0.23.2, Schuljahresprofile, Materialien, Aufgaben, Hinweise, Selbsteinschätzung, Wiederholungsintervalle und Tagesbudget.
- Lokal vorbereitet: inkrementelle Themenauswertung seit Beginn des vergangenen Schuljahres; einfache Erklärungen, Verbindungen und Kurzcheck-Entwürfe; Quellenbezug, Cache und Tokenzähler. Backendtests und Frontend-Build bestanden. Nicht mit dem tatsächlichen Azure-Modell erprobt und noch nicht ausgerollt.
- Noch nicht implementiert: adaptiver Mentor-Dialog, getrenntes Modell einzelner Fähigkeiten, belastbare Antwortbewertung, fortlaufende Aufgabenvarianten, fächerübergreifende Abdeckungsplanung und Hintergrundauswertung.
- Der bestehende Erfolgseintrag ist Selbsteinschätzung. Er darf nicht rückwirkend in einen objektiven Kompetenznachweis umgedeutet werden.

## Pädagogischer Ablauf

1. Ankommen: kurze Frage oder Auswahl, keine verpflichtende Stimmungserfassung.
2. Lernanlass aus Unterricht, Rückmeldung, fälliger Wiederholung oder Wunsch des Kindes vorschlagen. Eine überschaubare Alternative und Pause bleiben möglich.
3. Eine konkrete Aufgabe zeigen. „Ich weiß nicht“ gilt als zulässige Antwort. Kein Kind muss Fachbegriffe verwenden, um Hilfe zu erhalten.
4. Aus Antwort und Arbeitsweg mögliche Ursachen ableiten: Begriff, Vorwissen, Verfahren, Aufgabenverständnis oder Ausdruck. Diese Ursachen bleiben zunächst Hypothesen.
5. Mit einer kleinen Gegenprobe unterscheiden, welche Erklärung eher passt. Wenige Nachfragen; kein endloses sokratisches Verhör.
6. Passende Hilfe: Alltagssprache, korrektes Bild, ausgearbeitetes Beispiel oder kleinerer Schritt. Denkentscheidungen explizit vormachen. Grenzen einer Analogie nennen; Etymologie nur verwenden, wenn gesichert.
7. Eine veränderte Aufgabe ohne vorweggenommene Lösung anbieten. Eine soeben gelesene Erklärung ist Unterstützung; Ergebnisse unmittelbar danach sind keine dauerhaften Beherrschungsnachweise.
8. Später eine neue Variante ohne Hilfe anbieten, danach auch Übertragung in einen anderen Zusammenhang.
9. In einem Satz sichtbar machen, was nun gelingt und welche Lernstrategie geholfen hat. Verlässlich enden.

Beispiel bei „Mathe ist blöd“: Gefühl anerkennen; eine Wahl zwischen aktueller Aufgabe und einfachstem Beispiel anbieten. Bei falscher Bruchaddition ein Bild oder eine Frage zu gleich großen Teilen verwenden. Damit prüfen, ob die Bruchvorstellung oder nur die Rechenregel fehlt. Dieser Befund bleibt bis zu weiteren Beispielen vorläufig.

## Auswahl und nachhaltiges Wissen

Die Planung verbindet drei Lernanlässe über die Woche:
- Akut: gemeldete Unsicherheit, beobachtete Schwierigkeiten, noch offenes Nachholen.
- Erhaltung: Stichproben auch bei positiv bewerteten Themen; zeitlich verteiltes Abrufen bekannter Fähigkeiten.
- Verbindung und Vorbereitung: bekanntes Wissen mit Neuem verknüpfen, kleine fachliche Ausblicke, eine echte Frage oder ein Beispiel für den nächsten Unterricht vorbereiten.

Nicht jede Sitzung muss alle drei Anlässe enthalten. Die vorhandene Zeitgrenze bleibt bindend. Der Planer reserviert Gelegenheiten für Erhaltung und rotiert über Fächer; akute Themen dürfen andere Fächer nicht dauerhaft verdrängen. Konkrete Anteile werden im Familienversuch angepasst und sind keine behauptete wissenschaftliche Konstante.

Wiederholungsintervalle gehören künftig zur Fähigkeit, nicht nur zur identischen Aufgaben-ID. Antwortvarianten verhindern, dass auswendig gelernte Aufgaben mit Verständnis verwechselt werden. Nach einer Klausur läuft Erhaltung weiter. Klassenarbeiten ändern Prioritäten, setzen den Lernverlauf aber nicht zurück.

Ein zeitliches Fenster „seit letzter Klausur“ beweist keinen Stoffumfang. Prüfungsdatum, tatsächliche Themenliste und ermittelter Unterrichtsverlauf bleiben getrennt. Lehrpläne geben Rahmen, keine sichere Unterrichtsreihenfolge. Vorwissen und Ausblicke werden ausdrücklich als fachliche Vorschläge gekennzeichnet.

## Architektur

Bestehende App, Anmeldung, SQLite-Datenbank, Untis-Archiv, Kalender und Azure-Anbindung bleiben erhalten. Ergänzt werden folgende dauerhafte Entitäten:

| Baustein | Inhalt und Aufgabe |
|---|---|
| Fähigkeiten | Kleine überprüfbare Lernziele innerhalb von Fach und Themenfeld; nicht bloß Kapitelüberschriften |
| Beziehungen | Voraussetzung, Teil von, verwandt, Anwendung; Quelle und Sicherheit der Zuordnung |
| Beobachtungen | Aufgabe und Variante, Antwort, Kriterienbewertung, Hilfen, Zeitpunkt, Unsicherheit, Herkunft |
| Lernstand | Noch unbekannt, in Arbeit, mit Hilfe, wiederholt selbstständig, mit Abstand abgerufen, übertragen; keine künstlich genaue Prozentzahl |
| Mentorsitzung | Aktuelles Ziel, Lernphase, gestellte Fragen, erlaubte nächste Schritte, begrenzte Dialogzusammenfassung |
| Aufgabenfamilien | Geprüfte Aufgabe, Kriterien, typische Fehlvorstellungen, Varianten und Lösungsprüfer |
| Planung | Verteilte Wiederholung, Fachabdeckung, akut gemeldete Bedürfnisse, Zeitbudget und nächste Unterrichtsgelegenheiten |

Der Dialog ist eine Oberfläche dieser Architektur, nicht der alleinige Speicher. Eine serverseitige Ablaufsteuerung entscheidet über erlaubte Aktionen. Die KI schlägt eine Frage, Erklärung oder Bewertung strukturiert vor; sie erhält keinen direkten Zugriff zum Ändern von Noten oder Lernstand. Die App validiert Zustände, Quellen, Aufgabenreferenzen und Budget.

Bei eindeutig prüfbaren Ergebnissen werden deterministische Prüfungen verwendet. Freie Begründungen benötigen nachvollziehbare Kriterien; alternative richtige Antworten müssen zulässig bleiben. Uneindeutige Bewertungen werden als unsicher behandelt. Ein einzelner Fehler, langsames Tippen oder Frust begründet keine diagnostische Zuschreibung. Schwierigkeit und Unterstützungsart werden zuerst angepasst, statt Etiketten wie „schlecht in Mathe“ zu vergeben.

Das System bleibt eine Lernhilfe, keine klinische Diagnostik. Wiederholt nicht auflösbare Schwierigkeiten führen zu einer sachlichen Bitte um Unterstützung durch Eltern oder Lehrkraft.

## Dialog und iPhone

Eine Frage beziehungsweise Aufgabe pro Schritt. Kurze Texte, große Bedienelemente, Antwort per Auswahl, Freitext oder Ergebnisnotiz einer Papieraufgabe. „Anders erklären“, „Kleinerer Schritt“, „Weiß ich nicht“ und „Pause“ sind immer erreichbar. Ein freier Chat kann ergänzt werden; der Standard bleibt ein geführter Lernablauf. Spracheingabe ist optional später zu evaluieren.

Kein Leistungsranking unter Geschwistern, keine Strafe für ausgelassene Tage, keine Lobautomatik für jede Antwort. Fortschritt an konkretem Können zeigen. Interessenbeispiele nur verwenden, wenn das Kind sie mag und sie den Lerninhalt tatsächlich erklären.

Eltern sehen eine kurze Übersicht: Was wurde beobachtet? Was ist nur vermutet? Was hat geholfen? Wo ist menschliche Hilfe sinnvoll? Nicht die tägliche Verwaltung von Dutzenden Aufgaben. Langfristig sollen geprüfte Aufgabenfamilien und automatische Validierung den Freigabeaufwand reduzieren; die aktuelle manuelle Entwurfsfreigabe ist eine Übergangslösung.

## Qualität und Verbrauch

- Inhaltsauswertung nur für neue/geänderte Unterrichtseinträge, in begrenzten Gruppen.
- Feedbackauswertung, Termine, Wiederholungsplanung und Auswahl überwiegend lokal.
- Modell erhält nur die relevante Fähigkeit, Beispiele, kurze Sitzung und notwendige Beobachtungen; nicht das gesamte Schularchiv bei jeder Antwort.
- Tokenverbrauch und fehlgeschlagene Aufrufe protokollieren; tägliche Grenzen und verbindliches Ende je Sitzung. Ein Eurobudget setzt verifizierte Preise oder explizit konfigurierte Kostensätze voraus.
- Modellwahl über gemessene fachliche Qualität und Latenz, nicht allein über Namen; Wechsel ohne Verlust des Lernstands ermöglichen.
- Beispiele prüfen: falsche Antwort aus unterschiedlicher Ursache, richtige Antwort mit falscher Begründung, alternative richtige Lösung, unleserliche Eingabe, fehlendes Material, Müdigkeit, sichere Selbsteinschätzung trotz Fehler.
- Architekturtests: Kindtrennung, unterbrochene Sitzungen, Hilfehistorie, idempotente Verarbeitung, korrigierte Daten, Wiederholung über neue Aufgaben, Fachrotation und Kostenobergrenzen.
- Pädagogische Erfolgskriterien: spätere neue Aufgaben ohne Hilfe, weniger benötigte Hilfe, bessere Erklärung des Vorgehens, verträgliche Lernzeit und weniger Frust. Noten ergänzend betrachten.

## Umsetzungsfolge

1. Themenauswertung fachlich an echten Daten prüfen und als transparente Vorschlagsgrundlage fertigstellen.
2. Fähigkeiten, Beobachtungen und Mentorsitzungen ergänzen; vorhandene Selbsteinschätzungen als solche übernehmen.
3. Einen vollständigen Mentorablauf mit offenen kurzen Aufgaben, Gegenprobe, angepasster Erklärung und neuer Aufgabe implementieren. Die Architektur bleibt fachoffen; die ersten geprüften Aufgabenfamilien decken Deutsch und Mathematik ab.
4. Verzögerte Varianten, Fachrotation und Verbindungen integrieren. Dann Vorbereitung und Klausurstoffabgleich ausbauen.
5. Den Bedarf an Elternfreigaben mit geprüften Aufgabenfamilien und überprüfbaren Kriterien reduzieren. Autonomie erst erhöhen, wenn typische Fehlerszenarien zuverlässig behandelt werden.

## Forschungsgrundlage und Grenzen

- EEF: Strategien explizit am Fachinhalt vermitteln; Denken vormachen, gemeinsam üben, Hilfen schrittweise zurücknehmen. https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/metacognition-and-self-regulation
- IES/WWC: zeitlich verteiltes Lernen, Abrufübungen, ausgearbeitete Beispiele im Wechsel mit eigener Problemlösung, konkrete und abstrakte Darstellungen verbinden. https://ies.ed.gov/ncee/wwc/PracticeGuide/1
- Bastani et al., PNAS 2025: In einem Mathematik-Feldexperiment waren bessere Leistungen mit verfügbarer KI kein Beleg für bessere eigenständige Leistung. Hinweise statt fertiger Antworten begrenzten negative Effekte; ein allgemeiner positiver Nachweis für unseren Mentor folgt daraus nicht. https://doi.org/10.1073/pnas.2422633122

Die konkreten Abläufe und Architekturentscheidungen hier sind ein begründeter Entwurf für diese Familie, kein wissenschaftlich validiertes Gesamtprodukt und kein Versprechen von Bestnoten oder dauerhafter Schulfreude.
