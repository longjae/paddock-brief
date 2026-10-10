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

import httpx
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
    "TimingStats",
    "CurrentTyres",
    "TyreStintSeries",
    "TrackStatus",
    "WeatherData",
    "RaceControlMessages",
    "TeamRadio",
    "LapCount",
    "ExtrapolatedClock",
]
TEAM_RADIO_PATH_RE = re.compile(r"^TeamRadio/[A-Za-z0-9_-]+\.mp3$")
SESSION_PATH_RE = re.compile(r"^[A-Za-z0-9_/-]+/$")


def team_radio_audio_url(path: str, session_path: str) -> str:
    if not TEAM_RADIO_PATH_RE.fullmatch(path) or not SESSION_PATH_RE.fullmatch(session_path) or ".." in session_path:
        raise ValueError("Invalid team radio path")
    return f"https://livetiming.formula1.com/static/{session_path}{path}"


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


def _seconds(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == "—":
        return None
    try:
        parts = [float(part) for part in text.split(":")]
    except ValueError:
        return None
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[-3] * 3600 + parts[-2] * 60 + parts[-1]


def _flag(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


class LiveTimingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connection = "offline"
        self.last_error: str | None = None
        self.updated_at: str | None = None
        self.topics: dict[str, Any] = {}
        self.radio_transcripts: dict[str, str] = {}
        self._task: asyncio.Task[None] | None = None

    async def transcribe_team_radio(self, path: str, session_path: str) -> dict[str, str | None]:
        audio_url = team_radio_audio_url(path, session_path)
        if path in self.radio_transcripts:
            return {"audioUrl": audio_url, "transcript": self.radio_transcripts[path], "language": "en"}
        if not self.settings.openai_api_key:
            return {"audioUrl": audio_url, "transcript": None, "language": None}
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            audio_response = await client.get(audio_url, headers={"User-Agent": self.settings.collector_user_agent})
            audio_response.raise_for_status()
            transcript_response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                data={"model": "gpt-4o-mini-transcribe", "response_format": "json"},
                files={"file": (path.rsplit("/", 1)[-1], audio_response.content, "audio/mpeg")},
            )
            transcript_response.raise_for_status()
        transcript = str(transcript_response.json().get("text") or "").strip()
        if transcript:
            self.radio_transcripts[path] = transcript
        return {"audioUrl": audio_url, "transcript": transcript or None, "language": "en" if transcript else None}

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
        stats = self.topics.get("TimingStats", {}).get("Lines", {})
        current_topic = self.topics.get("CurrentTyres", {})
        current_tyres = current_topic.get("Tyres") or current_topic.get("Lines") or current_topic
        series_topic = self.topics.get("TyreStintSeries", {})
        tyre_series = series_topic.get("Stints") or series_topic.get("Lines") or {}
        drivers = self.topics.get("DriverList", {})
        rows: list[dict[str, Any]] = []
        for number, line in timing.items() if isinstance(timing, dict) else []:
            if not isinstance(line, dict):
                continue
            identity = drivers.get(str(number), {}) if isinstance(drivers, dict) else {}
            stint_source = app.get(str(number), {}) if isinstance(app, dict) else {}
            series_source = tyre_series.get(str(number), {}) if isinstance(tyre_series, dict) else {}
            stints = _items(series_source) or _items(stint_source.get("Stints", {}))
            stint = stints[-1] if stints else {}
            current = current_tyres.get(str(number), {}) if isinstance(current_tyres, dict) else {}
            if isinstance(current, str):
                current = {"Compound": current}
            stat_line = stats.get(str(number), {}) if isinstance(stats, dict) else {}
            timing_sectors = _items(line.get("Sectors", {}))
            best_sectors = _items(stat_line.get("BestSectors", {}))
            sectors = best_sectors or timing_sectors
            compound = str(current.get("Compound") or stint.get("Compound") or "UNKNOWN").upper()
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
                    "sectorFlags": [
                        {"personalFastest": _flag(sector.get("PersonalFastest")), "overallFastest": _flag(sector.get("OverallFastest"))}
                        for sector in timing_sectors[:3]
                    ],
                    "compound": compound,
                    "tyreAge": int(stint.get("TotalLaps") or 0),
                    "tyreNew": _flag(current.get("New", stint.get("New"))),
                    "stint": len(stints),
                    "tyreHistory": [
                        {
                            "compound": str(item.get("Compound") or "UNKNOWN").upper(),
                            "laps": int(item.get("TotalLaps") or 0),
                            "new": _flag(item.get("New")),
                        }
                        for item in stints
                    ],
                    "inPit": bool(line.get("InPit") or line.get("PitOut")),
                    "retired": bool(line.get("Retired") or line.get("Stopped")),
                }
            )
        rows.sort(key=lambda row: row["position"])
        lap_candidates = [row for row in rows if _seconds(row["bestLap"]) is not None]
        fastest_lap = min(lap_candidates, key=lambda row: _seconds(row["bestLap"]) or 999999) if lap_candidates else None
        fastest_sectors: list[dict[str, Any]] = []
        for index in range(3):
            candidates = [row for row in rows if index < len(row["sectors"]) and _seconds(row["sectors"][index]) is not None]
            leader = min(candidates, key=lambda row: _seconds(row["sectors"][index]) or 999999) if candidates else None
            fastest_sectors.append(
                {"sector": index + 1, "driver": leader["code"] if leader else "—", "time": leader["sectors"][index] if leader else "—"}
            )

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
        session_path = str(session_info.get("Path") or "")
        radio_items = _items(radio)[-12:][::-1]
        for item in radio_items:
            path = str(item.get("Path") or "")
            try:
                item["AudioUrl"] = team_radio_audio_url(path, session_path)
                item["SessionPath"] = session_path
            except ValueError:
                pass
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
            "fastestLap": {"driver": fastest_lap["code"], "time": fastest_lap["bestLap"]} if fastest_lap else None,
            "fastestSectors": fastest_sectors,
            "tyreInventory": {
                "available": False,
                "message": "공식 라이브 피드는 각 드라이버의 전체 잔여 타이어 세트 수를 제공하지 않습니다.",
            },
            "drivers": rows,
            "raceControl": _items(race_control)[-20:][::-1],
            "teamRadio": radio_items,
            "lastError": self.last_error,
        }


_service: LiveTimingService | None = None


def get_live_timing_service(settings: Settings | None = None) -> LiveTimingService:
    global _service
    if _service is None:
        from app.core.config import get_settings

        _service = LiveTimingService(settings or get_settings())
    return _service
