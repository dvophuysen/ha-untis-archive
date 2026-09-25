"""App-gezeichnete Abbildungen (D197): Prüfung, SVG, Klartext."""
import copy
import json
import math
import xml.etree.ElementTree as ET

import pytest
from backend import figures as F

NS = "{http://www.w3.org/2000/svg}"

SCHALTUNG = {
    "type": "schaltplan", "titel": "Parallelschaltung",
    "quelle": {"art": "batterie", "beschriftung": "4,5 V"},
    "netz": {"reihe": [
        {"teil": "schalter", "id": "S1", "zustand": "geschlossen"},
        {"parallel": [
            {"reihe": [{"teil": "lampe", "id": "L1"}, {"teil": "amperemeter", "id": "A2"}]},
            {"reihe": [{"teil": "lampe", "id": "L2"}]},
        ]},
        {"teil": "amperemeter", "id": "A1"},
    ]},
    "messgeraete": [{"teil": "voltmeter", "id": "V1", "ueber": "L1"}],
}
ZAHLENSTRAHL = {"type": "zahlenstrahl", "von": 0, "bis": 2, "schritt": "1/4",
                "marken": [{"wert": "3/4", "beschriftung": "A"}],
                "spruenge": [{"von": 0, "bis": "3/4", "beschriftung": "+3/4"}]}
BRUCHSTREIFEN = {"type": "bruchstreifen", "balken": [
    {"teile": 4, "gefaerbt": 3, "beschriftung": "Streifen A"}, {"teile": 8, "gefaerbt": 6}]}
GRAPH = {"type": "funktionsgraph", "titel": "Hyperbel", "funktionen": [
    {"term": "1/x", "beschriftung": "g"}, {"term": "0,5x^2-1"}],
    "punkte": [{"x": 2, "y": 1, "beschriftung": "P"}]}
TABELLE = {"type": "tabelle", "kopf": ["x", "y"], "zeilen": [[1, 2.5], ["2", "4"]]}


def _svg(spec):
    s = F.render(spec)
    root = ET.fromstring(s)
    assert root.tag == NS + "svg"
    assert root.get("width") and root.get("height") and root.get("viewBox")
    assert root.get("font-family") == "sans-serif"
    for el in root.iter():
        assert el.tag.split("}")[-1] not in ("script", "foreignObject", "image", "a")
        for k, v in el.attrib.items():
            assert not k.startswith("on") and "href" not in k
            assert "url(" not in v.replace("url(#", "")
    texte = " ".join("".join(el.itertext()) for el in root.iter(NS + "text"))
    return s, texte


def test_schaltplan_zeichnet_alle_kennungen():
    s, texte = _svg(SCHALTUNG)
    for kennung in ("S1", "L1", "L2", "A1", "A2", "V1", "4,5 V", "Parallelschaltung"):
        assert kennung in texte
    assert "matplotlib" not in s


def test_schaltplan_beschreibung_nennt_topologie():
    text = F.describe(SCHALTUNG)
    assert "L1 und L2 liegen parallel" in text
    assert "A1 liegt in der Hauptleitung" in text
    assert "A2 liegt im Zweig mit L1" in text
    assert "V1 liegt parallel zu L1" in text
    assert "Schalter S1 (geschlossen)" in text
    assert text in F.render(SCHALTUNG)   # zugleich Alternativtext


def test_schaltplan_varianten():
    spec = {"type": "schaltplan", "quelle": {"art": "quelle", "id": "U", "beschriftung": "12 V"},
            "netz": {"reihe": [
                {"teil": "widerstand", "id": "R1", "beschriftung": "100 Ω"},
                {"parallel": [{"teil": "motor", "id": "M1"},
                              {"reihe": [{"teil": "diode", "id": "D1", "sperrrichtung": True},
                                         {"parallel": [{"teil": "lampe", "id": "L1"},
                                                       {"teil": "lampe", "id": "L2"}]}]},
                              {"teil": "schalter", "id": "S2", "zustand": "offen"}]},
                {"teil": "knoten", "id": "K"}]},
            "messgeraete": [{"teil": "voltmeter", "id": "V1", "ueber": "quelle"}]}
    _, texte = _svg(spec)
    for kennung in ("R1", "100 Ω", "M1", "D1", "L1", "L2", "S2", "K", "V1", "U 12 V"):
        assert kennung in texte
    text = F.describe(spec)
    assert "M1, D1 und S2 liegen parallel" in text
    assert "in Sperrrichtung" in text and "misst die Spannung an der Quelle" in text
    _svg({"type": "schaltplan", "netz": {"teil": "lampe", "id": "L1"}})


def _fehler(spec, teil):
    with pytest.raises(ValueError) as e:
        F.validate(spec)
    assert teil in str(e.value), str(e.value)
    assert str(e.value).startswith("Abbildung ungültig")


def test_schaltplan_lehnt_falsches_ab():
    _fehler({"type": "schaltplan", "netz": {"teil": "kondensator", "id": "C1"}},
            "unzulässiger Wert")
    _fehler({"type": "schaltplan", "netz": {"reihe": [{"teil": "lampe"}]}}, "id: fehlt")
    _fehler({"type": "schaltplan", "netz": {"serie": []}}, "„teil“, „reihe“ oder „parallel“")
    _fehler({"type": "schaltplan", "netz": {"teil": "schalter", "id": "S1"}}, "zustand")
    tief = {"teil": "lampe", "id": "L1"}
    for i in range(4):
        tief = {"parallel": [tief, {"teil": "lampe", "id": f"X{i}"}]}
    _fehler({"type": "schaltplan", "netz": tief}, "Parallelschaltungen ineinander")
    viele = [{"teil": "lampe", "id": f"L{i}"} for i in range(13)]
    _fehler({"type": "schaltplan", "netz": {"reihe": viele}}, "zu viele")
    elf = [{"teil": "lampe", "id": f"L{i}"} for i in range(11)]
    _fehler({"type": "schaltplan", "netz": {"reihe": elf}, "messgeraete": [
        {"teil": "voltmeter", "id": "V1", "ueber": "L1"},
        {"teil": "voltmeter", "id": "V2", "ueber": "L2"}]}, "höchstens 12")
    doppelt = copy.deepcopy(SCHALTUNG)
    doppelt["netz"]["reihe"][2]["id"] = "A2"
    _fehler(doppelt, "doppelt")
    falsch = copy.deepcopy(SCHALTUNG)
    falsch["messgeraete"][0]["ueber"] = "L9"
    _fehler(falsch, "ueber")
    _fehler({"type": "schaltplan", "netz": {"teil": "lampe", "id": "L1", "farbe": "rot"}},
            "unbekanntes Feld")
    _fehler({"type": "schaltplan", "netz": {"teil": "lampe", "id": "<b>"}}, "Kennung")


def test_roh_eingaben_werden_begrenzt():
    _fehler({"type": "kreisdiagramm"}, "unbekannter Typ")
    _fehler("kein json", "JSON")
    _fehler([1, 2], "Objekt")
    tief: dict = {"teil": "lampe", "id": "L1"}
    for _ in range(40):
        tief = {"reihe": [tief]}
    _fehler({"type": "schaltplan", "netz": tief}, "verschachtelt")
    _fehler({"type": "tabelle", "kopf": ["x" * 20] * 8, "zeilen": [["a" * 5000] * 8]}, "")
    assert F.validate(json.dumps(TABELLE)).type == "tabelle"


def test_zahlenstrahl():
    _, texte = _svg(ZAHLENSTRAHL)
    assert "A" in texte and "+3/4" in texte
    text = F.describe(ZAHLENSTRAHL)
    assert "von 0 bis 2" in text and "3/4 („A“)" in text and "von 0 nach 3/4" in text
    assert F.zahl("1 1/2") == F.zahl("1,5") == F.zahl(1.5)
    assert F.zahl("-3/4") < 0
    _fehler({**ZAHLENSTRAHL, "marken": [{"wert": "5/2"}]}, "liegt nicht zwischen")
    _fehler({**ZAHLENSTRAHL, "bis": "drei"}, "keine Zahl")
    _fehler({**ZAHLENSTRAHL, "schritt": "1/100"}, "Hauptstrichen")
    _svg({"type": "zahlenstrahl", "von": -10, "bis": 30, "marken": [{"wert": -3.5}]})


def test_bruchstreifen():
    s, texte = _svg(BRUCHSTREIFEN)
    assert "Streifen A" in texte and "6" in texte and "8" in texte
    assert s.count("<rect") >= 4 + 8
    assert "6 von 8 Teilen gefärbt (6/8)" in F.describe(BRUCHSTREIFEN)
    _fehler({"type": "bruchstreifen", "balken": [{"teile": 4, "gefaerbt": 5}]}, "gefaerbt")
    _fehler({"type": "bruchstreifen", "balken": [{"teile": 25}]}, "zu groß")
    _fehler({"type": "bruchstreifen", "balken": [{"teile": 2}] * 7}, "zu viele")


def test_funktionsgraph():
    s, texte = _svg(GRAPH)
    assert "g" in texte and "P" in texte and "Hyperbel" in texte
    assert s.count("<polyline") >= 3   # 1/x in zwei Äste getrennt, dazu die Parabel
    text = F.describe(GRAPH)
    assert "y = 1/x („g“)" in text and "P(2 | 1)" in text


@pytest.mark.parametrize("term,x,y", [
    ("2x+1", 3, 7), ("-x^2", 3, -9), ("2^3^2", 0, 512), ("x²+1", 2, 5),
    ("3(x+1)", 1, 6), ("sqrt(x)", 9, 3), ("abs(x-5)", 2, 3), ("sin(pi/2)", 0, 1),
    ("cos(0)·2", 0, 2), ("0,5x", 4, 2), ("1/(x-1)", 1, math.nan), ("sqrt(x)", -1, math.nan),
])
def test_termparser(term, x, y):
    wert = F.kompiliere(term)(x)
    assert (math.isnan(wert) and math.isnan(y)) or wert == pytest.approx(y)


@pytest.mark.parametrize("term", [
    "__import__('os')", "x.__class__", "exp(x)", "sin x", "(x+1", "x+", "2**x" + "*" * 0 + "*",
    "lambda: 1", "x" * 81,
])
def test_termparser_lehnt_ab(term):
    with pytest.raises(ValueError):
        F.kompiliere(term)
    with pytest.raises(ValueError):
        F.validate({"type": "funktionsgraph", "funktionen": [{"term": term}]})


def test_tabelle():
    _, texte = _svg(TABELLE)
    assert "2,5" in texte and "y" in texte
    assert "x | y" in F.describe(TABELLE)
    _fehler({"type": "tabelle", "kopf": ["x", "y"], "zeilen": [["1"]]}, "Zellen")


def test_schema_und_anleitung():
    schema = F.json_schema()
    text = json.dumps(schema)
    for typ in ("schaltplan", "zahlenstrahl", "bruchstreifen", "funktionsgraph", "tabelle"):
        assert typ in text
        assert f'"type":"{typ}"' in F.SPEC_HELP.replace(" ", "")
    # Das Beispiel der Anleitung muss selbst gültig sein.
    start = F.SPEC_HELP.index('Beispiel: ') + len("Beispiel: ")
    beispiel = F.SPEC_HELP[start:F.SPEC_HELP.index("\n\n2.")]
    assert F.validate(json.loads(beispiel.replace("\n", ""))).type == "schaltplan"


def test_messgeraet_als_eigener_zweig():
    spec = {"type": "schaltplan", "netz": {"parallel": [
        {"teil": "lampe", "id": "L1"},
        {"reihe": [{"teil": "widerstand", "id": "R2"}, {"teil": "amperemeter", "id": "A1"}]},
        {"teil": "voltmeter", "id": "V9"}]}}
    text = F.describe(spec)
    assert "V9 bildet allein einen Zweig parallel zu L1 und R2" in text
    assert "A1 liegt im Zweig mit R2" in text
    _svg(spec)
