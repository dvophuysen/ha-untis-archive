"""Constants for the UNTIS Archive integration."""

from __future__ import annotations

DOMAIN = "untis_archive"

CONF_SERVER = "server"
CONF_SCHOOL = "school"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_STUDENT_ID = "student_id"
CONF_DISPLAY_NAME = "display_name"

UPDATE_INTERVAL_HOURS = 1
WINDOW_DAYS = 14

DB_SUBDIR = "untis_archive"
DB_FILENAME = "history.db"
DOCS_SUBDIR = "docs"

DEFAULT_CLIENT_NAME = "ha-untis-archive"
