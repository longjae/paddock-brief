from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.services.calendar_registry import calendar_registration, register_missing_active_events


RACE = {"season": "2026", "round": "18", "raceName": "United States Grand Prix", "date": "2026-10-25", "time": "20:00:00Z", "FirstPractice": {"date": "2026-10-23", "time": "17:30:00Z"}, "SecondPractice": {"date": "2026-10-23", "time": "21:00:00Z"}, "ThirdPractice": {"date": "2026-10-24", "time": "17:30:00Z"}, "Qualifying": {"date": "2026-10-24", "time": "21:00:00Z"}, "Circuit": {"circuitId": "americas", "circuitName": "Circuit of the Americas", "Location": {"country": "USA", "locality": "Austin"}}}


def test_registration_keeps_austin_timezone_and_all_sessions() -> None:
    event, sessions = calendar_registration(RACE, datetime(2026, 10, 25, tzinfo=UTC))
    assert event["slug"] == "2026-united-states" and event["timezone"] == "America/Chicago"
    assert event["start_at"] == "2026-10-23T17:30:00+00:00"
    assert [session["short_name"] for session in sessions] == ["FP1", "FP2", "FP3", "Q", "R"]
    assert sessions[-1]["session_type"] == "race" and sessions[-1]["status"] == "upcoming"


def test_missing_active_event_is_registered_without_overwriting_editorial(monkeypatch) -> None:
    service = MagicMock()
    service.races = AsyncMock(return_value=[RACE])
    monkeypatch.setattr("app.services.calendar_registry.JolpicaService", lambda: service)
    events, sessions = MagicMock(), MagicMock()
    database = MagicMock()
    database.table.side_effect = lambda table: {"events": events, "sessions": sessions}[table]
    events.select.return_value.execute.return_value.data = [{"slug": "2026-singapore"}]
    events.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"id": "event-18"}
    assert register_missing_active_events(database, datetime(2026, 10, 25, tzinfo=UTC)) == ["2026-united-states"]
    assert events.upsert.call_args.kwargs == {"on_conflict": "slug", "ignore_duplicates": True}
    assert len(sessions.upsert.call_args.args[0]) == 5
    events.upsert.reset_mock()
    events.select.return_value.execute.return_value.data = [{"slug": "2026-united-states"}]
    assert register_missing_active_events(database, datetime(2026, 10, 25, tzinfo=UTC)) == []
    events.upsert.assert_not_called()


def test_outside_weekend_does_not_register_future_event(monkeypatch) -> None:
    service = MagicMock()
    service.races = AsyncMock(return_value=[RACE])
    monkeypatch.setattr("app.services.calendar_registry.JolpicaService", lambda: service)
    database = MagicMock()
    database.table.return_value.select.return_value.execute.return_value.data = []
    assert register_missing_active_events(database, datetime(2026, 10, 1, tzinfo=UTC)) == []
    database.table.return_value.upsert.assert_not_called()
