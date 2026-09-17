"""Subject-independent learning rules. No model call is needed for scheduling."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

METHODS = {
    "recall": "Wissen und Wortschatz",
    "procedure": "Verfahren und Rechenwege",
    "explain": "Zusammenhänge verstehen",
    "write": "Texte und Argumentation",
    "speak": "Sprechen und Zuhören",
    "practical": "Praktisch und kreativ arbeiten",
}
METHOD_GUIDES = {
    "recall": "Erinnere dich ohne Vorlage. Prüfe danach und verwende das Wissen in einem eigenen Beispiel.",
    "procedure": "Erkläre einen Rechen- oder Arbeitsschritt. Löse dann eine ähnliche und eine veränderte Aufgabe.",
    "explain": "Erkläre warum. Nutze eine Skizze oder ein Beispiel und begründe eine Vorhersage.",
    "write": "Prüfe den Arbeitsauftrag. Ordne deine Gedanken, schreibe selbst und überarbeite anhand der Kriterien.",
    "speak": "Sprich deine Antwort laut. Notiere danach kurz, was gelang und was du noch üben möchtest.",
    "practical": "Plane dein Vorgehen, führe es durch und halte fest, was du beobachtet oder gestaltet hast.",
}


def today_local() -> date:
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def now_iso() -> str:
    return datetime.now(ZoneInfo("Europe/Berlin")).isoformat()


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileIn(InputModel):
    school_year: str = Field(pattern=r"^20\d{2}/20\d{2}$")
    grade: int = Field(ge=1, le=13)
    region: str = Field(default="", max_length=80)
    school_type: str = Field(default="", max_length=120)
    personal_goal: str = Field(default="", max_length=500)
    daily_minutes: int = Field(default=15, ge=0, le=120)
    max_sessions: int = Field(default=2, ge=1, le=5)
    study_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], max_length=7)
    ai_enabled: bool = False
    active: bool = True

    @field_validator("study_days")
    @classmethod
    def valid_days(cls, days):
        if any(d < 0 or d > 6 for d in days) or len(set(days)) != len(days):
            raise ValueError("Wochentage müssen eindeutig zwischen 0 und 6 liegen")
        return days

    @field_validator("school_year")
    @classmethod
    def consecutive_year(cls, value):
        a, b = value.split("/")
        if int(b) != int(a) + 1:
            raise ValueError("Schuljahr muss zwei aufeinanderfolgende Jahre enthalten")
        return value


class TopicIn(InputModel):
    profile_id: int = Field(gt=0)
    subject: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    objective: str = Field(min_length=1, max_length=1200)
    method: Literal["recall", "procedure", "explain", "write", "speak", "practical"] = "explain"
    status: Literal["planned", "active", "paused", "archived"] = "active"
    priority: int = Field(default=1, ge=0, le=3)
    source_note: str = Field(default="", max_length=2000)
    target_date: date | None = None


class MaterialIn(InputModel):
    title: str = Field(min_length=1, max_length=240)
    source_kind: Literal["teacher", "book", "worksheet", "curriculum", "web", "own"] = "own"
    source_ref: str = Field(default="", max_length=1000)
    content_text: str = Field(default="", max_length=30000)
    verified: bool = False


class ActivityIn(InputModel):
    kind: Literal["preview", "practice", "transfer", "oral"] = "practice"
    afb: int = Field(default=2, ge=1, le=3)
    operator: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=3, max_length=6000)
    explanation: str = Field(default="", max_length=6000)
    hint: str = Field(default="", max_length=2000)
    solution: str = Field(min_length=1, max_length=6000)
    criteria: str = Field(min_length=1, max_length=4000)
    minutes: int = Field(default=5, ge=1, le=30)
    source_ids: list[int] = Field(default_factory=list, max_length=20)
    published: bool = False


class GeneratedPack(InputModel):
    activities: list[ActivityIn] = Field(min_length=1, max_length=4)


class GenerateIn(InputModel):
    material_ids: list[int] = Field(min_length=1, max_length=6)


class AnswerIn(InputModel):
    answer: str = Field(min_length=1, max_length=10000)


class FinishIn(InputModel):
    outcome: Literal["again", "partly", "independent"]
    difficulty: Literal["easy", "okay", "hard"] = "okay"
    minutes: int = Field(ge=1, le=120)


def next_review(streak: int, outcome: str, help_used: bool, day: date) -> tuple[int, str]:
    if outcome == "independent" and not help_used:
        streak += 1
        interval = (2, 7, 14, 30, 60)[min(streak - 1, 4)]
    else:
        streak, interval = 0, 1
    return streak, (day + timedelta(days=interval)).isoformat()


class AiEndpointMissing(RuntimeError):
    """Die Foundry, die diese Stufe bedienen soll, ist nicht eingerichtet."""


class AiTierUnknown(RuntimeError):
    """Es wurde eine Stufe angefragt, die es nicht gibt."""


# Die vier Stufen der Konfigurationsseite. „hoch" bedient das Hauptgespräch,
# „transkription" die Spracheingabe; welche Stufe den Einstieg und das
# Abschreiben übernimmt, entscheiden die Eltern in der App.
TIERS = ("hoch", "mittel", "niedrig", "transkription")
MAIN_TIER = "hoch"
SPEECH_TIER = "transkription"


def _options(name: str) -> dict:
    try:
        value = json.loads(os.environ.get(name) or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def ai_platforms() -> dict:
    """Die beiden Foundry-Zugänge als {"1": {"url", "key"}, "2": {...}}."""
    raw = _options("LEARNING_AI_PLATFORMS")
    out = {}
    for number in ("1", "2"):
        entry = raw.get(f"foundry_{number}") or {}
        out[number] = {
            "url": str(entry.get("endpunkt") or "").strip(),
            "key": str(entry.get("api_key") or "").strip(),
        }
    return out


def ai_tiers() -> dict:
    """Die Modellstufen als {stufe: {model, deployment, foundry, rate}}.

    `model` benennt das Modell und trägt Preis, Log und die Kennungen
    gespeicherter Ergebnisse. `deployment` geht in den Aufruf an die Foundry und
    entspricht dem Modellnamen, solange nichts anderes eingetragen ist."""
    raw = _options("LEARNING_AI_MODELS")
    out = {}
    for tier in TIERS:
        entry = raw.get(tier) or {}
        model = str(entry.get("modellname") or "").strip()
        deployment = str(entry.get("bereitstellungsname") or "").strip() or model
        foundry = str(entry.get("foundry") or "1").strip() or "1"
        rate = tuple(_positive(entry.get(k)) for k in ("preis_eingang", "preis_ausgang"))
        out[tier] = {
            "model": model,
            "deployment": deployment,
            "foundry": foundry if foundry in ("1", "2") else "1",
            # Beide Preise oder keiner: ein halber Satz rechnet stiller falsch als keiner.
            "rate": rate if all(x is not None for x in rate) else None,
        }
    return out


def _positive(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def ai_settings(tier: str = MAIN_TIER) -> dict:
    """Alles, was ein Aufruf dieser Stufe braucht: Modell, Deployment, Adresse,
    Schlüssel und Preissatz.

    Zeigt die Stufe auf eine Foundry ohne Adresse oder Schlüssel, endet das hier.
    Ein Rückfall auf die andere Ressource wäre die gefährlichere Antwort: Er
    würde nach einer vermeintlich abgeschlossenen Umstellung weiter Kinderdaten
    an die alte Foundry senden, ohne dass es jemand merkt."""
    tiers = ai_tiers()
    if tier not in tiers:
        raise AiTierUnknown(tier)
    entry = tiers[tier]
    platform = ai_platforms()[entry["foundry"]]
    if entry["model"] and (not platform["url"] or not platform["key"]):
        raise AiEndpointMissing(f'{tier} → Foundry {entry["foundry"]}')
    return {**entry, "url": platform["url"], "key": platform["key"], "tier": tier}


def ai_status() -> dict:
    try:
        settings = ai_settings()
    except (AiEndpointMissing, AiTierUnknown):
        return {"configured": False, "host": "", "model": ""}
    return {
        "configured": bool(settings["url"] and settings["key"] and settings["model"]),
        "host": urlsplit(settings["url"]).hostname or "",
        "model": settings["model"],
    }


def decode_profile(row) -> dict:
    p = dict(row)
    p["study_days"] = json.loads(p["study_days"])
    p["ai_enabled"] = bool(p["ai_enabled"])
    p["active"] = bool(p["active"])
    return p


def uses_responses(url: str) -> bool:
    """Keep the supplied API version; recognise both Azure preview and v1 paths."""
    return urlsplit(url).path.rstrip("/").endswith("/responses")


def model_payload(url: str, model: str, instruction: str, context: dict, images: list) -> dict:
    content = [{"type": "text", "text": json.dumps(context, ensure_ascii=False)}, *images]
    if uses_responses(url):
        converted = []
        for part in content:
            if part["type"] == "text":
                converted.append({"type": "input_text", "text": part["text"]})
            else:
                converted.append({"type": "input_image", "image_url": part["image_url"]["url"]})
        return {
            "model": model,
            "instructions": instruction,
            "input": [{"role": "user", "content": converted}],
            "store": False,
        }
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": content},
        ],
    }


def model_output(url: str, response: dict) -> str:
    if not isinstance(response, dict):
        raise ValueError("Invalid response envelope")
    if not uses_responses(url):
        return response["choices"][0]["message"]["content"]
    if response.get("status") != "completed":
        raise ValueError("Response did not complete")
    parts = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            raise ValueError("Invalid output item")
        if item.get("type") != "message" or item.get("role") != "assistant":
            continue
        for part in item.get("content", []):
            if not isinstance(part, dict):
                raise ValueError("Invalid content item")
            if part.get("type") == "refusal":
                raise ValueError("Response refused")
            if part.get("type") == "output_text":
                parts.append(part["text"])
    if not parts:
        raise ValueError("No assistant text")
    return "".join(parts)
