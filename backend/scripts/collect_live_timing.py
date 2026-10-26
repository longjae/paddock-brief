"""Capture public F1 timing during sessions without an open browser tab."""

from __future__ import annotations

import argparse
import asyncio
import logging
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.live_snapshot_store import LiveSnapshotStore
from app.services.live_timing import LiveTimingService, SESSION_PATH_RE
from app.services.openf1 import _slug

LOGGER = logging.getLogger(__name__)
OPENF1_SESSIONS = "https://api.openf1.org/v1/sessions"
PADDOCK_API = os.environ.get("PADDOCK_API_BASE_URL", "https://paddock-brief-api.vercel.app/api/v1").rstrip("/")


def relay_session_path(state: dict[str, Any], slug: str, now: datetime) -> str | None:
    if state.get("event") != slug or not state.get("isLive") or not state.get("drivers"):
        return None
    try:
        updated = datetime.fromisoformat(str(state.get("updatedAt") or "").replace("Z", "+00:00"))
        if updated.tzinfo is None or not 0 <= (now - updated).total_seconds() <= 30:
            return None
    except ValueError:
        return None
    path = str(state.get("session", {}).get("path") or "")
    return path if SESSION_PATH_RE.fullmatch(path) and ".." not in path else None


async def collect_relay(duration_seconds: int, dry_run: bool) -> int:
    """Persist the application's existing public F1 stream when runner WSS is blocked."""
    print("Runner F1 connection unavailable; collecting through Paddock Brief live stream")
    store = LiveSnapshotStore(get_settings())
    count = 0
    last_update = None
    last_saved = 0.0
    deadline = time.monotonic() + duration_seconds
    async with httpx.AsyncClient(timeout=35) as client:
        event_response = await client.get(f"{PADDOCK_API}/events/featured")
        event_response.raise_for_status()
        event = event_response.json()
        slug = str(event["slug"])
        windows = []
        now = datetime.now(UTC)
        for session in event.get("sessions", []):
            try:
                start = datetime.fromisoformat(str(session["startsAt"]).replace(" ", "T") + ":00+09:00")
            except (KeyError, ValueError):
                continue
            end = start + timedelta(hours=3 if session.get("shortName") == "R" else 1.5)
            if start - timedelta(minutes=10) <= now <= end + timedelta(minutes=10):
                windows.append((end + timedelta(minutes=10) - now).total_seconds())
        if not windows:
            print("No scheduled session for live relay; collector idle")
            return 0
        deadline = min(deadline, time.monotonic() + max(windows))
        while time.monotonic() < deadline:
            try:
                async with client.stream("GET", f"{PADDOCK_API}/events/{slug}/live-stream") as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if time.monotonic() >= deadline:
                            break
                        if not line.startswith("data: "):
                            continue
                        state = json.loads(line[6:])
                        path = relay_session_path(state, slug, datetime.now(UTC))
                        if not path:
                            continue
                        if dry_run:
                            print(f"Live relay verified: {slug} / {state['session']['name']} / {len(state['drivers'])} drivers")
                            return 0
                        if state["updatedAt"] != last_update and time.monotonic() - last_saved >= 15:
                            await store.save(slug, path, state)
                            last_update = state["updatedAt"]
                            last_saved = time.monotonic()
                            count += 1
            except (httpx.HTTPError, ValueError):
                LOGGER.warning("Live relay interrupted; reconnecting", exc_info=True)
            await asyncio.sleep(min(3, max(0, deadline - time.monotonic())))
    print(f"Saved {count} timing snapshots through live relay")
    if not count:
        raise RuntimeError("Live relay produced no fresh session snapshots")
    return count


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
        if start - timedelta(minutes=10) <= now <= end + timedelta(minutes=10):
            candidates.append((start, row))
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def collection_window(session: dict[str, Any], now: datetime, requested: int) -> int:
    """Keep one runner through the session, with a bounded post-session grace."""
    end = datetime.fromisoformat(str(session["date_end"]).replace("Z", "+00:00")) if session.get("date_end") else now + timedelta(hours=3)
    return max(1, min(requested, int((end + timedelta(minutes=10) - now).total_seconds())))


async def collect(duration_seconds: int, dry_run: bool = False) -> int:
    settings = get_settings()
    if not dry_run and not (settings.supabase_url and settings.supabase_secret_key):
        raise RuntimeError("Supabase writer credentials are required")
    now = datetime.now(UTC)
    service = LiveTimingService(settings.model_copy(update={"live_timing_enabled": True}))
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(OPENF1_SESSIONS, params={"year": now.year})
            response.raise_for_status()
            session = active_session(response.json(), now)
    except httpx.HTTPStatusError as error:
        if error.response.status_code not in {401, 403, 429}:
            raise
        print("OpenF1 live access restricted; identifying session from public F1 feed")
        service.start()
        for _ in range(15):
            if service.topics.get("SessionInfo"):
                break
            await asyncio.sleep(1)
        try:
            session = feed_active_session(service.topics.get("SessionInfo", {}), datetime.now(UTC))
        except Exception:
            await service.stop()
            raise
        if not service.topics.get("SessionInfo"):
            await service.stop()
            return await collect_relay(duration_seconds, dry_run)
    if not session:
        await service.stop()
        print("No active F1 session; collector idle")
        return 0

    duration_seconds = collection_window(session, datetime.now(UTC), duration_seconds)

    meeting_name = str(session["meeting_name"])
    session_name = str(session.get("session_name") or "")
    event_slug = _slug(now.year, meeting_name)
    print(f"Collecting {meeting_name} / {session_name} for up to {duration_seconds}s")
    if dry_run:
        await service.stop()
        return 0

    store = LiveSnapshotStore(settings)
    last_saved_update: str | None = None
    count = 0
    last_progress = time.monotonic()
    deadline = time.monotonic() + duration_seconds
    service.start()
    try:
        while time.monotonic() < deadline:
            snapshot = service.snapshot(event_slug)
            info = service.topics.get("SessionInfo", {})
            path = relay_session_path(snapshot, event_slug, datetime.now(UTC))
            matches_session = str(info.get("Name") or "").casefold() == session_name.casefold()
            feed_meeting = str((info.get("Meeting") or {}).get("Name") or "")
            matches_meeting = feed_meeting.casefold() == meeting_name.casefold()
            update = str(snapshot.get("updatedAt") or "")
            if path and matches_session and matches_meeting and snapshot.get("drivers") and update and update != last_saved_update:
                try:
                    await store.save(event_slug, path, snapshot)
                    last_saved_update = update
                    count += 1
                    last_progress = time.monotonic()
                except Exception:
                    LOGGER.warning("Live timing snapshot write failed for %s", event_slug, exc_info=True)
            if time.monotonic() - last_progress >= 45:
                # A connected socket can still produce no usable data on hosted runners.
                await service.stop()
                return count + await collect_relay(max(1, int(deadline - time.monotonic())), False)
            await asyncio.sleep(min(15, max(0, deadline - time.monotonic())))
    finally:
        await service.stop()
    print(f"Saved {count} timing snapshots for {event_slug}")
    if not count:
        raise RuntimeError("Active session produced no saved timing snapshots")
    return count


def feed_active_session(info: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    """Convert venue-local F1 session dates using its explicit GMT offset."""
    if not info.get("Meeting", {}).get("Name") or not info.get("Name") or not info.get("StartDate"):
        return None
    offset = str(info.get("GmtOffset") or "+00:00:00")
    sign = -1 if offset.startswith("-") else 1
    hours, minutes, seconds = [int(part) for part in offset.lstrip("+-").split(":")]
    zone = timezone(sign * timedelta(hours=hours, minutes=minutes, seconds=seconds))
    def utc_date(value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=zone)).astimezone(UTC).isoformat()
    candidate = {"meeting_name": info["Meeting"]["Name"], "session_name": info["Name"], "date_start": utc_date(info["StartDate"])}
    if info.get("EndDate"):
        candidate["date_end"] = utc_date(info["EndDate"])
    return active_session([candidate], now)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=780)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.duration_seconds <= 14400:
        parser.error("duration must be 1 to 14400 seconds")
    asyncio.run(collect(args.duration_seconds, args.dry_run))
