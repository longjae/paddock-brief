"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { EventDetail, LiveTimingSnapshot } from "@/lib/types";
import { OfficialCircuitMap } from "@/components/official-circuit-map";
import { officialTrackMap } from "@/lib/official-track-maps";

type Point = { x: number; y: number };
type Car = { speed: number; rpm: number; gear: number; throttle: number; brake: number; drs: number | null };
type Standing = { number: number; position: number; code: string; team: string; colour: string };
type Frame = { time: string; positions: (Point & { number: number })[]; car: Car | null };
type ReplayEvent = { time: string; kind: "pit" | "control"; label: string };
type Replay = { available: true; lap: number; maxLap: number; focusNumber: number; frameSeconds: number; standings: Standing[]; trace: Point[]; frames: Frame[]; events: ReplayEvent[] } |
  { available: false; reason: string; maxLap?: number };

function cacheLap(cache: Map<string, Replay>, key: string, replay: Replay) {
  cache.delete(key);
  cache.set(key, replay);
  while (cache.size > 12) cache.delete(cache.keys().next().value!);
}

export function TrackReplay({ event, selectedDriverNumber = 0, liveTrack }: { event: EventDetail; selectedDriverNumber?: number; liveTrack?: LiveTimingSnapshot["track"] }) {
  const [lap, setLap] = useState(1);
  const [maxLap, setMaxLap] = useState(1);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(4);
  const [driverNumber, setDriverNumber] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [showOfficialMap, setShowOfficialMap] = useState(false);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const replayCache = useRef(new Map<string, Replay>());
  const race = event.sessions.find((session) => session.shortName === "R");
  const hasEnded = race?.status === "done" || (race ? new Date(`${race.startsAt.replace(" ", "T")}:00+09:00`).getTime() < Date.now() - 5 * 60 * 60_000 : false);
  const liveAgeSeconds = liveTrack?.sampledAt ? Math.max(0, Math.floor((Date.now() - new Date(liveTrack.sampledAt).getTime()) / 1000)) : null;
  const liveReady = liveAgeSeconds !== null && liveAgeSeconds <= 15 && !!liveTrack?.positions.length;

  useEffect(() => {
    setLap(1);
    setMaxLap(1);
    setFrameIndex(0);
    setPlaying(false);
    setPlaybackSpeed(4);
    setDriverNumber(0);
    setExpanded(false);
    setShowOfficialMap(false);
    setReplay(null);
    replayCache.current.clear();
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
    if (!hasEnded || liveReady || !race) return;
    const controller = new AbortController();
    setReplay(null);
    setFrameIndex(0);
    const cacheKey = `${event.slug}:${lap}:${driverNumber}`;
    const cached = replayCache.current.get(cacheKey);
    if (cached) {
      cacheLap(replayCache.current, cacheKey, cached);
      setReplay(cached);
      setMaxLap(cached.maxLap ?? 1);
      setLoading(false);
      return;
    }
    setLoading(true);
    const params = new URLSearchParams({ season: String(event.season), country: event.country, raceStart: race.startsAt, lap: String(lap), driver: String(driverNumber) });
    fetch(`/api/track-replay?${params}`, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("Replay unavailable"); return response.json() as Promise<Replay>; })
      .then((data) => { if (!controller.signal.aborted) { cacheLap(replayCache.current, cacheKey, data); setReplay(data); setMaxLap(data.maxLap ?? 1); if (!data.available) setPlaying(false); } })
      .catch(() => { if (!controller.signal.aborted) { setReplay({ available: false, reason: "위치 기록을 불러오지 못했습니다." }); setPlaying(false); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [event.slug, event.season, event.country, race?.startsAt, lap, driverNumber, hasEnded, liveReady, retry]);

  const replayReady = replay?.available ? replay : null;
  useEffect(() => {
    if (!playing || !replayReady || !race || lap >= replayReady.maxLap) return;
    const nextLap = lap + 1;
    const cacheKey = `${event.slug}:${nextLap}:${driverNumber}`;
    if (replayCache.current.has(cacheKey)) return;
    const controller = new AbortController();
    const params = new URLSearchParams({ season: String(event.season), country: event.country, raceStart: race.startsAt, lap: String(nextLap), driver: String(driverNumber) });
    fetch(`/api/track-replay?${params}`, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("Next lap unavailable"); return response.json() as Promise<Replay>; })
      .then((data) => { if (!controller.signal.aborted && data.available) cacheLap(replayCache.current, cacheKey, data); })
      .catch(() => { /* The next lap will be requested again when playback reaches it. */ });
    return () => controller.abort();
  }, [playing, replayReady, event.slug, event.season, event.country, race?.startsAt, lap, driverNumber]);
  useEffect(() => {
    if (!playing || !replayReady || !replayReady.frames.length) return;
    const timer = window.setTimeout(() => {
      if (frameIndex < replayReady.frames.length - 1) setFrameIndex(frameIndex + 1);
      else if (lap < replayReady.maxLap) setLap(lap + 1);
      else setPlaying(false);
    }, replayReady.frameSeconds * 1000 / playbackSpeed);
    return () => window.clearTimeout(timer);
  }, [playing, replayReady, frameIndex, lap, playbackSpeed]);

  const frame = replayReady?.frames[Math.min(frameIndex, replayReady.frames.length - 1)] ?? null;
  const recentEvents = frame ? replayReady?.events?.filter((item) => {
    const age = new Date(frame.time).getTime() - new Date(item.time).getTime();
    return age >= 0 && age < 20_000;
  }).slice(-2) ?? [] : [];
  const standings = replayReady?.standings ?? [];
  const livePositions = liveReady ? liveTrack!.positions.map((position) => {
    const driver = event.eventDrivers.find((item) => String(item.number) === position.number);
    return { ...position, number: Number(position.number), code: driver?.code || `#${position.number}`, team: driver?.team || "", colour: driver?.colour || "#e10600" };
  }) : [];
  const replayPositions = frame?.positions.map((position) => {
    const driver = standings.find((item) => item.number === position.number);
    return { ...position, code: driver?.code || `#${position.number}`, team: driver?.team || "", colour: driver?.colour || "#e10600" };
  }) ?? [];
  const positions = liveReady ? livePositions : replayPositions;
  const focusNumber = positions.some((position) => position.number === driverNumber) ? driverNumber :
    liveReady ? positions[0]?.number ?? 0 : replayReady?.focusNumber ?? standings[0]?.number ?? 0;
  const car = liveReady ? liveTrack?.cars[String(focusNumber)] ?? null : frame?.car ?? null;
  const trace = liveReady ? liveTrack?.trace ?? [] : replayReady?.trace ?? [];

  const geometry = useMemo(() => {
    if (trace.length < (liveReady ? 25 : 3)) return null;
    const xs = trace.map((point) => point.x);
    const ys = trace.map((point) => point.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const scale = Math.min(920 / Math.max(1, maxX - minX), 480 / Math.max(1, maxY - minY));
    const offsetX = (1000 - (maxX - minX) * scale) / 2;
    const offsetY = (560 - (maxY - minY) * scale) / 2;
    const convert = (point: Point) => ({ x: offsetX + (point.x - minX) * scale, y: 560 - (offsetY + (point.y - minY) * scale) });
    return { path: trace.map((point, index) => { const p = convert(point); return `${index ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`; }).join(" "), convert };
  }, [trace, liveReady]);

  return <section className={`panel track-replay ${expanded ? "expanded" : ""}`} role={expanded ? "dialog" : undefined} aria-modal={expanded || undefined} aria-label={expanded ? "트랙맵 확대" : undefined}><header><div><p className="eyebrow">TRACK MAP</p><h3>{showOfficialMap ? "공식 트랙맵" : liveReady ? "실시간 선수 위치" : "레이스 리플레이"}</h3></div><div className="track-replay-actions"><span>{showOfficialMap ? "F1 · FIA" : liveReady ? "F1 LIVE" : "OpenF1"}</span>{officialTrackMap(event.slug) && <button type="button" onClick={() => setShowOfficialMap((current) => !current)}>{showOfficialMap ? "선수 위치" : "공식 맵"}</button>}{(hasEnded || liveReady) && <button type="button" onClick={() => setExpanded((current) => !current)} aria-label={expanded ? "지도 닫기" : "지도 확대"}>{expanded ? "닫기" : "확대"}</button>}</div></header>
    {showOfficialMap ? <OfficialCircuitMap event={event} /> : !hasEnded && !liveReady ? <p className="track-replay-note">{liveTrack?.sampledAt ? "위치 신호가 지연되고 있습니다. 새 좌표를 기다리는 중입니다." : "이 세션의 선수 위치 신호를 기다리고 있습니다."}</p> : <>
      {!liveReady && <div className="track-replay-controls"><div className="track-replay-control-top"><button type="button" onClick={() => { if (!playing && replayReady && lap === maxLap && frameIndex === replayReady.frames.length - 1) setFrameIndex(0); setPlaying((value) => !value); }} disabled={!replayReady?.frames.length} aria-label={playing ? "리플레이 일시정지" : "리플레이 재생"}>{playing ? "Ⅱ 일시정지" : "▶ 재생"}</button><label>랩 <select aria-label="리플레이 랩 선택" value={lap} onChange={(change) => { setLap(Number(change.target.value)); setFrameIndex(0); }}>{Array.from({ length: Math.max(lap, maxLap) }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1} / {maxLap}</option>)}</select></label><label>속도 <select aria-label="리플레이 재생 속도" value={playbackSpeed} onChange={(change) => setPlaybackSpeed(Number(change.target.value))}>{[1, 2, 4, 8].map((speed) => <option key={speed} value={speed}>{speed}배</option>)}</select></label><span>{frame ? `${new Date(frame.time).toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul" })} KST` : "기록 대기"}</span></div><input aria-label="선택한 랩의 재생 위치" type="range" min="0" max={Math.max(0, (replayReady?.frames.length ?? 1) - 1)} value={frameIndex} disabled={!replayReady?.frames.length} onChange={(change) => { setPlaying(false); setFrameIndex(Number(change.target.value)); }} />{recentEvents.length > 0 && <div className="track-replay-events" aria-live="polite">{recentEvents.map((item) => <span className={item.kind} key={`${item.time}-${item.label}`} title={item.label}>{item.label}</span>)}</div>}</div>}
      {liveReady && !geometry && <p className="track-replay-note">트랙 윤곽을 수집하는 중입니다…</p>}
      {!liveReady && loading && <p className="track-replay-note">선택한 랩의 위치 기록을 불러오는 중입니다…</p>}
      {!liveReady && !loading && replay && !replay.available && <div className="track-replay-error"><p className="track-replay-note">{replay.reason}</p><button type="button" onClick={() => { replayCache.current.delete(`${event.slug}:${lap}:${driverNumber}`); setRetry((value) => value + 1); }}>다시 시도</button></div>}
      {geometry && <svg className="track-replay-map" viewBox="0 0 1000 560" role="img" aria-label={liveReady ? "실시간 선수 위치" : `${lap}랩 리플레이`}>
        <path d={geometry.path} fill="none" stroke="#343d47" strokeWidth="14" strokeLinecap="round" strokeLinejoin="round" />
        <path d={geometry.path} fill="none" stroke="#a7b0ba" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {positions.map((position) => {
          const point = geometry.convert(position);
          return <g key={position.number} transform={`translate(${point.x} ${point.y})`}><title>{position.code} · {position.team}</title><circle r={position.number === focusNumber ? "20" : "15"} fill={position.colour} stroke="#0d1119" strokeWidth="4" />{position.number === focusNumber && <text y="-25" textAnchor="middle" fill="#fff" fontSize="23" fontWeight="800" paintOrder="stroke" stroke="#0d1119" strokeWidth="4">{position.code}</text>}</g>;
        })}
      </svg>}
      {positions.length > 0 && <div className="track-replay-telemetry"><label>선수 <select aria-label="리플레이 선수 선택" value={focusNumber} onChange={(change) => { setDriverNumber(Number(change.target.value)); setFrameIndex(0); }}>{(liveReady ? positions : standings).map((position) => <option key={position.number} value={position.number}>{liveReady ? position.code : `P${"position" in position ? position.position : "—"} · ${position.code}`}</option>)}</select></label>
        {car ? <><b>{car.speed} <small>km/h</small></b><span>{car.gear} <small>GEAR</small></span><span>{car.rpm.toLocaleString()} <small>RPM</small></span><span>{car.throttle}% <small>THROTTLE</small></span><span>{car.brake ? "ON" : "OFF"} <small>BRAKE</small></span></> : <span>차량 데이터 없음</span>}
      </div>}
      {liveReady && <p className="track-replay-source">F1 라이브 피드 · 위치 신호 {liveAgeSeconds}초 전 · 좌표는 대략적인 위치입니다.</p>}
      {!liveReady && replayReady && <p className="track-replay-source">최종 순위 기준 선수 목록 · 약 2초 간격 위치 기록 · <a href="https://openf1.org/docs/" target="_blank" rel="noreferrer">OpenF1 데이터</a> · 실시간 아님</p>}
    </>}
  </section>;
}
