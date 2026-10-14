import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.schemas import EventDetail
from app.services.openf1 import OpenF1Service
from app.services.sample_data import DEMO_EVENT


def test_session_results_match_exact_gp_and_stint_laps() -> None:
    service = OpenF1Service()
    service.meetings = AsyncMock(return_value=[{"meeting_name": "Singapore Grand Prix", "meeting_key": 91}])
    service.sessions = AsyncMock(return_value=[{"session_name": "Race", "session_key": 92, "date_start": "2025-10-05T12:00:00+00:00"}])

    async def get(resource: str, **params: object):
        assert params == {"session_key": 92}
        return {
            "session_result": [{"driver_number": 16, "position": 1, "number_of_laps": 62, "duration": 7200.123, "gap_to_leader": 0}, {"driver_number": 55, "position": "NC", "number_of_laps": 0, "dnf": True}],
            "stints": [
                {"driver_number": 16, "stint_number": 2, "compound": "HARD", "lap_start": 21, "lap_end": 62, "tyre_age_at_start": 1},
                {"driver_number": 16, "stint_number": 1, "compound": "MEDIUM", "lap_start": 1, "lap_end": 20, "tyre_age_at_start": 0},
            ],
            "drivers": [{"driver_number": 16, "name_acronym": "LEC", "full_name": "Charles Leclerc", "team_name": "Ferrari", "team_colour": "ed1131"}, {"driver_number": 55, "name_acronym": "SAI", "full_name": "Carlos Sainz", "team_name": "Williams", "team_colour": "64c4ff"}],
        }[resource]

    service._get = AsyncMock(side_effect=get)
    result = asyncio.run(service.session_data(EventDetail.model_validate(DEMO_EVENT), "R"))
    assert result is not None
    assert result["status"] == "published"
    assert result["maxLap"] == 62
    assert [stint["compound"] for stint in result["drivers"][0]["stints"]] == ["MEDIUM", "HARD"]
    assert result["drivers"][0]["time"] == "2:00:00.123"
    assert result["drivers"][1]["position"] is None


def test_upcoming_session_does_not_fetch_results() -> None:
    service = OpenF1Service()
    service.meetings = AsyncMock(return_value=[{"meeting_name": "Singapore Grand Prix", "meeting_key": 91}])
    future = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
    service.sessions = AsyncMock(return_value=[{"session_name": "Race", "session_key": 92, "date_start": future}])
    service._get = AsyncMock()
    result = asyncio.run(service.session_data(EventDetail.model_validate(DEMO_EVENT), "R"))
    assert result is not None and result["status"] == "upcoming"
    service._get.assert_not_called()


def test_other_gp_is_not_used_as_result_fallback() -> None:
    service = OpenF1Service()
    service.meetings = AsyncMock(return_value=[{"meeting_name": "Miami Grand Prix", "meeting_key": 91}])
    service.sessions = AsyncMock()
    result = asyncio.run(service.session_data(EventDetail.model_validate(DEMO_EVENT), "R"))
    assert result is None
    service.sessions.assert_not_called()
