"""Runtime configuration via environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    history_db_path: Path
    webapp_db_path: Path
    frontend_dir: Path | None
    host: str
    port: int
    log_level: str
    supervisor_token: str | None
    supervisor_url: str
    dev_fake_user_id: str | None
    dev_fake_user_name: str | None
    is_dev: bool


def load() -> Settings:
    data_dir = Path(os.environ.get("WEBAPP_DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    frontend_env = os.environ.get("WEBAPP_FRONTEND_DIR")
    frontend_dir = Path(frontend_env) if frontend_env else None
    if frontend_dir and not frontend_dir.exists():
        frontend_dir = None

    return Settings(
        history_db_path=Path(
            os.environ.get("WEBAPP_HISTORY_DB", "/config/untis_archive/history.db")
        ),
        webapp_db_path=data_dir / "webapp.db",
        frontend_dir=frontend_dir,
        host=os.environ.get("WEBAPP_HOST", "127.0.0.1"),
        port=int(os.environ.get("WEBAPP_PORT", "8099")),
        log_level=os.environ.get("WEBAPP_LOG_LEVEL", "info"),
        supervisor_token=os.environ.get("SUPERVISOR_TOKEN"),
        supervisor_url=os.environ.get("SUPERVISOR_URL", "http://supervisor"),
        dev_fake_user_id=os.environ.get("DEV_FAKE_USER_ID"),
        dev_fake_user_name=os.environ.get("DEV_FAKE_USER_NAME"),
        is_dev=os.environ.get("WEBAPP_DEV", "0") == "1",
    )


SETTINGS = load()
