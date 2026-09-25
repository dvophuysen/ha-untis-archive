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
# the current week (the Schule instance allows roughly -5 / +9 days). Pulling
# wider just wastes traffic — the server silently truncates anyway.
WINDOW_DAYS_BACK = 5
WINDOW_DAYS_FORWARD = 9

# Der Hausaufgaben-Endpoint (/api/homeworks/lessons) unterliegt NICHT der
# Timetable-Fensterbeschränkung und akzeptiert weite Bereiche. Großzügig
# zurückschauen, damit (a) eine mehrtägige HA-Downtime keine in der
# Zwischenzeit vergebenen Aufgaben verliert und (b) der completed-Status
# der letzten Wochen weiter aktualisiert wird; nach vorn, damit weit im
# Voraus vergebene/fällige Aufgaben sicher mitkommen.
HOMEWORK_WINDOW_DAYS_BACK = 21
HOMEWORK_WINDOW_DAYS_FORWARD = 30

# The absence endpoint accepts the whole school year. Grab a generous
# window so we never miss past absences and can backfill on first pull.
ABSENCE_WINDOW_DAYS_BACK = 400
ABSENCE_WINDOW_DAYS_FORWARD = 30

DB_SUBDIR = "untis_archive"
DB_FILENAME = "history.db"
DOCS_SUBDIR = "docs"

DEFAULT_CLIENT_NAME = "ha-untis-archive"

# WebUntis-Fehlercode für falschen Benutzernamen oder falsches Passwort.
INVALID_CREDENTIALS = -8504

# WebUntis-Elementtyp „Schüler“ (1 Klasse, 2 Lehrkraft, 3 Fach, 4 Raum,
# 5 Schüler). Mit gesetzter Schüler-ID wird der Plan dieses Schülers geholt.
STUDENT_ELEMENT_TYPE = 5

# Lehrstoff trägt die Lehrkraft oft erst nach der Stunde ins Klassenbuch ein;
# der Stundenplan-Zeitstempel (getLatestImportTime) ändert sich dadurch nicht.
# Deshalb fragt jeder Abruf für Stunden der letzten Tage ohne Lehrstoff
# period/info erneut ab, begrenzt, damit WebUntis nicht überlastet wird.
TOPIC_BACKFILL_DAYS = 5
TOPIC_BACKFILL_MAX_PER_PULL = 40

# Offene Hausaufgaben, die länger als so viele Tage überfällig sind, fallen
# aus dem Sensor (die Zeilen bleiben in der Datenbank).
OPEN_HOMEWORK_MAX_OVERDUE_DAYS = 14

# Fehlzeiten, die WebUntis nicht mehr liefert, werden nur im laufenden
# Schuljahr entfernt, und nur bis zu so vielen je Abruf. Mehr deutet auf eine
# unvollständige Antwort hin; dann bleibt alles stehen.
ABSENCE_MAX_DELETIONS_PER_PULL = 5
