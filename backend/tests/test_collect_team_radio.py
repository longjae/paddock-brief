from datetime import UTC, datetime

from scripts.collect_team_radio import active_session_paths, openf1_radio_captures, radio_captures
from app.services.live_timing import radio_speaker_segments
import asyncio
import httpx
import pytest
from scripts.collect_team_radio import started_radio_sessions, published_radio_rows
from scripts.collect_team_radio import openf1_or_saved_captures


@pytest.mark.parametrize("status", [401, 403])
def test_live_access_restriction_uses_saved_public_f1_feed(status) -> None:
    def respond(request):
        if request.url.host == "api.openf1.org":
            return httpx.Response(status)
        if request.url.path.endswith("/events/featured"):
            return httpx.Response(200, json={"slug": "2026-united-states"})
        assert request.url.path.endswith("/events/2026-united-states/race-state")
        return httpx.Response(200, json={"event": "2026-united-states", "teamRadio": [
            {"SessionPath": "2026/United_States/Practice_1/", "Path": "TeamRadio/ANT.mp3", "Utc": "2026-10-23T18:00:00Z"},
            {"SessionPath": "../../other/", "Path": "TeamRadio/UNSAFE.mp3"},
        ]})
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await openf1_or_saved_captures(client, datetime(2026, 10, 23, 18, tzinfo=UTC))
    assert asyncio.run(check()) == [("2026/United_States/Practice_1/", {"path": "TeamRadio/ANT.mp3", "utc": "2026-10-23T18:00:00Z"})]


def test_fallback_does_not_mix_another_gp_or_hide_server_failures() -> None:
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await openf1_or_saved_captures(client, datetime.now(UTC))
        def wrong_event(request):
            if request.url.host == "api.openf1.org":
                return httpx.Response(401)
            if request.url.path.endswith("/events/featured"):
                return httpx.Response(200, json={"slug": "2026-united-states"})
            return httpx.Response(200, json={"event": "2026-singapore", "teamRadio": []})
        async with httpx.AsyncClient(transport=httpx.MockTransport(wrong_event)) as client:
            with pytest.raises(ValueError, match="does not match"):
                await openf1_or_saved_captures(client, datetime.now(UTC))
    asyncio.run(check())


def test_future_and_cancelled_sessions_are_not_requested_even_with_filter() -> None:
    now = datetime(2026, 10, 23, 7, tzinfo=UTC)
    sessions = [
        {"session_key": 1, "meeting_name": "United States", "date_start": "2026-10-23T17:30:00Z"},
        {"session_key": 2, "meeting_name": "United States", "date_start": "2026-10-22T17:30:00Z"},
        {"session_key": 3, "meeting_name": "United States", "date_start": "2026-10-22T17:30:00Z", "is_cancelled": True},
    ]
    assert [row["session_key"] for row in started_radio_sessions(sessions, now, "United States")] == [2]
    assert [row["session_key"] for row in started_radio_sessions(sessions, now)] == [2]


def test_missing_radio_is_normal_but_server_errors_still_fail() -> None:
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(404))) as client:
            assert await published_radio_rows(client, 11389) == []
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await published_radio_rows(client, 11389)
    asyncio.run(check())


def test_diarized_segments_keep_timing_without_guessing_identity() -> None:
    payload = {"segments": [
        {"start": 0.2, "end": 1.4, "speaker": "A", "text": "Box now."},
        {"start": 1.5, "end": 2.1, "speaker": "driver", "text": "Copy."},
        {"start": -1, "end": 2, "speaker": "B", "text": "bad"},
    ]}
    assert radio_speaker_segments(payload) == [
        {"start": 0.2, "end": 1.4, "speaker": "A", "text": "Box now."},
        {"start": 1.5, "end": 2.1, "speaker": None, "text": "Copy."},
    ]


def test_radio_archive_parses_list_and_delta_captures() -> None:
    stream = (
        '\ufeff00:00:01.000{"Captures":[{"Utc":"2026-10-11T12:00:00Z","Path":"TeamRadio/ONE.mp3"}]}\n'
        '00:00:02.000{"Captures":{"1":{"Utc":"2026-10-11T12:01:00Z","Path":"TeamRadio/TWO.mp3"}}}\n'
    )
    assert [item["path"] for item in radio_captures(stream)] == ["TeamRadio/TWO.mp3", "TeamRadio/ONE.mp3"]


def test_recent_session_selection_does_not_pull_old_events() -> None:
    index = {"Meetings": [{"Name": "Test Grand Prix", "Sessions": [
        {"Path": "2026/test/race/", "StartDate": "2026-10-11T12:00:00"},
        {"Path": "2026/old/race/", "StartDate": "2026-01-01T12:00:00"},
    ]}]}
    assert active_session_paths(index, datetime(2026, 10, 14, tzinfo=UTC)) == ["2026/test/race/"]


def test_openf1_fallback_keeps_only_recent_official_recordings() -> None:
    sessions = [
        {"session_key": 1, "meeting_name": "Singapore Grand Prix", "date_start": "2026-10-11T12:00:00+00:00"},
        {"session_key": 2, "meeting_name": "Old Grand Prix", "date_start": "2026-01-01T12:00:00+00:00"},
    ]
    rows = [
        {"session_key": 1, "date": "2026-10-11T12:01:00+00:00", "recording_url": "https://livetiming.formula1.com/static/2026/Singapore/Race/TeamRadio/VER.mp3"},
        {"session_key": 1, "date": "2026-10-11T12:01:00+00:00", "recording_url": "https://livetiming.formula1.com/static/2026/Singapore/Race/TeamRadio/VER.mp3"},
        {"session_key": 2, "date": "2026-01-01T12:01:00+00:00", "recording_url": "https://livetiming.formula1.com/static/2026/Old/Race/TeamRadio/OLD.mp3"},
        {"session_key": 1, "date": "2026-10-11T12:02:00+00:00", "recording_url": "https://example.com/TeamRadio/OTHER.mp3"},
    ]
    assert openf1_radio_captures(sessions, rows, datetime(2026, 10, 14, tzinfo=UTC)) == [
        ("2026/Singapore/Race/", {"path": "TeamRadio/VER.mp3", "utc": "2026-10-11T12:01:00+00:00"})
    ]
