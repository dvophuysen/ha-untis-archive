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
