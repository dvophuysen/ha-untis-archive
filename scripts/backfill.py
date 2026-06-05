"""Standalone backfill: pulls the maximum allowed window from WebUntis and
writes it into a local SQLite using the integration's storage module
directly — no Home Assistant required.

Useful for:
- bootstrapping a fresh DB after first install,
- inspecting what the integration would produce, on a workstation,
- debugging API or storage changes against real credentials.

Env vars:
    UNTIS_SERVER   e.g. gymnasium-am-wall.webuntis.com
    UNTIS_SCHOOL   the WebUntis loginName (NOT the display name)
    UNTIS_USER     the username
    UNTIS_PASS     the password
    DB_PATH        optional, default ./data/history.db
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
import types
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PKG = _ROOT / "custom_components" / "untis_archive"


def _load(name: str, file: Path):
    spec = importlib.util.spec_from_file_location(name, file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Build a synthetic package so the relative imports inside api.py /
# storage.py work without dragging in the HA-dependent __init__.
_pkg = types.ModuleType("untis_archive_pkg")
_pkg.__path__ = [str(_PKG)]
sys.modules["untis_archive_pkg"] = _pkg
const = _load("untis_archive_pkg.const", _PKG / "const.py")
api = _load("untis_archive_pkg.api", _PKG / "api.py")
storage = _load("untis_archive_pkg.storage", _PKG / "storage.py")


def _extract_lstext(period_info: dict) -> str:
    """Mirror of coordinator._extract_lstext, kept local so this script
    does not need to import coordinator.py (which depends on HA)."""
    if not isinstance(period_info, dict):
        return ""
    data = period_info.get("data") if isinstance(period_info.get("data"), dict) else period_info
    if not isinstance(data, dict):
        return ""
    blocks = data.get("blocks")
    if isinstance(blocks, list):
        for row in blocks:
            items = row if isinstance(row, list) else [row]
            for block in items:
                if not isinstance(block, dict):
                    continue
                topic = block.get("lessonTopic")
                if isinstance(topic, dict):
                    text = (topic.get("text") or "").strip()
                    if text:
                        return text
    return ""


def _env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        print(f"ERROR: env var {name} is required", file=sys.stderr)
        sys.exit(2)
    return v


async def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOGLEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    server = _env("UNTIS_SERVER")
    school = _env("UNTIS_SCHOOL")
    user = _env("UNTIS_USER")
    password = _env("UNTIS_PASS")
    db_path = Path(os.environ.get("DB_PATH", "./data/history.db")).resolve()

    print(f"DB: {db_path}")
    store = storage.UntisStorage(db_path)
    account_id = store.ensure_account(
        entry_id=f"backfill:{user}@{server}",
        name=f"backfill {user}",
        server=server,
        school=school,
        username=user,
        student_id=None,
        student_type=None,
    )
    print(f"account_id = {account_id}")

    client = api.UntisClient(server, school, user, password)
    try:
        try:
            session = await client.login()
        except api.UntisAuthError as err:
            print(f"LOGIN FAILED ({err.code}): {err}", file=sys.stderr)
            return 1
        print(
            f"login ok — personId={session.person_id} "
            f"type={session.person_type} klasse={session.klasse_id}"
        )

        today = date.today()
        tt_start = today - timedelta(days=const.WINDOW_DAYS_BACK)
        tt_end = today + timedelta(days=const.WINDOW_DAYS_FORWARD)
        abs_start = today - timedelta(days=const.ABSENCE_WINDOW_DAYS_BACK)
        abs_end = today + timedelta(days=const.ABSENCE_WINDOW_DAYS_FORWARD)

        # --- Stundenplan ---
        print(f"\n--- Stundenplan {tt_start} – {tt_end} ---")
        raw_tt = await client.get_timetable(tt_start, tt_end)
        ins = upd = same = 0
        need_topic: list[dict] = []
        for raw in raw_tt:
            try:
                lesson = storage.normalize_period(raw)
            except (KeyError, TypeError, ValueError):
                continue
            res = store.upsert_lesson(account_id, lesson)
            if res.action == "inserted":
                ins += 1
            elif res.action == "updated":
                upd += 1
            else:
                same += 1
            if not lesson.get("lstext") and lesson.get("code") != "cancelled":
                need_topic.append(lesson)
        print(f"  lessons new/upd/same: {ins}/{upd}/{same} (raw {len(raw_tt)})")

        # --- Lehrstoff per period/info nachholen ---
        topic_ok = topic_fail = 0
        for lesson in need_topic:
            try:
                info = await client.get_period_info(
                    day=date.fromisoformat(lesson["date"]),
                    start_time=lesson["start_time"],
                    end_time=lesson["end_time"],
                    period_id=lesson["untis_period_id"],
                )
            except api.UntisApiError:
                topic_fail += 1
                continue
            text = _extract_lstext(info)
            update = {
                "untis_period_id": lesson["untis_period_id"],
                "date": lesson["date"],
                "start_time": lesson["start_time"],
                "end_time": lesson["end_time"],
                "period_info_json": json.dumps(info, ensure_ascii=False, default=str),
            }
            if text:
                update["lstext"] = text
                update["is_supervision_guess"] = bool(
                    lesson["code"] == "irregular" and not text
                )
                topic_ok += 1
            store.upsert_lesson(account_id, update)
        print(f"  Lehrstoff nachgezogen: {topic_ok} (Fehler {topic_fail})")

        # --- Hausaufgaben ---
        print(f"\n--- Hausaufgaben {tt_start} – {tt_end} ---")
        try:
            raw_hw = await client.get_homework(tt_start, tt_end)
        except api.UntisApiError as e:
            print(f"  FEHLER: {e}")
            raw_hw = {}
        hw_n = 0
        for hw in storage.collect_homework(raw_hw):
            store.upsert_homework(account_id, hw)
            hw_n += 1
        print(f"  homework eingesammelt: {hw_n}")

        # --- Fehlzeiten ---
        print(f"\n--- Fehlzeiten {abs_start} – {abs_end} ---")
        try:
            raw_abs = await client.get_absences(abs_start, abs_end)
        except api.UntisApiError as e:
            print(f"  FEHLER: {e}")
            raw_abs = {}
        abs_n = 0
        for absence in storage.collect_absences(raw_abs):
            store.upsert_absence(account_id, absence)
            abs_n += 1
        print(f"  absences eingesammelt: {abs_n}")

        flagged = store.recompute_attendance(
            account_id, tt_start.isoformat(), tt_end.isoformat()
        )
        print(f"  Lessons als 'abwesend' markiert: {flagged}")

        store.mark_pull_complete(account_id)
        return 0
    finally:
        await client.close()
        store.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
