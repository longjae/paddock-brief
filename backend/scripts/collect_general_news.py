"""Collect recent F1 articles independently of the race-weekend window."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.collection_health import record_collection_health
from app.services.content_collector import (
    F1_BASE_URL,
    LATEST_CONTENT_URL,
    MEDIA_FEED_SOURCES,
    Formula1ContentCollector,
    OpenAISummarizer,
    canonicalize_web_url,
    discover_article_urls,
    discover_feed_article_urls,
    parse_article,
    parse_external_article,
)


def recent_publication(value: str | None, now: datetime, days: int = 7) -> datetime | None:
    if not value:
        return None
    try:
        published = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if published.tzinfo is None:
            return None
        published = published.astimezone(timezone.utc)
        return published if now - timedelta(days=days) <= published <= now + timedelta(hours=2) else None
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discovery-only", action="store_true")
    parser.add_argument("--max-articles", type=int, default=8)
    args = parser.parse_args()
    settings = Settings()
    if not settings.supabase_url or not settings.supabase_secret_key or (not args.discovery_only and not settings.openai_api_key):
        print(json.dumps({"ok": False, "error": "Required collector credentials are missing"}))
        return 2

    database = create_client(settings.supabase_url, settings.supabase_secret_key)
    collector = Formula1ContentCollector(
        database,
        OpenAISummarizer(settings.openai_api_key or "", settings.openai_summary_model),
        settings.collector_user_agent,
    )
    sources = [("formula1-editorial", "Formula 1", F1_BASE_URL, True)]
    sources += [(source.code, source.name, source.base_url, False) for source in MEDIA_FEED_SOURCES]
    candidates: list[tuple[str, str, str, bool, str]] = []
    errors: list[str] = []
    try:
        candidates += [(sources[0][0], sources[0][1], sources[0][2], True, url) for url in discover_article_urls(collector.fetch(LATEST_CONTENT_URL))]
    except Exception as exc:
        errors.append(f"Formula 1 discovery: {exc}")
    for source in MEDIA_FEED_SOURCES:
        try:
            candidates += [(source.code, source.name, source.base_url, False, url) for url in discover_feed_article_urls(collector.fetch(source.feed_url), source)]
        except Exception as exc:
            errors.append(f"{source.name} discovery: {exc}")

    existing = {
        canonicalize_web_url(row["source_url"], row["source_url"])
        for row in database.table("general_news").select("source_url").order("published_at", desc=True).limit(500).execute().data
    }
    teams = database.table("teams").select("code,name").execute().data if not args.discovery_only else []
    drivers = database.table("drivers").select("code,full_name").execute().data if not args.discovery_only else []
    now = datetime.now(timezone.utc)
    inserted = 0
    fresh = 0
    inserted_by_source: dict[str, int] = {}
    source_limit = max(2, (args.max_articles + len(sources) - 1) // len(sources))
    for code, name, base_url, official, url in candidates:
        if inserted >= args.max_articles:
            break
        if inserted_by_source.get(code, 0) >= source_limit:
            continue
        if canonicalize_web_url(url, base_url) in existing:
            continue
        try:
            document = parse_article(url, collector.fetch(url)) if official else parse_external_article(url, collector.fetch(url), name, base_url)
            published = recent_publication(document.published_at, now)
            if published is None or len(document.body) < 200:
                continue
            fresh += 1
            if args.discovery_only:
                inserted += 1
                inserted_by_source[code] = inserted_by_source.get(code, 0) + 1
                continue
            summary = collector.summarizer.summarize(document, teams, drivers)
            if args.dry_run:
                inserted += 1
                inserted_by_source[code] = inserted_by_source.get(code, 0) + 1
                continue
            source_id = collector.ensure_source(code, name, base_url, "official-editorial" if official else "media", is_official=official)
            database.table("general_news").upsert({
                "source_id": source_id,
                "source_url": document.url,
                "category": summary.category,
                "title": summary.title_ko,
                "korean_summary": summary.summary_ko,
                "korean_detail": summary.detail,
                "author": document.author,
                "tags": summary.tags,
                "team_codes": summary.team_codes,
                "driver_codes": summary.driver_codes,
                "published_at": published.isoformat(),
                "review_status": "approved",
            }, on_conflict="source_url").execute()
            existing.add(document.url)
            inserted += 1
            inserted_by_source[code] = inserted_by_source.get(code, 0) + 1
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    if not args.dry_run and not args.discovery_only:
        record_collection_health(database, "news", "failed" if not candidates else "partial" if errors else "succeeded", processed=inserted, failed=len(errors))
    print(json.dumps({"ok": bool(candidates), "discovered": len(candidates), "fresh": fresh, "inserted": inserted, "errors": errors}, ensure_ascii=False))
    return 0 if candidates else 1


if __name__ == "__main__":
    sys.exit(main())
