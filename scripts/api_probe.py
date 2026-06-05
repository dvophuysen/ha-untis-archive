"""Standalone probe for Phase A.

Reads credentials from environment variables, then calls each of the three
WebUntis endpoints and dumps the JSON to stdout. Lets us verify the API
client without involving Home Assistant.

Usage:

    export UNTIS_SERVER=herakles.webuntis.com
    export UNTIS_SCHOOL='Name der Schule'
    export UNTIS_USER=...
    export UNTIS_PASS=...
    # optional, only if auto-discovery via personId fails:
    # export UNTIS_STUDENT_ID=12345
    # export UNTIS_STUDENT_TYPE=5

    python scripts/api_probe.py

Acceptance: at least one timetable entry has a non-empty ``lstext`` and at
least one homework entry has non-empty ``text`` (assuming the school
actually uses those features).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Allow running the script directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.untis_archive.api import UntisAuthError, UntisClient, UntisError


def _env(name: str, required: bool = True) -> str | None:
    value = os.environ.get(name)
    if required and not value:
        print(f"ERROR: environment variable {name} is required", file=sys.stderr)
        sys.exit(2)
    return value


async def main() -> int:
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

    server = _env("UNTIS_SERVER")
    school = _env("UNTIS_SCHOOL")
    user = _env("UNTIS_USER")
    password = _env("UNTIS_PASS")

    override_id = os.environ.get("UNTIS_STUDENT_ID")
    override_type = os.environ.get("UNTIS_STUDENT_TYPE")
    elem_id = int(override_id) if override_id else None
    elem_type = int(override_type) if override_type else None

    today = date.today()
    start = today - timedelta(days=7)
    end = today + timedelta(days=7)

    client = UntisClient(server, school, user, password)
    try:
        try:
            session = await client.login()
        except UntisAuthError as err:
            print(f"LOGIN FAILED: {err}", file=sys.stderr)
            return 1

        print("=== SESSION ===")
        print(json.dumps(session.__dict__, indent=2, default=str))

        print("\n=== TIMETABLE (extended) ===")
        try:
            tt = await client.get_timetable(start, end, elem_id=elem_id, elem_type=elem_type)
            print(f"# {len(tt)} entries between {start} and {end}")
            print(json.dumps(tt, indent=2, ensure_ascii=False, default=str))
        except UntisError as err:
            print(f"TIMETABLE FAILED: {err}", file=sys.stderr)
            tt = []

        # Pick a recent period to ask period/info for.
        sample = None
        for entry in tt:
            if entry.get("id") and entry.get("date") and entry.get("startTime"):
                sample = entry
                break

        if sample:
            print("\n=== PERIOD INFO (sample) ===")
            try:
                day_int = int(sample["date"])
                day = date(day_int // 10000, (day_int // 100) % 100, day_int % 100)
                info = await client.get_period_info(
                    day=day,
                    start_time=int(sample["startTime"]),
                    end_time=int(sample["endTime"]),
                    period_id=int(sample["id"]),
                    elem_id=elem_id,
                    elem_type=elem_type,
                )
                print(f"# for period {sample['id']} on {day}")
                print(json.dumps(info, indent=2, ensure_ascii=False, default=str))
            except UntisError as err:
                print(f"PERIOD INFO FAILED: {err}", file=sys.stderr)
        else:
            print("\n=== PERIOD INFO ===\n# skipped: no sample period available")

        print("\n=== HOMEWORK ===")
        try:
            hw = await client.get_homework(start, end)
            print(json.dumps(hw, indent=2, ensure_ascii=False, default=str))
        except UntisError as err:
            print(f"HOMEWORK FAILED: {err}", file=sys.stderr)

        return 0
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
