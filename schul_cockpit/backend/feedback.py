"""Rückmeldung, aus der ein Kind lernt (D207). Gemeinsam für alle bewerteten
Übungen: je Aufgabe, was Punkte gebracht hat, wo und warum Punkte verloren
gingen und was genau gefehlt hat, die volle Lösung auf dem Weg des Kindes
und ein nächster Schritt; über allem, was schon sitzt, wo die meisten Punkte
liegen blieben und was als Nächstes geübt wird."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .learning import InputModel

# Warum Punkte verloren gingen; die Zusammenfassung bündelt danach.
LOSS_KINDS = {
    "nicht_bearbeitet": "Nicht bearbeitet",
    "unvollstaendig": "Unvollständig",
    "rechenweg": "Rechenweg oder Begründung fehlt",
    "rechenfehler": "Rechen- oder Flüchtigkeitsfehler",
    "ansatz": "Falscher Ansatz",
    "regel": "Regel, Formel oder Fachbegriff",
    "aufgabe": "Aufgabe nicht genau gelesen",
    "form": "Darstellung",
    "sprache": "Rechtschreibung oder Grammatik",
    "wortschatz": "Wort nicht gewusst",
}
LossKind = Literal["nicht_bearbeitet", "unvollstaendig", "rechenweg", "rechenfehler", "ansatz",
                   "regel", "aufgabe", "form", "sprache", "wortschatz"]
Half = dict(ge=0, le=20, multiple_of=0.5, allow_inf_nan=False)


# Qualitätssicherung beim Bewerten (D217): Die Musterlösung kann irren. Eine
# fachlich richtige Antwort verliert nie Punkte, weil sie von einer falschen
# Musterlösung abweicht.
QUALITY_RULES = (
    "Rechne jede Aufgabe selbst nach, bevor du bewertest; traue der Musterlösung nicht blind. Ist loesung oder kriterien "
    "fachlich oder rechnerisch falsch, gilt das fachlich Richtige: Eine richtige Antwort bekommt die Punkte, die sie mit "
    "richtiger Musterlösung bekäme; ziehe nie Punkte ab, weil sie von einer fehlerhaften Musterlösung abweicht, und rate "
    "dann nicht zu Übungen, die das Kind nicht braucht. Setze in diesem Fall loesung_falsch=true und nenne in "
    "loesung_hinweis knapp den Fehler der Musterlösung. rechnerpruefung nennt, was eine Rechnerprüfung schon gefunden "
    "hat; sie irrt bei richtiger Lesart nicht. "
)


class Earned(InputModel):
    text: str = Field(min_length=2, max_length=300)
    points: float = Field(**Half)


class Lost(InputModel):
    points: float = Field(**Half)
    kind: LossKind
    why: str = Field(min_length=2, max_length=400)   # was fehlte oder falsch war
    fix: str = Field(min_length=2, max_length=600)   # so hätte es die Punkte gegeben


class Detail(InputModel):
    """Felder je Aufgabe, zusätzlich zu Punkten, Begründung und nächstem Schritt."""
    earned: list[Earned] = Field(default_factory=list, max_length=8)
    lost: list[Lost] = Field(default_factory=list, max_length=8)
    model: str = Field(default="", max_length=1500)  # volle Lösung, möglichst auf dem Weg des Kindes


class Summary(InputModel):
    strengths: list[str] = Field(default_factory=list, max_length=3)
    focus: list[str] = Field(default_factory=list, max_length=3)


class ManualTask(Detail):
    """Eine Aufgabe, von Eltern geprüft (D207)."""
    points: float = Field(**Half)
    rationale: str = Field(min_length=3, max_length=1200)
    next_step: str = Field(min_length=3, max_length=400)
    transcription: str = Field(default="", max_length=3000)


class ManualOverall(Summary):
    text: str = Field(default="", max_length=800)


class ManualIn(InputModel):
    # Bewertung jeder Aufgabe (Index ab 0 als Text).
    tasks: dict[str, ManualTask] = Field(max_length=20)
    overall: ManualOverall = Field(default_factory=ManualOverall)


class SuggestIn(InputModel):
    hint: str = Field(default="", max_length=1000)


TASK_RULES = (
    "Rückmeldung zum Lernen, je Aufgabe, in einfacher Sprache und in der Du-Form ans Kind: "
    "earned nennt jeden Teil, der Punkte gebracht hat, mit Punkten. "
    "lost nennt jeden Abzug einzeln: points, kind (" + ", ".join(LOSS_KINDS) + "), why sagt konkret, was fehlte oder falsch war, "
    "fix zeigt genau, was dort hätte stehen müssen, mit dem richtigen Rechenschritt, Satz oder Wort. "
    "earned zusammen ergibt points, points plus lost zusammen ergibt die Höchstpunkte der Aufgabe. "
    "Nicht bearbeitet heißt ein Abzug über alle Punkte mit kind nicht_bearbeitet und fix als kurzer Lösungsweg. "
    "model ist die vollständige Lösung für volle Punkte, wenn möglich auf dem Weg, den das Kind begonnen hat. "
)
SUMMARY_RULES = "Gesamt: strengths bis zu drei Dinge, die schon sitzen; focus bis zu drei konkrete nächste Übungsschritte, das Wichtigste zuerst. "
INSTRUCTION = TASK_RULES + SUMMARY_RULES


def balance(entry: dict, most: float) -> dict:
    """Punkte der Einzelteile passend zum Ergebnis: Nach dem Mitteln zweier
    Durchgänge kann eine halbe Punktzahl fehlen oder zu viel sein. Die größte
    Position gleicht aus, damit das Kind nachrechnen kann."""
    pts = float(entry.get("points") or 0)
    for key, want in (("lost", most - pts), ("earned", pts)):
        items = [dict(x) for x in entry.get(key) or []]
        if not items:
            continue
        diff = want - sum(float(x["points"]) for x in items)
        if diff:
            big = max(items, key=lambda x: x["points"])
            if big["points"] + diff >= 0:
                big["points"] = big["points"] + diff
        entry[key] = [x for x in items if x["points"] > 0 or key == "earned"]
    return entry


def loss_summary(feedback: dict) -> list[dict]:
    """Verlorene Punkte nach Grund, meiste zuerst."""
    sums: dict[str, float] = {}
    for k, v in feedback.items():
        if not k.isdigit() or not isinstance(v, dict) or v.get("uncertain"):
            continue
        for x in v.get("lost") or []:
            sums[x["kind"]] = sums.get(x["kind"], 0) + float(x["points"])
    return [{"kind": k, "label": LOSS_KINDS.get(k, k), "points": p}
            for k, p in sorted(sums.items(), key=lambda kv: -kv[1]) if p > 0]


def for_child(feedback: dict) -> dict:
    """Was das Kind sieht: nur die aktuelle Bewertung, keine früheren Stände (D207)."""
    out = {k: v for k, v in (feedback or {}).items() if not k.startswith("_")}
    if any(k.isdigit() for k in out):
        out["losses"] = loss_summary(out)
    return out


def apply_manual(old: dict, body: ManualIn, most: list[float]) -> dict:
    """Neue Bewertung aus der Elternprüfung; die bisherige wandert zu den
    früheren Ständen (höchstens drei), die nur Eltern sehen. Wirft ValueError
    mit einer Meldung für die Eltern."""
    if set(body.tasks) != {str(i) for i in range(len(most))}:
        raise ValueError("Bitte jede Aufgabe bewerten.")
    fb = {}
    for i, top in enumerate(most):
        x = body.tasks[str(i)]
        if x.points > top:
            raise ValueError(f"Aufgabe {i + 1}: höchstens {top:g} Punkte.")
        before = old.get(str(i)) or {}
        entry = {**x.model_dump(), "uncertain": False, "checked_by_parent": True,
                 "solution_seen": bool(before.get("solution_seen"))}
        if not entry["transcription"]:
            entry["transcription"] = before.get("transcription", "")
        fb[str(i)] = balance(entry, top)
    o = body.overall
    if o.text or o.focus or o.strengths:
        fb["overall"] = {"text": o.text, "strengths": o.strengths, "focus": o.focus}
    fb["check"] = {**{k: v for k, v in (old.get("check") or {}).items() if k in ("passes", "per_task")}, "open": [], "manual": True}
    fb["_prior"] = ((old.get("_prior") or []) + [{k: v for k, v in old.items() if k != "_prior"}])[-3:]
    return fb
