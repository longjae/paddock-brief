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
from app.services.content_collector import Formula1ContentCollector, OpenAISummarizer, active_events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect and summarize official Formula 1 weekend content.")
    parser.add_argument("--event-slug", help="Collect one event even when it is outside the active window.")
    parser.add_argument("--force", action="store_true", help="Collect every configured event.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and summarize without writing to Supabase.")
    parser.add_argument("--discovery-only", action="store_true", help="Only verify source discovery; does not call OpenAI or write.")
    parser.add_argument("--pending", action="store_true", help="Store successful summaries as pending instead of approved.")
    parser.add_argument("--max-articles", type=int, default=20)
    parser.add_argument("--refresh-existing", action="store_true", help="Regenerate existing article and video summaries with the current prompt.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings()
    missing = [
        name
        for name, value in {
            "SUPABASE_URL": settings.supabase_url,
            "SUPABASE_SECRET_KEY": settings.supabase_secret_key or (settings.supabase_publishable_key if args.discovery_only else None),
            "OPENAI_API_KEY": settings.openai_api_key or ("not-required" if args.discovery_only else None),
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
        transcript_api_key=settings.transcript_api_key,
    )
    events = list(active_events(database, datetime.now(timezone.utc), args.event_slug, args.force))
    if not events:
        print(json.dumps({"ok": True, "status": "skipped", "reason": "No active race weekend"}, ensure_ascii=False))
        return 0

    results = []
    for event in events:
        started_at = datetime.now(timezone.utc)
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
    payload = {"ok": not any(result.failed for result in results), "results": [asdict(result) for result in results]}
    print(json.dumps(payload, ensure_ascii=False, default=str))
    return 1 if any(result.failed for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
