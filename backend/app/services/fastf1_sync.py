from __future__ import annotations

import math
import re
from datetime import timedelta
from typing import Any


VALID_COMPOUNDS = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}


def normalized_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def safe_number(value: object, default: float = 0) -> float:
    try:
        number = float(value)
        return default if math.isnan(number) else number
    except (TypeError, ValueError):
        return default


def format_gap(value: object, position: int) -> str:
    if position == 1:
        return "WINNER"
    if isinstance(value, timedelta):
        return f"+{value.total_seconds():.3f}"
    seconds = getattr(value, "total_seconds", lambda: None)()
    return f"+{seconds:.3f}" if seconds is not None and not math.isnan(seconds) else "—"


def latest_tyre_by_driver(lap_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in lap_rows:
        code = str(row.get("Driver") or "")
        lap_number = int(safe_number(row.get("LapNumber")))
        compound = str(row.get("Compound") or "").upper()
        if not code or compound not in VALID_COMPOUNDS:
            continue
        if code not in latest or lap_number >= latest[code]["lap_number"]:
            latest[code] = {
                "lap_number": lap_number,
                "compound": compound,
                "tyre_age": int(safe_number(row.get("TyreLife"))),
            }
    return latest


def classification_snapshot(result_rows: list[dict[str, Any]], lap_rows: list[dict[str, Any]]) -> dict[str, Any]:
    tyres = latest_tyre_by_driver(lap_rows)
    drivers = []
    for row in result_rows:
        position = int(safe_number(row.get("Position"), 999))
        code = str(row.get("Abbreviation") or "")
        tyre = tyres.get(code)
        if not code or position == 999 or not tyre:
            continue
        colour = str(row.get("TeamColor") or "888888").lstrip("#")
        drivers.append(
            {
                "position": position,
                "code": code,
                "name": str(row.get("FullName") or code),
                "team": str(row.get("TeamName") or "Unknown"),
                "colour": f"#{colour}",
                "compound": tyre["compound"],
                "tyreAge": tyre["tyre_age"],
                "gap": format_gap(row.get("Time"), position),
            }
        )
    return {"kind": "final-classification", "source": "FastF1", "drivers": sorted(drivers, key=lambda row: row["position"])}
