from app.services.race_results import public_classification_snapshot


def test_public_classification_keeps_drivers_without_tyre_data() -> None:
    race = {"Results": [
        {"position": "1", "Driver": {"code": "VER", "permanentNumber": "3", "givenName": "Max", "familyName": "Verstappen"}, "Constructor": {"name": "Red Bull"}, "Time": {"time": "1:40:00.000"}, "status": "Finished"},
        {"position": "2", "Driver": {"code": "LEC", "permanentNumber": "16", "givenName": "Charles", "familyName": "Leclerc"}, "Constructor": {"name": "Ferrari"}, "Time": {"time": "+7.335"}, "status": "Finished"},
    ]}
    stints = [{"driver_number": 3, "lap_start": 20, "lap_end": 62, "compound": "HARD", "tyre_age_at_start": 2}]
    state = public_classification_snapshot(race, stints, [{"driver_number": 3, "team_colour": "3671C6"}])
    assert [driver["code"] for driver in state["drivers"]] == ["VER", "LEC"]
    assert state["drivers"][0]["tyreAge"] == 45
    assert state["drivers"][0]["colour"] == "#3671C6"
    assert state["drivers"][1]["compound"] is None
    assert state["drivers"][1]["gap"] == "+7.335"
