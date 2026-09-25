"""App-gezeichnete Abbildungen für Aufgaben (D197).

Sprachmodelle zeichnen freies SVG unzuverlässig: Die Lampe landet im falschen
Zweig, das Amperemeter in der falschen Leitung. Deshalb schreibt das Modell nur
eine knappe, strenge JSON-Beschreibung; die App prüft sie und zeichnet selbst.
Dieselbe Beschreibung bleibt als Text beim Modell (`describe`), es weiß also
genau, was das Bild zeigt.

Typen: schaltplan, zahlenstrahl, bruchstreifen, funktionsgraph, tabelle.
`validate` prüft und wirft ValueError mit deutscher Meldung, `render` liefert
ein eigenständiges, bereinigtes SVG (weißer Grund, feste Farben, taugt als
<img> im Dunkelmodus und im Druck), `describe` den Klartext (auch als
Alternativtext), `SPEC_HELP` die Anleitung für Prompts, `json_schema()` das
Schema. Schaltpläne setzt schemdraw (reines Python, SVG-Backend ohne
matplotlib), alles andere zeichnet das Modul selbst.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from fractions import Fraction
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

MAX_TEILE = 12          # Bauteile im Schaltplan samt Messgeräten
MAX_PARALLEL_TIEFE = 3  # Parallelschaltungen ineinander
MAX_ROH_TIEFE = 24      # Verschachtelung des JSON überhaupt
MAX_ROH_LAENGE = 20000  # Zeichen des JSON

_ID = r"^[A-Za-z][A-Za-z0-9]{0,4}$"
_SVG_NS = "http://www.w3.org/2000/svg"
_BLAU = "#1f4e9c"
_FARBEN = ["#000000", _BLAU, "#b03020", "#2e7d32"]
_STRICHE = ["", "", "7 4", "2 3"]


class _Streng(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True,
                              allow_inf_nan=False)


def _kurz(n: int, default: Any = None) -> Any:
    return Field(default, max_length=n)


# --- Schaltplan -------------------------------------------------------------

TEILE = {"lampe": "Lampe", "widerstand": "Widerstand", "schalter": "Schalter",
         "amperemeter": "Amperemeter", "voltmeter": "Voltmeter",
         "motor": "Motor", "diode": "Diode", "knoten": "Knotenpunkt"}
_MESSER = {"amperemeter", "voltmeter", "knoten"}


class Teil(_Streng):
    teil: Literal["lampe", "widerstand", "schalter", "amperemeter",
                  "voltmeter", "motor", "diode", "knoten"]
    id: str = Field(pattern=_ID)
    beschriftung: str | None = _kurz(12)
    zustand: Literal["offen", "geschlossen"] | None = None
    sperrrichtung: bool = False

    @model_validator(mode="after")
    def _passt(self) -> Teil:
        if self.teil == "schalter" and not self.zustand:
            raise ValueError(f"Schalter {self.id} braucht „zustand“: offen oder geschlossen")
        if self.zustand and self.teil != "schalter":
            raise ValueError("„zustand“ gibt es nur beim Schalter")
        if self.sperrrichtung and self.teil != "diode":
            raise ValueError("„sperrrichtung“ gibt es nur bei der Diode")
        return self


class Reihe(_Streng):
    reihe: list[Glied] = Field(min_length=1, max_length=MAX_TEILE)


class Parallel(_Streng):
    parallel: list[Glied] = Field(min_length=2, max_length=5)


def _glied_art(v: Any) -> str | None:
    if isinstance(v, dict):
        return next((k for k in ("teil", "reihe", "parallel") if k in v), None)
    return {Teil: "teil", Reihe: "reihe", Parallel: "parallel"}.get(type(v))


Glied = Annotated[
    Annotated[Teil, Tag("teil")] | Annotated[Reihe, Tag("reihe")]
    | Annotated[Parallel, Tag("parallel")],
    Discriminator(_glied_art, custom_error_type="glied",
                  custom_error_message="Jedes Glied braucht „teil“, „reihe“ oder „parallel“"),
]
Reihe.model_rebuild()
Parallel.model_rebuild()


class Quelle(_Streng):
    art: Literal["batterie", "quelle"] = "batterie"
    id: str | None = Field(None, pattern=_ID)
    beschriftung: str | None = _kurz(12)


class Messgeraet(_Streng):
    teil: Literal["voltmeter"]
    id: str = Field(pattern=_ID)
    ueber: str = _kurz(8, ...)
    beschriftung: str | None = _kurz(12)


def _blaetter(g: Any) -> list[Teil]:
    if isinstance(g, Teil):
        return [g]
    return [t for z in (g.reihe if isinstance(g, Reihe) else g.parallel)
            for t in _blaetter(z)]


def _ptiefe(g: Any) -> int:
    if isinstance(g, Teil):
        return 0
    kinder = g.reihe if isinstance(g, Reihe) else g.parallel
    return max(_ptiefe(z) for z in kinder) + (1 if isinstance(g, Parallel) else 0)


class Schaltplan(_Streng):
    type: Literal["schaltplan"]
    titel: str | None = _kurz(80)
    quelle: Quelle = Field(default_factory=Quelle)
    netz: Glied
    messgeraete: list[Messgeraet] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def _pruefen(self) -> Schaltplan:
        teile = _blaetter(self.netz)
        if len(teile) + len(self.messgeraete) > MAX_TEILE:
            raise ValueError(f"höchstens {MAX_TEILE} Bauteile samt Messgeräten")
        if _ptiefe(self.netz) > MAX_PARALLEL_TIEFE:
            raise ValueError(f"höchstens {MAX_PARALLEL_TIEFE} Parallelschaltungen ineinander")
        ids = [t.id for t in teile] + [m.id for m in self.messgeraete]
        if self.quelle.id:
            ids.append(self.quelle.id)
        doppelt = sorted({i for i in ids if ids.count(i) > 1})
        if doppelt:
            raise ValueError(f"Kennung doppelt vergeben: {', '.join(doppelt)}")
        ziele = {t.id for t in teile if t.teil != "knoten"}
        gesehen: set[str] = set()
        for m in self.messgeraete:
            ziel = "quelle" if m.ueber in ("quelle", self.quelle.id) else m.ueber
            if ziel != "quelle" and ziel not in ziele:
                raise ValueError(f"{m.id}: „ueber“ muss die Kennung eines Bauteils "
                                 "oder „quelle“ sein")
            if ziel in gesehen:
                raise ValueError(f"an {m.ueber} hängt schon ein Voltmeter")
            gesehen.add(ziel)
        return self


# --- Zahlenstrahl, Bruchstreifen, Funktionsgraph, Tabelle -------------------

Zahl = int | float | Annotated[str, Field(max_length=16)]
_ZAHL_RE = re.compile(r"^([+-]?)(?:([0-9]+)\s+)?([0-9]+(?:[.,][0-9]+)?)(?:/([0-9]+))?$")


def zahl(v: Any) -> Fraction:
    """Zahl, Dezimalzahl („1,5“), Bruch („3/4“) oder gemischte Zahl („1 1/2“)."""
    if isinstance(v, bool):
        raise ValueError("keine Zahl")
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            raise ValueError("keine endliche Zahl")
        return Fraction(str(v)).limit_denominator(1000)
    s = str(v).strip().replace("−", "-").replace(" / ", "/")
    m = _ZAHL_RE.match(s)
    if not m:
        raise ValueError(f"„{v}“ ist keine Zahl (erlaubt: 2, -1,5, 3/4, 1 1/2)")
    vz, ganz, z, n = m.groups()
    if n is not None and ("." in z or "," in z):
        raise ValueError(f"„{v}“: Bruch nur mit ganzen Zahlen")
    if ganz is not None and n is None:
        raise ValueError(f"„{v}“ ist keine Zahl")
    nenner = int(n) if n else 1
    if not 0 < nenner <= 1000:
        raise ValueError(f"„{v}“: Nenner muss zwischen 1 und 1000 liegen")
    wert = Fraction(z.replace(",", ".")) / nenner + int(ganz or 0)
    return -wert if vz == "-" else wert


class Marke(_Streng):
    wert: Zahl
    beschriftung: str | None = _kurz(12)


class Sprung(_Streng):
    von: Zahl
    bis: Zahl
    beschriftung: str | None = _kurz(12)


class Zahlenstrahl(_Streng):
    type: Literal["zahlenstrahl"]
    titel: str | None = _kurz(80)
    von: Zahl = 0
    bis: Zahl
    schritt: Zahl = 1
    unterteilung: int = Field(1, ge=1, le=10)
    marken: list[Marke] = Field(default_factory=list, max_length=20)
    spruenge: list[Sprung] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _pruefen(self) -> Zahlenstrahl:
        von, bis, schritt = zahl(self.von), zahl(self.bis), zahl(self.schritt)
        if bis <= von:
            raise ValueError("„bis“ muss größer als „von“ sein")
        if schritt <= 0:
            raise ValueError("„schritt“ muss positiv sein")
        n = (bis - von) / schritt
        if n > 40 or n < 1:
            raise ValueError("zwischen 1 und 40 Hauptstrichen („schritt“ anpassen)")
        if n * self.unterteilung > 200:
            raise ValueError("zu viele Unterteilungsstriche")
        werte = [m.wert for m in self.marken]
        werte += [w for s in self.spruenge for w in (s.von, s.bis)]
        for w in werte:
            if not von <= zahl(w) <= bis:
                raise ValueError(f"{w} liegt nicht zwischen {self.von} und {self.bis}")
        if any(zahl(s.von) == zahl(s.bis) for s in self.spruenge):
            raise ValueError("ein Sprung braucht verschiedene Start- und Zielwerte")
        return self


class Balken(_Streng):
    teile: int = Field(ge=1, le=24)
    gefaerbt: int = Field(0, ge=0, le=24)
    beschriftung: str | None = _kurz(16)

    @model_validator(mode="after")
    def _pruefen(self) -> Balken:
        if self.gefaerbt > self.teile:
            raise ValueError("„gefaerbt“ darf nicht größer als „teile“ sein")
        return self


class Bruchstreifen(_Streng):
    type: Literal["bruchstreifen"]
    titel: str | None = _kurz(80)
    balken: list[Balken] = Field(min_length=1, max_length=6)
    zeige_bruch: bool = True


class Funktion(_Streng):
    term: str = Field(min_length=1, max_length=80)
    beschriftung: str | None = _kurz(20)

    @field_validator("term")
    @classmethod
    def _term(cls, v: str) -> str:
        kompiliere(v)
        return v


class Punkt(_Streng):
    x: float
    y: float
    beschriftung: str | None = _kurz(12)


class Funktionsgraph(_Streng):
    type: Literal["funktionsgraph"]
    titel: str | None = _kurz(80)
    x_min: float = -5
    x_max: float = 5
    y_min: float = -5
    y_max: float = 5
    gitter: bool = True
    x_achse: str = _kurz(12, "x")
    y_achse: str = _kurz(12, "y")
    funktionen: list[Funktion] = Field(default_factory=list, max_length=4)
    punkte: list[Punkt] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _pruefen(self) -> Funktionsgraph:
        for a, b, n in ((self.x_min, self.x_max, "x"), (self.y_min, self.y_max, "y")):
            if not a < b:
                raise ValueError(f"{n}_min muss kleiner als {n}_max sein")
            if b - a > 10000 or b - a < 0.01 or max(abs(a), abs(b)) > 1e5:
                raise ValueError(f"{n}-Bereich unpassend (Spanne 0,01 bis 10000)")
        if not self.funktionen and not self.punkte:
            raise ValueError("mindestens eine Funktion oder ein Punkt")
        return self


class Tabelle(_Streng):
    type: Literal["tabelle"]
    titel: str | None = _kurz(80)
    kopf: list[Annotated[str, Field(max_length=20)]] = Field(min_length=1, max_length=8)
    zeilen: list[list[Annotated[str, Field(max_length=20)]]] = Field(
        default_factory=list, max_length=15)

    @field_validator("kopf", "zeilen", mode="before")
    @classmethod
    def _texte(cls, v: Any) -> Any:
        def t(x: Any) -> Any:
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                return _de(x).replace("−", "-")
            return [t(y) for y in x] if isinstance(x, list) else x
        return t(v)

    @model_validator(mode="after")
    def _pruefen(self) -> Tabelle:
        if any(len(z) != len(self.kopf) for z in self.zeilen):
            raise ValueError("jede Zeile braucht so viele Zellen wie der Kopf Spalten")
        return self


Figure = Annotated[Schaltplan | Zahlenstrahl | Bruchstreifen | Funktionsgraph | Tabelle,
                   Field(discriminator="type")]
_ADAPTER: TypeAdapter = TypeAdapter(Figure)

_FEHLER = {
    "missing": "fehlt", "extra_forbidden": "unbekanntes Feld",
    "literal_error": "unzulässiger Wert", "string_too_long": "Text zu lang",
    "too_long": "zu viele Einträge", "too_short": "zu wenige Einträge",
    "string_pattern_mismatch": "Kennung ungültig (Buchstabe, dann bis zu 4 Buchstaben/Ziffern)",
    "union_tag_invalid": "unbekannter Typ (erlaubt: schaltplan, zahlenstrahl, "
                         "bruchstreifen, funktionsgraph, tabelle)",
    "union_tag_not_found": "„type“ fehlt",
    "greater_than_equal": "Wert zu klein", "less_than_equal": "Wert zu groß",
    "int_parsing": "ganze Zahl erwartet", "int_type": "ganze Zahl erwartet",
    "float_parsing": "Zahl erwartet", "float_type": "Zahl erwartet",
    "finite_number": "endliche Zahl erwartet", "bool_type": "true oder false erwartet",
    "string_type": "Text erwartet", "list_type": "Liste erwartet",
    "model_type": "Objekt erwartet", "dict_type": "Objekt erwartet",
}


def _meldung(e: ValidationError) -> str:
    teile = []
    for err in e.errors()[:3]:
        loc: list[str] = []
        for x in err["loc"]:
            if not loc or loc[-1] != str(x):
                loc.append(str(x))
        if loc and loc[0] in _ZEICHNER:
            loc = loc[1:]
        ort = ".".join(loc)
        if err["type"] == "value_error":
            text = str(err.get("ctx", {}).get("error") or err["msg"])
        elif err["type"] == "literal_error":
            erlaubt = str(err.get("ctx", {}).get("expected", "")).replace(" or ", " oder ")
            text = f"unzulässiger Wert, erlaubt: {erlaubt}"
        else:
            text = _FEHLER.get(err["type"], err["msg"])
        teile.append(f"{ort}: {text}" if ort else text)
    return "Abbildung ungültig – " + "; ".join(teile)


def _roh_tiefe(v: Any, t: int = 0) -> int:
    if t > MAX_ROH_TIEFE:
        return t
    if isinstance(v, dict):
        return max([_roh_tiefe(x, t + 1) for x in v.values()] or [t + 1])
    if isinstance(v, list):
        return max([_roh_tiefe(x, t + 1) for x in v] or [t + 1])
    return t


def validate(spec: Any) -> Any:
    """Prüft eine Beschreibung und liefert das Modell; ValueError auf Deutsch."""
    if isinstance(spec, BaseModel):
        return spec
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except ValueError:
            raise ValueError("Abbildung ungültig – kein gültiges JSON") from None
    if not isinstance(spec, dict):
        raise ValueError("Abbildung ungültig – ein JSON-Objekt erwartet")
    try:
        if len(json.dumps(spec, ensure_ascii=False)) > MAX_ROH_LAENGE:
            raise ValueError("Abbildung ungültig – Beschreibung zu lang")
    except TypeError:
        raise ValueError("Abbildung ungültig – nur JSON-Werte erlaubt") from None
    if _roh_tiefe(spec) > MAX_ROH_TIEFE:
        raise ValueError("Abbildung ungültig – zu tief verschachtelt")
    try:
        return _ADAPTER.validate_python(spec)
    except ValidationError as e:
        raise ValueError(_meldung(e)) from None


def json_schema() -> dict:
    """JSON-Schema der Vereinigung aller Abbildungstypen."""
    return _ADAPTER.json_schema()


# --- Termparser (kein eval) --------------------------------------------------

_FUNKTIONEN: dict[str, Callable[[float], float]] = {
    "sqrt": math.sqrt, "wurzel": math.sqrt, "abs": abs, "sin": math.sin, "cos": math.cos}
_KONSTANTEN = {"pi": math.pi, "e": math.e}
_NAMEN = sorted([*_FUNKTIONEN, *_KONSTANTEN, "x"], key=len, reverse=True)
_ZIFFERN = "0123456789"
_ERSATZ = {"−": "-", "·": "*", "×": "*", "⋅": "*", "÷": "/", "π": "pi", "√": "sqrt"}


def _tokens(term: str) -> list[tuple[str, Any]]:
    s = term.lower()
    for a, b in _ERSATZ.items():
        s = s.replace(a, b)
    out: list[tuple[str, Any]] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in _ZIFFERN or (c in ".," and s[i + 1:i + 2] in tuple(_ZIFFERN)):
            m = re.match(r"[0-9]*[.,]?[0-9]+", s[i:])
            out.append(("zahl", float(m.group().replace(",", "."))))
            i += len(m.group())
        elif c.isalpha() and c.isascii():
            m = re.match(r"[a-z]+", s[i:])
            wort = m.group()
            j = 0
            while j < len(wort):
                name = next((n for n in _NAMEN if wort.startswith(n, j)), None)
                if not name:
                    raise ValueError(f"unbekannter Name „{wort}“ im Term (erlaubt: x, pi, e, "
                                     "sqrt, abs, sin, cos)")
                out.append(("fn" if name in _FUNKTIONEN else "x" if name == "x"
                            else "zahl", name if name in _FUNKTIONEN or name == "x"
                            else _KONSTANTEN[name]))
                j += len(name)
            i += len(wort)
        elif c in "+-*/^()²³":
            out.append(("op", c))
            i += 1
        else:
            raise ValueError(f"unerlaubtes Zeichen „{c}“ im Term")
    if not out:
        raise ValueError("leerer Term")
    if len(out) > 80:
        raise ValueError("Term zu lang")
    return out


def _potenz(a: float, b: float) -> float:
    if a == 0 and b < 0:
        raise ZeroDivisionError
    return math.pow(a, b)


class _Parser:
    def __init__(self, toks: list[tuple[str, Any]]) -> None:
        self.t, self.i, self.tiefe = toks, 0, 0

    def blick(self) -> tuple[str, Any] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def op(self, *zeichen: str) -> str | None:
        k = self.blick()
        if k and k[0] == "op" and k[1] in zeichen:
            self.i += 1
            return k[1]
        return None

    def summe(self) -> Callable:
        f = self.produkt()
        while (o := self.op("+", "-")):
            g = self.produkt()
            f = (lambda a, b: lambda x: a(x) + b(x))(f, g) if o == "+" else \
                (lambda a, b: lambda x: a(x) - b(x))(f, g)
        return f

    def produkt(self) -> Callable:
        f = self.vorzeichen()
        while True:
            o = self.op("*", "/")
            k = self.blick()
            if o:
                g = self.vorzeichen()
            elif k and (k[0] in ("zahl", "x", "fn") or k == ("op", "(")):
                o, g = "*", self.potenz()   # 2x, 3(x+1)
            else:
                return f
            f = (lambda a, b: lambda x: a(x) * b(x))(f, g) if o == "*" else \
                (lambda a, b: lambda x: a(x) / b(x))(f, g)

    def vorzeichen(self) -> Callable:
        if self.op("-"):
            g = self.vorzeichen()
            return lambda x: -g(x)
        if self.op("+"):
            return self.vorzeichen()
        return self.potenz()

    def potenz(self) -> Callable:
        f = self.atom()
        if self.op("^"):
            g = self.vorzeichen()
            return lambda x: _potenz(f(x), g(x))
        if (o := self.op("²", "³")):
            n = 2.0 if o == "²" else 3.0
            return lambda x: _potenz(f(x), n)
        return f

    def atom(self) -> Callable:
        k = self.blick()
        if k is None:
            raise ValueError("Term endet unerwartet")
        self.i += 1
        if k[0] == "zahl":
            v = k[1]
            return lambda x: v
        if k[0] == "x":
            return lambda x: x
        if k[0] == "fn":
            if not self.op("("):
                raise ValueError(f"nach {k[1]} muss eine Klammer folgen: {k[1]}(…)")
            fn, g = _FUNKTIONEN[k[1]], self.klammer()
            return lambda x: fn(g(x))
        if k == ("op", "("):
            return self.klammer()
        raise ValueError(f"unerwartetes „{k[1]}“ im Term")

    def klammer(self) -> Callable:
        self.tiefe += 1
        if self.tiefe > 8:
            raise ValueError("zu viele Klammern ineinander")
        f = self.summe()
        if not self.op(")"):
            raise ValueError("schließende Klammer fehlt")
        self.tiefe -= 1
        return f


def kompiliere(term: str) -> Callable[[float], float]:
    """Übersetzt einen Term in x in eine Funktion; Rechenfehler geben NaN."""
    p = _Parser(_tokens(term))
    f = p.summe()
    if p.i != len(p.t):
        raise ValueError(f"unerwartetes „{p.t[p.i][1]}“ im Term")

    def sicher(x: float) -> float:
        try:
            y = float(f(x))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return math.nan
        return y if math.isfinite(y) else math.nan
    return sicher


# --- SVG-Hilfen --------------------------------------------------------------

_TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline",
         "polygon", "text", "tspan", "title", "defs", "clipPath"}
_ATTRS = {"x", "y", "dx", "dy", "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "d",
          "points", "width", "height", "viewBox", "transform", "fill", "stroke",
          "stroke-width", "stroke-dasharray", "stroke-linecap", "stroke-linejoin",
          "font-size", "font-weight", "font-style", "text-anchor",
          "dominant-baseline", "paint-order", "opacity", "fill-opacity",
          "clip-path", "id", "style", "role", "xml:space", "font-family",
          "{http://www.w3.org/XML/1998/namespace}space"}
_STIL_OK = re.compile(r"^[\w\s:;.,#%()\-]*$")


def _saeubern(svg: str) -> str:
    """Nur bekannte Elemente und Attribute, keine Verweise nach außen."""
    root = ET.fromstring(svg)

    def gehe(el: ET.Element) -> None:
        for kind in list(el):
            kind.tag = kind.tag.split("}")[-1] if isinstance(kind.tag, str) else ""
            if kind.tag not in _TAGS:
                el.remove(kind)
                continue
            gehe(kind)
        for k in list(el.attrib):
            v = el.attrib[k]
            if k not in _ATTRS or "url(" in v.replace("url(#", "") or "javascript" in v.lower():
                del el.attrib[k]
            elif k == "style":
                v = re.sub(r"font-family:[^;]*;?", "", v)
                v = re.sub(r"stroke-dasharray:-;?", "", v)
                if not _STIL_OK.match(v):
                    del el.attrib[k]
                else:
                    el.attrib[k] = v
            elif k == "font-family" and el.tag != "svg":
                del el.attrib[k]
    root.tag = "svg"
    gehe(root)
    root.set("xmlns", _SVG_NS)
    return ET.tostring(root, encoding="unicode")


def _x(s: Any) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _de(v: float | Fraction) -> str:
    """Zahl deutsch: Komma, echtes Minus, ohne überflüssige Nachkommastellen."""
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        s = str(int(round(f)))
    else:
        s = f"{f:.4f}".rstrip("0").rstrip(".").replace(".", ",")
    return s.replace("-", "−")


def _bruch(v: Fraction) -> str:
    return _de(v) if v.denominator == 1 else f"{v.numerator}/{v.denominator}".replace("-", "−")


def _text(x: float, y: float, s: Any, size: float = 14, anker: str = "middle",
          fett: bool = False, farbe: str = "#000000", halo: bool = False) -> str:
    extra = ' font-weight="bold"' if fett else ""
    if halo:
        extra += ' stroke="#ffffff" stroke-width="4" paint-order="stroke"'
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anker}" '
            f'fill="{farbe}"{extra}>{_x(s)}</text>')


def _breite(s: Any, size: float = 14) -> float:
    return len(str(s)) * size * 0.58


def _rahmen(inhalt: str, breite: float, hoehe: float, titel: str | None, alt: str) -> str:
    pad, oben = 14, (32 if titel else 0)
    breite = max(breite, _breite(titel or "", 17) + 4)
    w, h = breite + 2 * pad, hoehe + oben + 2 * pad
    kopf = _text(pad, pad + 18, titel, 17, "start", True) if titel else ""
    svg = (f'<svg xmlns="{_SVG_NS}" width="{w:.0f}" height="{h:.0f}" '
           f'viewBox="0 0 {w:.1f} {h:.1f}" font-family="sans-serif" role="img">'
           f'<title>{_x(alt)}</title>'
           f'<rect x="0" y="0" width="{w:.1f}" height="{h:.1f}" fill="#ffffff"/>{kopf}'
           f'<g transform="translate({pad},{pad + oben})">{inhalt}</g></svg>')
    return _saeubern(svg)


def _pfeilspitze(x: float, y: float, dx: float, dy: float, farbe: str, g: float = 9) -> str:
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    a = (x - ux * g - uy * g * 0.45, y - uy * g + ux * g * 0.45)
    b = (x - ux * g + uy * g * 0.45, y - uy * g - ux * g * 0.45)
    return (f'<polygon points="{x:.1f},{y:.1f} {a[0]:.1f},{a[1]:.1f} {b[0]:.1f},{b[1]:.1f}" '
            f'fill="{farbe}"/>')


def _bruch_svg(x: float, y: float, v: Fraction | tuple[int, int], farbe: str = "#000000",
               size: float = 14) -> str:
    """Bruch gestapelt (Zähler über Nenner), ganze Zahlen einzeilig; y = Oberkante.

    Ein Paar (z, n) bleibt ungekürzt, damit 2/4 als 2/4 dasteht."""
    zz, nn = v if isinstance(v, tuple) else (v.numerator, v.denominator)
    if nn == 1:
        return _text(x, y + size, _de(zz), size, farbe=farbe)
    z, n = str(abs(zz)), str(nn)
    w = max(_breite(z, size), _breite(n, size)) + 2
    out = (_text(x, y + size - 1, z, size, farbe=farbe)
           + f'<line x1="{x - w / 2:.1f}" y1="{y + size + 3:.1f}" x2="{x + w / 2:.1f}" '
             f'y2="{y + size + 3:.1f}" stroke="{farbe}" stroke-width="1.3"/>'
           + _text(x, y + 2 * size + 5, n, size, farbe=farbe))
    if zz < 0:
        out += _text(x - w / 2 - 6, y + size + 8, "−", size, farbe=farbe)
    return out


# --- Schaltplan zeichnen ------------------------------------------------------

_E, _KN, _G = 3.0, 1.0, 0.75            # Zweipollänge, Knotenlänge, Abstand Verzweigung
_OBEN, _UNTEN, _SCHLEIFE, _LUFT = 1.1, 1.1, 2.4, 0.5


def _mass(g: Any, gemessen: set[str]) -> tuple[float, float, float]:
    if isinstance(g, Teil):
        oben = _SCHLEIFE + 1.1 if g.id in gemessen else _OBEN
        return (_KN if g.teil == "knoten" else _E), oben, _UNTEN
    if isinstance(g, Reihe):
        ms = [_mass(z, gemessen) for z in g.reihe]
        return sum(m[0] for m in ms), max(m[1] for m in ms), max(m[2] for m in ms)
    ms = [_mass(z, gemessen) for z in g.parallel]
    ab = _versatz(ms)
    return max(m[0] for m in ms) + 2 * _G, ms[0][1], ab[-1] + ms[-1][2]


def _versatz(ms: list[tuple[float, float, float]]) -> list[float]:
    ab = [0.0]
    for vor, nach in zip(ms, ms[1:], strict=False):
        ab.append(ab[-1] + vor[2] + nach[1] + _LUFT)
    return ab


def _symbol(t: Teil) -> Any:
    import schemdraw.elements as elm
    from schemdraw.segments import SegmentText
    if t.teil == "lampe":
        return elm.Lamp2()
    if t.teil == "widerstand":
        return elm.ResistorIEC()
    if t.teil == "schalter":
        return _geschlossen() if t.zustand == "geschlossen" else elm.Switch()
    if t.teil == "amperemeter":
        return elm.MeterA()
    if t.teil == "voltmeter":
        return elm.MeterV()
    if t.teil == "motor":
        m = elm.Motor()
        m.segments.append(SegmentText((0.5, 0), "M"))
        return m
    d = elm.Diode()
    return d.reverse() if t.sperrrichtung else d


def _geschlossen() -> Any:
    """Geschlossener Schalter als gerader Hebel zwischen beiden Kontakten. Das
    Öffner-Symbol von schemdraw liegt schräg und war auf dem Blatt kaum von
    einem offenen Schalter zu unterscheiden."""
    from schemdraw.elements.twoterm import Element2Term, gap
    from schemdraw.segments import Segment, SegmentCircle
    r = 0.075

    class Geschlossen(Element2Term):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.segments.append(Segment([(0, 0), gap, (r * 2, 0), (1 - r * 2, 0), gap, (1, 0)]))
            self.segments.append(SegmentCircle((r, 0), r, fill="bg", zorder=3))
            self.segments.append(SegmentCircle((1 - r, 0), r, fill="bg", zorder=3))
    return Geschlossen()


def _quelle_symbol(art: str) -> Any:
    """Batterie (langer Strich = Pluspol) oder Quelle (Kreis mit Strich), links Plus."""
    import schemdraw.elements as elm
    from schemdraw.segments import Segment, SegmentText
    if art == "batterie":
        q, links, rechts = elm.BatteryCell(), -0.3, 0.5
    else:
        q, links, rechts = elm.Source(), -0.25, 1.25
        q.segments.append(Segment([(0, 0), (1, 0)]))
    q.segments.append(SegmentText((links, 0.5), "+", fontsize=13))
    q.segments.append(SegmentText((rechts, 0.5), "−", fontsize=13))
    return q


def _label(s: str | None) -> str:
    return (s or "").replace("$", "")


def _setze(d: Any, g: Any, x: float, y: float, gemessen: set[str],
           pos: dict[str, tuple[float, float, float]]) -> None:
    import schemdraw.elements as elm
    w = _mass(g, gemessen)[0]
    if isinstance(g, Teil):
        if g.teil == "knoten":
            d.add(elm.Line().at((x, y)).to((x + w, y)))
            d.add(elm.Dot().at((x + w / 2, y)).label(_label(g.id), loc="top"))
        else:
            el = _symbol(g).at((x, y)).right().length(w).label(_label(g.id), loc="top")
            if g.beschriftung:
                el.label(_label(g.beschriftung), loc="bottom")
            d.add(el)
        pos[g.id] = (x, x + w, y)
    elif isinstance(g, Reihe):
        for z in g.reihe:
            _setze(d, z, x, y, gemessen, pos)
            x += _mass(z, gemessen)[0]
    else:
        ms = [_mass(z, gemessen) for z in g.parallel]
        ab = _versatz(ms)
        xl, xr = x + _G, x + w - _G
        d.add(elm.Line().at((x, y)).to((xl, y)))
        d.add(elm.Line().at((xr, y)).to((x + w, y)))
        d.add(elm.Line().at((xl, y)).to((xl, y - ab[-1])))
        d.add(elm.Line().at((xr, y)).to((xr, y - ab[-1])))
        for i, (z, m) in enumerate(zip(g.parallel, ms, strict=True)):
            yi = y - ab[i]
            _setze(d, z, xl, yi, gemessen, pos)
            if xl + m[0] < xr - 1e-9:
                d.add(elm.Line().at((xl + m[0], yi)).to((xr, yi)))
            if i < len(ms) - 1:
                d.add(elm.Dot().at((xl, yi)))
                d.add(elm.Dot().at((xr, yi)))


def _schaltplan_svg(f: Schaltplan) -> tuple[str, float, float]:
    import schemdraw
    import schemdraw.elements as elm
    ziele = {("quelle" if m.ueber in ("quelle", f.quelle.id) else m.ueber): m
             for m in f.messgeraete}
    gemessen = set(ziele) - {"quelle"}
    w, _, unten = _mass(f.netz, gemessen)
    breite = max(w + 1.0, _E + 2.0)
    yb = -(unten + 1.3)
    d = schemdraw.Drawing(canvas="svg", show=False)
    d.config(unit=_E, fontsize=14, font="sans-serif", lw=2, margin=0.3, color="black")
    pos: dict[str, tuple[float, float, float]] = {}
    x0 = (breite - w) / 2
    d.add(elm.Line().at((0, 0)).to((x0, 0)))
    _setze(d, f.netz, x0, 0, gemessen, pos)
    d.add(elm.Line().at((x0 + w, 0)).to((breite, 0)))
    d.add(elm.Line().at((0, 0)).to((0, yb)))
    d.add(elm.Line().at((breite, 0)).to((breite, yb)))
    xs = (breite - _E) / 2
    d.add(elm.Line().at((0, yb)).to((xs, yb)))
    q = _quelle_symbol(f.quelle.art).at((xs, yb)).right().length(_E)  # links Pluspol
    oben_txt = [f.quelle.id, f.quelle.beschriftung] if "quelle" in ziele else [f.quelle.id]
    if any(oben_txt):
        q.label(_label(" ".join(s for s in oben_txt if s)), loc="top")
    if f.quelle.beschriftung and "quelle" not in ziele:
        q.label(_label(f.quelle.beschriftung), loc="bottom")
    d.add(q)
    d.add(elm.Line().at((xs + _E, yb)).to((breite, yb)))
    pos["quelle"] = (xs, xs + _E, yb)
    for ziel, m in ziele.items():
        a, b, y = pos[ziel]
        yv = y - _SCHLEIFE if ziel == "quelle" else y + _SCHLEIFE
        d.add(elm.Line().at((a, y)).to((a, yv)))
        v = elm.MeterV().at((a, yv)).right().length(b - a)
        text = _label(" ".join(s for s in (m.id, m.beschriftung) if s))
        v.label(text, loc="bottom" if ziel == "quelle" else "top")
        d.add(v)
        d.add(elm.Line().at((b, yv)).to((b, y)))
        d.add(elm.Dot().at((a, y)))
        d.add(elm.Dot().at((b, y)))
    roh = d.get_imagedata("svg")
    root = ET.fromstring(roh.decode() if isinstance(roh, bytes) else roh)
    vx, vy, vw, vh = (float(z) for z in root.get("viewBox").split())
    s = 1.2
    inhalt = "".join(ET.tostring(k, encoding="unicode") for k in root)
    inhalt = re.sub(r"\sxmlns(:\w+)?=\"[^\"]*\"", "", inhalt).replace("ns0:", "")
    return (f'<g transform="scale({s}) translate({-vx:.2f},{-vy:.2f})">{inhalt}</g>',
            vw * s, vh * s)


# --- Übrige Typen zeichnen ---------------------------------------------------

def _zahlenstrahl_svg(f: Zahlenstrahl) -> tuple[str, float, float]:
    von, bis, schritt = zahl(f.von), zahl(f.bis), zahl(f.schritt)
    als_bruch = any("/" in str(v) for v in (f.von, f.bis, f.schritt)) or (
        schritt.denominator not in (1, 2, 4, 5, 10, 20, 25, 50, 100))
    rand, laenge = 24.0, 600.0
    px = lambda v: rand + float((v - von) / (bis - von)) * laenge  # noqa: E731
    n = int((bis - von) / schritt)
    # Sprungbögen auf Ebenen verteilen, damit sie sich nicht überdecken
    ebenen: list[list[tuple[float, float]]] = []
    boegen = []
    for s in f.spruenge:
        a, b = sorted((px(zahl(s.von)), px(zahl(s.bis))))
        lv = next((i for i, e in enumerate(ebenen)
                   if all(b <= c or a >= dd for c, dd in e)), len(ebenen))
        if lv == len(ebenen):
            ebenen.append([])
        ebenen[lv].append((a, b))
        boegen.append((s, lv))
    marke_oben = 34 if any(m.beschriftung for m in f.marken) else 12
    bogen_oben = max([34 + 22 * lv + 20 for _, lv in boegen] or [0])
    y = max(marke_oben, bogen_oben) + 8
    out = [f'<line x1="{rand - 12:.1f}" y1="{y}" x2="{rand + laenge + 18:.1f}" y2="{y}" '
           'stroke="#000000" stroke-width="2"/>',
           _pfeilspitze(rand + laenge + 22, y, 1, 0, "#000000")]
    fein = schritt / f.unterteilung
    for k in range(n * f.unterteilung + 1):
        if k % f.unterteilung:
            xk = px(von + fein * k)
            out.append(f'<line x1="{xk:.1f}" y1="{y - 5}" x2="{xk:.1f}" y2="{y + 5}" '
                       'stroke="#000000" stroke-width="1.2"/>')
    werte = [von + schritt * k for k in range(n + 1)]
    texte = [_bruch(v) if als_bruch else _de(v) for v in werte]
    platz = laenge / max(n, 1)
    noetig = (max(_breite(t) for t in texte) + 10) / platz
    jeder = next(j for j in (1, 2, 5, 10, 20, 40) if j >= noetig)
    start = von / schritt   # Beschriftung an Vielfachen verankern (−10, −5, 0 …)
    versatz = int(start) % jeder if start.denominator == 1 else 0
    for k, v in enumerate(werte):
        xk = px(v)
        out.append(f'<line x1="{xk:.1f}" y1="{y - 9}" x2="{xk:.1f}" y2="{y + 9}" '
                   'stroke="#000000" stroke-width="2"/>')
        if (k + versatz) % jeder == 0:
            out.append(_bruch_svg(xk, y + 12, v) if als_bruch else _text(xk, y + 28, texte[k]))
    for s, lv in boegen:
        a, b = px(zahl(s.von)), px(zahl(s.bis))
        h = 34 + 22 * lv
        ym, xm = y - 4, (a + b) / 2
        out.append(f'<path d="M{a:.1f},{ym} Q{xm:.1f},{ym - 2 * h} {b:.1f},{ym}" '
                   f'fill="none" stroke="{_BLAU}" stroke-width="2"/>')
        out.append(_pfeilspitze(b, ym, b - xm, 2 * h, _BLAU))
        if s.beschriftung:
            out.append(_text(xm, ym - h - 6, s.beschriftung, 14, fett=True, farbe=_BLAU,
                             halo=True))
    reihe_links = -1e9
    for m in sorted(f.marken, key=lambda m: zahl(m.wert)):
        xk = px(zahl(m.wert))
        out.append(f'<circle cx="{xk:.1f}" cy="{y}" r="5" fill="{_BLAU}"/>')
        if m.beschriftung:
            hoch = xk - _breite(m.beschriftung) / 2 < reihe_links + 4
            out.append(_text(xk, y - (30 if hoch else 12), m.beschriftung, 14, fett=True,
                             farbe=_BLAU, halo=True))
            if not hoch:
                reihe_links = xk + _breite(m.beschriftung) / 2
    return "".join(out), rand * 2 + laenge + 10, y + (50 if als_bruch else 36)


def _bruchstreifen_svg(f: Bruchstreifen) -> tuple[str, float, float]:
    lw = max([_breite(b.beschriftung) for b in f.balken if b.beschriftung] or [-12]) + 12
    bw, bh, luft = 480.0, 36.0, 18.0
    out = []
    for i, b in enumerate(f.balken):
        y = i * (bh + luft)
        tw = bw / b.teile
        for k in range(b.teile):
            fill = "#9fb8dd" if k < b.gefaerbt else "#ffffff"
            out.append(f'<rect x="{lw + k * tw:.2f}" y="{y}" width="{tw:.2f}" height="{bh}" '
                       f'fill="{fill}" stroke="#000000" stroke-width="1.5"/>')
        out.append(f'<rect x="{lw}" y="{y}" width="{bw}" height="{bh}" fill="none" '
                   'stroke="#000000" stroke-width="2.5"/>')
        if b.beschriftung:
            out.append(_text(lw - 12, y + bh / 2 + 5, b.beschriftung, 14, "end"))
        if f.zeige_bruch:
            out.append(_bruch_svg(lw + bw + 30, y + 1, (b.gefaerbt, b.teile)))
    hoehe = len(f.balken) * (bh + luft) - luft
    return "".join(out), lw + bw + (60 if f.zeige_bruch else 0), hoehe


def _schritt(spanne: float, ziel: int = 10) -> float:
    roh = spanne / ziel
    e = 10 ** math.floor(math.log10(roh))
    return next(m * e for m in (1, 2, 5, 10) if m * e >= roh - 1e-12)


def _zuege(fn: Callable[[float], float], f: Funktionsgraph) -> list[list[tuple[float, float]]]:
    """Dicht abtasten; an Sprungstellen und außerhalb des Bereichs trennen."""
    n, spanne = 900, f.y_max - f.y_min
    xs = [f.x_min + (f.x_max - f.x_min) * i / n for i in range(n + 1)]
    ys = [fn(x) for x in xs]
    drin = [math.isfinite(y) and f.y_min - 0.02 * spanne <= y <= f.y_max + 0.02 * spanne
            for y in ys]
    zuege: list[list[tuple[float, float]]] = []
    zug: list[tuple[float, float]] = []
    for i, (x, y) in enumerate(zip(xs, ys, strict=True)):
        sichtbar = math.isfinite(y) and abs(y) < 1e7 and (
            drin[i] or (i and drin[i - 1]) or (i < n and drin[i + 1]))
        if sichtbar and zug:
            px_, py_ = zug[-1]
            if abs(y - py_) > 0.4 * spanne:
                ym = fn((x + px_) / 2)
                if not (math.isfinite(ym) and min(y, py_) - 1e-9 <= ym <= max(y, py_) + 1e-9):
                    sichtbar = False
        if not sichtbar:
            if len(zug) > 1:
                zuege.append(zug)
            zug = [(x, y)] if math.isfinite(y) and abs(y) < 1e7 and drin[i] else []
            continue
        zug.append((x, y))
    if len(zug) > 1:
        zuege.append(zug)
    return zuege


def _funktionsgraph_svg(f: Funktionsgraph) -> tuple[str, float, float]:
    xs_, ys_ = f.x_max - f.x_min, f.y_max - f.y_min
    w = 520.0
    h = min(560.0, max(240.0, w * ys_ / xs_))
    ml, mt, mb, mr = 34.0, 22.0, 26.0, 34.0
    sx = lambda x: ml + (x - f.x_min) / xs_ * w  # noqa: E731
    sy = lambda y: mt + h - (y - f.y_min) / ys_ * h  # noqa: E731
    out = []
    ax_y = sy(min(max(0.0, f.y_min), f.y_max))
    ax_x = sx(min(max(0.0, f.x_min), f.x_max))

    def striche(a: float, b: float, st: float) -> list[float]:
        k = math.ceil(a / st - 1e-9)
        return [k * st + i * st for i in range(int((b - k * st) / st + 1e-9) + 1)]
    lx, ly = _schritt(xs_), _schritt(ys_)
    if f.gitter:
        for st, achse in ((lx, "x"), (ly, "y")):
            m = st / 10 ** math.floor(math.log10(st))
            g = st / 2 if round(m) == 2 else st
            if achse == "x":
                for v in striche(f.x_min, f.x_max, g):
                    out.append(f'<line x1="{sx(v):.1f}" y1="{mt}" x2="{sx(v):.1f}" '
                               f'y2="{mt + h:.1f}" stroke="#c8c8c8" stroke-width="1"/>')
            else:
                for v in striche(f.y_min, f.y_max, g):
                    out.append(f'<line x1="{ml}" y1="{sy(v):.1f}" x2="{ml + w:.1f}" '
                               f'y2="{sy(v):.1f}" stroke="#c8c8c8" stroke-width="1"/>')
        out.append(f'<rect x="{ml}" y="{mt}" width="{w}" height="{h:.1f}" fill="none" '
                   'stroke="#9a9a9a" stroke-width="1"/>')
    out.append(f'<line x1="{ml - 6}" y1="{ax_y:.1f}" x2="{ml + w + 14:.1f}" y2="{ax_y:.1f}" '
               'stroke="#000000" stroke-width="1.8"/>')
    out.append(_pfeilspitze(ml + w + 20, ax_y, 1, 0, "#000000"))
    out.append(f'<line x1="{ax_x:.1f}" y1="{mt + h + 6:.1f}" x2="{ax_x:.1f}" y2="{mt - 14}" '
               'stroke="#000000" stroke-width="1.8"/>')
    out.append(_pfeilspitze(ax_x, mt - 20, 0, -1, "#000000"))
    out.append(_text(ml + w + 18, ax_y - 10, f.x_achse, 14, "end", True, halo=True))
    out.append(_text(ax_x + 10, mt - 8, f.y_achse, 14, "start", True))
    for v in striche(f.x_min, f.x_max, lx):
        if abs(v) < 1e-9 and f.x_min < 0 < f.x_max:
            continue
        out.append(f'<line x1="{sx(v):.1f}" y1="{ax_y - 4:.1f}" x2="{sx(v):.1f}" '
                   f'y2="{ax_y + 4:.1f}" stroke="#000000" stroke-width="1.5"/>')
        out.append(_text(sx(v), ax_y + 18, _de(v), 12, halo=True))
    for v in striche(f.y_min, f.y_max, ly):
        if abs(v) < 1e-9 and f.y_min < 0 < f.y_max:
            continue
        out.append(f'<line x1="{ax_x - 4:.1f}" y1="{sy(v):.1f}" x2="{ax_x + 4:.1f}" '
                   f'y2="{sy(v):.1f}" stroke="#000000" stroke-width="1.5"/>')
        out.append(_text(ax_x - 7, sy(v) + 4, _de(v), 12, "end", halo=True))
    if f.x_min < 0 < f.x_max and f.y_min < 0 < f.y_max:
        out.append(_text(ax_x - 7, ax_y + 16, "0", 12, "end", halo=True))
    kid = "k" + hashlib.sha1(f.model_dump_json().encode()).hexdigest()[:8]
    out.append(f'<defs><clipPath id="{kid}"><rect x="{ml}" y="{mt}" width="{w}" '
               f'height="{h:.1f}"/></clipPath></defs>')
    etiketten = []
    for i, fu in enumerate(f.funktionen):
        farbe, strich = _FARBEN[i], _STRICHE[i]
        zuege = _zuege(kompiliere(fu.term), f)
        dash = f' stroke-dasharray="{strich}"' if strich else ""
        for z in zuege:
            pts = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in z)
            out.append(f'<polyline points="{pts}" fill="none" stroke="{farbe}" '
                       f'stroke-width="2.4" stroke-linejoin="round"{dash} '
                       f'clip-path="url(#{kid})"/>')
        sicht = [(x, y) for z in zuege for x, y in z if f.y_min <= y <= f.y_max]
        if fu.beschriftung and sicht:
            x, y = sicht[int(len(sicht) * 0.85)]
            tx, ty = sx(x), sy(y) - 10
            ty = min(max(ty, mt + 14), mt + h - 6)
            etiketten.append(_text(min(tx, ml + w - 4), ty, fu.beschriftung, 14,
                                   "end" if tx > ml + w * 0.5 else "start", True, farbe, True))
    for p in f.punkte:
        if f.x_min <= p.x <= f.x_max and f.y_min <= p.y <= f.y_max:
            out.append(f'<circle cx="{sx(p.x):.1f}" cy="{sy(p.y):.1f}" r="4" fill="#000000"/>')
            if p.beschriftung:
                rechts = sx(p.x) < ml + w - 40
                out.append(_text(sx(p.x) + (7 if rechts else -7), sy(p.y) - 8, p.beschriftung,
                                 14, "start" if rechts else "end", True, halo=True))
    out += etiketten
    return "".join(out), ml + w + mr, mt + h + mb


def _tabelle_svg(f: Tabelle) -> tuple[str, float, float]:
    spalten = [max([_breite(f.kopf[i], 14)] + [_breite(z[i], 14) for z in f.zeilen]) + 20
               for i in range(len(f.kopf))]
    zh = 30.0
    out = []
    breite = sum(spalten)
    out.append(f'<rect x="0" y="0" width="{breite:.1f}" height="{zh}" fill="#eeeeee"/>')
    for r, zeile in enumerate([f.kopf, *f.zeilen]):
        x = 0.0
        for i, zelle in enumerate(zeile):
            out.append(_text(x + spalten[i] / 2, r * zh + 20, zelle, 14, fett=r == 0))
            x += spalten[i]
    hoehe = zh * (len(f.zeilen) + 1)
    for r in range(len(f.zeilen) + 2):
        out.append(f'<line x1="0" y1="{r * zh}" x2="{breite:.1f}" y2="{r * zh}" '
                   f'stroke="#000000" stroke-width="{2 if r in (0, 1) else 1.2}"/>')
    x = 0.0
    for sp in [0, *spalten]:
        x += sp
        out.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{hoehe}" '
                   'stroke="#000000" stroke-width="1.2"/>')
    return "".join(out), breite, hoehe


_ZEICHNER = {"schaltplan": _schaltplan_svg, "zahlenstrahl": _zahlenstrahl_svg,
             "bruchstreifen": _bruchstreifen_svg, "funktionsgraph": _funktionsgraph_svg,
             "tabelle": _tabelle_svg}


def render(spec: Any) -> str:
    """Prüft die Beschreibung und liefert ein eigenständiges SVG."""
    f = validate(spec)
    inhalt, breite, hoehe = _ZEICHNER[f.type](f)
    return _rahmen(inhalt, breite, hoehe, f.titel, describe(f))


# --- Klartext ----------------------------------------------------------------

def _teil_text(t: Teil) -> str:
    s = f"{TEILE[t.teil]} {t.id}"
    extra = [x for x in (t.beschriftung, t.zustand,
                         "in Sperrrichtung" if t.sperrrichtung else None) if x]
    return s + (f" ({', '.join(extra)})" if extra else "")


def _glied_text(g: Any) -> str:
    if isinstance(g, Teil):
        return _teil_text(g)
    if isinstance(g, Reihe):
        teile = [_glied_text(z) for z in g.reihe]
        return teile[0] if len(teile) == 1 else "[" + " → ".join(teile) + "]"
    return "parallel { " + " | ".join(_glied_text(z) for z in g.parallel) + " }"


def _kopf_id(g: Any) -> str:
    teile = _blaetter(g)
    haupt = [t for t in teile if t.teil not in _MESSER] or teile
    return haupt[0].id


def _und(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " und " + xs[-1]


def _schaltplan_text(f: Schaltplan) -> list[str]:
    q = "Batterie" if f.quelle.art == "batterie" else "Spannungsquelle"
    q += f" {f.quelle.id}" if f.quelle.id else ""
    q += f" ({f.quelle.beschriftung})" if f.quelle.beschriftung else ""
    kette = f.netz.reihe if isinstance(f.netz, Reihe) else [f.netz]
    saetze = [f"Stromkreis mit {q}.",
              "Vom Pluspol aus der Reihe nach: " + " → ".join(_glied_text(z) for z in kette)
              + " → zurück zur Quelle."]
    ort: dict[str, str] = {}
    allein: dict[str, list[str]] = {}   # Messgerät bildet allein einen Zweig

    def gehe(g: Any, zweig: str | None) -> None:
        if isinstance(g, Teil):
            ort[g.id] = zweig or ""
        elif isinstance(g, Reihe):
            for z in g.reihe:
                gehe(z, zweig)
        else:
            koepfe = [_kopf_id(z) for z in g.parallel]
            details = "; ".join(f"Zweig {i + 1}: {', '.join(t.id for t in _blaetter(z))}"
                                for i, z in enumerate(g.parallel))
            saetze.append(f"{_und(koepfe)} liegen parallel zueinander ({details}).")
            for z, k in zip(g.parallel, koepfe, strict=True):
                if len(_blaetter(z)) == 1:
                    allein[k] = [x for x in koepfe if x != k]
                gehe(z, k)
    gehe(f.netz, None)
    for t in _blaetter(f.netz):
        if t.teil not in ("amperemeter", "voltmeter"):
            continue
        if t.id in allein:
            andere = _und(allein[t.id])
            saetze.append(f"{t.id} bildet allein einen Zweig parallel zu {andere}"
                          + (" und misst die Spannung daran." if t.teil == "voltmeter"
                             else " (überbrückt sie)."))
        elif t.teil == "amperemeter":
            saetze.append(f"{t.id} liegt im Zweig mit {ort[t.id]}." if ort[t.id] else
                          f"{t.id} liegt in der Hauptleitung (misst den Gesamtstrom).")
        else:
            saetze.append(f"Voltmeter {t.id} liegt in Reihe im Stromkreis"
                          + (f" (Zweig mit {ort[t.id]})." if ort[t.id] else "."))
    for m in f.messgeraete:
        ziel = "der Quelle" if m.ueber in ("quelle", f.quelle.id) else m.ueber
        wert = f" (Anzeige {m.beschriftung})" if m.beschriftung else ""
        saetze.append(f"Voltmeter {m.id}{wert} liegt parallel zu {ziel} "
                      f"und misst die Spannung an {ziel}.")
    return saetze


def _zahl_text(v: Any) -> str:
    return str(v).replace(".", ",") if isinstance(v, float) else str(v)


def describe(spec: Any) -> str:
    """Kurzer deutscher Klartext dessen, was gezeichnet ist."""
    f = validate(spec)
    titel = f" „{f.titel}“" if f.titel else ""
    if isinstance(f, Schaltplan):
        s = _schaltplan_text(f)
        s[0] = f"Schaltplan{titel}: " + s[0]
        return " ".join(s)
    if isinstance(f, Zahlenstrahl):
        s = (f"Zahlenstrahl{titel} von {_zahl_text(f.von)} bis {_zahl_text(f.bis)}, "
             f"Hauptstriche im Abstand {_zahl_text(f.schritt)}")
        s += f", jeweils in {f.unterteilung} Teile unterteilt." if f.unterteilung > 1 else "."
        if f.marken:
            s += " Markiert: " + ", ".join(
                _zahl_text(m.wert) + (f" („{m.beschriftung}“)" if m.beschriftung else "")
                for m in f.marken) + "."
        if f.spruenge:
            s += " Sprünge: " + ", ".join(
                f"von {_zahl_text(p.von)} nach {_zahl_text(p.bis)}"
                + (f" („{p.beschriftung}“)" if p.beschriftung else "") for p in f.spruenge) + "."
        return s
    if isinstance(f, Bruchstreifen):
        teile = [f"{i + 1}) " + (f"„{b.beschriftung}“: " if b.beschriftung else "")
                 + f"{b.gefaerbt} von {b.teile} Teilen gefärbt ({b.gefaerbt}/{b.teile})"
                 for i, b in enumerate(f.balken)]
        return f"Bruchstreifen{titel}, alle gleich lang: " + "; ".join(teile) + "."
    if isinstance(f, Funktionsgraph):
        s = (f"Koordinatensystem{titel}: {f.x_achse} von {_de(f.x_min)} bis {_de(f.x_max)}, "
             f"{f.y_achse} von {_de(f.y_min)} bis {_de(f.y_max)}"
             + (", mit Gitter." if f.gitter else ", ohne Gitter.")).replace("−", "-")
        if f.funktionen:
            s += " Graphen: " + "; ".join(
                f"y = {fu.term}" + (f" („{fu.beschriftung}“)" if fu.beschriftung else "")
                for fu in f.funktionen) + "."
        if f.punkte:
            s += " Punkte: " + ", ".join(
                (p.beschriftung or "") + f"({_de(p.x)} | {_de(p.y)})".replace("−", "-")
                for p in f.punkte) + "."
        return s
    zeilen = "; ".join(" | ".join(z) for z in f.zeilen)
    return (f"Tabelle{titel} mit den Spalten {' | '.join(f.kopf)}"
            + (f". Zeilen: {zeilen}." if zeilen else ", ohne Zeilen."))


SPEC_HELP = """\
ABBILDUNGEN: Zeichne nie selbst SVG. Beschreibe eine Abbildung als JSON-Objekt;
die App zeichnet sie. Erlaubte Formen (Felder mit ? sind optional; "titel"? bis 80 Zeichen
geht überall):

1. Schaltplan
{"type":"schaltplan","titel"?:"…",
 "quelle":{"art":"batterie"|"quelle","id"?:"U","beschriftung"?:"4,5 V"},
 "netz":GLIED,"messgeraete"?:[{"teil":"voltmeter","id":"V1","ueber":"L1"|"quelle","beschriftung"?:"…"}]}
GLIED ist eines von:
 {"teil":ART,"id":"L1","beschriftung"?:"100 Ω"}  ART: lampe, widerstand, schalter, amperemeter,
   voltmeter, motor, diode, knoten; schalter braucht "zustand":"offen"|"geschlossen";
   diode kann "sperrrichtung":true haben.
 {"reihe":[GLIED,…]}        Glieder hintereinander (Reihenschaltung)
 {"parallel":[GLIED,…]}     2 bis 5 Zweige nebeneinander (Parallelschaltung)
Die Quelle schließt den Kreis: Strom fließt vom Pluspol durch "netz" in der angegebenen
Reihenfolge zurück. Amperemeter setzt du als Glied in die Leitung, deren Strom es misst; ein
Voltmeter über einem Bauteil kommt in "messgeraete" mit "ueber". Kennungen eindeutig (Buchstabe
+ bis zu 4 Zeichen), höchstens 12 Bauteile samt Messgeräten, höchstens 3 Parallelschaltungen
ineinander.
Beispiel: {"type":"schaltplan","quelle":{"art":"batterie","beschriftung":"4,5 V"},"netz":{"reihe":[
 {"teil":"schalter","id":"S1","zustand":"geschlossen"},{"parallel":[{"reihe":[{"teil":"lampe","id":"L1"},
 {"teil":"amperemeter","id":"A2"}]},{"teil":"lampe","id":"L2"}]},{"teil":"amperemeter","id":"A1"}]}}

2. Zahlenstrahl
{"type":"zahlenstrahl","von":0,"bis":2,"schritt":"1/4","unterteilung"?:1..10,
 "marken"?:[{"wert":"3/4","beschriftung"?:"A"}],"spruenge"?:[{"von":0,"bis":"3/4","beschriftung"?:"+3/4"}]}
Zahlen als Zahl oder Text: 2, -1.5, "1,5", "3/4", "1 1/2". 1 bis 40 Hauptstriche, höchstens
20 Marken und 10 Sprünge, alle Werte im Bereich. Marken ohne Beschriftung zeigen nur den Punkt.
Brüche als Schritt beschriften die Striche als Brüche.

3. Bruchstreifen (alle Streifen gleich lang, zum Vergleichen)
{"type":"bruchstreifen","balken":[{"teile":4,"gefaerbt":3,"beschriftung"?:"…"}],"zeige_bruch"?:true}
1 bis 6 Streifen, teile 1..24, gefaerbt 0..teile. zeige_bruch schreibt gefaerbt/teile daneben.

4. Funktionsgraph
{"type":"funktionsgraph","x_min":-5,"x_max":5,"y_min":-5,"y_max":5,"gitter"?:true,
 "x_achse"?:"x","y_achse"?:"y","funktionen":[{"term":"0,5x^2-1","beschriftung"?:"f"}],
 "punkte"?:[{"x":1,"y":2,"beschriftung"?:"P"}]}
Terme nur in x mit Zahlen, + - * / ^, Klammern, pi, sqrt(), abs(), sin(), cos() (Bogenmaß);
"2x" ist erlaubt. Höchstens 4 Funktionen, 12 Punkte, Term bis 80 Zeichen.

5. Tabelle
{"type":"tabelle","kopf":["x","y"],"zeilen":[["1","2"],["2","4"]]}
Bis 8 Spalten, 15 Zeilen, Zellen bis 20 Zeichen; jede Zeile so lang wie der Kopf.
"""


# ------------------------------------------------------------------ Einbindung

MINT = re.compile(r"mathe|physik|chemie|technik|informatik|naturwiss|\bnw\b|werken|biolog", re.I)


def suits(subject: str | None) -> bool:
    """Fächer, in denen Aufgaben gezeichnete Abbildungen brauchen können."""
    return bool(MINT.search(subject or ""))


def prepared(spec: Any) -> dict:
    """Geprüfte Abbildung für eine gespeicherte Aufgabe: Beschreibung, Klartext
    und das SVG als data-URI (als <img> eingebunden, also ohne Skript)."""
    import base64
    figure = validate(spec)
    data = figure.model_dump(mode="json", exclude_none=True) if hasattr(figure, "model_dump") else spec
    svg = render(data)
    return {"figur": data, "figur_text": describe(data),
            "figur_src": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()}
