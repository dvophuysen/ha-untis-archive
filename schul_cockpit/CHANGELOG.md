# Changelog

Alle relevanten Änderungen am Schul-Cockpit-Add-on. Neueste oben.

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
