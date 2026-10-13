from __future__ import annotations

from typing import Any

import httpx

from app.services.fastf1_sync import VALID_COMPOUNDS, normalized_name, safe_number


def fetch_public_results(season: int, round_number: int, country: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Get the published classification and optional last tyre stint."""
    with httpx.Client(timeout=20) as client:
        response = client.get(f"https://api.jolpi.ca/ergast/f1/{season}/{round_number}/results.json", params={"limit": 100})
        response.raise_for_status()
        races = response.json()["MRData"]["RaceTable"]["Races"]
        if len(races) != 1 or normalized_name(country) not in normalized_name(races[0]["raceName"]):
            raise ValueError("Jolpica result does not match the selected event")
        race = races[0]
        results = race.get("Results") or []
        if not results:
            raise ValueError("Jolpica has not published race results")

        stints: list[dict[str, Any]] = []
        try:
            sessions_response = client.get("https://api.openf1.org/v1/sessions", params={"year": season, "country_name": country, "session_name": "Race"})
            sessions_response.raise_for_status()
            sessions = sessions_response.json()
            race_date = race.get("date", "")
            matching = [item for item in sessions if str(item.get("date_start", ""))[:10] == race_date]
            if len(matching) == 1:
                stint_response = client.get("https://api.openf1.org/v1/stints", params={"session_key": matching[0]["session_key"]})
                stint_response.raise_for_status()
                stints = stint_response.json()
        except (httpx.HTTPError, ValueError, KeyError):
            pass  # Classification is still useful when tyre data is unavailable.
    return race, stints


def public_classification_snapshot(race: dict[str, Any], stints: list[dict[str, Any]]) -> dict[str, Any]:
    latest_stint: dict[int, dict[str, Any]] = {}
    for stint in stints:
        number = int(safe_number(stint.get("driver_number")))
        if number and (number not in latest_stint or safe_number(stint.get("lap_end")) >= safe_number(latest_stint[number].get("lap_end"))):
            latest_stint[number] = stint

    drivers = []
    for result in race.get("Results") or []:
        person = result.get("Driver") or {}
        number = int(safe_number(person.get("permanentNumber")))
        stint = latest_stint.get(number) or {}
        compound = str(stint.get("compound") or "").upper()
        tyre_age = int(safe_number(stint.get("tyre_age_at_start"))) + max(0, int(safe_number(stint.get("lap_end"))) - int(safe_number(stint.get("lap_start"))) + 1)
        position = int(safe_number(result.get("position")))
        if not position or not person.get("code"):
            continue
        time = (result.get("Time") or {}).get("time")
        status = str(result.get("status") or "")
        drivers.append({
            "position": position,
            "code": person["code"],
            "name": f"{person.get('givenName', '')} {person.get('familyName', '')}".strip(),
            "team": (result.get("Constructor") or {}).get("name") or "Unknown",
            "colour": "#888888",
            "compound": compound if compound in VALID_COMPOUNDS else None,
            "tyreAge": tyre_age if compound in VALID_COMPOUNDS else None,
            "gap": "WINNER" if position == 1 else (time if str(time).startswith("+") else status),
        })
    if not drivers:
        raise ValueError("No classified drivers in Jolpica results")
    return {"kind": "final-classification", "source": "Jolpica · OpenF1 tyres" if stints else "Jolpica", "drivers": sorted(drivers, key=lambda row: row["position"])}
