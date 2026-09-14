"""Small encrypted-at-rest store for credentials used by server-side connectors.

The Fernet key lives beside, rather than inside, webapp.db. Home Assistant backs
up the complete add-on data directory, so database and key remain recoverable.
The application backup intentionally never exports the key or usable passwords.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import SETTINGS


def _key_path() -> Path:
    return SETTINGS.webapp_db_path.parent / "connector-secrets.key"


def _load_or_create_key() -> bytes:
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        key = path.read_bytes().strip()
    except FileNotFoundError:
        key = Fernet.generate_key()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:  # another worker won the race
            key = path.read_bytes().strip()
        else:
            with os.fdopen(fd, "wb") as handle:
                handle.write(key + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def encrypt_secret(value: str) -> str:
    return Fernet(_load_or_create_key()).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    try:
        return Fernet(_load_or_create_key()).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise RuntimeError("Gespeicherter Zugang kann nicht entschlüsselt werden") from exc
