# Quellen: welche Buchstelle hinter einer Aufgabe steht

Stand: 15.09.2026, abends. Beschreibt umgesetzten Bestand (0.55.0) und belegte
Befunde aus der laufenden Instanz.
Keine Kinder- oder Zugangsdaten; Konten werden als „Konto mit Regal" und
„Konto ohne Regal" unterschieden.

## Worum es geht

Eine Übungsaufgabe oder eine Übungsklausur ist nur dann brauchbar, wenn sie
sich auf den Stoff stützt, den die Schule tatsächlich behandelt hat. Ohne die
Originalquelle erfindet die KI etwas Ähnliches, und das Kind übt am Thema
vorbei. Die Frage ist also: Welche Buchstelle gehört zu welcher Stunde, und
habe ich sie?

Der überraschende Befund: In den meisten Fällen muss nichts hergeleitet werden,
weil die Lehrkräfte die Stelle selbst hinschreiben.

## Belegter Datenbestand

Geprüft am 15.09.2026 gegen das Unterrichtsarchiv seit Schuljahresbeginn.

Von 36 Hausaufgaben des einen Kontos nennen 27 eine konkrete Buchstelle, beim
anderen 14 von 30. Im Stundentext stehen Buchstellen seltener, aber es gibt
Fächer, in denen die Lehrkraft sie regelmäßig mitschreibt (sieben von neun
beschriebenen Lateinstunden).

Typische Schreibweisen aus dem echten Bestand:

```
Wortschatztraining Lektion 1, Übungen zu debere (TB S. 13 Aufg. C, AH S. 7 Aufg. C und Z)
Textband Seite 19 Aufgabe A3, für die Klassenarbeit lernen
Arbeitsheft S. 85, Aufg. 5
12 irregular verbs (chart p. 206 - drive/drove)
#libro, p. 50   vocabulario    4 b
#Grammatikheft, p. 18, n°14 (estudiarlo) +  p. 19 casilla azul
Buch, S.30-32. lest M6 und den Infokasten. Bearbeitet Aufgabe 1 auf S. 34
S. 64/5 zu Ende notieren
```

## Umgesetzt: der Quellenbestand (0.53.0)

Die Zielvorgabe (D37): Der Mentor arbeitet am Originalmaterial oder gar
nicht, und das Material liegt bereit, bevor jemand es braucht. Daraus folgt
ein Bestand, keine Liste.

**Binden.** `sources.sync_links` liest jeden Stunden- und Hausaufgabentext
seit Schuljahresbeginn und bindet jede erkannte Stelle an ihren Untis-Eintrag
(`source_links`: Eintrag, Fach, Buchteil, Seite, Zitat). Wird ein Eintrag in
Untis geändert, verschwinden seine alten Stellen; Stand und Versuchszähler
einer weiter genannten Stelle bleiben.

**Holen.** `source_collector.collect` sammelt je Kind die noch fehlenden
Schulbuchseiten, gebündelt je Buch in einer Browsersitzung, neueste Einträge
zuerst, höchstens 40 Seiten je Lauf. Zwei Läufe am Tag, jeder einmal: nach
2 Uhr und nach 14 Uhr (`background_loop`, alle zehn Minuten geprüft). Eltern
können ihn auf der Materialseite von Hand anstoßen.

**Ablegen.** Eine gelieferte Seite wird ein Material wie ein Foto: Art
`book_page`, Herkunft `book_fetch`, Buch, Seite, Stundendatum. Die vorhandene
Materialauswertung liest sie, extrahiert den Text, ordnet Themen zu. Mentor,
Lernkarten und Klausurstoff lesen heute schon Materialien; der 60er-Cache
ist damit nur noch Rückfall. Die Materialliste blendet Buchseiten aus
(`?books=1` zeigt sie), damit sie die Fotos der Kinder nicht begraben.

**Prüfen (D30, D31).** Vor dem Ablegen die Leerseitenprüfung
(`looks_blank`, Pixelstatistik: leere BiBox-Hülle 1 %, Buchseite 30 %). Die
Auswertung liest die gedruckten Seitenzahlen (`printed_pages`) und ob der
Inhalt zu den Unterrichtszitaten passt (`fits_quote`); daraus `page_check`
ok, mismatch, unknown oder blank. Bei mismatch löscht der Lauf nichts, er
bestellt einmal mit dem Versatz nach und legt die richtige Seite unter der
gedruckten Nummer ab. Der Nachweis je Buch steht in
`digital_textbook_access`: proven (Seitenzahl bestätigt), readable, blank,
viewer_error. Ein Treffer im Katalog zählt nicht mehr als vorhanden.

**Stand je Stelle.** `refresh_status` setzt: digital (liegt abgerufen im
Bestand; Detail belegt, plausibel oder ungeprüft), scanned (ein Foto aus der
Ablage nennt die Seite), pending (Buchseite unterwegs), unavailable (das
Buch liefert nach zwei Versuchen nichts Lesbares), paper (nur auf Papier,
oder Hypothese Schulbuch widerlegt: `passt_nicht`). Die Karte „Was mir noch
fehlt" zeigt die drei sichtbaren Zustände je Fach mit Grund.

**Mentor.** `homework_page_images` nimmt Seiten aus dem Bestand und startet
den Browser nur für Seiten, die dort fehlen; die holt es und legt sie ab. Der
Seitenerkenner ist derselbe wie in der Bilanz: „p. 50" zählt, „AH S. 7"
nicht. Bis 0.52.6 verstand der Mentor nur „S." und „Seite" und bekam für
Spanisch nie eine Seite.

## Umgesetzt: die Quellenbilanz (0.52.0, korrigiert in 0.52.1)

`backend/sources.py` sammelt diese Stellen regelbasiert, ohne KI, und stellt
ihnen gegenüber, was vorhanden ist. Die Materialseite zeigt das Ergebnis als
aufklappbare Karte „Was mir noch fehlt", je Fach, mit Zitat und Datum.
Endpunkt: `GET /api/accounts/{id}/materials/sources`.

### Regeln, die sich als notwendig erwiesen haben

**Nur eine ausdrückliche Seitenangabe zählt.** Erlaubt sind `S.`, `Seite`,
`p.`, `pp.`, `página`. Ohne diese Regel wird aus „#libro, p. 50 vocabulario
4 b" eine Seite 4, obwohl 4 b die Aufgabe ist. Aufgabennummern (`Nr.`, `Aufg.`,
`n°`) werden dadurch automatisch nicht als Seiten gelesen.

**Wortgrenzen sind Pflicht.** Ein erster Entwurf ohne `\b` hielt „Klassenfahrt"
für eine Arbeitsheftangabe, weil „fahrt" ein „ah" enthält.

**Der zuletzt genannte Buchteil gilt weiter.** In „Buch, S. 30-32 … Aufgabe 1
auf S. 34" gehört auch die 34 ins Buch. Steht nirgends im Text ein Buchteil,
heißt die Quelle „Unbekannt"; erfunden wird keiner.

**Hausaufgaben tragen keine Fach-ID.** Untis speichert an einer Hausaufgabe nur
das Kürzel („LA", „SN"), niemals `subject_untis_id`. Der Join über die ID kann
deshalb nicht funktionieren — in der ersten Fassung stand jedes Fach doppelt
auf der Liste, einmal als „LATEIN" und einmal als „LA". Aufgelöst wird über das
echte Untis-Kürzel aus dem `payload_json` der Stunde (`su[0].name`); eine
Präfixregel würde „SN" → „SPANISCH" nicht treffen. Ein gepflegter Eintrag in
`subject_aliases` hat Vorrang.

### Zuordnung der Kürzel

Aus dem Wortlaut abgeleitet, nicht von Menschen bestätigt. Die Annahme steht in
der Anzeige, damit man ihr widersprechen kann.

| geschrieben | gilt als | Art |
|---|---|---|
| BB, Begleitband | Begleitband (eigenes Buch, nur von eigenen Seiten belegt) | Papier oder digital |
| TB, Textband | Textband (das Hauptbuch) | digital möglich |
| Lehrbuch, Buch, SB, libro, Kursbuch | Schulbuch (das Hauptbuch) | digital möglich |
| vocabulario, Wordbank, Wortschatzteil | Schulbuch, Vokabelteil | digital möglich |
| AH, A-Heft, Arbeitsheft, workbook, cuaderno, cda, Übungsheft | Arbeitsheft | nur Papier |
| Grammatikheft, Beiheft | Grammatikheft | nur Papier |
| Arbeitsblatt, AB, Handout, Merkblatt, Kopie | Arbeitsblatt | nur Papier |

Diese Ableitung hat sich im Betrieb bewährt; die Kürzel mussten nicht erfragt
werden. Seit 0.57.0 zählt eine Aufzählung hinter der Angabe vollständig
(„S. 10, 11, 14, 15"), solange sie aufsteigt und nah bleibt; „S. 12, 3a" ist
Seite 12 mit Aufgabe 3a.

## Belegter Befund: Seitenabruf aus dem Medienregal

Am 15.09.2026 an der laufenden Instanz geprüft, mit echten Abrufen.

### Was abrufbar ist

| Buch | Betrachter | Ergebnis |
|---|---|---|
| Spanisch-Lehrwerk | Klett | Seiten kommen, lesbar |
| Deutschbuch | Klett | Seiten kommen, lesbar |
| Englisch-Lehrwerk | Klett | Seiten kommen, lesbar |
| Physik | Westermann | Seiten kommen, lesbar |
| Geschichte | Klett | Seiten kommen |
| Chemie | Westermann | Seiten kommen |
| Mathematik (BiBox) | Westermann/BiBox | bis 0.52.5 `loaded`, Seite leer; seit 0.52.6 lesbar |
| Erdkunde (BiBox Diercke) | Westermann/BiBox | wie Mathematik; seit 0.52.6 lesbar |
| Politik (click & study) | Buchner | zweimal am Regalsprung gescheitert, im dritten Lauf lesbar; seit 0.52.3 wartet der Sprung auf die Kachel |

**BiBox, aufgeklärt (D40).** Die leere Seite war kein Lizenzproblem. Der
Betrachter zeichnet mit WebGL; die Konsole meldete „CanvasRenderer is not yet
implemented", `webgl=false`. Das Alpine-Chromium 131 des Add-ons bringt keinen
SwiftShader mit (kein `libvk_swiftshader.so`), und jede GPU-Einstellung
scheiterte an einer fehlenden Vulkan-Erweiterung: Der GPU-Prozess startete in
Schleife neu und der Browser kam zwei Minuten lang nicht hoch. Seit 0.52.6
enthält das Image Mesa mit Lavapipe (Software-Vulkan); WebGL läuft über ANGLE
auf Vulkan, Start in unter zwei Sekunden, Seiten lesbar. Der Weg dahin steht
im Changelog 0.52.2 bis 0.52.6: erst mehr Diagnose im Seitentest, dann eine
Browser-Sonde, die Chromium mit mehreren Varianten direkt startet
(`POST /textbooks/browser-check`). Beides bleibt für künftige Betrachter.

Nebenbefund: Der Fernzugriff über Nabu Casa kappt jede Anfrage nach 100
Sekunden. Seitentest und Sammellauf laufen deshalb als Hintergrundaufträge,
die die Seite nachfragt (`start_job`/`job_state` in `textbook_context`).

### Drei Fehler, die jedes Verfahren berücksichtigen muss

**Die gelieferte Seite ist oft nicht die bestellte.** Bei acht erfolgreichen
Abrufen stimmte sie dreimal nicht: Bestellung 50 lieferte die Doppelseite
48/49, Bestellung 172 lieferte 170/171, Bestellung 214 lieferte 210/211. Die
Schnittstelle meldete jedes Mal die bestellte Nummer als `shown_page`. Die
gedruckte Seitenzahl steht unten auf dem Bild und ist der einzige Beleg. Sie
muss abgelesen und gegen die Bestellung geprüft werden.

**`loaded` heißt nicht lesbar.** Ohne eine Prüfung, ob überhaupt Buchinhalt auf
dem Bild ist, wird aus einer leeren Seite ein stilles „passt nicht" und eine
unnötige Scan-Aufforderung.

**Ein Treffer im Katalog ist kein Zugriff.** Die Quellenbilanz verbucht heute
jede Buchseite als vorhanden, sobald das Fach ein Buch im Katalog hat. Für die
beiden nicht abrufbaren Bücher ist das falsch; ihre Seiten fehlen zu Unrecht
nicht auf der Liste. Der Abruf gehört je Buch einmal nachgewiesen.

Ein Abruf dauert ein bis zwei Minuten. Seiten werden dreißig Tage
zwischengespeichert, aber nur sechzig Stück je Kind (`textbook_context.py`,
`CACHE_KEEP`). Für ein Kapitel reicht das, für ein Schuljahr nicht.

## Belegter Befund: inhaltliche Verifikation funktioniert

Drei Stellen ohne Quellenangabe wurden von Hand aufgelöst, indem die
Standardannahme „Schulbuch" geprüft statt geglaubt wurde.

**„S. 171" (Spanisch).** Abgerufen: die Vokabelliste des Lehrwerks, mit der
Überschrift „Unidad 3 ¡Acércate! ▸ p. 48". Belegt, und das Buch nennt die
Einheit und deren Anfangsseite selbst.

**„S. 48" (Spanisch).** Abgerufen: die Auftaktdoppelseite der Unidad 3. Belegt,
bestätigt dieselbe Einheit.

**„S. 64/5 zu Ende notieren" (Deutsch).** Abgerufen: Seite 64 mit dem Thema
„Immer online, immer erreichbar? — Diskutieren und argumentieren". Aufgabe 5
auf dieser Seite verlangt, einen Standpunkt zu formulieren und zu begründen —
genau das, was „zu Ende notieren" meint. Belegt, und die Schreibweise ist
geklärt: „64/5" heißt Seite 64, Aufgabe 5, nicht Seiten 64 bis 65.

**Die Kapitelgrenze ergibt sich mit.** Weiterblättern zeigte auf Seite 60/61
den „Resumen" der Einheit. Die Einheit läuft also von 48 bis 61, der
zugehörige Wortschatz ab 171. Der Resumen listet zugleich den Grammatikstoff
der Einheit auf. Für den Stoffumfang einer anstehenden Arbeit ist das eine
Quelle aus dem Buch selbst, keine Schätzung.

Damit ist bestätigt, was der Nutzer vorgeschlagen hat: Vokabelteile sind nach
Einheiten markiert und verweisen auf die Einheit im Hauptteil. Wenn die Einheit
zu den Stundenthemen ringsum passt, ist die Zuordnung fachlich verifiziert und
muss nicht erfragt werden.

## Das Prüfverfahren (D30, gebaut in 0.53.0)

Vom Nutzer am 15.09.2026 als „klingt gut" bestätigt; Umsetzung siehe oben.

Fehlt zu einer Seitenangabe der Buchteil, gilt zunächst die Annahme Schulbuch.
Diese Annahme ist eine Hypothese, die der Inhalt bestätigen oder widerlegen
muss. Vier Ergebnisse:

1. **Belegt** — Seite geholt, gedruckte Seitenzahl stimmt, Inhalt passt zum
   Zitat und zu den Stundenthemen ringsum. Niemand wird gefragt.
2. **Plausibel** — Seite geholt, sie stammt aus diesem Buch, der Themenbezug
   ist dünn. Bleibt drin, gekennzeichnet als unsicher.
3. **Passt nicht** — Seite geholt, Inhalt widerspricht. Also ein anderes Heft:
   auf die Einkaufsliste, und die Liste kann benennen, welches es nicht ist.
4. **Nicht prüfbar** — kein abrufbares Buch. Bleibt auf der Einkaufsliste.

Nur 3 und 4 werden eingefordert.

Die Prüfung läuft in den beiden Sammelläufen und nur für neu hinzugekommene
Stellen. Einmal geprüft bleibt geprüft; gedruckte Seiten ändern sich nicht.
Ergebnis 1 heißt im Bestand `belegt`, 2 `plausibel`, 3 `passt_nicht`, 4
`unavailable` oder `paper`.

### Danach: die Aufforderung

Ebenfalls abgestimmt, noch nicht gebaut. Fehlt eine Quelle, bittet die App
konkret darum, nennt Heft, Seite und Anlass und zitiert den Unterrichtseintrag.
Kommt der Scan, wird die Bilanz neu gerechnet; fehlt weiter etwas, wird erneut
gefragt, bis es da ist. Grenzen: höchstens einmal am Tag, und nur bei
anstehender Arbeit oder aktiver Lernkarte, sonst entsteht derselbe
Nachlaufdruck, den das Produkt abschaffen soll. Kommt nichts, darf geübt
werden, aber die Übungsklausur schreibt dazu, dass die Originalquelle fehlt.

## Umgesetzt: die Buchstruktur (0.54.0, D39)

`book_structure.read_toc` holt je Buch einmal die Seiten 2 bis 5 (und 6 bis
9, wenn das Verzeichnis weitergeht) und lässt das Modell das Inhaltsverzeichnis
ablesen: Nummer, Titel, Ebene, Anfangsseite, Art (Kapitel, Vokabelteil,
Grammatik, Anhang) und zu welcher Lektion ein Anhang gehört. Ein Kapitel
endet, wo das nächste derselben Ebene beginnt, höchstens sechzig Seiten
später. Stand je Buch in `digital_textbook_access.toc_state`; der Sammellauf
liest je Lauf höchstens drei Verzeichnisse, bevor er Seiten holt.

**Kapitelregel.** `expand` läuft im Takt von `sync_links`: Zu jedem Kapitel,
aus dem ein Untis-Eintrag eine Seite nennt, werden alle Seiten als zu holende
Stellen gebunden (`entry_kind = chapter`), dazu die Vokabel- und
Grammatikteile, die das Verzeichnis dieser Lektion zuordnet. Genannte Seiten
kommen vor Kapitelseiten. Schneidet kein Eintrag das Kapitel mehr an, fallen
die Zeilen weg. Der Klausurstoff (`exam_scope.collect`) führt die im Zeitraum
angeschnittenen Kapitel als eigene Einträge, mit Seitenbereich und Anhängen;
der Mentor bekommt bei der Hausaufgabenhilfe `book_context`: das Kapitel der
genannten Seite, seinen Bereich, was dazugehört.

**Eigener KI-Rahmen (D41).** Buchseiten lesen und Verzeichnisse ablesen laufen
unter dem Zweck `sources` mit 15 Euro im Monat, getrennt vom
Hintergrund-Rahmen. Der erste Sammellauf hatte 12 Seiten geholt und keine
gelesen, weil der Hintergrund-Rahmen (5 Euro) bereits zu 4,35 Euro verbraucht
war.

## Umgesetzt: Einträge ohne Quelle, Fachgewohnheit, Aufforderung (0.55.0)

**Einträge ohne Seitenangabe (D42).** `book_structure.map_entries` nimmt je
Buch die neuen Stunden- und Hausaufgabentexte ohne Seitenangabe. Steht eine
Lektionsnummer im Text, entscheidet `rule_match` ohne Modell; zwei Nummern
sind keine Zuordnung. Den Rest bekommt das Modell mit dem Inhaltsverzeichnis
in einem Aufruf je Buch (Zweck `sources`), höchstens 40 Texte je Aufruf, und
nennt Kapitel oder „keines“ mit Sicherheit; unter 0,6 zählt als keines. Das
Ergebnis liegt in `entry_chapters` mit dem Hash des Textes, damit nichts
zweimal gefragt wird und ein geänderter Text neu gefragt wird. Ein so
erschlossenes Kapitel gilt in `touched_chapters` als angeschnitten, mit
Kennzeichen `inferred`; die Kapitelregel holt es, die Bilanz und der
Klausurstoff zeigen die Herkunft.

**Fachgewohnheit (D42).** `sources.subject_habits` zählt je Fach die
ausdrücklichen Buchteile. Ab drei Angaben mit vier Fünfteln auf demselben Teil
gilt er für die Stellen ohne Buchteil: Zeigt er auf Arbeitsheft oder Blatt,
wird die Stelle nicht als Schulbuch geholt, sondern steht mit dem Grund
`gewohnheit` auf der Einkaufsliste. Eine bereits geholte Seite, deren Inhalt
zum Zitat passt, bleibt.

**Aufforderung (D43).** `sources.photo_requests` nimmt die Arbeiten der
nächsten vierzehn Tage (`exams.resolve_exams`, also Klausurplan und Untis) und
die Papierstellen dieser Fächer, höchstens drei, mit Heft, Seiten und Zitat.
Die Abendkarte zeigt sie unter „Für die Arbeit brauche ich noch“ mit Sprung
zur Materialseite; die abendliche Mitteilung zählt „Heftseiten für die Arbeit“
als offenen Punkt. Ohne Arbeit: nichts.

## Umgesetzt: zwei Bücher, Papierbücher, Klausurzettel (0.57.0, D45–D47)

- `sources.serves(have, want)` entscheidet, ob eine Seite eines Buchteils eine
  genannte Stelle belegt; `book_serves` dasselbe für das digitale Buch im
  Regal. Der Begleitband ist ein eigenes Buch (`SEPARATE_BOOKS`).
- `materials.source_label`/`source_page`: Buchteil und gedruckte Seite einer
  Datei. Gesetzt von der Einkaufsliste (`claim`), vom Upload mit Vorgabe oder
  von der Auswertung (`Insight.printed_pages`, `Insight.book_part`). Der
  Abgleich (`_scanned_pages`, `scan_for`) nutzt zuerst diese Angaben und
  sonst nur Titel und Kurzbeschreibung — nicht mehr den erkannten Text.
- Materialart `exam_notice`: `sources.exam_notices` liefert die Zettel,
  `mentions` bindet ihre Stellen mit `entry_kind` exam_notice; Priorität wie
  Hausaufgaben (`source_collector.priorities`), eigene Einheit im Klausurstoff
  (`exam_scope.collect`), vorn im Mentor-Kontext (`materials.for_context`).
- Materialart `toc` plus Buchteil: `book_structure.read_paper_toc` liest aus
  allen Fotos dieses Verzeichnisses die Kapitel (bis acht Aufnahmen, je zwei
  zu einem Bild) und trägt das Buch in `paper_books` ein. `expand` bindet die
  Kapitelseiten mit dem Buchteil als `part_label`; `overview(..., label)`
  zählt fotografierte statt abgerufener Seiten. `exam_scope.book_chapters`
  nimmt Papierbücher dazu.
- Fach: `/api/accounts/{id}/subjects` liefert `untis_name`; die Materialseite
  wählt daraus, `materials.canonical_subject` bringt jede Eingabe auf die
  Schreibweise des Stundenplans.

## Offene Punkte

- Der Klausurstoff nennt den Zettel als Einheit; ob das Modell ihn beim
  Gruppieren als Vorgabe behandelt (statt als eine Notiz unter vielen), ist
  am ersten echten Stoffplan zu prüfen.
- Stellen ohne Buchteil in einem Fach mit zwei Papierbüchern („Voc. 1.
  Lektion S. 10, 11") landen als „Unbekannte Quelle" auf der Liste und werden
  vom ersten passenden Foto beliebigen Buchteils gestrichen.

- Der Regal-Scan des Kontos ohne Regal läuft in einen Einwilligungsdialog des
  Verlags und speichert dessen Schaltflächen („Abbrechen", „Weiter zur App",
  „Welche Daten werden übertragen?") als Bücher. Der Dialog muss erkannt und
  abgewiesen werden; die drei Einträge sind zu entfernen, wofür es bisher
  keinen Weg gibt. Digitale Bücher gibt es dort erst ab Jahrgang 7.
- `CACHE_KEEP = 60` betrifft nur noch den Rückfall-Cache; der Bestand liegt in
  `materials` ohne Limit außer dem Speicher je Kind (200 MB, rund 150 KB je
  Seite).
- Die Bilanz zählt jede genannte Stelle seit Schuljahresbeginn. Für einen
  Sammelauftrag zum Scannen ist das richtig; für eine einzelne Arbeit müsste
  sie auf deren Stoffzeitraum eingegrenzt werden.
- Die Bilanz sagt nicht, ob eine Heftseite überhaupt bearbeitet wurde. Sie ist
  eine Einkaufsliste, kein Nachweis einer Pflicht.
- Layoutwünsche zur Karte hat der Nutzer angekündigt.
