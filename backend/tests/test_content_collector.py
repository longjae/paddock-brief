from datetime import datetime, timezone

import httpx

from app.services.content_collector import (
    KoreanArticleSummary,
    Formula1ContentCollector,
    TEAM_EDITORIAL_SOURCES,
    canonicalize_url,
    canonicalize_web_url,
    discover_article_urls,
    discover_team_article_urls,
    document_matches_event,
    event_is_active,
    parse_article,
    parse_team_article,
    parse_youtube_subtitle,
    team_document_matches_event,
)


def test_summary_schema_is_strict_and_requires_long_form_content() -> None:
    schema = KoreanArticleSummary.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["SummarySection"]["additionalProperties"] is False
    assert schema["properties"]["summary_ko"]["minLength"] == 180
    assert schema["$defs"]["SummarySection"]["properties"]["body"]["minLength"] == 120


def test_youtube_json3_subtitle_is_flattened_without_timing_metadata() -> None:
    payload = '{"events":[{"tStartMs":1000,"segs":[{"utf8":"Hello "},{"utf8":"paddock"}]},{"segs":[{"utf8":"Next lap"}]}]}'
    assert parse_youtube_subtitle(payload, ".json3") == "Hello paddock Next lap"


def test_youtube_vtt_subtitle_removes_timestamps_and_duplicate_lines() -> None:
    payload = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<c>Box, box</c>\n\n00:00:02.000 --> 00:00:03.000\nBox, box\nPush now"
    assert parse_youtube_subtitle(payload, ".vtt") == "Box, box Push now"


def test_external_transcript_api_is_optional_third_provider() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.params["video_url"] == "SQYus-yb4xE"
        return httpx.Response(200, json={"video_id": "SQYus-yb4xE", "language": "asr-en", "transcript": "Race  strategy   explained"})

    collector = Formula1ContentCollector(
        database=None,  # type: ignore[arg-type]
        summarizer=None,  # type: ignore[arg-type]
        user_agent="test",
        transcript_api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    text, language = collector.fetch_youtube_transcript_from_api("SQYus-yb4xE")
    assert text == "Race strategy explained"
    assert language == "asr-en"


def test_transcript_fallback_reaches_external_provider_after_free_providers_fail(monkeypatch) -> None:
    collector = Formula1ContentCollector(
        database=None,  # type: ignore[arg-type]
        summarizer=None,  # type: ignore[arg-type]
        user_agent="test",
        transcript_api_key="test-key",
    )
    attempts: list[str] = []

    def fail_primary(video_id: str) -> tuple[str, str]:
        attempts.append("youtube-transcript-api")
        raise RuntimeError("blocked")

    def fail_ytdlp(video_id: str) -> tuple[str, str]:
        attempts.append("yt-dlp")
        raise RuntimeError("rate limited")

    def succeed_external(video_id: str) -> tuple[str, str]:
        attempts.append("transcript-api")
        return "Paddock interview transcript", "en"

    monkeypatch.setattr(collector, "fetch_youtube_transcript", fail_primary)
    monkeypatch.setattr(collector, "fetch_youtube_transcript_with_ytdlp", fail_ytdlp)
    monkeypatch.setattr(collector, "fetch_youtube_transcript_from_api", succeed_external)

    assert collector.fetch_youtube_transcript_with_fallback("SQYus-yb4xE") == ("Paddock interview transcript", "en")
    assert attempts == ["youtube-transcript-api", "yt-dlp", "transcript-api"]


def test_discovers_only_formula1_articles_and_videos() -> None:
    page = '''
    <a href="/en/latest/article/race-report.abc?utm_source=x">Report</a>
    <a href="https://www.formula1.com/en/latest/video/interview.xyz">Video</a>
    <a href="/en/drivers/max-verstappen">Driver</a>
    '''
    assert discover_article_urls(page) == {
        "https://www.formula1.com/en/latest/article/race-report.abc",
        "https://www.formula1.com/en/latest/video/interview.xyz",
    }


def test_discovers_only_mclaren_formula1_articles() -> None:
    source = TEAM_EDITORIAL_SOURCES[0]
    page = '''
    <a href="/racing/formula-1/2026/singapore-grand-prix/preview/?utm_source=x">Preview</a>
    <a href="/racing/indycar/2026/indy-500/">IndyCar</a>
    <a href="https://example.com/racing/formula-1/2026/not-official/">External</a>
    '''
    assert discover_team_article_urls(page, source) == {
        "https://mclaren.com/racing/formula-1/2026/singapore-grand-prix/preview"
    }


def test_discovers_mercedes_news_and_reports() -> None:
    source = TEAM_EDITORIAL_SOURCES[1]
    page = '''
    <a href="/news/five-things-about-singapore?source=home">Feature</a>
    <a href="/reports/race-report-singapore">Report</a>
    <a href="/races/singapore-grand-prix-2026">Race hub</a>
    '''
    assert discover_team_article_urls(page, source) == {
        "https://mercedesamgf1.com/news/five-things-about-singapore",
        "https://mercedesamgf1.com/reports/race-report-singapore",
    }


def test_parses_team_article_without_rewriting_its_domain() -> None:
    source = TEAM_EDITORIAL_SOURCES[1]
    page = '''
    <meta property="og:title" content="Singapore race preview" />
    <meta property="article:published_time" content="2026-10-08T10:00:00Z" />
    <main><p>George Russell and Kimi Antonelli prepare for the Singapore Grand Prix.</p></main>
    '''
    article = parse_team_article("https://www.mercedesamgf1.com/news/singapore?x=1", page, source)
    assert article.url == "https://mercedesamgf1.com/news/singapore"
    assert article.author == "Mercedes-AMG PETRONAS F1 Team"
    assert canonicalize_web_url(article.url + "?x=1", source.base_url) == article.url


def test_parses_metadata_and_article_paragraphs() -> None:
    page = '''
    <html><head>
      <meta property="og:title" content="Drivers react to Sepang" />
      <meta name="description" content="The Malaysian Grand Prix reaction." />
      <meta property="article:published_time" content="2026-10-04T12:00:00Z" />
    </head><body><nav><p>This navigation paragraph must be ignored completely.</p></nav>
      <main><h2>Opening reactions from the paddock</h2>
      <p>Max Verstappen and his rivals discussed a difficult race at Sepang.</p></main>
    </body></html>
    '''
    article = parse_article("https://formula1.com/en/latest/article/test.abc", page)
    assert article.title == "Drivers react to Sepang"
    assert article.published_at == "2026-10-04T12:00:00Z"
    assert "Opening reactions" in article.body
    assert "navigation" not in article.body


def test_event_window_opens_on_thursday_and_closes_monday() -> None:
    event = {"start_at": "2026-10-09T08:30:00Z", "end_at": "2026-10-11T14:00:00Z", "timezone": "Asia/Singapore"}
    assert event_is_active(event, datetime(2026, 10, 7, 16, tzinfo=timezone.utc))  # Thursday 00:00 local
    assert event_is_active(event, datetime(2026, 10, 12, 15, 59, tzinfo=timezone.utc))
    assert not event_is_active(event, datetime(2026, 10, 7, 15, 59, tzinfo=timezone.utc))
    assert not event_is_active(event, datetime(2026, 10, 12, 16, 1, tzinfo=timezone.utc))


def test_matches_sepang_aliases() -> None:
    document = parse_article(
        "https://www.formula1.com/en/latest/article/test.abc",
        '<meta property="og:title" content="Qualifying at Sepang"><p>The Malaysian Grand Prix weekend continued in heavy rain.</p>',
    )
    event = {"country": "Malaysia", "locality": "Kuala Lumpur", "circuit_name": "Sepang International Circuit", "short_name": "Bahrain Grand Prix in Malaysia"}
    assert document_matches_event(document, event)
    assert canonicalize_url(document.url + "?x=1") == document.url


def test_team_article_does_not_match_only_because_body_mentions_next_race() -> None:
    source = TEAM_EDITORIAL_SOURCES[0]
    document = parse_team_article(
        "https://www.mclaren.com/racing/formula-1/2026/bahrain-grand-prix/race-report/",
        '''
        <meta property="og:title" content="2026 Bahrain Grand Prix in Malaysia race report" />
        <meta name="description" content="Our report from Sepang." />
        <p>The team now turns its attention to next week's Singapore Grand Prix.</p>
        ''',
        source,
    )
    singapore = {
        "country": "Singapore",
        "locality": "Singapore",
        "circuit_name": "Marina Bay Street Circuit",
        "short_name": "Singapore Grand Prix",
    }
    assert document_matches_event(document, singapore)
    assert not team_document_matches_event(document, singapore)
