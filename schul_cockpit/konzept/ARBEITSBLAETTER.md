# Arbeitsblätter mit Bezug: welches Blatt ist gemeint?

Stand 17.09.2026. Entschieden (D85), Stufe 1 gebaut in 0.81.0. Anlass:
Nutzerrückmeldung nach der Fehlbindung einer Ausarbeitung an „Arbeitsblatt
beenden“ (D83).

## Entschieden am 17.09.2026

1. Raten abgeschafft; auch eindeutige Fälle sind nur Vorschläge zum Antippen.
2. Ein ausgefülltes Blatt ist Blatt und Bearbeitung zugleich.
3. Kind und Eltern ordnen zu; Eltern berichtigen.
4. Bei Stunden ohne Untis-Text genügt der Kandidat nach Stundenplan.

Gebaut in 0.81.0: Rolle an den Verknüpfungen, keine Bindung über die Nähe
im Datum, Vorschläge am losen Blatt in der Materialliste, „Vorhandenes Blatt
zuordnen“ und Foto mit Eintragsbezug in der Quellenbilanz, Blatt je Eintrag.
Offen aus Stufe 2 und 3: Kandidaten schon beim Einwerfen mit Vorsortierung
durch die Auswertung, Kennung in Listen und Mentor, Mentor-Wortlaut bei
fehlendem Blatt.

## Das Problem

Buchseiten haben eine Nummer; ein Arbeitsblatt hat keine. Untis-Einträge sagen
„Arbeitsblatt beenden“, „AB bearbeiten“, „Lückentext Arbeitsblatt
vervollständigen“ und nennen nie, welches Blatt. Heute sind es je Kind zwei
bis vier solche Einträge im Bestand; jedes Fach mit Blättern erzeugt laufend
neue. Zwei Wochen später weiß niemand mehr, welches Blatt zu welchem Eintrag
gehörte.

Was die App heute tut (Stand 0.80.0):

- Jede Nennung „Arbeitsblatt“ wird als Stelle mit Seite 0 gebunden
  (`source_links`).
- Ein Foto der Art Arbeitsblatt oder Handout, das an eine Aufgabe gehängt
  wurde, belegt genau deren Hausaufgabe.
- Ein loses Blatt desselben Fachs innerhalb von fünf Tagen um den Eintrag
  belegt die Stelle ebenfalls: eine Vermutung, die richtig sein kann und
  niemandem gezeigt wird.
- Mitschrift und erledigte Hausaufgabe belegen nichts mehr.

Das Raten ist die Schwachstelle. Es liefert ein falsches „liegt vor“ und macht
das Nachtragen später unmöglich, weil kein Mensch je gesagt hat, was gemeint
war.

## Leitgedanke

Ein Arbeitsblatt bekommt seine Kennung aus dem Ereignis, zu dem es gehört:
Fach, Tag der Ausgabe, Kurztitel. „AB Mathe 26.08. Lückentext Brüche“ ist so
eindeutig wie „S. 104“. Die Ausgabe ist die Stunde, in der die Lehrkraft das
Blatt verteilt hat, oder der Tag, an dem die Hausaufgabe gestellt wurde. Diese
Kennung wird nicht geraten, sondern beim Einwerfen mit einem Tipp gewählt und
später jederzeit berichtigt. Nur ein bestätigter Bezug erzeugt „liegt vor“.

## Vorschlag in vier Teilen

**1. Bezug beim Einwerfen wählen.** Erkennt die Auswertung ein Arbeitsblatt
oder Handout, zeigt die Bestätigungszeile die Kandidaten des Fachs aus den
letzten 14 Tagen: Hausaufgaben und Stunden, die ein Blatt nennen, zuerst
(„Arbeitsblatt beenden, gestellt 16.09.“, „Stunde 15.09.: Laborgeräte AB“),
danach nach Nähe zum Datum, dazu die Ähnlichkeit des erkannten Titels mit dem
Eintragstext („Lückentext“ trifft „Lückentext Arbeitsblatt“). Ein Tipp setzt
den Bezug, „Keins davon“ lässt das Blatt lose. Wird aus einer Hausaufgabe
heraus fotografiert, ist der Bezug schon gesetzt und wird nur angezeigt.

**2. Nur ein bestätigter Bezug belegt.** Die Fünf-Tage-Vermutung entfällt.
Statt still zu binden, wird sie zum Vorschlag in der Gegenlese-Karte: „Ist das
das Blatt zu ‚Arbeitsblatt beenden‘ vom 16.09.?“ mit einem Tipp „Ja“ (wie „So
korrigieren“, D81). Der Mentor bekommt ein Blatt nur über den Bezug der
Hausaufgabe; fehlt er, sagt er „Zu dieser Hausaufgabe ist kein Arbeitsblatt
hinterlegt, zeig mir ein Foto“ statt ein fremdes Blatt zu benutzen.

**3. Rückwirkend zuordnen.** In der Quellenbilanz steht an jedem „fehlt:
Arbeitsblatt“ ein Knopf „Blatt zuordnen“: die Liste der Blätter des Fachs mit
Kennung (Ausgabetag, Titel, Vorschaubild), dazu „Fotografieren“. So lässt
sich der Eintrag von vor zwei Wochen nachtragen, ohne zu suchen. Umgekehrt
zeigt jedes Blatt seine Bezüge und einen Knopf „Weiteren Eintrag zuordnen“.

**4. Ein Blatt, mehrere Einträge.** Ein Blatt taucht in der Stunde der
Ausgabe, in der Hausaufgabe „beenden“ und später in „AB besprochen“ auf. Die
Kennung bleibt dieselbe; jeder Eintrag verweist auf das eine Blatt. Nennt ein
neuer Eintrag ein Blatt, ohne dass ein neues eingeworfen wurde, wird das
jüngste Blatt des Fachs vorgeschlagen, nie gesetzt.

## Datenmodell

`material_links` kennt bereits `task`, `lesson`, `topic`, `exam` mit `origin`
(`ai`, `mensch`). Neu ist die Rolle des Bezugs: `relation` mit `blatt` (das
Material ist das Blatt des Eintrags), `ergebnis` (die Bearbeitung des Kindes
dazu) und `stoff` (Thema). Bisher ergibt sich die Rolle aus der Materialart
(Arbeitsblatt = Blatt, erledigte Hausaufgabe = Ergebnis); ausdrücklich
gespeichert übersteht sie eine Neuauswertung und erlaubt den Sonderfall
ausgefülltes Blatt. Die Kennung wird nicht gespeichert, sondern aus Bezug und
Material abgeleitet: Ausgabetag = Datum der verknüpften Stunde oder „Gegeben
am“ der Hausaufgabe, sonst `document_date`, sonst Aufnahmedatum mit dem
Vermerk „ungefähr“.

`source_links` mit Seite 0 wird nur noch über eine Verknüpfung mit `relation =
blatt` auf denselben Eintrag oder auf die Stunde am Tag der Ausgabe belegt.

## Auswertung

Die Auswertung bekommt zusätzlich die Kandidaten (Einträge der letzten 14
Tage mit Blatt-Nennung) als `hinweise.blatt_kandidaten` und gibt
`sheet_candidate` zurück: den wahrscheinlichsten Eintrag mit Begründung aus
dem Blatt (Überschrift, Aufgabennummern, Datum auf dem Blatt). Das ist die
Vorsortierung für den Tipp, keine Entscheidung. Ein aufgedrucktes Datum auf
dem Blatt ist der stärkste Beleg für die Ausgabe.

## Offene Fragen

1. **Raten abschaffen?** Vorschlag: ja, vollständig; die Vermutung wird zum
   Vorschlag mit einem Tipp. Kosten: bis zur Bestätigung steht „fehlt“, wo
   heute manchmal richtig geraten wurde.
2. **Ausgefülltes Blatt.** Fotografiert das Kind das bearbeitete Blatt, ist es
   Blatt und Ergebnis zugleich. Vorschlag: Art Arbeitsblatt, `contains_solutions`
   wahr, zwei Verknüpfungen (`blatt` und `ergebnis`); der Mentor nutzt nur den
   Aufgabentext, die Übungsklausur schließt es aus.
3. **Wer ordnet zu.** Vorschlag: das Kind beim Einwerfen mit einem Tipp
   (`origin = kind`), Eltern berichtigen in der Gegenlese-Karte; ein Bezug
   der Eltern schlägt einen des Kindes.
4. **Stunden ohne Untis-Text.** Ist keine Stunde des Fachs mit Blatt-Nennung
   da, bleibt der Kandidat „Stunde am Tag X“ nach Stundenplan. Reicht das?

## Reihenfolge, wenn wir das bauen

1. Raten beenden, Vorschlag in der Gegenlese-Karte, „Blatt zuordnen“ in der
   Quellenbilanz, `relation` an den Verknüpfungen. Ein Release.
2. Kandidaten beim Einwerfen mit Vorsortierung durch die Auswertung, Kennung
   in Listen und im Mentor, „Weiteren Eintrag zuordnen“.
3. Mentor-Wortlaut bei fehlendem Blatt, Wochenrückblick nennt Blätter ohne
   Bezug.
