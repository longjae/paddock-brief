import os

os.environ["APP_USE_SAMPLE_DATA"] = "true"

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from datetime import datetime, timezone

from app.services.openf1 import _featured_meeting, _slug
from app.services.media_window import media_window
from app.services.repository import EventRepository

client = TestClient(app)


def test_meeting_slugs_do_not_collide_for_same_country() -> None:
    assert _slug(2026, "Spanish Grand Prix") == "2026-spanish"
    assert _slug(2026, "Barcelona Grand Prix") == "2026-barcelona"


def test_media_window_opens_on_local_thursday_for_sunday_race() -> None:
    window = media_window("2026-10-11T14:00:00+00:00", "+08:00:00")
    assert window["mediaOpenAt"] == "2026-10-07T16:00:00+00:00"
    assert window["mediaOpenLabel"] == "10월 8일 목요일 · 개최지 현지시간"


def test_media_window_stays_on_thursday_for_saturday_race() -> None:
    window = media_window("2026-09-26T13:00:00+00:00", "+04:00:00")
    assert window["mediaOpenLabel"] == "9월 24일 목요일 · 개최지 현지시간"


def test_featured_event_stays_on_latest_race_until_next_media_window() -> None:
    rows = [
        {
            "meeting_name": "Bahrain Grand Prix",
            "date_end": "2026-10-04T09:00:00+00:00",
            "gmt_offset": "+08:00:00",
        },
        {
            "meeting_name": "Singapore Grand Prix",
            "date_end": "2026-10-11T14:00:00+00:00",
            "gmt_offset": "+08:00:00",
        },
    ]
    selected = _featured_meeting(rows, datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc))
    assert selected["meeting_name"] == "Bahrain Grand Prix"


def test_featured_event_switches_when_next_media_window_opens() -> None:
    rows = [
        {
            "meeting_name": "Bahrain Grand Prix",
            "date_end": "2026-10-04T09:00:00+00:00",
            "gmt_offset": "+08:00:00",
        },
        {
            "meeting_name": "Singapore Grand Prix",
            "date_end": "2026-10-11T14:00:00+00:00",
            "gmt_offset": "+08:00:00",
        },
    ]
    selected = _featured_meeting(rows, datetime(2026, 10, 7, 16, 0, tzinfo=timezone.utc))
    assert selected["meeting_name"] == "Singapore Grand Prix"


def test_sample_event_list_uses_frontend_field_names() -> None:
    event = EventRepository(Settings(app_use_sample_data=True)).list_events()[0]
    assert set(event) == {"slug", "season", "round", "name", "country", "circuit", "dateLabel", "mediaOpenAt", "mediaOpenLabel"}


def test_health_uses_jolpica_mode() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "jolpica"


def test_event_detail_contract() -> None:
    response = client.get("/api/v1/events/2026-singapore")
    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "2026-singapore"
    assert payload["tyreAllocation"] == {"hard": "C3", "medium": "C4", "soft": "C5"}
    assert len(payload["videos"]) == 2


def test_unknown_event_returns_404() -> None:
    response = client.get("/api/v1/events/not-found")
    assert response.status_code == 404


def test_supabase_rows_are_normalized_to_frontend_contract() -> None:
    event = EventRepository._normalize(
        {
            "slug": "2026-test",
            "season": 2026,
            "round": 1,
            "short_name": "Test Grand Prix",
            "country": "Testland",
            "circuit_name": "Test Circuit",
            "date_label": "3월 1일",
            "start_at": "2026-03-01T00:00:00Z",
            "sessions": [
                {
                    "name": "Race",
                    "short_name": "R",
                    "starts_at": "2026-03-01T06:00:00Z",
                    "status": "upcoming",
                }
            ],
            "videos": [],
            "interviews": [],
            "tyre_allocations": [],
        }
    )
    assert event.sessions[0].shortName == "R"
    assert event.tyreAllocation.hard == "TBC"


def test_supabase_one_to_one_tyre_relation_is_normalized() -> None:
    event = EventRepository._normalize(
        {
            "slug": "2026-test",
            "season": 2026,
            "round": 1,
            "short_name": "Test Grand Prix",
            "country": "Testland",
            "circuit_name": "Test Circuit",
            "start_at": "2026-03-01T00:00:00Z",
            "sessions": [],
            "videos": [],
            "interviews": [],
            "tyre_allocations": {
                "hard_compound": "C1",
                "medium_compound": "C2",
                "soft_compound": "C3",
                "source_url": "https://example.com/tyres",
            },
        }
    )
    assert event.tyreAllocation.hard == "C1"
    assert event.tyreSourceUrl == "https://example.com/tyres"


def test_final_classification_snapshot_is_normalized() -> None:
    event = EventRepository._normalize(
        {
            "slug": "2026-test",
            "season": 2026,
            "round": 1,
            "short_name": "Test Grand Prix",
            "country": "Testland",
            "circuit_name": "Test Circuit",
            "start_at": "2026-03-01T00:00:00Z",
            "sessions": [
                {
                    "name": "Race",
                    "short_name": "R",
                    "starts_at": "2026-03-01T06:00:00Z",
                    "status": "done",
                    "race_state_snapshots": [
                        {
                            "captured_at": "2026-03-01T08:00:00Z",
                            "state": {
                                "kind": "final-classification",
                                "drivers": [
                                    {
                                        "position": 1,
                                        "code": "TST",
                                        "name": "Test Driver",
                                        "team": "Test Team",
                                        "colour": "#ffffff",
                                        "compound": "SOFT",
                                        "tyreAge": 12,
                                        "gap": "WINNER",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
            "videos": [],
            "interviews": [],
            "tyre_allocations": {},
        }
    )
    assert event.drivers[0].code == "TST"
    assert event.drivers[0].tyreAge == 12


def test_team_content_is_normalized() -> None:
    event = EventRepository._normalize(
        {
            "slug": "2026-test",
            "season": 2026,
            "round": 1,
            "short_name": "Test Grand Prix",
            "country": "Testland",
            "circuit_name": "Test Circuit",
            "start_at": "2026-03-01T00:00:00Z",
            "sessions": [],
            "videos": [],
            "interviews": [],
            "tyre_allocations": {},
            "team_content": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "content_kind": "interview",
                    "title": "Team interview",
                    "source_url": "https://example.com/interview",
                    "korean_summary": "한국어 요약",
                    "participants": ["Test Driver"],
                    "published_at": "2026-03-01T08:00:00Z",
                    "teams": {"code": "test", "name": "Test Team", "colour": "#ffffff", "sort_order": 1},
                    "sources": {"name": "Test Source"},
                }
            ],
        }
    )
    assert event.teamContent[0].team == "Test Team"
    assert event.teamContent[0].contentType == "interview"
    assert event.teamContent[0].detailedSummary == "한국어 요약"


def test_media_articles_are_normalized() -> None:
    event = EventRepository._normalize(
        {
            "slug": "2026-test",
            "season": 2026,
            "round": 1,
            "short_name": "Test Grand Prix",
            "country": "Testland",
            "circuit_name": "Test Circuit",
            "start_at": "2026-03-01T00:00:00Z",
            "sessions": [],
            "videos": [],
            "interviews": [],
            "tyre_allocations": {},
            "event_news": [
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "category": "analysis",
                    "title": "Race analysis",
                    "source_url": "https://example.com/analysis",
                    "korean_summary": "분석 요약",
                    "author": "Reporter",
                    "tags": ["전략"],
                    "team_codes": ["test"],
                    "driver_codes": ["TST"],
                    "published_at": "2026-03-01T09:00:00Z",
                    "is_paywalled": False,
                    "sources": {"name": "Test Media"},
                }
            ],
        }
    )
    assert event.news[0].outlet == "Test Media"
    assert event.news[0].tags == ["전략"]
    assert event.news[0].detailedSummary == "분석 요약"


def test_event_drivers_are_normalized() -> None:
    event = EventRepository._normalize(
        {
            "slug": "2026-test",
            "season": 2026,
            "round": 1,
            "short_name": "Test Grand Prix",
            "country": "Testland",
            "circuit_name": "Test Circuit",
            "start_at": "2026-03-01T00:00:00Z",
            "sessions": [],
            "videos": [],
            "interviews": [],
            "tyre_allocations": {},
            "event_drivers": [
                {
                    "id": "33333333-3333-3333-3333-333333333333",
                    "result_position": 1,
                    "result_status": "classified",
                    "points": 25,
                    "drivers": {"code": "TST", "full_name": "Test Driver", "permanent_number": 99, "nationality": "Testland", "profile_url": "https://example.com/driver", "previous_season_rank": 4},
                    "teams": {"code": "test", "name": "Test Team", "colour": "#ffffff", "sort_order": 1},
                }
            ],
        }
    )
    assert event.eventDrivers[0].code == "TST"
    assert event.eventDrivers[0].resultPosition == 1
    assert event.eventDrivers[0].previousSeasonRank == 4
