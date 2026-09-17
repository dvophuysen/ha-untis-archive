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


def test_no_flat_ai_option_survived_the_move_to_the_platform_block():
    # Alte Namen dürfen nicht stehen bleiben: der Supervisor würde sie behalten
    # und das Backend liest sie nicht mehr, also liefe die App still ohne sie.
    assert not [k for k in CONFIG['options'] if k.startswith('learning_ai')]
    assert not [k for k in CONFIG['schema'] if k.startswith('learning_ai')]


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


def test_both_foundries_are_empty_by_default_and_the_key_is_a_password():
    for name in ('foundry_1', 'foundry_2'):
        assert CONFIG['options']['ki_plattformen'][name] == {'endpunkt': '', 'api_key': ''}
        assert CONFIG['schema']['ki_plattformen'][name]['api_key'] == 'password?'


def test_every_tier_offers_the_same_four_fields_and_a_foundry_choice():
    from backend.learning import TIERS
    assert set(CONFIG['options']['ki_modelle']) == set(TIERS)
    for tier, entry in CONFIG['options']['ki_modelle'].items():
        assert entry['modellname'], f'{tier}: ohne Vorgabemodell'
        # Leerer Bereitstellungsname heißt „wie der Modellname"; 0 heißt „Satz aus der Tabelle".
        assert entry['bereitstellungsname'] == '' and entry['foundry'] == '1'
        assert entry['preis_eingang'] == 0 and entry['preis_ausgang'] == 0
        assert CONFIG['schema']['ki_modelle'][tier]['foundry'] == 'list(1|2)'


def test_nested_options_match_their_schema_shape():
    def walk(options, schema, prefix=''):
        assert set(options) <= set(schema), f'{prefix}: ohne Schema {sorted(set(options)-set(schema))}'
        for key, value in options.items():
            if isinstance(value, dict):
                assert isinstance(schema[key], dict), f'{prefix}{key}: Block braucht Blockschema'
                walk(value, schema[key], f'{prefix}{key}.')
    walk(CONFIG['options'], CONFIG['schema'])
