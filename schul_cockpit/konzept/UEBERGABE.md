# Übergabe an die nächste Session

Stand 19.09.2026, abends. Live läuft Schul-Cockpit **1.12.6**, `main` und
Arbeitsbranch stehen gleich, 550 Tests grün. Keine Kindernamen, PINs oder
Schlüssel in diesem Dokument (D15/D68).

## Nachtrag 24.09.2026

**1.13.11 ist eingespielt.** Die Session hat die App geprüft. Der vollständige Befund liegt als Bericht beim Nutzer; offen und abzustimmen sind:

- Sicherheit: Ingress-Kopfzeile gilt seit 1.13.12 nur noch von 172.30.32.2 (D146). PIN-Sperre seit 1.13.13 atomar und wachsend (D147). Geheimnisse werden nach Nutzerentscheidung nicht getauscht (D148).
- Kosten: Cachefreundliche Reihenfolge und Token-Erfassung seit 1.13.15 (D149). Ab 01.10. auswerten (`GET /api/accounts/{id}/learning/mentor` als Elternteil → `budget.tokens`), dann Mentor-Kontext entschlacken; Structured Output offen. Modelle für Foundry 2 (Nutzerentscheidung 24.09.): **gpt-5.6-luna** für klein/niedrig (Lesen, Vokabeln, Hintergrund; günstiger als gpt-5-mini, laut D132 gleich gut beim Vokabellesen) und **gpt-5.6-terra** für mittel/hoch (Mentor, Kontrolle, sorgfältige Lesung). Keine Sonderfreischaltung nötig; zu klären sind Angebot in der Region und Kontingent (TPM).
- Azure-Zugang für die nächste Session: Der Nutzer legt eine App-Registrierung mit „Cognitive Services Contributor“ auf der Foundry-2-Ressource und „Cognitive Services Usages Reader“ auf dem Abonnement an und trägt `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_SUBSCRIPTION_ID` in die Claude-Umgebung ein. Dann: Token per Client-Credentials von login.microsoftonline.com holen (beide Hosts sind erreichbar, `az` ist nicht installiert), in management.azure.com Modelle und Kontingent der Ressource prüfen, Luna und Terra bereitstellen, mit `vocab/{fach}/compare` und `materials/{id}/analysis/compare` gegen gpt-5-mini eichen (D129: nie durch Umstellen und Neulesen), Kontingentantrag formulieren, Stufen in den Add-on-Optionen umstellen und `RATES` in `ai_gateway.py` um die gpt-5.6-Sätze prüfen. Nie Schlüssel ausgeben.
- Mentor: Hilfeleiter in der Hausaufgabenhilfe seit 1.13.16 (D150). An den nächsten echten Gesprächen ansehen, ob sie zu zäh wirkt; Übungseinheiten haben noch keine.
- Eltern: Nutzungsbericht „So wurde die App genutzt“ (nur Eltern, aufklappbar) ist entworfen, nicht gebaut.
- Drift: Seit 0.74 kein Release für Fachübersicht, Elternüberblick, Übungsklausuren. Doku widersprüchlich, Archivierung der Altkonzepte vorgeschlagen.

## Nachtrag 22.09.2026

**1.13.9 ist eingespielt** (Nacht zum 23.09.): Fotos aus Hausaufgabe und
Kontrolle werden Material der Aufgabe, mehrere auf einmal (D143). Beim nächsten
echten Lauf ansehen, ob die Lesung der Chat-Fotos klappt und ob sie beim Üben
auftauchen. Davor **1.13.8** (22.09., abends). 1.13.7 fand bei Untis-Aufgaben
kein Material, weil das Fach nur im Titel steht; 1.13.8 behebt das und lässt
das Fach von Hand wählen (D142). Inhalt (D141): In Hausaufgabenhilfe und
Kontrolle bindet „Aus Materialien" mehrere abgelegte Seiten des Fachs in den
Chat ein; der Chat darf dafür sechs Bilder je Aufruf schicken. Nach dem
Einspielen an einer echten Kontrolle mit zwei, drei Heftseiten ansehen, ob der
Mentor alle Seiten prüft und was ein Zug dann kostet.

Zwei Tests in `tests/test_lernstand.py` waren seit dem 22.09. rot: Die
Arbeitsübersicht teilt nach dem echten heutigen Datum ein, und die Testarbeit
lag fest auf dem 21.09. Sie liegt jetzt immer zehn Tage in der Zukunft; alle
611 Tests grün.

## Das Nächste zuerst

Der neue Vokabelweg ist gebaut, ausgeliefert und an allen vier Listen gemessen.
Offen sind zwei Stellen, beide in Spanisch von Kind A:

- „Unidad 1 ¡Bienvenidos a mi barrio!" trägt 451 Wörter. Der Laufkopf dieser
  Seiten nennt keine Marke, also fehlt der Hinweis, wo die nächste Unidad
  beginnt. Die Elternansicht `GET /learning/vocab/SPANISCH/outline` zeigt ohne
  Modellaufruf, was die Gliederung zu sehen bekommt — dort anfangen.
- „Lista cronológica" (86 Wörter) ist ein eigener Anhangteil, kein Wortschatz
  einer Einheit. Dafür gibt es `_OTHER_PART`; der Name steht nur noch nicht
  darin, und ob er allgemein genug ist, gehört geprüft.

Kleinere Beobachtungen: In Englisch von Kind A hat S. 164/165 keine einzige
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
- **1.11.1 (D138)** Jede gedruckte Seite wird nur einmal gelesen. Das
  Englischbuch von Kind A kommt als Doppelseite, und der Viewer lieferte auf jede ungerade
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
- **1.12.1 bis 1.12.6** Sechs Nachbesserungen, jede am echten Lauf abgelesen:
  die Gliederung erst setzen, wenn Überschriften gelesen sind; den Anker ohne
  Lautschrift vergleichen; eine Überschrift ohne eigenes Wort dort beginnen
  lassen, wo die nächste beginnt; den Laufkopf mit seiner Marke lesen
  („Vocabulary AC 3" nennt den Teil, zu dem die Seite gehört); „Holiday words"
  ist trotz des Wortes „words" kein Laufkopf; und die Optik entscheidet nichts.

## Gemessen, nicht geschätzt

Alle vier Listen am Abend des 19.09., nach sechs Nachbesserungen, die jede am
echten Lauf abgelesen ist:

- Englisch von Kind A: 9 Einheiten, 550 Wörter, genau die Gliederung des Buchs
  (Unit 1, Across cultures 1, Text smart 1, Across cultures 2, Unit 2, Text
  smart 2, Across cultures 3, Unit 3, Across cultures 4) mit den Abschnitten in
  Buchreihenfolge. Vorher: 15 zusammenhanglose Bündel, 1217 Wörter.
- Englisch von Kind B: 4 Einheiten, 381 Wörter.
- Latein von Kind B: 54 Wörter, davon die 42 geübten mit vollem Verlauf. Der
  Lernstand hat den ganzen Umbau überstanden.
- Spanisch von Kind A: 7 Einheiten, 671 Wörter statt 1523.
- Die erste Vokabel-Doppelseite (Material 251, gedruckt 160/161) liest das
  kleine Modell fehlerfrei: 21 von 21 Wörtern, richtige Reihenfolge, richtige
  Bedeutungen, und von der Erklärseite links kein einziges Wort — auch nicht
  aus der Lauttabelle, die wie eine Wortliste aussieht.
- Englisch von Kind A kam in 40 Abrufen für 24 verschiedene Doppelseiten; gerade
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

- Die beiden Stellen in Spanisch von Kind A, oben unter „Das Nächste zuerst".
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
- Tests `python3 -m pytest tests` (550 grün), Frontend `npm run build`.
  Migrationen ans Ende von `_MIGRATIONS` in `db.py`.
- Messen statt schätzen. Eichungen laufen über `vocab/{fach}/compare` und
  `materials/{id}/analysis/compare`, beide speichern nichts. Ein Vergleich
  zweier Modellstufen darf nie über das Umstellen der Stufe und erneutes
  Einlesen laufen: Der Textstand enthält das Modell nicht, es käme der
  gespeicherte Stand zurück (D129).
- Der Nutzer entscheidet Grundsatzfragen, will Vorschläge mit Empfehlung und
  konsequentes Abarbeiten ohne Rückfragen bei allem anderen. Qualität steht weit
  vor Kosten.
