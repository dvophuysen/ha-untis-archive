"""Eine Überschriften-Antwort mit zu langem Titel oder ungefragtem Feld wird
gekürzt und gelesen, nicht verworfen: Sie ist bezahlt (am 19.09. zwei Seiten)."""
import json

from backend import vocab


def test_long_titles_and_extra_fields_do_not_discard_the_answer():
    answer = {"ueberschriften": [{"titel": "T" * 130, "erstes_wort": "w" * 100, "wo": "seitenkopf-extra"}] * 20,
              "beginnt_mit_ueberschrift": True, "hinweis_ohne_lernwoerter": "ungefragt"}
    found = vocab.HeadsOut.model_validate_json(json.dumps(answer))
    assert len(found.ueberschriften) == 16
    head = found.ueberschriften[0]
    assert len(head.titel) == 90 and len(head.erstes_wort) == 80 and len(head.wo) == 12
