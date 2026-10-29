from datetime import UTC, datetime, timedelta

from app.services.collection_health import public_health, record_collection_health


def test_public_health_excludes_errors_and_distinguishes_delay_from_failure() -> None:
    now = datetime(2026, 10, 29, 5, tzinfo=UTC)
    stamp = (now - timedelta(hours=7)).isoformat()
    rows = [{"kind": "news", "status": "succeeded", "finished_at": stamp, "errors": ["private secret"], "processed_count": 2},
            {"kind": "videos", "status": "partial", "finished_at": stamp, "metadata_unverified_count": 2, "pending_count": 3}]
    news, videos, radio = public_health(rows, now)
    assert news["delayed"] and news["status"] == "succeeded"
    assert videos["status"] == "partial" and not videos["delayed"]
    assert (videos["metadataUnverified"], videos["pending"]) == (2, 3)
    assert radio["status"] == "unknown" and radio["finishedAt"] is None
    assert "private secret" not in str([news, videos, radio])


def test_partial_failure_preserves_previous_full_success() -> None:
    saved = []
    class Database:
        def table(self, name): return self
        def select(self, columns): return self
        def eq(self, key, value): return self
        def limit(self, count): return self
        def execute(self): return type("Result", (), {"data": [{"last_success_at": "2026-10-28T00:00:00Z"}]})()
        def upsert(self, payload, **kwargs):
            saved.append(payload)
            return self
    record_collection_health(Database(), "radio", "partial", failed=1, translation_missing=2)
    assert saved[0]["last_success_at"] == "2026-10-28T00:00:00Z"
    assert saved[0]["translation_missing_count"] == 2
    assert "errors" not in saved[0]


def test_status_store_failure_does_not_destroy_successful_content_job() -> None:
    class Database:
        def table(self, name): raise RuntimeError("private details")
    record_collection_health(Database(), "news", "succeeded", processed=3)
