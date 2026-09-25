"""Tests der HA-Komponente gegen einen echten Home-Assistant-Kern
(pytest-homeassistant-custom-component). Getrennt von ``tests/``, weil
sie eine eigene Umgebung mit Home Assistant brauchen:

    pip install pytest-homeassistant-custom-component
    python -m pytest tests_ha -c tests_ha/pytest.ini
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def isolated_config_dir(request, tmp_path):
    """Jede Prüfung mit eigener ``history.db``. Sonst liegt sie im
    gemeinsamen Testkonfigurationsordner des Pakets und wächst über alle
    Läufe hinweg."""
    if "hass" in request.fixturenames:
        request.getfixturevalue("hass").config.config_dir = str(tmp_path)
    yield
