import asyncio
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from app.schemas import ChampionshipSnapshot, EventDetail
from app.services.media_window import media_window


JOLPICA_BASE_URL = "https://api.jolpi.ca/ergast/f1"
KST = ZoneInfo("Asia/Seoul")
SESSION_KEYS = (
    ("FirstPractice", "Practice 1", "FP1"),
    ("SecondPractice", "Practice 2", "FP2"),
    ("ThirdPractice", "Practice 3", "FP3"),
    ("SprintQualifying", "Sprint Qualifying", "SQ"),
    ("Sprint", "Sprint", "S"),
    ("Qualifying", "Qualifying", "Q"),
    ("Race", "Race", "R"),
)


def _parse_datetime(date_value: str, time_value: str | None = None) -> datetime:
    return datetime.fromisoformat(f"{date_value}T{time_value or '00:00:00Z'}".replace("Z", "+00:00"))


def _slug(year: int, race_name: str) -> str:
    short_name = re.sub(r"\s+Grand Prix$", "", race_name, flags=re.IGNORECASE)
    normalized = re.sub(r"[^a-z0-9]+", "-", short_name.lower()).strip("-")
    return f"{year}-{normalized}"


def _media_window_for_race(race: dict[str, Any]) -> dict[str, str]:
    race_at = _parse_datetime(race["date"], race.get("time"))
    return media_window(race_at.isoformat(), "+00:00:00")


def _featured_race(rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    opened = [row for row in rows if datetime.fromisoformat(_media_window_for_race(row)["mediaOpenAt"]) <= now]
    return opened[-1] if opened else rows[0]


def _session_payload(race: dict[str, Any], now: datetime) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for key, name, short_name in SESSION_KEYS:
        value = race if key == "Race" else race.get(key)
        if not value:
            continue
        starts_at = _parse_datetime(value["date"], value.get("time"))
        estimated_end = starts_at + timedelta(hours=2 if key == "Race" else 1)
        status = "done" if estimated_end < now else "live" if starts_at <= now <= estimated_end else "upcoming"
        payload.append(
            {
                "name": name,
                "shortName": short_name,
                "startsAt": starts_at.astimezone(KST).strftime("%m월 %d일 %H:%M"),
                "status": status,
            }
        )
    return payload


def _event_drivers(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"jolpica-{row['Driver']['driverId']}",
            "code": row["Driver"].get("code") or row["Driver"]["driverId"][:3].upper(),
            "name": f"{row['Driver']['givenName']} {row['Driver']['familyName']}",
            "number": int(row.get("number") or row["Driver"].get("permanentNumber") or 0),
            "nationality": row["Driver"].get("nationality", ""),
            "profileUrl": row["Driver"].get("url"),
            "team": row["Constructor"]["name"],
            "teamCode": row["Constructor"]["constructorId"],
            "colour": "#888888",
            "resultPosition": int(row["position"]) if str(row.get("position", "")).isdigit() else None,
            "resultStatus": row.get("status", "entered"),
            "points": float(row.get("points") or 0),
            "previousSeasonRank": None,
        }
        for row in results
    ]


def _standings_payload(
    constructor_rows: list[dict[str, Any]], driver_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    constructors = [
        {
            "position": int(row["position"]),
            "teamCode": row["Constructor"]["constructorId"],
            "team": row["Constructor"]["name"],
            "nationality": row["Constructor"].get("nationality", ""),
            "points": float(row.get("points") or 0),
            "wins": int(row.get("wins") or 0),
        }
        for row in constructor_rows
    ]
    drivers = []
    for row in driver_rows:
        constructor = (row.get("Constructors") or [{}])[0]
        driver = row["Driver"]
        drivers.append(
            {
                "position": int(row["position"]),
                "code": driver.get("code") or driver["driverId"][:3].upper(),
                "name": f"{driver['givenName']} {driver['familyName']}",
                "teamCode": constructor.get("constructorId", ""),
                "team": constructor.get("name", ""),
                "points": float(row.get("points") or 0),
                "wins": int(row.get("wins") or 0),
            }
        )
    return constructors, drivers


class JolpicaService:
    """Free schedule and results adapter using the Ergast-compatible Jolpica API."""

    def __init__(self) -> None:
        self._races: dict[int, list[dict[str, Any]]] = {}
        self._results: dict[tuple[int, int], list[dict[str, Any]]] = {}
        self._standings: dict[tuple[int, int], ChampionshipSnapshot] = {}
        self._lock = asyncio.Lock()

    async def _get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=2),
            headers={"User-Agent": "PaddockBrief/1.0"},
        ) as client:
            response = await client.get(f"{JOLPICA_BASE_URL}/{path}")
            response.raise_for_status()
            return response.json()

    async def races(self, year: int) -> list[dict[str, Any]]:
        if year not in self._races:
            async with self._lock:
                if year not in self._races:
                    data = await self._get(f"{year}.json?limit=100")
                    self._races[year] = data["MRData"]["RaceTable"]["Races"]
        return self._races[year]

    async def results(self, year: int, round_number: int) -> list[dict[str, Any]]:
        cache_key = (year, round_number)
        if cache_key not in self._results:
            data = await self._get(f"{year}/{round_number}/results.json?limit=100")
            races = data["MRData"]["RaceTable"]["Races"]
            self._results[cache_key] = races[0].get("Results", []) if races else []
        return self._results[cache_key]

    async def championship(self, year: int, event_round: int) -> ChampionshipSnapshot:
        cache_key = (year, event_round)
        if cache_key in self._standings:
            return self._standings[cache_key]

        source_year = year - 1 if event_round == 1 else year
        source_round = None if event_round == 1 else event_round - 1
        prefix = f"{source_year}" if source_round is None else f"{source_year}/{source_round}"
        constructor_data, driver_data = await asyncio.gather(
            self._get(f"{prefix}/constructorStandings.json?limit=100"),
            self._get(f"{prefix}/driverStandings.json?limit=100"),
        )
        constructor_lists = constructor_data["MRData"]["StandingsTable"].get("StandingsLists", [])
        driver_lists = driver_data["MRData"]["StandingsTable"].get("StandingsLists", [])
        constructor_rows = constructor_lists[0].get("ConstructorStandings", []) if constructor_lists else []
        driver_rows = driver_lists[0].get("DriverStandings", []) if driver_lists else []
        constructors, drivers = _standings_payload(constructor_rows, driver_rows)
        basis_label = (
            f"{source_year} 시즌 최종 순위 · ROUND 1 기준"
            if source_round is None
            else f"{source_year} ROUND {source_round} 종료 기준"
        )
        snapshot = ChampionshipSnapshot(
            season=year,
            eventRound=event_round,
            sourceSeason=source_year,
            sourceRound=source_round,
            basisLabel=basis_label,
            constructors=constructors,
            drivers=drivers,
        )
        self._standings[cache_key] = snapshot
        return snapshot

    async def list_events(self, year: int) -> list[dict[str, object]]:
        return [self._event_summary(row) for row in await self.races(year)]

    async def featured_event(self, year: int) -> EventDetail:
        rows = await self.races(year)
        race = _featured_race(rows, datetime.now(timezone.utc))
        return await self._event_detail(race)

    async def event_by_slug(self, slug: str) -> EventDetail | None:
        try:
            year = int(slug.split("-", 1)[0])
        except (ValueError, IndexError):
            return None
        for race in await self.races(year):
            if _slug(year, race["raceName"]) == slug:
                return await self._event_detail(race)
        return None

    @staticmethod
    def _event_summary(race: dict[str, Any]) -> dict[str, object]:
        year = int(race["season"])
        race_at = _parse_datetime(race["date"], race.get("time"))
        first = next((race.get(key) for key, _, _ in SESSION_KEYS if key != "Race" and race.get(key)), race)
        start_at = _parse_datetime(first["date"], first.get("time"))
        location = race["Circuit"]["Location"]
        return {
            "slug": _slug(year, race["raceName"]),
            "season": year,
            "round": int(race["round"]),
            "name": race["raceName"],
            "country": location["country"],
            "circuit": race["Circuit"]["circuitName"],
            "dateLabel": f"{start_at.astimezone(KST).month}월 {start_at.astimezone(KST).day}일 — {race_at.astimezone(KST).month}월 {race_at.astimezone(KST).day}일 · KST",
            **_media_window_for_race(race),
        }

    async def _event_detail(self, race: dict[str, Any]) -> EventDetail:
        summary = self._event_summary(race)
        year = int(race["season"])
        round_number = int(race["round"])
        results = await self.results(year, round_number) if _parse_datetime(race["date"], race.get("time")) < datetime.now(timezone.utc) else []
        country = quote(str(summary["country"]))
        return EventDetail.model_validate(
            {
                **summary,
                "trackMapUrl": None,
                "sessions": _session_payload(race, datetime.now(timezone.utc)),
                "videos": [
                    {
                        "id": f"formula1-{year}-{round_number}",
                        "category": "공식 영상 모음",
                        "title": f"{race['raceName']} 공식 인터뷰와 하이라이트",
                        "source": "Formula 1",
                        "duration": "공식 채널",
                        "url": f"https://www.youtube.com/@Formula1/search?query={country}%20{year}%20interview",
                        "youtubeId": None,
                        "participants": ["Formula 1 official channel"],
                    }
                ],
                "tyreAllocation": {"hard": "TBC", "medium": "TBC", "soft": "TBC"},
                "tyreSourceUrl": None,
                "summary": [
                    "캘린더와 공식 결과는 무료 Jolpica F1 API에서 불러왔습니다.",
                    "종료된 세션의 타이어와 랩 데이터는 FastF1 배치가 검증 후 보강합니다.",
                ],
                "drivers": [],
                "eventDrivers": _event_drivers(results),
            }
        )


@lru_cache
def get_jolpica_service() -> JolpicaService:
    return JolpicaService()
