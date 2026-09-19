# Übergabe an die nächste Session

Stand 19.09.2026. Auf `main` liegt Schul-Cockpit **1.12.0**, im Store bereit;
die laufende Instanz stand beim Schreiben noch auf 1.11.0, weil der Nutzer
Updates selbst einspielt. Arbeitsbranch und `main` stehen gleich, 541 Tests
grün. Keine Kindernamen, PINs oder Schlüssel in diesem Dokument (D15/D68).

## Das Nächste zuerst

Sobald 1.12.0 läuft, muss der neue Vokabelweg an echten Seiten gemessen werden.
Er ist vollständig gebaut und mit Tests abgedeckt, aber noch nie mit einem
echten Modell gelaufen — die Tests beantworten die Modellfragen selbst.

1. Trainer für Englisch (Konto 1) öffnen, dabei laufen beide Lesedurchgänge und
   `regroup()` an. Der Lauf ist durch `_BUSY` gegen Doppelläufe gesichert; keine
   eigenen Parallelskripte daneben starten, das ging schon einmal schief.
2. `/vocab/ENGLISCH/units` gegen das Buch halten: Green Line 4, Wortschatzteil
   S. 160–190. Erwartet werden Einheiten wie „Unit 1 On the move" mit den
   Abschnitten „Introduction", „Station 1", „Station 2", nicht fünfzehn
   zusammenhanglose Bündel.
3. Prüfen, ob das Dictionary ab S. 191 draußen bleibt (die Wörter sind dann
   `hidden=1`, nicht gelöscht).
4. Dasselbe für Spanisch (Konto 1) und Englisch (Konto 2).

Geht etwas schief, liegt der Hebel fast immer in der Antwort auf die
Überschriftenfrage. Sie steht je Seite in `vocab_headings.heads` und lässt sich
dort ansehen, ohne einen Aufruf zu kosten. `regroup()` kostet nichts und kann
beliebig oft laufen.

## Was diese Session gebaut hat

Entscheidungen D137 bis D140 in [ENTSCHEIDUNGEN.md](ENTSCHEIDUNGEN.md).

- **1.11.0 (D137)** Der erste Lesedurchgang jeder Seite läuft auf der Stufe
  „klein", also auf der zweiten Foundry. Die gründliche zweite Lesung ist ein
  Zugewinn, keine Bedingung: Scheitert sie, gilt die erste. Anlass waren fünfzig
  Materialien mit 502, weil beide Stufen auf der ersten Foundry lagen.
- **1.11.1 (D138)** Jede gedruckte Seite wird nur einmal gelesen. Noahs
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

- Die erste Vokabel-Doppelseite von Green Line 4 (Material 251, gedruckt
  160/161) hat das kleine Modell fehlerfrei gelesen: 21 von 21 Wörtern in der
  richtigen Reihenfolge, richtige Bedeutungen, und von der Erklärseite links
  kein einziges Wort — auch nicht aus der Lauttabelle, die wie eine Wortliste
  aussieht. Am Modell lag es also nicht.
- Noahs Englisch: 40 abgerufene Materialien, 24 verschiedene Doppelseiten.
  Gerade Bestellungen kamen richtig, ungerade um vier Seiten versetzt.
  S. 186/187 und 188/189 fehlen bis heute.
- Vokabelbestand vor dem Umbau: Konto 1 Englisch 1217 Wörter in 15 Einheiten,
  Spanisch 1523 in 9; Konto 2 Englisch 424 in 5, Latein 57 in 3. Geübt ist
  ausschließlich Latein (42 Wörter) — die englischen und spanischen Listen
  durften deshalb gefahrlos neu entstehen.

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
- Immer auf `main` ausliefern: auf der Arbeitsbranch entwickeln,
  `git merge --ff-only`, beide pushen, dann `/store/reload` über
  `scripts/ha_supervisor.mjs`. **Das Update selbst spielt der Nutzer ein.**
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
