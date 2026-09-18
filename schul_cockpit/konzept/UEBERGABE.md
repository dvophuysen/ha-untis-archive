# Übergabe an die nächste Session

Stand 17.09.2026, nachmittags. Live läuft Schul-Cockpit 0.90.0, Add-on-Log ohne
Fehler. `main` ist ausgeliefert, Arbeitsbranch und `main` stehen gleich. Keine
Kindernamen, PINs oder Schlüssel in diesem Dokument (D15/D68).

## Was diese Session ausgeliefert hat (0.82.0 bis 0.90.0)

Entscheidungen D87 bis D94 in [ENTSCHEIDUNGEN.md](ENTSCHEIDUNGEN.md), Belege je
Release oben in [UMSETZUNGSSTAND.md](UMSETZUNGSSTAND.md).

- 0.82/0.83 KI-Einrichtung an einer Stelle (D87, D88): zwei Azure-Foundry-Zugänge,
  vier Modellstufen (hoch, mittel, niedrig, transkription) mit Modellname,
  optionalem Bereitstellungsnamen, Foundry-Auswahl und eigenen Kostensätzen. Die
  App kennt nur Stufen. Zwei Pannen dabei: ein falsches Optionsschema (0.82.1)
  und ein 503 in den Übersichten (0.83.1), beide mit Test abgesichert.
- 0.83.2 „Kapitel prüfen" springt zum Buch statt auf eine leere Seite.
- 0.84.0 Richtwerte statt Sperren (D89): kein Aufruf scheitert mehr an einem
  Rahmen, Hochrechnung auf den Monat, Warnung ab 60 €, Freigabe von
  Reservierungen, die der Anbieter nie angenommen hat.
- 0.85.0 Zwei Durchgänge beim Materiallesen (D90): günstig lesen, bei
  Handschrift, Arbeitsheft, Tabelle, MINT-Fach oder Unlesbarem gründlich
  nachlesen, Tabellen zusätzlich mit hoher Reasoning-Tiefe.
- 0.86.0 Bestand einer Abfrage in der App (D91): der Merkzettel wird geführt
  statt jede Runde neu geschrieben; Buchseiten gehen nur noch mit, solange kein
  Bestand steht.
- 0.87.0 Arbeitsblätter Stufe 2 und 3 (D92): Vorsortierung durch die Auswertung
  mit Beleg vom Blatt, Kennung „AB GE 16.09. Titel", Mentor bittet bei fehlendem
  Bezug um ein Foto.
- 0.88.0 Verfassung des Kindes (D93): einsilbige Antworten, viele Hinweise oder
  späte Stunde führen zu kleineren Schritten und einem Pausenangebot.
- 0.89.0/0.89.1 Eichwerkzeug für die Unterrichtsauswertung.
- 0.90.0 Unterrichtsauswertung auf der niedrigen Stufe (D94), mit eigener
  Einstellung getrennt vom Abschreiben.

## Messwerte, auf die sich das stützt

Alle 630 Aufrufe im September: 50,06 € gebucht, real rund 26 $ zum Listenpreis.
Laufender Betrieb 1,75 $/Tag, davon 62 % Automatik ohne Kind, 34 % die Kinder.
Ein Mentor-Zug 0,023 $, eine Buchseite 0,054 $, eine Aufnahme 0,0008 $, die
36-zügige Verben-Abfrage 1,69 $. Eichungen an zehn Materialseiten und zwölf
Unterrichtsstunden: Zahlen in UMSETZUNGSSTAND.md. Die Buchung liegt bewusst
rund beim Doppelten der Azure-Rechnung und warnt deshalb früh.

## Offen

- Erste echte Kontrolle mit Foto beobachten (D80): Es gibt weiterhin keine.
- Foto ohne Frage im Hilfegespräch als Auslöser der Kontrolle (Konzept, offen).
- Grundsatzfragen beim Nutzer: Oberthema übbar
  ([LERNEINHEITEN.md](LERNEINHEITEN.md)), Kostensätze vor dem 01.12.2026.
- Der Sensor „Hausaufgaben offen" ist geklärt und kein Defekt: In UNTIS lässt
  sich nichts abhaken, der Sensor trägt alle Hausaufgaben, das Sync-Skript
  filtert auf das Fällige.
- Hochrechnung steht bei rund 150 € gebucht im Monat. Der Siebentageschnitt
  enthält die Eichungen dieses Tages und das einmalige Einlesen; die Wirkung der
  günstigen Stufen zeigt sich erst in normalen Tagen.

## Arbeitsweise

- Immer auf `main` ausliefern, Updates sofort einspielen (Nutzerwunsch
  17.09.): `git merge --ff-only`, beide pushen, dann `/store/reload` und
  `/addons/<slug>/update` über `scripts/ha_supervisor.mjs`. Der Update-Aufruf
  antwortet mit `unknown_error`, obwohl er anläuft; auf die Version warten.
- Jede sichtbare Änderung: Version in `schul_cockpit/config.yaml`, Eintrag in
  `CHANGELOG.md`, Abschnitt oben in UMSETZUNGSSTAND.md, Entscheidung als D-Nummer.
- Tests `python3 -m pytest tests` (463 grün), Frontend `npm run build`.
  Migrationen ans Ende von `_MIGRATIONS` in `db.py`.
- Messen statt schätzen: Der Lese-Schlüssel steht in den Add-on-Optionen, die
  Aufrufe in `mentor_ai_calls` über die Lese-API (READ_ACCESS.md). Eichungen
  laufen über `materials/{id}/analysis/compare` und
  `learning/discovery/compare`, beide speichern nichts.
- Der Nutzer entscheidet Grundsatzfragen, will Vorschläge mit Empfehlung und
  konsequentes Abarbeiten ohne Rückfragen bei allem anderen. Qualität steht weit
  vor Kosten.

## Warteschlange: Antwort-Chips und doppelte Aufgabenstellung (18.09.)

Nutzerrückmeldung mit Bildschirmfoto, Thema „Spanische Texte verstehen und
erschließen". Noch nicht gebaut, nur festgehalten.

**Befund aus dem Code.** Die drei Chips sind keine Absicht, sondern ein
Höchstwert: `Reply.choices` erlaubt bis zu drei, `turn()` schneidet zusätzlich
auf drei ab. Wie viele es tatsächlich werden und was daraufsteht, entscheidet
das Modell frei; die App prüft nur, dass kein Chip die Lösung verrät
(`safe_choices`, D95) und ersetzt sie nach zwei Hinweisen durch „Anderes
Beispiel / Für heute fertig". Es gibt keine Regel, was ein Chip sein soll —
deshalb steht unter einer Auswahlaufgabe mit a/b/c so etwas wie „Auf den
Satzbau achten", das als Antwort sinnlos ist.

**Fragen des Nutzers.**

- Warum immer drei? Nur weil drei die Obergrenze ist. Kein didaktischer Grund.
- Warum nicht a | b | c | „Ich benötige Hilfe"? Weil D95 Chips verbietet, die
  die Lösung enthalten — der Anlass war eine angetippte richtige Antwort, die
  als eigene Leistung gebucht wurde. Bei einer Auswahlaufgabe sind die Buchstaben
  aber gerade keine verratene Lösung, sondern die Aufgabe selbst. Die Sperre ist
  hier zu grob: Sie müsste den Buchstaben (a/b/c) vom Lösungstext trennen.
- Was soll „Auf den Satzbau achten" für eine Antwort sein? Nichts. Ein Chip muss
  entweder eine Antwort auf die gestellte Aufgabe sein oder ein Weg weiterzureden
  („Erst kurz erklären", „Weiß ich nicht"). Ein Lerntipp ist beides nicht.

**Zweite Beobachtung.** Der Mentor leitet die Aufgabe zweimal ein: einmal im
Fließtext der Nachricht, einmal im Kasten „Deine Aufgabe" aus `task.prompt`.
Die Ansicht zeigt beides untereinander (`Mentor.svelte`, `m.payload.task`).
Entweder stellt die Nachricht die Aufgabe und der Kasten entfällt, oder die
Nachricht führt nur hin und die Aufgabe steht allein im Kasten. Heute steht
sie doppelt, in leicht abweichender Formulierung.

**Vorschlag für später.** Chips bekommen eine Rolle: bei einer Auswahlaufgabe
die Antwortmöglichkeiten als Buchstaben, sonst höchstens zwei Wege
weiterzureden, und immer „Weiß ich nicht". Die Anweisung sagt außerdem, dass
die Nachricht zur Aufgabe hinführt und sie nicht wiederholt.
