from functools import lru_cache

from fastapi import HTTPException
from supabase import Client, create_client

from app.core.config import Settings, get_settings
from app.schemas import EventDetail
from app.services.media_window import media_window
from app.services.sample_data import DEMO_EVENT


class EventRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Client | None = None
        if settings.supabase_configured and not settings.app_use_sample_data:
            self.client = create_client(settings.supabase_url or "", settings.supabase_key or "")

    def get_event(self, slug: str) -> EventDetail:
        if self.client is None:
            if slug != DEMO_EVENT["slug"]:
                raise HTTPException(status_code=404, detail="Event not found")
            return EventDetail.model_validate(DEMO_EVENT)

        response = (
            self.client.table("events")
            .select("*, sessions(*, race_state_snapshots(*)), videos(*, sources(name)), interviews(*), tyre_allocations(*), team_content(*, teams(code,name,colour,sort_order), sources(name)), event_news(*, sources(name)), event_drivers(*, drivers(*), teams(code,name,colour,sort_order))")
            .eq("slug", slug)
            .single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Event not found")
        return self._normalize(response.data)

    def list_events(self) -> list[dict[str, object]]:
        if self.client is None:
            return [{key: DEMO_EVENT[key] for key in ("slug", "season", "round", "name", "country", "circuit", "dateLabel", "mediaOpenAt", "mediaOpenLabel")}]
        response = self.client.table("events").select("slug, season, round, short_name, country, circuit_name, start_at, end_at").order("round").execute()
        return [
            {
                "slug": row["slug"],
                "season": row["season"],
                "round": row["round"],
                "name": row["short_name"],
                "country": row["country"],
                "circuit": row["circuit_name"],
                "dateLabel": str(row["start_at"]),
                **media_window(str(row["end_at"]), "+09:00:00"),
            }
            for row in response.data
        ]

    def enrich_event(self, event: EventDetail) -> EventDetail:
        """Overlay reviewed Supabase editorial content on live OpenF1 data."""
        if self.client is None:
            return event
        try:
            stored = self.get_event(event.slug)
        except Exception:
            return event
        event.videos = stored.videos
        event.name = stored.name
        event.country = stored.country
        event.circuit = stored.circuit
        event.trackMapUrl = stored.trackMapUrl or event.trackMapUrl
        event.tyreAllocation = stored.tyreAllocation
        event.tyreSourceUrl = stored.tyreSourceUrl
        event.summary = stored.summary
        event.drivers = stored.drivers
        event.teamContent = stored.teamContent
        event.news = stored.news
        event.eventDrivers = stored.eventDrivers
        return event

    @staticmethod
    def _normalize(row: dict) -> EventDetail:
        allocation_value = row.get("tyre_allocations") or {}
        allocation = allocation_value[0] if isinstance(allocation_value, list) and allocation_value else allocation_value
        session_rows = sorted(row.get("sessions") or [], key=lambda item: item["starts_at"])
        sessions = [
            {
                "name": session["name"],
                "shortName": session["short_name"],
                "startsAt": str(session["starts_at"]),
                "status": session["status"],
            }
            for session in session_rows
        ]
        snapshots = [
            snapshot
            for session in session_rows
            for snapshot in session.get("race_state_snapshots") or []
            if (snapshot.get("state") or {}).get("kind") == "final-classification"
        ]
        latest_snapshot = max(snapshots, key=lambda item: item["captured_at"], default=None)
        drivers = (latest_snapshot or {}).get("state", {}).get("drivers", [])
        video_rows = sorted(
            row.get("videos") or [],
            key=lambda item: item.get("published_at") or item.get("collected_at") or "",
            reverse=True,
        )
        videos = [
            {
                "id": str(video["id"]),
                "category": video["category"],
                "title": video["title"],
                "source": (video.get("sources") or {}).get("name", video.get("channel_name", "Official")),
                "duration": video.get("duration_label") or "—",
                "url": video["source_url"],
                "youtubeId": video.get("external_id") if video.get("platform") == "youtube" else None,
                "participants": video.get("participants") or [],
                "summary": video.get("korean_summary"),
                "detailedSummary": video.get("korean_detail"),
                "transcriptStatus": video.get("transcript_status") or "pending",
                "transcriptLanguage": video.get("transcript_language"),
            }
            for video in video_rows
        ]
        interview_rows = sorted(
            row.get("interviews") or [],
            key=lambda item: item.get("published_at") or item.get("collected_at") or "",
            reverse=True,
        )
        team_content_rows = sorted(
            row.get("team_content") or [],
            key=lambda item: (
                (item.get("teams") or {}).get("sort_order", 99),
                item.get("published_at") or "",
            ),
        )
        news_rows = sorted(
            row.get("event_news") or [],
            key=lambda item: item.get("published_at") or "",
            reverse=True,
        )
        event_driver_rows = sorted(
            row.get("event_drivers") or [],
            key=lambda item: (
                (item.get("teams") or {}).get("sort_order", 99),
                (item.get("drivers") or {}).get("previous_season_rank") or 999,
                (item.get("drivers") or {}).get("full_name", ""),
            ),
        )
        return EventDetail.model_validate(
            {
                "slug": row["slug"],
                "season": row["season"],
                "round": row["round"],
                "name": row["short_name"],
                "country": row["country"],
                "circuit": row["circuit_name"],
                "trackMapUrl": row.get("track_map_url"),
                "dateLabel": row.get("date_label") or str(row["start_at"]),
                **media_window(str(row.get("end_at") or row["start_at"]), "+09:00:00"),
                "sessions": sessions,
                "videos": videos,
                "tyreAllocation": {
                    "hard": allocation.get("hard_compound", "TBC"),
                    "medium": allocation.get("medium_compound", "TBC"),
                    "soft": allocation.get("soft_compound", "TBC"),
                },
                "tyreSourceUrl": allocation.get("source_url"),
                "summary": [
                    line
                    for item in interview_rows
                    for line in (item.get("korean_summary") or "").splitlines()
                    if line.strip()
                ],
                "drivers": drivers,
                "teamContent": [
                    {
                        "id": str(item["id"]),
                        "team": (item.get("teams") or {}).get("name", "Other"),
                        "teamCode": (item.get("teams") or {}).get("code", "other"),
                        "colour": (item.get("teams") or {}).get("colour", "#888888"),
                        "source": (item.get("sources") or {}).get("name", "Source"),
                        "category": item["content_kind"],
                        "title": item["title"],
                        "url": item["source_url"],
                        "summary": item["korean_summary"],
                        "detailedSummary": item.get("korean_detail") or item["korean_summary"],
                        "participants": item.get("participants") or [],
                        "publishedAt": str(item["published_at"]) if item.get("published_at") else None,
                        "contentType": item["content_kind"],
                    }
                    for item in team_content_rows
                ],
                "news": [
                    {
                        "id": str(item["id"]),
                        "outlet": (item.get("sources") or {}).get("name", "Media"),
                        "category": item["category"],
                        "title": item["title"],
                        "url": item["source_url"],
                        "summary": item["korean_summary"],
                        "detailedSummary": item.get("korean_detail") or item["korean_summary"],
                        "author": item.get("author"),
                        "tags": item.get("tags") or [],
                        "teamCodes": item.get("team_codes") or [],
                        "driverCodes": item.get("driver_codes") or [],
                        "publishedAt": str(item["published_at"]) if item.get("published_at") else None,
                        "isPaywalled": item.get("is_paywalled", False),
                    }
                    for item in news_rows
                ],
                "eventDrivers": [
                    {
                        "id": str(item["id"]),
                        "code": (item.get("drivers") or {}).get("code", ""),
                        "name": (item.get("drivers") or {}).get("full_name", "Unknown"),
                        "number": (item.get("drivers") or {}).get("permanent_number", 0),
                        "nationality": (item.get("drivers") or {}).get("nationality", ""),
                        "profileUrl": (item.get("drivers") or {}).get("profile_url"),
                        "team": (item.get("teams") or {}).get("name", "Unknown"),
                        "teamCode": (item.get("teams") or {}).get("code", "unknown"),
                        "colour": (item.get("teams") or {}).get("colour", "#888888"),
                        "resultPosition": item.get("result_position"),
                        "resultStatus": item.get("result_status", "entered"),
                        "points": float(item.get("points") or 0),
                        "previousSeasonRank": (item.get("drivers") or {}).get("previous_season_rank"),
                    }
                    for item in event_driver_rows
                ],
            }
        )


@lru_cache
def get_repository() -> EventRepository:
    return EventRepository(get_settings())
