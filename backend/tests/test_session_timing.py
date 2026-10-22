import asyncio
from unittest.mock import AsyncMock

import httpx

from app.schemas import EventDetail
from app.services.openf1 import OpenF1Service
from app.services.sample_data import DEMO_EVENT
from app.services.session_timing import historical_snapshot


SESSION = {"session_name": "Practice 1", "session_key": 12, "date_start": "2025-10-03T08:00:00+00:00", "date_end": "2025-10-03T09:00:00+00:00"}
RESULTS = {"status": "published", "maxLap": 3, "drivers": [{"number": 16, "position": 1, "code": "LEC", "name": "Charles Leclerc", "team": "Ferrari", "colour": "#ff0000", "gap": 0, "status": "CLASSIFIED", "stints": [{"compound": "SOFT", "startLap": 1, "endLap": 3, "tyreAgeAtStart": 2}]}]}
LAPS = [{"driver_number": 16, "lap_number": 2, "lap_duration": 90.1, "duration_sector_1": 30.0, "duration_sector_2": 30.1, "duration_sector_3": 30.0, "segments_sector_1": [2048, 2051]}, {"driver_number": 16, "lap_number": 3, "lap_duration": 91.2, "duration_sector_1": 31.0, "duration_sector_2": 30.1, "duration_sector_3": 30.1, "segments_sector_1": [2049, 0]}]


def test_practice_archive_preserves_final_rank_last_lap_and_source() -> None:
    snapshot = historical_snapshot("2026-singapore", SESSION, RESULTS, LAPS, [], [], [])
    assert snapshot["session"]["name"] == "Practice 1"
    assert snapshot["session"]["ended"] is True
    assert snapshot["isLive"] is False and snapshot["archived"] is True
    driver = snapshot["drivers"][0]
    assert driver["lastLap"] == "1:31.200" and driver["bestLap"] == "1:30.100"
    assert driver["miniSectors"] == [["green", "unknown"], [], []]
    assert driver["compound"] == "SOFT" and driver["tyreAge"] == 5
    assert driver["pitStops"] is None  # Stint changes do not prove a pit-stop count.
    assert snapshot["track"] is None  # No historical location is invented.


def test_radio_history_maps_official_urls_and_rejects_other_hosts() -> None:
    official = "https://livetiming.formula1.com/static/2025/2025-10-05_Singapore_Grand_Prix/2025-10-03_Practice_1/TeamRadio/LEC.mp3"
    snapshot = historical_snapshot("2026-singapore", SESSION, RESULTS, [], [], [{"recording_url": official, "driver_number": 16, "date": "2025-10-03T08:30:00Z"}, {"recording_url": "https://other.example/static/test/TeamRadio/a.mp3"}], [])
    assert len(snapshot["teamRadio"]) == 1
    assert snapshot["teamRadio"][0]["Path"] == "TeamRadio/LEC.mp3"
    assert snapshot["teamRadio"][0]["SessionPath"].endswith("Practice_1/")


def test_optional_radio_failure_does_not_hide_timing_and_cache_is_per_session() -> None:
    service = OpenF1Service()
    service._matching_session = AsyncMock(return_value=SESSION)
    service.session_data = AsyncMock(return_value=RESULTS)

    async def get(resource, **params):
        assert params["session_key"] == 12
        if resource == "team_radio":
            raise httpx.ReadTimeout("unavailable")
        return LAPS if resource == "laps" else []

    service._get = AsyncMock(side_effect=get)
    result = asyncio.run(service.session_timing(EventDetail.model_validate(DEMO_EVENT), "FP1"))
    assert result["drivers"][0]["bestLap"] == "1:30.100"
    assert result["teamRadio"] == []
    asyncio.run(service.session_timing(EventDetail.model_validate(DEMO_EVENT), "FP1"))
    assert service.session_data.await_count == 1


def test_upcoming_archive_does_not_request_feed_records() -> None:
    service = OpenF1Service()
    service._matching_session = AsyncMock(return_value={**SESSION, "date_start": "2099-10-03T08:00:00Z", "date_end": "2099-10-03T09:00:00Z"})
    service.session_data = AsyncMock(return_value={"status": "upcoming", "drivers": []})
    service._get = AsyncMock()
    result = asyncio.run(service.session_timing(EventDetail.model_validate(DEMO_EVENT), "FP1"))
    assert result["archiveStatus"] == "upcoming" and result["drivers"] == []
    service._get.assert_not_called()
