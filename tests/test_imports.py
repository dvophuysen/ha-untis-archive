"""Jedes Backend-Modul muss sich übersetzen lassen. 0.63.0 startete nicht,
weil ein Syntaxfehler in main.py kein Test je geladen hatte."""
import py_compile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "schul_cockpit" / "backend"
MODULES = sorted(p for p in BACKEND.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.parametrize("path", MODULES, ids=lambda p: str(p.relative_to(BACKEND)))
def test_module_compiles(path):
    py_compile.compile(str(path), doraise=True)
