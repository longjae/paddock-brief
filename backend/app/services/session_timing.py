"""Normalize public historical session records for the timing dashboard."""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


def lap_time(value: Any) -> str:
    if not isinstance(value, (int, float)) or value <= 0:
        return "—"
    minutes, seconds = divmod(float(value), 60)
    return f"{int(minutes)}:{seconds:06.3f}" if minutes else f"{seconds:.3f}"


def historical_snapshot(event_slug: str, session: dict[str, Any], results: dict[str, Any],
                        laps: list[dict[str, Any]], control: list[dict[str, Any]],
                        radio: list[dict[str, Any]], weather: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    end = session.get("date_end")
    ended = bool(end and datetime.fromisoformat(end.replace("Z", "+00:00")) < now)
    colours = {2048: "yellow", 2049: "green", 2051: "purple", 2064: "pit"}
    by_driver: dict[int, list[dict[str, Any]]] = {}
    for lap in laps:
        if isinstance(lap.get("driver_number"), int):
            by_driver.setdefault(lap["driver_number"], []).append(lap)
    rows = []
    for driver in results.get("drivers", []):
        driver_laps = sorted(by_driver.get(driver["number"], []), key=lambda lap: lap.get("lap_number") or 0)
        complete = [lap for lap in driver_laps if isinstance(lap.get("lap_duration"), (int, float)) and lap["lap_duration"] > 0]
        last = complete[-1] if complete else {}
        best = min(complete, key=lambda lap: lap["lap_duration"]) if complete else {}
        sectors = [min((lap[f"duration_sector_{index}"] for lap in driver_laps if isinstance(lap.get(f"duration_sector_{index}"), (int, float)) and lap[f"duration_sector_{index}"] > 0), default=None) for index in (1, 2, 3)]
        stints = driver.get("stints", [])
        stint = stints[-1] if stints else {}
        age = max(0, (stint.get("endLap") or stint.get("startLap") or 0) - (stint.get("startLap") or 0) + 1) + (stint.get("tyreAgeAtStart") or 0) if stint else 0
        gap = driver.get("gap")
        if isinstance(gap, list):
            gap = next((item for item in reversed(gap) if item is not None), None)
        rows.append({
            "number": str(driver["number"]), "position": driver.get("position") or 99,
            "code": driver["code"], "name": driver["name"], "team": driver["team"], "colour": driver["colour"],
            "gap": "LEADER" if driver.get("position") == 1 else f"+{gap:.3f}" if isinstance(gap, (int, float)) else str(gap or "—"),
            "interval": "—", "lastLap": lap_time(last.get("lap_duration")), "bestLap": lap_time(best.get("lap_duration")),
            "sectors": [lap_time(value) for value in sectors],
            "currentSectors": [lap_time(last.get(f"duration_sector_{index}")) for index in (1, 2, 3)],
            "sectorFlags": [{"personalFastest": False, "overallFastest": False} for _ in range(3)],
            "miniSectors": [[colours.get(code, "unknown") for code in (last.get(f"segments_sector_{index}") or [])] for index in (1, 2, 3)],
            "compound": stint.get("compound") or "UNKNOWN", "tyreAge": age, "tyreNew": False,
            "stint": len(stints), "pitStops": None,
            "tyreHistory": [{"compound": item["compound"], "laps": max(0, (item.get("endLap") or 0) - (item.get("startLap") or 0) + 1), "new": item.get("tyreAgeAtStart") == 0} for item in stints],
            "inPit": False, "retired": driver.get("status") in {"DNF", "DNS", "DSQ"},
        })
    rows.sort(key=lambda row: row["position"])
    fastest = min((lap for lap in laps if isinstance(lap.get("lap_duration"), (int, float)) and lap["lap_duration"] > 0), key=lambda lap: lap["lap_duration"], default=None)
    codes = {int(row["number"]): row["code"] for row in rows}
    fastest_sectors = []
    for index in (1, 2, 3):
        field = f"duration_sector_{index}"
        leader = min((lap for lap in laps if isinstance(lap.get(field), (int, float)) and lap[field] > 0), key=lambda lap: lap[field], default=None)
        fastest_sectors.append({"sector": index, "driver": codes.get(leader["driver_number"], "—") if leader else "—", "time": lap_time(leader[field]) if leader else "—"})
    radio_items = []
    for item in sorted(radio, key=lambda row: row.get("date") or "", reverse=True)[:50]:
        audio_url = item.get("recording_url") or ""
        parsed = urlparse(audio_url)
        if parsed.scheme != "https" or parsed.hostname != "livetiming.formula1.com" or "/static/" not in parsed.path or "/TeamRadio/" not in parsed.path:
            continue
        session_path, filename = parsed.path.split("/static/", 1)[1].rsplit("/TeamRadio/", 1)
        radio_items.append({"Utc": item.get("date"), "RacingNumber": str(item.get("driver_number") or ""), "Path": f"TeamRadio/{filename}", "SessionPath": f"{session_path}/", "AudioUrl": audio_url})
    last_weather = max(weather, key=lambda row: row.get("date") or "", default={})
    max_lap = max((lap.get("lap_number") or 0 for lap in laps), default=results.get("maxLap") or 0)
    return {
        "event": event_slug, "connection": "offline", "isLive": False, "source": "OpenF1", "archived": True,
        "archiveStatus": results.get("status", "pending"), "updatedAt": end if ended else None, "delaySeconds": None,
        "session": {"name": session["session_name"], "meeting": None, "remaining": "00:00:00" if ended else "—", "lap": max_lap, "totalLaps": max_lap if session["session_name"] in {"Race", "Sprint"} else 0, "ended": ended},
        "trackStatus": {"code": "", "message": "세션 종료" if ended else "공개 기록 확인 중"},
        "weather": {"AirTemp": last_weather.get("air_temperature"), "TrackTemp": last_weather.get("track_temperature")},
        "fastestLap": {"driver": codes.get(fastest["driver_number"], "—"), "time": lap_time(fastest["lap_duration"])} if fastest else None,
        "fastestSectors": fastest_sectors, "drivers": rows,
        "raceControl": [{"Utc": item.get("date"), "Message": item.get("message"), "Category": item.get("category"), "Flag": item.get("flag")} for item in sorted(control, key=lambda row: row.get("date") or "", reverse=True)[:100]],
        "teamRadio": radio_items, "track": None, "lastError": None,
    }
