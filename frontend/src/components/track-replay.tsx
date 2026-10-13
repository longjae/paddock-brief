"use client";

import { useEffect, useMemo, useState } from "react";
import type { EventDetail } from "@/lib/types";
import { OfficialCircuitMap } from "@/components/official-circuit-map";
import { officialTrackMap } from "@/lib/official-track-maps";

type Point = { x: number; y: number };
type Replay = { available: true; sessionTime: string; trace: Point[]; positions: (Point & { number: number; code: string; team: string; colour: string })[]; focusNumber: number; car: { speed: number; rpm: number; gear: number; throttle: number; brake: number; drs: number | null } | null } |
  { available: false; reason: string };

export function TrackReplay({ event, selectedDriverNumber = 0 }: { event: EventDetail; selectedDriverNumber?: number }) {
  const [minute, setMinute] = useState(10);
  const [driverNumber, setDriverNumber] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [showOfficialMap, setShowOfficialMap] = useState(false);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [loading, setLoading] = useState(false);
  const race = event.sessions.find((session) => /race|grand prix|레이스/i.test(session.name) && !/sprint|스프린트/i.test(session.name));
  const hasEnded = race?.status === "done" || (race ? new Date(`${race.startsAt.replace(" ", "T")}:00+09:00`).getTime() < Date.now() - 5 * 60 * 60_000 : false);

  useEffect(() => {
    setMinute(10);
    setDriverNumber(0);
    setExpanded(false);
    setShowOfficialMap(false);
    setReplay(null);
  }, [event.slug]);

  useEffect(() => {
    if (selectedDriverNumber) setDriverNumber(selectedDriverNumber);
  }, [selectedDriverNumber]);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (key: KeyboardEvent) => { if (key.key === "Escape") setExpanded(false); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

  useEffect(() => {
    if (!hasEnded) return;
    const controller = new AbortController();
    setLoading(true);
    const params = new URLSearchParams({ season: String(event.season), country: event.country, raceStart: race!.startsAt, minute: String(minute), driver: String(driverNumber) });
    fetch(`/api/track-replay?${params}`, { signal: controller.signal })
      .then((response) => response.json() as Promise<Replay>)
      .then((data) => { if (!controller.signal.aborted) setReplay(data); })
      .catch(() => { if (!controller.signal.aborted) setReplay({ available: false, reason: "위치 기록을 불러오지 못했습니다." }); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [event.slug, event.season, event.country, race?.startsAt, minute, driverNumber, hasEnded]);

  const geometry = useMemo(() => {
    if (!replay?.available) return null;
    const xs = replay.trace.map((point) => point.x);
    const ys = replay.trace.map((point) => point.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const scale = Math.min(920 / Math.max(1, maxX - minX), 480 / Math.max(1, maxY - minY));
    const offsetX = (1000 - (maxX - minX) * scale) / 2;
    const offsetY = (560 - (maxY - minY) * scale) / 2;
    const convert = (point: Point) => ({ x: offsetX + (point.x - minX) * scale, y: 560 - (offsetY + (point.y - minY) * scale) });
    return { path: replay.trace.map((point, index) => { const p = convert(point); return `${index ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`; }).join(" "), convert };
  }, [replay]);

  return <section className={`panel track-replay ${expanded ? "expanded" : ""}`} role={expanded ? "dialog" : undefined} aria-modal={expanded || undefined} aria-label={expanded ? "트랙맵 확대" : undefined}><header><div><p className="eyebrow">TRACK REPLAY</p><h3>{showOfficialMap ? "공식 트랙맵" : "선수 위치 기록"}</h3></div><div className="track-replay-actions"><span>{showOfficialMap ? "F1 · FIA" : "OpenF1"}</span>{officialTrackMap(event.slug) && <button type="button" onClick={() => setShowOfficialMap((current) => !current)}>{showOfficialMap ? "위치 기록" : "공식 맵"}</button>}{hasEnded && <button type="button" onClick={() => setExpanded((current) => !current)} aria-label={expanded ? "지도 닫기" : "지도 확대"}>{expanded ? "닫기" : "확대"}</button>}</div></header>
    {showOfficialMap ? <OfficialCircuitMap event={event} /> : !hasEnded ? <p className="track-replay-note">이 세션의 실시간 좌표는 연결되지 않았습니다. 종료된 레이스는 위치 기록으로 다시 볼 수 있습니다.</p> : <>
      <label className="track-replay-control">레이스 시작 후 <strong>{minute}분</strong><input type="range" min="5" max="180" step="5" value={minute} onChange={(change) => setMinute(Number(change.target.value))} /></label>
      {loading && <p className="track-replay-note">위치 기록을 불러오는 중입니다…</p>}
      {!loading && replay && !replay.available && <p className="track-replay-note">{replay.reason}</p>}
      {replay?.available && geometry && <svg className="track-replay-map" viewBox="0 0 1000 560" role="img" aria-label={`레이스 시작 후 ${minute}분의 선수 위치 기록`}>
        <path d={geometry.path} fill="none" stroke="#343d47" strokeWidth="14" strokeLinecap="round" strokeLinejoin="round" />
        <path d={geometry.path} fill="none" stroke="#a7b0ba" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {replay.positions.map((position) => {
          const driver = event.eventDrivers.find((item) => item.number === position.number);
          const point = geometry.convert(position);
          return <g key={position.number} transform={`translate(${point.x} ${point.y})`}><title>{driver?.code || position.code} · {driver?.team || position.team}</title><circle r={position.number === replay.focusNumber ? "20" : "15"} fill={driver?.colour || position.colour} stroke="#0d1119" strokeWidth="4" />{position.number === replay.focusNumber && <text y="-25" textAnchor="middle" fill="#fff" fontSize="23" fontWeight="800" paintOrder="stroke" stroke="#0d1119" strokeWidth="4">{driver?.code || position.code}</text>}</g>;
        })}
      </svg>}
      {replay?.available && <div className="track-replay-telemetry"><label>선수 <select value={replay.focusNumber} onChange={(change) => setDriverNumber(Number(change.target.value))}>{replay.positions.map((position) => { const driver = event.eventDrivers.find((item) => item.number === position.number); return <option key={position.number} value={position.number}>{driver?.code || position.code}</option>; })}</select></label>
        {replay.car ? <><b>{replay.car.speed} <small>km/h</small></b><span>{replay.car.gear} <small>GEAR</small></span><span>{replay.car.rpm.toLocaleString()} <small>RPM</small></span><span>{replay.car.throttle}% <small>THROTTLE</small></span><span>{replay.car.brake ? "ON" : "OFF"} <small>BRAKE</small></span></> : <span>차량 데이터 없음</span>}
      </div>}
      {replay?.available && <p className="track-replay-source">기준 시각 {new Date(replay.sessionTime).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST · 약 3초 범위 · <a href="https://openf1.org/docs/" target="_blank" rel="noreferrer">OpenF1 위치 데이터</a> · 실시간 아님</p>}
    </>}
  </section>;
}
