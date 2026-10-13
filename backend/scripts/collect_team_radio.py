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


async def collect(meeting_filter: str, max_clips: int, dry_run: bool) -> int:
    settings = get_settings()
    if not dry_run and (not settings.openai_api_key or not settings.supabase_configured):
        raise RuntimeError("OPENAI_API_KEY and Supabase credentials are required")
    service = LiveTimingService(settings)
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        index_response = await client.get(f"{BASE}/{datetime.now(UTC).year}/Index.json")
        index_response.raise_for_status()
        paths = active_session_paths(index_response.json(), datetime.now(UTC), meeting_filter)
        candidates: list[tuple[str, dict[str, str]]] = []
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
                await asyncio.to_thread(
                    lambda: service.radio_store.table("team_radio_transcripts").upsert({
                        "session_path": session_path,
                        "path": path,
                        "transcript": result["transcript"],
                        "translation": result.get("translation"),
                    }).execute()
                )
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
    parser.add_argument("--max-clips", type=int, default=12)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(collect(args.meeting, args.max_clips, args.dry_run))
