"""Attendance compatibility for archives that marked lateness as absence.

The archive remains read-only. A connection-local lessons view corrects old
flags for every app consumer, including direct SQL aggregates and feedback.
Classification uses the source reason, never a guessed duration threshold.
"""

import sqlite3

LATE_REASON_SQL = "lower(trim(coalesce(reason, ''))) IN ('verspätet', 'verspätung')"


def install_attendance_view(conn: sqlite3.Connection) -> None:
    columns = [r[1] for r in conn.execute('PRAGMA main.table_info(lessons)')]
    absence_columns = {r[1] for r in conn.execute('PRAGMA main.table_info(absences)')}
    needed = {'account_id', 'start_date', 'end_date', 'start_time', 'end_time', 'reason'}
    if not needed <= absence_columns or not {'was_absent', 'date', 'account_id', 'start_time', 'end_time'} <= set(columns):
        return
    overlap = """a.account_id=l.account_id
        AND l.date BETWEEN a.start_date AND a.end_date
        AND (l.date > a.start_date OR l.end_time > a.start_time)
        AND (l.date < a.end_date OR l.start_time < a.end_time)"""
    late = LATE_REASON_SQL.replace('reason', 'a.reason')
    only_late = f"""EXISTS (SELECT 1 FROM main.absences a WHERE {overlap} AND {late})
        AND NOT EXISTS (SELECT 1 FROM main.absences a WHERE {overlap} AND NOT ({late}))"""
    # Preserve the archive row cursor for paginated read integrations.
    fields = ['l.rowid AS rowid']
    for name in columns:
        quoted = '"' + name.replace('"', '""') + '"'
        if name == 'was_absent':
            fields.append(f'CASE WHEN ({only_late}) THEN 0 ELSE l.was_absent END AS was_absent')
        elif name == 'absence_reason':
            fields.append(f'CASE WHEN ({only_late}) THEN NULL ELSE l.absence_reason END AS absence_reason')
        else:
            fields.append('l.' + quoted)
    conn.execute('CREATE TEMP VIEW lessons AS SELECT ' + ', '.join(fields) + ' FROM main.lessons l')
