"""Der Nutzungsbericht für Eltern: wie die App in einer Woche genutzt wurde.

Er beschreibt, er bewertet nicht. Nutzungszahlen sind kein Erfolgsziel
(VISION „Erfolg messen“), es gibt keine Note, keinen Score und keinen
Vergleich zwischen Geschwistern (D72). Jede Auffälligkeit trägt vier Teile:
was beobachtet wurde, den Beleg, eine mögliche Deutung und was die App nicht
sehen kann (D126 G17/G18). Sichtbar nur für Eltern.

Quellen sind die Zeitstempel, die die App ohnehin speichert, dazu seit
1.13.17 die Art jeder Anfrage an den Mentor und die Nutzungszeit je Tag
(`usage_days`, 90 Tage). Kein Modellaufruf.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import day_close
from .db import webapp_conn
from .learning import today_local
from .subject_names import label as subject_label
from .week_review import _has, _short, week_bounds

TZ = ZoneInfo("Europe/Berlin")
# Nach 22 Uhr oder vor halb sieben gilt als spät bzw. früh.
LATE = time(22, 0)
EARLY = time(6, 30)
# „Weiß ich nicht“ in höchstens so vielen Sekunden gilt als schnell aufgedeckt.
FAST_SECONDS = 3
FAST_SERIES = 15
# Eine Pause über zehn Minuten trennt zwei Blöcke.
GAP = timedelta(minutes=10)
KEEP_DAYS = 90
MODES = {"homework_help": "Hausaufgabenhilfe", "homework_check": "Kontrolle", "topic": "Thema üben"}
HELP_KINDS = {"hint", "example"}
VIEW_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,29}$")


def local(ts) -> datetime | None:
    """Ein gespeicherter Zeitstempel in Berliner Ortszeit; ohne Zone gilt er als
    Ortszeit, Unlesbares fällt weg."""
    try:
        dt = datetime.fromisoformat(str(ts or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)


def _odd_hour(dt: datetime) -> bool:
    return dt.time() >= LATE or dt.time() < EARLY


def _blocks(times: list[datetime]) -> list[tuple[datetime, datetime]]:
    out: list[list[datetime]] = []
    for t in sorted(times):
        if out and t - out[-1][1] <= GAP:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [(a, b) for a, b in out]


def _minutes(times: list[datetime]) -> int:
    """Grobe Arbeitszeit aus Zeitstempeln: jeder Block zählt von seinem ersten
    bis zum letzten Ereignis plus eine Minute."""
    return sum(int((b - a).total_seconds() // 60) + 1 for a, b in _blocks(times))


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _warn(title: str, evidence: str, meaning: str, unseen: str) -> dict:
    return {"title": title, "evidence": evidence, "meaning": meaning, "unseen": unseen}


def week(account_id: int, today: date | None = None) -> dict:
    today = today or today_local()
    start, end = week_bounds(today)
    # Einen Tag Rand auf beiden Seiten: gespeichert wird oft in UTC, ein Abend
    # nach Mitternacht Berliner Zeit stünde sonst im falschen Tag.
    lo, hi = (start - timedelta(days=1)).isoformat(), (end + timedelta(days=1)).isoformat()

    def inweek(dt):
        return dt is not None and start <= dt.date() <= end

    with closing(webapp_conn()) as c:
        args = (account_id, lo, hi)
        messages = [dict(r) for r in c.execute(
            "SELECT m.session_id,m.created_at,m.payload,s.subject,s.source_json FROM mentor_messages m "
            "JOIN mentor_sessions s ON s.id=m.session_id WHERE m.account_id=? AND m.role='user' "
            "AND s.is_test=0 AND s.is_demo=0 AND substr(m.created_at,1,10) BETWEEN ? AND ?", args)]
        opened = [dict(r) for r in c.execute(
            "SELECT s.id,s.created_at,s.subject,s.source_json FROM mentor_sessions s WHERE s.account_id=? "
            "AND s.is_test=0 AND s.is_demo=0 AND substr(s.created_at,1,10) BETWEEN ? AND ? "
            "AND NOT EXISTS (SELECT 1 FROM mentor_messages m WHERE m.session_id=s.id AND m.role='user')", args)]
        evidence = [dict(r) for r in c.execute(
            "SELECT e.session_id,e.created_at,e.help_used,e.result FROM mentor_evidence e "
            "JOIN mentor_sessions s ON s.id=e.session_id WHERE e.account_id=? AND e.invalidated=0 "
            "AND s.is_test=0 AND s.is_demo=0 AND substr(e.created_at,1,10) BETWEEN ? AND ?", args)]
        vocab, solved = [], {}
        if _has(c, "vocab_attempts"):
            vocab = [dict(r) for r in c.execute(
                "SELECT word_id,created_at,result,answer,seconds FROM vocab_attempts WHERE account_id=? "
                "AND substr(created_at,1,10) BETWEEN ? AND ? ORDER BY created_at,id", args)]
            solved = {r[0]: r[1] for r in c.execute(
                "SELECT word_id,MAX(created_at) FROM vocab_attempts WHERE account_id=? AND result='correct' "
                "GROUP BY word_id", (account_id,))}
        done = [dict(r) for r in c.execute(
            "SELECT completed_at,due_date FROM tasks WHERE account_id=? AND status='done' AND completed_at IS NOT NULL "
            "AND substr(completed_at,1,10) BETWEEN ? AND ?", args)]
        overdue = c.execute(
            "SELECT COUNT(*) FROM tasks WHERE account_id=? AND status IN ('open','in_progress') AND due_date IS NOT NULL "
            "AND due_date<?", (account_id, today.isoformat())).fetchone()[0]
        checkins = [dict(r) for r in c.execute(
            "SELECT k.created_at,k.rating,u.role,u.is_admin FROM lesson_checkins k LEFT JOIN users u ON u.id=k.user_id "
            "WHERE k.account_id=? AND substr(k.created_at,1,10) BETWEEN ? AND ?", args)]
        uploads = [dict(r) for r in c.execute(
            "SELECT created_at FROM materials WHERE account_id=? AND hidden=0 AND COALESCE(origin,'upload')!='book_fetch' "
            "AND substr(created_at,1,10) BETWEEN ? AND ?", args)]
        afternoon = [dict(r) for r in c.execute(
            "SELECT created_at FROM afternoon_checks WHERE account_id=? AND substr(created_at,1,10) BETWEEN ? AND ?",
            args)] if _has(c, "afternoon_checks") else []
        usage = [dict(r) for r in c.execute(
            "SELECT day,actor,first_at,last_at,opens,active_seconds,views_json FROM usage_days "
            "WHERE account_id=? AND day BETWEEN ? AND ?", (account_id, start.isoformat(), end.isoformat()))] \
            if _has(c, "usage_days") else []

    # Wann war das Kind tätig? Nur Handlungen, keine abgeleiteten Zustände.
    child_checkins = [k for k in checkins if not (k["is_admin"] or k["role"] in ("admin", "parent"))]
    stamps = [local(r["created_at"]) for r in messages + vocab + uploads + afternoon + child_checkins]
    stamps += [local(r["completed_at"]) for r in done]
    stamps = [t for t in stamps if inweek(t)]
    days: dict[str, list[datetime]] = defaultdict(list)
    for t in stamps:
        days[t.date().isoformat()].append(t)
    active_days = [{"day": d, "label": _short(d), "from": min(ts).strftime("%H:%M"), "to": max(ts).strftime("%H:%M")}
                   for d, ts in sorted(days.items())]
    odd = sorted({(t.date().isoformat(), t.strftime("%H:%M")) for t in stamps if _odd_hour(t)})
    odd_days: dict[str, list[str]] = defaultdict(list)
    for d, hm in odd:
        odd_days[d].append(hm)

    # App-Zeit aus dem Herzschlag des Frontends, getrennt nach Kind und Eltern.
    app = {"child_minutes": 0, "parent_minutes": 0, "opens": 0, "views": {}, "measured_days": 0}
    views: dict[str, int] = defaultdict(int)
    for u in usage:
        key = "child_minutes" if u["actor"] == "child" else "parent_minutes"
        app[key] += round((u["active_seconds"] or 0) / 60)
        if u["actor"] == "child":
            app["opens"] += u["opens"] or 0
            app["measured_days"] += 1
            for view, sec in json.loads(u["views_json"] or "{}").items():
                views[view] += int(sec)
    app["views"] = {k: round(v / 60) for k, v in sorted(views.items(), key=lambda x: -x[1]) if v >= 60}

    # Mentor: Einheiten, in denen das Kind in dieser Woche geschrieben hat.
    by_session: dict[int, dict] = {}
    for m in messages:
        t = local(m["created_at"])
        if not inweek(t):
            continue
        entry = by_session.setdefault(m["session_id"], {
            "subject": subject_label(m["subject"] or ""), "times": [], "turns": 0, "help": 0,
            "mode": MODES.get((json.loads(m["source_json"] or "{}") or {}).get("mode"), "Üben")})
        entry["times"].append(t)
        entry["turns"] += 1
        kind = (json.loads(m["payload"] or "{}") or {}).get("kind")
        if kind in HELP_KINDS:
            entry["help"] += 1
    own = defaultdict(int)
    for e in evidence:
        if inweek(local(e["created_at"])) and not e["help_used"]:
            own[e["session_id"]] += 1
    units = []
    for sid, e in by_session.items():
        units.append({"session_id": sid, "subject": e["subject"], "mode": e["mode"], "turns": e["turns"],
                      "help": e["help"], "own_evidence": own.get(sid, 0), "minutes": _minutes(e["times"]),
                      "day": _short(min(e["times"]).date().isoformat())})
    units.sort(key=lambda u: u["day"])
    modes: dict[str, int] = defaultdict(int)
    for u in units:
        modes[u["mode"]] += 1
    not_started = [{"subject": subject_label(o["subject"] or ""), "day": _short(local(o["created_at"]).date().isoformat())}
                   for o in opened if inweek(local(o["created_at"]))]

    # Vokabeln: richtig, falsch, aufgedeckt; und ob Aufgedecktes später sitzt.
    week_vocab = [v for v in vocab if inweek(local(v["created_at"]))]
    dont_know = [v for v in week_vocab if v["result"] != "correct" and not (v["answer"] or "").strip()]
    correct = sum(1 for v in week_vocab if v["result"] == "correct")
    revealed_words = {v["word_id"]: v["created_at"] for v in dont_know}
    later = sum(1 for w, at in revealed_words.items() if solved.get(w) and solved[w] > at)
    run, longest, run_words = 0, 0, []
    current_words: list[int] = []
    for v in week_vocab:
        fast = v in dont_know and v["seconds"] is not None and v["seconds"] <= FAST_SECONDS
        run = run + 1 if fast else 0
        current_words = current_words + [v["word_id"]] if fast else []
        if run > longest:
            longest, run_words = run, list(current_words)
    run_later = sum(1 for w in set(run_words) if solved.get(w) and solved[w] > revealed_words.get(w, ""))
    vocab_blocks = _blocks([local(v["created_at"]) for v in week_vocab])
    vocab_view = {"attempts": len(week_vocab), "correct": correct, "dont_know": len(dont_know),
                  "wrong": len(week_vocab) - correct - len(dont_know), "revealed_words": len(revealed_words),
                  "revealed_later_correct": later, "blocks": len(vocab_blocks),
                  "minutes": sum(int((b - a).total_seconds() // 60) + 1 for a, b in vocab_blocks),
                  "fast_series": longest}

    # Aufgaben: wann erledigt, gemessen am Fälligkeitstag.
    timing = {"before": 0, "on_due": 0, "after": 0, "undated": 0}
    for t in done:
        at = local(t["completed_at"])
        if not inweek(at):
            continue
        if not t["due_date"]:
            timing["undated"] += 1
        elif at.date().isoformat() < t["due_date"]:
            timing["before"] += 1
        elif at.date().isoformat() == t["due_date"]:
            timing["on_due"] += 1
        else:
            timing["after"] += 1

    # Check-ins: wie viele, von wem, und wie viele im Block mit gleicher Bewertung.
    week_checkins = [k for k in checkins if inweek(local(k["created_at"]))]
    kid_checkins = [k for k in week_checkins if k in child_checkins]
    series = []
    ordered = sorted(kid_checkins, key=lambda k: local(k["created_at"]))
    group: list[dict] = []
    for k in ordered + [None]:
        if k is not None and group and local(k["created_at"]) - local(group[-1]["created_at"]) <= timedelta(seconds=20):
            group.append(k)
            continue
        if len(group) >= 4:
            series.append({"count": len(group), "same": len({g["rating"] for g in group}) == 1})
        group = [k] if k is not None else []
    checkin_view = {"count": len(week_checkins), "by_child": len(kid_checkins),
                    "by_parent": len(week_checkins) - len(kid_checkins),
                    "days": len({local(k["created_at"]).date() for k in kid_checkins}),
                    "series": len(series), "uniform_series": sum(1 for s in series if s["same"])}

    upload_view = {"pages": sum(1 for u in uploads if inweek(local(u["created_at"]))),
                   "days": len({local(u["created_at"]).date() for u in uploads if inweek(local(u["created_at"]))})}

    closing_week = (day_close.reliability(account_id, today, weeks=1).get("current")
                    or {"evenings": 0, "closed": 0, "own": 0})
    open_evenings = max(0, (closing_week.get("evenings") or 0) - (closing_week.get("closed") or 0))

    warnings = []
    if len(not_started) >= 2:
        warnings.append(_warn(
            f"{len(not_started)} Mentor-Einheiten geöffnet, ohne eigene Antwort",
            ", ".join(f"{n['subject']} am {n['day']}" for n in not_started[:4]),
            "Der Einstieg hat vielleicht nicht gepasst, oder es wurde nur hineingeschaut.",
            "Ob stattdessen anders gearbeitet wurde, etwa auf Papier."))
    for u in units:
        if u["help"] >= 3 and u["help"] * 2 >= u["turns"] and not u["own_evidence"]:
            warnings.append(_warn(
                f"Viel Hilfe, keine Aufgabe ohne Hilfe gelöst ({u['subject']})",
                f"{u['mode']} am {u['day']}: {u['help']} Hilfeanfragen in {u['turns']} Nachrichten.",
                "Das Kind hing wirklich fest, oder es hat sich die Lösung Schritt für Schritt geholt.",
                "Ob es dieselbe Art Aufgabe danach allein kann; das zeigt erst eine spätere Übung."))
    if longest >= FAST_SERIES and run_later * 2 < len(set(run_words)):
        warnings.append(_warn(
            "Vokabeln schnell aufgedeckt, ohne dass sie später saßen",
            f"{longest} „Weiß ich nicht“ hintereinander in höchstens {FAST_SECONDS} Sekunden; "
            f"danach richtig: {run_later} von {len(set(run_words))} Wörtern.",
            "Durchgeklickt statt nachgedacht, oder die Wörter waren wirklich alle neu.",
            "Ob außerhalb der App gelernt wurde."))
    if odd_days:
        warnings.append(_warn(
            "Nutzung spät am Abend oder früh am Morgen",
            "; ".join(f"{_short(d)} {', '.join(hms[:3])}" for d, hms in sorted(odd_days.items())[:4]),
            "Eine Aufgabe kurz vor der Frist, oder es wurde Schlafenszeit.",
            "Ob das Gerät eines Elternteils benutzt wurde; ein Gespräch gilt immer als Gespräch des Kindes (D82)."))
    if overdue:
        warnings.append(_warn(
            f"{_plural(overdue, 'Aufgabe', 'Aufgaben')} überfällig",
            "Offen mit einem Fälligkeitstag in der Vergangenheit.",
            "Vergessen, oder erledigt und nur nicht abgehakt.",
            "Was außerhalb der App erledigt oder mit der Lehrkraft geklärt wurde."))
    if open_evenings >= 3:
        warnings.append(_warn(
            f"An {open_evenings} Abenden vor einem Schultag blieb etwas offen",
            f"{closing_week.get('closed', 0)} von {closing_week.get('evenings', 0)} Abenden abgeschlossen.",
            "Der Abend lief ohne Blick in die App, oder es gab wirklich nichts zu tun.",
            "Was ohne App vorbereitet wurde."))

    minutes = sum(u["minutes"] for u in units)
    head = [f"{_plural(len(active_days), 'Tag', 'Tage')} aktiv",
            _plural(len(units), "Mentor-Einheit", "Mentor-Einheiten"),
            _plural(vocab_view["blocks"], "Vokabelblock", "Vokabelblöcke")]
    if app["measured_days"]:
        head.append(f"rund {app['child_minutes']} Min. in der App")
    head.append(_plural(len(warnings), "Auffälligkeit", "Auffälligkeiten"))

    lines = [f"Aktiv an {_plural(len(active_days), 'Tag', 'Tagen')}"
             + (": " + ", ".join(f"{d['label']} {d['from']}–{d['to']}" for d in active_days) if active_days else ".")]
    if app["measured_days"]:
        lines.append(f"In der App rund {app['child_minutes']} Minuten, {app['opens']}-mal geöffnet"
                     + (f"; auf dem Elternkonto {app['parent_minutes']} Minuten." if app["parent_minutes"] else "."))
    if units:
        lines.append(f"Mentor: {_plural(len(units), 'Einheit', 'Einheiten')}, rund {minutes} Minuten ("
                     + ", ".join(f"{n}× {m}" for m, n in sorted(modes.items())) + f"), {sum(u['help'] for u in units)} Hilfeanfragen, "
                     + f"{sum(u['own_evidence'] for u in units)} Aufgaben ohne Hilfe gelöst.")
    else:
        lines.append("Keine Mentor-Einheit mit eigener Antwort.")
    if vocab_view["attempts"]:
        lines.append(f"Vokabeln: {vocab_view['attempts']} Abfragen in {_plural(vocab_view['blocks'], 'Block', 'Blöcken')}, "
                     f"{correct} richtig, {vocab_view['wrong']} falsch, {len(dont_know)}× aufgedeckt"
                     + (f"; von {len(revealed_words)} aufgedeckten Wörtern später {later} richtig." if revealed_words else "."))
    lines.append(f"Aufgaben erledigt: {timing['before']} vor dem Fälligkeitstag, {timing['on_due']} am Tag selbst, "
                 f"{timing['after']} danach" + (f", {timing['undated']} ohne Termin" if timing["undated"] else "")
                 + (f"; {overdue} überfällig." if overdue else "."))
    lines.append(f"Check-ins: {checkin_view['by_child']} vom Kind an {_plural(checkin_view['days'], 'Tag', 'Tagen')}"
                 + (f", {checkin_view['by_parent']} von Eltern" if checkin_view["by_parent"] else "") + ".")
    if upload_view["pages"]:
        lines.append(f"Material: {_plural(upload_view['pages'], 'Seite', 'Seiten')} an {_plural(upload_view['days'], 'Tag', 'Tagen')} abgelegt.")

    return {"week": {"start": start.isoformat(), "end": end.isoformat(), "label": f"{_short(start.isoformat())} bis {_short(end.isoformat())}"},
            "headline": " · ".join(head), "lines": lines, "warnings": warnings,
            "active_days": active_days, "late": [{"day": _short(d), "times": t} for d, t in sorted(odd_days.items())],
            "app": app, "mentor": {"units": units, "modes": dict(modes), "minutes": minutes, "not_started": not_started},
            "vocab": vocab_view, "tasks": {**timing, "overdue": overdue}, "checkins": checkin_view,
            "uploads": upload_view, "evenings": {**closing_week, "open": open_evenings}}


def record_ping(account_id: int, actor: str, view: str, seconds: int, opened: bool, now: datetime | None = None) -> None:
    """Ein Herzschlag des Frontends: so viele Sekunden war die App sichtbar,
    in dieser Ansicht. Gespeichert wird nur die Tagessumme, kein Klickprotokoll."""
    now = (now or datetime.now(TZ)).astimezone(TZ)
    day, stamp = now.date().isoformat(), now.isoformat(timespec="seconds")
    seconds = max(0, min(int(seconds or 0), 120))
    view = view if VIEW_PATTERN.match(view or "") else "sonst"
    with closing(webapp_conn()) as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            row = c.execute("SELECT views_json FROM usage_days WHERE account_id=? AND day=? AND actor=?",
                            (account_id, day, actor)).fetchone()
            views = json.loads(row["views_json"]) if row else {}
            if seconds:
                views[view] = views.get(view, 0) + seconds
            if row:
                c.execute("UPDATE usage_days SET last_at=?,opens=opens+?,active_seconds=active_seconds+?,views_json=? "
                          "WHERE account_id=? AND day=? AND actor=?",
                          (stamp, int(opened), seconds, json.dumps(views), account_id, day, actor))
            else:
                c.execute("INSERT INTO usage_days(account_id,day,actor,first_at,last_at,opens,active_seconds,views_json) "
                          "VALUES(?,?,?,?,?,?,?,?)", (account_id, day, actor, stamp, stamp, int(opened), seconds, json.dumps(views)))
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise


def purge(today: date | None = None) -> int:
    """Nutzungstage älter als 90 Tage löschen."""
    cutoff = ((today or today_local()) - timedelta(days=KEEP_DAYS)).isoformat()
    with closing(webapp_conn()) as c:
        return c.execute("DELETE FROM usage_days WHERE day<?", (cutoff,)).rowcount
