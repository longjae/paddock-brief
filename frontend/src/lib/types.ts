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
