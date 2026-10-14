"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import type { EventDetail } from "@/lib/types";
import { tyreImagePath } from "@/lib/tyre-image";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const COMPOUNDS = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"] as const;
type Compound = typeof COMPOUNDS[number];
type Stint = { number: number | null; compound: string; startLap: number | null; endLap: number | null; tyreAgeAtStart: number };
type ResultDriver = { number: number; position: number | null; code: string; name: string; team: string; colour: string; laps: number; time: string | null; gap: number | string | null; status: string; stints: Stint[] };
type SessionData = { status: "upcoming" | "pending" | "published"; session: string; drivers: ResultDriver[]; maxLap: number; source: string };

function gapLabel(value: number | string | null, status: string, position: number | null) {
  if (status !== "CLASSIFIED") return status;
  if (position === 1) return "LEADER";
  if (typeof value === "number") return `+${value.toFixed(3)}`;
  return value || "—";
}

export function WeekendSessionResults({ event }: { event: EventDetail }) {
  const [selectedSession, setSelectedSession] = useState("R");
  const [selectedCompound, setSelectedCompound] = useState<Compound | null>(null);
  const [data, setData] = useState<SessionData | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    setSelectedSession(event.sessions.some((session) => session.shortName === "R") ? "R" : event.sessions[0]?.shortName ?? "R");
    setSelectedCompound(null);
  }, [event.slug, event.sessions]);

  useEffect(() => {
    if (!event.sessions.some((session) => session.shortName === selectedSession)) return;
    const controller = new AbortController();
    setData(null);
    setError(false);
    setLoading(true);
    fetch(`${API_BASE}/events/${event.slug}/sessions/${selectedSession}/results`, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("session unavailable"); return response.json() as Promise<SessionData>; })
      .then((result) => setData(result))
      .catch(() => { if (!controller.signal.aborted) setError(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [event.slug, event.sessions, selectedSession, retryToken]);

  const session = event.sessions.find((item) => item.shortName === selectedSession);
  const fallbackDrivers: ResultDriver[] = selectedSession === "R" && session?.status === "done" ?
    (event.drivers.length ? event.drivers.map((driver) => ({ number: 0, position: driver.position, code: driver.code, name: driver.name, team: driver.team, colour: driver.colour, laps: 0, time: null, gap: driver.gap, status: "CLASSIFIED", stints: [] })) :
      event.eventDrivers.filter((driver) => driver.resultPosition != null).map((driver) => ({ number: driver.number, position: driver.resultPosition ?? null, code: driver.code, name: driver.name, team: driver.team, colour: driver.colour, laps: 0, time: null, gap: driver.resultStatus, status: "CLASSIFIED", stints: [] }))) : [];
  const visibleData: SessionData | null = data?.status === "published" ? data : fallbackDrivers.length && (error || data?.status === "pending") ? { status: "published", session: selectedSession, drivers: fallbackDrivers, maxLap: 0, source: "저장된 레이스 순위" } : data;
  const maxLap = Math.max(1, visibleData?.maxLap ?? 0);
  const hasStints = visibleData?.drivers.some((driver) => driver.stints.length > 0);
  return <section className="panel weekend-results" aria-label="세션별 결과와 스틴트">
    <div className="section-heading compact"><div><p className="eyebrow">SESSION RESULTS · STINTS</p><h2>세션별 결과와 스틴트</h2></div><span className="lap">{visibleData?.status === "published" ? visibleData.source : session?.status === "upcoming" ? "UPCOMING" : "DATA WAIT"}</span></div>
    <div className="weekend-session-tabs" role="group" aria-label="세션 선택">{event.sessions.map((item) => <button key={item.shortName} type="button" className={selectedSession === item.shortName ? "active" : ""} aria-pressed={selectedSession === item.shortName} onClick={() => { setSelectedSession(item.shortName); setSelectedCompound(null); }}>{item.shortName}<small>{item.name}</small></button>)}</div>
    <p className="weekend-results-context">{session?.name ?? selectedSession} · {session?.startsAt ?? ""} KST · {visibleData?.status === "published" ? "최종 결과" : session?.status === "upcoming" ? "시작 전" : "결과 확인 중"}</p>
    {loading && <p className="empty-state">세션 기록을 불러오는 중입니다.</p>}
    {error && !fallbackDrivers.length && <div className="session-error"><p className="empty-state">OpenF1 세션 기록을 불러오지 못했습니다.</p><button type="button" onClick={() => setRetryToken((value) => value + 1)}>다시 시도</button></div>}
    {!loading && !error && visibleData?.status !== "published" && <p className="empty-state">{data?.status === "upcoming" || session?.status === "upcoming" ? "세션 시작 전입니다. 결과와 스틴트는 경기 후 공개 기록이 나오면 표시됩니다." : "이 세션의 공개 최종 결과가 아직 없습니다."}</p>}
    {visibleData?.status === "published" && <>
      <div className="session-result-head"><span>POS</span><span>DRIVER</span><span>TIME / GAP</span><span>LAPS</span></div>
      <div className="session-result-list">{visibleData.drivers.map((driver) => <div className="session-result-row" key={`${driver.code}-${driver.number}`} style={{ "--driver-colour": driver.colour } as React.CSSProperties}><b>{driver.position ?? "—"}</b><span><strong>{driver.code}</strong><small>{driver.team}</small></span><span>{driver.time || gapLabel(driver.gap, driver.status, driver.position)}</span><span>{driver.laps || "—"}</span></div>)}</div>
      <div className="stint-section"><div className="section-heading compact"><div><p className="eyebrow">TYRE HISTORY</p><h3>스틴트</h3></div><span className="lap">{hasStints ? `${maxLap} LAPS` : "기록 대기"}</span></div>
        <div className="stint-compounds" role="group" aria-label="타이어 종류 선택">{COMPOUNDS.map((compound) => <button key={compound} type="button" className={selectedCompound === compound ? "active" : ""} aria-pressed={selectedCompound === compound} onClick={() => setSelectedCompound(selectedCompound === compound ? null : compound)}><Image src={tyreImagePath(compound)} alt="" width={35} height={35} /><span>{compound}</span></button>)}</div>
        {selectedCompound && <div className="selected-tyre"><Image src={tyreImagePath(selectedCompound)} alt={`${selectedCompound} 타이어 이미지`} width={82} height={82} /><div><b>{selectedCompound} 타이어</b><small>{visibleData.drivers.reduce((count, driver) => count + driver.stints.filter((stint) => stint.compound === selectedCompound).length, 0)}개 스틴트 · 선택한 타이어 구간을 강조합니다.</small></div><button type="button" onClick={() => setSelectedCompound(null)}>전체 보기</button></div>}
        {!hasStints && <p className="empty-state">이 세션에서 공개된 스틴트 기록이 없습니다.</p>}
        {hasStints && <div className="stint-list">{visibleData.drivers.filter((driver) => driver.stints.length > 0).map((driver) => <div className="stint-row" key={driver.number}><b>{driver.code}</b><div className="stint-track" aria-label={`${driver.code} 타이어 스틴트`}>{driver.stints.map((stint, index) => {
          const start = Math.max(1, stint.startLap ?? 1);
          const end = Math.max(start, stint.endLap ?? start);
          return <div key={`${driver.number}-${stint.number ?? index}`} className={`stint-segment ${stint.compound.toLowerCase()} ${selectedCompound && selectedCompound !== stint.compound ? "dimmed" : ""}`} style={{ left: `${(start - 1) / maxLap * 100}%`, width: `${Math.max(1, (end - start + 1) / maxLap * 100)}%` }} title={`${driver.code} · ${stint.compound} · ${start}–${end}랩 · 시작 시 타이어 ${stint.tyreAgeAtStart}랩 사용`}><span>{end - start + 1}L</span></div>;
        })}</div><small>{driver.stints.length} ST</small></div>)}</div>}
        <p className="stint-note">막대는 세션 누적 랩 기준입니다. 스틴트 사이 공백은 타이어 기록이 없는 구간입니다. 타이어를 선택하면 해당 구간을 강조합니다.</p>
      </div>
    </>}
  </section>;
}
