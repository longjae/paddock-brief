export type Session = {
  name: string;
  shortName: string;
  startsAt: string;
  status: "done" | "live" | "upcoming";
};

export type Video = {
  id: string;
  category: string;
  title: string;
  source: string;
  duration: string;
  url: string;
  youtubeId?: string | null;
  participants: string[];
  summary?: string | null;
  detailedSummary?: string | null;
  transcriptStatus?: "pending" | "ready" | "unavailable" | "failed";
  transcriptLanguage?: string | null;
  publishedAt?: string | null;
};

export type DriverState = {
  position: number;
  code: string;
  name: string;
  team: string;
  colour: string;
  compound: "SOFT" | "MEDIUM" | "HARD" | "INTERMEDIATE" | "WET";
  tyreAge: number;
  gap: string;
};

export type TeamContent = {
  id: string;
  team: string;
  teamCode: string;
  colour: string;
  source: string;
  category: string;
  title: string;
  url: string;
  summary: string;
  detailedSummary: string;
  participants: string[];
  publishedAt?: string | null;
  contentType: "interview" | "team-report" | "video" | "social";
};

export type NewsArticle = {
  id: string;
  outlet: string;
  category: "race-report" | "analysis" | "interview" | "feature" | "preview" | "results";
  title: string;
  url: string;
  summary: string;
  detailedSummary: string;
  author?: string | null;
  tags: string[];
  teamCodes: string[];
  driverCodes: string[];
  publishedAt?: string | null;
  isPaywalled: boolean;
};

export type EventDriver = {
  id: string;
  code: string;
  name: string;
  number: number;
  nationality: string;
  profileUrl?: string | null;
  team: string;
  teamCode: string;
  colour: string;
  resultPosition?: number | null;
  resultStatus: string;
  points: number;
  previousSeasonRank?: number | null;
};

export type EventDetail = {
  slug: string;
  season: number;
  round: number;
  name: string;
  country: string;
  circuit: string;
  trackMapUrl?: string | null;
  dateLabel: string;
  mediaOpenAt?: string | null;
  mediaOpenLabel: string;
  sessions: Session[];
  videos: Video[];
  tyreAllocation: { hard: string; medium: string; soft: string };
  tyreSourceUrl?: string | null;
  summary: string[];
  drivers: DriverState[];
  teamContent: TeamContent[];
  news: NewsArticle[];
  eventDrivers: EventDriver[];
};

export type EventSummary = Pick<EventDetail, "slug" | "season" | "round" | "name" | "country" | "circuit" | "dateLabel" | "mediaOpenAt" | "mediaOpenLabel">;

export type ConstructorStanding = {
  position: number;
  teamCode: string;
  team: string;
  nationality: string;
  points: number;
  wins: number;
};

export type DriverStanding = {
  position: number;
  code: string;
  name: string;
  teamCode: string;
  team: string;
  points: number;
  wins: number;
};

export type ChampionshipSnapshot = {
  season: number;
  eventRound: number;
  sourceSeason: number;
  sourceRound?: number | null;
  basisLabel: string;
  constructors: ConstructorStanding[];
  drivers: DriverStanding[];
};

export type LiveTimingDriver = {
  position: number; number: string; code: string; name: string; team: string; colour: string;
  gap: string; interval: string; lastLap: string; bestLap: string; sectors: string[];
  sectorFlags: Array<{ personalFastest: boolean; overallFastest: boolean }>;
  compound: string; tyreAge: number; tyreNew: boolean; stint: number;
  tyreHistory: Array<{ compound: string; laps: number; new: boolean }>;
  inPit: boolean; retired: boolean;
};

export type LiveTimingSnapshot = {
  event: string;
  connection: "disabled" | "offline" | "connecting" | "reconnecting" | "live";
  isLive: boolean;
  updatedAt?: string | null;
  delaySeconds?: number | null;
  session: { name: string; meeting?: string | null; remaining: string; lap: number; totalLaps: number };
  trackStatus: { code: string; message: string };
  weather: Record<string, string | number | boolean | null>;
  fastestLap?: { driver: string; time: string } | null;
  fastestSectors?: Array<{ sector: number; driver: string; time: string }>;
  tyreInventory?: { available: boolean; message: string };
  drivers: LiveTimingDriver[];
  raceControl: Array<Record<string, string | number | boolean | null>>;
  teamRadio: Array<Record<string, string | number | boolean | null>>;
  lastError?: string | null;
};
