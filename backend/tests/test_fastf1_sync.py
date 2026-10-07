from datetime import timedelta

from app.services.fastf1_sync import classification_snapshot, latest_tyre_by_driver


def test_latest_tyre_uses_last_valid_lap() -> None:
    tyres = latest_tyre_by_driver([
        {"Driver": "NOR", "LapNumber": 1, "Compound": "MEDIUM", "TyreLife": 1},
        {"Driver": "NOR", "LapNumber": 20, "Compound": "HARD", "TyreLife": 12},
    ])
    assert tyres["NOR"] == {"lap_number": 20, "compound": "HARD", "tyre_age": 12}


def test_builds_frontend_classification_snapshot() -> None:
    state = classification_snapshot(
        [{"Position": 1, "Abbreviation": "NOR", "FullName": "Lando Norris", "TeamName": "McLaren", "TeamColor": "FF8700", "Time": timedelta(hours=1)}],
        [{"Driver": "NOR", "LapNumber": 57, "Compound": "HARD", "TyreLife": 31}],
    )
    assert state["kind"] == "final-classification"
    assert state["drivers"][0]["compound"] == "HARD"
    assert state["drivers"][0]["gap"] == "WINNER"
