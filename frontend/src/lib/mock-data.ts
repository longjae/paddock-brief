import type { EventDetail } from "./types";

export const demoEvent: EventDetail = {
  slug: "2026-singapore",
  season: 2026,
  round: 18,
  name: "Singapore Grand Prix",
  country: "Singapore",
  circuit: "Marina Bay Street Circuit",
  trackMapUrl: "https://media.formula1.com/content/dam/fom-website/2018-redesign-assets/Track%20icons%204x3/Singapore%20carbon.png",
  dateLabel: "2026-10-09 — 2026-10-11 · KST",
  mediaOpenAt: "2026-10-07T16:00:00+00:00",
  mediaOpenLabel: "10월 8일 목요일 · 개최지 현지시간",
  sessions: [
    { name: "Practice 1", shortName: "FP1", startsAt: "2026-10-09 18:30", status: "done" },
    { name: "Practice 2", shortName: "FP2", startsAt: "2026-10-09 22:00", status: "done" },
    { name: "Qualifying", shortName: "Q", startsAt: "2026-10-10 22:00", status: "live" },
    { name: "Race", shortName: "R", startsAt: "2026-10-11 21:00", status: "upcoming" }
  ],
  videos: [
    {
      id: "formula1-singapore-search",
      category: "공식 영상 채널",
      title: "싱가포르 GP 인터뷰·브리핑 영상",
      source: "Formula 1 YouTube",
      duration: "공개 후 자동 반영",
      url: "https://www.youtube.com/@Formula1/search?query=Singapore%202026%20interview",
      participants: ["Formula 1 official channel"]
    },
    {
      id: "fia-singapore-transcripts",
      category: "공식 기자회견 원문",
      title: "FIA 기자회견·인터뷰 자료",
      source: "FIA",
      duration: "공개 후 번역 대상",
      url: "https://www.fia.com/news/formula-1",
      participants: ["FIA Formula One World Championship"]
    }
  ],
  tyreAllocation: { hard: "C3", medium: "C4", soft: "C5" },
  tyreSourceUrl: "https://press.pirelli.com/tyre-compound-selections-for-baku-sepang-and-singapore/",
  summary: [
    "긴 피트레인 손실 때문에 원스톱과 트랙 포지션의 가치가 크다.",
    "야간 경기지만 높은 노면 온도와 후륜 과열이 주요 변수다.",
    "예선 트래픽과 세이프티카 확률이 전략 선택에 큰 영향을 준다."
  ],
  drivers: [],
  teamContent: [],
  news: [],
  eventDrivers: []
};
