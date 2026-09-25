"""Merkzettel für einen einzelnen Aufruf.

Kompass und Heute fragen dieselben Lesefunktionen viele Male: das Raster jeder
Arbeit, das Vokabelpensum, den Stundenplan eines Zeitraums, den Wortbestand. Jede
Abfrage öffnet eine eigene Datenbankverbindung und rechnet neu; so kamen auf dem
Gerät mehrere Sekunden je Aufruf zusammen. Innerhalb von ``scope()`` rechnet eine
mit ``@memo`` markierte Funktion je Argumente nur einmal.

Der Merkzettel gilt nur für den laufenden Aufruf (ContextVar), nie darüber hinaus.
Ohne ``scope()`` verhalten sich die Funktionen wie bisher. Wer innerhalb eines
Aufrufs schreibt, was eine gemerkte Funktion liest, ruft ``forget()``. Ergebnisse
gehen als Kopie hinaus, damit ein Aufrufer, der sie verändert, keinem anderen
den Stand verdirbt.
"""
from __future__ import annotations

import contextvars
import copy
import functools
from contextlib import contextmanager

_CACHE: contextvars.ContextVar[dict | None] = contextvars.ContextVar("request_cache", default=None)
# Geschlossene Datenbankverbindungen des Aufrufs zum Wiederverwenden (db.py):
# Jede neue Verbindung liest zuerst das ganze Schema, das kostet mehr als die
# meisten Abfragen selbst.
_IDLE: contextvars.ContextVar[list | None] = contextvars.ContextVar("request_cache_idle", default=None)


@contextmanager
def scope():
    """Ein Merkzettel für die Dauer des Blocks. Verschachtelt gilt der äußere."""
    if _CACHE.get() is not None:
        yield
        return
    token, idle_token = _CACHE.set({}), _IDLE.set([])
    try:
        yield
    finally:
        idle = _IDLE.get() or []
        _IDLE.reset(idle_token)
        _CACHE.reset(token)
        for conn in idle:
            try:
                conn.discard()
            except Exception:  # anderer Thread: schließt der Aufräumer
                pass


def idle() -> list | None:
    """Die freien Verbindungen des laufenden Aufrufs, ohne ``scope()`` None."""
    return _IDLE.get()


def forget() -> None:
    """Nach einem Schreibzugriff: alles Gemerkte des Aufrufs verwerfen."""
    cache = _CACHE.get()
    if cache is not None:
        cache.clear()


def _shallow(value):
    return list(value) if isinstance(value, list) else value


def memo(fn=None, *, shallow: bool = False):
    """Ergebnis je Argumente merken, solange ein ``scope()`` läuft. ``shallow``
    kopiert nur die äußere Liste: für große Ergebnisse, deren Einträge kein
    Aufrufer verändert."""
    def wrap(f):
        clone = _shallow if shallow else copy.deepcopy

        @functools.wraps(f)
        def inner(*args, **kwargs):
            cache = _CACHE.get()
            if cache is None:
                return f(*args, **kwargs)
            key = (f.__module__, f.__qualname__, args, tuple(sorted(kwargs.items())))
            try:
                hit = key in cache
            except TypeError:  # nicht hashbare Argumente: nicht merken
                return f(*args, **kwargs)
            if not hit:
                cache[key] = f(*args, **kwargs)
            return clone(cache[key])
        return inner
    return wrap(fn) if fn is not None else wrap
