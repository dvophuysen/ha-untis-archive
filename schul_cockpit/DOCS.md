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
- **Aufgaben**: vollständige Liste, gruppiert nach Fälligkeit. Sub-Tasks,
  Aufwandsschätzung, Notizen pro Aufgabe.
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

- **Alle Daten bleiben auf deiner HA-Instanz** — keine externen
  Verbindungen.
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
