"""Register missing collection targets from the public race calendar."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from app.services.jolpica import JolpicaService, _parse_datetime, _session_payload, _slug
from app.services.content_collector import event_is_active


COUNTRY_ZONES = {"Australia": "Australia/Melbourne", "China": "Asia/Shanghai", "Japan": "Asia/Tokyo", "USA": "America/New_York", "United States": "America/New_York", "Canada": "America/Toronto", "Monaco": "Europe/Monaco", "Spain": "Europe/Madrid", "Austria": "Europe/Vienna", "UK": "Europe/London", "United Kingdom": "Europe/London", "Belgium": "Europe/Brussels", "Hungary": "Europe/Budapest", "Netherlands": "Europe/Amsterdam", "Italy": "Europe/Rome", "Azerbaijan": "Asia/Baku", "Bahrain": "Asia/Bahrain", "Malaysia": "Asia/Kuala_Lumpur", "Singapore": "Asia/Singapore", "Mexico": "America/Mexico_City", "Brazil": "America/Sao_Paulo", "Qatar": "Asia/Qatar", "UAE": "Asia/Dubai", "Saudi Arabia": "Asia/Riyadh"}


def calendar_registration(race: dict[str, Any], now: datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    location = race["Circuit"]["Location"]
    circuit_id = race["Circuit"]["circuitId"]
    zone = {"americas": "America/Chicago", "vegas": "America/Los_Angeles"}.get(circuit_id, COUNTRY_ZONES.get(location["country"], "UTC"))
    race_start = _parse_datetime(race["date"], race.get("time"))
    first = race.get("FirstPractice") or race
    event = {"slug": _slug(int(race["season"]), race["raceName"]), "season": int(race["season"]), "round": int(race["round"]), "official_name": race["raceName"], "short_name": race["raceName"], "country": {"USA": "United States", "UK": "United Kingdom", "UAE": "United Arab Emirates"}.get(location["country"], location["country"]), "locality": location.get("locality"), "circuit_name": race["Circuit"]["circuitName"], "start_at": _parse_datetime(first["date"], first.get("time")).isoformat(), "end_at": (race_start + timedelta(hours=2)).isoformat(), "timezone": zone}
    sessions = []
    for session in _session_payload(race, now):
        start = datetime.fromisoformat(session["startsAt"].replace(" ", "T") + ":00+09:00")
        name = session["shortName"]
        sessions.append({"name": session["name"], "short_name": name, "session_type": "race" if name == "R" else "qualifying" if name == "Q" else "sprint" if name == "S" else "sprint-qualifying" if name == "SQ" else "practice", "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=2 if name == "R" else 1)).isoformat(), "status": session["status"]})
    return event, sessions


def register_missing_active_events(database: Any, now: datetime, event_slug: str | None = None) -> list[str]:
    year = int(event_slug.split("-", 1)[0]) if event_slug else now.year
    races = asyncio.run(JolpicaService().races(year))
    existing = {row["slug"] for row in database.table("events").select("slug").execute().data}
    inserted = []
    for race in races:
        event, sessions = calendar_registration(race, now)
        if event["slug"] in existing or (event_slug and event["slug"] != event_slug):
            continue
        if not event_slug and not event_is_active(event, now):
            continue
        database.table("events").upsert(event, on_conflict="slug", ignore_duplicates=True).execute()
        row = database.table("events").select("id").eq("slug", event["slug"]).single().execute().data
        if sessions:
            database.table("sessions").upsert([{**session, "event_id": row["id"]} for session in sessions], on_conflict="event_id,name", ignore_duplicates=True).execute()
        inserted.append(event["slug"])
    return inserted
