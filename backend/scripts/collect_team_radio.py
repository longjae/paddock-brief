"""Save published F1 radio clips as searchable English/Korean captions."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.live_timing import LiveTimingService, SESSION_PATH_RE, _items, team_radio_audio_url

BASE = "https://livetiming.formula1.com/static"
OPENF1 = "https://api.openf1.org/v1"
LOGGER = logging.getLogger(__name__)


def active_session_paths(index: dict[str, Any], now: datetime, meeting_filter: str = "") -> list[str]:
    paths: list[str] = []
    for meeting in index.get("Meetings", []):
        if meeting_filter and meeting_filter.lower() not in str(meeting.get("Name") or "").lower():
            continue
        for session in meeting.get("Sessions", []):
            path = str(session.get("Path") or "")
            start = str(session.get("StartDate") or "")
            if not SESSION_PATH_RE.fullmatch(path) or ".." in path or not start:
                continue
            try:
                local_start = datetime.fromisoformat(start)
            except ValueError:
                continue
            # The index uses venue-local time. A wide window covers every GP offset.
            if not meeting_filter and not (now.replace(tzinfo=None) - timedelta(days=4) <= local_start <= now.replace(tzinfo=None) + timedelta(days=1)):
                continue
            paths.append(path)
    return paths


def radio_captures(stream: str) -> list[dict[str, str]]:
    captures: dict[str, dict[str, str]] = {}
    for line in stream.lstrip("\ufeff").splitlines():
        try:
            payload = json.loads(line[12:])
        except (json.JSONDecodeError, IndexError):
            continue
        for item in _items(payload.get("Captures", {})):
            path = str(item.get("Path") or "")
            if path:
                captures[path] = {"path": path, "utc": str(item.get("Utc") or "")}
    return sorted(captures.values(), key=lambda item: item["utc"], reverse=True)


def openf1_radio_captures(sessions: list[dict[str, Any]], rows: list[dict[str, Any]], now: datetime, meeting_filter: str = "") -> list[tuple[str, dict[str, str]]]:
    recent = {
        session.get("session_key") for session in sessions
        if (meeting_filter.lower() in str(session.get("meeting_name") or session.get("country_name") or "").lower())
        and session.get("date_start")
        and (meeting_filter or now - timedelta(days=4) <= datetime.fromisoformat(session["date_start"]) <= now + timedelta(days=1))
    }
    captures = []
    prefix = f"{BASE}/"
    for row in rows:
        url = str(row.get("recording_url") or "")
        if row.get("session_key") not in recent or not url.startswith(prefix) or "TeamRadio/" not in url:
            continue
        session_path, filename = url[len(prefix):].rsplit("TeamRadio/", 1)
        path = f"TeamRadio/{filename}"
        try:
            team_radio_audio_url(path, session_path)
        except ValueError:
            continue
        captures.append((session_path, {"path": path, "utc": str(row.get("date") or "")}))
    return sorted(captures, key=lambda pair: pair[1]["utc"], reverse=True)


async def collect(meeting_filter: str, max_clips: int, dry_run: bool) -> int:
    settings = get_settings()
    if not dry_run and (not settings.openai_api_key or not settings.supabase_url or not settings.supabase_secret_key):
        raise RuntimeError("OPENAI_API_KEY and Supabase secret credentials are required")
    service = LiveTimingService(settings)
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        index_response = await client.get(f"{BASE}/{datetime.now(UTC).year}/Index.json")
        candidates: list[tuple[str, dict[str, str]]] = []
        if index_response.is_success:
            paths = active_session_paths(index_response.json(), datetime.now(UTC), meeting_filter)
            for session_path in paths:
                response = await client.get(f"{BASE}/{session_path}TeamRadio.jsonStream")
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                for capture in radio_captures(response.text):
                    try:
                        team_radio_audio_url(capture["path"], session_path)
                    except ValueError:
                        continue
                    candidates.append((session_path, capture))
        else:
            LOGGER.warning("F1 archive index returned %s; using OpenF1 radio list", index_response.status_code)
            sessions_response = await client.get(f"{OPENF1}/sessions", params={"year": datetime.now(UTC).year})
            sessions_response.raise_for_status()
            sessions = sessions_response.json()
            recent_keys = [
                session["session_key"] for session in sessions
                if session.get("date_start") and session.get("session_key")
                and (meeting_filter.lower() in str(session.get("meeting_name") or session.get("country_name") or "").lower())
                and (meeting_filter or datetime.now(UTC) - timedelta(days=4) <= datetime.fromisoformat(session["date_start"]) <= datetime.now(UTC) + timedelta(days=1))
            ]
            rows = []
            for key in recent_keys:
                response = await client.get(f"{OPENF1}/team_radio", params={"session_key": key})
                response.raise_for_status()
                rows.extend(response.json())
            candidates = openf1_radio_captures(sessions, rows, datetime.now(UTC), meeting_filter)
            paths = list({session_path for session_path, _ in candidates})
    candidates.sort(key=lambda pair: pair[1]["utc"], reverse=True)
    saved = 0
    existing_by_session: dict[str, set[str]] = {}
    for session_path, capture in candidates:
        if session_path not in existing_by_session:
            existing = await service.saved_team_radio_transcripts(session_path) if service.radio_store else []
            existing_by_session[session_path] = {str(item["path"]) for item in existing}
        path = capture["path"]
        if path in existing_by_session[session_path]:
            continue
        if dry_run:
            print(f"Would transcribe {session_path}{path}")
            saved += 1
        else:
            try:
                result = await service.transcribe_team_radio(path, session_path)
                if not result.get("transcript"):
                    continue
                existing_by_session[session_path].add(path)
                saved += 1
                print(f"Saved {session_path}{path}")
            except (httpx.HTTPError, ValueError) as error:
                LOGGER.warning("Skipped %s: %s", path, type(error).__name__)
        if saved >= max_clips:
            break
    print(f"Sessions: {len(paths)}; published clips: {len(candidates)}; processed: {saved}")
    return saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting", default="")
    parser.add_argument("--max-clips", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(collect(args.meeting, args.max_clips, args.dry_run))
