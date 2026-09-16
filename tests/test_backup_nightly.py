"""Die nächtliche Sicherung des Add-ons über den Supervisor."""
from backend import backup

SLUG = "e54108c7_schul_cockpit"


def entry(name, date, addons, ha=False, slug="x"):
    return {"slug": slug, "name": name, "date": date, "type": "partial" if not ha else "full",
            "content": {"homeassistant": ha, "addons": addons, "folders": []}}


def test_only_backups_containing_the_addon_count():
    backups = [
        entry("Automatic backup 2026.9.2", "2026-09-16T03:26:32+00:00", ["core_mariadb", "a0d7b954_ssh"], ha=True),
        entry("Schul-Cockpit 0.34.0", "2026-09-14T06:20:47+00:00", [SLUG]),
        entry("Automatic backup 2026.9.2", "2026-09-15T02:51:32+00:00", ["core_mariadb"], ha=True),
    ]
    state = backup.backup_state(backups, SLUG)
    assert state["last_ha_backup"] == "2026-09-16T03:26:32+00:00"
    assert state["last_addon_backup"] == "2026-09-14T06:20:47+00:00" and state["addon_backups"] == 1
    # Der Supervisor liefert Add-ons auch als Objekte.
    assert backup.own_backups([entry("x", "2026-09-10", [{"slug": SLUG, "name": "Schul-Cockpit"}])], SLUG)


def test_pruning_keeps_seven_own_nightly_backups_and_never_touches_others():
    own = [entry(f"Schul-Cockpit 0.63.0 2026-09-{d:02d} 03:30", f"2026-09-{d:02d}T01:30:00+00:00", [SLUG], slug=f"own{d}") for d in range(1, 11)]
    manual = entry("Schul-Cockpit 0.34.0", "2026-08-30T06:20:47+00:00", [SLUG], slug="manual")
    full = entry("Schul-Cockpit 0.63.0 2026-08-29 03:30", "2026-08-29T01:30:00+00:00", [SLUG, "core_mariadb"], slug="mixed")
    ha = entry("Vollsicherung", "2026-08-28T01:00:00+00:00", [SLUG], ha=True, slug="full")
    prune = backup.to_prune(own + [manual, full, ha], SLUG)
    assert sorted(b["slug"] for b in prune) == ["own1", "own2", "own3"], "die drei ältesten eigenen Nachtsicherungen"
