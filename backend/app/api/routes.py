from datetime import datetime
import time

import httpx
import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.schemas import ChampionshipSnapshot, EventDetail, Health
from app.services.jolpica import JolpicaService, get_jolpica_service
from app.services.repository import EventRepository, get_repository
from app.services.openf1 import OpenF1Service, get_openf1_service
from app.services.live_timing import LiveTimingService, get_live_timing_service
from app.services.live_snapshot_store import get_live_snapshot_store

router = APIRouter()
LOGGER = logging.getLogger(__name__)


async def persisted_live_state(slug: str) -> dict[str, Any] | None:
    try:
        return await get_live_snapshot_store().latest(slug)
    except Exception:
        LOGGER.warning("Saved live timing state unavailable for %s", slug, exc_info=True)
        return None


@router.get("/health", response_model=Health)
def health(settings: Settings = Depends(get_settings)) -> Health:
    mode = "supabase" if settings.supabase_configured and not settings.app_use_sample_data else "jolpica"
    return Health(mode=mode, supabaseConfigured=settings.supabase_configured)


@router.get("/news/latest")
def latest_news(limit: int = Query(40, ge=1, le=100), repository: EventRepository = Depends(get_repository)) -> list[dict[str, object]]:
    return repository.latest_news(limit)


@router.get("/standings/{season}/{round_number}", response_model=ChampionshipSnapshot)
async def get_standings(
    season: int,
    round_number: int,
    jolpica: JolpicaService = Depends(get_jolpica_service),
) -> ChampionshipSnapshot:
    if round_number < 1:
        raise HTTPException(status_code=400, detail="Round must be at least 1")
    try:
        return await jolpica.championship(season, round_number)
    except (httpx.HTTPError, KeyError, ValueError, IndexError) as error:
        raise HTTPException(status_code=502, detail="Championship standings unavailable") from error


@router.get("/events")
async def list_events(
    repository: EventRepository = Depends(get_repository),
    jolpica: JolpicaService = Depends(get_jolpica_service),
    openf1: OpenF1Service = Depends(get_openf1_service),
) -> list[dict[str, object]]:
    try:
        calendar = await jolpica.list_events(datetime.now().year)
        reviewed = repository.list_events()
        merged = {(int(event["season"]), int(event["round"])): event for event in calendar}
        merged.update({(int(event["season"]), int(event["round"])): event for event in reviewed})
        return sorted(merged.values(), key=lambda event: (int(event["season"]), int(event["round"])))
    except (httpx.HTTPError, KeyError, ValueError):
        try:
            return await openf1.list_events(datetime.now().year)
        except (httpx.HTTPError, KeyError, ValueError):
            return repository.list_events()


@router.get("/events/featured", response_model=EventDetail)
async def get_featured_event(
    repository: EventRepository = Depends(get_repository),
    jolpica: JolpicaService = Depends(get_jolpica_service),
    openf1: OpenF1Service = Depends(get_openf1_service),
) -> EventDetail:
    try:
        events = await list_events(repository, jolpica, openf1)
        now = datetime.now().astimezone()
        opened = [event for event in events if event.get("mediaOpenAt") and datetime.fromisoformat(str(event["mediaOpenAt"])) <= now]
        selected = opened[-1] if opened else events[0]
        return await get_event(str(selected["slug"]), repository, jolpica, openf1)
    except (httpx.HTTPError, KeyError, ValueError, IndexError, HTTPException):
        try:
            event = await jolpica.featured_event(datetime.now().year)
            return repository.enrich_event(event)
        except (httpx.HTTPError, KeyError, ValueError, IndexError):
            event = await openf1.featured_event(datetime.now().year)
            return repository.enrich_event(event)


@router.get("/events/{slug}", response_model=EventDetail)
async def get_event(
    slug: str,
    repository: EventRepository = Depends(get_repository),
    jolpica: JolpicaService = Depends(get_jolpica_service),
    openf1: OpenF1Service = Depends(get_openf1_service),
) -> EventDetail:
    try:
        return repository.get_event(slug)
    except (HTTPException, httpx.HTTPError):
        pass
    try:
        event = await jolpica.event_by_slug(slug)
        if event is not None:
            return repository.enrich_event(event)
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    try:
        event = await openf1.event_by_slug(slug)
        if event is not None:
            return repository.enrich_event(event)
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    raise HTTPException(status_code=404, detail="Event not found") from None


@router.get("/events/{slug}/videos")
def get_videos(slug: str, repository: EventRepository = Depends(get_repository)) -> list[dict]:
    return [video.model_dump() for video in repository.get_event(slug).videos]


@router.get("/events/{slug}/interviews")
def get_interviews(slug: str, repository: EventRepository = Depends(get_repository)) -> list[dict[str, object]]:
    event = repository.get_event(slug)
    return [{"event": event.slug, "summary": summary, "reviewStatus": "sample"} for summary in event.summary]


@router.get("/events/{slug}/race-state")
async def get_race_state(
    slug: str,
    repository: EventRepository = Depends(get_repository),
    jolpica: JolpicaService = Depends(get_jolpica_service),
    openf1: OpenF1Service = Depends(get_openf1_service),
) -> dict[str, object]:
    event = await get_event(slug, repository, jolpica, openf1)
    live = get_live_timing_service().snapshot(slug)
    if live["drivers"]:
        return live
    saved = await persisted_live_state(slug)
    if saved:
        return saved
    live["drivers"] = [driver.model_dump() for driver in event.drivers]
    return live


@router.get("/events/{slug}/sessions/{short_name}/results")
async def get_session_results(
    slug: str,
    short_name: str,
    repository: EventRepository = Depends(get_repository),
    jolpica: JolpicaService = Depends(get_jolpica_service),
    openf1: OpenF1Service = Depends(get_openf1_service),
) -> dict[str, object]:
    event = await get_event(slug, repository, jolpica, openf1)
    if short_name not in {session.shortName for session in event.sessions}:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        result = await openf1.session_data(event, short_name)
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(status_code=502, detail="Session results unavailable") from None
    if result is None:
        raise HTTPException(status_code=404, detail="OpenF1 meeting not found")
    return result


@router.get("/events/{slug}/sessions/{short_name}/laps")
async def get_session_laps(
    slug: str,
    short_name: str,
    driver_a: int,
    driver_b: int,
    repository: EventRepository = Depends(get_repository),
    jolpica: JolpicaService = Depends(get_jolpica_service),
    openf1: OpenF1Service = Depends(get_openf1_service),
) -> dict[str, object]:
    if driver_a < 1 or driver_b < 1 or driver_a == driver_b:
        raise HTTPException(status_code=400, detail="Choose two different drivers")
    event = await get_event(slug, repository, jolpica, openf1)
    if short_name not in {session.shortName for session in event.sessions}:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        result = await openf1.session_laps(event, short_name, driver_a, driver_b)
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(status_code=502, detail="Lap records unavailable") from None
    if result is None:
        raise HTTPException(status_code=404, detail="OpenF1 meeting not found")
    return result


async def live_timing_events(
    slug: str,
    request: Request,
    settings: Settings,
    *,
    max_duration_seconds: float = 240,
    interval_seconds: float = 2,
):
    collector = LiveTimingService(settings)
    collector.start()
    started = time.monotonic()
    last_saved_check = 0.0
    saved: dict[str, Any] | None = None
    try:
        yield "retry: 1000\n\n"
        while time.monotonic() - started < max_duration_seconds and not await request.is_disconnected():
            payload = collector.snapshot(slug)
            if not payload["drivers"]:
                if time.monotonic() - last_saved_check >= 10:
                    saved = await persisted_live_state(slug)
                    last_saved_check = time.monotonic()
                if saved:
                    payload = saved
            yield f"event: timing\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(interval_seconds)
    finally:
        await collector.stop()


@router.get("/events/{slug}/live-stream")
async def get_live_stream(slug: str, request: Request, settings: Settings = Depends(get_settings)) -> StreamingResponse:
    return StreamingResponse(
        live_timing_events(slug, request, settings),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/team-radio/transcript")
async def get_team_radio_transcript(path: str, sessionPath: str) -> dict[str, Any]:
    try:
        return await get_live_timing_service().transcribe_team_radio(path, sessionPath)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Team radio transcription unavailable") from error


@router.get("/team-radio/transcripts")
async def get_team_radio_transcripts(sessionPath: str) -> list[dict[str, Any]]:
    try:
        return await get_live_timing_service().saved_team_radio_transcripts(sessionPath)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
