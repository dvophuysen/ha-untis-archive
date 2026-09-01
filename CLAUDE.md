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
- `.mcp.json` bindet zusätzlich den HA-MCP-Server der Instanz ein
  (`$HA_URL/mcp_server/sse`, Integration „Model Context Protocol
  Server“). Er spricht nur die Assist-Schnittstelle — für Diagnosen die
  REST-API bevorzugen.
- Beide Variablen werden in der Claude-Code-Umgebung gepflegt
  (claude.ai/code → Umgebung → Environment variables) und gelten ab der
  nächsten Session. Der Token gehört niemals ins Repo.

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
  Bump in `custom_components/untis_archive/manifest.json` (triggert den
  Release-Workflow in `.github/workflows/release.yml`).
