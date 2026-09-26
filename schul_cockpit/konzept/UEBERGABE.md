# Übergabe an die nächste Session

Stand 26.09.2026. Live läuft Schul-Cockpit **1.36.0** (vergessene Rückmeldungen bleiben offen wie Hausaufgaben, D210; vier Ringe auf der Familienkarte, Freitagsstand am Wochenende, D209; 1.34.0 war die Überarbeitung D208); untis_archive **0.6.0** ist über HACS installiert und wird erst mit dem nächsten HA-Neustart durch den Nutzer wirksam (HA 2026.9.3; getestet gegen 2026.2.3, neuer geht unter Python 3.13 nicht). Keine Kindernamen,
PINs oder Schlüssel in diesem Dokument (D15/D68). Maßgeblicher Einstieg ist
[README.md](README.md) in diesem Ordner; Einzelheiten zu jedem Release
stehen im [CHANGELOG](../CHANGELOG.md), die Begründungen in
[ENTSCHEIDUNGEN.md](ENTSCHEIDUNGEN.md).

## Überarbeitung 26.09.2026 (1.34.0, D208)

- Vollständige Durchsicht des Codes, Befunde und Umsetzungsstand in [OPTIMIERUNG.md](OPTIMIERUNG.md). Umgesetzt in sechs Strängen: KI-Pipeline (Anspruch `analysis_claimed_at`, dauerhafte Versuchszähler, Abbildungen mit `attempts`), Kern (Migrationen je Schritt in einer Transaktion, `split_statements`; Sitzungen als sha256; `reconcile` über alle Tabellen mit `account_id`), Tagesablauf (`tasks.ha_description` als Abgleichschlüssel, Minutenschleife über alle Konten, `rewards.note_later`), Lernen (`topic_answers_void`, `mc.stable_version`, `mc.fit_context`, `schoolday.py`, `digital_textbook_misses`), Frontend (Lazy-Seiten, Kindwechsel mit `{#key}`, Update-Neuladen nur ohne Eingaben), HA-Komponente (`lessons.removed_at`, `absence_deletions`, Lehrstoff-Nachlauf, `backup.py`).
- Neu für Mehrfach-Schreibzugriffe: `db.tx(conn)`; `with conn:` allein ist bei `isolation_level=None` keine Transaktion.
- Offen: Vokabel-Wiederholung mit Abstand (D155, eigener Entwurf), Liste „Bewusst offen“ in OPTIMIERUNG.md. Nach dem HA-Neustart prüfen, ob `absence_deletions` leer bleibt oder nur echte Löschungen enthält und ob der Lehrstoff-Nachlauf die Stunden der letzten Tage füllt.
- Tests: 1023 Backend, 18 `tests_ha` (Python 3.13, `pytest-homeassistant-custom-component==0.13.316`), 13 Browser-Tests (`NODE_PATH=/opt/node22/lib/node_modules/playwright/node_modules SCHOOL_TEST_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome node tests/<name>_browser.cjs`), `npm test` im Frontend.

## UX-Überarbeitung 25.09.2026 (1.17.0 bis 1.21.0, D171 bis D177)

- 1.17.0 Tempo und Tokens, eine Lernstand-Farbskala; 1.18.0 Startseite nach Phasen (vor, in, nach der Schule), Ringe, Tasche als Kacheln, Selbsteintragen per Text; 1.19.0 Geräterollen (Mitlesen, Kind am Elterngerät, Testmodus) über die Kopfzeile `X-View-Mode` (`view_mode.py`); 1.20.0 Serie mit Retten, acht Abzeichen, Jahresmedaille (`rewards.py`, Seite „Ich“), Zählung ab 25.09.2026 (`reward_config.start_day`); 1.21.0 Gestaltung je Kind (`profile_prefs`).
- 1.22.0: Übungsarbeiten und Raster Thema × Anforderungsbereich (D178, `practice.py`, `routers/practice.py`, `PracticeRaster.svelte`), Wochenend-Regel (D179). 1.22.2: Fotorückgabe für alle Übungsklausuren. 1.23.0: täglicher Lernplan und vier Bereiche auf Heute (D180, `study_plan.py`), Vokabelpensum, Papier-Vokabeltest, zwölf Abzeichen (D181, `vocab_pensum.py`, `reward_extras.py`). Offen: Lesezugang für Kalibrierbericht (exam_topics, topic_answers, exam_dates), Hinweis „Lektion fehlt“ im Vokabelpensum, Kurztest-Nachweis themengenau, Tempo von `note_extra_vocab` messen.
- 1.23.2 Archiv nach der Arbeit (D182), 1.23.3 Vokabel-Leseauftrag repariert, Latein Lektion 2 als zweiter geprüfter Bestand (book_key latein-begleitband-lektion-2). 1.24.0 Eltern-Hülle (D183) und rollende Woche (D184). 1.24.1 Zuklappen auf Heute und Vokabeltests aus Hausaufgaben (D187). 1.25.0 Lernseite als Kompass (D186) und Lernplan ohne Deckel mit Puffer (D188). Offen: automatische Vokabelprüfung (D185, Agent), Prüfansicht für neue Vokabelseiten unter Erledigen, Familienkarte auf DayStrip umstellen, alter /week-Endpunkt entfernen.
- Offen: Abzeichen-Grenzen nach vier Wochen echter Nutzung prüfen (D173). „Vorbereitet“ wird nur beim Laden der Startseite des Kindes geprüft (`rewards.note_prepared` in `today.photo_requests`). Sonderabzeichen Klausurphase und Abitur sind beschrieben, aber nicht gebaut. Im Testmodus sind Tasche und Lernraum gesperrt (Demo-Sperre in `learning.access`), nur Aufgaben und Rückmeldungen werden zurückgenommen.
- Nächste Entwürfe laut Nutzer: Woche als Tagesliste, Arbeiten als Drei-Schritte-Karte, ruhigere Wörter auf der Elternkarte, Textdurchgang. Erinnerungen bleiben zurückgestellt. `tests/subjects_browser.cjs` schlug schon vor dieser Arbeit fehl.

## Was läuft

- Vokabeltrainer: Listen kommen seit 1.13.0 über einen geprüften
  Buchbestand, der Buch für Buch nach einer Quellenprüfung aktiviert wird
  (D152, D153). Bedeutungen prüft gpt-5-mini auf Foundry 2, richtige
  Antworten zählen unabhängig von der Dauer, Eltern können einzelne
  Versuche aus der Wertung nehmen (D154 bis D157). Fächer ohne aktiven
  Bestand laufen weiter über die Gliederung aus D139.
- Hausaufgabenhilfe und Kontrolle: abgelegte Seiten lassen sich einbinden,
  Chat-Fotos werden Material der Aufgabe, angekreuzte Seiten gehen beim
  Senden mit (D141 bis D144). Seit 1.13.16 dosiert eine Hilfeleiter die
  Hilfe (D150).
- Sicherheit: Das Dateileck über den Direktport ist seit 1.13.11
  geschlossen, die Ingress-Kopfzeile gilt seit 1.13.12 nur noch vom
  Supervisor (D146), die PIN-Sperre zählt seit 1.13.13 atomar und wächst
  (D147). Geheimnisse werden nach Nutzerentscheidung nicht getauscht (D148).
- Kosten: Ein Modellwechsel liest den Bestand nur noch neu, wenn das neue
  Modell stärker ist (D145). Seit 1.13.15 ist der Mentor-Kontext für das
  Prompt-Caching sortiert, Cache- und Denk-Token werden je Aufruf
  gespeichert (D149). Live stehen seit dem Ausfall der ersten Foundry
  alle Stufen auf gpt-5-mini (Foundry 2); Zielbild siehe D162.

## Repository seit 24.09.2026

Das öffentliche Repository wurde mit bereinigter Historie neu angelegt (keine Kindernamen, keine Schule, keine Adressen, keine Arbeits-E-Mail; D148, Thema 10 der Prüfung). Das alte liegt privat als `dvophuysen/ha-untis-archive-alt` und ist für diese Sessions nicht freigegeben. Add-on-Store und HACS laufen unter derselben Adresse weiter; HACS kennt das neue Repository, installiert ist v0.5.3; v0.5.4 (Datenbank im Executor, Recorder ohne große Listen, Neuanmeldung bei abgelehntem Passwort) braucht nach dem HACS-Update einen HA-Neustart, den der Nutzer macht. Tests der Komponente: `tests_ha/` mit pytest-homeassistant-custom-component unter Python 3.13. Nie wieder echte Namen, Adressen, Hostnamen oder Schulkennungen in Code, Tests, Kommentare oder Commit-Texte schreiben.

## Offen

- Kosten: Ab 01.10. die Token-Erfassung auswerten
  (`GET /api/accounts/{id}/learning/mentor` als Elternteil → `budget.tokens`),
  dann den Mentor-Kontext entschlacken (D149); Structured Output offen.
- Modelle (D162, ersetzt D160): Ziel sind **gpt-6-luna** für die Lese-
  und Vokabelstufen und **gpt-6-sol** für Mentor und sorgfältige Lesung,
  auf Dauer auf Foundry 2. Offen: Kontingentanträge auf Foundry 2 (Sweden
  Central, Global Standard, je 100) am 24.09. abgelehnt, auch für East US;
  Foundry 2 steht auf Kontingentstufe 0. Erst Nutzung aufbauen, ab 24.10.
  erneut beantragen, mit mehreren Regionen. Ab 28.09. (neues Guthaben
  auf Foundry 1) dort beide bereitstellen und gegen gpt-5-mini eichen,
  auch die Bildlesung; die App bleibt bis zur Bewilligung auf gpt-5-mini
  (Nutzerentscheidung „nur testen“). Preise stehen seit 1.13.20 in `RATES`.
  Der Router in Norway East (10 Einheiten, fest auf gpt-5.6-terra) ist nur
  Reserve. Plan B, falls der Antrag im Oktober wieder scheitert: die VMs
  samt Netz und die Speech-Gruppe aus dem Abo von Foundry 1 in das von
  Foundry 2 umziehen (n8n mit App Service und Zertifikat bleibt), dann
  trägt Foundry 1 (Stufe 1, gpt-6 verfügbar) die App; vorher Probelauf mit
  der Umzugsprüfung von Azure. Der Nutzer arbeitet mit Azure Cloud Shell; Befehle als Bash-Block
  geben, Schlüssel bleiben in Shell-Variablen.
- Azure-Zugang für die nächste Session: Der Nutzer legt eine App-Registrierung mit „Cognitive Services Contributor“ auf der Foundry-2-Ressource und „Cognitive Services Usages Reader“ auf dem Abonnement an und trägt `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_SUBSCRIPTION_ID` in die Claude-Umgebung ein. Dann: Token per Client-Credentials von login.microsoftonline.com holen (beide Hosts sind erreichbar, `az` ist nicht installiert), in management.azure.com Modelle und Kontingent der Ressource prüfen, Luna und Terra bereitstellen, mit `vocab/{fach}/compare` und `materials/{id}/analysis/compare` gegen gpt-5-mini eichen (D129: nie durch Umstellen und Neulesen), Kontingentantrag formulieren, Stufen in den Add-on-Optionen umstellen und `RATES` in `ai_gateway.py` um die gpt-5.6-Sätze prüfen. Nie Schlüssel ausgeben.
- Mentor: An den nächsten echten Gesprächen ansehen, ob die Hilfeleiter
  (D150) zu zäh wirkt; Übungseinheiten haben noch keine.
- Hausaufgabenhilfe: Beim nächsten echten Lauf ansehen, ob die Lesung der
  Chat-Fotos klappt und ob sie beim Üben auftauchen (D143), und an einer
  echten Kontrolle mit zwei, drei Heftseiten, ob der Mentor alle Seiten
  prüft und was ein Zug dann kostet (D141).
- Gegenlesen (D165, 1.13.28–1.13.30): Eltern sehen nur noch echte Zweifel;
  Lautschrift, Zeichensetzung und Eintragungen des Kindes zählen nicht,
  unscharfe oder abgeschnittene Fotos gehen als Bitte ans Kind („neu
  fotografieren“, ersetzt das alte Foto). Stand 24.09.: Kind B 0 zum
  Gegenlesen, 1 Foto-Bitte; Kind A 2. Nach einigen Tagen ansehen, ob neue
  Zweifel-Formulierungen durchrutschen (`review_doubts()`).
- KI-Kosten seit gpt-5-mini: rund 1,40 € am Tag angerechnet (September bis
  18.09. rund 10 € am Tag). Nachtlauf-Kontrolle am 25.09. vorgemerkt: wirkt
  D145, und sind Kind Bs zwölf nächtliche Vokabel-Aufrufe weg?
- Eltern: Startseite seit 1.14.0 als Karte je Kind mit Status, offenen
  Punkten, Arbeiten mit Lernstand-Balken und „Beobachten“; jeder Baustein
  springt zum Kind in den Abschnitt (D166). Mit dem Nutzer nach einigen
  Tagen prüfen, ob die Status-Regeln zu oft oder zu selten anschlagen.
  Der Nutzungsbericht (D159) speist nur noch die Wochennachricht (D161);
  späte Nutzung zählt nur auf der Anmeldung des Kindes, Mentor und
  Vokabeln speichern das angemeldete Konto erst ab 1.14.0.
- Seit 0.74 kein Release für Fachübersicht, Elternüberblick und
  Übungsklausuren.
- Zielbild Mentor (D126), Stufe 2: Lagebesprechung und Lagebild für die
  Eltern. Entwurf steht, Bau war vom Nutzer zurückgestellt.
- Auswahlaufgaben seit 1.13.27 (D164): an echten Gesprächen ansehen, ob der
  Mentor sie in den erlaubten Lagen nutzt und ob die Ablenker taugen.
  Offen aus früheren Sessions: der Prüfungs-Kapitelindex.
- Vokabeltrainer: Tages- und Wochenverlauf mit Elternübersicht ist in
  [docs/vocabulary-learning-quality.md](../../docs/vocabulary-learning-quality.md)
  verbindlich vorgemerkt, aber nicht gebaut; Grammatikmuster brauchen einen
  eigenen Lernmodus.
- Alter Vokabelweg (D139), nur noch für Fächer ohne aktiven Prüfbestand;
  zuerst live nachsehen, welche Fächer inzwischen einen haben. Stand
  19.09.: In Spanisch von Kind A trägt „Unidad 1 ¡Bienvenidos a mi
  barrio!“ 451 Wörter, weil der Laufkopf keine Marke nennt
  (`GET /learning/vocab/SPANISCH/outline` zeigt ohne Modellaufruf, was die
  Gliederung sieht), und „Lista cronológica“ gehört als eigener Anhangteil
  in `_OTHER_PART`. In Englisch von Kind A meldet S. 164/165 keine
  Überschrift, bei Kind B steht „Irregular verbs“ unter „Unit 1“ statt
  unter dem Grammatikanhang. Eine Korrekturschnittstelle für die
  Gliederung wäre billig: Einheit und Abschnitt einer Seite von Hand
  setzen, `regroup()` achtet die Festlegung wie `book_chapters.locked`.
  Nutzerentscheidung 24.09.: erst beobachten, noch nicht bauen (D164).
- Nachprüfen (Stand 19.09.): zwei Vokabelseiten scheiterten mit einem
  Lesefehler, einige Materialien standen nicht auf „ready“, und im
  Englischbuch von Kind A fehlten die gedruckten Seiten 186 bis 189.

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
- Tests `python3 -m pytest tests` (1023 grün), Frontend `npm run build` und `npm test`.
  Migrationen ans Ende von `_MIGRATIONS` in `db.py`.
- Messen statt schätzen. Eichungen laufen über `vocab/{fach}/compare` und
  `materials/{id}/analysis/compare`, beide speichern nichts. Ein Vergleich
  zweier Modellstufen darf nie über das Umstellen der Stufe und erneutes
  Einlesen laufen: Der Textstand enthält das Modell nicht, es käme der
  gespeicherte Stand zurück (D129).
- Der Nutzer entscheidet Grundsatzfragen, will Vorschläge mit Empfehlung und
  konsequentes Abarbeiten ohne Rückfragen bei allem anderen. Qualität steht weit
  vor Kosten.
- Während einer laufenden Lernsitzung nichts einspielen und nicht neu
  starten; Lernhistorie nie durch Testläufe verändern (D158).
