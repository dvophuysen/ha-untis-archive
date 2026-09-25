# Arbeitsweise

- **Erst planen, dann umsetzen.** Vor jeder Änderung (Code, Konfiguration,
  Struktur, Releases) den Plan mit dem Nutzer abstimmen und auf sein
  ausdrückliches Ok warten. Das gilt auch für scheinbar offensichtliche
  Fixes. Ausgenommen sind reine Lese- und Diagnoseschritte.

# Live-Zugriff auf die HA-Instanz

- Sind die Umgebungsvariablen `HA_URL` (z.B. `https://xyz.ui.nabu.casa`,
  ohne Slash am Ende) und `HA_TOKEN` (Long-lived Access Token) gesetzt,
  ist die laufende Instanz per REST-API erreichbar.
  `python3 scripts/ha_diagnose.py` prüft damit die komplette
  Hausaufgaben-Pipeline: Sensor-Inhalt, Todo-Listen (inkl. fälschlich
  erledigter Einträge), Abgleich und Fehlerlog.
- Add-on-Logs (die einzige Stelle, an der Browser- und Seitenabruf-Fehler
  des Schul-Cockpits landen) liest `python3 scripts/ha_addon_log.py
  --lines 20000 --grep textbook`. Der Supervisor-Proxy gibt sie unter
  `/api/hassio/addons/<slug>/logs` heraus; ein Admin-Token genügt, und
  ohne `Range: entries=:-N:` kommen nur 100 Zeilen. Slug des Cockpits:
  `e54108c7_schul_cockpit`. Die Sammelpfade `/api/hassio/addons` und
  `/api/hassio/app/...` antworten mit 401 — daraus folgt kein fehlender
  Zugang. In der Claude-Code-Sandbox blockt der Agent-Proxy Python-urllib
  mit 403; `ha_diagnose.py` fällt dann selbst auf `curl` zurück, andere
  Aufrufe dort direkt per `curl` machen.
- Den vollen Supervisor-Zugriff (Add-on-Info, Store-Reload, Ingress-Sitzung)
  gibt `node scripts/ha_supervisor.mjs <endpoint> [method]` über die
  HA-Websocket-API (Kommando `supervisor/api`). Textantworten wie Logs kann
  dieser Weg nicht liefern, dafür den REST-Proxy nehmen. Die Add-on-API
  selbst (Verläufe, Materialien, Aufgaben) ist über eine Ingress-Sitzung
  erreichbar; der Kopf des Skripts zeigt den Weg. Vor jedem Einspielen `python3 scripts/ha_activity.py`
  laufen lassen: Rückgabe 1 heißt, in den letzten zehn Minuten war ein Kind in
  der App, dann warten. Elternzugänge halten Updates nicht auf (Wunsch des
  Nutzers). Add-on-Updates immer selbst
  einspielen, außer der Nutzer sagt ausdrücklich etwas anderes: nach dem Push
  `/store/reload post`, dann `/addons/e54108c7_schul_cockpit/update post`. Der
  Update-Aufruf antwortet mit `unknown_error`, obwohl er anläuft — auf die
  Version warten, nicht abbrechen.
- Stand und offene Punkte für eine neue Session:
  [schul_cockpit/konzept/UEBERGABE.md](schul_cockpit/konzept/UEBERGABE.md).
- `.mcp.json` bindet zusätzlich den HA-MCP-Server der Instanz ein
  (`$HA_URL/mcp_server/sse`, Integration „Model Context Protocol
  Server“). Er spricht nur die Assist-Schnittstelle — für Diagnosen die
  REST-API bevorzugen. Solange die Integration nicht eingerichtet ist,
  antwortet die Adresse mit 404; das installierte Add-on „Home Assistant
  MCP Server“ ist etwas anderes und nur über Ingress erreichbar.
- Beide Variablen werden in der Claude-Code-Umgebung gepflegt
  (claude.ai/code → Umgebung → Environment variables) und gelten ab der
  nächsten Session. Der Token gehört niemals ins Repo.

# Tests

- `python3 -m pytest tests` aus dem Repo-Wurzelverzeichnis; `pyproject.toml`
  setzt die Importpfade. Abhängigkeiten: `schul_cockpit/backend/requirements.txt`
  plus `pytest pytest-asyncio`. Frontend: `cd schul_cockpit/frontend && npm ci
  && npm run build`. Dasselbe läuft in `.github/workflows/tests.yml` bei jedem
  Push auf `main`.

# Repo-Workflow

- **Immer auf `main` ausliefern.** Änderungen werden direkt auf `main`
  fertiggestellt und gepusht — keine Feature-Branches, kein PR-Umweg,
  außer der Nutzer fordert es ausdrücklich. Falls vom Harness eine
  Arbeitsbranch vorgegeben ist: dort entwickeln, dann fast-forward in
  `main` mergen und `main` pushen.
- **Schul-Cockpit-Add-on:** sichtbare Änderungen brauchen einen
  Versions-Bump in `schul_cockpit/config.yaml` plus einen Eintrag in
  `schul_cockpit/CHANGELOG.md` — sonst zeigt HA kein Update an.
- **HA-Komponente `untis_archive`:** sichtbare Änderungen brauchen einen
  Bump in `custom_components/untis_archive/manifest.json`. Pushes aus
  Claude-Sitzungen starten keine GitHub-Workflows: das Release
  (`.github/workflows/release.yml`) und die Tests (`tests.yml`) per
  `workflow_dispatch` anstoßen (GitHub-MCP `actions_run_trigger`). Danach in
  HACS `hacs/repository/refresh` per Websocket, `update.install` auf
  `update.untis_archive_update_2`; wirksam erst nach einem HA-Neustart, den
  der Nutzer auslöst. Tests der Komponente: `tests_ha/` (siehe dortige
  `conftest.py`).

# Dauerhafter lesender Schul-Datenzugriff

Für Datenanalysen des Schul-Cockpits zuerst [READ_ACCESS.md](schul_cockpit/READ_ACCESS.md) lesen. Die App bietet ab 0.23.3 eine eigene schlüsselgeschützte, nach Kind begrenzte Lese-API. Keine PIN oder SSH-Anmeldung nötig. Zugangsdaten ausschließlich in der HA-App-Konfiguration; nie in Git oder Chat ausgeben.
