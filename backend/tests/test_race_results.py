from app.services.race_results import public_classification_snapshot


def test_public_classification_keeps_drivers_without_tyre_data() -> None:
    race = {"Results": [
        {"position": "1", "Driver": {"code": "VER", "permanentNumber": "3", "givenName": "Max", "familyName": "Verstappen"}, "Constructor": {"name": "Red Bull"}, "Time": {"time": "1:40:00.000"}, "status": "Finished"},
        {"position": "2", "Driver": {"code": "LEC", "permanentNumber": "16", "givenName": "Charles", "familyName": "Leclerc"}, "Constructor": {"name": "Ferrari"}, "Time": {"time": "+7.335"}, "status": "Finished"},
        {"position": "3", "Driver": {"code": "GAS", "permanentNumber": "10", "givenName": "Pierre", "familyName": "Gasly"}, "Constructor": {"name": "Alpine"}, "Time": {"time": "+2.171"}, "status": "+1 Lap"},
    ]}
    stints = [{"driver_number": 3, "lap_start": 20, "lap_end": 62, "compound": "HARD", "tyre_age_at_start": 2}]
    state = public_classification_snapshot(race, stints, [{"driver_number": 3, "team_colour": "3671C6"}])
    assert [driver["code"] for driver in state["drivers"]] == ["VER", "LEC", "GAS"]
    assert state["drivers"][0]["tyreAge"] == 45
    assert state["drivers"][0]["colour"] == "#3671C6"
    assert state["drivers"][1]["compound"] is None
    assert state["drivers"][1]["gap"] == "+7.335"
    assert state["drivers"][2]["gap"] == "+1 Lap"


def test_public_results_validate_country_round_and_circuit_not_race_title(monkeypatch):
    import copy
    import httpx
    import pytest
    from app.services import race_results
    race = {"season": "2026", "round": "21", "raceName": "Las Vegas Grand Prix", "date": "2026-11-22", "Circuit": {"circuitName": "Las Vegas Strip Street Circuit", "Location": {"locality": "Las Vegas", "country": "USA"}}, "Results": [{"position": "1"}]}
    payload = copy.deepcopy(race)
    real_client = httpx.Client
    def handler(request):
        data = {"MRData": {"RaceTable": {"Races": [payload]}}} if request.url.host == "api.jolpi.ca" else []
        return httpx.Response(200, json=data)
    monkeypatch.setattr(race_results.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler)))
    result, _, _ = race_results.fetch_public_results(2026, 21, "USA", locality="Las Vegas")
    assert result["raceName"] == "Las Vegas Grand Prix"
    result, _, _ = race_results.fetch_public_results(2026, 21, "United States", locality="Las Vegas", circuit_name="Las Vegas Strip Street Circuit")
    assert result["Circuit"]["Location"]["country"] == "USA"
    for field, value in [("round", "20"), ("season", "2025")]:
        payload = {**copy.deepcopy(race), field: value}
        with pytest.raises(ValueError, match="does not match"):
            race_results.fetch_public_results(2026, 21, "USA", locality="Las Vegas")
    payload = copy.deepcopy(race)
    payload["Circuit"]["Location"]["locality"] = "Miami"
    with pytest.raises(ValueError, match="does not match"):
        race_results.fetch_public_results(2026, 21, "USA", locality="Las Vegas")
    payload = copy.deepcopy(race)
    payload["Circuit"]["Location"]["country"] = "Mexico"
    with pytest.raises(ValueError, match="does not match"):
        race_results.fetch_public_results(2026, 21, "USA", locality="Las Vegas")
