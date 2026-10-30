"use client";

import { useEffect, useMemo, useState } from "react";
import type { EventDetail } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
type DriverOption = { number: number; code: string; name: string; team: string; colour: string };
type Results = { status: "upcoming" | "pending" | "published"; drivers: DriverOption[] };
type Lap = { lap: number; duration: number | null; sectors: Array<number | null>; pitOut: boolean };
type LapData = { status: "upcoming" | "pending" | "published"; drivers: Array<{ number: number; laps: Lap[] }> };

async function comparisonResponse<T>(response: Response, fallback: string): Promise<T> {
  if (response.ok) return response.json() as Promise<T>;
  const payload = await response.json().catch(() => null);
  const code = payload?.detail?.code;
  const message = code === "openf1_access_limited"
    ? "OpenF1 공개 기록의 접근이 제한돼 랩 비교를 사용할 수 없습니다. 실시간 순위는 별도 F1 피드로 계속 표시됩니다. 세션 종료 후 다시 확인해 주세요."
    : code === "openf1_rate_limited"
      ? "OpenF1 요청 한도에 도달했습니다. 잠시 뒤 다시 시도해 주세요."
      : fallback;
  throw new Error(message);
}

function defaultSession(event: EventDetail): string {
  const completed = event.sessions.filter((session) => session.status === "done" || Date.now() - new Date(`${session.startsAt.replace(" ", "T")}:00+09:00`).getTime() > 2 * 60 * 60_000);
  return completed.at(-1)?.shortName ?? event.sessions[0]?.shortName ?? "R";
}

function validLap(lap: Lap): boolean {
  return !lap.pitOut && lap.duration !== null && lap.duration >= 40 && lap.duration <= 300;
}

function timeLabel(seconds: number | null): string {
  if (seconds === null) return "—";
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${(seconds % 60).toFixed(3).padStart(6, "0")}`;
}

function deltaLabel(seconds: number | null): string {
  if (seconds === null) return "—";
  return `${seconds >= 0 ? "+" : "−"}${Math.abs(seconds).toFixed(3)}`;
}

function stats(laps: Lap[]) {
  const clean = laps.filter(validLap);
  const durations = clean.map((lap) => lap.duration as number);
  return {
    clean,
    best: durations.length ? Math.min(...durations) : null,
    average: durations.length ? durations.reduce((sum, value) => sum + value, 0) / durations.length : null,
    sectors: [0, 1, 2].map((index) => {
      const values = clean.map((lap) => lap.sectors[index]).filter((value): value is number => typeof value === "number");
      return values.length ? Math.min(...values) : null;
    }),
  };
}

export function LapComparison({ event, initialSession }: { event: EventDetail; initialSession?: string }) {
  const [selectedSession, setSelectedSession] = useState(() => initialSession ?? defaultSession(event));
  const [results, setResults] = useState<Results | null>(null);
  const [driverA, setDriverA] = useState(0);
  const [driverB, setDriverB] = useState(0);
  const [lapData, setLapData] = useState<LapData | null>(null);
  const [resultsError, setResultsError] = useState("");
  const [lapsError, setLapsError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    setSelectedSession(initialSession ?? defaultSession(event));
    setResults(null);
    setLapData(null);
  }, [event.slug, event, initialSession]);

  useEffect(() => {
    if (!event.sessions.some((session) => session.shortName === selectedSession)) return;
    const controller = new AbortController();
    setResults(null);
    setLapData(null);
    setResultsError("");
    setDriverA(0);
    setDriverB(0);
    fetch(`${API_BASE}/events/${event.slug}/sessions/${selectedSession}/results`, { signal: controller.signal })
      .then((response) => comparisonResponse<Results>(response, "세션 결과를 불러오지 못했습니다."))
      .then((payload) => {
        if (controller.signal.aborted) return;
        setResults(payload);
        if (payload.status === "published") {
          setDriverA(payload.drivers[0]?.number ?? 0);
          setDriverB(payload.drivers[1]?.number ?? 0);
        }
      })
      .catch((error) => { if (!controller.signal.aborted) setResultsError(error instanceof Error ? error.message : "세션 결과를 불러오지 못했습니다."); });
    return () => controller.abort();
  }, [event.slug, event.sessions, selectedSession, retry]);

  useEffect(() => {
    if (!driverA || !driverB || driverA === driverB) return;
    const controller = new AbortController();
    setLapData(null);
    setLapsError("");
    fetch(`${API_BASE}/events/${event.slug}/sessions/${selectedSession}/laps?driver_a=${driverA}&driver_b=${driverB}`, { signal: controller.signal })
      .then((response) => comparisonResponse<LapData>(response, "랩 기록을 불러오지 못했습니다."))
      .then((payload) => { if (!controller.signal.aborted) setLapData(payload); })
      .catch((error) => { if (!controller.signal.aborted) setLapsError(error instanceof Error ? error.message : "랩 기록을 불러오지 못했습니다."); });
    return () => controller.abort();
  }, [event.slug, selectedSession, driverA, driverB, retry]);

  const optionA = results?.drivers.find((driver) => driver.number === driverA);
  const optionB = results?.drivers.find((driver) => driver.number === driverB);
  const first = useMemo(() => stats(lapData?.drivers.find((driver) => driver.number === driverA)?.laps ?? []), [lapData, driverA]);
  const second = useMemo(() => stats(lapData?.drivers.find((driver) => driver.number === driverB)?.laps ?? []), [lapData, driverB]);
  const lapNumbers = useMemo(() => Array.from(new Set([...first.clean, ...second.clean].map((lap) => lap.lap))).sort((a, b) => a - b), [first.clean, second.clean]);
  const limits = useMemo(() => {
    const durations = [...first.clean, ...second.clean].map((lap) => lap.duration as number);
    return { low: durations.length ? Math.floor(Math.min(...durations) - 1) : 0, high: durations.length ? Math.ceil(Math.max(...durations) + 1) : 1, maxLap: Math.max(1, ...lapNumbers) };
  }, [first.clean, second.clean, lapNumbers]);
  const plot = (laps: Lap[]) => laps.map((lap) => `${40 + (lap.lap - 1) / Math.max(1, limits.maxLap - 1) * 630},${162 - ((lap.duration as number) - limits.low) / Math.max(1, limits.high - limits.low) * 128}`).join(" ");
  const firstByLap = new Map(first.clean.map((lap) => [lap.lap, lap.duration as number]));
  const secondByLap = new Map(second.clean.map((lap) => [lap.lap, lap.duration as number]));

  return <section className="panel lap-comparison" aria-label="두 선수 랩 기록 비교">
    <header><div><p className="eyebrow">LAP COMPARISON</p><h3>랩 기록 비교</h3></div><a href="https://openf1.org/docs/" target="_blank" rel="noreferrer">데이터: OpenF1 ↗</a></header>
    <div className="lap-compare-controls"><label>세션<select aria-label="비교할 세션" value={selectedSession} onChange={(change) => setSelectedSession(change.target.value)}>{event.sessions.map((session) => <option key={session.shortName} value={session.shortName}>{session.shortName} · {session.name}</option>)}</select></label>
      <label>선수 A<select aria-label="첫 번째 선수" value={driverA} disabled={!results?.drivers.length} onChange={(change) => setDriverA(Number(change.target.value))}>{results?.drivers.map((driver) => <option key={driver.number} value={driver.number}>{driver.code} · {driver.name}</option>)}</select></label>
      <label>선수 B<select aria-label="두 번째 선수" value={driverB} disabled={!results?.drivers.length} onChange={(change) => setDriverB(Number(change.target.value))}>{results?.drivers.map((driver) => <option key={driver.number} value={driver.number}>{driver.code} · {driver.name}</option>)}</select></label>
      {(resultsError || lapsError) && <button type="button" onClick={() => setRetry((value) => value + 1)}>다시 시도</button>}
    </div>
    {resultsError && <p className="empty-state">{resultsError}</p>}
    {!results && !resultsError && <p className="empty-state">비교할 선수와 랩 기록을 불러오는 중입니다.</p>}
    {results?.status === "upcoming" && <p className="empty-state">이 세션은 아직 시작하지 않았습니다. 랩 기록은 세션 후 공개되면 비교할 수 있습니다.</p>}
    {results?.status === "pending" && <p className="empty-state">이 세션의 공개 결과가 아직 없습니다. 기록이 나오면 랩 비교를 사용할 수 있습니다.</p>}
    {results?.status === "published" && driverA === driverB && <p className="empty-state">서로 다른 선수 두 명을 선택하세요.</p>}
    {results?.status === "published" && driverA !== driverB && lapsError && <p className="empty-state">{lapsError}</p>}
    {results?.status === "published" && driverA !== driverB && !lapData && !lapsError && <p className="empty-state">랩 기록을 불러오는 중입니다.</p>}
    {lapData?.status === "pending" && <p className="empty-state">이 세션에서 공개된 랩 기록이 없습니다.</p>}
    {lapData?.status === "published" && first.clean.length + second.clean.length === 0 && <p className="empty-state">비교할 수 있는 유효 랩이 없습니다.</p>}
    {lapData?.status === "published" && first.clean.length + second.clean.length > 0 && <>
      <div className="lap-compare-summary">{[[optionA, first], [optionB, second]].map(([option, record], index) => {
        const driver = option as DriverOption | undefined;
        const item = record as ReturnType<typeof stats>;
        return <article key={driver?.number ?? index} style={{ "--lap-colour": driver?.colour ?? "#888" } as React.CSSProperties}><div><span>{index === 0 ? "A" : "B"}</span><b>{driver?.code ?? "—"}</b><small>{driver?.team ?? ""}</small></div><dl><div><dt>최고 랩</dt><dd>{timeLabel(item.best)}</dd></div><div><dt>평균 랩</dt><dd>{timeLabel(item.average)}</dd></div><div><dt>유효 랩</dt><dd>{item.clean.length}</dd></div></dl><p>최고 섹터 · {item.sectors.map((sector, sectorIndex) => `S${sectorIndex + 1} ${sector?.toFixed(3) ?? "—"}`).join(" · ")}</p></article>;
      })}</div>
      <div className="lap-compare-chart"><svg viewBox="0 0 700 195" role="img" aria-label={`${optionA?.code ?? "A"}와 ${optionB?.code ?? "B"}의 랩별 시간 추이`} preserveAspectRatio="none"><line x1="40" y1="34" x2="670" y2="34" /><line x1="40" y1="98" x2="670" y2="98" /><line x1="40" y1="162" x2="670" y2="162" /><text x="4" y="38">{timeLabel(limits.high)}</text><text x="4" y="166">{timeLabel(limits.low)}</text><text x="40" y="187">1 LAP</text><text x="632" y="187">{limits.maxLap} LAP</text>{first.clean.length > 1 && <polyline points={plot(first.clean)} stroke={optionA?.colour ?? "#e33"} />}{second.clean.length > 1 && <polyline points={plot(second.clean)} stroke={optionB?.colour ?? "#5bf"} />}</svg></div>
      <p className="lap-compare-note">피트 아웃랩, 시간이 없거나 40초 미만·5분 초과인 랩은 비교에서 제외했습니다. 같은 랩 번호끼리 차이를 계산합니다.</p>
      <div className="lap-compare-table"><div className="lap-compare-table-head"><span>LAP</span><span>{optionA?.code ?? "A"}</span><span>{optionB?.code ?? "B"}</span><span>차이 A−B</span></div>{lapNumbers.map((lap) => {
        const a = firstByLap.get(lap) ?? null;
        const b = secondByLap.get(lap) ?? null;
        return <div className="lap-compare-table-row" key={lap}><b>{lap}</b><span>{timeLabel(a)}</span><span>{timeLabel(b)}</span><strong className={a !== null && b !== null && a < b ? "faster" : ""}>{deltaLabel(a !== null && b !== null ? a - b : null)}</strong></div>;
      })}</div>
    </>}
  </section>;
}
