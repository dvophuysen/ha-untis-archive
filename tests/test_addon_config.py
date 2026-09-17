"""Das Optionsschema des Add-ons muss zu den Vorgabewerten passen.

Anlass: `list(str)?` für eine Liste. `list(...)` ist in Home Assistant die
Auswahl aus festen Werten, eine Liste wird als YAML-Liste geschrieben. Der
Supervisor lehnte die Optionen ab („value must be one of ['str']"), das Add-on
ließ sich nicht mehr starten, und die Fehlermeldung schrieb alle Optionen im
Klartext ins Log. Das fällt nur an der laufenden Instanz auf, deshalb hier.
"""
from pathlib import Path

import yaml

CONFIG = yaml.safe_load((Path(__file__).parents[1] / 'schul_cockpit' / 'config.yaml').read_text())


def test_every_option_has_a_schema_entry():
    missing = set(CONFIG['options']) - set(CONFIG['schema'])
    assert not missing, f'ohne Schema: {sorted(missing)}'


def test_list_options_use_a_yaml_list_as_schema():
    for name, default in CONFIG['options'].items():
        if isinstance(default, list):
            schema = CONFIG['schema'][name]
            assert isinstance(schema, list), f"{name}: Liste braucht ein Listenschema, nicht {schema!r}"
            assert len(schema) == 1 and isinstance(schema[0], str), f'{name}: genau ein Elementtyp'


def test_scalar_options_do_not_use_a_list_schema():
    for name, default in CONFIG['options'].items():
        if not isinstance(default, list):
            assert not isinstance(CONFIG['schema'][name], list), f'{name}: Listenschema ohne Liste als Vorgabe'


def test_the_second_access_is_optional_and_empty_by_default():
    # Ohne Eintrag läuft alles über den ersten Zugang; ein Update darf nichts umstellen.
    assert CONFIG['options']['learning_ai_url_2'] == ''
    assert CONFIG['options']['learning_ai_key_2'] == ''
    assert CONFIG['options']['learning_ai_models_2'] == []
    assert CONFIG['schema']['learning_ai_key_2'] == 'password?'
