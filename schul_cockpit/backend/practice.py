"""Übungsarbeiten zu einer Arbeit und das Raster Thema × Anforderungsbereich (D178).

Eine Arbeit gilt als vorbereitet, wenn jedes Thema in den Anforderungsbereichen
I und II sicher sitzt. Das wird nicht geschätzt, sondern an Aufgaben gemessen:
an Übungsarbeiten auf Papier oder am Gerät und an den Aufgaben im Gespräch mit
dem Lernbegleiter. Alle landen als Antwort je Thema in ``topic_answers`` und
zählen in dasselbe Raster.

Eine Zelle ist
  offen     noch keine Aufgabe,
  unsicher  unter 60 % der Punkte,
  fast      60 bis 79 %, oder 80 % und mehr in erst einer Aufgabe,
  sicher    80 % und mehr über wenigstens zwei Aufgaben ohne Hilfe,
  bestätigt sicher und dabei in einer Probearbeit gezeigt.
Gezählt werden die letzten vier Aufgaben der Zelle; alte Fehler wachsen heraus.
Sitzt ein höherer Bereich sicher, gilt ein noch offener darunter als mit gezeigt.
"""
from __future__ import annotations

from contextlib import closing

from .db import webapp_conn

AFBS = (1, 2, 3)
AFB_NAMES = {1: "Wiedergeben", 2: "Anwenden", 3: "Übertragen"}
RECENT = 4
SURE = 0.8
NEAR = 0.6
# Das Ziel vor einer Arbeit: I und II sicher in jedem Thema. III ist Kür.
GOAL_AFB = 2

FORMATS = {
    "einstieg": {"label": "Einstiegstest", "minutes": 30,
                 "why": "Alle Themen, je eine Aufgabe zum Wiedergeben und zum Anwenden. Zeigt, wo du stehst."},
    "kurz": {"label": "Kurztest", "minutes": 20,
             "why": "Ein bis drei Themen, gezielt auf dem nächsten Niveau."},
    "mix": {"label": "Mix", "minutes": 30,
            "why": "Die schwächsten Themen gemischt, jeweils auf dem nächsten Niveau."},
    "probe": {"label": "Probearbeit", "minutes": 45,
              "why": "Wie die echte Arbeit: alle Themen, alle Bereiche, volle Zeit."},
}
MAX_TASKS = 12


def ratio_of(a: dict) -> tuple[float, float] | None:
    """Punkte und Höchstpunkte einer Antwort; Gesprächsaufgaben ohne Punkte zählen 1/½/0."""
    if a.get("result") == "uncertain":
        return None
    if a.get("points") is not None and a.get("max_points"):
        return float(a["points"]), float(a["max_points"])
    return {"correct": (1.0, 1.0), "partial": (0.5, 1.0), "incorrect": (0.0, 1.0)}.get(a.get("result"), None)


def cell(answers: list[dict]) -> dict:
    """Zustand einer Zelle aus ihren Antworten (älteste zuerst)."""
    rows = [(a, ratio_of(a)) for a in answers if not a.get("help_used")]
    rows = [(a, r) for a, r in rows if r][-RECENT:]
    helped = sum(1 for a in answers if a.get("help_used"))
    if not rows:
        return {"state": "offen", "tasks": 0, "ratio": None, "helped": helped}
    got = sum(r[0] for _, r in rows)
    most = sum(r[1] for _, r in rows)
    ratio = got / most if most else 0.0
    if ratio < NEAR:
        state = "unsicher"
    elif ratio < SURE or len(rows) < 2:
        state = "fast"
    elif any(a.get("paper_format") == "probe" for a, _ in rows):
        state = "bestaetigt"
    else:
        state = "sicher"
    return {"state": state, "tasks": len(rows), "ratio": round(ratio, 2), "helped": helped}


def is_sure(c: dict) -> bool:
    return c["state"] in ("sicher", "bestaetigt")


def row_of(answers: list[dict]) -> dict:
    """Die drei Zellen eines Themas, mit dem „mit gezeigt" von oben nach unten."""
    cells = {k: cell([a for a in answers if (a.get("afb") or 1) == k]) for k in AFBS}
    for k in (1, 2):
        if cells[k]["state"] == "offen" and any(is_sure(cells[h]) for h in AFBS if h > k):
            cells[k] = {**cells[k], "state": "sicher", "implied": True}
    level = 0
    for k in AFBS:
        if not is_sure(cells[k]):
            break
        level = k
    # Das nächste Niveau zum Üben: der niedrigste Bereich, der noch nicht sitzt.
    target = next((k for k in AFBS if not is_sure(cells[k])), 3)
    return {"cells": {str(k): v for k, v in cells.items()}, "level": level, "target": target,
            "ready": level >= GOAL_AFB}


def topics(account_id: int, exam_key: str) -> list[dict]:
    """Die Themen einer Arbeit, die ein Raster bekommen: ohne veraltete und ohne
    Vokabelthemen (die übt der Vokabeltrainer, D-Stufe C)."""
    from .lernstand import is_vocab_topic, public
    with closing(webapp_conn()) as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM exam_topics WHERE account_id=? AND exam_key=? AND stale=0 ORDER BY position,id",
            (account_id, exam_key))]
    return [public(r) for r in rows if not is_vocab_topic(r)]


def raster(account_id: int, exam_key: str) -> dict:
    items = topics(account_id, exam_key)
    ids = [t["id"] for t in items]
    answers: dict[int, list[dict]] = {i: [] for i in ids}
    if ids:
        with closing(webapp_conn()) as c:
            marks = ",".join("?" * len(ids))
            for r in c.execute(f"SELECT * FROM topic_answers WHERE account_id=? AND topic_id IN ({marks}) "
                               "ORDER BY created_at,id", (account_id, *ids)):
                answers[r["topic_id"]].append(dict(r))
    rows = []
    for t in items:
        rows.append({"id": t["id"], "title": t["title"], "detail": t["detail"], "places_label": t["places_label"],
                     "stage": t["stage"], **row_of(answers[t["id"]])})
    ready = sum(1 for r in rows if r["ready"])
    return {"topics": rows, "ready": ready, "total": len(rows), "goal_afb": GOAL_AFB,
            "afb_names": {str(k): v for k, v in AFB_NAMES.items()},
            "formats": [{"key": k, **{x: v[x] for x in ("label", "minutes", "why")}} for k, v in FORMATS.items()]}


def _weakness(r: dict) -> tuple:
    """Schwächste zuerst: niedriges Niveau, dann niedriger Anteil im Zielbereich."""
    cells = r["cells"]
    target = cells[str(r["target"])]
    return (r["level"], target["ratio"] if target["ratio"] is not None else -1, r["id"])


def slots(fmt: str, rows: list[dict], chosen: list[int] | None = None, level: int | None = None) -> list[dict]:
    """Welche Aufgaben die Arbeit bekommt: je Platz ein Thema und ein Bereich.

    ``level`` None heißt stufenweise: jedes Thema auf seinem nächsten Niveau.
    Eine Zahl heißt: gleich auf diesem Bereich, auch wenn darunter noch nicht
    alles sitzt; ein Treffer dort gilt unten mit (siehe row_of)."""
    if fmt not in FORMATS:
        raise ValueError("format")
    if not rows:
        return []
    by_id = {r["id"]: r for r in rows}
    pick = [by_id[i] for i in (chosen or []) if i in by_id]

    def aim(r):
        return level or r["target"]

    out: list[dict] = []
    if fmt == "einstieg":
        pool = pick or rows
        out = [{"topic_id": r["id"], "afb": 1} for r in pool]
        out += [{"topic_id": r["id"], "afb": 2} for r in pool][: max(0, MAX_TASKS - len(out))]
    elif fmt == "kurz":
        pool = (pick or sorted(rows, key=_weakness)[:1])[:3]
        per = 3 if len(pool) == 1 else 2
        for r in pool:
            a = aim(r)
            out += [{"topic_id": r["id"], "afb": a} for _ in range(per - 1)]
            out.append({"topic_id": r["id"], "afb": min(3, a + 1) if a < 3 else a})
    elif fmt == "mix":
        pool = (pick or [r for r in sorted(rows, key=_weakness) if not r["ready"]] or sorted(rows, key=_weakness))[:4]
        for r in pool:
            out += [{"topic_id": r["id"], "afb": aim(r)}, {"topic_id": r["id"], "afb": min(3, aim(r) + 1)}]
    elif fmt == "probe":
        pool = pick or rows
        # Wie eine echte Arbeit: etwa 40 % I, 40 % II, 20 % III, jedes Thema dabei.
        n = min(MAX_TASKS, max(6, len(pool)))
        want = [1] * round(n * .4) + [2] * round(n * .4)
        want += [3] * (n - len(want))
        order = sorted(pool, key=_weakness)
        for i, afb in enumerate(sorted(want)):
            out.append({"topic_id": order[i % len(order)]["id"], "afb": afb})
    return out[:MAX_TASKS]


def result_of(points: float, most: float, uncertain: bool) -> str:
    if uncertain:
        return "uncertain"
    if most and points / most >= SURE:
        return "correct"
    return "partial" if points > 0 else "incorrect"
