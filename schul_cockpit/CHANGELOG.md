# Changelog

Alle relevanten Änderungen am Schul-Cockpit-Add-on. Neueste oben.

## 0.20.1 — Plan-Grid auf fixe Periodenzeilen, klarere Vertretung
- **Fixe Stundenzeilen**: Das Plan-Grid auf der Übersicht alignt jetzt
  zeilenweise auf die Startzeit der Stunde. Periode 1 steht über alle
  Tage hinweg in derselben Zeile, leere Zellen entstehen wo ein Tag in
  der Periode keinen Unterricht hat. Vorher haben die Spalten unabhängig
  gepackt — wer sehen wollte, wann Mathe wiederkommt, musste mitzählen.
- **Vertretungen kompakt in einer Zelle**: Bei Fachersatz wird das
  ursprüngliche Fach durchgestrichen *und* das neue Fach in derselben
  Zelle gezeigt (z. B. `M̶u̶ MA`). Bleibt das Fach gleich und es ist nur
  Lehrer/Raum-Vertretung, erscheint ein ⇄-Symbol neben dem Fach.
- **Roter Ampel-Punkt auf Entfällen entfernt**: durchgestrichener,
  gestrichelter Rahmen ist Signal genug. Klausuren behalten ihr 📝-Eck.
- **„Heute"-Rahmen als Overlay**: liegt jetzt hinter den Zellen, damit
  die Mo–Fr-Reihen sauber alignt bleiben statt von der Padding-Box des
  alten Spalten-Wrappers verschoben zu werden.

## 0.20.0 — Eltern-Dashboard „Übersicht" für mehrere Kinder
- **Neue Startseite „Übersicht" 🏠** für Eltern-Accounts mit mindestens
  zwei verlinkten Kindern. Zeigt pro Kind nebeneinander: NOW-Streifen
  („jetzt 3. Std Mathe · bis 13:20"), anstehende Klausuren mit
  Ampel-Punkt, offene Hausaufgaben, Fächer mit Unterstützungsbedarf
  („Mitlernen 🤝") und einen 5-Tage-Plan-Grid Mo–Fr. Klick auf einen
  Block schaltet das Kind aktiv und springt in den Detail-View — die
  bisherige Switching-Mechanik bleibt unverändert.
- **Klausur-Ampel zentral**: kombiniert Tage bis zur Klausur, Lernstand
  (😟/😐/😀) und das Verständnis-Signal aus den Lesson-Checkins der
  letzten 21 Tage im jeweiligen Fach. Eine Klausur in einem Sorgenfach
  ohne Lernstart kippt früh auf 🟠/🔴, eine gut sitzende bleibt 🟢 auch
  knapp vor dem Termin.
- **Hausaufgaben-Ampel im Eltern-Stil**: heute fällig = ❗ (im Unterricht
  schon abgefragt), morgen = 🔴 (jetzt handeln), diese Woche = 🟠,
  später = 🟢.
- **Plan-Grid „rollende Schulwoche"**: feste Mo–Fr-Spalten; bereits
  vergangene Wochentage werden mit demselben Wochentag der Folgewoche
  aufgefüllt, heute bekommt einen blauen Rahmen. Am Wochenende zeigt das
  Grid komplett die kommende Woche. Klausur-Slots, Vertretungen,
  Entfälle und Sondertermine erscheinen als kleine Eck-Emojis (📝 🔁 🛑).
- **Backend-Aggregator** `GET /api/dashboard` liefert alle Blöcke für
  alle verlinkten Kinder in einem Roundtrip — kein Fanout von sechs
  Endpoints × zwei Kindern im Frontend.
- Eltern mit nur einem verlinkten Kind sehen die App wie bisher: keine
  Tab-Änderung, kein Default-Switch, das Dashboard ist nicht erreichbar.

## 0.19.14 — Hotfix Sync-500: UNIQUE-Constraint beim Untis-ID-Dedup
- **Bugfix:** 0.19.13 hat den Keeper-Eintrag auf eine UID rebinded, die
  noch in einer anderen Reihe der gleichen Gruppe lag → kollidierte mit
  `UNIQUE(account_id, ha_uid)`, der Sync brach mit 500 ab, Duplikate
  blieben stehen. Reihenfolge gefixt: erst die anderen Reihen löschen,
  dann den Keeper rebinden.

## 0.19.13 — HA-Dedup nutzt die Untis-Hausaufgaben-ID, nicht den Inhalt
- **Untis-ID als kanonischer Dedup-Schlüssel:** Der Tag `[MA260611]` &
  Co. in den Notes ist über alle Varianten derselben Aufgabe konstant —
  egal wie oft die HA-Automation neue UIDs vergibt. Sync gruppiert
  ha_todo-Reihen jetzt darüber statt über `(title, due_date, notes)`,
  was bei kleinsten Untis-Änderungen (z.B. Fälligkeit nachgeschoben)
  durchgerutscht ist.
- **Cross-Status:** der Dedup räumt jetzt auch offene Reihen weg, wenn
  für dieselbe Untis-ID schon eine erledigte Reihe existiert. Done
  schlägt offen — kein „erledigte HA poppt wieder auf" mehr.
- Beim Sync wird die Keeper-Reihe an die aktuell von HA gelieferte UID
  rebinded, damit sie beim nächsten Lauf wiedererkannt wird (statt vom
  Orphan-Pfad weggeräumt zu werden).

## 0.19.12 — Klausuren direkt auf der Klausuren-Seite bearbeiten
- Eltern/Admin sehen jetzt oben rechts auf der Klausuren-Seite einen
  „✏️ verwalten"-Link, der direkt in die volle Verwaltung (Kalender,
  Fach-Zuordnung, Termine ergänzen) führt. War vorher nur tief im Setup
  versteckt.
- **Manuelle Termine inline bearbeiten:** Pro manuellem Eintrag im
  „Ausstehend"-Block gibt es „✏️ bearbeiten" und „✕". Bearbeiten öffnet
  ein kleines Datum/Titel-Formular direkt in der Karte — typischer
  Fall: Nachschreibtermin wegen Krankheit verschoben.
- **Kalender-Termine** zeigen einen Hinweis: dort muss die Quelle (z.B.
  iServ) angefasst werden, alternativ über Verwalten dismissen und
  manuell neu anlegen. Wir können iServ-Termine nicht von uns aus
  zurückschreiben.
- Backend: neuer Endpoint `PATCH /accounts/{id}/manual-exams/{id}` für
  Datum/Fach/Titel/Notiz. Nur Eltern/Admin.

## 0.19.11 — Erledigte HA poppt nicht mehr auf, wenn HA-Automation UID wechselt
- **Bugfix:** Abgehakte Hausaufgaben tauchten wieder im aktiven Block
  auf, sobald die HA-Automation für denselben Inhalt eine neue UID
  ausgeliefert hat. Der Dedup-Pfad aus 0.19.8 hatte abgeschlossene
  Einträge bewusst stehen lassen (Historie), aber den Insert-Pfad nicht
  gegen Done-History abgeglichen — also wurden neue Aktiv-Reihen
  angelegt, obwohl die Aufgabe als erledigt bekannt war.
- Sync prüft jetzt vor jedem Insert: existiert eine ERLEDIGTE Aufgabe
  mit identischem `(Fach, Fälligkeit, Aufgabentext)`? Wenn ja → die alte
  Done-Reihe übernimmt die neue UID (rebind), kein neuer Aktiv-Eintrag.
- Toast „N alte/doppelte HA aufgeräumt" zählt diese Rebinds mit.

## 0.19.10 — Heute-Stundenplan bleibt, Morgen als gestrichelte Vorschau drunter
- 0.19.9 hat den Stundenplan nach Schulschluss zu früh auf „Morgen"
  umgeschaltet — Feedback (😀/😐/😟) für den heutigen Tag konnte man
  damit nachmittags nicht mehr geben. Korrigiert: „Heute" bleibt immer
  oben (mit allen Bewertungs-Buttons), darunter erscheint die
  „Morgen"-Vorschau zum Tasche packen.
- Vorschau-Stunden sind visuell dezent (gestrichelter Rahmen,
  transparenter Hintergrund, kein Detail-Modal, keine Rating-Spalte) —
  klar als Vorschau erkennbar, lenkt nicht vom Heute-Block ab.
- HeaderChips bleiben wie in 0.19.9: rote Klausur-Leiste verschwindet
  nach Schulschluss, Cram-Karte für die nächste nicht-sattelfeste
  Klausur erscheint prominent.

## 0.19.9 — Heute schaltet nach Schulschluss auf Morgen, Klausur sichtbar rot
- **Heute-Klausur-Leiste verschwindet jetzt zuverlässig**, sobald die
  zugeordnete Schulstunde Beginn passiert ist oder Schulschluss erreicht
  ist. Vorher stand die rote „🚨 Heute Klausur: SPANISCH"-Leiste nach
  Schulende noch stundenlang.
- **Cram-Karte auch auf Heute**: Klausur in ≤3 Tagen mit Lernstand noch
  nicht „sicher" landet als eigene rote Karte unter der Klausur-Leiste —
  spiegelt das „Muss lernen"-Layout aus dem Plan. Der entsprechende
  📝-Chip entfällt, damit nichts doppelt steht.
- **Stundenplan-Block schaltet nach Schulschluss auf den nächsten
  Schultag.** Überschrift ist jetzt groß und sprechend („Morgen ·
  Do. 12.06." statt „Stundenplan 2026-06-11"). Backend `/today` liefert
  dafür neu `next: {date, lessons}` für den nächsten Tag mit Stunden
  (Wochenende/Ferien werden bis zu 7 Tagen übersprungen).
- SW-Cache erneut gebumpt für die installierten PWAs.

## 0.19.8 — HA-Todo-Sync räumt Orphans und Duplikate auf
- **Bugfix:** Wenn die HA-Automation für dieselbe Hausaufgabe pro Lauf
  eine neue UID vergeben hat (oder wenn ein HA-Eintrag gelöscht wurde),
  blieb der Eintrag in der App-DB stehen. Bei Josia hatten sich so 17
  identische „Mathematik / Seite 201 7)" angesammelt.
- Sync löscht jetzt **offene `ha_todo`-Zeilen**, deren UID nicht mehr in
  der HA-Liste auftaucht. Erledigte Einträge bleiben (sind Historie).
- Zusätzlich werden offene Einträge mit identischem `(Fach, Fälligkeit,
  Aufgabentext)` auf einen kollabiert — fängt parallel angelegte
  Duplikate ein, ohne zwei echte Mathe-HAs am gleichen Tag falsch
  zusammenzulegen (Untis-Titel ist nur das Fach, der Aufgabentext steckt
  in den Notes).
- Der „↻ Sync"-Knopf gibt eine kurze Rückmeldung, wenn Einträge bereinigt
  wurden („✓ N alte/doppelte HA aufgeräumt").

## 0.19.7 — Klausur-Endspurt: eigene MUSS-Sektion + klares Stufensystem
- **Nicht-sattelfeste Klausuren in ≤ 3 Tagen** rutschen aus „Sollte
  heute" raus und werden im Plan als eigene **„Muss lernen"**-Sektion
  oben angezeigt. Eigene rot eingefasste Karte pro Klausur, grosses
  Lernstand-Emoji rechts — geht so nicht mehr unter.
- Pensum-Banner mit klarem 5-Stufen-System statt einem nichtssagenden
  „lerntag":
  - 🟢 *Frei — Pause heute* (nichts Pflicht)
  - 🟢 *Wenig zu tun* (1–2 HAs)
  - 🟡 *Überschaubar* (3–4 HAs)
  - 🟠 *Viel — fang mit den schnellen an* (≥5 HAs)
  - 🔴 *🔥 Klausur-Endspurt — heute lernen* (sobald eine cram-Klausur
    aktiv ist; überschreibt die HA-basierte Stufe).
- Endspurt-Banner ist rot hinterlegt und groesser als die anderen.
- Service-Worker-Cache gebumpt, damit installierte PWAs sicher neu
  laden statt das alte Banner-Layout zu cachen.

## 0.19.6 — Lernstand der Klausur überall sichtbar + harter Lerntag im Plan
- **Lernstand-Emoji überall**: 😟 (viel offen) / 😐 (mittel) / 😀 (sicher)
  / ⚪ (nicht begonnen) erscheint jetzt direkt auf dem 📝-Klausur-Chip
  auf „Heute", auf der roten „Heute Klausur"-Leiste und auf jeder
  „… vorbereiten"-Karte im Plan. Vorher lag das nur auf der
  Klausuren-Seite — der wichtigste Vorbereitungs-Signal-Wert war damit
  praktisch unsichtbar.
- **„Sollte heute"-Vorbereiten-Karte für heutige Klausur ausgeblendet.**
  Vorbereiten kann man am Klausurmorgen nichts mehr; das Item war reines
  Rauschen und stand zwischen den echten To-Dos.
- **Neuer Pensum-Status „harter Lerntag — Klausur steht an"** (rot)
  überschreibt „wenig/überschaubar/viel" sobald in den nächsten zwei
  Tagen eine Klausur ansteht, deren Lernstand noch nicht „sicher" ist.
  Damit zeigt der Plan-Banner endlich die Realität: zwei Hausaufgaben +
  morgen Mathe-Klausur auf mittlerem Niveau ist kein „wenig zu tun".

## 0.19.5 — Untis-ID `[EN260612]` & Co. werden jetzt zuverlässig versteckt
- `stripUntisMetadata` hat nur Tags mit dem festen Präfix `SN`
  ausgeblendet. Englisch (`[EN…]`), Deutsch (`[DE…]`), Mathe (`[MA…]`)
  blieben sichtbar und blähten die Hausaufgaben-Zellen auf.
- Filter ist jetzt generisch: `[<1–5 Buchstaben><Ziffern>]` — passt auf
  alle Untis-Fach-Kürzel.

## 0.19.4 — Alle anstehenden Klausuren als eigene Chips
- Bisher hat der Header nur die **nächste** Klausur als 📝-Chip gezeigt.
  Wer zwei Klausuren in zwei Tagen schreibt, sah nur die erste — genau
  das war der Auslöser: Noah hatte morgen Spanisch und übermorgen die
  zweite, im Header tauchte nur Spanisch auf.
- Jetzt bekommt jede Klausur in den nächsten 7 Tagen einen eigenen
  Chip. Das harte 4-Chip-Limit ist weg; die Reihe wickelt sich um.

## 0.19.3 — Klausur-Chip nutzt jetzt die kuratierte Klausur-Quelle
- **Bugfix:** Der neue 📝-Chip und die rote "Heute Klausur"-Leiste lasen
  Untis' eigenes `period_info_json.exam`-Feld — das ist für die
  Schüler-Rolle bekanntermaßen tot und liefert keine Klausuren. Folge:
  Kinder mit anstehenden Klausuren sahen nichts. Beide ziehen jetzt aus
  `/api/accounts/{id}/exams` (HA-Kalender + manuelle Einträge), wie die
  Klausuren-Seite selbst.
- Rote Leiste springt zur ersten heutigen Stunde des passenden Faches.

## 0.19.2 — Versionsanzeige im Frontend repariert (war immer "dev")
- `vite.config.js` las die Add-on-Version aus `../config.yaml`, im
  Docker-Build-Kontext fehlte die Datei aber — also fiel die Anzeige
  immer auf `dev` zurück. Damit war im Login/Setup nicht erkennbar,
  welche Version wirklich läuft, was Cache-Probleme schwer
  diagnostizierbar machte. Jetzt wird `config.yaml` in den
  Frontend-Build-Stage kopiert, die Versionsanzeige zeigt die echte
  Add-on-Version.

## 0.19.1 — Bugfix: PWAs der Kinder bekamen die 0.19.0-Chips nicht
- In 0.19.0 wurde nur das Frontend-Bundle neu gebaut, `sw.js` selbst
  blieb byte-identisch. Damit registriert der Browser keinen neuen
  Service Worker → kein `skipWaiting`, kein automatischer Reload, die
  installierten PWAs zeigten weiter den alten Heute-Header.
- Cache-Marker in `sw.js` gebumpt; beim nächsten Öffnen der App
  installiert sich der SW neu, leert den alten Cache und lädt die Seite
  einmalig automatisch nach.

## 0.19.0 — Heute-Header: Aktions-Chips statt Status-Banner
- Die alte „X heute · Y bald · N Klausuren"-Zeile auf „Heute" ist weg.
  Stattdessen oben eine handlungs-orientierte Kopfleiste.
- Phase „vor Unterrichtsschluss" (= solange noch eine Stunde aussteht):
  Chips zeigen ⚡ Plan-Änderungen für die noch kommenden Stunden, 🗣
  mündlich-Tipps für Fächer, die heute noch dran sind, 📚 HA bis morgen,
  und 📝 die nächste Klausur in ≤ 7 Tagen.
- Phase „nach Schluss" (auch an Wochenenden / freien Tagen): nur 📚 und
  📝 — was bis morgen vorbereitet sein muss.
- Steht heute noch eine Klausur an, gibt es eine eigene rote Leiste
  „🚨 Heute Klausur: <Fach>" über den Chips.
- Chips sind klickbar und springen direkt ans Ziel (Stundenkarte,
  Klausur-Seite, Fach-Detail oder zur „Heute zu erledigen"-Sektion).

## 0.18.0 — Check-ins gehören dem Kind, nicht der eintragenden Person
- **Bugfix:** Wenn Eltern Stunden-Feedback (😀 😐 😟) für ein Kind
  eintrugen, sah das Kind weiterhin alles unausgefüllt — und umgekehrt.
  Grund: die Check-in-Reihe war pro `(Account, Stunde, User)` eindeutig,
  also bekam jede:r eine eigene Kopie. Jetzt ist sie pro `(Account,
  Stunde)` eindeutig: alle, die Zugriff auf das Kind haben, sehen
  dasselbe Feedback und können sich gegenseitig ergänzen/korrigieren.
- Migration läuft beim ersten Start: bestehende Doppel-Reihen werden
  zusammengeführt, der **neueste** Eintrag (nach `updated_at`) gewinnt.
  `user_id` bleibt als „zuletzt bearbeitet von" für das Audit-Log.
- Gleicher Fix für „Stoff nachgeholt"-Häkchen (caught_up).
- Mündlich-Vorschläge, Plan-Frühwarnung, Nachmittags-Vorschläge und
  Notiz-Suche profitieren automatisch — sie sehen jetzt alles Feedback
  zum Kind, egal wer es eingetragen hat.

## 0.17.2 — Webclip: inline statt attachment (iOS-Installer öffnen)
- Profil wird jetzt mit `Content-Disposition: inline` ausgeliefert. iOS
  hat keinen Download-Manager — `attachment` führte zu einer leeren
  Seite. Mit `inline` erkennt Safari den MIME-Typ und übergibt das
  Profil direkt an Settings.app („Profil installieren?").

## 0.17.1 — Webclip-Download für iOS-PWA gefixt
- Webclip-Knopf nutzt jetzt direkte Navigation statt fetch+Blob —
  iOS-Standalone-PWAs ignorieren den `<a download>`-Trick still, sodass
  vorher gar nichts passierte. Direkte Navigation triggert den System-
  Profile-Installer zuverlässig.
- Service-Worker-Cache invalidiert, damit der Fix auch in installierten
  PWAs ankommt.

## 0.17.0 — iPhone-Bildschirmzeit-Hilfe + Webclip
- Neue Sektion „iPhone-Bildschirmzeit" in den Einstellungen mit
  Klick-Anleitung: App-Domain zum Kopieren für „Erlaubte Websites".
- **Webclip-Download** pro Kind (unsigniertes .mobileconfig): legt ein
  Vollbild-App-Icon mit Deep-Link auf das richtige Kind an und erscheint
  als eigener Eintrag in Bildschirmzeit → App-Limits (dort auf „Immer
  erlaubt" setzbar, ohne ganz Safari freizugeben). Nur Admin; erfordert
  gesetzte externe URL.

## 0.16.0 — Datensicherung (Backup/Restore)
- Neue Admin-Sektion „Datensicherung" in den Einstellungen.
- **Backup-Download** als ein ZIP mit **beiden** Datenbanken (App-Daten
  `webapp.db` + UNTIS-Archiv `history.db`) plus Manifest — konsistent
  per SQLite-Online-Backup (sauberer WAL-Checkpoint). Die beiden DBs
  sind voneinander abhängig und werden so zum selben Zeitpunkt gesichert.
- **Restore**: spielt aus ZIP oder .db die `webapp.db` zurück (Schema
  geprüft; alte DB wird vorher als `.bak` gesichert, die letzten 3
  bleiben erhalten). `history.db` wird bewusst NICHT überschrieben
  (Integration hält sie live offen) — Wiederherstellung über
  HA-Backup-Restore, mit Hinweis in der App.
- **Statusanzeige**: Zähler (Aufgaben/Check-ins/Klausuren/Noten), DB-
  Größe, Zeitpunkt des letzten HA-Backups; Warnung, wenn noch kein
  HA-Backup gefunden wurde. Nur für Admin.

## 0.15.1 — Stundenkarte: Marker & Check-in-Reihe
- Vertretungs-/Änderungs-/Ausfall-/Klausur-Markierung wieder als
  deutliche farbige Badges (statt blasser Mini-Emojis): ❌ Ausfall,
  ↺ Vertretung (auch bei Lehrer-/Raum-/Fachwechsel, mit „statt …"),
  🤒 versäumt, 📝 Klausur.
- Check-in-Emojis einheitlich in EINER Zeile: 👀 links als optionaler
  Slot (nur bei Vertretung), bei normalen Stunden leer freigehalten,
  dann 😀 😐 😟 — immer an derselben Position.

## 0.15.0 — Nicht belegte Kurse/Wahlfächer ausblenden
- Neue Einstellungs-Sektion **„Kurse / Wahlfächer"** (🛠 Einstellungen):
  jeder Kurs (Fach + Lehrer) mit Häufigkeit und Schalter belegt /
  nicht belegt; pro Fach ein „ganzes Fach aus/ein"-Knopf.
- Ausgeblendete Kurse verschwinden aus Heute, Woche, Fächern,
  „mündlich punkten"-Vorschlägen und der Klausur-Fach-Erkennung.
- Behebt die überzähligen Parallelkurse aus dem WebUntis-Kursband
  (z.B. mehrere Instrumental-/Gesang-Kurse, die das Kind nicht belegt).
- Wer genau einen Parallelkurs belegt, lässt den an und blendet die
  anderen aus.

## 0.14.0 — Plan & Aufgaben zusammengeführt, Note als Dropdown
- **Plan und Aufgaben sind jetzt eine Seite** (Tab „Plan"). Der separate
  „Aufgaben"-Tab entfällt → wieder 6 Tabs, Platz für „Klausur".
  Aufbau: Pensum · Heute zu erledigen · Sollte heute · Demnächst (diese
  Woche / später / ohne Datum) · „erledigte anzeigen" · + anlegen · Sync.
- **Klausur-Note als Dropdown** statt Freitext. Intern als KMK-Punkte
  0–15 gespeichert (umrechenbar). Sek I zeigt Noten mit Tendenz
  (1+ … 5− · 6), Sek II Punkte — Grundlage für späteren Notenausgleich.

## 0.13.0 — Eigene Klausuren-Seite (Lernstand + Noten)
- Neuer Tab **„Klausur"** mit zwei Blöcken:
  - **Ausstehend** (nächste zuerst): pro Klausur ein Lernstand-Wahlfeld
    (nicht begonnen / viel offen / mittel / sicher) als Selbsteinschätzung.
  - **Vergangen** (jüngste zuerst): Feld zum Eintragen der erhaltenen
    **Note**.
- Quelle wie gehabt: verknüpfter Kalender + manuelle Termine.
- Lernstand/Note werden pro Klausur gespeichert (Kind setzt Lernstand,
  Eltern/Kind die Note).

## 0.12.0 — Neuer Plan: MUSS/SOLLTE/KANN + Klausuren statt Budget
- **Budget-Knöpfe entfernt.** Der Plan zeigt stattdessen oben einen
  Pensum-Indikator (nichts/wenig/überschaubar/viel).
- **Muss heute**: überfällige + heute/morgen fällige Hausaufgaben,
  schnellste zuerst (damit Kleinkram nicht zum Berg wird).
- **Sollte heute** (max. 3, bedarfsgetrieben): Klausur-Vorbereitung
  (Frühwarnung „Klausur in X Tagen" aus den erkannten Terminen),
  versäumter Stoff nachholen, wiederkehrende Verständnislücken.
- **Anstehende Klausuren**: sichtbare Übersicht der nächsten 4 Wochen
  direkt im Plan — aus verknüpftem Kalender + manuellen Terminen.
- Damit nutzt der Plan jetzt die in 0.11 eingeführte Klausur-Erkennung.

## 0.11.1 — Changelog nachgeholt
- Diese `CHANGELOG.md` angelegt, damit HA den Verlauf im Add-on-Store
  anzeigt. Inhaltlich keine Funktionsänderung gegenüber 0.11.0.

## 0.11.0 — Klausur-Erkennung aus verknüpftem Kalender + Diagnose
- Klausurtermine kommen jetzt aus einem **pro Kind verknüpften HA-Kalender**
  (z.B. iServ-Abo), gelesen über die Supervisor-API. Grund: die WebUntis-
  Schüler-Logins geben Klausuren nicht her (live verifiziert: dedizierter
  Endpoint 403, Stundenplan nur ±9 Tage). `period_info_json.exam` bleibt
  nur als Fallback.
- Automatische **Fach-Erkennung** aus dem Termin-Text via Alias (MA/Mathe/
  Mathematik → Mathematik, WN/WuN/Werte und Normen, BI/Bio …), gespeist
  aus den echten Fächern des Kindes — nicht belegte Fächer (z.B.
  Religion) matchen dadurch automatisch nicht.
- **Übersteuerung**: Termine manuell einem Fach zuordnen oder als „nicht
  zutreffend" markieren (Turnier/Ausflug/ungenutzter Nachschreibtermin);
  konfigurierbare Ausschluss-Wörter.
- **Mündlich abgesprochene** Prüfungstermine manuell ergänzbar.
- Neue **Diagnose-Ansicht** „Klausuren verwalten" (Setup-Bereich): zeigt
  alle Kalender-Termine mit Erkennungs-Status zum Prüfen/Kuratieren.
- Die Plan-Steuerung (Anzeige & Frühwarnung) folgt in v0.12.0 auf dieser
  jetzt verlässlichen Klausur-Basis.

## 0.10.0 — Tagesbudget folgt dem Nds. Hausaufgaben-Erlass
- Tagesbudget je Kind kommt aus dem [RdErl. d. MK v. 12.09.2019]
  (Primar 30, Sek I 60, Sek II 120 min werktags; Wochenende 0;
  Nachmittagsunterricht ×0,75).
- Klassenstufe wird aus den UNTIS-Stammdaten erkannt (z.B. „5a" → Sek I,
  „EF/Q1" → Sek II), bei exotischer Klassenbezeichnung manuell setzbar.
- Setting „An Erlass orientieren" als Toggle; manueller Override in
  beide Richtungen weiterhin möglich.

## 0.9.0 — Notify-API für HA-Automationen (Hermes/WhatsApp)
- Pro Kind ein Notify-Token (Setup → Benachrichtigungen).
- `GET /api/notify/<id>/summary?token=…` liefert kompakte Zahlen
  (Tasks, Fehlstunden, nächste Klausur) + Deep-Links + fertige
  deutsche Nachrichten-Templates.
- Add-on-Option `external_url` für vollständige URLs in den Templates.
- Deep-Link-Support `?acc=<id>` setzt den aktiven Account beim Aufruf.

## 0.8.x — Stabilisierung & UX
- 0.8.8: Fehlstunden im Wochenraster visualisiert (🤒 / ✓ pro Stunde,
  ganztägige Abwesenheit am Tag-Header).
- 0.8.7: Vorbereitung-Vorschläge schauen nach vorne (nächste Stunde des
  Fachs), nicht zurück auf heute.
- 0.8.6: Klick auf abgelaufene Stunde im Wochenplan öffnet das
  Check-in-Sheet (gleiche Komponente wie Heute).
- 0.8.5: Erledigte Lernzeit zählt gegen das Tagesbudget; Tagesbudget-
  Schnellwahl im Plan nur für Eltern/Admin.
- 0.8.4: Bug-Fix — abgehakte Hausaufgaben springen nicht mehr zurück
  (Konfliktauflösung beim HA-ToDo-Sync neu, App-Done gewinnt immer).
- 0.8.3: Add-on-Panel auch für Nicht-Admin-HA-User sichtbar
  (`panel_admin: false`).
- 0.8.2: Sticky-Bottom-Nav-Fix für Safari-Tab-Modus.
- 0.8.1: Hausaufgaben-Checkbox war im Safari-Tab unzuverlässig
  (verschachteltes `<button>` aufgelöst), Optimistic-UI + sichtbare
  Fehlermeldung statt stillem Stehenbleiben.
- 0.8.0: „Fehlt"-Seite (🤒 Cluster-Übersicht der Abwesenheiten mit
  Wochenend-Brückenlogik) + freie Lernzeit + +-Übernehmen-Vorschläge
  im Plan.

## 0.7.x — Plan-Detail & Layout-Politur
- 0.7.0: Hausaufgaben-Inhalt im Plan sichtbar; HA-todo-Metadaten
  (Gegeben/Fällig/SN) aus der Anzeige gestrippt; Frist als natürliche
  Sprache („morgen fällig", „4 Tage überfällig").
- Diverse Safari-/PWA-Layoutfixe (Bottom-Nav, Status-Bar-Überlagerung,
  Rubber-Band).

## 0.6.x — PWA-Updates, Cache, Versionsanzeige
- 0.6.3: Timezone-Fix („morgen" wurde fälschlich als „heute" gewertet).
- 0.6.2: Service-Worker macht Hands-off-Updates (skipWaiting +
  controllerchange-Reload) — neues PWA-Update kommt automatisch beim
  nächsten Öffnen an.
- 0.6.1: Cloudflare-/Browser-Caching von `sw.js` / `index.html`
  deaktiviert (no-cache-Header). Versionsnummer ist im Bundle einge-
  backen und im Login/Setup sichtbar.
- 0.6.0: Bottom-Nav klebt wieder am Rand (alle Sticky/Flex-Versuche
  zurückgedreht), HA-Beschreibung im Plan sichtbar.

## 0.5.x — PIN-Login + Direct-URL (PWA-Installation)
- 0.5.9: Hausaufgaben mit Fälligkeit „morgen" zählen jetzt als „heute
  zu erledigen".
- 0.5.x: PIN-Login pro Kind, eigene Direct-URL, 1-Jahres-Sliding-
  Session, PWA-Installierbarkeit, ID-Stabilität gegen Re-Setup.

## 0.4.x / 0.3.x / 0.2.x / 0.1.x
- Erste Version: Add-on-Skelett, Ingress-Auth, Untis-Datenanbindung
  (read-only `history.db`), Today/Plan/Aufgaben/Woche/Fächer, HA-ToDo-
  Sync bidirektional, Demo-Modus, Audit-Log, Service-Worker, App-Shell.
