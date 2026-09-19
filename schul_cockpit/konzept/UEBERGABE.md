# Übergabe an die nächste Session

Stand 19.09.2026, abends. Live läuft Schul-Cockpit **1.12.6**, `main` und
Arbeitsbranch stehen gleich, 550 Tests grün. Keine Kindernamen, PINs oder
Schlüssel in diesem Dokument (D15/D68).

## Das Nächste zuerst

Der neue Vokabelweg ist gebaut, ausgeliefert und an allen vier Listen gemessen.
Offen sind zwei Stellen, beide in Kind A Spanisch:

- „Unidad 1 ¡Bienvenidos a mi barrio!" trägt 451 Wörter. Der Laufkopf dieser
  Seiten nennt keine Marke, also fehlt der Hinweis, wo die nächste Unidad
  beginnt. Die Elternansicht `GET /learning/vocab/SPANISCH/outline` zeigt ohne
  Modellaufruf, was die Gliederung zu sehen bekommt — dort anfangen.
- „Lista cronológica" (86 Wörter) ist ein eigener Anhangteil, kein Wortschatz
  einer Einheit. Dafür gibt es `_OTHER_PART`; der Name steht nur noch nicht
  darin, und ob er allgemein genug ist, gehört geprüft.

Kleinere Beobachtungen: In Kind A Englisch hat S. 164/165 keine einzige
Überschrift gemeldet, deshalb hängen dort 77 Wörter an „Station 2: Idiot
nephew?". Bei Kind B steht „Irregular verbs" unter „Unit 1" statt unter dem
Grammatikanhang, weil „Grammar" nur als Laufkopf vorkommt und ein Laufkopf nie
einen Block öffnet.

## Was diese Session gebaut hat

Entscheidungen D137 bis D140 in [ENTSCHEIDUNGEN.md](ENTSCHEIDUNGEN.md).

- **1.11.0 (D137)** Der erste Lesedurchgang jeder Seite läuft auf der Stufe
  „klein", also auf der zweiten Foundry. Die gründliche zweite Lesung ist ein
  Zugewinn, keine Bedingung: Scheitert sie, gilt die erste. Anlass waren fünfzig
  Materialien mit 502, weil beide Stufen auf der ersten Foundry lagen.
- **1.11.1 (D138)** Jede gedruckte Seite wird nur einmal gelesen. Kind A
  Englischbuch kommt als Doppelseite, und der Viewer lieferte auf jede ungerade
  Bestellung eine um vier Seiten versetzte Doppelseite: vierzig Abrufe für rund
  fünfzehn Seiten. Das allein erklärt die unbrauchbaren Listen.
- **1.12.0 (D139)** Die Gliederung entsteht aus dem Vergleich aller Seiten eines
  Buchteils. Zwei getrennte Fragen je Seite — erst die Überschriften, dann die
  Wörter —, eingeordnet wird in der App. Die dritte Ebene (Kasten) entfällt,
  `regroup()` setzt die Sortierung ohne Modellaufruf und ohne einen Lernstand
  anzufassen, und das Wörterverzeichnis hinter dem Wortschatzteil wird
  abgeschnitten.
- **1.12.0 (D140)** Doppelseitenbücher werden nur noch nach ihren linken Seiten
  bestellt; eine gelieferte Doppelseite deckt beide gedruckten Seiten ab.

## Gemessen, nicht geschätzt

Alle vier Listen am Abend des 19.09., nach sechs Nachbesserungen, die jede am
echten Lauf abgelesen ist:

- Kind A Englisch: 9 Einheiten, 550 Wörter, genau die Gliederung des Buchs
  (Unit 1, Across cultures 1, Text smart 1, Across cultures 2, Unit 2, Text
  smart 2, Across cultures 3, Unit 3, Across cultures 4) mit den Abschnitten in
  Buchreihenfolge. Vorher: 15 zusammenhanglose Bündel, 1217 Wörter.
- Kind B Englisch: 4 Einheiten, 381 Wörter.
- Kind B Latein: 54 Wörter, davon die 42 geübten mit vollem Verlauf. Der
  Lernstand hat den ganzen Umbau überstanden.
- Kind A Spanisch: 7 Einheiten, 671 Wörter statt 1523.
- Die erste Vokabel-Doppelseite (Material 251, gedruckt 160/161) liest das
  kleine Modell fehlerfrei: 21 von 21 Wörtern, richtige Reihenfolge, richtige
  Bedeutungen, und von der Erklärseite links kein einziges Wort — auch nicht
  aus der Lauttabelle, die wie eine Wortliste aussieht.
- Kind A Englisch kam in 40 Abrufen für 24 verschiedene Doppelseiten; gerade
  Bestellungen richtig, ungerade um vier Seiten versetzt. Gedruckt 186–189
  fehlen bis heute.

## Was sich dabei als falsch erwiesen hat

Zwei Regeln, die plausibel klangen und an echten Seiten scheiterten:

- **Die Optik entscheidet nichts.** „Größer, farbig, gerahmt" wird
  mitgeschrieben, aber ein Buch, das seine Abschnitte genauso hervorhebt wie
  seine Teile, macht daraus lauter Einheiten — bei Kind B wurden „Station 2",
  „Story" und „Check-out" zu eigenen Einheiten.
- **Eine Überschrift am Seitenkopf ist nicht automatisch eine Einheit.** Sie ist
  der Laufkopf und öffnet nie einen Block; sie nennt aber die Marke des Teils,
  und das ist der stärkste Hinweis überhaupt.

## Offen

- Die Messung oben. Ohne sie ist 1.12.0 nur getestet, nicht bewährt.
- Ein Teil ohne Nummer wird an seiner Optik als Einheit erkannt
  (`head_levels`). Das ist die einzige Regel, die auf eine Beobachtung des
  Modells baut; sie greift nur, wenn höchstens die Hälfte der übrigen
  Überschriften genauso aussieht. Beim Messen daraufschauen.
- Eine Korrekturschnittstelle für die Gliederung wäre jetzt billig: Einheit und
  Abschnitt einer Seite von Hand setzen, ohne neu zu lesen. `regroup()` müsste
  solche Festlegungen nur achten, wie `book_chapters.locked` es vormacht.
- Zwei Vokabelseiten scheitern weiter mit einem Lesefehler; ein paar Materialien
  stehen nicht auf „ready".
- Zielbild Mentor (D126), Stufe 2: Lagebesprechung und Lagebild für die Eltern.
  Entwurf steht, Bau war vom Nutzer zurückgestellt.
- Antwort-Chips und der Prüfungs-Kapitelindex, beide aus früheren Sessions.

## Arbeitsweise

- Vor jeder Änderung den Plan abstimmen und auf ein ausdrückliches Ok warten
  (CLAUDE.md). Reine Lese- und Diagnoseschritte sind ausgenommen.
- Immer auf `main` ausliefern und selbst einspielen: auf der Arbeitsbranch
  entwickeln, `git merge --ff-only`, beide pushen, dann `/store/reload post`
  und `/addons/e54108c7_schul_cockpit/update post` über
  `scripts/ha_supervisor.mjs`. Der Update-Aufruf antwortet mit
  `unknown_error`, obwohl er anläuft; auf die Version warten.
- Jede sichtbare Änderung: Version in `schul_cockpit/config.yaml`, Eintrag in
  `CHANGELOG.md`, Entscheidung als D-Nummer. Versionsstellen: erste neue
  Architektur, zweite Feature-Sets und bedeutsame Funktionsänderungen, dritte
  Korrekturen und Optimierungen.
- Tests `python3 -m pytest tests` (541 grün), Frontend `npm run build`.
  Migrationen ans Ende von `_MIGRATIONS` in `db.py`.
- Messen statt schätzen. Eichungen laufen über `vocab/{fach}/compare` und
  `materials/{id}/analysis/compare`, beide speichern nichts. Ein Vergleich
  zweier Modellstufen darf nie über das Umstellen der Stufe und erneutes
  Einlesen laufen: Der Textstand enthält das Modell nicht, es käme der
  gespeicherte Stand zurück (D129).
- Der Nutzer entscheidet Grundsatzfragen, will Vorschläge mit Empfehlung und
  konsequentes Abarbeiten ohne Rückfragen bei allem anderen. Qualität steht weit
  vor Kosten.
