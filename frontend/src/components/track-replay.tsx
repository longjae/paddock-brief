"use client";

import { useEffect, useMemo, useState } from "react";
import type { EventDetail, LiveTimingSnapshot } from "@/lib/types";
import { OfficialCircuitMap } from "@/components/official-circuit-map";
import { officialTrackMap } from "@/lib/official-track-maps";

type Point = { x: number; y: number };
type Replay = { available: true; sessionTime: string; trace: Point[]; positions: (Point & { number: number; code: string; team: string; colour: string })[]; focusNumber: number; car: { speed: number; rpm: number; gear: number; throttle: number; brake: number; drs: number | null } | null } |
  { available: false; reason: string };

export function TrackReplay({ event, selectedDriverNumber = 0, liveTrack }: { event: EventDetail; selectedDriverNumber?: number; liveTrack?: LiveTimingSnapshot["track"] }) {
  const [minute, setMinute] = useState(10);
  const [driverNumber, setDriverNumber] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [showOfficialMap, setShowOfficialMap] = useState(false);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [loading, setLoading] = useState(false);
  const race = event.sessions.find((session) => /race|grand prix|레이스/i.test(session.name) && !/sprint|스프린트/i.test(session.name));
  const hasEnded = race?.status === "done" || (race ? new Date(`${race.startsAt.replace(" ", "T")}:00+09:00`).getTime() < Date.now() - 5 * 60 * 60_000 : false);
  const liveAgeSeconds = liveTrack?.sampledAt ? Math.max(0, Math.floor((Date.now() - new Date(liveTrack.sampledAt).getTime()) / 1000)) : null;
  const liveReady = liveAgeSeconds !== null && liveAgeSeconds <= 15 && !!liveTrack?.positions.length;

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
    if (!hasEnded || liveReady) return;
    const controller = new AbortController();
    setLoading(true);
    const params = new URLSearchParams({ season: String(event.season), country: event.country, raceStart: race!.startsAt, minute: String(minute), driver: String(driverNumber) });
    fetch(`/api/track-replay?${params}`, { signal: controller.signal })
      .then((response) => response.json() as Promise<Replay>)
      .then((data) => { if (!controller.signal.aborted) setReplay(data); })
      .catch(() => { if (!controller.signal.aborted) setReplay({ available: false, reason: "위치 기록을 불러오지 못했습니다." }); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [event.slug, event.season, event.country, race?.startsAt, minute, driverNumber, hasEnded, liveReady]);

  const livePositions = liveReady ? liveTrack!.positions.map((position) => {
    const driver = event.eventDrivers.find((item) => String(item.number) === position.number);
    return { ...position, number: Number(position.number), code: driver?.code || `#${position.number}`, team: driver?.team || "", colour: driver?.colour || "#e10600" };
  }) : [];
  const replayPositions = replay?.available ? replay.positions : [];
  const positions = liveReady ? livePositions : replayPositions;
  const focusNumber = positions.some((position) => position.number === driverNumber) ? driverNumber : positions[0]?.number ?? 0;
  const car = liveReady ? liveTrack?.cars[String(focusNumber)] ?? null : replay?.available ? replay.car : null;
  const trace = liveReady ? liveTrack?.trace ?? [] : replay?.available ? replay.trace : [];

  const geometry = useMemo(() => {
    if (trace.length < (liveReady ? 25 : 3)) return null;
    const boundsPoints = [...trace, ...positions];
    const xs = boundsPoints.map((point) => point.x);
    const ys = boundsPoints.map((point) => point.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const scale = Math.min(920 / Math.max(1, maxX - minX), 480 / Math.max(1, maxY - minY));
    const offsetX = (1000 - (maxX - minX) * scale) / 2;
    const offsetY = (560 - (maxY - minY) * scale) / 2;
    const convert = (point: Point) => ({ x: offsetX + (point.x - minX) * scale, y: 560 - (offsetY + (point.y - minY) * scale) });
    return { path: trace.map((point, index) => { const p = convert(point); return `${index ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`; }).join(" "), convert };
  }, [trace, positions, liveReady]);

  return <section className={`panel track-replay ${expanded ? "expanded" : ""}`} role={expanded ? "dialog" : undefined} aria-modal={expanded || undefined} aria-label={expanded ? "트랙맵 확대" : undefined}><header><div><p className="eyebrow">TRACK MAP</p><h3>{showOfficialMap ? "공식 트랙맵" : liveReady ? "실시간 선수 위치" : "선수 위치 기록"}</h3></div><div className="track-replay-actions"><span>{showOfficialMap ? "F1 · FIA" : liveReady ? "F1 LIVE" : "OpenF1"}</span>{officialTrackMap(event.slug) && <button type="button" onClick={() => setShowOfficialMap((current) => !current)}>{showOfficialMap ? "선수 위치" : "공식 맵"}</button>}{(hasEnded || liveReady) && <button type="button" onClick={() => setExpanded((current) => !current)} aria-label={expanded ? "지도 닫기" : "지도 확대"}>{expanded ? "닫기" : "확대"}</button>}</div></header>
    {showOfficialMap ? <OfficialCircuitMap event={event} /> : !hasEnded && !liveReady ? <p className="track-replay-note">{liveTrack?.sampledAt ? "위치 신호가 지연되고 있습니다. 새 좌표를 기다리는 중입니다." : "이 세션의 선수 위치 신호를 기다리고 있습니다."}</p> : <>
      {!liveReady && <label className="track-replay-control">레이스 시작 후 <strong>{minute}분</strong><input type="range" min="5" max="180" step="5" value={minute} onChange={(change) => setMinute(Number(change.target.value))} /></label>}
      {liveReady && !geometry && <p className="track-replay-note">트랙 윤곽을 수집하는 중입니다…</p>}
      {!liveReady && loading && <p className="track-replay-note">위치 기록을 불러오는 중입니다…</p>}
      {!liveReady && !loading && replay && !replay.available && <p className="track-replay-note">{replay.reason}</p>}
      {geometry && <svg className="track-replay-map" viewBox="0 0 1000 560" role="img" aria-label={liveReady ? "실시간 선수 위치" : `레이스 시작 후 ${minute}분의 선수 위치 기록`}>
        <path d={geometry.path} fill="none" stroke="#343d47" strokeWidth="14" strokeLinecap="round" strokeLinejoin="round" />
        <path d={geometry.path} fill="none" stroke="#a7b0ba" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {positions.map((position) => {
          const driver = event.eventDrivers.find((item) => item.number === position.number);
          const point = geometry.convert(position);
          return <g key={position.number} transform={`translate(${point.x} ${point.y})`}><title>{driver?.code || position.code} · {driver?.team || position.team}</title><circle r={position.number === focusNumber ? "20" : "15"} fill={driver?.colour || position.colour} stroke="#0d1119" strokeWidth="4" />{position.number === focusNumber && <text y="-25" textAnchor="middle" fill="#fff" fontSize="23" fontWeight="800" paintOrder="stroke" stroke="#0d1119" strokeWidth="4">{driver?.code || position.code}</text>}</g>;
        })}
      </svg>}
      {positions.length > 0 && <div className="track-replay-telemetry"><label>선수 <select value={focusNumber} onChange={(change) => setDriverNumber(Number(change.target.value))}>{positions.map((position) => { const driver = event.eventDrivers.find((item) => item.number === position.number); return <option key={position.number} value={position.number}>{driver?.code || position.code}</option>; })}</select></label>
        {car ? <><b>{car.speed} <small>km/h</small></b><span>{car.gear} <small>GEAR</small></span><span>{car.rpm.toLocaleString()} <small>RPM</small></span><span>{car.throttle}% <small>THROTTLE</small></span><span>{car.brake ? "ON" : "OFF"} <small>BRAKE</small></span></> : <span>차량 데이터 없음</span>}
      </div>}
      {liveReady && <p className="track-replay-source">F1 라이브 피드 · 위치 신호 {liveAgeSeconds}초 전 · 좌표는 대략적인 위치입니다.</p>}
      {!liveReady && replay?.available && <p className="track-replay-source">기준 시각 {new Date(replay.sessionTime).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST · 약 3초 범위 · <a href="https://openf1.org/docs/" target="_blank" rel="noreferrer">OpenF1 위치 데이터</a> · 실시간 아님</p>}
    </>}
  </section>;
}
