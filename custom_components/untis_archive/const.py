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

# Schools usually restrict the JSON-RPC timetable to a small window around
# the current week (the GaW instance allows roughly -5 / +9 days). Pulling
# wider just wastes traffic — the server silently truncates anyway.
WINDOW_DAYS_BACK = 5
WINDOW_DAYS_FORWARD = 9

# The absence endpoint accepts the whole school year. Grab a generous
# window so we never miss past absences and can backfill on first pull.
ABSENCE_WINDOW_DAYS_BACK = 400
ABSENCE_WINDOW_DAYS_FORWARD = 30

DB_SUBDIR = "untis_archive"
DB_FILENAME = "history.db"
DOCS_SUBDIR = "docs"

DEFAULT_CLIENT_NAME = "ha-untis-archive"
