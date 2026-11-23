import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.services.repository import EventRepository
from app.services.content_collector import Formula1ContentCollector, TEAM_EDITORIAL_SOURCES, discover_team_article_urls, SourceDocument, team_article_is_current
from app.services.collection_health import source_health
from app.services.live_timing import radio_speaker_segments, LiveTimingService
from app.core.config import Settings
from scripts.run_github_live_worker import dispatch_cycle, scheduled_session
from scripts.install_macos_live_worker import agent_config
from app.services.openf1_telemetry import OpenF1Telemetry, session_matches, fresh_rows

NOW = datetime(2026, 11, 27, 14, 10, tzinfo=UTC)
EVENT = {"slug": "2026-qatar", "sessions": [{"name": "Practice 1", "shortName": "FP1", "startsAt": "2026-11-27 23:00"}]}


def test_github_worker_uses_session_window_dedup_and_restart_cooldown():
    async def check():
        command = AsyncMock(return_value=[])
        metadata = {}
        await dispatch_cycle(EVENT, NOW, metadata, command)
        assert command.await_count == 2
        assert metadata["workflowStatus"] == "dispatched"
        await dispatch_cycle(EVENT, NOW + timedelta(seconds=60), metadata, command)
        assert command.await_count == 3  # list only, no repeated dispatch
        assert "snapshotsSaved" not in metadata
        command.reset_mock()
        command.return_value = [{"databaseId": 5, "status": "queued"}]
        await dispatch_cycle(EVENT, NOW, {}, command)
        assert command.await_count == 1
        command.reset_mock()
        await dispatch_cycle(EVENT, NOW - timedelta(hours=3), {}, command)
        command.assert_not_awaited()
    asyncio.run(check())


def test_github_worker_check_only_never_dispatches():
    command = AsyncMock(return_value=[])
    state = {}
    asyncio.run(dispatch_cycle(EVENT, NOW, state, command, allow_dispatch=False))
    assert state["workflowStatus"] == "ready-to-dispatch"
    assert command.await_count == 1
    config = agent_config(Path('/project/backend'), Path('/support'), Path('/logs'), '/opt/homebrew/bin/gh')
    assert 'run_github_live_worker.py' in ' '.join(config['ProgramArguments'])
    assert '.env.live-worker' not in ' '.join(config['ProgramArguments'])


def test_optional_invalid_rows_do_not_remove_other_content():
    row = {"slug": "2026-test", "season": 2026, "round": 1, "short_name": "Test GP", "country": "Testland", "circuit_name": "Test Circuit", "start_at": "2026-03-01T00:00:00Z",
           "videos": [{"id": "good", "category": "interview", "title": "Valid interview", "source_url": "https://example.com/good"}, {"id": "bad", "category": "interview", "title": None, "source_url": "https://example.com/bad"}],
           "interviews": [{"korean_summary": "정상 인터뷰"}], "team_content": [{"id": "broken"}], "sessions": [None]}
    event = EventRepository._normalize(row)
    assert len(event.videos) == 1 and event.summary == ["정상 인터뷰"]
    assert len(event.dataWarnings) == 3
    assert event.slug == '2026-test'
    assert 'example.com' not in ' '.join(event.dataWarnings)


def test_sitemap_discovery_is_host_scoped_and_has_eleven_unique_teams():
    assert len({source.team_code for source in TEAM_EDITORIAL_SOURCES}) == 11
    source = next(source for source in TEAM_EDITORIAL_SOURCES if source.team_code == 'williams')
    xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://www.williamsf1.com/articles/id/las-vegas-2026</loc></url><url><loc>https://evil.example/articles/id/leak</loc></url></urlset>'
    assert discover_team_article_urls(xml, source) == {'https://williamsf1.com/articles/id/las-vegas-2026'}
    status = source_health([{'code': source.code, 'status': 'blocked', 'team': 'private secret', 'errors': ['secret'], 'discovered': 0}])
    assert status[0]['team'] == 'Williams'
    assert 'secret' not in str(status)


def test_archived_team_story_is_not_assigned_to_current_gp():
    event = {'start_at': '2026-11-20T00:00:00Z', 'end_at': '2026-11-22T08:00:00Z'}
    def article(date): return SourceDocument('https://example.com', 'Preview', published_at=date)
    assert team_article_is_current(article('2026-11-19T12:00:00Z'), event)
    assert not team_article_is_current(article('2025-11-19T12:00:00Z'), event)
    assert not team_article_is_current(article(None), event)


def test_blocked_caption_cooldown_skips_transcription_and_summary():
    db = Mock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": "blocked", "external_id": "abcdefghijk", "transcript_retry_after": (datetime.now(UTC) + timedelta(hours=10)).isoformat()}]
    collector = Formula1ContentCollector(db, Mock(), 'test')
    collector.fetch_youtube_transcript_with_fallback = Mock()
    result = collector.summarize_youtube_videos({'id': 'event'}, [], [])
    assert result == (0, 0, [])
    collector.fetch_youtube_transcript_with_fallback.assert_not_called()
    collector.summarizer.summarize.assert_not_called()


def test_radio_segments_are_sorted_and_invalid_times_are_removed():
    segments = radio_speaker_segments({'segments': [{'start': 5, 'end': 6, 'speaker': 'B', 'text': 'Reply'}, {'start': 1, 'end': 4, 'speaker': 'A', 'text': 'Question'}, {'start': float('nan'), 'end': 10, 'text': 'bad'}]})
    assert [segment['speaker'] for segment in segments] == ['A', 'B']


def test_openf1_telemetry_rejects_wrong_session_stale_samples_and_handles_utc_date():
    info = {'Name': 'Race', 'Path': '2026/2026-11-21_Race/', 'Meeting': {'Location': 'Las Vegas'}}
    session = {'session_key': 7, 'session_name': 'Race', 'location': 'Las Vegas', 'date_start': '2026-11-22T04:00:00Z', 'date_end': '2026-11-22T07:00:00Z', 'gmt_offset': '-08:00:00'}
    now = datetime(2026, 11, 22, 5, tzinfo=UTC)
    assert session_matches(session, info, now)
    assert not session_matches({**session, 'location': 'Miami'}, info, now)
    assert not session_matches(session, {**info, 'Name': 'Practice 1'}, now)
    assert not session_matches(session, info, now + timedelta(days=1))
    assert len(fresh_rows([{'date': now.isoformat()}, {'date': (now - timedelta(minutes=2)).isoformat()}], now)) == 1


def test_authorized_telemetry_maps_real_fields_without_inventing_samples():
    async def check():
        provider = OpenF1Telemetry('server-secret')
        now = datetime(2026, 11, 27, 14, 10, tzinfo=UTC)
        session = {'session_key': 7, 'session_name': 'Practice 1', 'location': 'Lusail', 'date_start': '2026-11-27T14:00:00Z', 'date_end': '2026-11-27T15:00:00Z', 'gmt_offset': '+03:00:00'}
        provider.api._get = AsyncMock(side_effect=[[session], [{'driver_number': 16, 'date': now.isoformat(), 'x': 12, 'y': 24}], [{'driver_number': 16, 'date': now.isoformat(), 'speed': 300, 'rpm': 11000, 'n_gear': 8, 'throttle': 99, 'brake': 0}]])
        data = await provider.sample({'Name': 'Practice 1', 'Path': '2026/2026-11-27_Practice_1/', 'Meeting': {'Location': 'Lusail'}}, now)
        service = LiveTimingService(Settings(app_use_sample_data=True))
        service._capture_track('Position.z', data[0])
        service._capture_track('CarData.z', data[1])
        assert service.track_positions['16']['x'] == 12
        assert service.track_car_data['16']['speed'] == 300
        assert service.track_car_data['16']['gear'] == 8
    asyncio.run(check())


def test_sitemap_articles_rank_by_lastmod_before_random_article_id():
    from app.services.content_collector import rank_team_article_urls
    source = next(item for item in TEAM_EDITORIAL_SOURCES if item.team_code == "williams")
    page = '<urlset><url><loc>https://www.williamsf1.com/articles/zzz/old</loc><lastmod>2020-01-01</lastmod></url><url><loc>https://www.williamsf1.com/articles/aaa/new</loc><lastmod>2026-11-23</lastmod></url></urlset>'
    assert rank_team_article_urls(page, source)[0].endswith('/aaa/new')

@pytest.mark.parametrize('size', [0, 24 * 1024 * 1024 + 1])
def test_radio_empty_or_oversized_audio_never_reaches_transcription(monkeypatch, size):
    import app.services.live_timing as module
    real_client = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, content=b'x' * size)
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    service = LiveTimingService(Settings(openai_api_key='test-key', app_use_sample_data=False))
    async def check():
        with pytest.raises(ValueError, match='empty or exceeds'):
            await service.transcribe_team_radio('TeamRadio/TEST.mp3', '2026/test/Race/')
    asyncio.run(check())
    assert calls == ['GET']


def test_openf1_token_is_only_sent_as_authorization_header(monkeypatch):
    from app.services.openf1 import OpenF1Service
    import app.services.openf1 as module
    real_client = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=[])
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    asyncio.run(OpenF1Service('test-token')._get('location', session_key=1))
    assert calls[0].headers['Authorization'] == 'Bearer test-token'
    assert 'test-token' not in str(calls[0].url)
