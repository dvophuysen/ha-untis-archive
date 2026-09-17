# Arbeitsblätter Stufe 2 und 3 0.87.0

Stand 17.09.2026. Umsetzung der offenen Stufen aus ARBEITSBLAETTER.md (D85),
Entscheidung D92.

**Gebaut.** `material_analysis._context()` hängt `hinweise.blatt_kandidaten`
an, sobald das Material an keiner Hausaufgabe hängt; `Insight.sheet_candidate`
und `sheet_reason` nehmen die Vorsortierung entgegen, `_apply()` legt sie als
`materials.sheet_hint` ab (Migration `materials_015_sheet_candidate`). Die
Instruktion verlangt einen Beleg vom Blatt und verbietet ausdrücklich, nach
Datumsnähe zu raten — das kann die App selbst. `routers/materials.py` sortiert
den Vorschlag nach oben und reicht den Grund mit.

`sources.sheet_label()` bildet die Kennung aus Fach, Tag und Titel, mit
`SUBJECT_SHORT` für die Fachkürzel und „ca." für ein geschätztes Datum.
`sources.sheet_for_task()` liefert das Blatt einer Hausaufgabe ausschließlich
über einen gesetzten Bezug. Der Mentor bekommt es als `arbeitsblatt` in den
Kontext; fehlt es, steht dort `vorhanden: false`, und die Instruktion gibt den
Wortlaut vor, statt ein fremdes Blatt anzunehmen.

**Tests.** Kennung in drei Varianten (aufgedrucktes Datum, geschätzter Tag,
Datum des Bezugs), und dass zwei Blätter desselben Fachs vom selben Tag ohne
Bezug nicht an die Hausaufgabe gebunden werden. 460 Tests grün, Frontend gebaut.

# Bestand einer Abfrage in der App 0.86.0

Stand 17.09.2026. Erste echte Abfrage beobachtet (D84), Befund umgesetzt (D91).

**Befund.** Konto 2, Englisch, 36 Züge, unregelmäßige Verben Seite 206. Der
Merkzettel im Feld `summary` stand am Ende auf einem Satz. Falsch waren in
Runde eins fall, feed, feel, fight, find und fit; die Sammelwiederholung nannte
fit, fly und forget. In Runde zwei gingen beat, become, bite und bring daneben
und wurden nie wiederholt. Kosten des Gesprächs: 1,69 $ Liste, dominiert von
Seitenbildern in jedem Zug.

**Gebaut.** `QuizItem` und `Reply.quiz` in `routers/mentor.py`;
`merge_quiz()` schreibt den Bestand fort statt ihn zu ersetzen, weil das Modell
nur die Items der laufenden Runde sieht; `open_items()` liefert, was offen ist.
Gespeichert in `mentor_sessions.quiz_json` (Migration
`mentor_sessions_004_quiz`), zurück in den Kontext als `abfrage.bestand` und
`abfrage.offen`, dazu in `view()` als `quiz`/`quiz_open` für die Oberfläche.
Die Instruktion verlangt nur noch die Änderung der Runde. `Mentor.svelte` zeigt
unter dem Gespräch, was zu wiederholen ist.

Buchseiten: `quiz_running` unterdrückt `homework_page_images`, sobald ein
Bestand steht und keine Aufgabe offen ist; der Kontext meldet dann
`textbook.status = im_bestand`, und die Instruktion verbietet, deswegen nach
einem Foto zu fragen.

**Tests.** Fortschreiben über mehrere Runden inklusive der Regel, dass
„richtig" einen Fehler nicht abschließt; Speichern und Zurückgeben über zwei
Züge; und dass der zweite Zug einer Abfrage ohne Seitenbild auskommt.
458 Tests grün, Frontend gebaut.

# Zwei Durchgänge beim Materiallesen 0.85.0

Stand 17.09.2026. Eichung im Auftrag des Nutzers, Qualität ausdrücklich weit
vor Kosten (D90).

**Messung.** Zehn echte Seiten, jede von allen drei Stufen neu gelesen, „hoch"
als Bezug für die Eigenstreuung des Modells. Gedruckter Buchtext 1,00/1,00/1,00
bei Text, Wörtern und Zahlen auf allen Stufen; gemischte Seiten 0,99.
Handschrift: Zahlen 1,00 auf „hoch" gegen 0,82 auf „mittel" und „niedrig".
Arbeitsheft: Textähnlichkeit 0,85 gegen 0,62 und 0,61, dazu 19 verlorene Zeilen.
Abbildungsseiten sind auf keiner Stufe reproduzierbar, auch „hoch" nicht (0,40
gegen sich selbst): Dort wird ein Bild frei beschrieben. Seitenart und
Handschrift-Erkennung stimmten siebenmal von sieben auf allen Stufen.
„mittel" war nirgends besser als „niedrig" und zweimal schlechter.

Zweite Runde auf drei technischen Seiten (Physik-Schaltplan, Mathe mit Graph
und Wertetabellen, Äquivalenzumformungen), Stufe und Reasoning-Tiefe gekreuzt:
Die Schaltplan-Topologie gaben alle fünf Läufe richtig wieder, Luna ausführlicher
als Sol. Die Wertetabelle verlor auf „hoch/low" reproduzierbar Werte (fehlend
2, 4, 4, 7, 12) und war erst auf „hoch/high" vollständig. Die Zuversicht lag
auch bei Verlusten bei 0,98 und taugt deshalb nicht als Auslöser.

**Gebaut.** `material_analysis.escalation(row, insight)` entscheidet nach
Seitenart, Handschrift-Flag, Materialart, Fach und Zahlendichte über einen
zweiten Durchgang; `read_material()` liest erst günstig, dann bei Bedarf
gründlich und gibt die Lesung samt benutzter Stufe zurück. `analyze()`
speichert nur die letzte Lesung, `_apply()` schreibt die tatsächlich benutzte
Stufe nach `analysis_model`, und `due()` erkennt beide Stufen als erledigt an —
sonst hätte der Nachtlauf jede günstig gelesene Seite endlos neu gelesen.

**Tests.** Eskalationsregeln je Fall, der zweite Durchgang als das Gespeicherte,
und die Fälligkeit nach günstiger Lesung. Zwei Test-Stubs mit fester Signatur
bekamen `**kw`, weil `extract()` jetzt eine Stufe durchreicht. 455 Tests grün.

# Richtwerte statt Sperren 0.84.0

Stand 17.09.2026. Nutzerentscheidung: keine harten Grenzen, dafür Kosten im
Blick und Warnung ab 60 € (D89). Grundlage ist die Messung aller 630 Aufrufe
des Septembers: 50,06 € gebucht, real rund 26 $ zum Listenpreis; laufender
Betrieb 1,75 $/Tag, davon 62 % Automatik ohne Kind, 34 % die Kinder selbst.

**Gebaut.** `ai_gateway.thresholds()` ersetzt die fünf `raise`-Pfade in
`reserve()` und liefert die Liste der überschrittenen Richtwerte; sie landet in
der neuen Spalte `mentor_ai_calls.over_budget` (Migration
`mentor_ai_calls_001_over_budget`) und als Warnung im Log. `release()` löst eine
Reservierung auf, `release_stale()` räumt Aufrufe weg, die nach einer Stunde
weder abgerechnet noch gescheitert sind; `effective_sum()` zählt freigegebene
mit null. `complete()` und `transcribe()` geben frei, wenn der Anbieter die
Anfrage nie angenommen hat (Status unter 500 oder keine Verbindung), und buchen
weiter bei Zeitüberschreitung und Serverfehlern. `projection()` rechnet den
Monat aus dem Schnitt der letzten sieben Tage hoch; `status()` liefert
`projected_eur`, `per_day_eur` und `over_budget`, und `warning` schlägt an der
Hochrechnung an statt am erreichten Betrag. `Mentor.svelte` zeigt Verbrauch,
Tagesschnitt und Hochrechnung und nennt die Rahmen ausdrücklich als Richtwerte.

**Nicht gebaut, bewusst.** Keine Notbremse: vom Nutzer abgelehnt. Keine
Umstellung auf Dollar und keine Umrechnung alter Datensätze: als unnötige
Verkomplizierung verworfen, der Aufschlag bleibt und warnt früh.

**Tests.** `tests/test_ai_endpoints.py` um Freigabe, Stundenregel und
Hochrechnung erweitert; drei Tests, die das alte Sperrverhalten festschrieben,
prüfen jetzt den Vermerk statt des Fehlers. 452 Tests grün, Frontend gebaut.

# KI-Plattformen und Modellstufen 0.83.0

Stand 17.09.2026. Nutzerentwurf einer zentralen KI-Konfiguration (D88); löst
die Namensliste aus 0.82 ab, die an der Anforderung vorbeiging.

**Gebaut.** `config.yaml`: Block `ki_plattformen` (foundry_1, foundry_2 mit
`endpunkt`/`api_key`) und `ki_modelle` (hoch, mittel, niedrig, transkription mit
`modellname`, `bereitstellungsname`, `foundry` als `list(1|2)`, `preis_eingang`,
`preis_ausgang`). Alle `learning_ai_*` entfernt. `run.sh` liest beide Blöcke mit
`jq` aus `/data/options.json` und reicht sie als kompaktes JSON weiter, statt
sich auf die Ausgabeform von bashio zu verlassen.

`backend/learning.py`: `ai_platforms()`, `ai_tiers()`, `ai_settings(stufe)` mit
`AiEndpointMissing`/`AiTierUnknown`, `ai_status()` über die Stufe „hoch".
`ai_gateway.py`: `tier_for(purpose)` statt `model_for`, `settings_for()`,
`rate_for()` (Konfiguration vor Tabelle, halber Satz zählt nicht),
`model_name()` für Kennungen ohne Zugangsprüfung, `reserve()` nimmt die
aufgelöste Stufe, `complete()` schickt den Bereitstellungsnamen und bucht auf
den Modellnamen, `transcribe_url()`/`transcribe()` über die Stufe
„transkription", `status()` liefert Stufen mit Modell, Sätzen und Foundry,
`endpoint_overview()` die Startzeile.

Aufrufer: `routers/mentor.py` (Elternwahl prüft Stufen, `open_unit(tier=)`,
Eichungsvergleich über Stufen, Qualitätskennung über `model_name()`),
`material_analysis.py` (`extract(tier=)`, `analysis_model` und `due()` über die
Stufe der Auswertung statt fest über das Hauptmodell), `routers/materials.py`
(`CompareIn.tier`), `routers/discovery.py`, `exam_scope.py`.
`Mentor.svelte`: die beiden Auswahlfelder heißen „Stufe für …" und bieten
Hoch/Mittel/Niedrig mit Modellnamen und Satz. Migration
`mentor_ai_config_003_tiers` übersetzt gespeicherte Modellnamen in Stufen.

**Preise.** Die hinterlegten Sätze stehen jetzt begründet auf dem
veröffentlichten Listenpreis für Standard Global (Sol 5/30, Terra 2/12, Luna
0,20/1,20 USD je Mio.) mit Faktor 2 auf den Eingang und 1,5 auf den Ausgang.
Datenzonenstandard veröffentlicht Microsoft nicht; der Aufschlag deckt ihn mit
ab. Luna stand mit 1,90/9,00 € rund neunfach zu hoch und ist auf 0,40/1,80 €
berichtigt; das Modell war nicht im Einsatz, die bisherige Abrechnung bleibt
unberührt.

**Nachtrag 0.83.1.** `transcribe_url()` lief über `settings_for()` und warf
damit 503, wenn die Stufe „transkription" keinen Zugang hat. Vier Übersichten
(Mentor-Dashboard, Vokabelansichten) benutzen den Rückgabewert aber nur als
Ja/Nein, ob ein Mikrofon angeboten wird, und gaben deshalb selbst 503 zurück:
Die Mentor-Übersicht war offline, bis die Plattform eingetragen war. Lesende
Pfade sind jetzt nachsichtig, nur der wirkliche Aufruf bricht ab. Test:
`test_the_views_still_render_without_any_foundry`.

**Tests.** `tests/test_ai_endpoints.py` (Stufe nennt Modell, Bereitstellung und
Foundry; kein Rückfall; Zug ruft die Bereitstellung auf der eigenen Ressource
und bucht auf den Modellnamen; gemischte API-Formen; Satz aus der Konfiguration
vor der Tabelle, halber Satz zählt nicht, ohne Satz kein Aufruf; Elternwahl
übersteht einen Modellwechsel; Startzeile; eine Foundry allein; Migration),
`tests/test_addon_config.py` um verschachtelte Optionen erweitert, Fixture
`ai_env()` in `tests/test_learning.py` für alle Tests mit KI. 447 Tests grün,
Frontend gebaut.

# Zwei Foundry-Zugänge nebeneinander 0.82.0

Stand 17.09.2026. Nutzerauftrag: Modelle schrittweise auf eine andere Foundry
übertragen, solange beide parallel laufen (D87). Steuerung in der
App-Konfiguration; die Oberfläche bleibt unberührt.

**Gebaut.** `config.yaml` und `run.sh` um `learning_ai_url_2`,
`learning_ai_key_2` und `learning_ai_models_2` (`list(str)`) erweitert. In
`backend/learning.py`: `deployment_names()` liest die Liste in jeder Form, die
bashio durchreicht (JSON ein- oder mehrzeilig, Komma-Text, `null`), `ai_settings()` liefert `url_2`, `key_2`
und `models_2`, `ai_endpoint(model)` entscheidet je Deployment-Name über den
Zugang und wirft `AiEndpointMissing`, wenn der zweite unvollständig ist;
`ai_status()` meldet den Host, der das Hauptmodell bedient. In
`ai_gateway.py`: `endpoint_for()` macht daraus eine 503-Meldung mit
Modellnamen, `complete()` baut Nutzlast, API-Erkennung, Adresse und
`api-key`-Header aus dem aufgelösten Zugang, `transcribe_url()` und
`transcribe()` folgen dem Zugang des Transkriptions-Deployments,
`endpoint_overview()` liefert die Startzeile (inklusive `sources_model` und
`opening_model` aus `mentor_ai_config`, ohne Schlüssel und ohne Pfad).
`main.py` loggt sie beim Start. Die Vorprüfung in `routers/discovery.py`
prüft jetzt den Zugang des Hintergrundmodells statt fest den ersten.

**Nicht gebaut, absichtlich.** Keine Zuordnung in der Elternansicht, keine
Spalte in `mentor_ai_config`, keine Änderung an `RATES` (Deployment-Namen
bleiben gleich). Unterschiedliche API-Formen je Zugang funktionieren, weil
die Art am Pfad erkannt wird; das ist Nebenwirkung, nicht Ziel.

**Nachtrag 0.82.1.** `learning_ai_models_2` stand als `list(str)?` im Schema.
`list(...)` ist in Home Assistant die Auswahl aus festen Werten; eine Liste
wird als YAML-Liste geschrieben. Der Supervisor lehnte die Optionen ab und das
Add-on blieb nach dem Update gestoppt. Die Fehlermeldung schrieb dabei alle
Optionen im Klartext ins Supervisor-Log, den Azure-Schlüssel eingeschlossen;
der Nutzer wurde auf den Tausch hingewiesen. `tests/test_addon_config.py`
prüft jetzt Optionen gegen Schema.

**Tests.** `tests/test_ai_endpoints.py`: Namensliste aus Zeilen und Kommas
inklusive bashio-`null`, Zuordnung je Deployment, Fail-Closed ohne Rückfall,
Zug mit dem Schlüssel der aufgerufenen Ressource vor und nach dem Umzug des
Hauptmodells, gemischte API-Formen, Transkriptionsadresse und -schlüssel am
eigenen Deployment, `ai_status()` und Startzeile, unveränderter Betrieb mit
einem einzigen Zugang. 441 Tests grün.

# Arbeitsblätter mit Bezug, Stufe 1 0.81.0

Stand 17.09.2026. Nutzerentscheidung zu ARBEITSBLAETTER.md (D85) und zwei
Rückmeldungen (Doppelseite von Hand, Begriffe D86).

**Gebaut.** `material_links.relation` (Migration), `materials.link(...,
relation)` mit Upsert; `LINK_KINDS` um `homework`. `sources.is_sheet_link`,
`_sheet_photos` bindet nur über Aufgabe, Hausaufgabe oder Stunde mit Rolle
blatt oder Blatt-Materialart; `refresh_status` ohne `_sheet_near`;
`sheet_candidates` (gleiches Fach, Seite 0, paper, ±14 Tage, drei nächste);
Ledger führt Seite 0 je Eintrag mit `entry_kind`/`entry_id`. Router: Listing
hängt `sheet_candidates` an lose Blätter, `LinkIn.relation`, Upload nimmt
`homework_id` und beansprucht Seite 0 nicht mehr je Fach, `MaterialPatch.printed_pages`
mit Sperre (auch in `_apply`). Frontend: Vorschläge unter der Materialzeile,
„Vorhandenes Blatt zuordnen“ je Eintrag in der Quellenbilanz, Foto von dort
mit Eintragsbezug, Feld „Gedruckte Seite(n)“, Begriffe.

**Geprüft.** Blattbindung über Aufgabe, Stunde, Hausaufgabe und Rolle; lose
Mitschrift zählt nicht; Nähe bindet nicht, Vorschlag richtig sortiert, Tipp
bindet; Ledger je Eintrag; Doppelseite per Korrektur gesperrt gegen Lesung.

**Live geprüft (0.81.0 eingespielt).** Fehlbindung an „Arbeitsblatt
beenden“ weg, Doppelseite 10/11 gesetzt und gesperrt, Autor-Migration
gelaufen, Verlaufsliste mit Wortlaut. Log ohne Fehler.

**Offen.** Stufe 2 (Kandidaten beim Einwerfen, Kennung „AB Mathe 26.08.
Lückentext“ in Listen), Stufe 3 (Mentor bittet um Foto statt fremdes Blatt).
Übergabe an die nächste Session: [UEBERGABE.md](UEBERGABE.md).

---

# Blattbindung und Abfragen 0.80.0

Stand 17.09.2026. Nutzerrückmeldung (Fehlbindung) und die drei Vorschläge aus
der Bewertung des Verben-Gesprächs.

**Gebaut (D83).** `sources._sheet_photos`: `SHEET_KINDS = (worksheet, handout)`;
nur diese Arten kommen in den losen Vorrat und belegen über eine Aufgabenverknüpfung
ihre Hausaufgabe; an eine Aufgabe gehängte Fotos werden aus dem losen Vorrat
ausgeschlossen. `refresh_status` setzt die betroffene Stelle beim nächsten Lauf
zurück auf „paper“.

**Gebaut (D84).** `HOMEWORK_INSTRUCTION` um drei Absätze: Abfragen, Merkzettel,
Bestand nur von der Seite. `Reply.summary` bis 2000 Zeichen. Der Kontext trug
`summary` schon jede Runde mit; neu ist, dass die Instruktion es als Merkzettel
nutzt.

**Geprüft.** Test: Ausarbeitung an alter Aufgabe belegt nichts, Blatt an
derselben Aufgabe belegt nur deren Hausaufgabe, loses Blatt der Nachbartage
zählt, lose Mitschrift nicht. Mentor-Tests unverändert grün.

**Nachtrag 0.80.1.** Die Ausarbeitung war als notes eingeordnet; own_work heißt
in der Oberfläche jetzt „Erledigte Hausaufgabe (eigene Bearbeitung)“, die
Auswertung bekommt `hinweise.gehoert_zu_hausaufgabe.auftrag` und die Regel:
handschriftlich und an eine Hausaufgabe gehängt heißt own_work, nicht notes.
Das betroffene Material wurde live von Hand berichtigt.

**Offen.** Nächste echte Abfrage beobachten: Merkzettel-Inhalt, Wiederholung
der Fehler, Ende. Danach die Kostenoption (Seiten nicht je Zug) entscheiden.

---

# Verläufe des Kindes 0.79.0

Stand 17.09.2026. Nutzerrückmeldung: Gespräche auf dem Elterngerät standen als
„Eltern“ im Verlauf; die Verlaufsliste nannte nur „Hilfe: Englisch“.

**Gebaut (D82).** `author_of(user, session)` schreibt „kind“, außer im
Demo-Modus; Migration `mentor_message_author_002` stellt bestehende echte
Verläufe um. `session_label` (Wortlaut der Hausaufgabe aus `sources.task_text`,
bei Kontrolle mit Präfix, sonst Ziel) und `last_at` in Dashboard und Detail;
Nachrichtenzahl in der Liste; Sortierung nach letztem Dialog; neue
Hausaufgaben-Einheiten tragen den Wortlaut auch im Ziel. `Mentor.svelte`:
eine Liste mit Art, Stand, letztem Dialog und Zahl, abgehakte Hausaufgaben
darin statt eingeklappt; Kopf des Gesprächs mit Wortlaut und letztem Dialog.

**Geprüft.** Autor „kind“ für Eltern im echten Verlauf, „eltern“ im Demo;
Wortlaut und letzter Dialog in Liste und Detail.

**Offen.** Bewertung des Abfrage-Gesprächs (unregelmäßige Verben) mit
Vorschlägen an die Instruktion liegt beim Nutzer zur Entscheidung.

---

# Kontrollieren und „So korrigieren“ 0.78.0

Stand 17.09.2026. MENTOR_EINSTIEG Schritt 4 und die offene Bedienfrage aus 0.77.0.

**Gebaut (D80).** `routers/mentor.py`: `StartIn.check` mit `homework_task_id`
eröffnet den Modus `homework_check` (eigener Verlauf je Hausaufgabe, der
reichste gewinnt, wie bei der Hilfe); feste Begrüßung ohne Modellaufruf,
`situation` kontrollieren/„Lösung prüfen“ in der Quelle; `CHECK_INSTRUCTION`
(Urteil je Aufgabe, kein Ergebnis, keine Zählung, Ende als Vorschlag);
`HOMEWORK_MODES` für Uhr, Zuggrenze, Wiederaufnahme, Ablage nach dem Haken;
Buchseiten der Aufgabe immer beigefügt; Aufgabe und Einschätzung der Antwort
werden verworfen; Ende-Frage „Noch eine Seite zeigen“. `learning_plan` zählt
den Modus wie die Hilfe nicht auf den Tagesplan. `mentor_opening.LAGEN` und
`situation` kennen die Lage. `TaskDetail.svelte`: „Lösung prüfen lassen“ →
`#/learning?check=<id>`; `Mentor.svelte` startet den Modus, zeigt den Hinweis
und macht „Foto der Lösung“ zum Hauptknopf, solange kein Foto da ist.

**Gebaut (D81).** `notice_check.check` nummeriert die Seitenangabe (`span`);
`replace_pages` ersetzt in einem Durchgang über den ursprünglichen Text nur
die Seiten der passenden Angabe. Route `POST …/materials/{id}/plausibility/apply`
mit `fixes[]`, Korrektur der Eltern (Sperre), danach `after_analysis`.
`Materialien.svelte`: ein Knopf je Angabe, „So korrigieren: Textband S. 10, 11“.

**Geprüft.** Kontrolle: eigener Verlauf neben der Hilfe, Instruktion,
Aufgabentext im Kontext, keine Evidenz, kein Verbrauch, Ende als Vorschlag mit
den Kontroll-Antworten, „Für heute fertig“ schließt. Übernahme: nur Seiten der
Angabe, Lektions- und Aufgabennummern bleiben, falscher Buchteil ändert nichts,
Route sperrt das Textfeld und ruft die Nachbereitung, zweiter Tipp 409.
Gesamt 70 Tests in den betroffenen Dateien grün, Frontend gebaut.

**Offen.** Erste echte Kontrolle am Foto eines Kindes beobachten (Lesbarkeit
der Handschrift, Urteilsqualität) und die Instruktion daran nachschärfen. Ein
Foto ohne Frage im Hilfegespräch als Auslöser der Kontrolle (Konzept) ist
nicht gebaut. Schritt 5 (Verfassung) offen.

---

# Gegenlesen mit Kontext 0.77.0

Stand 17.09.2026. Folge aus D78: Handschrift ist ein Kontextproblem.

**Gebaut (D79).** `notice_check.py`: `taught_places` sammelt aus den Stunden-
und Hausaufgabentexten des Schuljahrs (`sources.mentions`, nur lesson und
homework, gleiches Fach) je Buchteil die genannten Seiten; `check` hält jede
Stelle des Zettels dagegen (`sources.serves` für die Buchteil-Verträglichkeit)
und schlägt bei unbekannten Seiten eine Ziffernverwechslung vor, die auf eine
bekannte Stelle führt (einzelne Ziffer oder alle verwechselbaren Ziffern:
77 → 11). `routers/materials.index` hängt das Ergebnis als `plausibility` an
Einträge zum Gegenlesen, die Themenliste oder Handschrift sind; die Liste
liefert dafür `page_type`, `handwritten` und den Text ungeprüfter Zettel.
`Materialien.svelte` zeigt die Zweifel rot mit Vorschlag, sonst „Alle
Stellen kommen so im Unterricht vor“.

**Geprüft.** Vier Tests: Stellen je Buchteil, Verwechslungsvarianten, der
falsch gelesene Zettel der Eichung (alle fünf 7er-Seiten mit dem richtigen
Vorschlag, die richtige Lesung ohne Beanstandung, ohne Unterricht keine
Behauptung), Route hängt die Prüfung nur an Zettel und Handschrift.

**Offen.** Live am nächsten echten Zettel beobachten. Ob der Vorschlag mit
einem Tipp übernommen werden kann („So korrigieren“) statt über das
Formular, ist eine Bedienfrage für später.

---

# Eichung der Reasoning-Tiefe, dritter Durchgang (0.76.0 live)

Stand 17.09.2026, spät. Hauptmodell mit „medium“ gegen „low“ an fünf Seiten,
gemessen mit dem neuen Werkzeug (Wörter, Zahlen, Zeilen). Kosten 1,08 €.

| Seite | Tiefe | Seitenart erkannt | Zahlen | Befund |
|---|---|---|---|---|
| Themenblatt Latein, handschriftlich | low | handwriting, Handschrift ja | 0,27 | „S. 70, 71“ statt 10, 11; „TB S. 70, 71, 74, 75“ statt 10, 11, 14, 15; „BB S. 17“ statt 14 |
| dito | medium | handwriting | 0,36 | „S. 70, 71“ und „TB S. 70, 71, 74, 75“ falsch; BB 13, 13–15, 14 richtig |
| Mathe-Arbeitsblatt | low / medium | formula, Handschrift ja (Kreise) | 1,00 / 1,00 | alle 16 Gleichungen gleich; nur die durchgestrichene r) abweichend |
| Physik-Schaltpläne | low / medium | mixed | 1,00 | alle Schaltungen richtig, nur Wortwahl der Beschreibungen anders |
| Latein-Arbeitsheft S. 7 | low / medium | mixed, Handschrift ja | 1,00 | gleich; Buchstabenfolge im Staub einmal mit Makra |
| Wimmelbild zur Antike | low / medium | figure | 1,00 | Beschreibung gleichwertig, andere Worte |

**Befund 1: Die gespeicherte richtige Lesung des Themenblatts war eine
menschliche Korrektur.** `content_text` ist gesperrt, `verified=1`,
korrigiert am 16.09. um 11:22. Kein Modell, in keiner Tiefe, liest die
handschriftliche 1 dieses Kindes als 1; alle lesen 7. Das Gegenlesen (D51)
hat den Fehler abgefangen. Ohne Gegenlesen hätte die App Kapitel 7 statt
Kapitel 1 als Klausurstoff geholt.

**Befund 2: „medium“ bringt an diesen fünf Seiten nichts Messbares** und
kostet 10 bis 50 Prozent mehr. Die Tiefe bleibt im Betrieb „low“ (D78).

**Befund 3: Seitenart und Handschrift werden erkannt**, auch handschriftliche
Kreise auf einem gedruckten Arbeitsblatt. Damit landen solche Seiten ab
0.76.0 zum Gegenlesen; ob das bei Arbeitsblättern mit bloßen Markierungen zu
oft ist, zeigt der Alltag.

**Schluss.** Handschrift ist kein Modell- und kein Tiefenproblem, sondern ein
Kontextproblem: Die 1 dieses Kindes sieht wie eine 7 aus, und nur der
Zusammenhang (erste Arbeit, Lektion 1, Unterricht nennt S. 10 bis 15)
entscheidet. Nächster Schritt (Vorschlag): Plausibilitätsprüfung
handschriftlicher Themenlisten gegen die Stellen, die Unterricht und
Hausaufgaben desselben Fachs seit der letzten Arbeit nennen, mit Hinweis in
der Gegenlese-Karte („S. 70, 71 kommen im Unterricht nicht vor; gemeint
S. 10, 11?“).

---

# Messwerkzeug und Handschrift 0.76.0

Stand 17.09.2026. Folge der zweiten Eichung (0.75.1): Die Wortabdeckung war
blind für Ziffern und Zeilen, Handschrift wurde nur über den Vertrauenswert
zum Gegenlesen geschickt, die Reasoning-Tiefe war nicht messbar.

**Gebaut (D77).** `material_analysis.compare_texts`: Wortabdeckung wie bisher,
dazu Zahlen als Vielfachmenge (`number_recall`, `missing_numbers`,
`extra_numbers`), Zeilen nur in der einen oder anderen Lesung (`only_stored`,
`only_read`), Formelzeilen; `compare` gibt die volle Lesung zurück und nimmt
`effort` an. `Insight.page_type` (text, table, handwriting, figure, formula,
mixed) und `Insight.handwritten`, in der Instruktion mit dem Hinweis auf 1/7
und 0/6; `_apply` speichert beides (Migration `materials_014_page_type`).
`materials.needs_review`: Handschrift immer. `ai_gateway.complete(effort=…)`
mit Voreinstellung low; nur die Eichung nutzt es. `ANALYSIS_VERSION` bleibt 3:
ein Nachlesen aller 144 Materialien für die Seitenart kostete rund 14 €, die
Seitenart füllt sich mit jeder neuen Lesung.

**Geprüft.** Zwei Tests: Ziffern- und Zeilenfehler werden gemessen, wo die
Wortabdeckung 0,8 meldet; Handschrift geht bei Vertrauen 0,97 zum Gegenlesen,
Gedrucktes nicht. 155 Tests der betroffenen Module grün.

**Nächste Messung (mit Ok des Nutzers).** Hauptmodell mit medium gegen low an
fünf Seiten (Themenblatt handschriftlich, Mathe-Arbeitsblatt, Physik-
Schaltpläne, Arbeitsheft mit handschriftlichen Einträgen, Wimmelbild), rund
1 €. Braucht die Instanz auf 0.76.0.

---

# Eichung der Lesemodelle, zweiter Durchgang 0.75.1

Stand 17.09.2026. Nutzerauftrag: sorgfältig an echten Seiten eichen, Qualität
vor Kosten, Kosten nicht unnötig. Zwölf gespeicherte Seiten wurden mit dem
mittleren (terra) und dem kleinen Modell (luna) neu gelesen und gegen die
gespeicherte Lesung des Hauptmodells (sol) gehalten, dazu vier Originalbilder
selbst angesehen. Kosten der Messung 0,74 €, nichts gespeichert.

**Befunde.**

- Handschrift (Themenblatt zur Lateinarbeit): sol richtig (S. 10, 11; BB 13;
  13–15; 14; TB 10, 11, 14, 15), von den Eltern gegengelesen. terra las jede
  handschriftliche 1 als 7 (S. 70, 77; BB 73; 73–75; 74). luna traf 13, 13–15
  und 14, aber zweimal 70/71 statt 10/11. Beide günstigen Modelle sind für
  Handschrift unbrauchbar; ein falscher Zettel würde das falsche Kapitel holen.
- Mathematik-Arbeitsblatt (Gleichungen mit Klammern): sol richtig (am Bild
  geprüft). terra drei Fehler in sechzehn Gleichungen (d: „= 4“ statt „= 0“,
  k: „3x“ statt „3x − 5“, l: „5(x − 4)“ statt „6(5x − 4)“). luna in den
  geprüften Zeilen richtig. Die Wortabdeckung (0,94) sieht solche Fehler nicht,
  weil Ziffern anderswo auf der Seite vorkommen.
- Physik-Arbeitsblatt mit Schaltplänen: sol beschreibt alle sechs Schaltungen
  richtig (am Bild geprüft). terra und luna beschreiben A2 ebenfalls richtig;
  der Rest der Lesungen liegt nur gekürzt vor (Werkzeuggrenze).
- Lernwörter (Begleitband S. 10): terra verlor „venīre“, ein Lernwort; luna
  vollständig. Grammatik S. 13: terra verlor „masculinum“; luna vollständig.
- Tabelle unregelmäßiger Verben: terra vollständig, luna verlor die
  Lautschrift.
- Fließtext (Deutsch-Doppelseite, Politik, Spanisch): beide 0,90 bis 0,97;
  die fehlenden Wörter sind Bildbeschreibungen, kein Inhalt.

**Schluss (D75).** Das Abschreiben bleibt beim Hauptmodell. Jedes günstigere
Modell hat auf mindestens einer Seitenart inhaltlich tragende Fehler: Ziffern,
Lernwörter, Handschrift. Ein Umstieg je Seitenart ist erst vertretbar, wenn
das Messwerkzeug Ziffern und Zeilen vergleicht (offen, siehe unten).

**Fehler gefunden und behoben.** Textband S. 10/11 (der Lektionstext der
ersten Lateinarbeit) stand seit 15.09. als „gelesen“ mit leerem Text und
leerer Kurzbeschreibung da, Vertrauen 0,98. Ursache: Das Korrekturformular
schickte alle Felder mit, auch den damals noch leeren Text; `routers/
materials.correct` sperrte jedes gesendete Feld, und `material_analysis._apply`
durfte den Text danach nie füllen. Beide günstigen Modelle lasen die Seite
fehlerfrei (2.400 Zeichen). Behoben in 0.75.1: leere Textfelder sind keine
Korrektur, das Formular schickt nur Geändertes, Migration
`materials_013_unlock_empty_text` gibt Text und Kurzbeschreibung frei und
setzt betroffene Materialien auf `pending` (Nachtlauf liest sie). Von 144
gelesenen Materialien war genau dieses eine betroffen. Zwei Tests.

**Offen für das Messwerkzeug.** `material_analysis.compare` liefert nur 600
Zeichen Lesung und misst Wörter, nicht Ziffern oder Zeilen. Vorschlag: volle
Lesung zurückgeben, Zeilenvergleich für Formelseiten, Ziffernfolgen
vergleichen, Seitenart aus dem Bild bestimmen. Reasoning-Tiefe ist heute für
alle Aufrufe „low“ (`ai_gateway.complete`); ob „medium“ Handschrift beim
Hauptmodell verbessert, ist ungemessen.

---

# Ende als Vorschlag, Verstehen als Einstieg 0.75.0

Stand 17.09.2026. Nutzerwunsch vom 16.09.: Der Mentor soll eine Sitzung nie
abbrechen, sondern höchstens vorschlagen, ob das Kind beenden oder
weitermachen will. Dazu Schritt 2 aus MENTOR_EINSTIEG.md.

**Gebaut (D73).** `routers/mentor.turn`: Nur `kind=finish` beendet. Zeit-
und Zuggrenze (12 Züge oder `max_minutes` bei Übung, `MAX_TURNS` bei Themen)
erzeugen ohne Modellaufruf die Frage `CAP_TEXT` mit den Antworten „Für heute
fertig“ und „Noch weitermachen“ (Themen: „Noch eine Aufgabe“); die Aufgabe
bleibt stehen. Erneut gefragt wird frühestens nach `PROPOSE_EVERY` (6)
weiteren Zügen (`mentor_sessions.end_proposed_turn`, Migration
`mentor_end_proposal_001`). Das `action finish` des Modells setzt die Einheit
nicht mehr auf `completed`: Nachricht plus Stufensatz (Themen) plus Satz zur
nachgeholten Stunde (Nachholen) plus Frage, Aufgabe geleert, Einheit offen.
`CONTINUE_RULE` sagt dem Modell, dass finish ein Vorschlag ist und „Noch
weitermachen“ eine neue Aufgabe verlangt. Hausaufgabenhilfe war schon ohne
Grenze. Die Budgetgrenze je Einheit (`SESSION_MICRO`) bleibt als einzige
harte Grenze; sie meldet sich als Fehler, nicht als Abschluss.

**Gebaut (D74).** „Mit dem Mentor verstehen“ an jeder beendeten Stunde mit
Rückmeldung 1 oder 2 (`LessonCard.svelte`, `LessonDetail.svelte`), derselbe
Weg wie beim Nachholen (`#/learning?lesson_id=…`); `situation` erkennt aus
der Rückmeldung die Lage „erklaeren“ (seit 0.69.0).

**Geprüft.** Tests angepasst und ergänzt: Grenze fragt statt zu beenden,
ohne Modellaufruf, erneut nach sechs Zügen; finish des Modells als Vorschlag
mit Antworten, danach „Noch weitermachen“ mit neuer Aufgabe; Themen-Einheit
bei „sitzt“ mit Stufensatz und Frage; Nachhol-Einheit setzt die Stunde beim
Vorschlag auf nachgeholt und bleibt offen. 143 Mentor-Tests grün,
Frontend-Build bestanden.

**Offen.** Live-Prüfung der Wortwahl mit den Kindern. Schritte 4 und 5 aus
MENTOR_EINSTIEG.md (Kontrollieren mit Foto, Verfassung).

---

# Wochenrückblick 0.74.0

Stand 16.09.2026, abends. Fünftes und letztes Paket der Reihenfolge aus D67;
Masterplan Abschnitt 10 („knappe Wochenübersicht mit wenigen Aussagen“).

**Gebaut (D72).** `week_review.review`: Montag bis Sonntag der laufenden
Woche; Abende vor einem Schultag aus `day_close.reliability` (aktuell und
Vorwoche), Stufenwechsel aus `topic_events` (auf/ab nach `PROGRESS`),
bestandene Kurzprüfungen (Wechsel auf gefestigt), abgeschlossene
Mentor-Einheiten ohne Test und Demo mit Minuten und Fächern,
Vokabelabfragen, erledigte Aufgaben der Woche und überfällige jetzt,
Antworten nach der Schule (`afternoon_checks`), fehlendes Material für
Arbeiten in 14 Tagen (`sources.photo_requests`), Arbeiten mit vorhandenem
Material, KI-Kosten des Kontos in der Woche (abgerechnet plus reserviert).
Daraus deterministische Sätze (`lines`) und die Rohzahlen. Route
`GET /accounts/{id}/week-review`. `WeekReview.svelte` in der
Elternübersicht je Kind unter dem Tagescheck, drei Zeilen, aufklappbar.

**Geprüft.** Drei Tests (`test_week_review.py`): Zahlen und Sätze einer
gefüllten Woche (Vorwoche, Demo und anderes Konto zählen nicht), die leere
Woche ohne erfundene Aussagen, Route mit Kontogrenze. Frontend-Build
bestanden.

**Offen.** Der vierwöchige Familienversuch aus Masterplan Abschnitt 10 kann
jetzt beginnen; die Ausgangslage ist der erste Rückblick. Ob die Kinder
ihren eigenen Rückblick sehen sollen, ist offen (die Route erlaubt es, die
Kinderansicht zeigt ihn nicht). Die Verlässlichkeitszahl (D34) ist damit
den Eltern sichtbar; ob und wie sie den Kindern gezeigt wird, bleibt zu
verabreden.

---

# Fächerübersicht auf dem Lernstand 0.73.0

Stand 16.09.2026, abends. Viertes Paket der Reihenfolge aus D67; löst die
offene Datenbedeutung aus FAECHERUEBERSICHT.md.

**Gebaut (D71).** `lernstand.subject_overview`: je Fach die Verteilung der
Stufen über die nicht veralteten Themen der offiziellen Themenlisten seit
Schuljahresbeginn (1. August), Vokabel-Themen ohne Mentor-Antworten mit der
Stufe aus den Wörtern, die Stufenwechsel der letzten vier Wochen aus
`topic_events` als auf/ab gezählt (`PROGRESS`-Reihenfolge neu < angefangen <
wackelt < sitzt < gefestigt) mit Kennzeichen aufwärts, abwärts, stabil oder
kein Verlauf. Sortierung: Anteil sicherer Themen, dann weniger Wackler, dann
Name. Route `GET /accounts/{id}/subjects/stages`; die Fachliste trägt
zusätzlich `key` zum Zusammenführen. `Subjects.svelte`: Balken aus den fünf
Stufen mit Klartext darunter, Trendtext rechts, Selbsteinschätzung als
Rückfall für Fächer ohne Themenliste (so beschriftet), aufgeklappt die
Themen mit Stufe, Grund, Gefühl, Üben/Prüfen und Weg zur Arbeit.

**Geprüft.** `test_subject_overview_counts_stages_and_stage_changes_per_subject`:
Zählung je Fach, Ausschluss von Vorjahr und veralteten Themen, Trend nur aus
dem Zeitfenster, Reihenfolge Wackler zuerst, „kein Verlauf“ ohne Wechsel,
Route für Kind und Eltern mit Kontogrenze. Frontend-Build bestanden.

**Offen.** Live-Abnahme auf 320/390/430 px und im Dunkelmodus
(Abnahmeliste in FAECHERUEBERSICHT.md). Elternstartseite bleibt
Folgeentscheidung. Fächer ohne Themenliste (kein Klausurtermin) haben keinen
gemessenen Stand; ob Übungsthemen aus dem Unterricht (learning_topics)
später mitzählen, ist offen.

---

# Nachholen als Lage 0.72.0

Stand 16.09.2026, abends. Drittes Paket der Reihenfolge aus D67; Schritt 3
aus MENTOR_EINSTIEG.md.

**Gebaut (D70).** Die Lage „nachholen“ gab es seit 0.69.0 in
`mentor_opening.situation`, aber ohne Einstieg außer dem Plan und ohne Ende.
Jetzt: `mentor_context.context` gibt der versäumten Stunde ihre eigenen
Quellen mit (`source_links` der Stunde → `materials.for_context(...,
material_ids=…)`, Rang wie die Verknüpfung zur Aufgabe) und meldet
`source.missed` samt Minuten. `routers/mentor.catch_up_done` setzt beim Ende
einer Nachhol-Einheit (Knopf oder `action finish` des Modells) denselben
`caught_up`-Eintrag wie der Haken in der Liste, Notiz „Mit dem Mentor
nachgeholt“, und hängt den Satz „Die Stunde vom … gilt damit als nachgeholt“
an. Eine nachgeholte Stunde ist keine Nachhol-Lage mehr (`caught_up` an den
Stunden im Snapshot). Einstiege: Nachhol-Liste (`Absences.svelte`) und
Stundenansicht (`LessonDetail.svelte`) verlinken `#/learning?lesson_id=…`;
`Mentor.svelte` startet daraus eine freiwillige Einheit.

**Geprüft.** Zwei neue Tests in `test_opening.py`: Einstieg aus einer
versäumten Stunde mit Absenz (Instruktion der Lage, `situation.missed`,
Quelle der Stunde vorn im Material mit Inhalt, Chip „Nachholen“), Ende per
Knopf setzt `caught_up`; Abschluss durch das Modell ebenso, danach kein
Nachholen mehr. Frontend-Build bestanden.

**Offen.** Live an einer echten versäumten Stunde prüfen (Konto mit 14
offenen Stunden). Schritte 2, 4 und 5 aus MENTOR_EINSTIEG.md (Erklären als
eigener Einstieg, Kontrollieren mit Foto, Verfassung) bleiben offen.

---

# Die Frage nach der Schule 0.71.0

Stand 16.09.2026, abends. Zweites Paket der Reihenfolge aus D67; Stufe 2 aus
VERANTWORTUNG.md.

**Gebaut (D69).** `afternoon_check.py`: `last_lesson_end` aus dem Stundenplan
des Tages (ohne ausgefallene und ausgeblendete Stunden), `notify` im
Erinnerungsdienst (`reminders.run_once`) mit Fenster von 30 Minuten ab
Schulende plus Abstand, einmal je Gerät und Tag (`afternoon_app_deliveries`),
nicht mehr nach einer Antwort. `state` für die Karte: aktiv zwischen letzter
Stunde und Abendzeit, geschlossen nach „nichts Neues“. `intake_photo` legt
Material und Aufgabe sofort an (Titel vorläufig, fällig nächster Schultag,
`material_links` Art `task`, Eintrag in `afternoon_checks`); `refine` trägt
nach der Lesung Fach, Titel „Fach: Titel des Materials“ und den Tag der
nächsten Stunde des Fachs nach, einmal, nur solange die Aufgabe offen ist.
Aufgerufen aus `material_analysis.after_analysis`, damit auch der Nachtlauf
eine gescheiterte Lesung nachträgt. Router `/accounts/{id}/afternoon-check`
(GET, POST nothing, POST photo). Einstellungen `afternoon_enabled` (aus) und
`afternoon_delay` (20 Minuten) in `reminder_settings`. Frontend:
`AfternoonCheck.svelte` oben in der Heute-Ansicht, Abschnitt „Nach der
Schule“ in den Erinnerungs-Einstellungen.

**Geprüft.** Acht neue Tests (`test_afternoon_check.py`): Einstellungen,
Zeitpunkt der Mitteilung, kein Versand ohne Einschalten oder nach Antwort,
Karte aktiv nur zwischen Schulende und Abend, Foto legt die Aufgabe sofort an,
Lesung trägt Fach/Titel/Termin nach, ohne Fach bleibt der vorläufige Termin,
erledigte Aufgabe bleibt unangetastet. Frontend-Build bestanden.

**Offen.** Live-Prüfung auf einem Kindergerät (Mitteilung, Kamera aus der
Karte) steht aus; die Einstellung ist ab Werk aus. Ob es eine kleine
Anerkennung für die Routine gibt, bleibt eine Entscheidung der Eltern
(VERANTWORTUNG.md, offene Entscheidungen). Die Lesung eines Fotos kostet den
üblichen Hintergrundrahmen.

---

# Betriebspaket 0.70.0

Stand 16.09.2026, abends. Erstes von fünf Paketen der Reihenfolge aus D67.

**Web-Push entfernt (D65).** `reminders.run_once` versendet nur noch über
`app_notify` (Home-Assistant-App). `routers/push.py`, `webpush_setup.py`,
`pywebpush`, die Push-Handler in `sw.js` und der Browser-Abschnitt in
`ReminderSettings.svelte` sind weg; Migration `push_002_drop_web_push` löscht
`push_subscriptions` und die VAPID-Schlüssel aus `schema_meta`.
`reminder_deliveries` bleibt als Verlauf. Anlass: Jede Abendmitteilung
erzeugte im Add-on-Log einen Stacktrace „Could not deserialize key data“.

**Testlauf (D66).** `.github/workflows/tests.yml` führt bei jedem Push auf
`main` und in Pull Requests die Backend-Tests und den Frontend-Build aus.
`pyproject.toml` setzt `pythonpath = ["tests", "schul_cockpit"]`, damit
`python3 -m pytest tests` ohne Umgebungsvariablen läuft. Lokal: 398 Tests
grün, Frontend-Build bestanden. Beobachtung: `test_opening.py::
test_situation_is_read_from_entry_point_and_signals` schlug in einem von drei
vollständigen Läufen fehl und allein immer durch; Ursache noch offen.

**Doku-Hygiene (D68).** Kindernamen aus Konzepten, Changelog, Code-Kommentaren,
Integrationsdoku (Beispielnamen Anna/Ben) und Testdaten entfernt;
`docs/handover.md` (Stand 0.2.0, mit Zugangsnamen) gelöscht.
`scripts/ha_diagnose.py` mit curl-Rückfall.

## Bekannte Lücken

- Sensor „Hausaufgaben offen“ der Integration zählt 39 bzw. 57 Einträge, die
  Todo-Listen 3 bzw. 4 offene; Untis `completed` ist unzuverlässig. Anzeige
  neben dem Dashboard irritiert. Zurückgestellt, siehe IDEEN.md.
- Die Kostensätze der Modelle in `ai_gateway` laufen am 01.12.2026 ab.

---

# Quellenbestand 0.52.2–0.69.8

Stand 16.09.2026, nachmittags. Bis 0.69.8 auf der laufenden Instanz installiert
(Prüfung am Abend des 16.09.: Add-on 0.69.8, kein Update ausstehend, Watchdog
und Auto-Update an).

## Was ausgeliefert ist

**Anstöße und Einstieg (0.68.0 bis 0.69.2, D63, D64, D64a).** `triggers.py`:
Sammellauf nach Änderung (Material, Aufgaben, Regal, Kapitel), Untis-Wächter
alle fünf Minuten, Wiederholung gescheiterter Auswertungen. `mentor_opening.py`:
Lage deterministisch, erster Zug vom Modell mit erster Aufgabe und Tipps aus
dem Inhalt, Schlusssatz mit Stufe; Hilfe zählt nur bei offener Aufgabe.
Eichung an zwei Themen: terra gleichwertig zu sol, luna erfand Vorgeschichte;
`opening_model = gpt-5.6-terra` gesetzt. Vokabeltrainer: Einstieg unter Lernen
mit Sprachauswahl, Rücksetzen je Sprache für Eltern, Vorlesen entfernt.
Klausurkarte: Entfernen nur noch unter „Themen bearbeiten (Eltern)“.
Konzept: MENTOR_EINSTIEG.md (Nachholen in 0.72.0; Erklären, Kontrollieren noch offen).

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
Live geprüft: die Lateinliste eines Kontos ergab fünf Themen mit allen Stellen belegt
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

- Die Inhaltsverzeichnisse von Green Line 4 und Geschichte und Geschehen 3/4
  liegen nicht auf den Seiten 2 bis 9; dort greift die Kapitelregel nicht.
  Ausweg seit 0.60.0: Verzeichnisfoto auch für digitale Bücher. Der
  Regal-Dialog als Buch ist seit 0.62.0 erkannt und löschbar.
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
