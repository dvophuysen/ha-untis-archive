# Quellenbestand 0.52.2–0.67.0

Stand 16.09.2026, nachmittags. Bis 0.56.11 auf der laufenden Instanz installiert und
mit echten Abrufen geprüft; 0.57.0 folgt in derselben Session.

## Was ausgeliefert ist

**Klausurseite neu (0.67.0, D62).** `Klausuren.svelte` komplett neu: drei
Punkte mit Ampel, aufklappbare Themenliste mit Stufen, Gefühl je Arbeit und
Thema, „Auch behandelt“, Kapitel, Übungsarbeit. Nur Frontend; Daten kommen aus
`exams/all` (`sources`, `topics`, `stages`, `scope`). Offen: Fahrplan mit Tagen
(Option B) bewusst nicht gebaut.

**Vokabeltrainer (0.66.0, D61).** `vocab.py` mit `vocab_words` je Seite
(Modell zerlegt, jedes Wort muss im Seitentext stehen), `vocab_attempts`,
deterministische Bewertung (`judge_meaning`, `judge_foreign`), Stand je Wort
und Stufe (`vocab.replay`), Karten Wackler zuerst. Route `#/vokabeln/<Fach>`,
Klausurkarte verlinkt Vokabel-Themen dorthin und übernimmt deren Stufe aus den
Wörtern (`lernstand.topics_for`). Offen: Kartenfoto für Stufe 2, Formen-Trainer
Latein (Kandidatenabgleich), Spanisch-Wortseiten fehlen noch als Material.

**Spracheingabe (0.65.0/0.65.1, D60).** `Speech.svelte` (halten, sprechen,
loslassen; MediaRecorder mit mp4 auf iPhone, webm sonst; Lautstärkemessung
gegen erfundenen Text aus Stille), `POST /sessions/{sid}/transcribe`,
`ai_gateway.transcribe` gegen `gpt-4o-transcribe` in der Hauptressource.
Live geprüft am 16.09.: 2-Sekunden-Testton, Antwort 200 in 1,8 s; aus Rauschen
erfand das Modell „Mit der a-Deklination.“ (Prompt-Bias), deshalb 0.65.1 mit
Lautstärkegrenze im Browser. Kosten je Aufnahme im Cent-Bruchteil, gebucht als
Kinderzweck.

**Lernstand je Thema (0.64.0, D59).** `exam_topics` aus der offiziellen
Themenliste (Modell zerlegt, Text prüft, Hash schützt vor Doppelaufrufen),
`topic_answers` mit Signalen (Sekunden, Löschungen, Hilfe, Umerklären,
Aufgabenart), `lernstand.replay` liest die Stufe ab. Themen-Einheiten im Mentor
(`mode: topic`) ohne Uhr, mit Kurzprüfung ab drei Tagen nach „sitzt“.
Klausurkarte zeigt Themen sortiert mit Stelle, Materialstand und Gefühl.
Live geprüft: Josias Lateinliste ergab fünf Themen mit allen Stellen belegt
(Begleitband S. 13, 13–15, 14; Textband S. 10–11, 14–15; Vokabeln S. 10–11);
Einheit startet und meldet „Thema 2 von 5 · Stufe: neu“. Offen: Themen ohne
Themenliste kommen weiter aus dem erschlossenen Unterricht (`exam_scope`),
noch ohne Stufe; Spracheingabe und Vokabeltrainer folgen (0.65, 0.66).

**Sicherung und Betrieb (0.63.0 bis 0.63.3, D56 bis D58).** Die Backup-
Anzeige zeigt, ob ein HA-Backup dieses Add-on enthält (Rolle `backup`, vorher
403 und darum „kein Backup“); die automatischen HA-Backups enthalten es täglich
(am 16.09.: 32 Sicherungen, letzte 03:26). Eigene Nachtsicherung nur als
Rückfall. Der Knopf „Jetzt in Home Assistant sichern“ legt eine Teilsicherung
an (live geprüft: „Schul-Cockpit 0.63.1 2026-09-16 13:16“); die Antwort dauert
etwa zwei Minuten und kommt über Nabu Casa als 524 zurück, die Sicherung ist
trotzdem da. ZIP-Download geprüft: 160 MB in 141 s. Dabei aufgefallen und in
0.63.3 behoben: `webapp.db` lief ohne WAL, jede Anfrage schreibt beim Anmelden
„zuletzt gesehen“, und die fünf Sekunden Wartezeit reichten während der
Sicherung nicht; fünfzehn Vorschaubilder scheiterten mit „database is locked“.
Lehre aus 0.63.0: Syntaxfehler in `main.py` ließ das Add-on nicht starten;
`tests/test_imports.py` lädt seither jedes Modul. Vokabular vereinheitlicht
(0.63.2, D57): „offizielle Themenliste“, „Thema“, „Stelle“, „Stufe“.

**Pakete B bis D aus der Ideenliste (0.60.0 bis 0.62.0, D53 bis D55).**
Verzeichnisfotos gelten auch für digitale Bücher ohne lesbares Verzeichnis
(`read_paper_toc` legt die Kapitel unter dem digitalen Titel ab); Kapitel sind
von Hand berichtigbar und gesperrt (`update_chapter`, `book_chapters.locked`,
Begleitband Lektion 11, 12 und 19 live korrigiert). Das Abschreibmodell ist je
Zweck wählbar und wurde geeicht: nicht umgestellt (siehe oben). Die Rahmen der
Eltern stehen in der Mentor-Ansicht. Fotos tragen Bildabdruck und Schärfemaß;
Duplikate und unscharfe Aufnahmen werden beim Ablegen gemeldet. Der
Einwilligungsdialog des Verlags wird erkannt, die drei Dialogeinträge im Regal
des jüngeren Kindes sind entfernt. Offen: Klausurseite neu (E, wartet auf
Layoutwünsche und die Bildschirmzeit-Antwort), Vokabeltrainer (zurückgestellt,
Eingabe per Tippen zu umständlich).

**Eichung der Abschreibmodelle (0.61.0/0.61.1, D54): nicht umgestellt.** Acht
echte Seiten (Begleitband-Grammatik und -Wortschatz, Textband-Lektionstext,
Arbeitsheft, Verzeichnisseite, handschriftlicher Klausurzettel, zwei
abgerufene Doppelseiten aus Deutsch und Mathematik) wurden mit dem Hauptmodell
noch einmal und mit den beiden günstigeren Modellen gelesen. Maß: gedruckte
Seitenzahl, Buchteil, Wortabdeckung gegenüber der gespeicherten Lesung.
Hauptmodell gegen sich selbst: Wortabdeckung 0,95 bis 1,00, es fehlen nur
Wörter aus Bildbeschreibungen; 0,07 bis 0,14 Euro je Seite. Mittleres Modell
(rund 0,04 Euro): auf Einzelseiten 0,91 bis 0,99, aber bei der
Mathematik-Doppelseite 34/35 nur Seite 35 gelesen (Abdeckung 0,66), auf dem
Klausurzettel alle Seitenzahlen verloren, auf der Wortschatzseite ein Lernwort
(„cōgitāre“). Kleines Modell (rund 0,016 Euro): Lektionstext nur zur Hälfte
(0,48). Doppelseiten sind der Hauptanteil des Bestands; ein Modell, das eine
Seite davon auslässt, spart am falschen Ende. Das Abschreiben bleibt beim
Hauptmodell. Der Vergleichsaufruf bleibt für spätere Modelle bestehen.

**Ankündigung, Gegenlesen, Buchvermutung (0.59.0, D50–D52).** Ein Zettel
der Lehrkraft legt den Stoffplan fest (`NOTICE_RULE`, Kategorie `context`).
Zettel, Verzeichnisse und unsichere Lesungen bitten auf der Materialseite um
„Stimmt so“ (`needs_review`, `verified`). Stellen ohne Buchteil bekommen das
wahrscheinlichste Buch (`_book_guesser`) als Vermutung auf der Einkaufsliste.
Dazu 0.58.x: Materialstand auf der Klausurkarte (`exam_sources`), Tagesrahmen
je Kind ohne Hintergrundarbeit, ausgeblendete Kurse ohne Rückmeldepflicht.
Offen aus der Ideenliste des Nutzers: Verzeichnisse aus Fotos auch für
digitale Bücher ohne lesbares Verzeichnis, Kapitel von Hand korrigieren,
günstigeres Modell fürs Abschreiben mit Eichung, Rahmen in der Elternansicht,
Duplikate und unscharfe Fotos, Klausurseite neu, Regal-Dialogeinträge.

**Zwei Bücher, Papierbücher, Klausurzettel (0.57.0, D45–D47).** Textband und
Begleitband sind eigene Quellen (`sources.serves`); Aufzählungen von Seiten
gelten ganz. Der abfotografierte Zettel zum Klausurstoff (`exam_notice`)
bindet seine Stellen mit Vorrang; Papierbücher bekommen ihr Verzeichnis aus
Fotos (`toc`, `paper_books`, `read_paper_toc`) und die Kapitelregel. Jede
Datei kennt Buchteil und gedruckte Seite; das Fach kommt aus dem Katalog.
Tests: `tests/test_paper_books.py`.

Live-Befund Latein (Konto 2, 0.57.0–0.57.4): Beide Verzeichnisse aus Fotos
gelesen (Textband 105 Einträge aus 5 Fotos, Begleitband 35). Dabei gelernt:
die Schnittstelle verkleinert jedes Bild auf 1600 Pixel und ließ zwei Bilder
zu, fünf Fotos gehen jetzt einzeln in einem Aufruf (0.57.2); ein Teil ohne
Nummer („Gefahr im Circus Maximus", Lektionen 1–3) ist kein Kapitel (0.57.3);
nummerierte Lektionen, die „Wortschatz" heißen, sind Kapitel (0.57.4). Die
Auswertung las den handschriftlichen Klausurzettel mit „70, 71" statt
„10, 11"; der Text wurde von Hand korrigiert und ist gesperrt. Drei
„Grammatik üben"-Seiten des Textbands hielt das Modell für Arbeitsheft oder
Begleitband; von Hand berichtigt. Uploads von Quellenseiten laufen seit
0.57.1 im Quellen-Rahmen, weil 26 Auswertungen an einem Nachmittag den
Tagesrahmen sprengten.

**Quellen sichtbar, Hausaufgabe neu (0.56.0, D44).** `sources.segments`
zerlegt jeden Untis-Text; `annotate_lessons` und `annotate_tasks` hängen Stand
und Material an (Tag, Woche, Fachdetail, Aufgabenliste). Die Aufgabe findet
ihre Untis-Hausaufgabe über die Kennung in den Notizen, sonst über den
Wortlaut. `SourceText` rendert die Links, `TaskDetail` ersetzt das alte
Formular. `prepare_intros` schreibt im Sammellauf die Einstiegshilfe
(`tasks.intro`). Materialliste vollständig mit Seitenweise-Laden.

**Einträge ohne Quelle, Fachgewohnheit, Aufforderung (0.55.0, D42/D43).**
Stundentexte ohne Seitenangabe werden ihrem Kapitel zugeordnet (Regel, sonst
Modell mit Inhaltsverzeichnis) und das Kapitel als Hypothese eingesammelt.
Nennt eine Lehrkraft sonst immer das Arbeitsheft, gilt das für ihre Stellen
ohne Buchteil. Vor einer Arbeit bittet die Abendkarte um die fehlenden
Heftseiten, höchstens drei, mit Zitat.

**Zweiter und dritter Live-Lauf (0.54.0/0.55.0).** Inhaltsverzeichnisse
gelesen: Chemie 105 Einträge, Deutschbuch 85, Diercke 105, Mathematik 38;
Green Line und Geschichte und Geschehen auf den Seiten 2 bis 9 nicht gefunden.
Der dritte Lauf holte 30 Seiten in 917 Sekunden, 10 davon mit bestätigter
Seitenzahl, und ordnete 40 Stundentexte ohne Seitenangabe zu (33 Kapitel,
7 keines). Danach: Mathematik Kapitel 1 „Gleichungen“ vollständig (28 von 28
Seiten), Deutsch Kapitel 3 vollständig (8 von 8), Erdkunde Kapitel 3 „Städte
im Wandel“ 3 von 36 unterwegs. Das Add-on aktualisiert sich selbst
(`auto_update`), sobald der Store eine neue Version sieht; 0.55.0 kam so
mitten in einen Lauf.

**Buchstruktur und Kapitelregel (0.54.0, D39).** Inhaltsverzeichnis je Buch
einmal gelesen (`book_chapters`), angeschnittene Kapitel samt Vokabel- und
Grammatikteil vollständig geholt, im Klausurstoff und im Mentor-Kontext
geführt. Eigener KI-Rahmen für den Quellenbestand, 15 Euro im Monat (D41).

**Erster Live-Sammellauf (0.53.0).** 12 von 13 genannten Buchseiten in 404
Sekunden geholt und abgelegt, keine leer, keine Fehlabrufe; Spanisch,
Politik, Deutsch, Mathematik. Die KI-Auswertung scheiterte am erschöpften
Hintergrund-Rahmen (429), daraus D41.

**Alle neun Bücher des Kontos mit Regal liefern Seiten (0.52.6, D40).** Die
BiBox-Bücher zeichnen mit WebGL; das Image trägt jetzt Mesa mit Lavapipe.
Belegt: Mathematik 18/19 „Gleichungen lösen mit systematischem Probieren",
Erdkunde 20/21 „Die Klimazonen der Erde", gedruckte Seitenzahlen stimmen.
Politik (click & study) lieferte Seite 30 lesbar; der Regalsprung wartet seit
0.52.3 auf die Kachel. Der Weg: Diagnose im Seitentest (0.52.2), Browser-Sonde
(0.52.5), Software-GPU (0.52.6). Details in [Quellen](QUELLEN.md).

**Hintergrundaufträge (0.52.4).** Nabu Casa kappt Anfragen nach 100 Sekunden;
Seitentest, Browser-Sonde und Sammellauf laufen deshalb als Aufträge, die die
Seite nachfragt. Ein Browserstart, der scheitert, wird bis zum Neustart nicht
wiederholt; Start, Abschluss und Ende stehen mit Dauer im Protokoll.

**Quellenbestand (0.53.0, D37/D38).** `source_links` bindet jede genannte
Stelle an ihren Untis-Eintrag. `source_collector` holt fehlende Schulbuchseiten
um 14 Uhr und nachts, höchstens 40 je Kind und Lauf, und legt sie als
Materialien ab (`origin=book_fetch`, Buch, Seite, Stundendatum). Die
Materialauswertung liest gedruckte Seitenzahl und Passung zum Zitat; daraus
der Nachweis je Buch (`digital_textbook_access`, D31) und der Stand je Stelle
(D30). Der Mentor nimmt Seiten aus dem Bestand. Karte und Einstellungen zeigen
die Zustände; Eltern stoßen den Lauf von Hand an.

## Fehler, die dabei gefunden und behoben wurden

- `--disable-gpu` schaltete WebGL ab; `--ignore-gpu-blocklist` ließ den Browser
  auf dem Pi zwei Minuten hängen; die Ursache war der fehlende SwiftShader.
- Der Mentor verstand nur „S." und „Seite"; für Spanisch („p. 50") bekam er nie
  eine Buchseite. Jetzt derselbe Erkenner wie in der Bilanz.
- Die Bilanz verbuchte jede Buchseite als vorhanden, sobald das Fach ein Buch
  im Katalog hatte (D31).
- `digital_textbook_pages` und `digital_textbook_fetches` fehlten beim
  Kontowechsel.

## Bekannte Lücken

- Der Regal-Scan des Kontos ohne Regal speichert Dialogschaltflächen als
  Bücher; kein Löschweg.
- Die Inhaltsverzeichnisse von Green Line 4 und Geschichte und Geschehen 3/4
  liegen nicht auf den Seiten 2 bis 9; dort greift die Kapitelregel noch
  nicht. Ein zweiter Versuch an anderer Stelle im Buch steht aus.
- Ob die App auf dem älteren Kindergerät eine Bildschirmzeit-Auszeit übersteht,
  ist weiterhin nur vom Nutzer prüfbar.

---

# Quellenbilanz und abgeleiteter Tagesabschluss 0.51.0–0.52.1

Stand 15.09.2026, auf der laufenden Instanz installiert und geprüft. 210 Python-Tests grün.

## Was ausgeliefert ist

**Quellenbilanz (0.52.0, korrigiert 0.52.1).** `backend/sources.py` liest aus Stunden- und Hausaufgabentexten die genannten Buchstellen und stellt ihnen gegenüber, was digital im Regal liegt oder in der Materialablage vorhanden ist. Endpunkt `GET /api/accounts/{id}/materials/sources`; er muss im Router vor `/{material_id}` stehen, sonst versucht FastAPI, „sources" als ID zu lesen. Die Materialseite zeigt das Ergebnis als aufklappbare Karte „Was mir noch fehlt", je Fach, mit Zitat und Datum. Angefordert oder abgerufen wird nichts. Details und Befunde: [Quellen](QUELLEN.md).

**Abgeleiteter Tagesabschluss (0.51.0, umgebaut 0.51.2).** `backend/day_close.py` hält fest, wann an einem Tag nichts mehr offen war und ob die Erinnerung da schon draußen war. Eingetragen wird das vom Erinnerungsdienst (`reminders.run_once` → `record_if_clear`), nicht von einer Bedienhandlung. Der zunächst gebaute Knopf ist verworfen (D32) und entfernt, bevor ihn jemand gesehen hat. Sichtbar ist davon nichts; die Angabe trägt die Morgenmitteilung und das Maß der Verlässlichkeit.

**Morgen-Rückfall (0.51.0, ab Werk aus seit 0.51.1).** `reminders.morning_fallback` schickt vor dem Aufbruch eine kurze Mitteilung, aber nur an den, der am Abend nicht fertig war, nur an Schultagen und nur wenn Hausaufgaben oder Tasche offen sind. Einstellungen `morning_enabled` und `morning_at` in der Elternansicht, Voreinstellung 06:45, ausgeschaltet.

**Kontowechsel.** `reconcile._ACCOUNT_TABLES` führt jetzt auch `reminder_app_targets`, `reminder_app_deliveries`, `day_closures` und `morning_app_deliveries` mit. Vorher hätte ein Wechsel die für Mitteilungen gewählten Telefone verloren, ohne Fehlermeldung.

## Fehler, die dabei gefunden und behoben wurden

- Ein Fach stand doppelt auf der Quellenliste, als Langform aus den Stunden und als Kürzel aus den Hausaufgaben. Untis speichert an einer Hausaufgabe keine Fach-ID; aufgelöst wird über `su[0].name` aus dem `payload_json` der Stunde.
- Die Regalabfrage nutzte einen falschen Spaltennamen und verschluckte den Fehler in einem `try/except`. Dadurch wären alle Buchseiten eines Kontos auf der Einkaufsliste gelandet. Vom Test gefunden.
- Ein erstes Suchmuster hielt „Klassenfahrt" für eine Arbeitsheftangabe und „vocabulario 4 b" für Seite 4.
- Der Stoff einer Arbeit begann bis 0.50.1 unter Umständen bei einer Arbeit des vorigen Schuljahres.

## Bekannte Lücken

- Die Bilanz verbucht jede Buchseite als vorhanden, sobald das Fach ein Buch im Katalog hat. Zwei von acht Büchern eines Kontos sind aber nicht abrufbar (D31).
- Die inhaltliche Verifikation einer Seite (D30) ist abgestimmt, aber nicht gebaut.
- Der Regal-Scan speichert die Schaltflächen eines Einwilligungsdialogs als Bücher; drei solche Einträge stehen in einem Konto und lassen sich derzeit nicht löschen.
- `CACHE_KEEP = 60` begrenzt die zwischengespeicherten Buchseiten je Kind.
- Die Inhaltsverzeichnisse von Green Line 4 und Geschichte und Geschehen 3/4
  liegen nicht auf den Seiten 2 bis 9; dort greift die Kapitelregel noch
  nicht. Ein zweiter Versuch an anderer Stelle im Buch steht aus.
- Ob die App auf dem älteren Kindergerät eine Bildschirmzeit-Auszeit übersteht, ist weiterhin nur vom Nutzer prüfbar.

---

# Grafische Fächerliste 0.34.0

Auf ausdrücklichen Auftrag, das Gesamtpaket fertigzustellen und bereitzustellen, wurde die grafische Fachliste ergänzt. Balken visualisieren bestehende Themen-Selbsteinschätzungen einschließlich neutraler unbekannter Themen; keine neue Kompetenzformel. Sortierung stärkorientiert nach Anteil verstandener unter eingeschätzten Themen, bekannte Fächer vor unbekannten, Gleichstände alphabetisch. Alle sichtbaren Fächer bleiben erreichbar.

Verlauf: bis zu zwölf tatsächliche Rückmeldungen, dedupliziert nach Unterrichtsstunde, chronologisch sortiert; gleiche Skala 1/2/3. Gleiche horizontale Abstände stehen für aufeinanderfolgende Beobachtungen, nicht gleich lange Zeitintervalle. Keine Glättung, keine Leistungs-/Trendklassifikation, keine vermischten KI-Leistungsbelege. Datierte Einzelwerte, Themen und Quellen im Drilldown erreichbar. Ein Fach gleichzeitig offen, Tastaturbedienung erhalten. Elternstartseite nicht um die neue Liste ergänzt.

Prüfung: 10 gezielte Python-Tests (bestehender Plan plus Unbekannt-/Historien-/Deduplizierungsfälle), Produktionsbuild, Browserprüfung für Sortierung, neutrale Unbekannte, einen Drilldown, Übungslinks, Quellen, Tastatur, Datenfehler, 320/390/430/768 px und größere Schrift erfolgreich. Helle Smartphone-Ansicht visuell kontrolliert. Die Prüfbelege für das enthaltene iPhone-Paket stehen darunter. Keine echte Geräte-/PWA-Abnahme behauptet.

Veröffentlichung/Installation werden nach tatsächlicher Ausführung dokumentiert. Voriger lokaler Stand 0.33.1 wird durch dieses Gesamtpaket abgelöst.

---

# iPhone-Korrekturpaket 0.33.1

Fälligkeit und Hilfe bleiben in der rechten Spalte untereinander bei 320/390/430/768 px. Sichtbare Checkbox 24 px bei 44 px Bedienfläche; weniger Karten-/Zeilenabstände. Gemeinsames ActionLabel für Gespräch und Navigation in zentralen Tages-, Lern-, Fach- und Elternansichten. Fachsymbole bleiben erhalten. Keine Änderung der Bewertungslogik.

Produktionsbuild erfolgreich. Bestehende Browserabläufe für Tagesdashboard (einschließlich Speichern und Fehler), Elternansicht und Kinderlernen erfolgreich. Geometrieprüfung: Hilfe unter Datum, gleiche rechte Kante, mindestens 44 px Hilfe-Bedienfläche und kein horizontaler Überlauf auf den vier Breiten. Helle/dunkle iPhone-Screenshots visuell geprüft. Browser verfügt nicht über vollständige Emoji-Schriften; echte Apple-Emoji/PWA-Abnahme steht aus.

Grafische Fachübersicht als getrenntes Folgepaket in [FAECHERUEBERSICHT.md](FAECHERUEBERSICHT.md) ausgearbeitet. Kompakte Statusbalken, Verlauf und Drilldown sind Ziel; Bewertungs-/Trendregeln bleiben offen. Einbau in Elternstartseite ausdrücklich spätere Entscheidung.

Veröffentlichung blockiert: Git-Push konnte sich nicht authentifizieren (could not read Username). Nur lokal auf Branch codex/iphone-ui-0331 vorbereitet; weder Remote-Veröffentlichung noch Live-Installation behauptet. Änderungspaket separat gesichert.

---

# UI-Konsolidierung 0.33.0

Neue verbindliche Gestaltungsregeln und Ansichtsprüfung: [UI_DESIGN.md](../UI_DESIGN.md). Gemeinsame Aufgaben-/Lernzeilen, frei wählbarer Themenkatalog, farbiges Elterncockpit ohne doppelte Listen, Fachsymbole und deutsche Datumsanzeigen umgesetzt. Freiwillig gewählte Übung wird auch bei späterer Fortsetzung nicht durch den automatischen Tagesvorschlag gesperrt; tatsächliche Tagesanrechnung bleibt einmalig.

Die alten Beschreibungen unten sind historische Umsetzungsschritte. Insbesondere die erklärungsreiche Wochenvorschau und das additive Elterncockpit sind durch die neue Gestaltung ersetzt. Spätere Leistungsbelege sind noch nicht vollständig in die Fachampel integriert.

---

# Konsolidierte Fächer und Hausaufgabenhilfe 0.32.0

Vier zusammenhängende Nutzerkorrekturen umgesetzt:

1. Erledigte Aufgaben werden absteigend nach completed_at angezeigt, bei fehlender Zeit absteigend nach Fälligkeit. Die neueste versehentlich bestätigte Aufgabe bleibt so auffindbar und über den bestehenden Haken wieder zu öffnen.
2. Hausaufgabe ist selbst die Übung: redundante Zusatzübungs-/Übungstestkarte entfernt. Kleiner Hilfe-Link übermittelt ausschließlich die Aufgaben-ID. Der Server prüft Kontozugehörigkeit und lädt den aktuellen Auftrag. Separater Coach-Prompt erklärt Auftrag, Vorwissen und einzelne Schritte mit höchstens einer neuen Frage. Kein vorweggenommenes Gesamtergebnis; keine zusätzliche Testaufgabe oder Kompetenzbewertung. Serverseitig werden task/assessment-Ausgaben in diesem Modus nicht als Lernaufgaben/Belege gespeichert. Kein automatischer Erledigt-Haken, kein zusätzlicher Lernslot und keine doppelte Zeitreservierung. KI-Freigabe, Kostenbegrenzung, Foto-/Nachrichtenrechte bleiben bestehen. Elternansicht folgt den vorhandenen getrennten Test-/Leseregeln.
3. Fachkatalog aus kontoabhängigen Unterrichtsnamen, Quellkürzeln, bekannten Synonymen und konfigurierten Aliasen. Exakte Zuordnung statt Freitextraten. Auswahl wird ohne Schreibvarianten-Dubletten angeboten; Aufgaben behalten freie Titel und bekommen nur bei eindeutigem Fachtitel den ausgeschriebenen Namen. Bestehende Quellwerte müssen dafür nicht pauschal überschrieben werden.
4. Fachkarten zeigen gemeinsam genutzte Lernziele, keine mehrfachen Listen pro Datum. Zielidentität ist datumunabhängig; bereits erkannte Themencluster mit weiterhin gültigen Quellfingerprints werden wiederverwendet. Alle Stundenquellen inklusive einzelner Ratings und Zeiten bleiben erhalten. Neueste Rückmeldung statt dauerhaftem Vorrang einer älteren negativen Rückmeldung. Alte Zielschlüssel werden auf die neuen Gruppen abgebildet, bestehende Session-/Skill-Verknüpfungen bleiben nachvollziehbar. Eine Gruppierung ist kein Beweis für Beherrschung und führt unterschiedliche Skill-Nachweise nicht zusammen. Verwandte, aber noch nicht gemeinsam erkannte Themen bleiben getrennte Teilanliegen; der Mentor erhält konsolidierten Themenkontext und soll vorhandene Kenntnisse nutzen, statt doppelte Lernpflichten zu erzeugen.

Prüfung: 91 Python-Tests, fünf JavaScript-Logiktests, Browserabläufe für Eltern-/Fächeransicht, Kinderlernen/Tests/Hilfe und Tagesdashboard. Breiten 320/390/768 Pixel ohne horizontales Überlaufen; Fachkarten visuell kontrolliert. Browser-Emoji-Schriften eingeschränkt. Keine pädagogische Echtabnahme oder vollständige automatische semantische Gleichsetzung behauptet.

Gesamtvision weiter offen: gemeinsame Fachauswertung mit tatsächlichen späteren Übungsbelegen stärker integrieren, Coach durch den ganzen Tagesablauf, reale Geräteabnahme der Push-Fangleine und abgestimmte optionale Belohnungsregeln. Diese Veröffentlichung ist ein größerer Konsolidierungsblock, kein fertiger Endstand.

---

# Gesamtfortschritt und Familien-Tagescheck 0.31.0

Die Tagesorganisation ist als nutzbarer Kern umgesetzt: Tagesansicht, Material-Stundenplan, freie Lernwahl, selbst erzeugte Übungstests, Elternfreigabe, Löschweg, optionale Push-Fangleine und Anwesenheitskorrektur. Die Gesamtvision ist noch nicht vollständig umgesetzt; keine belastbare Prozentangabe und keine Behauptung einer pädagogisch fertig abgenommenen App.

0.31.0 ergänzt den kompakten Eltern-Tagescheck pro Kind, gespeist aus den bestehenden Tages-/Pack-APIs und derselben Aufgaben-/Feedbacklogik. Angezeigt werden offene Aufgaben bis morgen, undatierte/spätere Aufgaben, bestätigte Fächer am nächsten geplanten Schultag sowie offene Rückmeldungen nur zu beendeten heutigen Stunden. Fehlende Daten zeigen einen Fehler statt Entwarnung. Direkter Zugang zur Kinderansicht. Fokus-/Minutenaktualisierung mit Schutz gegen veraltete Antworten; keine zweite Packliste, kein zusätzlicher KI-Aufruf. Überfällige Aufgaben werden nicht als nachweislich versäumt bezeichnet. Bestehende Fach-/Klausurdetails bleiben zugänglich.

Prüfung: Produktionsbuild sowie Browserablauf mit zwei synthetischen Kindern, unterschiedlichen Bestätigungen, zukünftigen Stunden, Datenfehler und Breiten 320/390/768 Pixel erfolgreich. Keine echten Kinderbestätigungen geändert.

## Nächste größere Phasen

1. **Elternüberblick konsolidieren:** Tagescheck ist erster Meilenstein. Nächster Meilenstein sind gemeinsame Fachauswertungen mit klar getrennten Selbsteinschätzungen, Übungsbelegen und Organisationsnachweisen; redundante Detailblöcke reduzieren.
2. **Coach im Tagesablauf:** dieselben sichtbaren Aufgaben und Checklisten aufgreifen, hilfreiche kurze Rückmeldung nach Aktionen, frei wählbare Reihenfolge. Meilenstein: kompletter Morgen-/Schul-/Nachmittags-/Abendablauf ohne doppelte Planung oder neue Dateneingabepflichten.
3. **Lernqualität und Testvorbereitung:** tatsächliche Lernanlässe, altersgerechte Aufgaben, verlässliche Stoffgrenzen, vollständige lesbare Ausgaben; Erzeugung bis Bearbeitung und Auswertung zusammen abnehmen. Kein erfundener Buchinhalt.
4. **Erfolge und Fangleine:** zunächst belegbare freundliche Erfolgsrückmeldung; konkrete Punkte-/Streakregeln vor Aktivierung abstimmen. Geräteberechtigung und Push-Empfang auf den Kindergeräten noch praktisch abnehmen. Mehrere Erinnerungszeitfenster sind noch offen.

Autark möglich: Umsetzung, Konsolidierung, technische Prüfungen und geprüfte Veröffentlichung. Einbeziehung erforderlich bei neuen Bewertungs-/Belohnungsregeln, Eskalationen und konkreten Geräte-/Erinnerungseinstellungen, die noch nicht gewählt wurden.

---

# Einheitlicher Leseexport 0.30.2

Die Installationsnachprüfung von 0.30.1 identifizierte den separaten schreibgeschützten Integrationszugang als weiteren Verbraucher. Er installiert nun dieselbe Anwesenheitssicht vor query_only. Die Sicht erhält explizit die Archiv-rowid, damit Pagination stabil bleibt. Absenz-Rohmeldungen bleiben erhalten. Regressionstest prüft mehrere Seiten, Kontogrenzen, korrigierte Fehlmarkierung und Schreibschutz. 82 Python-Tests und Frontend-Produktionsbuild erfolgreich.

# Anwesenheitskorrektur 0.30.1

Die expliziten Untis-Gründe „Verspätet“/„Verspätung“ werden für Fehlstunden, Feedbacksperren und Nachholbedarf ignoriert. Keine Minutenschwelle. Eine verbindungslokale SQLite-Sicht korrigiert vorhandene Fehlmarkierungen zentral für alle App-Abfragen, ohne das schreibgeschützte Quellarchiv zu verändern. Überlappende tatsächliche Abwesenheiten haben Vorrang; Meldungen anderer Konten oder außerhalb der Stunde verändern nichts. Fehlzeitenmetadaten und Mentor-Zeitberechnung schließen Verspätungen ebenfalls aus. Originalmeldungen bleiben im Integrationsdatensatz absences nachvollziehbar.

Prüfung: 81 Python-Tests erfolgreich, einschließlich expliziter Verspätung unterschiedlicher Dauer, überlappender echter Abwesenheit, Kontogrenzen, gespeicherter Rückmeldung und Archiv-Neuberechnung. Frontend-Produktionsbuild erfolgreich. Keine UI-Umgestaltung in diesem Fehlerpaket.

Zusätzlich korrigiert die Archiv-Integration recompute_attendance nach ihrem eigenen Update die gespeicherten Flags beim Abgleich. Der App-Fix benötigt dieses separate Update nicht.

# Optionale Erinnerungssicherung 0.30.0

Ein täglicher gebündelter Tagescheck für offene Aufgaben mit Fälligkeit bis morgen, noch nicht bestätigtes Fachmaterial für morgen und fehlende Rückmeldung zu beendeten heutigen Stunden. Kein KI-Aufruf, keine Ableitung eines tatsächlichen Versäumnisses aus fehlendem Häkchen. Standard aus; Eltern wählen ausdrücklich eine Zeit zwischen 14 und 21 Uhr (Europe/Berlin). Versand nur im folgenden 30-Minuten-Fenster. Kinder melden Geräte selbst an; Eltern erhalten keine automatischen Eskalationen.

Persistente Reservierung vor Versand verhindert Doppelversand nach Neustarts. Bei unklarem/fehlgeschlagenem Versand kein automatisches Wiederholen am selben Tag; Status sichtbar, Testweg vorhanden. Push-TTL 30 Minuten. Providerannahme ist kein Empfangsnachweis. Daten und Empfänger werden vor Versand erneut geprüft. Ungültige Geräte (404/410) werden entfernt; Transporttimeout zehn Sekunden. Neue Geräte werden nur für unterstützte HTTPS-Pushdienste registriert. Account-Reconciliation bezieht Packlisten und Erinnerungen ein.

Service Worker ergänzt Push-/Klickhandler mit auf die App begrenzten Links. Alle privaten API-Aufrufe umgehen seinen Cache; API-Antworten erhalten no-store. Alte Cacheversion wird bei Aktivierung gelöscht. Offline wird für diese Daten ein Fehler statt eines alten Erledigungsstands gezeigt.

Prüfung: 71 Python-Tests aus Lern-/Mentor-/Plan-/Pack-/Integritäts- und Erinnerungsbereichen (70 gemeinsam, zusätzliche Account-Neuzuordnung separat); Service-Worker-Ereignistest für Anzeige, fehlerhafte Payload, sichere Links und API-Cacheausschluss; bestehende Browserabläufe plus Eltern-Zeitwahl und Kinder-Leseansicht; Produktionsbuild. Reale Registrierung/Zustellung auf Kindergeräten noch nicht abgenommen, keine echte Nachricht versendet, keine Uhrzeit eingeschaltet.

Nutzung: Einstellungen → Erinnerungen. Im Elternkonto Zeit speichern/einschalten; im Kinderkonto auf dem betreffenden Gerät anmelden und Testnachricht prüfen. Auf iOS/iPadOS als Home-Screen-Web-App und nach ausdrücklichem Tippen auf Anmeldung; siehe [WebKit-Dokumentation](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/). Ruhe-/Fokus-Einstellungen können die Anzeige beeinflussen. Fehlende Empfangsbestätigung wird nicht als Kinderfehler interpretiert.

Weiter: echte Geräteabnahme und Alltagserfahrung; danach bedarfsgerechte zusätzliche Zeitfenster, Mentor-Coaching und faire optionale Erfolgsrückmeldung. Aktuell eine tägliche Fangleine, kein vollständiges Mehrphasen-Reminder-System.

---

# Materialcheck im Stundenplan 0.29.4

Packen zeigt den vollständigen nächsten Schultag in chronologischer Reihenfolge einschließlich Ausfällen, Anfang/Ende, Raum- und Lehrerwechseln. Beim ersten stattfindenden Vorkommen jedes Fachs steht ein Material-Häkchen, danach kein weiteres für dasselbe Fach. Doppelstunden bleiben als Zeiten sichtbar. Ausgefallene/abwesende Stunden erzeugen kein Material-Häkchen. Ausgeblendete Kurse bleiben ausgeblendet.

Allgemeine Packpunkte Mäppchen und Trinken entfernt; alte gespeicherte Fachschlüssel bleiben gültig. Alte allgemeine Bestätigungen werden nicht mehr gezählt. Morgens derselbe Stundenplan für heute, nächster Schultag weiterhin vollständig sichtbar. Keine getrennten doppelten Vorschau-Karten.

Hausaufgabenabschluss verkürzt und mit Party-Emoji gestaltet. Fehler beim Laden zeigen weiter einen Fehler statt falscher Entwarnung. Keine variable KI-Textgenerierung nötig.

Prüfung: sechs Packlisten-API-Tests, Produktionsbuild und Tagesdashboard-Browserablauf mit synthetischen Daten. Doppelstunden mit einem Häkchen, sichtbarer Ausfall/Raumwechsel, Speicherung/Fehler, Abend-Morgen-Erhalt und 320/390/768 Pixel geprüft. Darstellung geprüft; Testsystem hat weiterhin unvollständige Emoji-Schriften. Live-Installation separat bestätigen.

---

# Gemeinsame Farb- und Navigationsgestaltung 0.29.3

Petrol als Handlungsfarbe; Mint für Packen/freies Üben, Blau für Schule, Lavendel für Lernvorschläge. Farben dienen Orientierung, nicht einer neuen Leistungsbewertung. Heller und dunkler Modus verwenden abgestimmte Flächen. Hauptnavigation und Lernreiter kombinieren Emoji und Text; aktive Zustände zusätzlich per Fläche/Schrift und zugänglichen Attributen.

Kinder sehen im Mentor kompakte aktuelle Empfehlungen statt der vollständigen zweiten Wochenplanung. Freie Wahl und Aufgaben bleiben sichtbar, Detailplanung bleibt erreichbar. Fokusdarstellung und reduzierte Bewegung ergänzt.

Prüfung: Produktionsbuild und vorhandene Browserabläufe für Tagesdashboard, Packen, Kinderwahl/Übungstests, Elternfreigabe und Löschung erfolgreich; 320/390/768 Pixel ohne horizontales Überlaufen. Helle/dunkle Screenshots geprüft. Test-Chromium hat keine vollständigen Emoji-Schriften; tatsächliche Apple-Emoji-Darstellung nicht damit abgenommen. Backend unverändert. Bestehende Barrierefreiheitshinweise nicht vollständig bereinigt.

---

# Freies Üben und gezielte Verlaufskorrektur 0.29.2

Freie Fachwahl steht direkt vor den Vorschlägen. Offene Hausaufgaben sind als Übungsanlass auswählbar; ein Kalendereintrag ist keine Voraussetzung. Kinder können Fach, Themen und Dauer eines Übungstests selbst wählen. Bestehende Konto-/Schreibrechte, KI-Freischaltung und Kostenkontrolle bleiben wirksam. Kinderentwürfe werden direkt als nutzbare, noch nicht elterngeprüfte KI-Übungen gespeichert. Elternprüfung und isolierte Demo bleiben erhalten. Bestehende Elternentwürfe benötigen die sichtbare Freigabe, damit Kinder sie sehen.

Eltern-Löschweg: Lernen → Gespräche → Einheit öffnen → Diese Einheit entfernen → Einheit endgültig löschen. Version und laufende Bearbeitung werden vor der Transaktion geprüft. Nachrichten, Anhänge, Belege und Planzeit werden entfernt; betroffene Lernstände und Wiederholungen aus verbleibenden Belegen neu berechnet. Kostenbuchungen bleiben erhalten. Keine pauschale Löschung anderer Übungen.

Prüfung: 63 Python-Tests aus Lernraum, Mentor, Lernplan, Packliste und Rückmeldeintegrität; Produktionsbuild; Browserfälle mit synthetischen Kinder-/Elternkonten für freie Fachwahl, Hausaufgaben-Übungstest, verborgene Lösungen, Eltern-Leseansicht/Freigabe und erfolgreiche/fehlgeschlagene Löschung. Tagesdashboard-Browserprüfung ebenfalls bestanden. Kein vollständiger Live-Schreibtest in echten Kinderkonten; vorhandener Integrationszugang ist nur lesbar.

---

# Gespeicherte Packcheckliste 0.29.1

Direkt sichtbare Checkliste im Tagesdashboard, morgens für den aktuellen und danach für den nächsten Schultag. Bestätigungen bleiben pro Konto und Datum erhalten. Ausfall, Abwesenheit und ausgeblendete Kurse werden berücksichtigt; unbekannte Unterrichtsdaten werden nicht als vollständige Packliste ausgegeben. Materialien bleiben allgemein, etwa Sportzeug und Fachunterlagen. Konkrete Sondermaterialien aus Unterrichtsnotizen werden noch nicht ausgewertet.

Additive Datenbankmigration; stabile Materialschlüssel bewahren Bestätigungen bei Raum- und Zeitänderungen. Neue Fächer öffnen nur neue Punkte. Schreibrechte, Demo-Schutz, Versionskonflikte und Quellenänderungen werden serverseitig geprüft. Elternbestätigungen speichern die tatsächliche Benutzerkennung; aus Häkchen wird keine eigenständige Leistung des Kindes abgeleitet.

Prüfung: 60 Python-Tests, vier JavaScript-Tests, Produktionsbuild sowie Browserprüfung mit synthetischen Daten für Speicherfehler, Neuladen und 320/390/768 Pixel. Bestehende Svelte-Barrierefreiheitshinweise bleiben; kein Nachweis für echte Geräte oder Push-Zustellung. Live-Installation wird separat dokumentiert.

Nächstes Paket: konfigurierbare, gebündelte Erinnerungen anhand tatsächlich offener Aufgaben und Packpunkte. Zeitfenster und Geräte vor Aktivierung konkret abstimmen. Mentor-Checklisten, gemeinsame Fachauswertung, Elternübersicht und optionale Erfolgsrückmeldungen bleiben weitere Phasen.

---

# Tagesdashboard 0.29.0

Erster Umsetzungsschritt des UI-Redesigns: direkt sichtbare Tagesaufgaben und Lernvorschläge, offene Rückmeldungen mit erreichbarem Verlauf, allgemeine nächste Schulvorschau und reduzierte Hauptnavigation. Vorhandene Direktlinks bleiben erhalten. Elternstart anhand der Rolle statt nur der Kontenzahl.

Prüfung: 55 bestehende Python-Tests; vier neue JavaScript-Tests für Tagesaufteilung und Datumsgrenzen; Browserprüfung am Produktionsbuild mit synthetischen Daten für erfolgreiche/fehlgeschlagene Speicherung, sichtbare Aufgabenbereiche und 320/390/768 Pixel. Helle und dunkle Screenshots geprüft. Bestehende Svelte-Barrierefreiheitshinweise bleiben. Echter iPhone-/PWA-Betrieb und Zustellung von Push wurden damit nicht geprüft.

Packbestätigungen, Reminder-Zeitsteuerung, Belohnungen, vollständige Zusammenführung der Fachbewertung und weitere Mentorinteraktion sind Folgepakete. Kein vollständiger Abschluss der Gesamtvision. Veröffentlichung und Live-Version werden separat dokumentiert.

---

# Korrekturpaket 0.28.2

Stand: 13.09.2026. Ausgangspunkt: Remote 58cf623, laufende App 0.28.1 über Supervisor und Health-API bestätigt. Zunächst geprüfter Code; Veröffentlichung und Live-Abnahme separat nachtragen.

- Kommentar ohne Emoji erzeugt keine Bewertung. Transaktionale Migration erhält alte Werte, IDs, Zeitstempel und stabile Unterrichtsbezüge. Keine rückwirkende Interpretation alter Kommentare.
- Verständnisstatistik zählt nur 1–3; Aufsicht und Kommentare sind ausgeschlossen. Notizen ohne Bewertung bleiben als Rückmeldelücke sichtbar.
- Erinnerungszahl ist accountweit. Bestehende Benutzerfelder bleiben kompatibel. In durchsuchbaren HA-Automationen und Skripten kein Treffer für `checkin_reminder` oder `unrated_lessons_today`; keine Zustellwirkung nachgewiesen, keine Nachricht versendet.
- Elternansicht begrenzt ihre Aussage auf Unterrichtsrückmeldungen. Spätere Mentorfortschritte einzubeziehen bleibt Aufgabe der gemeinsamen Fachauswertung.
- 55 Lern-/Mentor-/Plan-/Integritätstests bestanden. Produktionsbuild erfolgreich mit bestehenden Svelte-Barrierefreiheitshinweisen. Neue Version noch nicht live geprüft.

Vor Installation einen Wiederherstellungspunkt der App-Daten vorhalten. Alter Code allein ist nach neuen NULL-Bewertungen kein vollständiger Rückweg. Wiederherstellung alter App-Daten würde spätere Eingaben verlieren; bevorzugt vorwärts korrigieren. Migration lokal auf Datenerhalt und wiederholten Start geprüft.

Nächster Produktschritt: Fachzustände und iPhone-Vorschau mit repräsentativen Fällen ausarbeiten. Bewertungs-/Trendregeln vor produktiver Nutzung entscheiden.

---

## Historischer Stand

# Belegter Stand und nächste Arbeit

Stand: 13.09.2026. Codebasis: Release 0.28.1, GitHub-Commit 16a7c44c2c2fb41ad5ea55a0f4643fd336a05330. Konzeptfortschreibung ändert keine laufende App.

## Vorhanden

- Direkte Stundenbewertung mit drei Emojis; zusätzliche Aufsichtsmarkierung bei Vertretung. Abwesenheit/Ausfall in der Oberfläche gesondert behandelt.
- Hausaufgaben mit Erledigung und Teilaufgaben, Unterrichtsvorschau, Elternübersicht mit Mitlernen, Klausuren und Feedbacklücken.
- Gemeinsamer Lernplan für Plan, Nachmittagsplanung, Fächervorbereitung und Mentor; Tagesbelastung und Sieben-Tage-Vorschau.
- Mentorverläufe, Aufgabenbelege und Wiederholungszustände; Trennung zwischen Hilfe, Selbstbericht und selbstständiger Leistung sowie Demo/Kinderstand.
- Übungsklausuren mit Unterrichtsthemengruppierung, Ergänzung eigener Themen, Druck-, Online-, Foto- und Selbstkontrollpfaden im Code. Nicht alle Wege sind Ende-zu-Ende live abgenommen.
- Web-Push-Anmeldungen/Testfunktion und HA-Nachrichtenvorlagen vorhanden. Aktive Zustellung und Zeitsteuerung nicht aus bloßer Codeexistenz ableiten.

## Prüfbelege und Grenzen

51 automatisierte Lern-/Mentor-/Plantests sowie Frontend-Produktionsbuild für 0.28.1 bestanden. Live sichtbar geprüft: korrigierte Fachrotation in Wochenvorschau, aktualisierte nächste Unterrichtstermine und Kennzeichnung angerechneter Zeit ohne falsche Überlastungsmeldung. Die HA-Versionabfrage beim letzten Nachtest schlug fehl; die neue Oberfläche wurde direkt geprüft.

Geschichts-Demo: neun erfundene Stunden und drei Hausaufgaben ergeben drei auswählbare Themenbereiche. Klausurentwurf wurde erzeugt; sechs Aufgaben erschienen für 15 Minuten zu umfangreich. Nicht freigegeben. Zeitkalibrierung und kompletter Druck-/Foto-/Bewertungsdurchlauf bleiben offen. Tests ersetzen keine pädagogische Wirksamkeitsmessung.

# Zentrale Materialablage 0.40.0

Umgesetzt: Stufe 1 und 2 aus [Materialablage](MATERIALIEN.md), zusätzlich die Nutzung durch Mentor und Übungsklausur, damit Abgelegtes sofort wirkt. Commit 5d6babf.

Eine Tabelle `materials` je Kind mit Verknüpfungen zu Thema, Hausaufgabe, Stunde und Arbeit; getrennte Datumsangaben für Upload, Aufnahme und inhaltliche Zugehörigkeit; `locked_fields` schützt jede menschliche Korrektur vor späteren Auswertungen. Upload als Foto oder PDF bis 12 MB aus der Materialliste, aus jeder Hausaufgabenzeile und aus dem Lernbereich, auch mehrseitig. Auswertung startet sofort im Hintergrund; ein nächtlicher Lauf holt offene, fehlgeschlagene und veraltete Einträge nach, höchstens 40 je Nacht über das bestehende Hintergrundbudget. Text-PDFs werden ohne Modell gelesen, gescannte Seiten über `pdftoppm` dem bildfähigen Modell vorgelegt. Bestehende `learning_materials` wandern mit Themenbezug und Prüfstatus in die neue Ablage.

Geprüft: 162 automatisierte Tests und Frontend-Produktionsbuild bestanden, davon 12 neue für Ablage, Rechte, gesperrte Felder, Themenverknüpfung, Kontextauswahl und nächtliche Auswahl. Live auf der laufenden Instanz: ein fotografiertes Physik-Arbeitsblatt wurde ohne weitere Eingabe als Fach PHYSIK, Art Arbeitsblatt, mit Titel, Kurzbeschreibung und Datum eingeordnet, automatisch mit dem passenden Thema verknüpft, und die Schaltpläne wurden in beschreibenden Text übersetzt. Der Lernmentor beantwortete anschließend eine Frage zu einer Aufgabe dieses Blattes inhaltlich richtig.

Offen: Übernahme vorhandener Chatanhänge in die Ablage, Suche über größere Bestände, Obergrenzen für Seiten je PDF in der Praxis, und die in MATERIALIEN.md notierten Fragen zu Aufbewahrungsdauer und Benachrichtigung. Ein gescanntes Mehrseiten-PDF wurde noch nicht live geprüft.

## Durch Codeprüfung belegte Lücken

1. `routers/dashboard.py`: Mitlernen wertet 21 Tage alte Check-ins aus, ab drei Rückmeldungen und 30 Prozent gelb/rot; spätere Mentorfortschritte fehlen in dieser Berechnung. „Alles im grünen Bereich“ ist daher zu weitgehend.
2. `LessonCard.svelte` und `LessonDetail.svelte`: Notiz ohne Emoji setzt automatisch Bewertung 2. Organisatorische Kommentare können Unsicherheit vortäuschen.
3. `routers/notify.py`: identischer accountweiter Stand wird je verknüpftem Benutzer geliefert und im Nachrichtenvorschlag aufsummiert. Potenziell vervielfachte Zahl fehlender Rückmeldungen; tatsächliche HA-Nutzung dieser Vorlage noch prüfen.
4. Sieben Hauptziele für Kinder, zusätzlich Elternübersicht; ausführlicher Plan auch im Mentor. Informationsdichte und doppelte Wege bereinigen.
5. Keine integrierte kompakte Fachübersicht mit belegtem Trend und aufklappbarer KI-Tiefenanalyse.
6. Keine eigenständige strukturierte Erfassung externer Übungseinheiten; keine gespeicherte Material-Packliste im geprüften Stand.

## Vorgeschlagene Reihenfolge – noch keine fertigen Funktionen

1. Bestehende Daten-/Anzeigewidersprüche korrigieren und vorhandene Rückmeldewege erhalten.
2. Regeln und repräsentative Fälle für Fachzustand, Trend und unbekannten Stand festlegen. Kompakte Oberfläche daran entwerfen; keine scheinpräzise Gesamtnote.
3. Fachübersicht und konsistente Elternansicht auf gemeinsamem Datenbestand umsetzen, Details nur aufklappbar.
4. KI-Tiefenanalyse mit Quellen, Aktualitätsstand und begrenzten Kosten ergänzen; gespeicherte Analysen wiederverwenden.
5. Externe Übungen und Packbestätigung schlank in bestehende Fach-/Tagesansichten einfügen.
6. Klausurumfang kalibrieren und ausstehende Arbeitswege live prüfen.
7. Mit den Nutzenden Alltagstauglichkeit und Fortschritt beobachten; erst danach offene Gamification-Varianten auswählen.

Bei jeder Fortsetzung Remote-Stand, lokale Änderungen und Live-Version neu prüfen. Bereits gefundene Fehler nicht als behoben ausgeben, solange Codeänderung und Prüfung fehlen.
