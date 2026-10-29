"""Safe, small public summaries; never expose private collector error bodies."""

from datetime import UTC, datetime
import logging
from typing import Any

LOGGER = logging.getLogger(__name__)
KINDS = ("news", "videos", "radio")


def record_collection_health(database: Any, kind: str, status: str, *, processed: int | None = 0, failed: int = 0, unavailable: int = 0, translation_missing: int = 0, pending: int = 0, metadata_unverified: int = 0, event_slug: str | None = None) -> None:
    if kind not in KINDS or status not in {"succeeded", "partial", "failed", "skipped"}:
        raise ValueError("Invalid collection health category or status")
    now = datetime.now(UTC).isoformat()
    try:
        prior = database.table("collection_health").select("last_success_at").eq("kind", kind).limit(1).execute().data
        previous_success = prior[0].get("last_success_at") if prior else None
        database.table("collection_health").upsert({
            "kind": kind, "event_slug": event_slug, "status": status, "finished_at": now,
            "last_success_at": now if status == "succeeded" else previous_success,
            "processed_count": processed, "failed_count": failed,
            "unavailable_count": unavailable, "translation_missing_count": translation_missing,
            "pending_count": pending, "metadata_unverified_count": metadata_unverified,
        }, on_conflict="kind").execute()
    except Exception as error:
        LOGGER.warning("Collection health write unavailable (%s)", type(error).__name__)


def public_health(rows: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    by_kind = {row["kind"]: row for row in rows if row.get("kind") in KINDS}
    result = []
    for kind in KINDS:
        row = by_kind.get(kind, {})
        age = None
        try:
            stamp = datetime.fromisoformat(str(row.get("finished_at") or "").replace("Z", "+00:00"))
            if stamp.tzinfo:
                age = max(0, int((now - stamp).total_seconds()))
        except ValueError:
            pass
        result.append({
            "kind": kind, "status": row.get("status", "unknown"), "eventSlug": row.get("event_slug"),
            "finishedAt": row.get("finished_at"), "lastSuccessAt": row.get("last_success_at"),
            "processed": row.get("processed_count"), "failed": row.get("failed_count", 0),
            "unavailable": row.get("unavailable_count", 0), "translationMissing": row.get("translation_missing_count", 0),
            "pending": row.get("pending_count", 0), "metadataUnverified": row.get("metadata_unverified_count", 0),
            "ageSeconds": age, "delayed": kind != "videos" and age is not None and age > 6 * 3600 and row.get("status") != "skipped",
        })
    return result
