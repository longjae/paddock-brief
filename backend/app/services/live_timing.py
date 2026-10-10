"""Small, defensive adapter for Formula 1's unofficial SignalR timing feed.

The upstream protocol is not public.  Keep raw topic handling isolated here so a
seasonal schema change degrades one panel instead of breaking the whole API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import websockets

from app.core.config import Settings

LOGGER = logging.getLogger(__name__)
RECORD_SEPARATOR = "\x1e"
PUBLIC_TOPICS = [
    "DriverList",
    "SessionInfo",
    "SessionData",
    "TimingData",
    "TimingAppData",
    "TrackStatus",
    "WeatherData",
    "RaceControlMessages",
    "TeamRadio",
    "LapCount",
    "ExtrapolatedClock",
]


def _deep_merge(current: Any, update: Any) -> Any:
    if not isinstance(current, dict) or not isinstance(update, dict):
        return deepcopy(update)
    merged = deepcopy(current)
    for key, value in update.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    return []


class LiveTimingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connection = "offline"
        self.last_error: str | None = None
        self.updated_at: str | None = None
        self.topics: dict[str, Any] = {}
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self.settings.live_timing_enabled and self._task is None:
            self._task = asyncio.create_task(self._run(), name="f1-live-timing")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        attempt = 0
        while True:
            try:
                self.connection = "connecting" if attempt == 0 else "reconnecting"
                headers = {"User-Agent": self.settings.collector_user_agent}
                if self.settings.f1_live_token:
                    headers["Authorization"] = f"Bearer {self.settings.f1_live_token}"
                async with websockets.connect(
                    self.settings.live_timing_url,
                    additional_headers=headers,
                    origin="https://www.formula1.com",
                    open_timeout=15,
                    ping_interval=20,
                    ping_timeout=20,
                ) as socket:
                    await socket.send(json.dumps({"protocol": "json", "version": 1}) + RECORD_SEPARATOR)
                    await socket.send(
                        json.dumps(
                            {"type": 1, "invocationId": "1", "target": "Subscribe", "arguments": [PUBLIC_TOPICS]}
                        )
                        + RECORD_SEPARATOR
                    )
                    self.connection = "live"
                    self.last_error = None
                    attempt = 0
                    async for payload in socket:
                        for frame in str(payload).split(RECORD_SEPARATOR):
                            if frame:
                                self.consume_signalr(json.loads(frame))
            except asyncio.CancelledError:
                raise
            except Exception as error:  # upstream is unofficial; reconnect without taking down the API
                attempt += 1
                self.connection = "reconnecting"
                self.last_error = type(error).__name__
                LOGGER.warning("F1 live timing disconnected (%s)", type(error).__name__)
                await asyncio.sleep(min(30, 2 ** min(attempt, 5)))

    def consume_signalr(self, message: dict[str, Any]) -> None:
        if message.get("type") == 3:
            result = message.get("result")
            if isinstance(result, dict):
                for topic in PUBLIC_TOPICS:
                    if topic in result:
                        self.topics[topic] = _deep_merge(self.topics.get(topic, {}), result[topic])
                self.updated_at = datetime.now(UTC).isoformat()
                self.connection = "live"
            return
        if message.get("type") != 1 or str(message.get("target", "")).lower() != "feed":
            return
        arguments = message.get("arguments") or []
        if len(arguments) < 2:
            return
        topic, payload = arguments[0], arguments[1]
        if topic not in PUBLIC_TOPICS:
            return
        self.topics[topic] = _deep_merge(self.topics.get(topic, {}), payload)
        self.updated_at = datetime.now(UTC).isoformat()
        self.connection = "live"

    def snapshot(self, event_slug: str) -> dict[str, Any]:
        timing = self.topics.get("TimingData", {}).get("Lines", {})
        app = self.topics.get("TimingAppData", {}).get("Lines", {})
        drivers = self.topics.get("DriverList", {})
        rows: list[dict[str, Any]] = []
        for number, line in timing.items() if isinstance(timing, dict) else []:
            if not isinstance(line, dict):
                continue
            identity = drivers.get(str(number), {}) if isinstance(drivers, dict) else {}
            stint_source = app.get(str(number), {}) if isinstance(app, dict) else {}
            stints = _items(stint_source.get("Stints", {}))
            stint = stints[-1] if stints else {}
            sectors = _items(line.get("Sectors", {}))
            rows.append(
                {
                    "position": int(line.get("Position") or 99),
                    "number": str(number),
                    "code": identity.get("Tla") or identity.get("RacingNumber") or str(number),
                    "name": identity.get("FullName") or identity.get("BroadcastName") or str(number),
                    "team": identity.get("TeamName") or "",
                    "colour": f"#{identity.get('TeamColour', '777777')}",
                    "gap": line.get("GapToLeader") or ("LEADER" if str(line.get("Position")) == "1" else "—"),
                    "interval": (line.get("IntervalToPositionAhead") or {}).get("Value", "—"),
                    "lastLap": (line.get("LastLapTime") or {}).get("Value", "—"),
                    "bestLap": (line.get("BestLapTime") or {}).get("Value", "—"),
                    "sectors": [(sector.get("Value") or "—") for sector in sectors[:3]],
                    "compound": str(stint.get("Compound") or "UNKNOWN").upper(),
                    "tyreAge": int(stint.get("TotalLaps") or 0),
                    "inPit": bool(line.get("InPit") or line.get("PitOut")),
                    "retired": bool(line.get("Retired") or line.get("Stopped")),
                }
            )
        rows.sort(key=lambda row: row["position"])

        session_info = self.topics.get("SessionInfo", {})
        meeting_name = str((session_info.get("Meeting") or {}).get("Name") or "")
        requested_name = event_slug.split("-", 1)[-1].replace("-", " ")
        normalized_meeting = re.sub(r"[^a-z0-9 ]", "", meeting_name.lower())
        event_matches = not meeting_name or all(word in normalized_meeting for word in requested_name.split())
        if not event_matches:
            rows = []
        race_control = self.topics.get("RaceControlMessages", {}).get("Messages", {})
        radio = self.topics.get("TeamRadio", {}).get("Captures", {})
        lap_count = self.topics.get("LapCount", {})
        track = self.topics.get("TrackStatus", {})
        clock = self.topics.get("ExtrapolatedClock", {})
        return {
            "event": event_slug,
            "connection": self.connection if self.settings.live_timing_enabled else "disabled",
            "isLive": self.connection == "live" and bool(rows),
            "updatedAt": self.updated_at,
            "delaySeconds": None,
            "session": {
                "name": session_info.get("Name") or "세션 대기 중",
                "meeting": meeting_name or None,
                "remaining": clock.get("Remaining") or "—",
                "lap": int(lap_count.get("CurrentLap") or 0),
                "totalLaps": int(lap_count.get("TotalLaps") or 0),
            },
            "trackStatus": {"code": str(track.get("Status") or ""), "message": track.get("Message") or "정보 없음"},
            "weather": self.topics.get("WeatherData", {}),
            "drivers": rows,
            "raceControl": _items(race_control)[-20:][::-1],
            "teamRadio": _items(radio)[-12:][::-1],
            "lastError": self.last_error,
        }


_service: LiveTimingService | None = None


def get_live_timing_service(settings: Settings | None = None) -> LiveTimingService:
    global _service
    if _service is None:
        from app.core.config import get_settings

        _service = LiveTimingService(settings or get_settings())
    return _service
