"""Async WebUntis client.

Covers the three endpoints needed by this integration:

1. JSON-RPC (``/WebUntis/jsonrpc.do``) for the timetable.
2. Internal REST ``/WebUntis/api/public/period/info`` for the lesson topic
   (``lstext`` body shown in the official iOS app).
3. Internal REST ``/WebUntis/api/homeworks/lessons`` for homework.

Endpoints 2 and 3 are not part of the documented JSON-RPC API; they are
reverse-engineered from the WebUntis web UI and may change without notice.

A single :class:`httpx.AsyncClient` is used. The JSON-RPC ``authenticate``
call also yields a ``JSESSIONID`` cookie which the internal REST endpoints
accept, as long as the ``schoolname`` cookie is set alongside.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from .const import DEFAULT_CLIENT_NAME

_LOGGER = logging.getLogger(__name__)


class UntisError(Exception):
    """Base error."""


class UntisAuthError(UntisError):
    """Login failed."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class UntisApiError(UntisError):
    """A WebUntis call returned an error or an unexpected payload."""


@dataclass
class UntisSession:
    session_id: str
    person_type: int
    person_id: int
    klasse_id: int | None = None


def _date_to_untis(d: date) -> int:
    """WebUntis uses YYYYMMDD as an integer."""
    return int(d.strftime("%Y%m%d"))


def _schoolname_cookie(school: str) -> str:
    """Encode the school name the way WebUntis sets its ``schoolname`` cookie.

    Format observed in the wild: ``_<base64(school) without padding>``.
    Plain school name also works on most instances; the encoded form is
    more compatible.
    """
    encoded = base64.b64encode(school.encode("utf-8")).decode("ascii").rstrip("=")
    return f"_{encoded}"


class UntisClient:
    """Thin async wrapper around the three WebUntis endpoints we need."""

    def __init__(
        self,
        server: str,
        school: str,
        username: str,
        password: str,
        *,
        client_name: str = DEFAULT_CLIENT_NAME,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._server = server.strip().rstrip("/").removeprefix("https://").removeprefix("http://")
        self._school = school.strip()
        self._username = username
        self._password = password
        self._client_name = client_name
        # httpx.AsyncClient is created lazily inside _ensure_http() because
        # its constructor loads the CA certificate bundle synchronously
        # (ssl.SSLContext.load_verify_locations) — doing that on the event
        # loop trips Home Assistant's "blocking call detected" guard.
        self._http: httpx.AsyncClient | None = http_client
        self._owns_http = http_client is None
        self._session: UntisSession | None = None

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            loop = asyncio.get_running_loop()
            self._http = await loop.run_in_executor(
                None,
                lambda: httpx.AsyncClient(
                    base_url=f"https://{self._server}",
                    timeout=30.0,
                    follow_redirects=True,
                    headers={"User-Agent": f"{self._client_name}/0.1"},
                ),
            )
        return self._http

    async def __aenter__(self) -> "UntisClient":
        await self.login()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    @property
    def session(self) -> UntisSession:
        if self._session is None:
            raise UntisAuthError("Not logged in. Call login() first.")
        return self._session

    async def login(self) -> UntisSession:
        """Authenticate against the JSON-RPC endpoint.

        Sets ``JSESSIONID`` (via Set-Cookie) and the ``schoolname`` cookie
        explicitly so the internal REST endpoints accept the session.
        """
        payload = {
            "id": "ha-untis-login",
            "method": "authenticate",
            "params": {
                "user": self._username,
                "password": self._password,
                "client": self._client_name,
            },
            "jsonrpc": "2.0",
        }
        http = await self._ensure_http()
        try:
            resp = await http.post(
                "/WebUntis/jsonrpc.do",
                params={"school": self._school},
                json=payload,
            )
        except httpx.HTTPError as err:
            raise UntisAuthError(f"Login request failed: {err}") from err

        # WebUntis returns the JSON-RPC error envelope with non-200 statuses too
        # (e.g. HTTP 404 for an unknown school carries code=-8500). Parse the body
        # first; only fall back to a status-code message if it isn't JSON-RPC.
        try:
            data = resp.json()
        except ValueError as err:
            raise UntisAuthError(
                f"Login HTTP {resp.status_code}: {resp.text[:200]}"
            ) from err
        if isinstance(data, dict) and "error" in data:
            err_obj = data["error"] or {}
            code = err_obj.get("code") if isinstance(err_obj, dict) else None
            message = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
            raise UntisAuthError(message or f"Login error: {err_obj}", code=code)
        if resp.status_code != 200:
            raise UntisAuthError(f"Login HTTP {resp.status_code}: {resp.text[:200]}")
        result = data.get("result") or {}
        try:
            session = UntisSession(
                session_id=result["sessionId"],
                person_type=int(result["personType"]),
                person_id=int(result["personId"]),
                klasse_id=int(result["klasseId"]) if result.get("klasseId") else None,
            )
        except (KeyError, TypeError, ValueError) as err:
            raise UntisAuthError(f"Unexpected login payload: {result}") from err

        # The JSESSIONID is already in the cookie jar via Set-Cookie.
        # The schoolname cookie is needed by /api/public/* endpoints.
        http.cookies.set("schoolname", _schoolname_cookie(self._school))

        self._session = session
        _LOGGER.debug("Logged in: personType=%s personId=%s", session.person_type, session.person_id)
        return session

    async def logout(self) -> None:
        if self._session is None:
            return
        try:
            await self._rpc("logout", {})
        except UntisError as err:
            _LOGGER.debug("logout RPC failed (ignored): %s", err)
        finally:
            self._session = None

    async def close(self) -> None:
        await self.logout()
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _rpc(self, method: str, params: dict[str, Any] | list[Any]) -> Any:
        body = {
            "id": f"ha-untis-{method}",
            "method": method,
            "params": params,
            "jsonrpc": "2.0",
        }
        try:
            resp = await self._http.post(
                "/WebUntis/jsonrpc.do",
                params={"school": self._school},
                json=body,
            )
        except httpx.HTTPError as err:
            raise UntisApiError(f"RPC {method} failed: {err}") from err
        if resp.status_code != 200:
            raise UntisApiError(f"RPC {method} HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if "error" in data:
            raise UntisApiError(f"RPC {method} error: {data['error']}")
        return data.get("result")

    async def get_timetable(
        self,
        start: date,
        end: date,
        *,
        elem_id: int | None = None,
        elem_type: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch the timetable for the given window, in extended form.

        Defaults to the logged-in person.
        """
        s = self.session
        params = {
            "options": {
                "element": {
                    "id": elem_id if elem_id is not None else s.person_id,
                    "type": elem_type if elem_type is not None else s.person_type,
                },
                "startDate": _date_to_untis(start),
                "endDate": _date_to_untis(end),
                "showLsText": True,
                "showSubstText": True,
                "showStudentgroup": True,
                "showLsNumber": True,
                "showInfo": True,
                "showBooking": True,
                "klasseFields": ["id", "name", "longname"],
                "roomFields": ["id", "name", "longname"],
                "subjectFields": ["id", "name", "longname"],
                "teacherFields": ["id", "name", "longname"],
            }
        }
        result = await self._rpc("getTimetable", params)
        return result or []

    async def get_period_info(
        self,
        *,
        day: date,
        start_time: int,
        end_time: int,
        period_id: int,
        elem_id: int | None = None,
        elem_type: int | None = None,
    ) -> dict[str, Any]:
        """Fetch the lesson topic body for a single period.

        ``start_time`` / ``end_time`` are WebUntis HHMM integers (e.g. 800,
        1545) as returned by ``getTimetable``.
        """
        s = self.session
        params = {
            "date": _date_to_untis(day),
            "starttime": start_time,
            "endtime": end_time,
            "elemid": elem_id if elem_id is not None else s.person_id,
            "elemtype": elem_type if elem_type is not None else s.person_type,
            "ttFmtId": 1,
            "selectedPeriodId": period_id,
        }
        try:
            resp = await self._http.get("/WebUntis/api/public/period/info", params=params)
        except httpx.HTTPError as err:
            raise UntisApiError(f"period/info failed: {err}") from err
        if resp.status_code != 200:
            raise UntisApiError(
                f"period/info HTTP {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()

    async def get_teachers(self) -> list[dict[str, Any]]:
        """Master list of all teachers at the school (~99 at GaW).

        Needed so we can resolve a Kürzel like 'BRU' (which Untis attaches
        as ``orgname`` to substitutions) to a full name. Required because
        the substitution payload only carries the Kürzel, not the longname.
        """
        return await self._rpc("getTeachers", {}) or []

    async def get_klassen(self) -> list[dict[str, Any]]:
        return await self._rpc("getKlassen", {}) or []

    async def get_current_schoolyear(self) -> dict[str, Any]:
        return await self._rpc("getCurrentSchoolyear", {}) or {}

    async def get_holidays(self) -> list[dict[str, Any]]:
        return await self._rpc("getHolidays", {}) or []

    async def get_latest_import_time(self) -> int | None:
        """Server-side timestamp (ms since epoch) of the most recent
        timetable import. Used to skip the timetable pass when nothing
        new has been imported since our last pull.
        """
        result = await self._rpc("getLatestImportTime", {})
        return int(result) if isinstance(result, (int, float)) else None

    async def get_absences(self, start: date, end: date) -> dict[str, Any]:
        """Fetch absences for the logged-in student.

        Endpoint: ``/WebUntis/api/classreg/absences/students``. Accepts the
        whole school year, so this is the one place we can backfill from.
        Requires YYYYMMDD integer dates and the student id from the session.
        """
        s = self.session
        params = {
            "startDate": _date_to_untis(start),
            "endDate": _date_to_untis(end),
            "studentId": s.person_id,
            "excuseStatusId": -1,
            "includeTodaysAbsence": "true",
        }
        try:
            resp = await self._http.get(
                "/WebUntis/api/classreg/absences/students", params=params
            )
        except httpx.HTTPError as err:
            raise UntisApiError(f"absences fetch failed: {err}") from err
        if resp.status_code != 200:
            raise UntisApiError(
                f"absences HTTP {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()

    async def get_homework(self, start: date, end: date) -> dict[str, Any]:
        """Fetch homework entries for the given window."""
        # Endpoint requires YYYYMMDD integers; ISO strings trigger HTTP 500.
        params = {
            "startDate": _date_to_untis(start),
            "endDate": _date_to_untis(end),
        }
        try:
            resp = await self._http.get(
                "/WebUntis/api/homeworks/lessons", params=params
            )
        except httpx.HTTPError as err:
            raise UntisApiError(f"homeworks/lessons failed: {err}") from err
        if resp.status_code != 200:
            raise UntisApiError(
                f"homeworks/lessons HTTP {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()
