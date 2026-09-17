# Übergabe an die nächste Session

Stand 17.09.2026, abends. Live läuft Schul-Cockpit 0.81.0 (vom Nutzer
eingespielt), Add-on-Log ohne Fehler. `main` ist ausgeliefert, Arbeitsbranch
und `main` stehen gleich. Keine Kindernamen, PINs oder Schlüssel in diesem
Dokument (D15/D68); Konten heißen hier Konto 1 und Konto 2.

## Was diese Session ausgeliefert hat (0.70.0 bis 0.81.0)

Belege je Release in [UMSETZUNGSSTAND.md](UMSETZUNGSSTAND.md), Entscheidungen
D65 bis D86 in [ENTSCHEIDUNGEN.md](ENTSCHEIDUNGEN.md), Nutzertexte in
`schul_cockpit/CHANGELOG.md`.

- 0.70 Betrieb: Web-Push entfernt, CI (`.github/workflows/tests.yml`), Doku.
- 0.71 Nachmittags-Mitteilung mit automatischer Fälligkeit.
- 0.72 Nachholen als Mentor-Lage (Fehlzeit → Einstieg, Ende setzt nachgeholt).
- 0.73 Fächerübersicht auf den fünf Lernstand-Stufen; 0.74.1 neueste zuerst.
- 0.74 Wochenrückblick für Eltern ohne Modellaufruf.
- 0.75 Der Mentor beendet nie selbst: Grenze und Modell-Ende sind Vorschläge
  (D73); Verstehen als Einstieg an der Stunde (D74); 0.75.1 leere
  Korrekturfelder sperren nichts mehr (D76).
- 0.76 Eichung: Seitenart und Handschrift je Lesung, Handschrift immer zum
  Gegenlesen (D77), Zahlen- und Zeilenvergleich, Reasoning-Tiefe wählbar
  (bleibt low, D78). Drei Eichungsrunden dokumentiert; Hauptmodell bleibt
  fürs Abschreiben (D75).
- 0.77 Gegenlesen mit Kontext: Seiten eines Zettels gegen Unterricht und
  Hausaufgaben, Ziffernverwechslung als Vorschlag (D79).
- 0.78 Kontrollieren: „Lösung prüfen lassen“ an der Hausaufgabe (D80); „So
  korrigieren“ mit einem Tipp je Seitenangabe (D81).
- 0.79 Gespräche gelten als Gespräche des Kindes, Demo ist Simulation (D82);
  Verlaufsliste mit Wortlaut der Hausaufgabe, Art, Stand, letztem Dialog.
- 0.80 Angehängte Fotos belegen kein fremdes Arbeitsblatt (D83); Abfragen
  mit Merkzettel in der Hausaufgabenhilfe (D84); 0.80.1 Begriff
  Aufgabenbearbeitung.
- 0.81 Arbeitsblätter mit Bezug, Stufe 1 (D85): kein Raten, Vorschläge zum
  Antippen, „Vorhandenes Blatt zuordnen“, Rolle an Verknüpfungen,
  Doppelseite von Hand („10-11“), Begriffe Mitschrift/Aufgabenbearbeitung (D86).

## Live geprüft nach 0.81.0

- Die falsche Bindung an „Arbeitsblatt beenden“ (Konto 2, Geschichte) ist
  weg; die Stelle steht wieder als fehlend.
- Die Doppelseite 10/11 des Geschichtsbuchs ist auf beide Seiten gesetzt
  (gesperrt); die Ausarbeitung dazu steht als Aufgabenbearbeitung.
- Die Autor-Migration ist gelaufen: im Verben-Gespräch steht das Kind als
  Sprecher; die Verlaufsliste zeigt den Wortlaut der Hausaufgaben.

## Als Nächstes, in dieser Reihenfolge

1. **Erste echte Abfrage beobachten** (D84): Merkzettel im Zusammenfassungs-
   feld, Wiederholung der Fehler, Ende als Vorschlag. Verlauf per
   Ingress-API lesen (`.../learning/mentor/sessions/<id>`). Danach die
   Kostenoption entscheiden: Buchseiten nicht mehr bei jedem Zug mitschicken,
   sobald der Bestand im Merkzettel steht (36 Züge × Bilder im Verben-Gespräch).
2. **Erste echte Kontrolle beobachten** (D80): Lesbarkeit der Handschrift,
   Urteil je Aufgabe, ob das Modell trotz Verbot Ergebnisse nennt; Instruktion
   `CHECK_INSTRUCTION` in `routers/mentor.py` nachschärfen.
3. **Arbeitsblätter Stufe 2 und 3** ([ARBEITSBLAETTER.md](ARBEITSBLAETTER.md)):
   Kandidaten schon beim Einwerfen mit Vorsortierung durch die Auswertung
   (`hinweise.blatt_kandidaten`, `sheet_candidate`), Kennung „AB Fach Datum
   Titel“ in Listen und Mentor, Mentor bittet bei fehlendem Blatt um ein Foto
   statt ein fremdes zu nehmen. Entschieden ist alles (D85), es fehlt nur der Bau.
4. **Mentor-Einstieg Schritt 5** ([MENTOR_EINSTIEG.md](MENTOR_EINSTIEG.md)):
   Verfassung, kürzere Einheiten bei Frust- und Müdigkeitssignalen, Erfolg zum
   Schluss. Konzept liegt vor, keine offene Grundsatzfrage.
5. Foto ohne Frage im Hilfegespräch als Auslöser der Kontrolle (Konzept, offen).

## Grundsatzfragen, die der Nutzer noch nicht entschieden hat

- Lerneinheiten-Gruppierung nach Feld ([LERNEINHEITEN.md](LERNEINHEITEN.md)):
  Ist ein Oberthema selbst übbar?
- Kostensätze der Modelle laufen am 01.12.2026 ab (`ai_gateway.RATE_UNTIL`);
  danach sperrt der Gateway. Preise vom Nutzer oder Freigabe zur Übernahme.
- Sensor „Hausaufgaben offen“ der Integration widerspricht den Todo-Listen:
  aus dem Todo-Abgleich speisen oder umbenennen.
- Abschreibmodell (D54/D75): günstigere Modelle nur je Seitenart nach Messung.

## Budget

September (Stand 17.09.): Monat 45,71 von 50 €, Quellen 28,50 von 30 €,
Hintergrund 9,75 von 20 €. Wochenverbrauch Konto 2 rund 19,5 €, darin die
Eichungen. Bis zum Monatswechsel wenig Luft; lange Abfragen mit Buchseiten je
Zug sind der größte Posten. Der Nutzer will Qualität vor Kosten, aber keine
unnötigen Kosten.

## Arbeitsweise, die sich bewährt hat

- Immer auf `main` ausliefern (CLAUDE.md): auf dem Harness-Branch entwickeln,
  `git merge --ff-only` nach `main`, beide pushen, jeweils als eigener
  Befehl (kombinierte Push-Befehle blockt der Klassifizierer).
- Jede sichtbare Änderung: Version in `schul_cockpit/config.yaml`, Eintrag in
  `CHANGELOG.md`, Abschnitt in UMSETZUNGSSTAND.md oben, Entscheidung als D-Nummer.
- Tests: `python3 -m pytest tests` (432 grün), Frontend `npm run build` in
  `schul_cockpit/frontend`. Migrationen ans Ende von `_MIGRATIONS` in `db.py`.
- Live-Diagnose: `scripts/ha_diagnose.py`, `scripts/ha_addon_log.py` (beide
  mit curl-Fallback), `scripts/ha_supervisor.mjs` (Websocket, Ingress-Sitzung).
  Python-urllib bekommt in der Sandbox 403. `cd` in Verbundbefehlen setzt das
  Arbeitsverzeichnis zurück: absolute Pfade nehmen. Add-on-Updates nie selbst
  auslösen.
- Der Nutzer entscheidet Grundsatzfragen und will Vorschläge mit Empfehlung;
  Bedienung einfach halten, Vorschläge zum Antippen statt Automatik oder
  Formular; Kinder nutzen die Geräte der Eltern.
