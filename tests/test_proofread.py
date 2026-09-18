"""Gegenlesen nur dort, wo die Lesung unsicher ist (D118).

Der Anlass steht im Beispiel: eine Arbeitsheftseite Mathematik mit sechzig
Zeilen gedruckten Aufgaben und drei eingetragenen Brüchen. Wer diese Textwand
ohne Foto daneben zwanzigmal bestätigt, bestätigt beim einundzwanzigsten Mal
blind."""

from backend import proofread

SEITE = """30 Rechnen mit Brüchen

Addieren von Brüchen

1 Berechne. Kürze, wenn möglich.

a) 2/7 + 4/7 = ___ [Kind: 6/7]
b) 1/10 + 7/10 = ___
c) 7/9 + 6/9 = ___ [Kind: 1 4/9]
d) 11/12 + 7/12 = ___
e) 13/8 + 7/8 + 4/8 = ___ [Kind: 3 2/8]
f) 5/6 + 11/6 + 17/6 = ___

2 Berechne. Kürze, wenn möglich.

a) 1/3 kg + 5/6 kg = ___
b) 2/7 m + 3/5 m = ___"""


def text_of(segments):
    return "".join(s.get("text", "") for s in segments)


def test_only_the_doubtful_lines_are_shown_with_their_context():
    view = proofread.view(SEITE)
    # Die drei Eintragungen des Kindes sind die Stellen, auf die es ankommt.
    assert view["spots"] == 3
    assert [s["text"] for s in view["segments"] if s["kind"] == "mark"] == [
        "[Kind: 6/7]", "[Kind: 1 4/9]", "[Kind: 3 2/8]"]
    # Gekürzt wird, was weit weg steht: die Überschrift oben und Aufgabe 2.
    assert view["shortened"]
    gekuerzt = text_of(view["segments"])
    assert "Rechnen mit Brüchen" not in gekuerzt and "2/7 m + 3/5 m" not in gekuerzt
    # Der unmittelbare Zusammenhang bleibt: je eine Zeile davor und dahinter.
    assert "b) 1/10 + 7/10" in gekuerzt and "d) 11/12 + 7/12" in gekuerzt
    assert sum(s["lines"] for s in view["segments"] if s["kind"] == "gap") == 10


def test_a_reported_doubt_carries_its_suggestion_to_the_same_spot():
    """Meldet die Lesung Zweifel an einer Stelle, die schon als Eintragung
    markiert ist, wird daraus eine Stelle mit Vorschlag — nicht zwei."""
    view = proofread.view(SEITE, [{"text": "[Kind: 1 4/9]", "alternative": "[Kind: 1 4/3]",
                                   "reason": "9 oder 3"}])
    marken = [s for s in view["segments"] if s["kind"] == "mark"]
    assert [(s["text"], s["suggest"], s["reason"]) for s in marken] == [
        ("[Kind: 1 4/9]", "[Kind: 1 4/3]", "9 oder 3")]
    # Eine gemeldete Stelle, die im Text nicht steht, hilft beim Suchen nicht
    # und wird gesondert genannt, statt stillschweigend zu verschwinden.
    lose = proofread.view(SEITE, [{"text": "steht hier nicht", "alternative": "", "reason": "x"}])
    assert [d["text"] for d in lose["loose"]] == ["steht hier nicht"]


def test_a_page_without_a_doubt_stays_whole_and_needs_no_second_look():
    sauber = "Aufgabe 1\nBerechne 2 + 2.\nAufgabe 2\nBerechne 3 + 3."
    view = proofread.view(sauber)
    assert view["spots"] == 0 and not view["shortened"]
    assert text_of(view["segments"]) == sauber
    assert proofread.uncertain(sauber) is False
    # Sauber gelesene Handschrift kostet keinen Blick, eine unleserliche Stelle schon.
    assert proofread.uncertain("a) ___ [Kind: 6/7]") is False
    assert proofread.uncertain("a) ___ [Kind: […]]") is True
    assert proofread.uncertain(sauber, [{"text": "2 + 2"}]) is True


def test_a_single_skipped_line_stays_because_a_gap_there_saves_nothing():
    text = "eins\nzwei [Kind: a]\ndrei\nvier\nfünf [Kind: b]\nsechs"
    view = proofread.view(text)
    assert not view["shortened"], "zwischen den Stellen liegt nur eine Zeile"
    assert "drei" in text_of(view["segments"]) and "vier" in text_of(view["segments"])


def test_a_correction_replaces_exactly_the_one_spot():
    text = "a) 2/7 + 4/7 = ___ [Kind: 6/7]\nb) 1/7 + 6/7 = ___ [Kind: 6/7]"
    fixed = proofread.resolve(text, "a) 2/7 + 4/7 = ___ [Kind: 6/7]", "a) 2/7 + 4/7 = ___ [Kind: 5/7]")
    assert fixed == "a) 2/7 + 4/7 = ___ [Kind: 5/7]\nb) 1/7 + 6/7 = ___ [Kind: 6/7]"
    # Eine Stelle, die über einen Zeilenumbruch hinweg gemeldet wurde, wird gefunden.
    assert proofread.resolve("Voc. pp.\n216/7", "Voc. pp. 216/7", "Voc. pp. 216/8") == "Voc. pp. 216/8"
    # Was nicht mehr dasteht, wird nicht geraten.
    assert proofread.resolve(text, "gibt es nicht", "x") is None


def test_what_the_reading_was_sure_of_may_disappear_into_the_gap():
    """Sagt die Lesung, wo sie unsicher war, bestimmen nur diese Stellen den
    Ausschnitt. Eine sicher gelesene Eintragung ist dann eine eindeutige
    Passage; sie bleibt markiert, wo sie ohnehin zu sehen ist, hält aber keine
    Zeile mehr offen."""
    view = proofread.view(SEITE, [{"text": "[Kind: 3 2/8]", "alternative": "[Kind: 3 2/3]",
                                   "reason": "8 oder 3"}])
    gezeigt = text_of(view["segments"])
    assert "[Kind: 3 2/8]" in gezeigt
    # Die beiden sicher gelesenen Eintragungen weiter oben tragen den Ausschnitt
    # nicht mehr; die erste liegt jetzt in der Lücke.
    assert "[Kind: 6/7]" not in gezeigt
    assert sum(s["lines"] for s in view["segments"] if s["kind"] == "gap") > 10
    # Markiert bleibt trotzdem jede Eintragung, die in den gezeigten Zeilen steht.
    eng = "a) ___ [Kind: 1]\nb) ___ [Kind: 7]\nc) weit weg\nd) weit weg\ne) weit weg\nf) ___ [Kind: 9]"
    nah = proofread.view(eng, [{"text": "[Kind: 1]", "alternative": "[Kind: 7]", "reason": "1 oder 7"}])
    assert [s["text"] for s in nah["segments"] if s["kind"] == "mark"] == ["[Kind: 1]", "[Kind: 7]"]
