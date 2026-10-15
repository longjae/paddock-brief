import os
import asyncio
from unittest.mock import MagicMock

os.environ["APP_USE_SAMPLE_DATA"] = "true"

from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.core.config import Settings
from app.main import app
from datetime import datetime, timezone

from app.services.openf1 import _featured_meeting, _slug
from app.services.media_window import media_window
from app.services.repository import EventRepository
from app.api import routes
from app.services.fia_documents import DecisionDocumentParser, event_documents_url

client = TestClient(app)


def test_fia_document_parser_keeps_decisions_and_penalties() -> None:
    parser = DecisionDocumentParser()
    parser.feed('''<ul><li class="document-row"><a href="/system/files/decision-document/decision.pdf"><div class="title">Doc 12 - Decision - Car 44</div><div class="published">Published on 25.10.26 18:00 CET</div></a></li><li class="document-row"><a href="/system/files/decision-document/classification.pdf"><div class="title">Final classification</div></a></li></ul>''')
    assert len(parser.documents) == 1
    assert parser.documents[0]["url"] == "https://www.fia.com/system/files/decision-document/decision.pdf"
    assert "season-2026-2072" in event_documents_url(2026, "United States Grand Prix")


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


def test_missing_reviewed_event_can_fall_back_to_calendar() -> None:
    repository = EventRepository(Settings(app_use_sample_data=True))
    repository.client = MagicMock()
    repository.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None
    try:
        repository.get_event("2026-united-states")
    except HTTPException as error:
        assert error.status_code == 404
    else:
        raise AssertionError("Missing reviewed event must return 404")
    repository.client.table.return_value.select.return_value.eq.return_value.maybe_single.assert_called_once()


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


def test_race_state_exposes_live_connection_contract() -> None:
    response = client.get("/api/v1/events/2026-singapore/race-state")
    assert response.status_code == 200
    payload = response.json()
    assert payload["event"] == "2026-singapore"
    assert payload["connection"] == "disabled"
    assert payload["isLive"] is False
    assert "raceControl" in payload


def test_live_stream_uses_one_collector_and_stops_it(monkeypatch) -> None:
    class Collector:
        started = False
        stopped = False

        def start(self) -> None:
            self.started = True

        def snapshot(self, slug: str) -> dict[str, object]:
            return {"event": slug, "connection": "live", "drivers": [{"code": "TST"}]}

        async def stop(self) -> None:
            self.stopped = True

    class RequestStub:
        async def is_disconnected(self) -> bool:
            return False

    collector = Collector()
    monkeypatch.setattr(routes, "LiveTimingService", lambda _settings: collector)

    async def check() -> None:
        stream = routes.live_timing_events(
            "2026-singapore", RequestStub(), Settings(app_use_sample_data=True),
            max_duration_seconds=30, interval_seconds=0,
        )
        assert await anext(stream) == "retry: 1000\n\n"
        frame = await anext(stream)
        assert "event: timing" in frame
        assert '"event": "2026-singapore"' in frame
        await stream.aclose()

    asyncio.run(check())
    assert collector.started is True
    assert collector.stopped is True


def test_live_stream_falls_back_to_saved_state_until_feed_connects(monkeypatch) -> None:
    class Collector:
        def start(self) -> None:
            pass

        def snapshot(self, slug: str) -> dict[str, object]:
            return {"event": slug, "drivers": []}

        async def stop(self) -> None:
            pass

    class RequestStub:
        async def is_disconnected(self) -> bool:
            return False

    async def saved(slug: str) -> dict[str, object]:
        return {"event": slug, "connection": "offline", "drivers": [{"code": "TST"}]}

    monkeypatch.setattr(routes, "LiveTimingService", lambda _settings: Collector())
    monkeypatch.setattr(routes, "persisted_live_state", saved)

    async def check() -> None:
        stream = routes.live_timing_events("2026-test", RequestStub(), Settings(app_use_sample_data=True))
        await anext(stream)
        frame = await anext(stream)
        assert '"code": "TST"' in frame
        await stream.aclose()

    asyncio.run(check())


def test_lap_comparison_requires_two_different_drivers() -> None:
    response = client.get("/api/v1/events/2026-singapore/sessions/R/laps?driver_a=16&driver_b=16")
    assert response.status_code == 400


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
    assert event.sessions[0].startsAt == "2026-03-01 15:00"
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


def test_news_collection_time_is_not_shown_as_publication_time() -> None:
    event = EventRepository._normalize({
        "slug": "2026-test", "season": 2026, "round": 1, "short_name": "Test Grand Prix",
        "country": "Testland", "circuit_name": "Test Circuit", "start_at": "2026-03-01T00:00:00Z",
        "sessions": [], "videos": [], "interviews": [], "tyre_allocations": {},
        "event_news": [{
            "id": "33333333-3333-3333-3333-333333333333", "category": "analysis",
            "title": "Undated report", "source_url": "https://example.com/undated",
            "korean_summary": "발행일이 없는 기사", "collected_at": "2026-03-02T09:00:00Z",
            "sources": {"name": "Test Media"},
        }],
    })
    assert event.news[0].publishedAt is None


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
