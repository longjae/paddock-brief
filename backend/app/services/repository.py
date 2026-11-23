from functools import lru_cache

from pydantic import ValidationError

from fastapi import HTTPException
from supabase import Client, create_client

from app.core.config import Settings, get_settings
from app.schemas import EventDetail, DriverState
from app.services.media_window import media_window
from app.services.sample_data import DEMO_EVENT
from app.services.time_format import format_kst_date_range, format_kst_datetime


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
            .maybe_single()
            .execute()
        )
        if response is None or not response.data:
            raise HTTPException(status_code=404, detail="Event not found")
        return self._normalize(response.data)

    def latest_news(self, limit: int = 40) -> list[dict[str, object]]:
        if self.client is None:
            return []
        rows = (
            self.client.table("general_news")
            .select("id,category,title,source_url,korean_summary,korean_detail,author,tags,team_codes,driver_codes,published_at,sources(name)")
            .eq("review_status", "approved")
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return [
            {
                "id": str(row["id"]),
                "outlet": (row.get("sources") or {}).get("name", "Media"),
                "category": row["category"],
                "title": row["title"],
                "url": row["source_url"],
                "summary": row["korean_summary"],
                "detailedSummary": row["korean_detail"],
                "author": row.get("author"),
                "tags": row.get("tags") or [],
                "teamCodes": row.get("team_codes") or [],
                "driverCodes": row.get("driver_codes") or [],
                "publishedAt": str(row["published_at"]),
                "isPaywalled": False,
            }
            for row in rows
        ]

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
                "dateLabel": format_kst_date_range(row["start_at"], row["end_at"]),
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
        """Keep unrelated editorial content available when one optional record is bad."""
        sections = {"sessions": "sessions", "videos": "videos", "interviews": "summary", "team_content": "teamContent", "event_news": "news", "event_drivers": "eventDrivers"}
        base = {**row, **{name: [] for name in sections}}
        warnings = []
        try:
            event = EventRepository._normalize_unchecked(base)
        except (ValidationError, TypeError, KeyError, ValueError):
            # Allocation is optional; core GP identity must still validate.
            base["tyre_allocations"] = {}
            event = EventRepository._normalize_unchecked(base)
            warnings.append("타이어 배정 정보를 확인하지 못했습니다.")
        labels = {"sessions": "세션", "videos": "영상", "interviews": "인터뷰", "team_content": "팀 콘텐츠", "event_news": "기사", "event_drivers": "선수"}
        for name, target in sections.items():
            entries = row.get(name) or []
            valid, rejected = [], 0
            if not isinstance(entries, list):
                entries, rejected = [], 1
            for item in entries:
                try:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid record")
                    entry = {**item, "race_state_snapshots": []} if name == "sessions" else item
                    candidate = EventRepository._normalize_unchecked({**base, name: [entry]})
                    valid.extend(getattr(candidate, target))
                except (ValidationError, KeyError, TypeError, ValueError, AttributeError):
                    rejected += 1
            if name == "sessions":
                valid.sort(key=lambda session: session.startsAt)
            elif name in {"videos", "team_content", "event_news"}:
                valid.sort(key=lambda item: item.publishedAt or "", reverse=True)
            setattr(event, target, valid)
            if rejected:
                warnings.append(f"{labels[name]} {rejected}건을 확인하지 못했습니다. 다른 자료는 계속 볼 수 있습니다.")
        snapshots = [snapshot for session in row.get("sessions", []) if isinstance(session, dict)
                     for snapshot in (session.get("race_state_snapshots") if isinstance(session.get("race_state_snapshots"), list) else []) if isinstance(snapshot, dict)
                     and isinstance(snapshot.get("state"), dict) and snapshot["state"].get("kind") == "final-classification"] if isinstance(row.get("sessions", []), list) else []
        latest = max(snapshots, key=lambda item: str(item.get("captured_at") or ""), default={})
        drivers = latest.get("state", {}).get("drivers") or []
        rejected = 0
        if not isinstance(drivers, list):
            drivers, rejected = [], 1
        for driver in drivers:
            try:
                event.drivers.append(DriverState.model_validate(driver))
            except ValidationError:
                rejected += 1
        colours = {driver.code: driver.colour for driver in event.eventDrivers}
        for driver in event.drivers:
            if driver.colour == "#888888" and colours.get(driver.code):
                driver.colour = colours[driver.code]
        event.drivers.sort(key=lambda driver: driver.position)
        if rejected:
            warnings.append(f"결과 선수 {rejected}명의 일부 정보를 확인하지 못했습니다.")
        event.dataWarnings = warnings
        return event

    @staticmethod
    def _normalize_unchecked(row: dict) -> EventDetail:
        allocation_value = row.get("tyre_allocations") or {}
        allocation = allocation_value[0] if isinstance(allocation_value, list) and allocation_value else allocation_value
        session_rows = sorted(row.get("sessions") or [], key=lambda item: item["starts_at"])
        sessions = [
            {
                "name": session["name"],
                "shortName": session["short_name"],
                "startsAt": format_kst_datetime(session["starts_at"]),
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
                "youtubeId": video.get("external_id") if video.get("platform") == "youtube" and video.get("is_embeddable") is not False else None,
                "participants": video.get("participants") or [],
                "summary": video.get("korean_summary"),
                "detailedSummary": video.get("korean_detail"),
                "transcriptStatus": video.get("transcript_status") or "pending",
                "transcriptLanguage": video.get("transcript_language"),
                "transcriptRetryAt": video.get("transcript_retry_after"),
                "publishedAt": str(video["published_at"]) if video.get("published_at") else None,
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
            key=lambda item: item.get("published_at") or item.get("collected_at") or "",
            reverse=True,
        )
        news_rows = sorted(
            row.get("event_news") or [],
            key=lambda item: item.get("published_at") or item.get("collected_at") or "",
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
        colours_by_code = {
            (item.get("drivers") or {}).get("code"): (item.get("teams") or {}).get("colour")
            for item in event_driver_rows
        }
        for driver in drivers:
            if driver.get("colour") == "#888888" and colours_by_code.get(driver.get("code")):
                driver["colour"] = colours_by_code[driver["code"]]
        return EventDetail.model_validate(
            {
                "slug": row["slug"],
                "season": row["season"],
                "round": row["round"],
                "name": row["short_name"],
                "country": row["country"],
                "circuit": row["circuit_name"],
                "trackMapUrl": row.get("track_map_url"),
                "dateLabel": format_kst_date_range(row["start_at"], row.get("end_at") or row["start_at"]),
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
                        "publishedAt": str(item.get("published_at") or item.get("collected_at")) if item.get("published_at") or item.get("collected_at") else None,
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
