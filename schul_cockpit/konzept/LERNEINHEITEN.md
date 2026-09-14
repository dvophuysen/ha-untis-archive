# Zuschnitt und Reihenfolge der Lerneinheiten

Stand: 15.09.2026. Prüfbericht und Entwurf zur Entscheidung. Grundlage ist eine
Durchsicht der tatsächlich entstandenen Themen beider Kinder über dreizehn Monate,
nicht eine Überlegung am Schreibtisch.

## Wie es heute arbeitet

Ein Hintergrunddienst sucht alle zehn Minuten je Kind nach Unterrichtseinträgen, die
noch nicht ausgewertet sind. Er nimmt sich ein einziges Fach vor, bündelt bis zu 24
Einträge und lässt die KI daraus Themenfelder bilden. Bestehende Titel des Fachs
werden mitgegeben mit der Anweisung, passende exakt wiederzuverwenden. Einträge ohne
erkennbaren Lerninhalt soll die KI als unklar zurückgeben, mit einer Rückfrage.

Aus jedem Thema entsteht einmalig eine kurze Verständnisaufgabe. Bereits vorhandene
Aufgaben und ihre Wiederholungsstände werden nie überschrieben.

Drei Eigenschaften dieses Verfahrens sind für das Folgende entscheidend. Es ist rein
hinzufügend: Ist ein Eintrag einmal einem Thema zugeordnet, wird diese Zuordnung nie
wieder überprüft. Es sieht immer nur einen Ausschnitt: bis zu 24 Einträge eines Fachs,
plus die letzten 40 Titel. Und es kennt keinen Schuljahreswechsel; das Fenster reicht
dreizehn Monate zurück.

Die Liste, die im Plan erscheint, entsteht getrennt davon. Sie geht die Unterrichtsstunden
von neu nach alt durch und bildet je Eintrag einen Schlüssel: Hat die Stunde ein
erkanntes Thema, zählt das Thema. Hat sie keines, wird der rohe Eintragstext zum Titel
der Lerneinheit.

## Was die Durchsicht zeigt

Insgesamt 81 Themen über beide Kinder, aus 350 ausgewerteten Unterrichtseinträgen in 17
KI-Läufen. Der fachliche Zuschnitt ist überwiegend brauchbar: Titel wie „Brüche
erweitern, kürzen und vergleichen" oder „Substantive der a-/o-Deklination und
Satzglieder" beschreiben, worum es ging, und sind für ein Kind lesbar. Das Verfahren
funktioniert im Kern.

Sechs Schwächen sind dabei klar geworden.

### Das Urteil „kein Lernthema" wurde gespeichert und übergangen

Das ist der Fehler, den du im Fach Englisch gesehen hast, und er ist der schwerwiegendste.
Die KI hat organisatorische Einträge zuverlässig erkannt und korrekt als unklar
markiert, mit Rückfragen wie „Wurde bei den Klassengeschäften ein fachlicher
Englischinhalt behandelt?" oder „Wurde bei der AG-Vorstellung ein geschichtliches Thema
behandelt?".

Der Plan hat dieses Urteil nicht gelesen. Er prüft nur, ob ein Thema vorliegt, und
nimmt sonst den Rohtext als Titel. Also standen genau die Einträge, die die Auswertung
aussortiert hatte, als Lerneinheiten in der Liste: eine AG-Vorstellung in der Aula, eine
Bücherausgabe mit Hausaufgabenvergleich, eine Vertretungsstunde. Über beide Kinder
waren 40 Einträge als unklar markiert; jeder davon konnte auf diesem Weg zur
Übungsaufgabe werden.

Behoben. Der Plan überspringt jetzt, was die Auswertung ausdrücklich als unklar
eingestuft hat.

### Die Liste hat keine Ordnung, die man sehen kann

Sie folgt dem Datum der jüngsten Stunde, absteigend. Dadurch stehen Einheiten desselben
Fachs weit auseinander, in einer beobachteten Liste etwa Mathematik an Position 7, 10
und 11 und Latein an 2, 12 und 16. Nichts daran ist falsch, nur unbrauchbar für einen
Menschen, der überlegt, was er als Nächstes tut.

Hinzu kommt, dass die Übersicht der erkannten Themen nach einer anderen Regel sortiert
als der Plan. Zwei Ansichten derselben Sache, zwei Reihenfolgen.

### Ein Themenfeld zerfällt in Teile, die niemand wieder zusammenführt

Weil das Verfahren nur hinzufügt, entstehen über Wochen Reihen wie fünf getrennte
Themen zur Bruchrechnung, zwei zum simple past oder drei zum Frankenreich. Fachlich ist
jeder Zuschnitt für sich vertretbar. Als Liste ist es zu kleinteilig, und vor allem geht
verloren, dass die Teile aufeinander aufbauen.

Umgekehrt gibt es Themen aus einer einzigen Stunde, deren Beleglage dünn ist.

### Das vorige Schuljahr steht gleichberechtigt daneben

Das Auswertungsfenster reicht dreizehn Monate zurück. Etwa die Hälfte aller Themen
stammt aus dem vorigen Schuljahr und aus einem niedrigeren Jahrgang. Sie erscheinen
ohne Unterschied neben dem aktuellen Stoff. In einem Fach bestand der gesamte
Themenbestand aus Einträgen des vorigen Jahres.

### Doppelstunden zählen doppelt

Eine Doppelstunde steht als zwei Einträge mit identischem Text im Archiv. Beide landen
im selben Thema und erscheinen als zwei Belege. Der Eindruck, wie ausführlich etwas
behandelt wurde, verzerrt sich damit zugunsten der Fächer mit Doppelstunden.

### Ein Eintrag kann nur zu einem Thema gehören

Unterrichtseinträge mischen häufig Organisation und Inhalt in einer Zeile, etwa
„Organisatorisches zur Klassenfahrt; general information; conditionals" oder
„Organisatorisches: Leistungsanforderungen, Materialien / My summer holidays". Das
Datenmodell erlaubt je Stunde genau eine Zuordnung. Entweder der ganze Eintrag wird
zum Thema gezählt, samt Organisationsteil, oder er fällt ganz heraus.

## Vorschläge

### Reihenfolge und Gruppierung

Zwei Blöcke statt einer langen Liste.

Oben steht, was jetzt dran ist: fällige Wiederholungen und Themen, zu denen das Kind
Unsicherheit gemeldet hat. Dieser Block ist kurz und deshalb ungruppiert; er ist nach
Dringlichkeit sortiert.

Darunter der Bestand, nach Fächern gruppiert. Innerhalb eines Fachs die ältesten
ungeprüften Themen zuerst. Das ist die Antwort auf deine Frage nach der Richtung: Neu
Behandeltes ist noch frisch, das Risiko liegt bei dem, was länger zurückliegt und nie
überprüft wurde. Ein Fach zeigt zugeklappt seine Zahl und das älteste offene Thema.

Die Themenübersicht der Eltern bekommt dieselbe Ordnung. Eine Sache, eine Reihenfolge.

### Nächtliche Konsolidierung, und warum sie fast nie zusammenführen darf

Mein erster Entwurf hat zwei Vorgänge vermengt, die auseinandergehören. Der Einwand,
dabei Genauigkeit zu verlieren, trifft genau diese Stelle.

Gruppieren heißt: Mehrere Themen erscheinen unter einem Feld, in der Reihenfolge, in der
sie aufeinander aufbauen. Jedes Thema behält seinen Titel, seine Belege, seinen
Wiederholungsstand und seine Aufgabe. Es geht nichts verloren, die Liste wird nur
lesbar.

Zusammenführen heißt: Aus zwei Themen wird eines. Dabei geht etwas verloren, und zwar
das Wichtigste. Werden „Brüche erweitern und kürzen" und „Brüche addieren" zu
„Bruchrechnung", kann der Lernstand nicht mehr sagen, dass das eine sitzt und das
andere nicht. Genau diese Unterscheidung ist der Zweck der ganzen Beobachtung.

Das Problem, das wir lösen wollen, ist ein Anzeigeproblem: Die Liste ist unübersichtlich.
Anzeigeprobleme löst man in der Anzeige. Also gruppieren, und zusammenführen nur im
Ausnahmefall.

Zusammengeführt wird nur, wenn die beiden Themen nie wirklich verschieden waren. Alle
drei Bedingungen müssen gelten: Sie beschreiben denselben Vorgang statt zweier Schritte;
sie liegen unmittelbar beieinander; und an keinem von beiden wurde bereits geübt, es
gibt also weder Belege noch einen Wiederholungsstand. Trifft eine der drei nicht zu,
wird gruppiert und nicht zusammengeführt.

Daraus folgt eine Faustregel für den Zuschnitt insgesamt: Für den Nachweis ist fein
besser, für die Übersicht ist grob besser. Das sind zwei Aufgaben, keine eine. Die
Belege bleiben so fein, wie unterrichtet wurde; die Übersicht wird so grob, wie ein
Mensch sie im Kopf behalten kann. Weil sich Gruppen zuklappen lassen, ist beides
gleichzeitig möglich.

Der nächtliche Lauf nimmt sich daher ein Fach je Kind vor und beantwortet vor allem die
Gruppierungsfrage: Welche Themen gehören zu einem Feld, und in welcher Reihenfolge bauen
sie aufeinander auf? Die Zusammenführungsfrage stellt er nur für Themenpaare, die die
drei Bedingungen oben erfüllen.

Zwei weitere Grenzen. Ein Thema, an dem bereits geübt wurde, verliert seinen Titel nie;
ein Oberthema verweist darauf, statt es zu ersetzen. Und je Fach höchstens eine
Umstrukturierung pro Woche, damit die Ordnung nicht unter den Kindern wegwandert.

Offen bleibt, ob ein Oberthema selbst übbar sein soll. Dafür spräche eine
Wiederholung, die quer über die Teile prüft; dagegen, dass ein Ergebnis darauf keinem
Teil zugeordnet werden kann. Vorschlag: zunächst nicht übbar, nur Ordnungsrahmen.

### Schuljahresgrenze

Themen aus abgeschlossenen Schuljahren gehören in den Bestand, nicht in die Liste. Der
Schnitt ist derselbe wie beim Klausurarchiv, der 1. August. Ein Feld, das
weitergeführt wird, darf die Teile des Vorjahrs als Grundlage ausweisen, ohne sie als
offene Aufgabe zu führen.

### Doppelstunden

Belege werden nach Tag gezählt, nicht nach Zeile. Zwei gleiche Einträge desselben Tages
sind eine Behandlung.

### Gemischte Einträge

Der saubere Weg wäre, je Eintrag den inhaltlichen Teil getrennt festzuhalten und nur
diesen dem Thema zuzuordnen. Das ist eine Änderung am Datenmodell und sollte erst nach
den übrigen Punkten kommen. Bis dahin gilt die schärfere Regel: Ist ein Eintrag
überwiegend organisatorisch, wird er als unklar geführt und erscheint nicht als
Lerneinheit, auch wenn am Rand ein Fachwort vorkommt.

## Offene Fragen

Ob sechs Themen je Fach und Schuljahr der richtige Anlass für eine Umstrukturierung
sind. Ob die Rückfragen der Auswertung den Eltern aktiv angeboten werden, damit ein
knapp beschriebener Eintrag nachträglich zum Thema wird; heute bleibt er als Stunde mit
offener Frage stehen, und niemand sieht die Frage.

Entschieden am 15.09.2026: Sport, Schwimmen und Verfügungsstunde erzeugen keine
Übungsaufgaben. Bewegung lässt sich am Handy nicht nachholen, die Verfügungsstunde ist
kein Lernfach.

Ebenfalls entschieden: Ein Eintrag ohne Thema ist nicht gleich ein Eintrag ohne Wert.
Die Auswertung unterscheidet organisatorisch von inhaltlich zu knapp beschrieben; nur
das Erste fällt aus den Übungsaufgaben. Anlass war, dass ein Unit-Einstieg und ein
Lehrwerkkapitel zunächst mit der Bücherausgabe zusammen verschwunden sind.
