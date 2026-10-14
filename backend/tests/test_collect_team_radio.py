from datetime import UTC, datetime

from scripts.collect_team_radio import active_session_paths, openf1_radio_captures, radio_captures


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
        {"session_key": 2, "date": "2026-01-01T12:01:00+00:00", "recording_url": "https://livetiming.formula1.com/static/2026/Old/Race/TeamRadio/OLD.mp3"},
        {"session_key": 1, "date": "2026-10-11T12:02:00+00:00", "recording_url": "https://example.com/TeamRadio/OTHER.mp3"},
    ]
    assert openf1_radio_captures(sessions, rows, datetime(2026, 10, 14, tzinfo=UTC)) == [
        ("2026/Singapore/Race/", {"path": "TeamRadio/VER.mp3", "utc": "2026-10-11T12:01:00+00:00"})
    ]
