"""Eltern passen den Lernplan eines Tages an (D214).

Der Plan eines Tages wird berechnet und festgehalten (D180); was Eltern daran
ändern, steht getrennt in ``study_plan_changes`` und wird bei jedem Lesen auf die
festgehaltene Liste angewendet. So bleibt nachvollziehbar, was die App geplant
und was ein Elternteil geändert hat, und „Zurücksetzen“ stellt den Plan wieder her.

Einfach: weniger (streicht den letzten offenen Schritt) und mehr (holt den
nächsten Schritt dazu). Erweitert: einen Schritt streichen oder aus der Liste
der übrigen Schritte hinzufügen. Hinzugefügtes zählt als Pflicht, Gestrichenes
nie als versäumt. Anpassen lässt sich der Plan von heute (am Wochenende die
Freitagsliste) und der des nächsten Schultags. Ist der nächste Schultag noch
nicht festgehalten, wirken „weniger“ und „mehr“ als Anzahl, die beim Festhalten
am Morgen in einzelne Schritte übersetzt wird.
"""
from __future__ import annotations

import json
import logging
from contextlib import closing
from datetime import date, timedelta

from .db import tx, webapp_conn

LOG = logging.getLogger("schul_cockpit.plan_adjust")

ACTIONS = ("drop", "add", "less", "more")


def rows(account_id: int, day: date) -> list[dict]:
    try:
        with closing(webapp_conn()) as c:
            return [dict(r) for r in c.execute(
                "SELECT id,action,step_key,step_json,user_id,created_at FROM study_plan_changes "
                "WHERE account_id=? AND day=? ORDER BY id", (account_id, day.isoformat()))]
    except Exception:
        return []  # Tabelle entsteht mit der Migration; vorher gibt es keine Änderungen


def apply(account_id: int, day: date, steps: list[dict], changes: list[dict] | None = None,
          candidates=None) -> list[dict]:
    """Die Liste des Tages mit den Änderungen der Eltern, in ihrer Reihenfolge.
    ``candidates`` (nur für noch nicht festgehaltene Tage): liefert auf Abruf die
    übrigen Schritte, aus denen „mehr“ den nächsten nimmt."""
    out = [dict(s) for s in steps]
    for r in rows(account_id, day) if changes is None else changes:
        keys = {s["key"] for s in out}
        if r["action"] == "drop":
            out = [s for s in out if s["key"] != r["step_key"]]
        elif r["action"] == "add" and r["step_key"] not in keys and r["step_json"]:
            out.append({**json.loads(r["step_json"]), "by_parent": True})
        elif r["action"] == "less":
            if out:
                out.pop()
        elif r["action"] == "more" and candidates is not None:
            nxt = next((c for c in candidates() if c["key"] not in keys), None)
            if nxt:
                out.append({**nxt, "by_parent": True})
    return out


def candidates(account_id: int, day: date, current: list[dict], raw: list[dict] | None = None) -> list[dict]:
    """Was sich noch hinzufügen lässt: gestrichene Schritte der Liste zuerst, dann
    die übrigen Schritte der Arbeiten (die im Notfall-Fenster zuerst, sonst nach
    Termin, je Arbeit in der Reihenfolge des Plans), dann das Vokabelpensum."""
    from . import study_plan as sp
    have = {s["key"] for s in current}
    out: list[dict] = []

    def take(st):
        if st["key"] not in have and all(o["key"] != st["key"] for o in out):
            out.append({k: v for k, v in st.items() if k not in ("done", "skipped", "waiting", "by_parent", "attempt_id")})

    for st in raw or []:
        take(st)
    ordered = sorted(sp.plans(account_id, day), key=lambda p: p["exam_date"])
    focus = sp._focus(account_id, day, ordered)
    for p in sorted(ordered, key=lambda p: (p["exam_key"] not in focus, p["exam_date"])):
        for st in p.get("all_steps") or []:
            take(st)
    for v in sp._vocab(account_id, day):
        take(sp._vocab_step(v))
    return out


def materialize(account_id: int, day: date, raw: list[dict]) -> None:
    """Beim Festhalten eines Tages: „weniger“ und „mehr“ werden einzelne Schritte,
    damit die Liste über den Tag gleich bleibt."""
    changes = rows(account_id, day)
    if not any(r["action"] in ("less", "more") for r in changes):
        return
    steps = [dict(s) for s in raw]
    concrete: list[tuple[str, str, str | None, int | None, str]] = []
    pool = None
    for r in changes:
        keys = {s["key"] for s in steps}
        if r["action"] == "drop":
            steps = [s for s in steps if s["key"] != r["step_key"]]
            concrete.append(("drop", r["step_key"], None, r["user_id"], r["created_at"]))
        elif r["action"] == "add":
            if r["step_key"] not in keys and r["step_json"]:
                steps.append(json.loads(r["step_json"]))
            concrete.append(("add", r["step_key"], r["step_json"], r["user_id"], r["created_at"]))
        elif r["action"] == "less" and steps:
            gone = steps.pop()
            concrete.append(("drop", gone["key"], None, r["user_id"], r["created_at"]))
        elif r["action"] == "more":
            if pool is None:
                pool = candidates(account_id, day, steps, raw)
            nxt = next((c for c in pool if c["key"] not in keys), None)
            if nxt:
                steps.append(nxt)
                concrete.append(("add", nxt["key"], json.dumps(nxt, ensure_ascii=False), r["user_id"], r["created_at"]))
    with closing(webapp_conn()) as c, tx(c):
        c.execute("DELETE FROM study_plan_changes WHERE account_id=? AND day=?", (account_id, day.isoformat()))
        c.executemany("INSERT INTO study_plan_changes(account_id,day,action,step_key,step_json,user_id,created_at) "
                      "VALUES(?,?,?,?,?,?,?)", [(account_id, day.isoformat(), *row) for row in concrete])


def days(account_id: int, today: date) -> list[dict]:
    """Die Tage, die sich anpassen lassen: die Liste von heute (am Wochenende die
    vom letzten Schultag) und der nächste Schultag."""
    from . import rewards, study_plan as sp
    carry = sp.carry_day(account_id, today)
    first = carry or today
    ahead = rewards.school_days(account_id, today + timedelta(days=1), today + timedelta(days=21))
    out = [{"day": first, "label": "Heute" if not carry else f"Liste vom {sp._weekday(carry)} (gilt bis zum nächsten Schultag)"}]
    if ahead and ahead[0] != first:
        out.append({"day": ahead[0], "label": f"Nächster Schultag, {sp._weekday(ahead[0])} {sp._de(ahead[0].isoformat())}"})
    return out


def state(account_id: int, day: date, today: date) -> dict:
    """Plan eines Tages für die Eltern: Schritte mit Stand, was sich hinzufügen
    lässt und was schon geändert wurde."""
    from . import study_plan as sp
    raw = sp.stored_raw(account_id, day)
    frozen = raw is not None
    base = raw if frozen else sp.compute(account_id, day)
    changes = rows(account_id, day)
    pool = lambda: candidates(account_id, day, base, raw)  # noqa: E731
    steps = apply(account_id, day, base, changes, candidates=pool)
    checked = sp.mark_done(account_id, steps, day, max(day, today)) if steps else []
    names = _names([r["user_id"] for r in changes])
    log = [{"action": r["action"], "title": (json.loads(r["step_json"])["title"] if r["step_json"]
                                             else next((s["title"] for s in base if s["key"] == r["step_key"]), "")),
            "at": r["created_at"], "by": names.get(r["user_id"], "")} for r in changes]
    return {"day": day.isoformat(), "frozen": frozen,
            "steps": [{k: s.get(k) for k in ("key", "kind", "title", "subject", "exam_date", "format", "done",
                                               "skipped", "by_parent")} for s in checked],
            "open": sum(1 for s in checked if not s["done"]), "total": len(checked),
            "candidates": [{k: s.get(k) for k in ("key", "kind", "title", "subject", "exam_date", "format")}
                           for s in candidates(account_id, day, steps, raw)],
            "changes": log}


def _names(user_ids: list[int | None]) -> dict[int, str]:
    ids = sorted({u for u in user_ids if u})
    if not ids:
        return {}
    with closing(webapp_conn()) as c:
        return {r[0]: r[1] or "" for r in c.execute(
            f"SELECT id,display_name FROM users WHERE id IN ({','.join('?' * len(ids))})", ids)}


def change(account_id: int, day: date, today: date, action: str, key: str | None, user_id: int | None) -> dict:
    """Eine Änderung festhalten. Bei einem festgehaltenen Tag werden „weniger“ und
    „mehr“ gleich zu einem bestimmten Schritt; „reset“ nimmt alles zurück."""
    from . import study_plan as sp
    from .learning import now_iso
    if action == "reset":
        with closing(webapp_conn()) as c, tx(c):
            c.execute("DELETE FROM study_plan_changes WHERE account_id=? AND day=?", (account_id, day.isoformat()))
        return state(account_id, day, today)
    if action not in ACTIONS:
        raise ValueError("Unbekannte Änderung")
    raw = sp.stored_raw(account_id, day)
    base = raw if raw is not None else sp.compute(account_id, day)
    changes = rows(account_id, day)
    pool = lambda: candidates(account_id, day, base, raw)  # noqa: E731
    current = apply(account_id, day, base, changes, candidates=pool)
    step_key, step_json = key, None
    if raw is not None and action == "less":
        checked = sp.mark_done(account_id, current, day, max(day, today))
        last = next((s for s in reversed(checked) if not s["done"]), None)
        if not last:
            raise LookupError("Es ist nichts mehr offen.")
        action, step_key = "drop", last["key"]
    elif raw is not None and action == "more":
        nxt = next(iter(candidates(account_id, day, current, raw)), None)
        if not nxt:
            raise LookupError("Es gibt keinen weiteren Schritt.")
        action, step_key, step_json = "add", nxt["key"], json.dumps(nxt, ensure_ascii=False)
    elif action == "drop":
        if not any(s["key"] == key for s in current):
            raise LookupError("Dieser Schritt steht nicht im Plan.")
    elif action == "add":
        found = next((s for s in candidates(account_id, day, current, raw) if s["key"] == key), None)
        if not found:
            raise LookupError("Dieser Schritt lässt sich nicht hinzufügen.")
        step_json = json.dumps(found, ensure_ascii=False)
    elif action == "less" and not current:
        raise LookupError("Es ist nichts mehr offen.")
    with closing(webapp_conn()) as c, tx(c):
        c.execute("INSERT INTO study_plan_changes(account_id,day,action,step_key,step_json,user_id,created_at) VALUES(?,?,?,?,?,?,?)",
                  (account_id, day.isoformat(), action, step_key, step_json, user_id, now_iso()))
    from .request_cache import forget
    forget()
    return state(account_id, day, today)
