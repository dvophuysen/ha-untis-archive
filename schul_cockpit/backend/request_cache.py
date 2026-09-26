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


class _Memo(dict):
    closed = False


class _Idle(list):
    closed = False


@contextmanager
def scope():
    """Ein Merkzettel für die Dauer des Blocks. Verschachtelt gilt der äußere.

    Eine Hintergrundaufgabe, die im Block startet, erbt Merkzettel und
    Verbindungsliste (asyncio kopiert den Kontext). Nach dem Block sind beide
    geschlossen: Die Aufgabe liest dann ohne Merkzettel und bekommt nie eine der
    hier geschlossenen Verbindungen."""
    current = _CACHE.get()
    if current is not None and not current.closed:
        yield
        return
    cache, pool = _Memo(), _Idle()
    token, idle_token = _CACHE.set(cache), _IDLE.set(pool)
    try:
        yield
    finally:
        _IDLE.reset(idle_token)
        _CACHE.reset(token)
        cache.closed = pool.closed = True
        cache.clear()
        from .db import _POOL_LOCK
        with _POOL_LOCK:
            leftover = list(pool)
            pool.clear()
        for conn in leftover:
            try:
                conn.discard()
            except Exception:  # anderer Thread: schließt der Aufräumer
                pass


def idle() -> list | None:
    """Die freien Verbindungen des laufenden Aufrufs, ohne ``scope()`` None."""
    pool = _IDLE.get()
    return None if pool is None or pool.closed else pool


def forget() -> None:
    """Nach einem Schreibzugriff: alles Gemerkte des Aufrufs verwerfen."""
    cache = _CACHE.get()
    if cache is not None:
        cache.clear()


def _active() -> dict | None:
    cache = _CACHE.get()
    return None if cache is None or cache.closed else cache


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
            cache = _active()
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
