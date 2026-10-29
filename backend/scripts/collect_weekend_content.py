from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.content_collector import Formula1ContentCollector, OpenAISummarizer, CollectionResult, active_events
from app.services.calendar_registry import register_missing_active_events
from app.services.collection_health import record_collection_health


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect and summarize official Formula 1 weekend content.")
    parser.add_argument("--event-slug", help="Collect one event even when it is outside the active window.")
    parser.add_argument("--force", action="store_true", help="Collect every configured event.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and summarize without writing to Supabase.")
    parser.add_argument("--discovery-only", action="store_true", help="Only verify source discovery; does not call OpenAI or write.")
    parser.add_argument("--videos-only", action="store_true", help="Collect official video metadata without articles, transcription, or AI summaries.")
    parser.add_argument("--pending", action="store_true", help="Store successful summaries as pending instead of approved.")
    parser.add_argument("--max-articles", type=int, default=20)
    parser.add_argument("--refresh-existing", action="store_true", help="Regenerate existing article and video summaries with the current prompt.")
    args = parser.parse_args()
    if args.videos_only and args.discovery_only:
        parser.error("Choose either --videos-only or --discovery-only")
    return args


def main() -> int:
    args = parse_args()
    settings = Settings()
    missing = [
        name
        for name, value in {
            "SUPABASE_URL": settings.supabase_url,
            "SUPABASE_SECRET_KEY": settings.supabase_secret_key or (settings.supabase_publishable_key if args.discovery_only else None),
            "OPENAI_API_KEY": settings.openai_api_key or ("not-required" if args.discovery_only or args.videos_only else None),
        }.items()
        if not value
    ]
    if missing:
        print(json.dumps({"ok": False, "error": f"Missing environment variables: {', '.join(missing)}"}))
        return 2

    database = create_client(settings.supabase_url or "", settings.supabase_secret_key or settings.supabase_publishable_key or "")
    collector = Formula1ContentCollector(
        database=database,
        summarizer=OpenAISummarizer(settings.openai_api_key or "", settings.openai_summary_model),
        user_agent=settings.collector_user_agent,
        youtube_api_key=settings.youtube_api_key,
        transcript_api_key=settings.transcript_api_key,
    )
    events = list(active_events(database, datetime.now(timezone.utc), args.event_slug, args.force))
    if not events and not args.dry_run and not args.discovery_only:
        registered = register_missing_active_events(database, datetime.now(timezone.utc), args.event_slug)
        if registered:
            print(json.dumps({"registered_events": registered}))
            events = list(active_events(database, datetime.now(timezone.utc), args.event_slug, args.force))
    if not events:
        print(json.dumps({"ok": True, "status": "skipped", "reason": "No active race weekend"}, ensure_ascii=False))
        return 0

    results = []
    for event in events:
        started_at = datetime.now(timezone.utc)
        if args.videos_only:
            inserted, failed, errors = collector.collect_youtube_videos(
                event, database.table("drivers").select("code,full_name").execute().data,
                dry_run=args.dry_run, review_status="pending" if args.pending else "approved",
            )
            result = CollectionResult(event_slug=event["slug"], inserted=inserted, failed=failed, errors=errors)
        else:
            result = collector.collect_event(
                event,
                dry_run=args.dry_run,
                review_status="pending" if args.pending else "approved",
                max_articles=args.max_articles,
                discovery_only=args.discovery_only,
                refresh_existing=args.refresh_existing,
            )
        results.append(result)
        if not args.discovery_only and not args.dry_run:
            video_errors = sum(error.startswith(("youtube", "video")) for error in result.errors)
            videos = database.table("videos").select("transcript_status,is_embeddable,published_at").eq("event_id", event["id"]).execute().data or []
            metadata_unverified = sum(row.get("is_embeddable") is False and not row.get("published_at") for row in videos)
            unavailable = sum(row.get("transcript_status") == "unavailable" for row in videos)
            summary_failed = any(row.get("transcript_status") == "failed" for row in videos)
            video_status = "failed" if video_errors and not videos else "partial" if video_errors or metadata_unverified or unavailable or summary_failed else "succeeded"
            record_collection_health(database, "videos", video_status, processed=result.inserted if args.videos_only else None, failed=video_errors, pending=sum(row.get("transcript_status") in {"pending", "failed"} for row in videos), unavailable=unavailable, metadata_unverified=metadata_unverified, event_slug=event["slug"])
            status = "succeeded" if result.failed == 0 else ("partial" if result.inserted else "failed")
            database.table("content_collection_runs").insert(
                {
                    "event_id": event["id"],
                    "event_slug": event["slug"],
                    "started_at": started_at.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "status": status,
                    "discovered_count": result.discovered,
                    "relevant_count": result.relevant,
                    "inserted_count": result.inserted,
                    "skipped_count": result.skipped,
                    "failed_count": result.failed,
                    "errors": result.errors,
                    "dry_run": args.dry_run,
                }
            ).execute()
    total_failure = bool(results) and all(
        result.failed > 0 and result.inserted == 0 and result.updated == 0
        for result in results
    )
    payload = {"ok": not total_failure, "results": [asdict(result) for result in results]}
    print(json.dumps(payload, ensure_ascii=False, default=str))
    return 1 if total_failure else 0


if __name__ == "__main__":
    sys.exit(main())
