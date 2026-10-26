"""Read the most recent independently collected live timing state."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from supabase import create_client

from app.core.config import Settings, get_settings


class LiveSnapshotStore:
    def __init__(self, settings: Settings) -> None:
        self.client = (
            create_client(settings.supabase_url, settings.supabase_key)
            if settings.supabase_configured and not settings.app_use_sample_data else None
        )
        self.writable = bool(self.client and settings.supabase_secret_key)

    async def save(self, event_slug: str, session_path: str, state: dict[str, Any]) -> None:
        if not self.client or not self.writable:
            raise RuntimeError("Live snapshot writer requires Supabase secret credentials")
        if not state.get("drivers") or not state.get("updatedAt"):
            raise ValueError("A populated live timing snapshot is required")
        await asyncio.to_thread(
            lambda: self.client.table("live_timing_latest").upsert({
                "event_slug": event_slug,
                "session_path": session_path,
                "captured_at": state["updatedAt"],
                "state": state,
            }, on_conflict="event_slug").execute()
        )

    async def latest(self, event_slug: str) -> dict[str, Any] | None:
        if not self.client:
            return None
        response = await asyncio.to_thread(
            lambda: self.client.table("live_timing_latest")
            .select("captured_at,state")
            .eq("event_slug", event_slug)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        row = response.data[0]
        state = row.get("state")
        if not isinstance(state, dict) or state.get("event") != event_slug or not state.get("drivers"):
            return None
        captured_at = datetime.fromisoformat(str(row["captured_at"]).replace("Z", "+00:00"))
        age = max(0, int((datetime.now(UTC) - captured_at).total_seconds()))
        return {
            **state,
            "connection": "offline",
            "isLive": False,
            "captureSource": "saved",
            "delaySeconds": age,
            "updatedAt": captured_at.isoformat(),
        }


@lru_cache
def get_live_snapshot_store() -> LiveSnapshotStore:
    return LiveSnapshotStore(get_settings())
