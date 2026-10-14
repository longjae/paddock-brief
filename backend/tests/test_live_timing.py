import pytest
import asyncio
import base64
import json
import zlib
import httpx

from app.core.config import Settings
from app.services.live_timing import LiveTimingService, _deep_merge, team_radio_audio_url


def test_deep_merge_preserves_existing_timing_fields() -> None:
    current = {"Lines": {"1": {"Position": "1", "GapToLeader": ""}}}
    update = {"Lines": {"1": {"LastLapTime": {"Value": "1:31.000"}}}}
    merged = _deep_merge(current, update)
    assert merged["Lines"]["1"]["Position"] == "1"
    assert merged["Lines"]["1"]["LastLapTime"]["Value"] == "1:31.000"


def _zipped(value: dict) -> str:
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    raw = json.dumps(value).encode()
    return base64.b64encode(compressor.compress(raw) + compressor.flush()).decode()


def test_live_position_and_car_channels_are_decoded_and_reset_with_session() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.consume_signalr({"type": 1, "target": "feed", "arguments": ["SessionInfo", {"Path": "2026/test/race/", "Name": "Race", "Meeting": {"Name": "Test Grand Prix"}}]})
    service.consume_signalr({"type": 1, "target": "feed", "arguments": ["Position.z", _zipped({"Position": [{"Timestamp": "2026-01-01T12:00:00Z", "Entries": {"1": {"X": 120, "Y": 240, "Status": "OnTrack"}}}]})]})
    service.consume_signalr({"type": 1, "target": "feed", "arguments": ["CarData.z", _zipped({"Entries": [{"Utc": "2026-01-01T12:00:00Z", "Cars": {"1": {"Channels": {"0": 12000, "2": 310, "3": 8, "4": 90, "5": 0}}}}]})]})
    track = service.snapshot("2026-test")["track"]
    assert track["positions"][0]["x"] == 120
    assert track["cars"]["1"]["speed"] == 310
    assert track["trace"] == [{"x": 120, "y": 240}]
    service.consume_signalr({"type": 1, "target": "feed", "arguments": ["SessionInfo", {"Path": "2026/test/qualifying/"}]})
    assert service.track_positions == {}
    assert service.track_car_data == {}


def test_signalr_feed_is_normalized_to_live_timing_contract() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    messages = [
        ("DriverList", {"1": {"Tla": "TST", "FullName": "Test Driver", "TeamName": "Test Team", "TeamColour": "ff0000"}, "2": {"Tla": "RIV", "FullName": "Rival Driver"}}),
        ("TimingData", {"Lines": {
            "1": {"Position": "1", "GapToLeader": "", "IntervalToPositionAhead": {"Value": ""}, "LastLapTime": {"Value": "1:31.000"}, "BestLapTime": {"Value": "1:30.500"}},
            "2": {"Position": "2", "BestLapTime": {"Value": "1:31.200"}},
        }}),
        ("TimingStats", {"Lines": {
            "1": {"BestSectors": {"0": {"Value": "30.100"}, "1": {"Value": "31.200"}, "2": {"Value": "29.200"}}},
            "2": {"BestSectors": {"0": {"Value": "29.900"}, "1": {"Value": "31.500"}, "2": {"Value": "29.400"}}},
        }}),
        ("TimingAppData", {"Lines": {"1": {"Stints": {"0": {"Compound": "MEDIUM", "TotalLaps": 2, "New": "true"}, "1": {"Compound": "SOFT", "TotalLaps": 4, "New": "false"}}}}}),
        ("CurrentTyres", {"Tyres": {"1": {"Compound": "SOFT", "New": "false"}}}),
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
    assert snapshot["drivers"][0]["stint"] == 2
    assert snapshot["drivers"][0]["tyreHistory"][0] == {"compound": "MEDIUM", "laps": 2, "new": True}
    assert snapshot["fastestLap"] == {"driver": "TST", "time": "1:30.500"}
    assert snapshot["fastestSectors"] == [
        {"sector": 1, "driver": "RIV", "time": "29.900"},
        {"sector": 2, "driver": "TST", "time": "31.200"},
        {"sector": 3, "driver": "TST", "time": "29.200"},
    ]
    assert snapshot["tyreInventory"]["available"] is False


def test_non_feed_signalr_messages_are_ignored() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.consume_signalr({"type": 6})
    assert service.topics == {}


def test_race_control_messages_are_retained_when_upstream_delta_removes_them() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.consume_signalr({"type": 1, "target": "feed", "arguments": ["SessionInfo", {"Path": "2026/test/race/", "Meeting": {"Name": "Test Grand Prix"}}, "now"]})
    service.consume_signalr({"type": 1, "target": "feed", "arguments": ["RaceControlMessages", {"Messages": {"1": {"Utc": "2026-01-01T00:00:01Z", "Category": "Flag", "Message": "YELLOW FLAG"}}}, "now"]})
    service.consume_signalr({"type": 1, "target": "feed", "arguments": ["RaceControlMessages", {"Messages": {"1": None, "2": {"Utc": "2026-01-01T00:00:02Z", "Category": "Flag", "Message": "GREEN FLAG"}}}, "now"]})

    messages = service.snapshot("2026-test")["raceControl"]
    assert [message["Message"] for message in messages] == ["GREEN FLAG", "YELLOW FLAG"]


def test_other_grand_prix_does_not_show_previous_race_data() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.topics = {
        "SessionInfo": {"Name": "Race", "Meeting": {"Name": "Singapore Grand Prix"}},
        "TimingData": {"Lines": {"1": {"Position": "1", "BestLapTime": {"Value": "1:30.000"}}}},
        "RaceControlMessages": {"Messages": {"1": {"Utc": "2026-10-11T12:00:00Z", "Message": "CHEQUERED FLAG"}}},
        "TeamRadio": {"Captures": {"1": {"Path": "TeamRadio/test.mp3"}}},
        "LapCount": {"CurrentLap": 62, "TotalLaps": 62},
    }
    snapshot = service.snapshot("2026-united-states")
    assert snapshot["session"]["meeting"] is None
    assert snapshot["session"]["lap"] == 0
    assert snapshot["drivers"] == []
    assert snapshot["raceControl"] == []
    assert snapshot["teamRadio"] == []
    assert snapshot["fastestLap"] is None


def test_race_control_history_resets_when_session_changes() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service._track_session({"Path": "2026/test/sprint/"})
    service._capture_race_control({"Messages": [{"Utc": "1", "Message": "SPRINT MESSAGE"}]})
    service._track_session({"Path": "2026/test/qualifying/"})
    assert service.race_control_history == {}


def test_signalr_subscription_result_seeds_full_session_state() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.consume_signalr(
        {
            "type": 3,
            "invocationId": "1",
            "result": {
                "DriverList": {"63": {"Tla": "RUS", "FullName": "George Russell"}},
                "SessionInfo": {"Name": "Sprint", "Meeting": {"Name": "Singapore Grand Prix"}},
                "TimingData": {"Lines": {"63": {"Position": "1"}}},
                "LapCount": {"CurrentLap": 2, "TotalLaps": 19},
            },
        }
    )

    snapshot = service.snapshot("2026-singapore")
    assert snapshot["isLive"] is True
    assert snapshot["session"] == {"name": "Sprint", "meeting": "Singapore Grand Prix", "remaining": "—", "lap": 2, "totalLaps": 19}
    assert snapshot["drivers"][0]["code"] == "RUS"


def test_snapshot_does_not_mix_another_grand_prix() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.topics = {
        "SessionInfo": {"Name": "Race", "Meeting": {"Name": "Singapore Grand Prix"}},
        "TimingData": {"Lines": {"1": {"Position": "1"}}},
        "DriverList": {"1": {"Tla": "TST"}},
    }
    assert service.snapshot("2026-singapore")["drivers"]
    assert service.snapshot("2026-japanese")["drivers"] == []


def test_team_radio_audio_url_is_restricted_to_official_paths() -> None:
    path = "TeamRadio/VER_3_20261010_173427.mp3"
    session_path = "2026/2026-10-10_Singapore_Grand_Prix/2026-10-10_Sprint/"
    assert team_radio_audio_url(path, session_path) == f"https://livetiming.formula1.com/static/{session_path}{path}"
    with pytest.raises(ValueError):
        team_radio_audio_url("https://example.com/radio.mp3", session_path)
    with pytest.raises(ValueError):
        team_radio_audio_url(path, "../../private/")


def test_saved_radio_transcript_is_available_without_runtime_openai_key() -> None:
    class StoredRadio:
        def table(self, name):
            assert name == "team_radio_transcripts"
            return self

        def select(self, columns):
            return self

        def eq(self, column, value):
            return self

        def limit(self, count):
            return self

        def execute(self):
            return type("Result", (), {"data": [{"transcript": "Box, box", "translation": "피트로 들어오세요"}]})()

    service = LiveTimingService(Settings(app_use_sample_data=True, openai_api_key=None))
    service.radio_store = StoredRadio()
    result = asyncio.run(service.transcribe_team_radio("TeamRadio/VER_3_20261010_173427.mp3", "2026/2026-10-10_Singapore_Grand_Prix/2026-10-10_Sprint/"))
    assert result["transcript"] == "Box, box"
    assert result["translation"] == "피트로 들어오세요"


def test_new_radio_transcript_is_saved_for_later_requests(monkeypatch) -> None:
    import app.services.live_timing as live_timing

    saved = []

    class StoredRadio:
        def table(self, name):
            assert name == "team_radio_transcripts"
            return self

        def select(self, columns):
            return self

        def eq(self, column, value):
            return self

        def limit(self, count):
            return self

        def upsert(self, value, on_conflict):
            assert on_conflict == "session_path,path"
            saved.append(value)
            return self

        def execute(self):
            return type("Result", (), {"data": []})()

    def respond(request):
        if request.url.path.endswith(".mp3"):
            return httpx.Response(200, content=b"audio")
        if request.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": "Box, box"})
        return httpx.Response(200, json={"output_text": "피트로 들어오세요"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(live_timing.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs))
    service = LiveTimingService(Settings(app_use_sample_data=True, openai_api_key="test", supabase_secret_key="secret"))
    service.radio_store = StoredRadio()
    result = asyncio.run(service.transcribe_team_radio("TeamRadio/TEST.mp3", "2026/test/Race/"))
    assert result["transcript"] == "Box, box"
    assert saved == [{"session_path": "2026/test/Race/", "path": "TeamRadio/TEST.mp3", "transcript": "Box, box", "translation": "피트로 들어오세요"}]


def test_mini_sector_colours_follow_timing_segments() -> None:
    service = LiveTimingService(Settings(app_use_sample_data=True))
    service.topics = {
        "SessionInfo": {"Meeting": {"Name": "Test Grand Prix"}},
        "DriverList": {"1": {"Tla": "TST"}},
        "TimingData": {"Lines": {"1": {"Position": "1", "NumberOfPitStops": "1", "Sectors": {
            "0": {"Value": "30.100", "Segments": {"0": {"Status": 2048}, "1": {"Status": 2049}}},
            "1": {"Segments": [{"Status": 2051}, {"Status": 2064}]},
            "2": {"Segments": {"0": {"Status": 9999}}},
        }}}},
    }
    assert service.snapshot("2026-test")["drivers"][0]["miniSectors"] == [
        ["yellow", "green"], ["purple", "pit"], ["unknown"],
    ]
    assert service.snapshot("2026-test")["drivers"][0]["currentSectors"] == ["30.100", "—", "—"]
    assert service.snapshot("2026-test")["drivers"][0]["pitStops"] == 1
