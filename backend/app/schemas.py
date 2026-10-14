from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Session(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    shortName: str
    startsAt: str
    status: Literal["done", "live", "upcoming"]


class Video(BaseModel):
    id: str
    category: str
    title: str
    source: str
    duration: str
    url: str
    youtubeId: str | None = None
    participants: list[str]
    summary: str | None = None
    detailedSummary: str | None = None
    transcriptStatus: Literal["pending", "ready", "unavailable", "failed"] = "pending"
    transcriptLanguage: str | None = None
    publishedAt: str | None = None


class TyreAllocation(BaseModel):
    hard: str
    medium: str
    soft: str


class DriverState(BaseModel):
    position: int
    code: str
    name: str
    team: str
    colour: str
    compound: Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]
    tyreAge: int
    gap: str


class TeamContent(BaseModel):
    id: str
    team: str
    teamCode: str
    colour: str
    source: str
    category: str
    title: str
    url: str
    summary: str
    detailedSummary: str
    participants: list[str]
    publishedAt: str | None = None
    contentType: Literal["interview", "team-report", "video", "social"]


class NewsArticle(BaseModel):
    id: str
    outlet: str
    category: Literal["race-report", "analysis", "interview", "feature", "preview", "results"]
    title: str
    url: str
    summary: str
    detailedSummary: str
    author: str | None = None
    tags: list[str]
    teamCodes: list[str]
    driverCodes: list[str]
    publishedAt: str | None = None
    isPaywalled: bool = False


class EventDriver(BaseModel):
    id: str
    code: str
    name: str
    number: int
    nationality: str
    profileUrl: str | None = None
    team: str
    teamCode: str
    colour: str
    resultPosition: int | None = None
    resultStatus: str
    points: float
    previousSeasonRank: int | None = None


class ConstructorStanding(BaseModel):
    position: int
    teamCode: str
    team: str
    nationality: str = ""
    points: float
    wins: int


class DriverStanding(BaseModel):
    position: int
    code: str
    name: str
    teamCode: str
    team: str
    points: float
    wins: int


class ChampionshipSnapshot(BaseModel):
    season: int
    eventRound: int
    sourceSeason: int
    sourceRound: int | None = None
    basisLabel: str
    constructors: list[ConstructorStanding]
    drivers: list[DriverStanding]


class EventDetail(BaseModel):
    slug: str
    season: int
    round: int
    name: str
    country: str
    circuit: str
    trackMapUrl: str | None = None
    dateLabel: str
    gmtOffset: str | None = None
    mediaOpenAt: str | None = None
    mediaOpenLabel: str = "레이스 주 목요일 · 개최지 현지시간"
    sessions: list[Session]
    videos: list[Video]
    tyreAllocation: TyreAllocation
    tyreSourceUrl: str | None = None
    summary: list[str]
    drivers: list[DriverState]
    teamContent: list[TeamContent] = Field(default_factory=list)
    news: list[NewsArticle] = Field(default_factory=list)
    eventDrivers: list[EventDriver] = Field(default_factory=list)


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    mode: Literal["jolpica", "supabase"]
    supabaseConfigured: bool
