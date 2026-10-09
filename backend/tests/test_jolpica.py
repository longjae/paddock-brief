from datetime import datetime, timezone

from app.services.jolpica import _event_drivers, _featured_race, _session_payload, _slug, _standings_payload


RACE = {
    "season": "2026",
    "round": "1",
    "raceName": "Australian Grand Prix",
    "date": "2026-03-08",
    "time": "04:00:00Z",
    "FirstPractice": {"date": "2026-03-06", "time": "01:30:00Z"},
    "Qualifying": {"date": "2026-03-07", "time": "05:00:00Z"},
    "Circuit": {"circuitName": "Albert Park", "Location": {"locality": "Melbourne", "country": "Australia"}},
}


def test_jolpica_slug_and_sessions() -> None:
    assert _slug(2026, RACE["raceName"]) == "2026-australian"
    sessions = _session_payload(RACE, datetime(2026, 3, 9, tzinfo=timezone.utc))
    assert [session["shortName"] for session in sessions] == ["FP1", "Q", "R"]
    assert all(session["status"] == "done" for session in sessions)
    assert sessions[0]["startsAt"] == "2026-03-06 10:30"


def test_jolpica_featured_race_uses_thursday_window() -> None:
    next_race = {**RACE, "raceName": "Chinese Grand Prix", "date": "2026-03-15", "round": "2"}
    assert _featured_race([RACE, next_race], datetime(2026, 3, 11, 23, tzinfo=timezone.utc))["round"] == "1"
    assert _featured_race([RACE, next_race], datetime(2026, 3, 12, 1, tzinfo=timezone.utc))["round"] == "2"


def test_jolpica_results_become_event_drivers() -> None:
    drivers = _event_drivers([
        {
            "position": "1", "number": "4", "points": "25", "status": "Finished",
            "Driver": {"driverId": "norris", "code": "NOR", "givenName": "Lando", "familyName": "Norris", "nationality": "British"},
            "Constructor": {"constructorId": "mclaren", "name": "McLaren"},
        }
    ])
    assert drivers[0]["code"] == "NOR"
    assert drivers[0]["resultPosition"] == 1


def test_jolpica_standings_are_normalized() -> None:
    constructors, drivers = _standings_payload(
        [{"position": "1", "points": "620", "wins": "12", "Constructor": {"constructorId": "mclaren", "name": "McLaren", "nationality": "British"}}],
        [{"position": "1", "points": "401", "wins": "7", "Driver": {"driverId": "norris", "code": "NOR", "givenName": "Lando", "familyName": "Norris"}, "Constructors": [{"constructorId": "mclaren", "name": "McLaren"}]}],
    )
    assert constructors[0]["teamCode"] == "mclaren"
    assert drivers[0]["code"] == "NOR"
    assert drivers[0]["teamCode"] == "mclaren"
