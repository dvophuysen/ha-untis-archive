# Schul-Cockpit — Installation & Nutzung

## Voraussetzungen

- **UNTIS Archive Integration** (`custom_components/untis_archive/`)
  ist installiert, eingerichtet und hat schon einmal gepollt
  (`history.db` muss existieren).
- Home Assistant OS oder Supervised (das Add-on nutzt Ingress und die
  Supervisor-API).
- Pro Kind eine **HA-ToDo-Liste** (z.B. via dem eingebauten
  `todo.local`-Helper) — die HA-Automation, die Untis-Hausaufgaben in
  diese Listen schreibt, läuft unverändert weiter.

## Installation

1. In HA → **Einstellungen → Add-ons → Add-on-Store** öffnen.
2. Oben rechts ⋮ → **Repositorien**.
3. Repo-URL `https://github.com/dvophuysen/ha-untis-archive` eintragen
   und hinzufügen.
4. Im Store taucht **„Schul-Cockpit"** auf → Installieren → Starten.
5. „Im Seitenleisten-Menü zeigen" aktivieren (optional, sehr bequem).

## Erster Login & Setup

- Der erste eingeloggte HA-User wird automatisch **Admin**.
- Auf dem Heute-Screen erscheint oben rechts ein ⚙️-Symbol → Setup.
- Pro HA-User: Rolle (Eltern / Kind / Admin) setzen und die zugehörigen
  Untis-Kinder per Klick zuordnen.
- Pro Kind: die HA-ToDo-Liste auswählen, die deine Untis-Automation
  füllt.

Andere Familienmitglieder müssen sich einmal eingeloggt haben, damit
sie im Setup-Screen auftauchen.

## Tägliche Nutzung

- **Heute**: Stundenplan + Check-ins (😀 / 😐 / 😟) pro Stunde, fällige
  Aufgaben on top.
- **Plan**: priorisierter Nachmittagsplan mit Zeitbudget. Schnellwahl
  30/45/60/90/120 Min, „📋"-Knopf kopiert die Liste als Markdown.
- **Aufgaben**: vollständige Liste, gruppiert nach Fälligkeit, mit Notizen
  pro Aufgabe. Eine Hausaufgabe öffnet seit 0.56.0 eine Leseansicht mit
  Auftrag, Einstiegshilfe, Material und Hilfe-Chat; Typ, Aufwand und
  Teilaufgaben sind entfallen ([D44](konzept/ENTSCHEIDUNGEN.md)).
- **Woche**: Heatmap der letzten/kommenden Woche, Farbe = Verständnis.
- **Fächer**: pro Fach die Lehrstoff-Timeline mit deinen Bewertungen +
  „Heute mündlich punkten"-Vorschläge.

## Sync mit HA-ToDo

- Läuft im Hintergrund alle 2 Min.
- Wird ein Task in der App abgehakt, wird der Eintrag in der HA-ToDo
  ebenfalls als erledigt markiert.
- Wird ein Eintrag in der HA-ToDo erledigt, übernimmt der nächste Sync
  das in die App.
- **Manuell angelegte Tasks** in der App (z.B. Klausurvorbereitungs-
  Lerneinheiten) gehen **nicht** in die HA-ToDo.

## Tagesbudget Lernzeit

Über das 🛠-Symbol oben rechts (pro Kind) lässt sich einstellen, wie
viele Minuten pro Tag standardmäßig zum Lernen zur Verfügung stehen
und welche Wochentage abweichen.

## Troubleshooting

- **„Bitte UNTIS-Archive-Integration aktualisieren"** im Add-on-Log:
  Das Add-on prüft beim Start, ob `history.db` alle erwarteten
  Spalten hat. Falls die Integration zu alt ist, kommt diese Meldung —
  in HACS aktualisieren.
- **Setup-Screen zeigt keine HA-User außer dir**: die anderen müssen
  sich einmal in der App eingeloggt haben.
- **Keine ToDo-Listen sichtbar**: das Add-on braucht
  `homeassistant_api: true` (ist in `config.yaml` gesetzt). Add-on
  neu starten.

## Als App auf den Home-Bildschirm (PWA)

Innerhalb von HA läuft die App über Ingress — dabei ist sie aber in die
HA-Oberfläche eingebettet und lässt sich auf dem iPhone nicht als
eigenständige App installieren. Dafür gibt es den **Direkt-Zugriff**:

1. Im Setup (Zahnrad oben rechts) für jedes Kind einen **PIN** vergeben.
2. Auf dem iPhone in **Safari** die Direkt-Adresse öffnen
   (siehe nächster Abschnitt — je nach Setup im LAN oder über Cloudflare).
3. Mit dem PIN des Kindes anmelden (30 Tage gültig).
4. Teilen-Symbol → **„Zum Home-Bildschirm"**.

Ergebnis: eigenes Icon, Vollbild ohne Safari-Leiste, offline-fähig
(zuletzt geladene Ansicht bleibt sichtbar). Innerhalb von HA über die
Seitenleiste funktioniert die App weiterhin ohne PIN.

### Direkt-URL im Heim-WLAN

`http://<HA-IP>:8099/` — z.B. `http://192.168.178.42:8099/`.
Funktioniert ohne weitere Konfiguration, ist aber nur im eigenen
Netzwerk erreichbar.

### Direkt-URL über Cloudflare Tunnel

Mit einem zweiten Public Hostname im bestehenden Tunnel bekommt die App
eine eigene öffentliche Subdomain (z.B. `https://schule.deinedomain.de`).

Schritt für Schritt im Cloudflare-Dashboard:

1. **Zero Trust → Networks → Tunnels** öffnen und den bestehenden
   Tunnel anklicken.
2. **Configure → Public Hostname** → **Add a public hostname**.
3. Felder:
   - **Subdomain:** z.B. `schule`
   - **Domain:** deine Domain (Dropdown)
   - **Path:** leer lassen
   - **Service – Type:** `HTTP` (nicht HTTPS! Der Tunnel terminiert TLS;
     intern spricht das Add-on Klartext-HTTP)
   - **URL:** `homeassistant.local:8099` (oder die feste IP, z.B.
     `192.168.178.42:8099`)
4. Speichern. Nach ein paar Sekunden ist `https://schule.deinedomain.de`
   live und zeigt direkt die App ohne HA-Rahmen.

**Wichtig — Cloudflare Access NICHT aktivieren** für diese Subdomain:
Der PIN-Login der App ist die einzige Auth-Schicht. Doppelte Anmeldung
(Cloudflare Access + PIN) ist für die Kinder verwirrend.

**Sicherheit der Session-Cookies:** Sobald Cloudflare HTTPS terminiert,
markiert das Add-on das Login-Cookie automatisch als `Secure`, sodass es
nie über unverschlüsseltes HTTP übertragen wird.

## Datensicherheit & Persistenz

- **Die Lern- und App-Daten liegen auf deiner HA-Instanz.** Ist die KI eingerichtet, gehen Fotos, Buchseiten, Unterrichts- und Hausaufgabentexte, Mentor-Gespräche und Sprachaufnahmen zur Auswertung an die konfigurierten Azure-AI-Foundry-Ressourcen; Schlüssel bleiben serverseitig. Einzelheiten: [README, Datenablage](README.md#datenablage).
- `webapp.db` (Check-ins, Aufgaben, PINs, Einstellungen) liegt in
  `/data/` und ist Teil **jedes HA-Backups**.
- **Add-on-Updates** (auch automatische) lassen `/data/` unangetastet.
- **Verknüpfung zum UNTIS-Archiv ist dauerhaft**: Zu jedem Check-in und
  jeder Aufgabe wird zusätzlich die stabile Untis-Kennung
  (`untis_period_id`, `entry_id`) gespeichert. Selbst wenn die
  UNTIS-Archive-Integration komplett entfernt und neu eingerichtet wird
  (was die internen Datenbank-IDs neu vergibt), erkennt die App das beim
  Start und repariert die Verknüpfungen automatisch — kein Datenverlust.
- **Einziger echter Löschfall**: Beim Deinstallieren des Add-ons fragt
  HA „Daten löschen?" — mit „Nein" überlebt `webapp.db` eine spätere
  Neuinstallation.


## Lernraum ab 0.23.0

Der neue Tab **Lernen** verbindet Unterrichtsthemen, Materialien und Übungen über alle Fächer und Schuljahre. Unter **Steuern** richten Eltern das aktive Schuljahr und den Lernrahmen ein. Die vorhandene Kind-Zuordnung gilt unverändert.

Unter **Themen** lassen sich eigene Übungen anlegen; KI-Entwürfe werden erst nach Prüfung freigegeben. Der Lernverlauf enthält ausdrücklich Selbsteinschätzungen, keine automatisch vergebenen Noten. Für Screenshots und PDFs stehen 100 MB je Kind zur Verfügung (8 MB je Datei). PDF-Inhalt für KI als Text ergänzen oder einzelne Seiten als Bilder einstellen.

Die KI wird an einer Stelle der Add-on-Konfiguration eingerichtet. Unter **KI-Plattformen** stehen zwei Azure-Foundry-Ressourcen mit je Endpunkt und API-Schlüssel; die zweite bleibt leer, solange nur eine im Einsatz ist. Darunter stehen unter **KI-Modelle** vier Stufen: Hoch, Mittel, Niedrig und Transkription. Je Stufe werden der Modellname, wahlweise ein abweichender Bereitstellungsname, die Foundry und wahlweise eigene Kostensätze eingetragen.

Hoch bedient das Hauptgespräch, Transkription die Spracheingabe. Welche Stufe den Einstieg in eine Einheit und das Abschreiben der Quellen übernimmt, wählen die Eltern in der App unter den Budgetgrenzen; ohne Wahl gilt Hoch. So lässt sich ein Modell in der Konfiguration austauschen, ohne dass die Auswahl der Eltern ins Leere zeigt.

Der Bereitstellungsname geht in den Aufruf an Azure, der Modellname in Preis, Log und die Kennungen gespeicherter Ergebnisse. Bleibt das Feld leer, sind beide gleich. Die Kostensätze in Euro je Million Token gelten, sobald Eingang und Ausgang gesetzt sind; bei 0 greift die hinterlegte Tabelle der App, und für ein Modell ohne beides wird kein Aufruf gemacht. Zeigt eine Stufe auf eine Foundry ohne Endpunkt oder Schlüssel, bricht ihr Aufruf mit einer Meldung ab, statt auf die andere Ressource auszuweichen.

Zusätzlich muss KI pro Schuljahr freigegeben werden. Ohne Konfiguration ist der Lernraum mit eigenen Aufgaben voll nutzbar. Welche Stufe welches Modell über welchen Host fährt, steht beim Start im Add-on-Log.

Früheres Gesamtkonzept mit Architektur und Inbetriebnahme (Stand 0.23 bis 0.83, archiviert): [LERNKONZEPT.md](konzept/archiv/LERNKONZEPT.md)


## Automatische Themenübersicht ab 0.24.0

Im Eltern-Lernraum unter **Heute → Unterricht automatisch auswerten** einschalten. KI muss zusätzlich im aktiven Schuljahr aktiviert sein. Eine Gruppe umfasst höchstens 24 neue/geänderte Einträge eines Fachs; **Weitere Unterrichtseinträge auswerten** stößt die nächste Gruppe von Hand an. Das Archivfenster beginnt am 1. August des vergangenen Schuljahres. Höchstens 6.000 aktuelle Datensätze werden betrachtet; eine Kürzung wird angezeigt.

An die KI gehen Jahrgang, Fach, Unterrichtsdatum und Stofftext sowie bereits erkannte Thementitel; Feedback, Fehlzeiten und Antworten bleiben für die Priorisierung lokal. Inhalte werden pro Eintrag auf 2.000 Zeichen und pro Gruppe auf 14.000 Zeichen begrenzt. Maximal 6.500 Ausgabetokens und gemeinsam zwölf Modellaufrufe pro Kind/Tag begrenzen den Aufwand. Tatsächliche gemeldete Tokens erfolgreicher Auswertungen werden angezeigt; dies ist keine vollständige Kostenabrechnung.

Themen erhalten Erklärungen, Verbindungen und einen **nicht freigegebenen** Kurzcheck. Eltern prüfen diesen unter **Kurzcheck prüfen und freigeben**. Freigegebene Aufgaben nutzen die vorhandenen Wiederholungsintervalle und Zeitbudgets. Unterrichtstexte beweisen weder Können noch Klausurrelevanz. Älterer Unterricht bleibt mit seinem Datum erkennbar, auch wenn er dem aktuellen Lernrahmen als Grundlage zugeordnet wird. Seit 0.25.0 läuft die Auswertung im Hintergrund, wenn sie hier und im Mentor unter „Neue Unterrichtsthemen im Hintergrund erschließen“ eingeschaltet ist: Der Dienst prüft jede Minute, je Kind kommt höchstens eine Gruppe alle zehn Minuten dran, nach einem Fehler erst vier Stunden später. Das Öffnen einer Seite löst keine Auswertung aus. Quellen und Materialien werden davon unabhängig ereignisgesteuert verarbeitet ([D63](konzept/ENTSCHEIDUNGEN.md)). Eine pausierte Auswertung löscht vorhandene Ergebnisse nicht.

API (jeweils unter `/api/accounts/{account_id}/learning/discovery`): GET Übersicht, PUT `/settings` mit `{ "enabled": true }`, POST `/scan` für eine begrenzte Gruppe. Elternrolle und bestehende Kontoberechtigungen sind erforderlich.

## Dauerhafter Analysezugang ab 0.23.3

Eine separate Lese-API liefert Unterricht, Rückmeldungen, Nachholen, Aufgaben und Lernverläufe. Authentifizierung, Filter, Pagination und Wiederverwendung in späteren Sessions: [READ_ACCESS.md](READ_ACCESS.md). Der Zugang ist standardmäßig deaktiviert und wird über `learning_read_token` sowie `learning_read_accounts` ausdrücklich eingerichtet.


## Lernmentor ab 0.25.0

Der Lernbereich startet jetzt mit dem Mentor. Bedienung, Kostensteuerung, Datenmodell und Grenzen mit Stand 0.28.0 stehen im archivierten [MENTOR_BETRIEB.md](konzept/archiv/MENTOR_BETRIEB.md). Maßgeblich für Stand und Entscheidungen ist [konzept/README.md](konzept/README.md); der frühere Masterplan liegt im [Archiv](konzept/archiv/MASTERPLAN.md). Die Abschnitte zur früheren 0.24.0-Vorarbeit beschreiben keinen eigenständigen Release; Seitenaufrufe lösen keine automatischen KI-Analysen mehr aus.

## Nutzungsbericht für Eltern ab 1.13.17

In der Familienansicht steht unter dem Wochenrückblick „So wurde die App
genutzt“. Er ist nur für Eltern sichtbar, beschreibt die Woche und nennt
Auffälligkeiten jeweils mit Beleg, möglicher Deutung und dem, was die App
nicht sehen kann. Dafür misst die App, wie lange sie sichtbar war (Summen je
Tag und Ansicht, nach 90 Tagen gelöscht), und merkt sich bei jeder Nachricht
an den Mentor, ob es eine Frage, eine Antwort oder eine Bitte um Hilfe war.

Als Nachricht an die Eltern am Sonntagabend, mit dem Mitteilungs-Token des
Kindes in `secrets.yaml`:

```yaml
# configuration.yaml
rest_command:
  schul_cockpit_woche_kind_a:
    url: !secret schul_cockpit_woche_kind_a   # http://e54108c7-schul-cockpit:8099/api/notify/1/usage-week?token=…
    method: get
```

```yaml
# Automation
triggers:
  - trigger: time
    at: "18:00:00"
conditions:
  - condition: time
    weekday: sun
actions:
  - action: rest_command.schul_cockpit_woche_kind_a
    response_variable: bericht
  - action: notify.mobile_app_eltern   # das Gerät eines Elternteils, nie das des Kindes
    data:
      title: "{{ bericht.content.title }}"
      message: "{{ bericht.content.text }}"
```

