# Quellen: welche Buchstelle hinter einer Aufgabe steht

Stand: 15.09.2026. Beschreibt umgesetzten Bestand (0.52.1), belegte Befunde aus
der laufenden Instanz und das abgestimmte, noch nicht gebaute Verfahren.
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
| TB, Textband, Lehrbuch, Buch, SB, libro, Kursbuch | Schulbuch | digital möglich |
| vocabulario, Wordbank, Wortschatzteil | Schulbuch, Vokabelteil | digital möglich |
| AH, A-Heft, Arbeitsheft, workbook, cuaderno, cda, Übungsheft | Arbeitsheft | nur Papier |
| Grammatikheft, Beiheft | Grammatikheft | nur Papier |
| Arbeitsblatt, AB, Handout, Merkblatt, Kopie | Arbeitsblatt | nur Papier |

Diese Ableitung hat sich im Betrieb bewährt; die Kürzel mussten nicht erfragt
werden.

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
| Mathematik (BiBox) | Westermann/BiBox | meldet `loaded`, Seite bleibt leer |
| Politik | Eduplaces | `viewer_error`: „Das Medienregal wurde nicht gefunden" |

Die leere Matheseite wurde zweimal abgerufen, beide Male dieselbe leere
Betrachterhülle mit korrekter Seitenanzeige „18 - 19", aber ohne Buchinhalt.

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

## Abgestimmtes Verfahren (noch nicht gebaut)

Vom Nutzer am 15.09.2026 als „klingt gut" bestätigt.

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

Die Prüfung gehört in den nächtlichen Lauf und nur für neu hinzugekommene
Stellen. Einmal geprüft bleibt geprüft; gedruckte Seiten ändern sich nicht.

### Danach: die Aufforderung

Ebenfalls abgestimmt, noch nicht gebaut. Fehlt eine Quelle, bittet die App
konkret darum, nennt Heft, Seite und Anlass und zitiert den Unterrichtseintrag.
Kommt der Scan, wird die Bilanz neu gerechnet; fehlt weiter etwas, wird erneut
gefragt, bis es da ist. Grenzen: höchstens einmal am Tag, und nur bei
anstehender Arbeit oder aktiver Lernkarte, sonst entsteht derselbe
Nachlaufdruck, den das Produkt abschaffen soll. Kommt nichts, darf geübt
werden, aber die Übungsklausur schreibt dazu, dass die Originalquelle fehlt.

## Offene Punkte

- Der Regal-Scan des Kontos ohne Regal läuft in einen Einwilligungsdialog des
  Verlags und speichert dessen Schaltflächen („Abbrechen", „Weiter zur App",
  „Welche Daten werden übertragen?") als Bücher. Der Dialog muss erkannt und
  abgewiesen werden; die drei Einträge sind zu entfernen, wofür es bisher
  keinen Weg gibt. Digitale Bücher gibt es dort erst ab Jahrgang 7.
- `CACHE_KEEP = 60` ist für eine Verifikation über ein Schuljahr zu klein.
- Die Bilanz zählt jede genannte Stelle seit Schuljahresbeginn. Für einen
  Sammelauftrag zum Scannen ist das richtig; für eine einzelne Arbeit müsste
  sie auf deren Stoffzeitraum eingegrenzt werden.
- Die Bilanz sagt nicht, ob eine Heftseite überhaupt bearbeitet wurde. Sie ist
  eine Einkaufsliste, kein Nachweis einer Pflicht.
- Layoutwünsche zur Karte hat der Nutzer angekündigt.
