import asyncio
from datetime import UTC, datetime, timedelta

from app.services.live_snapshot_store import LiveSnapshotStore
from scripts.collect_live_timing import active_session


def test_active_session_uses_real_session_window_and_ignores_old_races() -> None:
    now = datetime(2026, 10, 24, 18, tzinfo=UTC)
    rows = [
        {"meeting_name": "Singapore Grand Prix", "session_name": "Race", "date_start": "2026-10-11T11:00:00Z", "date_end": "2026-10-11T13:00:00Z"},
        {"meeting_name": "United States Grand Prix", "session_name": "Sprint", "date_start": "2026-10-24T17:00:00Z", "date_end": "2026-10-24T18:30:00Z"},
    ]
    assert active_session(rows, now) == rows[1]
    assert active_session(rows, now + timedelta(days=3)) is None


def test_saved_live_snapshot_returns_last_record_as_offline() -> None:
    class Query:
        def table(self, name):
            assert name == "live_timing_latest"
            return self

        def select(self, columns):
            return self

        def eq(self, name, value):
            assert (name, value) == ("event_slug", "2026-united-states")
            return self

        def limit(self, count):
            return self

        def execute(self):
            return type("Result", (), {"data": [{
                "captured_at": (datetime.now(UTC) - timedelta(seconds=60)).isoformat(),
                "state": {"event": "2026-united-states", "connection": "live", "isLive": True, "drivers": [{"code": "VER"}]},
            }]})()

    store = LiveSnapshotStore.__new__(LiveSnapshotStore)
    store.client = Query()
    result = asyncio.run(store.latest("2026-united-states"))
    assert result is not None
    assert result["drivers"][0]["code"] == "VER"
    assert result["connection"] == "offline"
    assert result["isLive"] is False
    assert result["delaySeconds"] > 0
