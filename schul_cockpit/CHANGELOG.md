# Changelog

Alle relevanten Änderungen am Schul-Cockpit-Add-on. Neueste oben.

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
