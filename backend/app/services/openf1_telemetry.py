"""Optional authenticated telemetry; never mix samples from different sessions."""
from datetime import UTC, datetime, timedelta, timezone
import math
from typing import Any

from app.services.fastf1_sync import normalized_name
from app.services.openf1 import OpenF1Service


def session_matches(session: dict, info: dict, now: datetime) -> bool:
    try:
        start = datetime.fromisoformat(session["date_start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(session["date_end"].replace("Z", "+00:00"))
        offset = session.get("gmt_offset") or "+00:00:00"
        sign = -1 if offset.startswith("-") else 1
        parts = [int(value) for value in offset.lstrip("+-").split(":")]
        local_date = start.astimezone(timezone(sign * timedelta(hours=parts[0], minutes=parts[1]))).date().isoformat()
        location = info.get("Meeting", {}).get("Location")
        return (start - timedelta(minutes=10) <= now <= end + timedelta(minutes=10)
                and session.get("session_name") == info.get("Name")
                and bool(location) and normalized_name(location) == normalized_name(session.get("location"))
                and local_date in str(info.get("Path") or "").split("/")[-2])
    except (KeyError, ValueError, TypeError, IndexError):
        return False


def fresh_rows(rows: list, now: datetime) -> list[dict]:
    result = []
    for row in rows:
        try:
            stamp = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
            if -5 <= (now - stamp).total_seconds() <= 30:
                result.append(row)
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(result, key=lambda row: row["date"])


class OpenF1Telemetry:
    def __init__(self, token: str):
        self.api = OpenF1Service(token)
        self.session: dict[str, Any] | None = None

    async def sample(self, info: dict, now: datetime) -> tuple[dict, dict] | None:
        if not self.session or not session_matches(self.session, info, now):
            sessions = await self.api._get("sessions", session_key="latest")
            self.session = next((row for row in sessions if session_matches(row, info, now)), None)
        if not self.session:
            return None
        params = {"session_key": self.session["session_key"], "date>": (now - timedelta(seconds=5)).isoformat()}
        positions = fresh_rows(await self.api._get("location", **params), now)
        cars = fresh_rows(await self.api._get("car_data", **params), now)
        location_samples, car_samples = [], []
        for row in positions:
            try:
                if not all(math.isfinite(float(row[key])) for key in ("x", "y")):
                    continue
                location_samples.append({"Timestamp": row["date"], "Entries": {str(row["driver_number"]): {"X": row["x"], "Y": row["y"], "Status": "OnTrack"}}})
            except (KeyError, ValueError, TypeError):
                continue
        for row in cars:
            keys = {"0": "rpm", "2": "speed", "3": "n_gear", "4": "throttle", "5": "brake"}
            try:
                channels = {channel: int(row[key]) for channel, key in keys.items()}
                car_samples.append({"Utc": row["date"], "Cars": {str(row["driver_number"]): {"Channels": channels}}})
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
        return {"Position": location_samples}, {"Entries": car_samples}
