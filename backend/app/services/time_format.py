from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def format_kst_datetime(value: Any) -> str:
    return parse_datetime(value).astimezone(KST).strftime("%Y-%m-%d %H:%M")


def format_kst_date_range(start_value: Any, end_value: Any) -> str:
    start = parse_datetime(start_value).astimezone(KST)
    end = parse_datetime(end_value).astimezone(KST)
    return f"{start:%Y-%m-%d} — {end:%Y-%m-%d} · KST"
