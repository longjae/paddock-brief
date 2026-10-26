import asyncio
from datetime import UTC, datetime, timedelta

from app.services.live_snapshot_store import LiveSnapshotStore
from scripts.collect_live_timing import active_session
from scripts.collect_live_timing import feed_active_session
from scripts.collect_live_timing import relay_session_path
from scripts.collect_live_timing import collection_window


def test_collection_covers_session_end_without_waiting_for_next_cron() -> None:
    now = datetime(2026, 10, 24, 17, 45, tzinfo=UTC)
    session = {"date_end": "2026-10-24T18:30:00Z"}
    assert collection_window(session, now, 14400) == 55 * 60
    assert collection_window(session, now, 60) == 60
    assert collection_window(session, now + timedelta(hours=2), 14400) == 1


def test_silent_direct_connection_switches_to_relay(monkeypatch) -> None:
    import httpx
    from unittest.mock import AsyncMock, Mock
    from scripts import collect_live_timing as module
    from app.core.config import Settings
    now = datetime.now(UTC)
    clock = [100.0]
    service = Mock()
    service.topics = {}
    service.snapshot.return_value = {"event": "2026-united-states", "drivers": [], "isLive": False}
    service.stop = AsyncMock()
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[{
        "meeting_name": "United States Grand Prix", "session_name": "Race", "date_start": (now - timedelta(minutes=10)).isoformat(), "date_end": (now + timedelta(hours=1)).isoformat(),
    }])))
    async def sleep(seconds):
        clock[0] += seconds
    relay = AsyncMock(return_value=2)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(app_use_sample_data=True, supabase_url="https://example.com", supabase_secret_key="test"))
    monkeypatch.setattr(module, "LiveTimingService", lambda settings: service)
    monkeypatch.setattr(module, "LiveSnapshotStore", lambda settings: Mock())
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: client)
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    monkeypatch.setattr(module, "collect_relay", relay)
    assert asyncio.run(module.collect(120)) == 2
    relay.assert_awaited_once_with(75, False)


def test_relay_recovers_from_disconnect_and_saves_fresh_data(monkeypatch) -> None:
    import httpx
    from unittest.mock import AsyncMock
    from scripts import collect_live_timing as module
    from datetime import timezone
    clock = [100.0]
    now = datetime.now(UTC)
    state = {"event": "2026-united-states", "isLive": True, "updatedAt": now.isoformat(), "drivers": [{"number": "12"}], "session": {"name": "Race", "path": "2026/US/Race/"}}
    streams = []
    def respond(request):
        if request.url.path.endswith("/featured"):
            return httpx.Response(200, json={"slug": "2026-united-states", "sessions": [{"shortName": "R", "startsAt": now.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")}]})
        streams.append(request)
        if len(streams) == 1:
            return httpx.Response(503)
        import json
        return httpx.Response(200, text="data: " + json.dumps(state) + "\n\n")
    async def sleep(seconds):
        clock[0] += seconds
    async def save(*args):
        clock[0] += 20
    store = type("Store", (), {"save": AsyncMock(side_effect=save)})()
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setattr(module, "LiveSnapshotStore", lambda settings: store)
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    assert asyncio.run(module.collect_relay(10, False)) == 1
    assert len(streams) == 2
    store.save.assert_awaited_once()


def test_relay_rejects_stale_other_gp_and_invalid_session_paths() -> None:
    now = datetime.now(UTC)
    state = {"event": "2026-united-states", "isLive": True, "updatedAt": now.isoformat(), "drivers": [{"number": "63"}], "session": {"path": "2026/United_States/Practice_3/"}}
    assert relay_session_path(state, "2026-united-states", now) == "2026/United_States/Practice_3/"
    assert relay_session_path(state, "2026-singapore", now) is None
    assert relay_session_path({**state, "updatedAt": (now - timedelta(minutes=5)).isoformat()}, "2026-united-states", now) is None
    assert relay_session_path({**state, "session": {"path": "../../other/"}}, "2026-united-states", now) is None


def test_public_feed_identifies_fp3_with_austin_timezone() -> None:
    info = {"Meeting": {"Name": "United States Grand Prix"}, "Name": "Practice 3", "StartDate": "2026-10-24T12:30:00", "EndDate": "2026-10-24T13:30:00", "GmtOffset": "-05:00:00"}
    result = feed_active_session(info, datetime(2026, 10, 24, 17, 45, tzinfo=UTC))
    assert result["session_name"] == "Practice 3"
    assert result["date_start"] == "2026-10-24T17:30:00+00:00"
    assert feed_active_session(info, datetime(2026, 10, 25, tzinfo=UTC)) is None


def test_calendar_401_can_identify_session_from_feed_without_openf1(monkeypatch) -> None:
    import httpx
    from unittest.mock import AsyncMock, Mock
    from scripts import collect_live_timing as module
    from app.core.config import Settings
    now = datetime.now(UTC)
    service = Mock()
    service.topics = {"SessionInfo": {"Meeting": {"Name": "United States Grand Prix"}, "Name": "Practice 3", "StartDate": (now - timedelta(minutes=15)).isoformat(), "EndDate": (now + timedelta(minutes=45)).isoformat(), "GmtOffset": "+00:00:00"}}
    service.stop = AsyncMock()
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(401)))
    monkeypatch.setattr(module, "get_settings", lambda: Settings(app_use_sample_data=True))
    monkeypatch.setattr(module, "LiveTimingService", lambda settings: service)
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: client)
    assert asyncio.run(module.collect(1, dry_run=True)) == 0
    service.start.assert_called_once()
    service.stop.assert_awaited_once()


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
    assert result["captureSource"] == "saved"
    assert result["delaySeconds"] > 0
