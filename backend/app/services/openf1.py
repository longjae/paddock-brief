import asyncio
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import httpx

from app.schemas import EventDetail
from app.services.media_window import media_window
from app.services.sample_data import DEMO_EVENT
from app.services.time_format import format_kst_date_range, format_kst_datetime
from app.services.session_timing import historical_snapshot


OPENF1_BASE_URL = "https://api.openf1.org/v1"


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _slug(year: int, meeting_name: str) -> str:
    short_name = re.sub(r"\s+Grand Prix$", "", meeting_name, flags=re.IGNORECASE)
    normalized = re.sub(r"[^a-z0-9]+", "-", short_name.lower()).strip("-")
    return f"{year}-{normalized}"


def _session_short_name(name: str) -> str:
    return {
        "Practice 1": "FP1",
        "Practice 2": "FP2",
        "Practice 3": "FP3",
        "Sprint Qualifying": "SQ",
        "Sprint Shootout": "SQ",
        "Sprint": "S",
        "Qualifying": "Q",
        "Race": "R",
    }.get(name, name[:3].upper())


def _featured_meeting(rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Keep the latest race featured until the next race's Thursday media window opens."""
    opened = [
        row
        for row in rows
        if _parse_datetime(
            media_window(row["date_end"], row.get("gmt_offset", "+00:00:00"))["mediaOpenAt"]
        )
        <= now
    ]
    return opened[-1] if opened else rows[0]


class OpenF1Service:
    """Small public-data adapter with a short in-process cache and safe fallback."""

    def __init__(self) -> None:
        self._meetings: dict[int, list[dict[str, Any]]] = {}
        self._sessions: dict[int, list[dict[str, Any]]] = {}
        self._session_data_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._lap_cache: dict[tuple[int, int, int], tuple[float, dict[str, Any]]] = {}
        self._timing_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def _get(self, resource: str, **params: object) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=12.0) as client:
            for attempt in range(3):
                try:
                    response = await client.get(f"{OPENF1_BASE_URL}/{resource}", params=params)
                    response.raise_for_status()
                    payload = response.json()
                    break
                except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
                    retryable = isinstance(error, httpx.TimeoutException) or error.response.status_code in {429, 500, 502, 503, 504}
                    if attempt == 2 or not retryable:
                        raise
                    await asyncio.sleep(0.8 * (attempt + 1))
        return payload if isinstance(payload, list) else []

    async def meetings(self, year: int) -> list[dict[str, Any]]:
        if year not in self._meetings:
            async with self._lock:
                if year not in self._meetings:
                    rows = await self._get("meetings", year=year)
                    self._meetings[year] = sorted(
                        [row for row in rows if not row.get("is_cancelled") and "Test" not in row.get("meeting_name", "")],
                        key=lambda row: row["date_start"],
                    )
        return self._meetings[year]

    async def sessions(self, meeting_key: int) -> list[dict[str, Any]]:
        if meeting_key not in self._sessions:
            self._sessions[meeting_key] = sorted(
                [row for row in await self._get("sessions", meeting_key=meeting_key) if not row.get("is_cancelled")],
                key=lambda row: row["date_start"],
            )
        return self._sessions[meeting_key]

    async def list_events(self, year: int) -> list[dict[str, object]]:
        rows = await self.meetings(year)
        return [
            {
                "slug": _slug(year, row["meeting_name"]),
                "season": year,
                "round": index,
                "name": row["meeting_name"],
                "country": row["country_name"],
                "circuit": row["location"],
                "dateLabel": self._date_label(row["date_start"], row["date_end"]),
                **media_window(row["date_end"], row.get("gmt_offset", "+00:00:00")),
            }
            for index, row in enumerate(rows, start=1)
        ]

    async def featured_event(self, year: int) -> EventDetail:
        rows = await self.meetings(year)
        now = datetime.now(timezone.utc)
        meeting = _featured_meeting(rows, now)
        return await self._event_detail(meeting, rows.index(meeting) + 1)

    async def event_by_slug(self, slug: str) -> EventDetail | None:
        try:
            year = int(slug.split("-", 1)[0])
        except (ValueError, IndexError):
            return None
        rows = await self.meetings(year)
        for index, meeting in enumerate(rows, start=1):
            if _slug(year, meeting["meeting_name"]) == slug:
                return await self._event_detail(meeting, index)
        return None

    async def session_data(self, event: EventDetail, short_name: str) -> dict[str, Any] | None:
        """Return published results and tyre stints for an exact GP and session."""
        session = await self._matching_session(event, short_name)
        if session is None:
            return None
        started = _parse_datetime(session["date_start"]) <= datetime.now(timezone.utc)
        if not started:
            return {"status": "upcoming", "session": short_name, "drivers": [], "maxLap": 0, "source": "OpenF1"}

        key = session["session_key"]
        cached = self._session_data_cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        results, stints, drivers = await asyncio.gather(
            self._get("session_result", session_key=key),
            self._get("stints", session_key=key),
            self._get("drivers", session_key=key),
        )
        by_number = {row.get("driver_number"): row for row in drivers}
        by_stint: dict[int, list[dict[str, Any]]] = {}
        for row in stints:
            number = row.get("driver_number")
            if isinstance(number, int):
                by_stint.setdefault(number, []).append(row)

        def time_label(value: Any) -> str | None:
            if isinstance(value, list):
                value = next((item for item in reversed(value) if isinstance(item, (int, float))), None)
            if not isinstance(value, (int, float)):
                return None
            if value >= 3600:
                hours, remainder = divmod(float(value), 3600)
                minutes, seconds = divmod(remainder, 60)
                return f"{int(hours)}:{int(minutes):02d}:{seconds:06.3f}"
            minutes, seconds = divmod(float(value), 60)
            return f"{int(minutes)}:{seconds:06.3f}" if value >= 60 else f"{seconds:.3f}"

        payload = []
        for result in results:
            number = result.get("driver_number")
            detail = by_number.get(number, {})
            if not isinstance(number, int) or not detail:
                continue
            raw_position = result.get("position")
            position = int(raw_position) if str(raw_position).isdigit() else None
            tyre_stints = sorted(by_stint.get(number, []), key=lambda item: (item.get("lap_start") or 0, item.get("stint_number") or 0))
            payload.append({
                "number": number,
                "position": position,
                "code": detail.get("name_acronym") or str(number),
                "name": detail.get("full_name") or detail.get("broadcast_name") or str(number),
                "team": detail.get("team_name") or "—",
                "colour": f"#{str(detail.get('team_colour') or '888888').lstrip('#')}",
                "laps": result.get("number_of_laps") or 0,
                "time": time_label(result.get("duration")),
                "gap": result.get("gap_to_leader"),
                "status": "DSQ" if result.get("dsq") else "DNS" if result.get("dns") else "DNF" if result.get("dnf") else "CLASSIFIED",
                "stints": [{
                    "number": stint.get("stint_number"),
                    "compound": str(stint.get("compound") or "UNKNOWN").upper(),
                    "startLap": stint.get("lap_start"),
                    "endLap": stint.get("lap_end"),
                    "tyreAgeAtStart": stint.get("tyre_age_at_start") or 0,
                } for stint in tyre_stints],
            })
        payload.sort(key=lambda row: (row["position"] is None, row["position"] or 999))
        max_lap = max((stint.get("lap_end") or 0 for stint in stints), default=0)
        result = {"status": "published" if payload else "pending", "session": short_name, "drivers": payload, "maxLap": max_lap, "source": "OpenF1"}
        if payload:
            self._session_data_cache[key] = (time.monotonic() + 300, result)
        return result

    async def session_timing(self, event: EventDetail, short_name: str) -> dict[str, Any] | None:
        session = await self._matching_session(event, short_name)
        if session is None:
            return None
        cached = self._timing_cache.get(session["session_key"])
        if cached and cached[0] > time.monotonic():
            return cached[1]
        results = await self.session_data(event, short_name)
        if results is None:
            return None
        if results["status"] == "upcoming":
            return historical_snapshot(event.slug, session, results, [], [], [], [])
        # Keep optional feed failures separate so published results remain usable.
        async def optional(resource: str) -> list[dict[str, Any]]:
            try:
                return await self._get(resource, session_key=session["session_key"])
            except httpx.HTTPError:
                return []
        laps, control = await asyncio.gather(optional("laps"), optional("race_control"))
        radio, weather = await asyncio.gather(optional("team_radio"), optional("weather"))
        result = historical_snapshot(event.slug, session, results, laps, control, radio, weather)
        if results["drivers"]:
            self._timing_cache[session["session_key"]] = (time.monotonic() + 300, result)
        return result

    async def _matching_session(self, event: EventDetail, short_name: str) -> dict[str, Any] | None:
        meetings = await self.meetings(event.season)
        meeting = next((row for row in meetings if _slug(event.season, row["meeting_name"]) == event.slug), None)
        if meeting is None:
            return None
        return next((row for row in await self.sessions(meeting["meeting_key"]) if _session_short_name(row["session_name"]) == short_name), None)

    async def session_laps(self, event: EventDetail, short_name: str, driver_a: int, driver_b: int) -> dict[str, Any] | None:
        session = await self._matching_session(event, short_name)
        if session is None:
            return None
        started = _parse_datetime(session["date_start"]) <= datetime.now(timezone.utc)
        if not started:
            return {"status": "upcoming", "session": short_name, "drivers": [], "source": "OpenF1"}
        key = session["session_key"]
        cache_key = (key, min(driver_a, driver_b), max(driver_a, driver_b))
        cached = self._lap_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        first, second = await asyncio.gather(
            self._get("laps", session_key=key, driver_number=driver_a),
            self._get("laps", session_key=key, driver_number=driver_b),
        )
        def normalized(rows: list[dict[str, Any]], number: int) -> dict[str, Any]:
            laps = []
            for row in rows:
                lap_number = row.get("lap_number")
                if not isinstance(lap_number, int) or row.get("driver_number") != number:
                    continue
                duration = row.get("lap_duration")
                laps.append({
                    "lap": lap_number,
                    "duration": duration if isinstance(duration, (int, float)) else None,
                    "sectors": [row.get(f"duration_sector_{index}") if isinstance(row.get(f"duration_sector_{index}"), (int, float)) else None for index in (1, 2, 3)],
                    "pitOut": row.get("is_pit_out_lap") is True,
                })
            laps.sort(key=lambda row: row["lap"])
            return {"number": number, "laps": laps}

        result = {"status": "published" if first or second else "pending", "session": short_name, "drivers": [normalized(first, driver_a), normalized(second, driver_b)], "source": "OpenF1"}
        if first or second:
            self._lap_cache[cache_key] = (time.monotonic() + 300, result)
        return result

    async def _event_detail(self, meeting: dict[str, Any], round_number: int) -> EventDetail:
        session_rows = await self.sessions(meeting["meeting_key"])
        now = datetime.now(timezone.utc)
        session_payload = []
        for row in session_rows:
            start = _parse_datetime(row["date_start"])
            end = _parse_datetime(row["date_end"])
            status = "done" if end < now else "live" if start <= now <= end else "upcoming"
            session_payload.append(
                {
                    "name": row["session_name"],
                    "shortName": _session_short_name(row["session_name"]),
                    "startsAt": format_kst_datetime(start),
                    "status": status,
                }
            )

        is_demo_event = _slug(meeting["year"], meeting["meeting_name"]) == DEMO_EVENT["slug"]
        videos = DEMO_EVENT["videos"] if is_demo_event else [
            {
                "id": f"formula1-{meeting['meeting_key']}",
                "category": "공식 영상 모음",
                "title": f"{meeting['meeting_name']} 공식 인터뷰와 하이라이트",
                "source": "Formula 1",
                "duration": "공식 채널",
                "url": f"https://www.youtube.com/@Formula1/search?query={meeting['country_name']}%202026%20interview",
                "youtubeId": None,
                "participants": ["Formula 1 official channel"],
            }
        ]
        return EventDetail.model_validate(
            {
                "slug": _slug(meeting["year"], meeting["meeting_name"]),
                "season": meeting["year"],
                "round": round_number,
                "name": meeting["meeting_name"],
                "country": meeting["country_name"],
                "circuit": meeting["location"],
                "trackMapUrl": meeting.get("circuit_image"),
                "dateLabel": self._date_label(meeting["date_start"], meeting["date_end"]),
                "gmtOffset": meeting.get("gmt_offset"),
                **media_window(meeting["date_end"], meeting.get("gmt_offset", "+00:00:00")),
                "sessions": session_payload,
                "videos": videos,
                "tyreAllocation": DEMO_EVENT["tyreAllocation"] if is_demo_event else {"hard": "TBC", "medium": "TBC", "soft": "TBC"},
                "tyreSourceUrl": DEMO_EVENT.get("tyreSourceUrl") if is_demo_event else None,
                "summary": DEMO_EVENT["summary"] if is_demo_event else [
                    "공식 인터뷰 원문과 영상 메타데이터는 수집 후 한국어 검수 상태와 함께 표시됩니다.",
                    "세션 일정과 트랙맵은 OpenF1 공개 API에서 불러왔습니다.",
                ],
                "drivers": [],
            }
        )

    @staticmethod
    def _date_label(start_value: str, end_value: str) -> str:
        return format_kst_date_range(start_value, end_value)


@lru_cache
def get_openf1_service() -> OpenF1Service:
    return OpenF1Service()
