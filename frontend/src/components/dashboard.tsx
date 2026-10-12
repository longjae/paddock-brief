"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { demoEvent } from "@/lib/mock-data";
import { F1_GLOSSARY, GLOSSARY_CATEGORIES } from "@/lib/glossary";
import type { GlossaryCategory } from "@/lib/glossary";
import type { ChampionshipSnapshot, EventDetail, EventSummary, NewsArticle, TeamContent, Video } from "@/lib/types";
import { LiveTiming } from "@/components/live-timing";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type ModalContent = {
  id: string;
  context: string;
  source: string;
  title: string;
  url: string;
  summary: string;
  detailedSummary: string;
  participants: string[];
  colour: string;
  detailLabel: string;
};

export type MainSection = "weekend" | "interviews" | "championship" | "live" | "glossary";
export type InterviewSection = "press" | "teams" | "drivers" | "videos" | "media";
type WeekendDay = "금요일" | "토요일" | "일요일";

const WEEKEND_DAYS: WeekendDay[] = ["금요일", "토요일", "일요일"];
const GP_KOREAN_KEYWORDS: Record<string, string[]> = {
  australian: ["호주", "멜버른"], chinese: ["중국", "상하이"], japanese: ["일본", "스즈카"], miami: ["마이애미"],
  canadian: ["캐나다", "몬트리올"], monaco: ["모나코"], barcelona: ["바르셀로나"], austrian: ["오스트리아", "슈필베르크"],
  british: ["영국", "실버스톤"], belgian: ["벨기에", "스파"], hungarian: ["헝가리", "헝가로링"], dutch: ["네덜란드", "잔드보르트"],
  italian: ["이탈리아", "몬차"], spanish: ["마드리드"], azerbaijan: ["아제르바이잔", "바쿠"],
  bahrain: ["바레인", "말레이시아", "세팡"], singapore: ["싱가포르", "마리나베이"], "united-states": ["미국 그랑프리", "미국 GP", "오스틴", "COTA"],
  "mexico-city": ["멕시코"], brazilian: ["브라질", "상파울루", "인터라고스"], "las-vegas": ["라스베이거스", "라스베가스"],
  qatar: ["카타르", "루사일"], "abu-dhabi": ["아부다비", "야스마리나"],
};

function articleMentionsEvent(article: NewsArticle, event: EventDetail): boolean {
  const slug = event.slug.replace(/^\d{4}-/, "");
  const sharedCountry = ["United States", "Spain"].includes(event.country);
  const aliases = [...(sharedCountry ? [event.name] : [event.country, event.name.replace(/ grand prix.*$/i, ""), slug.replaceAll("-", " ")]), event.circuit, ...(GP_KOREAN_KEYWORDS[slug] ?? [])];
  const content = [article.title, article.summary, ...article.tags].join(" ").toLocaleLowerCase();
  return aliases.some((alias) => alias.length >= 3 && content.includes(alias.toLocaleLowerCase()));
}

function pageHref(section: MainSection, eventSlug?: string, interviewView: InterviewSection = "press"): string {
  const prefix = eventSlug ? `/races/${eventSlug}` : "";
  if (section === "interviews") return `${prefix}/interviews/${interviewView}`;
  return `${prefix}/${section}`;
}

const TEAM_COLOURS: Record<string, string> = {
  mclaren: "#ff8000",
  mercedes: "#27f4d2",
  redbull: "#3671c6",
  ferrari: "#e8002d",
  williams: "#64c4ff",
  racingbulls: "#6692ff",
  astonmartin: "#229971",
  haas: "#b6babd",
  audi: "#f50537",
  alpine: "#ff87bc",
  cadillac: "#d4af37",
};

const TEAM_LOGO_SLUGS: Record<string, string> = {
  mercedes: "mercedes",
  ferrari: "ferrari",
  mclaren: "mclaren",
  redbull: "redbullracing",
  redbullracing: "redbullracing",
  racingbulls: "racingbulls",
  alpine: "alpine",
  haas: "haasf1team",
  haasf1team: "haasf1team",
  audi: "audi",
  williams: "williams",
  astonmartin: "astonmartin",
  cadillac: "cadillac",
};

const DRIVER_NUMBERS: Record<string, number> = {
  ANT: 12, RUS: 63, HAM: 44, LEC: 16, NOR: 4, PIA: 81, VER: 1, HAD: 6,
  LAW: 30, LIN: 41, GAS: 10, COL: 43, BEA: 87, OCO: 31, BOR: 5, HUL: 27,
  ALO: 14, STR: 18, SAI: 55, ALB: 23, TSU: 22, BOT: 77, PER: 11,
};

const DRIVER_ALIASES: Record<string, string[]> = {
  ANT: ["키미 안토넬리", "안드레아 키미 안토넬리", "안토넬리"], RUS: ["조지 러셀", "러셀"],
  HAM: ["루이스 해밀턴", "해밀턴"], LEC: ["샤를 르클레르", "르클레르"],
  NOR: ["랜도 노리스", "노리스"], PIA: ["오스카 피아스트리", "피아스트리"],
  VER: ["막스 베르스타펜", "막스 페르스타펜", "베르스타펜", "페르스타펜"], HAD: ["이삭 하지르", "아이작 하자르", "하지르", "하자르"],
  LAW: ["리암 로슨", "로슨"], LIN: ["아비드 린드블라드", "린드블라드"], GAS: ["피에르 가슬리", "가슬리"],
  COL: ["프랑코 콜라핀토", "콜라핀토"], BEA: ["올리버 베어먼", "베어먼"], OCO: ["에스테반 오콘", "오콘"],
  BOR: ["가브리엘 보르톨레토", "보르톨레토"], HUL: ["니코 휠켄베르크", "휠켄베르크"],
  ALO: ["페르난도 알론소", "알론소"], STR: ["랜스 스트롤", "스트롤"], SAI: ["카를로스 사인츠", "사인츠"],
  ALB: ["알렉산더 알본", "알본"], TSU: ["유키 츠노다", "츠노다"], BOT: ["발테리 보타스", "보타스"],
  PER: ["세르히오 페레스", "페레스"],
};

function normalizedIdentity(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "").replace(/^rb$/, "racingbulls");
}

function normalizedPerson(value: string): string {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

function mentionsDriver(participants: string[], driver: EventDetail["eventDrivers"][number]): boolean {
  const familyName = driver.name.split(" ").at(-1) ?? driver.name;
  const aliases = [driver.name, familyName, ...(DRIVER_ALIASES[driver.code] ?? [])].map(normalizedPerson);
  return participants.some((participant) => {
    const candidate = normalizedPerson(participant);
    return aliases.some((alias) => alias.length >= 3 && (candidate === alias || candidate.includes(alias)));
  });
}

function standingTeamColour(teamCode: string, teamName: string): string {
  return TEAM_COLOURS[normalizedIdentity(teamCode)] ?? TEAM_COLOURS[normalizedIdentity(teamName)] ?? "#8a8f88";
}

function TeamLogo({ teamCode, teamName, className = "" }: { teamCode: string; teamName: string; className?: string }) {
  const identity = normalizedIdentity(teamCode);
  const slug = TEAM_LOGO_SLUGS[identity] ?? TEAM_LOGO_SLUGS[normalizedIdentity(teamName)];
  if (!slug) return <span aria-hidden="true" className={`team-logo-fallback ${className}`}>{teamName.slice(0, 2).toUpperCase()}</span>;
  const src = slug === "mercedes"
    ? "/assets/team-logos/mercedes-mark.png"
    : `https://media.formula1.com/image/upload/e_trim/c_fit,w_96,h_48/q_auto/v1740000001/common/f1/2026/${slug}/2026${slug}logowhite.webp`;
  return (
    <img
      alt=""
      className={`team-logo ${className}`}
      height="48"
      loading="lazy"
      src={src}
      width="96"
    />
  );
}

function sessionDay(session: EventDetail["sessions"][number]): WeekendDay {
  const match = session.startsAt.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (match) {
    const weekday = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))).getUTCDay();
    if (weekday === 5) return "금요일";
    if (weekday === 6) return "토요일";
    if (weekday === 0) return "일요일";
  }
  if (["FP1", "FP2", "SQ"].includes(session.shortName)) return "금요일";
  if (["FP3", "Q", "S"].includes(session.shortName)) return "토요일";
  return "일요일";
}

function publishedDay(value?: string | null): string {
  if (!value) return "날짜 미정";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "날짜 미정";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "long",
    timeZone: "Asia/Seoul",
  }).format(date);
}

function publishedTime(value?: string | null): number {
  if (!value) return Number.NEGATIVE_INFINITY;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? Number.NEGATIVE_INFINITY : time;
}

function publishedStamp(value?: string | null): string {
  const time = publishedTime(value);
  if (!Number.isFinite(time)) return "발행일 미상";
  return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" }).format(time);
}

function reportAge(value: string | null | undefined, now: number): string {
  const time = publishedTime(value);
  if (!Number.isFinite(time) || now <= 0) return "";
  const days = Math.floor((now - time) / 86_400_000);
  if (days < 0) return "";
  if (days === 0) return "24시간 이내";
  return `${days}일 전`;
}

function sessionTime(value: string): number {
  return new Date(value.includes("T") ? value : `${value.replace(" ", "T")}+09:00`).getTime();
}

function shortBrief(text: string): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= 240) return clean;
  const sentences = clean.match(/[^.!?。]+[.!?。]?/g)?.map((sentence) => sentence.trim()).filter(Boolean) ?? [];
  const complete = sentences.slice(0, 2).join(" ");
  if (complete.length >= 100 && complete.length <= 260) return complete;
  const boundary = clean.lastIndexOf(" ", 240);
  return `${clean.slice(0, boundary > 170 ? boundary : 240).trimEnd()}…`;
}

function newestFirst<T extends { publishedAt?: string | null }>(items: T[]): T[] {
  return items.toSorted((left, right) => publishedTime(right.publishedAt) - publishedTime(left.publishedAt));
}

function groupByPublishedDay<T extends { publishedAt?: string | null }>(items: T[]): Array<[string, T[]]> {
  const groups = new Map<string, T[]>();
  newestFirst(items).forEach((item) => {
    const key = publishedDay(item.publishedAt);
    groups.set(key, [...(groups.get(key) ?? []), item]);
  });
  return [...groups.entries()];
}

function teamModalContent(item: TeamContent): ModalContent {
  return {
    id: item.id,
    context: item.team,
    source: item.source,
    title: item.title,
    url: item.url,
    summary: item.summary,
    detailedSummary: item.detailedSummary,
    participants: item.participants,
    colour: item.colour,
    detailLabel: "원문 구조별 상세 한국어 요약",
  };
}

function newsModalContent(article: NewsArticle, colour: string, driverName?: string): ModalContent {
  return {
    id: article.id,
    context: driverName ?? "F1 미디어",
    source: article.outlet,
    title: article.title,
    url: article.url,
    summary: article.summary,
    detailedSummary: article.detailedSummary,
    participants: [driverName, article.author].filter((value): value is string => Boolean(value)),
    colour,
    detailLabel: "기사 구조별 상세 한국어 요약",
  };
}

function videoModalContent(video: Video, colour: string, driverName: string): ModalContent {
  const hasSummary = Boolean(video.summary && video.detailedSummary);
  return {
    id: video.id,
    context: driverName,
    source: video.source,
    title: video.title,
    url: video.url,
    summary: video.summary ?? `${driverName} 선수가 등장하는 ${video.category} 영상이다. 아직 요약 가능한 공개 자막을 확인하지 못했다.`,
    detailedSummary: video.detailedSummary ?? `영상 정보\n${video.title}은(는) ${video.participants.join(" · ")} 관련 영상으로 분류되어 있다. 재생 시간 표시는 ${video.duration}이다.\n\n요약 상태\n${video.transcriptStatus === "unavailable" ? "공개 자막이 없거나 자막을 가져올 수 없어 내용을 임의로 요약하지 않았다." : video.transcriptStatus === "failed" ? "공개 자막 수집이 일시적으로 실패했다. 다음 배치에서 다시 시도하며, 확인되지 않은 영상 내용은 임의로 만들지 않는다." : "공개 자막 수집과 한국어 요약을 기다리는 중이다."}`,
    participants: video.participants,
    colour,
    detailLabel: hasSummary ? "공개 자막 기반 상세 한국어 요약" : "영상 정보와 요약 상태",
  };
}

function Tyre({ compound, age }: { compound: string; age: number }) {
  return (
    <span className={`tyre tyre-${compound.toLowerCase()}`}>
      {compound.slice(0, 1)} <small>{age}L</small>
    </span>
  );
}

function ContentDetailModal({ item, onClose }: { item: ModalContent; onClose: () => void }) {
  const detailSections = item.detailedSummary
    .split(/\n\s*\n/)
    .map((section) => section.split("\n").filter(Boolean))
    .filter((section) => section.length > 0);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [onClose]);

  return (
    <div className="content-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-describedby="content-modal-summary" aria-labelledby="content-modal-title" aria-modal="true" className="content-modal" role="dialog" style={{ "--team-colour": item.colour } as React.CSSProperties}>
        <button aria-label="상세 내용 닫기" autoFocus className="modal-close" onClick={onClose} type="button">×</button>
        <div className="content-modal-scroll">
          <div className="modal-meta"><span>{item.context}</span><em>{item.source}</em></div>
          <h3 id="content-modal-title">{item.title}</h3>
          <div className="modal-summary" id="content-modal-summary">
            <small>한눈에 보기</small>
            <p>{item.summary}</p>
          </div>
          <div className="modal-detail">
            <small>{item.detailLabel}</small>
            {detailSections.map((section, index) => (
              <article key={`${section[0]}-${index}`}>
                <h4>{section.length > 1 ? section[0] : `핵심 내용 ${index + 1}`}</h4>
                <p>{section.length > 1 ? section.slice(1).join(" ") : section[0]}</p>
              </article>
            ))}
          </div>
          {item.participants.length > 0 && <p className="modal-participants">{item.participants.join(" · ")}</p>}
          <a className="modal-source-link" href={item.url} rel="noreferrer" target="_blank">{item.source}에서 원문 보기 ↗</a>
        </div>
      </section>
    </div>
  );
}

export function Dashboard({
  initialSection = "weekend",
  initialEventSlug,
  initialInterviewSection = "press",
}: {
  initialSection?: MainSection;
  initialEventSlug?: string;
  initialInterviewSection?: InterviewSection;
}) {
  const router = useRouter();
  const [event, setEvent] = useState<EventDetail>(demoEvent);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [source, setSource] = useState<"sample" | "api">("sample");
  const [activeVideo, setActiveVideo] = useState(event.videos[0]?.id);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [activeTeam, setActiveTeam] = useState<string | null>(null);
  const [paddockView, setPaddockView] = useState<"team" | "driver">("team");
  const [activeOutlet, setActiveOutlet] = useState("all");
  const [activeDriver, setActiveDriver] = useState<string | null>(null);
  const [selectedContent, setSelectedContent] = useState<ModalContent | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const activeSection = initialSection;
  const [interviewSection, setInterviewSection] = useState<InterviewSection>(initialInterviewSection);
  const [championship, setChampionship] = useState<ChampionshipSnapshot | null>(null);
  const [championshipLoading, setChampionshipLoading] = useState(true);
  const [glossaryQuery, setGlossaryQuery] = useState("");
  const [showAllReports, setShowAllReports] = useState(false);
  const [glossaryCategory, setGlossaryCategory] = useState<"전체" | GlossaryCategory>("전체");
  const teamStripRef = useRef<HTMLDivElement>(null);
  const paddockSelectionChangedRef = useRef(false);

  useEffect(() => {
    setCurrentTime(Date.now());
    const clock = window.setInterval(() => setCurrentTime(Date.now()), 60_000);
    return () => {
      window.clearInterval(clock);
    };
  }, []);

  useEffect(() => {
    setInterviewSection(initialInterviewSection);
    if (initialInterviewSection === "drivers") setPaddockView("driver");
    if (initialInterviewSection === "teams") setPaddockView("team");
  }, [initialInterviewSection]);

  useEffect(() => {
    const controller = new AbortController();
    setChampionshipLoading(true);
    fetch(`${API_BASE}/standings/${event.season}/${event.round}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Standings unavailable");
        return response.json() as Promise<ChampionshipSnapshot>;
      })
      .then(setChampionship)
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setChampionship(null);
      })
      .finally(() => setChampionshipLoading(false));
    return () => controller.abort();
  }, [event.round, event.season]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    Promise.all([
      fetch(`${API_BASE}/events/${initialEventSlug ?? "featured"}`, { signal: controller.signal }),
      fetch(`${API_BASE}/events`, { signal: controller.signal }),
    ])
      .then(async ([featuredResponse, eventsResponse]) => {
        if (!featuredResponse.ok || !eventsResponse.ok) throw new Error("API unavailable");
        return Promise.all([featuredResponse.json() as Promise<EventDetail>, eventsResponse.json() as Promise<EventSummary[]>]);
      })
      .then(([featured, calendar]) => {
        setEvent(featured);
        setEvents(calendar);
        setActiveVideo(featured.videos[0]?.id);
        setActiveTeam(null);
        setActiveOutlet("all");
        setActiveDriver(null);
        paddockSelectionChangedRef.current = false;
        setSource("api");
      })
      .catch(() => setSource("sample"))
      .finally(() => {
        if (active) setIsInitialLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [initialEventSlug]);

  const selectedVideo = event.videos.find((video) => video.id === activeVideo) ?? event.videos[0];
  const classifiedDrivers = event.eventDrivers.filter((driver) => driver.resultPosition != null).toSorted((left, right) => (left.resultPosition ?? 99) - (right.resultPosition ?? 99));
  const raceRows = event.drivers.length > 0 ? event.drivers : classifiedDrivers.map((driver) => ({ position: driver.resultPosition ?? 99, code: driver.code, team: driver.team, colour: driver.colour, gap: driver.resultStatus, compound: null, tyreAge: null }));
  const raceComplete = classifiedDrivers.length > 0 || (event.drivers.length > 0 && event.sessions.some((session) => session.shortName === "R" && session.status === "done"));
  const mediaWindowOpen = !event.mediaOpenAt || (currentTime > 0 && currentTime >= new Date(event.mediaOpenAt).getTime());
  const teams = useMemo(() => {
    const seen = new Map<string, { code: string; name: string; colour: string; drivers: EventDetail["eventDrivers"] }>();
    event.eventDrivers.forEach((driver) => {
      const identity = normalizedIdentity(driver.teamCode || driver.team);
      const current = seen.get(identity) ?? { code: driver.teamCode, name: driver.team, colour: driver.colour, drivers: [] };
      current.drivers.push(driver);
      seen.set(identity, current);
    });
    event.teamContent.forEach((item) => {
      const identity = normalizedIdentity(item.teamCode || item.team);
      if (!seen.has(identity)) seen.set(identity, { code: item.teamCode, name: item.team, colour: item.colour, drivers: [] });
    });
    championship?.drivers.forEach((standing) => {
      const identity = normalizedIdentity(standing.teamCode || standing.team);
      const current = seen.get(identity) ?? { code: standing.teamCode, name: standing.team, colour: standingTeamColour(standing.teamCode, standing.team), drivers: [] };
      if (!current.drivers.some((driver) => driver.code === standing.code)) current.drivers.push({
        id: `${event.slug}-${standing.code}`,
        code: standing.code,
        name: standing.name,
        number: DRIVER_NUMBERS[standing.code] ?? 0,
        nationality: "",
        profileUrl: null,
        team: current.name,
        teamCode: current.code,
        colour: current.colour,
        resultPosition: null,
        resultStatus: "entered",
        points: 0,
        previousSeasonRank: standing.position,
      });
      seen.set(identity, current);
    });
    const constructorPositions = new Map<string, number>();
    championship?.constructors.forEach((standing) => {
      constructorPositions.set(normalizedIdentity(standing.teamCode), standing.position);
      constructorPositions.set(normalizedIdentity(standing.team), standing.position);
    });
    const driverPositions = new Map(championship?.drivers.map((driver) => [driver.code, driver.position]) ?? []);
    return [...seen.values()]
      .map((team) => ({
        ...team,
        drivers: team.drivers.toSorted((left, right) =>
          (driverPositions.get(left.code) ?? left.previousSeasonRank ?? 999) -
          (driverPositions.get(right.code) ?? right.previousSeasonRank ?? 999)
        ),
      }))
      .toSorted((left, right) => {
        const leftPosition = constructorPositions.get(normalizedIdentity(left.code)) ?? constructorPositions.get(normalizedIdentity(left.name)) ?? 999;
        const rightPosition = constructorPositions.get(normalizedIdentity(right.code)) ?? constructorPositions.get(normalizedIdentity(right.name)) ?? 999;
        return leftPosition - rightPosition || left.name.localeCompare(right.name);
      });
  }, [championship, event.eventDrivers, event.teamContent]);

  useEffect(() => {
    if (championshipLoading || teams.length === 0) return;
    const teamExists = teams.some((team) => team.code === activeTeam);
    if (!paddockSelectionChangedRef.current || !teamExists) setActiveTeam(teams[0].code);
  }, [activeTeam, championshipLoading, teams]);

  useEffect(() => {
    const strip = teamStripRef.current;
    if (!strip || !activeTeam || teams.length === 0) return;
    const frame = window.requestAnimationFrame(() => {
      if (activeTeam === teams[0].code) {
        strip.scrollTo({ left: 0, behavior: "auto" });
        return;
      }
      strip.querySelector<HTMLElement>(`[data-team-code="${CSS.escape(activeTeam)}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeTeam, teams]);

  useEffect(() => {
    if (interviewSection !== "drivers" || teams.length === 0) return;
    const activeTeamEntry = teams.find((team) => team.code === activeTeam) ?? teams[0];
    if (!activeTeamEntry.drivers.some((driver) => driver.code === activeDriver)) setActiveDriver(activeTeamEntry.drivers[0]?.code ?? null);
  }, [activeDriver, activeTeam, interviewSection, teams]);
  const visibleTeamContent = newestFirst(activeTeam ? event.teamContent.filter((item) => item.teamCode === activeTeam) : []);
  const categoryLabel = (kind: string) => ({ interview: "미디어 인터뷰", "team-report": "팀 코멘트", video: "팀 영상", social: "소셜" }[kind] ?? kind);
  const outlets = useMemo(() => [...new Set(event.news.map((article) => article.outlet))], [event.news]);
  const visibleNews = newestFirst(activeOutlet === "all" ? event.news : event.news.filter((article) => article.outlet === activeOutlet));
  const newsCategoryLabel = (kind: string) => ({ "race-report": "레이스 리포트", analysis: "분석", interview: "인터뷰", feature: "기획", preview: "프리뷰", results: "결과" }[kind] ?? kind);
  const selectedDriver = teams.flatMap((team) => team.drivers).find((driver) => driver.code === activeDriver);
  const driverContent = selectedDriver ? event.teamContent.filter((item) => mentionsDriver(item.participants, selectedDriver)) : [];
  const driverInterviewContent = newestFirst(selectedDriver ? driverContent.filter((item) =>
    item.contentType === "interview" && (mentionsDriver([item.title], selectedDriver) || mentionsDriver(item.participants.slice(0, 1), selectedDriver))
  ) : []);
  const driverInterviewUrls = new Set(driverInterviewContent.map((item) => item.url));
  const driverInterviewNews = newestFirst(selectedDriver ? event.news.filter((article) =>
    article.category === "interview" &&
    article.driverCodes.includes(selectedDriver.code) &&
    mentionsDriver([article.title, ...article.tags], selectedDriver) &&
    !driverInterviewUrls.has(article.url)
  ) : []);
  const driverInterviewItems = newestFirst([
    ...driverInterviewContent.map((item) => ({ kind: "team" as const, item, publishedAt: item.publishedAt })),
    ...driverInterviewNews.map((item) => ({ kind: "news" as const, item, publishedAt: item.publishedAt })),
  ]);
  const driverTeamContent = newestFirst(driverContent.filter((item) => item.contentType !== "interview"));
  const driverNews = newestFirst(selectedDriver ? event.news.filter((article) =>
    article.category !== "interview" && article.driverCodes.includes(selectedDriver.code) && mentionsDriver([article.title, ...article.tags], selectedDriver)
  ) : []);
  const sortedVideos = newestFirst(event.videos);
  const driverVideos = selectedDriver ? sortedVideos.filter((video) => video.participants.includes(selectedDriver.name)) : [];
  const pressConferenceNews = event.news.filter((article) =>
    article.tags.some((tag) => tag.includes("기자회견")) || article.title.includes("기자회견") || article.title.includes("프레스 컨퍼런스")
  );
  const weekendNews = event.news.filter((article) => article.category !== "interview" && articleMentionsEvent(article, event));
  const recentReports = newestFirst(weekendNews);
  const candidateReports = recentReports.filter((article) =>
    !/베팅|배당|판타지|오늘의 F1 역사/.test(article.title) &&
    !/확인할 수 없다|제공된 본문에는/.test(article.summary)
  );
  const freshReports = candidateReports.filter((article) => currentTime > 0 && currentTime - publishedTime(article.publishedAt) <= 48 * 60 * 60 * 1000 && publishedTime(article.publishedAt) <= currentTime);
  const prioritizedReports = freshReports.length > 0 ? freshReports : candidateReports;
  const leadReports = [...prioritizedReports.filter((article) => article.category === "race-report" || article.category === "analysis"), ...prioritizedReports.filter((article) => article.category !== "race-report" && article.category !== "analysis")].slice(0, 3);
  const latestReport = recentReports[0];
  const hasFreshReports = freshReports.length > 0;
  const todayKey = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: "Asia/Seoul" });
  const hasTodayReports = hasFreshReports && todayKey.format(publishedTime(freshReports[0].publishedAt)) === todayKey.format(currentTime);
  const weekendNewsByDate = groupByPublishedDay(showAllReports ? weekendNews : recentReports.slice(0, 9));
  const nextSession = currentTime > 0 ? event.sessions.filter((session) => sessionTime(session.startsAt) > currentTime).toSorted((left, right) => sessionTime(left.startsAt) - sessionTime(right.startsAt))[0] : undefined;
  const nextEvent = events.find((calendarEvent) => calendarEvent.season === event.season && calendarEvent.round === event.round + 1);
  const teamContentByDate = groupByPublishedDay(visibleTeamContent);
  const driverNewsByDate = groupByPublishedDay(driverNews);
  const driverTeamContentByDate = groupByPublishedDay(driverTeamContent);
  const driverInterviewItemsByDate = groupByPublishedDay(driverInterviewItems);
  const officialRaceHub = `https://www.formula1.com/en/racing/${event.season}/${event.slug.replace(`${event.season}-`, "")}`;
  const visibleGlossary = useMemo(() => {
    const query = glossaryQuery.trim().toLowerCase();
    return F1_GLOSSARY.filter((item) => {
      const matchesCategory = glossaryCategory === "전체" || item.category === glossaryCategory;
      const haystack = [item.term, item.korean, item.summary, ...item.aliases].join(" ").toLowerCase();
      return matchesCategory && (!query || haystack.includes(query));
    });
  }, [glossaryCategory, glossaryQuery]);

  if (isInitialLoading) {
    return (
      <main className="initial-loader" aria-busy="true" aria-live="polite">
        <div className="initial-loader-mark">PB</div>
        <p>CURRENT RACE WEEKEND</p>
        <strong>오늘의 그랑프리를 불러오는 중</strong>
        <span />
      </main>
    );
  }

  return (
    <main>
      <header className="topbar">
        <Link className="brand" href={pageHref("weekend", event.slug)} aria-label="Paddock Brief 홈">
          <span className="brand-mark">PB</span>
          <span>Paddock Brief</span>
        </Link>
        <nav aria-label="주요 메뉴">
          <Link className={activeSection === "weekend" ? "active" : ""} href={pageHref("weekend", event.slug)}>Weekend</Link>
          <Link className={activeSection === "interviews" ? "active" : ""} href={pageHref("interviews", event.slug, interviewSection)}>Interviews</Link>
          <Link className={activeSection === "championship" ? "active" : ""} href={pageHref("championship", event.slug)}>Championship</Link>
          <Link className={activeSection === "live" ? "active" : ""} href={pageHref("live", event.slug)}>Live</Link>
          <Link className={activeSection === "glossary" ? "active" : ""} href={pageHref("glossary", event.slug)}>F1 용어집</Link>
        </nav>
        <label className="event-select-wrap"><span>{event.season} 시즌</span><select className="event-select" aria-label="그랑프리 선택" value={event.slug} onChange={(change) => router.push(pageHref(activeSection, change.target.value, interviewSection))}>
          {events.length === 0 && <option value={event.slug}>{event.name}</option>}
          {events.map((calendarEvent) => <option key={calendarEvent.slug} value={calendarEvent.slug}>R{calendarEvent.round} · {calendarEvent.name}</option>)}
        </select></label>
        <div className={`data-pill ${source}`}>{source === "api" ? "API connected" : "Sample mode"}</div>
      </header>

      <div className={`app-shell ${activeSection === "live" ? "live-shell" : ""}`}>
        <div className="dashboard-page">
      <section className={`hero ${activeSection === "weekend" ? "hero-weekend" : ""}`} id="top">
        <div>
          <p className="eyebrow">ROUND {String(event.round).padStart(2, "0")} · {event.season}</p>
          <h1>{event.name}</h1>
          <p className="hero-copy">{event.circuit}<br />{event.dateLabel}</p>
        </div>
        <div className="track-card">
          {event.trackMapUrl ? <Image src={event.trackMapUrl} alt={`${event.circuit} 트랙 레이아웃`} width={470} height={220} sizes="(max-width: 980px) 90vw, 470px" /> : <div className="track-orbit"><span /><span /><span /></div>}
          <div className="track-meta"><b>{event.circuit.toUpperCase()}</b><small>{event.country.toUpperCase()} · TRACK MAP</small></div>
        </div>
      </section>

      {activeSection === "weekend" && (
        <section className="section-page weekend-page" id="weekend">
          <div className="weekend-status" role="status">
            <div><p className="eyebrow">선택한 GP 상태</p><strong>{nextSession ? `다음 세션 · ${nextSession.name}` : "이 GP의 세션 일정이 지났습니다"}</strong><small>{nextSession ? `${nextSession.startsAt} KST 예정` : "아래 일정과 경기 자료는 선택한 GP의 기록입니다."}</small></div>
            {!nextSession && nextEvent && <Link href={pageHref("weekend", nextEvent.slug)}>다음 경기 · {nextEvent.name} →</Link>}
          </div>
          <section className={`brief-overview ${hasFreshReports ? "fresh" : "archive"}`} aria-labelledby="brief-overview-title">
            <div className="brief-overview-heading"><div><p className="eyebrow">PADDOCK BRIEF</p><h2 id="brief-overview-title">{hasTodayReports ? "오늘 달라진 이야기" : hasFreshReports ? "최근 보도" : "지난 보도"}</h2></div><span>{latestReport ? `마지막 발행 ${publishedStamp(latestReport.publishedAt)} · ${reportAge(latestReport.publishedAt, currentTime)}` : "게시된 보도 없음"}</span></div>
            {!hasFreshReports && latestReport && <p className="brief-stale-note">이 GP와 직접 관련된 보도가 최근 48시간 안에 발행되지 않았습니다. 아래 내용은 지난 브리핑입니다.</p>}
            {leadReports.length > 0 ? <div className="brief-leads">{leadReports.map((article, index) => <article key={article.id}>
              <div className="brief-lead-meta"><span>{String(index + 1).padStart(2, "0")} · {article.outlet} · {newsCategoryLabel(article.category)}</span><time dateTime={article.publishedAt ?? undefined}>발행 {publishedStamp(article.publishedAt)} · {reportAge(article.publishedAt, currentTime)}</time></div>
              <h3>{article.title}</h3>
              <p className="brief-short"><b>30초 요약 · 보도된 내용</b>{shortBrief(article.summary)}</p>
              <dl><div><dt>편집 판단</dt><dd>{article.category === "analysis" ? "원문의 분석을 요약한 글입니다. 별도 편집 판단은 아직 없습니다." : "이 보도에 대한 별도 편집 판단은 아직 없습니다."}</dd></div><div><dt>다음 확인</dt><dd>{nextSession ? `${nextSession.name} 이후 새 자료` : "공식 발표 또는 후속 보도 공개 시"}</dd></div></dl>
              <button onClick={() => setSelectedContent(newsModalContent(article, "var(--f1-red)"))} type="button">원문과 깊은 분석 보기 →</button>
            </article>)}</div> : <p className="brief-empty">이 GP에서 확인할 수 있는 보도가 아직 없습니다. 아래 세션 일정과 공식 레이스 허브를 확인하세요.</p>}
          </section>
          <div className="page-heading">
            <div><p className="eyebrow">RACE WEEKEND</p><h2>위켄드 가이드 · 레이스 센터</h2><p>세션 일정, 타이어, 경기 순위와 레이스 자료를 한곳에서 확인합니다.</p></div>
            <a href={officialRaceHub} rel="noreferrer" target="_blank">Formula 1 공식 레이스 허브 ↗</a>
          </div>
          <div className="weekend-days">
            {WEEKEND_DAYS.map((day) => {
              const sessions = event.sessions.filter((session) => sessionDay(session) === day);
              return (
                <article className="weekend-day" key={day}>
                  <header><span>{day === "금요일" ? "FRI" : day === "토요일" ? "SAT" : "SUN"}</span><div><h3>{day}</h3><small>{sessions.length} SESSIONS</small></div></header>
                  <div className="day-sessions">
                    {sessions.map((session) => <div className={session.status} key={session.shortName}><b>{session.shortName}</b><span>{session.name}</span><small>{session.startsAt}</small><em>{session.status === "live" ? "LIVE" : session.status === "done" ? "완료" : currentTime > 0 && sessionTime(session.startsAt) < currentTime ? "시간 경과" : "예정"}</em></div>)}
                  </div>
                  <p>{day === "금요일" ? "연습주행 페이스, 셋업 변화와 타이어 롱런을 확인합니다." : day === "토요일" ? "마지막 연습주행과 예선 결과, 결승 그리드를 정리합니다." : "레이스 결과, 전략, 타이어와 경기 후 반응을 함께 확인합니다."}</p>
                </article>
              );
            })}
          </div>
          <div className="weekend-data-grid" id="race-centre">
            <section className="panel timing-card">
              <div className="section-heading compact"><div><p className="eyebrow">{raceComplete ? "RACE RESULT" : "LIVE PREVIEW"}</p><h2>레이스 센터</h2></div>{raceRows.length > 0 && <span className="lap">{raceComplete ? "FINAL" : "LIVE"}</span>}</div>
              <div className="timing-list">
                {raceRows.length === 0 && <p className="empty-state">{currentTime > 0 && event.sessions.some((session) => session.shortName === "R" && sessionTime(session.startsAt) < currentTime) ? "레이스 일정은 지났지만 최종 순위가 아직 수집되지 않았습니다. 공식 레이스 허브에서 결과를 확인해 주세요." : "레이스 세션이 시작되면 순위, 사용 타이어와 타이어 랩 수가 표시됩니다."}</p>}
                {raceRows.map((driver) => (
                  <div className="driver-row" key={driver.code}>
                    <b className="position">{driver.position}</b>
                    <i style={{ background: driver.colour }} />
                    <div><b>{driver.code}</b><small>{driver.team}</small></div>
                    {driver.compound && driver.tyreAge != null ? <Tyre compound={driver.compound} age={driver.tyreAge} /> : <span className="tyre-data-unavailable">타이어 기록 없음</span>}
                    <span className="gap">{driver.gap}</span>
                  </div>
                ))}
              </div>
              {raceRows.length > 0 && <p className="status-line"><span /> {raceComplete ? "FINAL CLASSIFICATION" : "RACE DATA"} <em>{event.drivers.length > 0 ? "경기 데이터" : "저장된 결과"}</em></p>}
            </section>
            <div className="weekend-data-side">
              <section className="panel tyre-card">
                <div className="section-heading compact"><div><p className="eyebrow">PIRELLI ALLOCATION</p><h2>이번 주말 타이어</h2></div>{event.tyreSourceUrl && <a href={event.tyreSourceUrl} target="_blank" rel="noreferrer">공식 출처 ↗</a>}</div>
                <div className="allocation">
                  <div className="compound hard"><span>H</span><b>Hard</b><small>{event.tyreAllocation.hard}</small></div>
                  <div className="compound medium"><span>M</span><b>Medium</b><small>{event.tyreAllocation.medium}</small></div>
                  <div className="compound soft"><span>S</span><b>Soft</b><small>{event.tyreAllocation.soft}</small></div>
                </div>
              </section>
              <div className="briefing panel"><p className="eyebrow">RACE BRIEF</p>{event.summary.map((item, index) => <p key={item}><span>0{index + 1}</span>{item}</p>)}</div>
            </div>
          </div>
          <details className="weekend-report-details"><summary>전체 브리핑 · {weekendNews.length}건 펼치기 <span>날짜별 보도와 상세 요약</span></summary><div className="weekend-feed panel">
            <div className="section-heading compact"><div><p className="eyebrow">DAILY REPORTS</p><h2>날짜별 레이스 자료</h2></div><span>{weekendNews.length} ARTICLES</span></div>
            {weekendNewsByDate.map(([day, articles]) => (
              <section className="dated-group" key={day}>
                <div className="dated-group-heading"><h3>{day}</h3><span>{articles.length}건</span></div>
                <div className="compact-card-grid">
                  {articles.map((article) => <button key={article.id} onClick={() => setSelectedContent(newsModalContent(article, "var(--f1-red)"))} type="button"><span>{article.outlet} · {newsCategoryLabel(article.category)} · {publishedStamp(article.publishedAt)} · {reportAge(article.publishedAt, currentTime)}</span><b>{article.title}</b><small>{article.summary}</small><em>상세 요약 보기 ↗</em></button>)}
                </div>
              </section>
            ))}
            {weekendNews.length > 9 && <button className="reports-toggle" onClick={() => setShowAllReports((value) => !value)} type="button">{showAllReports ? "최근 9건만 보기" : `전체 ${weekendNews.length}건 보기`}</button>}
            {weekendNews.length === 0 && <p className="empty-state">아직 이 GP의 보도가 없습니다.</p>}
          </div></details>
        </section>
      )}

      {activeSection === "interviews" && <div className="content-grid single-column">
        <section className="panel interview-panel" id="interviews">
          <div className="section-heading">
            <div><p className="eyebrow">OFFICIAL VOICES</p><h2>인터뷰 & 브리핑</h2></div>
          </div>

          <div className="content-tabs" role="tablist" aria-label="인터뷰 자료 구분">
            <Link className={interviewSection === "press" ? "active" : ""} href={pageHref("interviews", event.slug, "press")} role="tab">프레스 컨퍼런스</Link>
            <Link className={interviewSection === "teams" ? "active" : ""} href={pageHref("interviews", event.slug, "teams")} onClick={() => { setInterviewSection("teams"); setPaddockView("team"); }} role="tab">팀 뉴스</Link>
            <Link className={interviewSection === "drivers" ? "active" : ""} href={pageHref("interviews", event.slug, "drivers")} onClick={() => { setInterviewSection("drivers"); setPaddockView("driver"); setActiveDriver((current) => current ?? event.eventDrivers[0]?.code ?? null); setActiveTeam((current) => current ?? event.eventDrivers[0]?.teamCode ?? null); }} role="tab">선수 뉴스</Link>
            <Link className={interviewSection === "videos" ? "active" : ""} href={pageHref("interviews", event.slug, "videos")} role="tab">인터뷰 영상</Link>
            <Link className={interviewSection === "media" ? "active" : ""} href={pageHref("interviews", event.slug, "media")} role="tab">전체 미디어</Link>
          </div>

          <div className={`media-window ${mediaWindowOpen ? "open" : "scheduled"}`} role="status">
            <span>{mediaWindowOpen ? "PADDOCK OPEN" : "MEDIA OPENS THURSDAY"}</span>
            <div>
              <b>{mediaWindowOpen ? "공식 인터뷰 수집 중" : `${event.mediaOpenLabel}부터`}</b>
              <small>{mediaWindowOpen ? "새 인터뷰와 팀 코멘트가 공개되는 대로 한국어 요약에 반영됩니다." : "레이스 주 목요일부터 드라이버 기자회견과 팀별 코멘트를 확인할 수 있습니다."}</small>
            </div>
          </div>

          {interviewSection === "press" && (
            <section className="press-conference-section">
              <div className="press-intro">
                <div><p className="eyebrow">OFFICIAL PRESS CONFERENCES</p><h3>프레스 컨퍼런스 한국어 정리</h3></div>
                <p>공식 회견문을 질문 흐름과 주제별로 자세히 정리합니다. 원문 전체의 대체 번역이 아니라 맥락을 보존한 구조별 한국어 요약이며, 각 카드에서 공식 원문으로 이동할 수 있습니다.</p>
              </div>
              {pressConferenceNews.length > 0 ? groupByPublishedDay(pressConferenceNews).map(([day, articles]) => (
                <section className="dated-group" key={day}>
                  <div className="dated-group-heading"><h3>{day}</h3><span>{articles.length}건</span></div>
                  <div className="news-grid">
                    {articles.map((article) => (
                      <button className="news-card press-card" key={article.id} onClick={() => setSelectedContent(newsModalContent(article, "var(--f1-red)"))} type="button">
                        <div className="news-meta"><b>{article.outlet}</b><span>공식 기자회견</span></div>
                        <h4>{article.title}</h4><p>{article.summary}</p>
                        <footer><small>{article.author || article.outlet}</small><b>한국어 정리 보기 ↗</b></footer>
                      </button>
                    ))}
                  </div>
                </section>
              )) : <p className="empty-state">이 그랑프리의 공식 프레스 컨퍼런스 원문이 게시되면 날짜별로 번역·정리됩니다.</p>}
            </section>
          )}

          {interviewSection === "videos" && <>
          <div className="video-stage">
            {selectedVideo?.youtubeId ? (
              <iframe
                src={`https://www.youtube-nocookie.com/embed/${selectedVideo.youtubeId}?cc_load_policy=1&cc_lang_pref=ko&hl=ko`}
                title={selectedVideo.title}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            ) : (
              <a className="video-placeholder" href={selectedVideo?.url} target="_blank" rel="noreferrer">
                <span className="play">▶</span>
                <span>공식 영상 열기</span>
                <small>{selectedVideo?.source}</small>
              </a>
            )}
            <div className="video-caption">
              <span>{selectedVideo?.category}</span>
              <h3>{selectedVideo?.title}</h3>
              <p>{selectedVideo?.participants.join(" · ")}</p>
              {selectedVideo && <button className="video-summary-button" onClick={() => setSelectedContent(videoModalContent(selectedVideo, "var(--f1-red)", selectedVideo.participants[0] ?? "F1 영상"))} type="button">{selectedVideo.detailedSummary ? "영상 한국어 요약 보기 ↗" : selectedVideo.transcriptStatus === "unavailable" ? "자막 없음 · 영상 정보 보기" : selectedVideo.transcriptStatus === "failed" ? "요약 재시도 예정 · 상태 보기" : "영상 요약 준비 중 · 상태 보기"}</button>}
            </div>
          </div>

          <div className="video-list">
            {sortedVideos.map((video) => (
              <button className={video.id === activeVideo ? "selected" : ""} key={video.id} onClick={() => setActiveVideo(video.id)} type="button">
                <span className="mini-play">▶</span>
                <span><small>{video.category}</small><b>{video.title}</b><em>{video.source} · {video.duration}</em></span>
              </button>
            ))}
          </div>
          </>}

          {teams.length > 0 && (interviewSection === "teams" || interviewSection === "drivers") && (
            <section className="team-content paddock-browser" aria-label="팀과 선수 통합 정보">
              <div className="team-content-heading">
                <div><p className="eyebrow">TEAM & DRIVER PADDOCK</p><h3>팀과 선수</h3></div>
                <span>{championship?.basisLabel ?? "STANDINGS ORDER"}</span>
              </div>
              <p className="paddock-guide">팀 이름을 누르면 팀 인터뷰를, 선수 코드를 누르면 해당 선수의 결과와 관련 자료를 보여줍니다.</p>
              <div className="paddock-team-strip" aria-label={`${championship?.basisLabel ?? "직전 시즌 순위"} 기준 팀과 선수 선택`} ref={teamStripRef}>
                {teams.map((team) => (
                  <div className={`paddock-team-switcher ${activeTeam === team.code ? "active" : ""}`} data-team-code={team.code} key={team.code} style={{ "--team-colour": team.colour } as React.CSSProperties}>
                    <button className={activeTeam === team.code && paddockView === "team" ? "selected" : ""} onClick={() => { paddockSelectionChangedRef.current = true; setActiveTeam(team.code); setActiveDriver(null); setPaddockView("team"); setInterviewSection("teams"); }} type="button">
                      <i /><TeamLogo teamCode={team.code} teamName={team.name} /><span>{team.name}</span><small>TEAM</small>
                    </button>
                    <div>
                      {team.drivers.map((driver) => (
                        <button aria-label={`${driver.name} 선수 정보`} className={activeDriver === driver.code && paddockView === "driver" ? "selected" : ""} key={driver.code} onClick={() => { paddockSelectionChangedRef.current = true; setActiveTeam(team.code); setActiveDriver(driver.code); setPaddockView("driver"); setInterviewSection("drivers"); }} type="button">
                          <span>{driver.code}</span><small>{driver.number}</small>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {paddockView === "team" ? (
                <div className="paddock-team-content" style={{ "--team-colour": teams.find((team) => team.code === activeTeam)?.colour ?? "var(--f1-red)" } as React.CSSProperties}>
                  <div className="paddock-view-heading"><span>TEAM VIEW</span><h4>{teams.find((team) => team.code === activeTeam)?.name}</h4><small>{visibleTeamContent.length}개의 인터뷰와 코멘트</small></div>
                  {teamContentByDate.map(([day, items]) => (
                    <section className="dated-group" key={day}>
                      <div className="dated-group-heading"><h3>{day}</h3><span>팀 뉴스 {items.length}건</span></div>
                      <div className="team-content-grid">
                        {items.map((item) => (
                          <button className="team-content-card" key={item.id} onClick={() => setSelectedContent(teamModalContent(item))} style={{ "--team-colour": item.colour } as React.CSSProperties} type="button">
                            <div className="team-card-header"><div><TeamLogo teamCode={item.teamCode} teamName={item.team} /><span>TEAM NEWS · {item.team}</span></div><em>{categoryLabel(item.contentType)}</em></div>
                            <h4>{item.title}</h4><p>{item.summary}</p>
                            <footer><small>{item.source}</small><small>{item.participants.slice(0, 3).join(" · ")}</small><b>상세 요약 보기 ↗</b></footer>
                          </button>
                        ))}
                      </div>
                    </section>
                  ))}
                  {visibleTeamContent.length === 0 && <p className="empty-state">이 팀의 인터뷰와 코멘트를 수집 중입니다.</p>}
                </div>
              ) : selectedDriver ? (
                <div className="driver-detail" style={{ "--driver-colour": selectedDriver.colour } as React.CSSProperties}>
                  <div className="driver-identity">
                    <span>{selectedDriver.number}</span>
                    <div><p>{selectedDriver.team}</p><h4>{selectedDriver.name}</h4><small>{selectedDriver.nationality} · {selectedDriver.code}</small></div>
                    <div className="driver-result"><small>RACE RESULT</small><b>{selectedDriver.resultStatus === "retired" ? "DNF" : selectedDriver.resultPosition ? `P${selectedDriver.resultPosition}` : "—"}</b><em>{selectedDriver.points} PTS</em></div>
                  </div>
                  <section className="driver-content-section">
                    <div className="dated-group-heading"><h3>선수 인터뷰</h3><span>INTERVIEWS · {driverInterviewContent.length + driverInterviewNews.length}</span></div>
                    {driverInterviewItemsByDate.map(([day, entries]) => <section className="dated-group" key={day}><div className="dated-group-heading minor"><h3>{day}</h3><span>{entries.length}건</span></div><div className="driver-links">{entries.map(({ kind, item }) => <button key={`${kind}-${item.id}`} onClick={() => setSelectedContent(kind === "team" ? teamModalContent(item) : newsModalContent(item, selectedDriver.colour, selectedDriver.name))} type="button"><span>DRIVER INTERVIEW · {kind === "team" ? item.source : item.outlet}</span><b>{item.title}</b><small>{item.summary}</small><em>인터뷰 상세 요약 보기 ↗</em></button>)}</div></section>)}
                    {driverInterviewContent.length + driverInterviewNews.length === 0 && <p className="content-kind-note">이 선수의 직접 인터뷰를 수집 중입니다.</p>}
                  </section>
                  <section className="driver-content-section">
                    <div className="dated-group-heading"><h3>선수 직접 관련 뉴스</h3><span>DRIVER NEWS · {driverNews.length}</span></div>
                    {driverNewsByDate.map(([day, articles]) => <section className="dated-group" key={day}><div className="dated-group-heading minor"><h3>{day}</h3><span>{articles.length}건</span></div><div className="driver-links">{articles.map((article) => <button key={article.id} onClick={() => setSelectedContent(newsModalContent(article, selectedDriver.colour, selectedDriver.name))} type="button"><span>DRIVER NEWS · {article.outlet} · {newsCategoryLabel(article.category)}</span><b>{article.title}</b><small>{article.summary}</small><em>상세 요약 보기 ↗</em></button>)}</div></section>)}
                  </section>
                  {driverTeamContent.length > 0 && <section className="driver-content-section team-reference">
                    <div className="dated-group-heading"><h3>소속팀 뉴스</h3><span>TEAM NEWS · 별도 분류</span></div>
                    <p className="content-kind-note">선수 이름이 포함됐지만 팀 전체의 공식 코멘트인 자료입니다. 선수 개인 인터뷰와 구분해 표시합니다.</p>
                    {driverTeamContentByDate.map(([day, items]) => <section className="dated-group" key={day}><div className="dated-group-heading minor"><h3>{day}</h3><span>{items.length}건</span></div><div className="driver-links">{items.map((item) => <button key={item.id} onClick={() => setSelectedContent(teamModalContent(item))} type="button"><span>TEAM NEWS · {item.source} · {categoryLabel(item.contentType)}</span><b>{item.title}</b><small>{item.summary}</small><em>팀 뉴스 요약 보기 ↗</em></button>)}</div></section>)}
                  </section>}
                  {driverVideos.length > 0 && <section className="driver-content-section"><div className="dated-group-heading"><h3>관련 영상</h3><span>VIDEO · {driverVideos.length}</span></div><div className="driver-links">{driverVideos.map((video) => <button key={video.id} onClick={() => setSelectedContent(videoModalContent(video, selectedDriver.colour, selectedDriver.name))} type="button"><span>VIDEO · {video.source}</span><b>{video.title}</b><small>{video.participants.join(" · ")}</small><em>영상 정보 보기 ↗</em></button>)}</div></section>}
                  {driverNews.length + driverInterviewContent.length + driverInterviewNews.length + driverTeamContent.length + driverVideos.length === 0 && <p className="empty-state">이 선수의 개별 인터뷰와 기사를 수집 중입니다.</p>}
                  {selectedDriver.profileUrl && <a className="driver-profile-link" href={selectedDriver.profileUrl} rel="noreferrer" target="_blank">Formula 1 선수 프로필 ↗</a>}
                </div>
              ) : null}
            </section>
          )}

          {interviewSection === "media" && event.news.length > 0 && (
            <section className="media-roundup" aria-label="F1 미디어 기사 모음">
              <div className="team-content-heading">
                <div><p className="eyebrow">MEDIA ROUNDUP</p><h3>F1 미디어 라운드업</h3></div>
                <span>{outlets.length} OUTLETS · {event.news.length} ARTICLES</span>
              </div>
              <div className="outlet-tabs" role="tablist" aria-label="매체 필터">
                <button className={activeOutlet === "all" ? "active" : ""} onClick={() => setActiveOutlet("all")} role="tab" type="button">전체</button>
                {outlets.map((outlet) => <button className={activeOutlet === outlet ? "active" : ""} key={outlet} onClick={() => setActiveOutlet(outlet)} role="tab" type="button">{outlet}</button>)}
              </div>
              <div className="news-grid">
                {visibleNews.map((article) => (
                  <button className="news-card" key={article.id} onClick={() => setSelectedContent(newsModalContent(article, "var(--f1-red)"))} type="button">
                    <div className="news-meta"><b>{article.outlet}</b><span>{newsCategoryLabel(article.category)}</span></div>
                    <h4>{article.title}</h4>
                    <p>{article.summary}</p>
                    <div className="news-tags">{article.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>
                    <footer><small>{article.author || article.outlet}</small><b>상세 요약 보기 ↗</b></footer>
                  </button>
                ))}
              </div>
            </section>
          )}

          {interviewSection === "press" && <div className="briefing">
            <p className="eyebrow">한국어 내용 가이드</p>
            {event.summary.map((item, index) => <p key={item}><span>0{index + 1}</span>{item}</p>)}
          </div>}
        </section>
      </div>}

      {activeSection === "championship" && <section className="section-page championship-page" id="championship">
        <div className="page-heading">
          <div><p className="eyebrow">CHAMPIONSHIP ORDER</p><h2>컨스트럭터 & 드라이버 순위</h2><p>선택한 라운드가 시작되기 직전의 챔피언십 순위입니다. 같은 기준이 팀·선수 뉴스 정렬에도 적용됩니다.</p></div>
          {championship && <span className="standings-basis">{championship.basisLabel}</span>}
        </div>
        {championshipLoading ? <p className="empty-state standings-loading">챔피언십 순위를 불러오는 중입니다…</p> : championship ? (
          <div className="standings-grid">
            <section className="panel standings-panel">
              <header><div><p className="eyebrow">CONSTRUCTORS</p><h3>컨스트럭터 챔피언십</h3></div><span>{championship.constructors.length} TEAMS</span></header>
              <div className="standings-list">
                {championship.constructors.map((standing) => <div className="standing-row constructor-standing" key={standing.teamCode} style={{ "--standing-colour": standingTeamColour(standing.teamCode, standing.team) } as React.CSSProperties}><b>{standing.position}</b><TeamLogo teamCode={standing.teamCode} teamName={standing.team} /><div><strong>{standing.team}</strong><small>{standing.nationality}</small></div><span>{standing.wins}<small>WINS</small></span><em>{standing.points}<small>PTS</small></em></div>)}
              </div>
            </section>
            <section className="panel standings-panel">
              <header><div><p className="eyebrow">DRIVERS</p><h3>드라이버 챔피언십</h3></div><span>{championship.drivers.length} DRIVERS</span></header>
              <div className="standings-list">
                {championship.drivers.map((standing) => <div className="standing-row driver-standing" key={standing.code} style={{ "--standing-colour": standingTeamColour(standing.teamCode, standing.team) } as React.CSSProperties}><b>{standing.position}</b><div><strong><i>{standing.code}</i>{standing.name}</strong><small>{standing.team}</small></div><span>{standing.wins}<small>WINS</small></span><em>{standing.points}<small>PTS</small></em></div>)}
              </div>
            </section>
          </div>
        ) : <p className="empty-state standings-loading">이 라운드의 직전 챔피언십 순위를 아직 불러올 수 없습니다.</p>}
      </section>}

      {activeSection === "live" && <LiveTiming event={event} />}

      {activeSection === "glossary" && <section className="section-page glossary-page" id="glossary">
        <div className="page-heading glossary-heading">
          <div><p className="eyebrow">F1 GLOSSARY</p><h2>레이스를 읽는 F1 용어집</h2><p>중계와 기사에서 자주 나오는 표현을 한국어 설명과 실제 레이스 상황으로 정리했습니다.</p></div>
          <label className="glossary-search"><span>용어 검색</span><input aria-label="F1 용어 검색" onChange={(change) => setGlossaryQuery(change.target.value)} placeholder="언더컷, DRS, 타이어…" type="search" value={glossaryQuery} /></label>
        </div>
        <div className="glossary-categories" role="tablist" aria-label="F1 용어 카테고리">
          {GLOSSARY_CATEGORIES.map((category) => <button aria-selected={glossaryCategory === category} className={glossaryCategory === category ? "active" : ""} key={category} onClick={() => setGlossaryCategory(category)} role="tab" type="button">{category}</button>)}
        </div>
        <div className="glossary-result-heading"><span>{visibleGlossary.length} TERMS</span><small>카드를 열면 상세 설명과 실전 예시를 볼 수 있습니다.</small></div>
        <div className="glossary-grid">
          {visibleGlossary.map((item) => <details className="glossary-card" key={item.term}>
            <summary><div><span>{item.category}</span><h3>{item.term}</h3><strong>{item.korean}</strong></div><i aria-hidden="true">＋</i></summary>
            <p>{item.summary}</p>
            <div className="glossary-detail"><section><small>자세히</small><p>{item.detail}</p></section><section><small>레이스에서 이렇게 나와요</small><p>{item.example}</p></section></div>
            <footer><small>연관 용어</small>{item.related.map((related) => <button key={related} onClick={(click) => { click.preventDefault(); setGlossaryCategory("전체"); setGlossaryQuery(related); }} type="button">{related}</button>)}</footer>
          </details>)}
        </div>
        {visibleGlossary.length === 0 && <p className="empty-state glossary-empty">검색 결과가 없습니다. 영문·한글 표현이나 다른 카테고리로 찾아보세요.</p>}
      </section>}

      <footer>
        <span>Paddock Brief · 개인용 비공식 프로젝트</span>
        <span>Data adapters: Jolpica · FastF1 · YouTube · FIA · Pirelli</span>
      </footer>
      {selectedContent && <ContentDetailModal item={selectedContent} onClose={() => setSelectedContent(null)} />}
        </div>
      </div>
    </main>
  );
}
