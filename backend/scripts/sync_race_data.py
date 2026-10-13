from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any

from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.fastf1_sync import classification_snapshot, normalized_name, safe_number
from app.services.race_results import fetch_public_results, public_classification_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist completed race results and tyre state from FastF1.")
    parser.add_argument("--event-slug")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def frame_rows(frame: Any) -> list[dict[str, Any]]:
    return frame.to_dict(orient="records") if frame is not None else []


def main() -> int:
    args = parse_args()
    settings = Settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        print(json.dumps({"ok": False, "error": "SUPABASE_URL and SUPABASE_SECRET_KEY are required"}))
        return 2

    try:
        import fastf1
    except ImportError:
        print(json.dumps({"ok": False, "error": "Install the collector dependency group: uv sync --group collector"}))
        return 2

    database = create_client(settings.supabase_url, settings.supabase_secret_key)
    query = database.table("events").select("id,slug,season,round,short_name,country,locality,circuit_name,end_at")
    if args.event_slug:
        query = query.eq("slug", args.event_slug)
    events = query.order("end_at").execute().data
    now = datetime.now(timezone.utc)
    if not args.force and not args.event_slug:
        events = [
            event for event in events
            if now - timedelta(days=7) <= datetime.fromisoformat(str(event["end_at"]).replace("Z", "+00:00")) <= now
        ]

    outcomes: list[dict[str, Any]] = []
    for event in events:
        race_sessions = (
            database.table("sessions").select("id,ends_at").eq("event_id", event["id"]).eq("session_type", "race").limit(1).execute().data
        )
        if not race_sessions:
            outcomes.append({"slug": event["slug"], "status": "skipped", "reason": "race session missing"})
            continue
        race_session = race_sessions[0]
        captured_at = race_session.get("ends_at") or event["end_at"]
        existing = (
            database.table("race_state_snapshots").select("id").eq("session_id", race_session["id"]).eq("captured_at", captured_at).limit(1).execute().data
        )
        if existing and not args.force:
            outcomes.append({"slug": event["slug"], "status": "skipped", "reason": "already synced"})
            continue

        try:
            ff_event = fastf1.get_event(int(event["season"]), int(event["round"]))
            ff_name = f"{ff_event.get('EventName', '')} {ff_event.get('Location', '')} {ff_event.get('Country', '')}"
            expected = f"{event['short_name']} {event['locality']} {event['country']} {event['circuit_name']}"
            expected_terms = {normalized_name(term) for term in (event["country"], event["locality"], event["circuit_name"])}
            if not any(term and term in normalized_name(ff_name) for term in expected_terms):
                outcomes.append({"slug": event["slug"], "status": "skipped", "reason": f"FastF1 event mismatch: {ff_name}"})
                continue
            result_rows: list[dict[str, Any]] = []
            lap_rows: list[dict[str, Any]] = []
            try:
                session = fastf1.get_session(int(event["season"]), int(event["round"]), "R")
                session.load(telemetry=False, weather=False, messages=False)
                result_rows = frame_rows(session.results)
                lap_rows = frame_rows(session.laps)
                state = classification_snapshot(result_rows, lap_rows)
                if not state["drivers"] or not lap_rows:
                    raise ValueError("FastF1 classification or lap data unavailable")
            except Exception:
                race, stints, driver_details = fetch_public_results(int(event["season"]), int(event["round"]), str(event["country"]))
                state = public_classification_snapshot(race, stints, driver_details)
                result_rows = []
                lap_rows = [{"LapNumber": stint.get("lap_end")} for stint in stints]
            if not args.dry_run:
                database.table("race_state_snapshots").upsert(
                    {
                        "session_id": race_session["id"],
                        "captured_at": captured_at,
                    "lap": max((int(safe_number(row.get("LapNumber"))) for row in lap_rows), default=0),
                        "state": state,
                    },
                    on_conflict="session_id,captured_at",
                ).execute()
                database.table("sessions").update({"status": "done"}).eq("id", race_session["id"]).execute()

                driver_rows = database.table("drivers").select("id,code").execute().data
                team_rows = database.table("teams").select("id,name").execute().data
                driver_ids = {row["code"]: row["id"] for row in driver_rows}
                team_ids = {normalized_name(row["name"]): row["id"] for row in team_rows}
                for result in result_rows:
                    code = str(result.get("Abbreviation") or "")
                    team_id = next((value for name, value in team_ids.items() if name in normalized_name(result.get("TeamName"))), None)
                    if code in driver_ids and team_id:
                        database.table("event_drivers").upsert(
                            {
                                "event_id": event["id"],
                                "driver_id": driver_ids[code],
                                "team_id": team_id,
                                "grid_position": int(safe_number(result.get("GridPosition"))),
                                "result_position": int(safe_number(result.get("Position"))) or None,
                                "result_status": str(result.get("Status") or "classified"),
                                "points": safe_number(result.get("Points")),
                            },
                            on_conflict="event_id,driver_id",
                        ).execute()
            outcomes.append({"slug": event["slug"], "status": "dry-run" if args.dry_run else "synced", "drivers": len(state["drivers"])})
        except Exception as exc:
            outcomes.append({"slug": event["slug"], "status": "failed", "error": str(exc)})

    print(json.dumps({"ok": not any(row["status"] == "failed" for row in outcomes), "events": outcomes}, ensure_ascii=False, default=str))
    return 1 if any(row["status"] == "failed" for row in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
