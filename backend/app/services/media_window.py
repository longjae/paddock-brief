from datetime import datetime, time, timedelta, timezone


KOREAN_WEEKDAYS = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")


def _fixed_timezone(gmt_offset: str) -> timezone:
    sign = -1 if gmt_offset.startswith("-") else 1
    hours, minutes, seconds = (int(part) for part in gmt_offset.lstrip("+-").split(":"))
    return timezone(sign * timedelta(hours=hours, minutes=minutes, seconds=seconds))


def media_window(end_value: str, gmt_offset: str) -> dict[str, str]:
    """Return Thursday 00:00 in the event's local timezone for its race week."""
    event_timezone = _fixed_timezone(gmt_offset)
    local_end = datetime.fromisoformat(end_value.replace("Z", "+00:00")).astimezone(event_timezone)
    days_since_thursday = (local_end.weekday() - 3) % 7
    thursday = local_end.date() - timedelta(days=days_since_thursday)
    opens_local = datetime.combine(thursday, time.min, tzinfo=event_timezone)
    return {
        "mediaOpenAt": opens_local.astimezone(timezone.utc).isoformat(),
        "mediaOpenLabel": f"{thursday.month}월 {thursday.day}일 {KOREAN_WEEKDAYS[thursday.weekday()]} · 개최지 현지시간",
    }
