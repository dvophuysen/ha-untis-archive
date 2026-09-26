"""Gemeinsame Vorkehrungen für alle Tests.

Die Qualitätsprüfung der Musterlösungen (D217) ist ein eigener Modellaufruf.
Die Fixtures der übrigen Tests antworten auf jeden Aufruf mit ihrer Arbeit;
für sie gilt jede Musterlösung als geprüft. Tests der Prüfung selbst tragen
die Marke ``real_solution_check`` und laufen mit dem echten Ablauf."""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "real_solution_check: echte Prüfung der Musterlösungen (D217)")


@pytest.fixture(autouse=True)
def _solutions_checked(request, monkeypatch):
    if request.node.get_closest_marker("real_solution_check"):
        return
    from backend import solution_check

    async def ok(account_id, subject, tasks, flagged):
        return {i: solution_check.Checked(nr=i + 1, eigene_loesung="geprüft", ok=True) for i in range(len(tasks))}
    monkeypatch.setattr(solution_check, "_check", ok)
