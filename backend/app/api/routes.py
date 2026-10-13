from datetime import datetime

import httpx
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.schemas import ChampionshipSnapshot, EventDetail, Health
from app.services.jolpica import JolpicaService, get_jolpica_service
from app.services.repository import EventRepository, get_repository
from app.services.openf1 import OpenF1Service, get_openf1_service
from app.services.live_timing import get_live_timing_service

router = APIRouter()


@router.get("/health", response_model=Health)
def health(settings: Settings = Depends(get_settings)) -> Health:
    mode = "supabase" if settings.supabase_configured and not settings.app_use_sample_data else "jolpica"
    return Health(mode=mode, supabaseConfigured=settings.supabase_configured)


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
    live["drivers"] = [driver.model_dump() for driver in event.drivers]
    return live


@router.get("/events/{slug}/live-stream")
async def get_live_stream(slug: str, request: Request) -> StreamingResponse:
    async def events():
        while not await request.is_disconnected():
            payload = get_live_timing_service().snapshot(slug)
            yield f"event: timing\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/team-radio/transcript")
async def get_team_radio_transcript(path: str, sessionPath: str) -> dict[str, str | None]:
    try:
        return await get_live_timing_service().transcribe_team_radio(path, sessionPath)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Team radio transcription unavailable") from error


@router.get("/team-radio/transcripts")
async def get_team_radio_transcripts(sessionPath: str) -> list[dict[str, str | None]]:
    try:
        return await get_live_timing_service().saved_team_radio_transcripts(sessionPath)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
