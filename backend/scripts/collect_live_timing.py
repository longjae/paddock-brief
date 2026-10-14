"""Capture public F1 timing during sessions without an open browser tab."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.live_snapshot_store import LiveSnapshotStore
from app.services.live_timing import LiveTimingService
from app.services.openf1 import _slug

LOGGER = logging.getLogger(__name__)
OPENF1_SESSIONS = "https://api.openf1.org/v1/sessions"


def active_session(rows: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    candidates = []
    for row in rows:
        if row.get("is_cancelled") or not row.get("date_start") or not row.get("meeting_name"):
            continue
        try:
            start = datetime.fromisoformat(str(row["date_start"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(row["date_end"]).replace("Z", "+00:00")) if row.get("date_end") else start + timedelta(hours=3)
        except ValueError:
            continue
        if start.tzinfo is None or end.tzinfo is None:
            continue
        if start - timedelta(minutes=10) <= now <= end + timedelta(hours=1):
            candidates.append((start, row))
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


async def collect(duration_seconds: int, dry_run: bool = False) -> int:
    settings = get_settings()
    if not dry_run and not (settings.supabase_url and settings.supabase_secret_key):
        raise RuntimeError("Supabase writer credentials are required")
    now = datetime.now(UTC)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(OPENF1_SESSIONS, params={"year": now.year})
        response.raise_for_status()
        session = active_session(response.json(), now)
    if not session:
        print("No active F1 session; collector idle")
        return 0

    meeting_name = str(session["meeting_name"])
    session_name = str(session.get("session_name") or "")
    event_slug = _slug(now.year, meeting_name)
    print(f"Collecting {meeting_name} / {session_name} for up to {duration_seconds}s")
    if dry_run:
        return 0

    service = LiveTimingService(settings.model_copy(update={"live_timing_enabled": True}))
    store = LiveSnapshotStore(settings)
    last_saved_update: str | None = None
    count = 0
    deadline = time.monotonic() + duration_seconds
    service.start()
    try:
        while time.monotonic() < deadline:
            snapshot = service.snapshot(event_slug)
            info = service.topics.get("SessionInfo", {})
            path = str(info.get("Path") or "")
            matches_session = str(info.get("Name") or "").casefold() == session_name.casefold()
            feed_meeting = str((info.get("Meeting") or {}).get("Name") or "")
            matches_meeting = feed_meeting.casefold() == meeting_name.casefold()
            update = str(snapshot.get("updatedAt") or "")
            if path and matches_session and matches_meeting and snapshot.get("drivers") and update and update != last_saved_update:
                try:
                    await store.save(event_slug, path, snapshot)
                    last_saved_update = update
                    count += 1
                except Exception:
                    LOGGER.warning("Live timing snapshot write failed for %s", event_slug, exc_info=True)
            await asyncio.sleep(min(15, max(0, deadline - time.monotonic())))
    finally:
        await service.stop()
    print(f"Saved {count} timing snapshots for {event_slug}")
    if not count:
        raise RuntimeError("Active session produced no saved timing snapshots")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=780)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.duration_seconds <= 840:
        parser.error("duration must be 1 to 840 seconds")
    asyncio.run(collect(args.duration_seconds, args.dry_run))
