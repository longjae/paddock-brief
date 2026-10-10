from app.core.config import Settings
from app.services.live_timing import LiveTimingService, _deep_merge


def test_deep_merge_preserves_existing_timing_fields() -> None:
    current = {"Lines": {"1": {"Position": "1", "GapToLeader": ""}}}
    update = {"Lines": {"1": {"LastLapTime": {"Value": "1:31.000"}}}}
    merged = _deep_merge(current, update)
    assert merged["Lines"]["1"]["Position"] == "1"
    assert merged["Lines"]["1"]["LastLapTime"]["Value"] == "1:31.000"


def test_signalr_feed_is_normalized_to_live_timing_contract() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    messages = [
        ("DriverList", {"1": {"Tla": "TST", "FullName": "Test Driver", "TeamName": "Test Team", "TeamColour": "ff0000"}}),
        ("TimingData", {"Lines": {"1": {"Position": "1", "GapToLeader": "", "IntervalToPositionAhead": {"Value": ""}, "LastLapTime": {"Value": "1:31.000"}, "BestLapTime": {"Value": "1:30.500"}}}}),
        ("TimingAppData", {"Lines": {"1": {"Stints": {"0": {"Compound": "SOFT", "TotalLaps": 4}}}}}),
        ("SessionInfo", {"Name": "Practice 1", "Meeting": {"Name": "Test Grand Prix"}}),
        ("LapCount", {"CurrentLap": 3, "TotalLaps": 61}),
    ]
    for topic, payload in messages:
        service.consume_signalr({"type": 1, "target": "feed", "arguments": [topic, payload, "2026-01-01T00:00:00Z"]})

    snapshot = service.snapshot("2026-test")
    assert snapshot["session"]["name"] == "Practice 1"
    assert snapshot["session"]["lap"] == 3
    assert snapshot["drivers"][0]["code"] == "TST"
    assert snapshot["drivers"][0]["compound"] == "SOFT"
    assert snapshot["drivers"][0]["tyreAge"] == 4


def test_non_feed_signalr_messages_are_ignored() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.consume_signalr({"type": 6})
    assert service.topics == {}


def test_snapshot_does_not_mix_another_grand_prix() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.topics = {
        "SessionInfo": {"Name": "Race", "Meeting": {"Name": "Singapore Grand Prix"}},
        "TimingData": {"Lines": {"1": {"Position": "1"}}},
        "DriverList": {"1": {"Tla": "TST"}},
    }
    assert service.snapshot("2026-singapore")["drivers"]
    assert service.snapshot("2026-japanese")["drivers"] == []
