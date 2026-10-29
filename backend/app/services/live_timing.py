"""Small, defensive adapter for Formula 1's unofficial SignalR timing feed.

The upstream protocol is not public.  Keep raw topic handling isolated here so a
seasonal schema change degrades one panel instead of breaking the whole API.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import re
import zlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import httpx
import websockets
from supabase import create_client

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
    "Position.z",
    "CarData.z",
]
TEAM_RADIO_PATH_RE = re.compile(r"^TeamRadio/[A-Za-z0-9_-]+\.mp3$")
SESSION_PATH_RE = re.compile(r"^[A-Za-z0-9_/-]+/$")


def radio_speaker_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    segments = []
    for item in payload.get("segments", []):
        if not isinstance(item, dict) or not str(item.get("text") or "").strip():
            continue
        try:
            start, end = float(item["start"]), float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end):
            continue
        speaker = str(item.get("speaker") or "").strip()
        segments.append({"start": start, "end": end, "speaker": speaker if re.fullmatch(r"[A-Z]", speaker) else None, "text": str(item["text"]).strip()})
    return segments


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


def _mini_sectors(sectors: Any) -> list[list[str]]:
    """Keep only the public timing colours; unknown codes remain unavailable."""
    colours = {2048: "yellow", 2049: "green", 2051: "purple", 2064: "pit"}
    result: list[list[str]] = []
    for sector in _items(sectors)[:3]:
        segments = _items(sector.get("Segments", {}))
        result.append([
            colours.get(int(segment.get("Status") or 0), "unknown")
            if str(segment.get("Status") or 0).isdigit() else "unknown"
            for segment in segments
        ])
    return result


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


def _compressed_topic(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str):
        return {}
    try:
        decoded = zlib.decompress(base64.b64decode(payload.strip('"'), validate=True), -zlib.MAX_WBITS)
        value = json.loads(decoded)
        return value if isinstance(value, dict) else {}
    except (ValueError, zlib.error, json.JSONDecodeError):
        return {}


class LiveTimingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connection = "offline"
        self.last_error: str | None = None
        self.updated_at: str | None = None
        self.topics: dict[str, Any] = {}
        self.radio_transcripts: dict[str, str] = {}
        self.radio_translations: dict[str, str] = {}
        self.radio_proxy_preferred = False
        self.radio_store = create_client(settings.supabase_url, settings.supabase_key) if settings.supabase_configured and not settings.app_use_sample_data else None
        self.race_control_history: dict[str, dict[str, Any]] = {}
        self._session_path: str | None = None
        self.track_positions: dict[str, dict[str, Any]] = {}
        self.track_car_data: dict[str, dict[str, Any]] = {}
        self.track_trace: list[dict[str, float]] = []
        self._trace_driver: str | None = None
        self.track_updated_at: str | None = None
        self._task: asyncio.Task[None] | None = None

    def _capture_track(self, topic: str, payload: Any) -> None:
        data = _compressed_topic(payload)
        if topic == "Position.z":
            for sample in data.get("Position", []):
                if not isinstance(sample, dict):
                    continue
                timestamp = str(sample.get("Timestamp") or "")
                for number, point in (sample.get("Entries") or {}).items():
                    if not isinstance(point, dict):
                        continue
                    try:
                        x, y = float(point["X"]), float(point["Y"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if not math.isfinite(x) or not math.isfinite(y):
                        continue
                    self.track_positions[str(number)] = {"number": str(number), "x": x, "y": y, "sampledAt": timestamp}
                    if self._trace_driver is None and str(point.get("Status") or "OnTrack") in ("OnTrack", "0"):
                        self._trace_driver = str(number)
                    if str(number) == self._trace_driver:
                        self.track_trace.append({"x": x, "y": y})
                        self.track_trace = self.track_trace[-500:]
                if timestamp:
                    self.track_updated_at = timestamp
        elif topic == "CarData.z":
            for sample in data.get("Entries", []):
                if not isinstance(sample, dict):
                    continue
                timestamp = str(sample.get("Utc") or "")
                for number, car in (sample.get("Cars") or {}).items():
                    channels = car.get("Channels") if isinstance(car, dict) else None
                    if not isinstance(channels, dict):
                        continue
                    try:
                        self.track_car_data[str(number)] = {
                            "speed": int(channels["2"]), "rpm": int(channels["0"]),
                            "gear": int(channels["3"]), "throttle": int(channels["4"]),
                            "brake": int(channels["5"]), "sampledAt": timestamp,
                        }
                    except (KeyError, TypeError, ValueError):
                        continue

    def _capture_race_control(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        messages = payload.get("Messages", payload)
        for item in _items(messages):
            key = "|".join(
                str(item.get(field) or "")
                for field in ("Utc", "Message", "Category", "Flag", "RacingNumber")
            )
            if key.strip("|"):
                self.race_control_history[key] = deepcopy(item)
        while len(self.race_control_history) > 200:
            self.race_control_history.pop(next(iter(self.race_control_history)))

    def _track_session(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        path = str(payload.get("Path") or "")
        if path and self._session_path and path != self._session_path:
            self.race_control_history.clear()
            self.radio_transcripts.clear()
            self.radio_translations.clear()
            self.track_positions.clear()
            self.track_car_data.clear()
            self.track_trace.clear()
            self._trace_driver = None
            self.track_updated_at = None
        if path:
            self._session_path = path

    async def transcribe_team_radio(self, path: str, session_path: str, force: bool = False) -> dict[str, Any]:
        audio_url = team_radio_audio_url(path, session_path)
        if self.radio_store is not None and not force:
            try:
                stored = await asyncio.to_thread(
                    lambda: self.radio_store.table("team_radio_transcripts")
                    .select("transcript,translation,status,segments")
                    .eq("session_path", session_path)
                    .eq("path", path)
                    .limit(1)
                    .execute()
                )
                if stored.data:
                    row = stored.data[0]
                    if row.get("transcript") and not row.get("translation") and self.settings.openai_api_key and self.settings.supabase_secret_key:
                        try:
                            translation = await self.translate_team_radio(row["transcript"])
                            await asyncio.to_thread(lambda: self.radio_store.table("team_radio_transcripts").update({"translation": translation}).eq("session_path", session_path).eq("path", path).execute())
                            row = {**row, "translation": translation}
                        except Exception:
                            # Preserve the saved English and speaker segments; never re-transcribe.
                            LOGGER.warning("Saved radio translation retry failed for %s", path)
                    return {"audioUrl": audio_url, "transcript": row["transcript"] or None, "translation": row.get("translation"), "language": "en" if row["transcript"] else None, "status": row.get("status", "ready"), "segments": row.get("segments") or []}
            except Exception:
                LOGGER.warning("Stored team radio transcript unavailable for %s", path, exc_info=True)
        if path in self.radio_transcripts and not force:
            return {
                "audioUrl": audio_url,
                "transcript": self.radio_transcripts[path],
                "translation": self.radio_translations.get(path),
                "language": "en",
            }
        if not self.settings.openai_api_key:
            return {"audioUrl": audio_url, "transcript": None, "language": None}
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            proxy_url = self.settings.team_radio_audio_proxy_url
            proxy_params = {"sessionPath": session_path, "path": path}
            if self.radio_proxy_preferred and proxy_url:
                audio_response = await client.get(proxy_url, params=proxy_params)
            else:
                audio_response = await client.get(audio_url, headers={"User-Agent": self.settings.collector_user_agent})
                if audio_response.status_code == 403 and proxy_url:
                    self.radio_proxy_preferred = True
                    audio_response = await client.get(proxy_url, params=proxy_params)
            audio_response.raise_for_status()
            transcript_response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                data={"model": "gpt-4o-transcribe-diarize", "response_format": "diarized_json", "chunking_strategy": "auto"},
                files={"file": (path.rsplit("/", 1)[-1], audio_response.content, "audio/mpeg")},
            )
            transcript_response.raise_for_status()
        payload = transcript_response.json()
        transcript = str(payload.get("text") or "").strip()
        segments = radio_speaker_segments(payload)
        translation: str | None = None
        if transcript:
            self.radio_transcripts[path] = transcript
            try:
                translation = await self.translate_team_radio(transcript)
                self.radio_translations[path] = translation
            except (httpx.HTTPError, ValueError):
                LOGGER.warning("Team radio translation failed for %s", path)
        if self.radio_store is not None and self.settings.supabase_secret_key:
            await asyncio.to_thread(
                lambda: self.radio_store.table("team_radio_transcripts").upsert({
                    "session_path": session_path,
                    "path": path,
                    "transcript": transcript,
                    "translation": translation,
                    "status": "ready" if transcript else "unavailable",
                    "segments": segments,
                }, on_conflict="session_path,path").execute()
            )
        return {
            "audioUrl": audio_url,
            "transcript": transcript or None,
            "translation": translation,
            "language": "en" if transcript else None,
            "status": "ready" if transcript else "unavailable",
            "segments": segments,
        }

    async def translate_team_radio(self, transcript: str) -> str:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={"model": self.settings.openai_summary_model, "input": (
                    "다음 Formula 1 팀 라디오를 자연스럽고 간결한 한국어로 번역하세요. "
                    "고유명사와 F1 용어를 유지하고 번역문만 출력하세요.\n\n" + transcript
                )},
            )
            response.raise_for_status()
        payload = response.json()
        text = payload.get("output_text") or next((
            item.get("text") for output in payload.get("output", [])
            for item in output.get("content", []) if item.get("type") == "output_text"
        ), None)
        if not str(text or "").strip():
            raise ValueError("Empty radio translation")
        return str(text).strip()

    async def saved_team_radio_transcripts(self, session_path: str) -> list[dict[str, Any]]:
        if not SESSION_PATH_RE.fullmatch(session_path) or ".." in session_path:
            raise ValueError("Invalid team radio session path")
        if self.radio_store is None:
            return []
        result = await asyncio.to_thread(
            lambda: self.radio_store.table("team_radio_transcripts")
            .select("path,transcript,translation,status,segments")
            .eq("session_path", session_path)
            .execute()
        )
        return result.data or []

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
                        if topic in ("Position.z", "CarData.z"):
                            self._capture_track(topic, result[topic])
                            continue
                        self.topics[topic] = _deep_merge(self.topics.get(topic, {}), result[topic])
                        if topic == "SessionInfo":
                            self._track_session(result[topic])
                        elif topic == "RaceControlMessages":
                            self._capture_race_control(result[topic])
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
        if topic in ("Position.z", "CarData.z"):
            self._capture_track(topic, payload)
            self.updated_at = datetime.now(UTC).isoformat()
            self.connection = "live"
            return
        if topic == "SessionInfo":
            self._track_session(payload)
        elif topic == "RaceControlMessages":
            self._capture_race_control(payload)
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
                    "currentSectors": [(sector.get("Value") or "—") for sector in timing_sectors[:3]],
                    "sectorFlags": [
                        {"personalFastest": _flag(sector.get("PersonalFastest")), "overallFastest": _flag(sector.get("OverallFastest"))}
                        for sector in timing_sectors[:3]
                    ],
                    "miniSectors": _mini_sectors(line.get("Sectors", {})),
                    "compound": compound,
                    "tyreAge": int(stint.get("TotalLaps") or 0),
                    "tyreNew": _flag(current.get("New", stint.get("New"))),
                    "stint": len(stints),
                    "pitStops": int(line["NumberOfPitStops"]) if str(line.get("NumberOfPitStops", "")).isdigit() else None,
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
            return {
                "event": event_slug,
                "connection": "offline",
                "isLive": False,
                "updatedAt": None,
                "delaySeconds": None,
                "session": {"name": "세션 대기 중", "meeting": None, "remaining": "—", "lap": 0, "totalLaps": 0},
                "trackStatus": {"code": "", "message": "정보 없음"},
                "weather": {},
                "fastestLap": None,
                "fastestSectors": [],
                "tyreInventory": {"available": False, "message": "세션 시작 후 타이어 정보가 표시됩니다."},
                "drivers": [],
                "raceControl": [],
                "teamRadio": [],
                "track": None,
                "lastError": None,
            }
        race_control = self.topics.get("RaceControlMessages", {}).get("Messages", {})
        self._capture_race_control({"Messages": race_control})
        radio = self.topics.get("TeamRadio", {}).get("Captures", {})
        lap_count = self.topics.get("LapCount", {})
        track = self.topics.get("TrackStatus", {})
        clock = self.topics.get("ExtrapolatedClock", {})
        session_path = str(session_info.get("Path") or "")
        radio_items = _items(radio)[-150:][::-1]
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
            "captureSource": "live",
            "updatedAt": self.updated_at,
            "delaySeconds": None,
            "session": {
                "name": session_info.get("Name") or "세션 대기 중",
                "path": session_info.get("Path") or "",
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
            "raceControl": list(self.race_control_history.values())[-50:][::-1],
            "teamRadio": radio_items,
            "track": {
                "sampledAt": self.track_updated_at,
                "positions": list(self.track_positions.values()),
                "cars": self.track_car_data,
                "trace": self.track_trace,
            } if self.track_updated_at else None,
            "lastError": self.last_error,
        }


_service: LiveTimingService | None = None


def get_live_timing_service(settings: Settings | None = None) -> LiveTimingService:
    global _service
    if _service is None:
        from app.core.config import get_settings

        _service = LiveTimingService(settings or get_settings())
    return _service
