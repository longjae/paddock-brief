"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import type { EventDetail, LiveTimingSnapshot } from "@/lib/types";
import { tyreImagePath } from "@/lib/tyre-image";
import { TrackReplay } from "@/components/track-replay";
import { OfficialCircuitMap } from "@/components/official-circuit-map";
import { LapComparison } from "@/components/lap-comparison";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const STATUS_LABEL: Record<LiveTimingSnapshot["connection"], string> = { disabled: "수집기 대기", offline: "오프라인", connecting: "연결 중", reconnecting: "재연결 중", live: "실시간" };
const TRACK_LABEL: Record<string, string> = { "1": "트랙 정상", "2": "황기", "4": "세이프티카", "5": "적기", "6": "가상 세이프티카", "7": "VSC 종료 중" };
type RadioTranscript = { status: "loading" | "ready" | "unavailable" | "failed"; text?: string | null; translation?: string | null; audioUrl?: string };
type MobilePanel = "timing" | "track" | "control" | "radio" | "laps";

function value(item: Record<string, string | number | boolean | null>, key: string): string {
  return item[key] === null || item[key] === undefined ? "" : String(item[key]);
}

function mergeRaceControl(
  current: LiveTimingSnapshot["raceControl"],
  incoming: LiveTimingSnapshot["raceControl"],
): LiveTimingSnapshot["raceControl"] {
  const messages = new Map<string, LiveTimingSnapshot["raceControl"][number]>();
  for (const message of [...current, ...incoming]) {
    const key = [value(message, "Utc"), value(message, "Message"), value(message, "Category"), value(message, "Flag")].join("|");
    messages.set(key, message);
  }
  return Array.from(messages.values()).sort((a, b) => value(b, "Utc").localeCompare(value(a, "Utc"))).slice(0, 100);
}

export function LiveTiming({ event }: { event: EventDetail }) {
  const [snapshot, setSnapshot] = useState<LiveTimingSnapshot | null>(null);
  const [clockTime, setClockTime] = useState(0);
  const [streamState, setStreamState] = useState<"opening" | "open" | "retrying">("opening");
  const [radioTranscripts, setRadioTranscripts] = useState<Record<string, RadioTranscript>>({});
  const [radioTranslationEnabled, setRadioTranslationEnabled] = useState(true);
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("timing");
  const [selectedDriverNumber, setSelectedDriverNumber] = useState(0);
  const [openRadioPath, setOpenRadioPath] = useState("");
  const [raceControlHistory, setRaceControlHistory] = useState<LiveTimingSnapshot["raceControl"]>([]);
  const raceControlSession = useRef("");

  useEffect(() => {
    setClockTime(Date.now());
    const interval = window.setInterval(() => setClockTime(Date.now()), 5_000);
    return () => window.clearInterval(interval);
  }, []);

  const acceptSnapshot = (state: LiveTimingSnapshot) => {
    setSnapshot(state);
    const sessionKey = `${event.slug}:${state.session.name || "unknown"}`;
    const isNewSession = raceControlSession.current !== sessionKey;
    let stored: LiveTimingSnapshot["raceControl"] = [];
    if (isNewSession) {
      raceControlSession.current = sessionKey;
      try { stored = JSON.parse(window.localStorage.getItem(`race-control:${sessionKey}`) || "[]") as LiveTimingSnapshot["raceControl"]; }
      catch { stored = []; }
    }
    setRaceControlHistory((current) => {
      return mergeRaceControl(isNewSession ? stored : current, state.raceControl ?? []);
    });
  };

  useEffect(() => {
    if (!raceControlSession.current || !raceControlHistory.length) return;
    try { window.localStorage.setItem(`race-control:${raceControlSession.current}`, JSON.stringify(raceControlHistory)); }
    catch { /* storage is optional */ }
  }, [raceControlHistory]);

  const loadRadioTranscript = (path: string, sessionPath: string, audioUrl: string) => {
    if (!path || radioTranscripts[path]) return;
    setRadioTranscripts((current) => ({ ...current, [path]: { status: "loading", audioUrl } }));
    fetch(`${API_BASE}/team-radio/transcript?path=${encodeURIComponent(path)}&sessionPath=${encodeURIComponent(sessionPath)}`)
      .then((response) => { if (!response.ok) throw new Error("transcript unavailable"); return response.json() as Promise<{ audioUrl: string; transcript?: string | null; translation?: string | null }>; })
      .then((result) => setRadioTranscripts((current) => ({ ...current, [path]: { status: result.transcript ? "ready" : "unavailable", text: result.transcript, translation: result.translation, audioUrl: result.audioUrl } })))
      .catch(() => setRadioTranscripts((current) => ({ ...current, [path]: { status: "failed" } })));
  };

  const radioSessionPath = snapshot?.teamRadio.length ? value(snapshot.teamRadio[0], "SessionPath") : "";
  useEffect(() => {
    if (!radioSessionPath) return;
    let active = true;
    const loadSaved = () => {
      fetch(`${API_BASE}/team-radio/transcripts?sessionPath=${encodeURIComponent(radioSessionPath)}`)
        .then((response) => { if (!response.ok) throw new Error("saved captions unavailable"); return response.json() as Promise<Array<{ path: string; transcript: string; translation: string | null }>>; })
        .then((rows) => {
          if (!active) return;
          setRadioTranscripts((current) => {
            const next = { ...current };
            for (const row of rows) next[row.path] = { status: "ready", text: row.transcript, translation: row.translation };
            return next;
          });
        })
        .catch(() => { /* saved captions are optional while the collector is catching up */ });
    };
    loadSaved();
    const interval = window.setInterval(loadSaved, 60_000);
    return () => { active = false; window.clearInterval(interval); };
  }, [radioSessionPath]);

  useEffect(() => {
    let active = true;
    raceControlSession.current = "";
    setRaceControlHistory([]);
    setRadioTranscripts({});
    setOpenRadioPath("");
    setMobilePanel("timing");
    setSelectedDriverNumber(0);
    const loadState = () => fetch(`${API_BASE}/events/${event.slug}/race-state`, { cache: "no-store" })
      .then((response) => { if (!response.ok) throw new Error("live state unavailable"); return response.json() as Promise<LiveTimingSnapshot>; })
      .then((state) => { if (active) acceptSnapshot(state); })
      .catch(() => { if (active) setStreamState("retrying"); });
    void loadState();
    const poll = window.setInterval(() => { void loadState(); }, 15_000);
    const stream = new EventSource(`${API_BASE}/events/${event.slug}/live-stream`);
    stream.addEventListener("open", () => active && setStreamState("open"));
    stream.addEventListener("timing", (message) => {
      if (!active) return;
      try { acceptSnapshot(JSON.parse((message as MessageEvent<string>).data) as LiveTimingSnapshot); setStreamState("open"); }
      catch { setStreamState("retrying"); }
    });
    stream.addEventListener("error", () => active && setStreamState("retrying"));
    return () => { active = false; window.clearInterval(poll); stream.close(); };
  }, [event.slug]);

  const raceSession = event.sessions.find((session) => session.shortName === "R");
  const upcomingRace = raceSession && new Date(`${raceSession.startsAt.replace(" ", "T")}:00+09:00`).getTime() > Date.now();
  const raceEnded = raceSession?.status === "done" || (raceSession ? new Date(`${raceSession.startsAt.replace(" ", "T")}:00+09:00`).getTime() < Date.now() - 5 * 60 * 60_000 : false);
  const sessionEnded = raceEnded || snapshot?.session.remaining === "00:00:00";
  const updatedLabel = useMemo(() => !snapshot?.updatedAt ? "아직 수신된 라이브 신호가 없습니다" : `${new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Seoul" }).format(new Date(snapshot.updatedAt))} KST ${sessionEnded ? "피드 확인" : "갱신"}`, [snapshot?.updatedAt, sessionEnded]);
  const connection = snapshot?.connection ?? (streamState === "retrying" ? "reconnecting" : "connecting");
  const feedAgeSeconds = snapshot?.updatedAt && clockTime ? Math.max(0, Math.floor((clockTime - new Date(snapshot.updatedAt).getTime()) / 1000)) : null;
  const feedStale = !sessionEnded && snapshot?.isLive && feedAgeSeconds !== null && feedAgeSeconds > 30;
  const statusLabel = upcomingRace ? "레이스 예정" : sessionEnded ? "종료 세션 · 마지막 기록" : feedStale ? "데이터 갱신 지연" : connection === "live" && !snapshot?.isLive ? "피드 연결 · 세션 대기" : STATUS_LABEL[connection];
  const weather = snapshot?.weather ?? {};

  return <section className="section-page live-page" id="live">
    <div className="page-heading live-heading"><div><p className="eyebrow">LIVE TIMING</p><h2>{event.name}<small>{snapshot?.session.name || "세션 연결 중"}</small></h2></div><div className={`live-connection ${sessionEnded ? "ended" : feedStale ? "stale" : snapshot?.isLive ? "connected" : connection}`} role="status"><span /><div><b>{statusLabel}</b><small>{updatedLabel}{feedStale ? ` · ${feedAgeSeconds}초 전` : ""}</small></div></div></div>
    {upcomingRace && <section className="live-upcoming" aria-label="선택한 그랑프리 일정"><div><p className="eyebrow">UPCOMING GRAND PRIX</p><strong>{event.name}</strong><span>{event.circuit} · {event.dateLabel}</span></div><div className="live-upcoming-sessions">{event.sessions.map((session) => <div key={session.shortName}><b>{session.shortName}</b><span>{session.name}</span><time>{session.startsAt} KST</time></div>)}</div></section>}
    {upcomingRace && <section className="panel live-upcoming-map" aria-label="선택한 그랑프리 공식 트랙맵"><header><div><p className="eyebrow">CIRCUIT MAP</p><h3>공식 트랙맵</h3></div></header><OfficialCircuitMap event={event} /></section>}
    {upcomingRace && <p className="live-upcoming-note">첫 세션이 시작되면 순위, 미니섹터, 레이스 컨트롤과 팀 라디오가 표시됩니다.</p>}
    {!upcomingRace && <>
    <div className="live-summary-strip">
      <article><span>LAP</span><b>{snapshot?.session.lap || "—"}<small> / {snapshot?.session.totalLaps || "—"}</small></b></article>
      <article><span>TIME REMAINING</span><b>{snapshot?.session.remaining || "—"}</b></article>
      <article className={`track-${snapshot?.trackStatus.code || "unknown"}`}><span>TRACK STATUS</span><b>{TRACK_LABEL[snapshot?.trackStatus.code || ""] || snapshot?.trackStatus.message || "정보 대기"}</b></article>
      <article><span>AIR / TRACK</span><b>{String(weather.AirTemp ?? "—")}° <small>/ {String(weather.TrackTemp ?? "—")}°</small></b></article>
    </div>
    <div className="live-record-strip" aria-label="세션 패스티스트 기록">
      <article><span>FASTEST LAP</span><b>{snapshot?.fastestLap?.time || "—"}</b><small>{snapshot?.fastestLap?.driver || "기록 대기"}</small></article>
      {[1, 2, 3].map((sector) => {
        const record = snapshot?.fastestSectors?.find((item) => item.sector === sector);
        return <article key={sector}><span>FASTEST S{sector}</span><b>{record?.time || "—"}</b><small>{record?.driver || "기록 대기"}</small></article>;
      })}
    </div>
    <nav className="live-mobile-nav" aria-label="라이브 화면 선택">
      {([ ["timing", "순위"], ["track", "트랙맵"], ["control", "레이스 컨트롤"], ["radio", "팀 라디오"], ["laps", "랩 비교"] ] as const).map(([panel, label]) => <button key={panel} type="button" aria-current={mobilePanel === panel ? "page" : undefined} onClick={() => setMobilePanel(panel)}>{label}</button>)}
    </nav>
    <div className="live-grid">
      <section className={`panel live-tower ${mobilePanel === "timing" ? "mobile-active" : ""}`}><header><div><p className="eyebrow">TIMING TOWER</p><h3>실시간 순위</h3></div><span>{snapshot?.drivers.length ?? 0} DRIVERS</span></header>
        <div className="live-sector-meta"><strong>타이밍 · 미니섹터</strong><p className="mini-sector-legend"><span className="yellow" />일반 기록 <span className="green" />개인 최고 <span className="purple" />전체 최고 <span className="pit" />피트 <span className="unknown" />미제공</p></div>
        <p className="mini-sector-help">막대 상태와 섹터 시간은 별도 신호입니다. 한쪽만 들어올 수 있습니다. 회색 막대는 구간 상태 미제공, ‘—’는 섹터 시간 미제공입니다.{sessionEnded ? " 현재는 종료된 세션의 마지막 수신값을 보여줍니다." : ""}</p>
        <div className="live-tower-head"><span>POS</span><span>DRIVER</span><span>LAST</span><span>BEST</span><span>INTERVAL</span><span>GAP</span><span>MINI SECTORS · S1 / S2 / S3</span><span>TYRE / STINT</span></div><div className="live-tower-list">
        {!snapshot?.drivers.length && <p className="empty-state">{raceEnded ? "이 GP의 레이스는 종료됐습니다. 저장된 라이브 순위가 없습니다. 트랙맵의 위치 기록과 위켄드의 최종 결과를 확인하세요." : "세션이 시작되면 실시간 순위가 표시됩니다. 현재는 라이브 수집기 연결을 기다리고 있습니다."}</p>}
        {snapshot?.drivers.map((driver) => <article className={`${driver.inPit ? "in-pit" : ""} ${driver.retired ? "retired" : ""}`} key={driver.number} style={{ "--driver-colour": driver.colour } as React.CSSProperties}>
          <b>{driver.position}</b>
          <div className="live-driver-name"><i /><strong>{driver.code}</strong><small>{driver.team}</small></div>
          <time>{driver.lastLap}</time><time>{driver.bestLap}</time>
          <em>{driver.inPit ? "PIT" : driver.interval}</em><em>{driver.retired ? "OUT" : driver.gap}</em>
          <div className="live-mobile-metrics"><span>최근 {driver.lastLap || "—"}</span><span>최고 {driver.bestLap || "—"}</span><span>간격 {driver.inPit ? "PIT" : driver.interval || "—"}</span></div>
          <button className="live-driver-track-link" type="button" onClick={() => { setSelectedDriverNumber(Number(driver.number)); setMobilePanel("track"); }}>트랙에서 보기 →</button>
          <div className="mini-sector-dashboard" aria-label={`${driver.code} 미니섹터와 섹터 시간`}>
            {[0, 1, 2].map((index) => <div className="mini-sector-group" key={index} aria-label={`${index + 1}섹터: ${driver.currentSectors?.[index] && driver.currentSectors[index] !== "—" ? driver.currentSectors[index] : "시간 미제공"}, ${driver.miniSectors?.[index]?.length ? "구간 상태 수신" : "구간 상태 미제공"}`}>
              <div className="mini-sector-bars" aria-label={`${index + 1}섹터 구간 상태`}>
                {driver.miniSectors?.[index]?.length ? driver.miniSectors[index].map((colour, segment) => <span className={colour} key={segment} title={`${index + 1}섹터 ${segment + 1}구간: ${colour === "unknown" ? "피드 상태 미제공" : colour}`} />) : <span className="unknown" title="구간 상태 미제공" />}
              </div>
              <span className={`mini-sector-time ${driver.sectorFlags?.[index]?.overallFastest ? "purple" : driver.sectorFlags?.[index]?.personalFastest ? "green" : ""}`} title={driver.currentSectors?.[index] && driver.currentSectors[index] !== "—" ? `${index + 1}섹터 ${driver.currentSectors[index]}` : `${index + 1}섹터 시간 미제공`}>{driver.currentSectors?.[index] || "—"}</span>
            </div>)}
          </div>
          <div className="live-tyre-dashboard" title={(driver.tyreHistory ?? []).map((tyre) => `${tyre.compound} ${tyre.laps}랩`).join(" → ")} aria-label={`${driver.compound} 타이어, ${driver.stint || 0}번째 스틴트, ${driver.tyreAge}랩 사용`}>
            <Image className="live-tyre-image" src={tyreImagePath(driver.compound)} alt="" width={38} height={38} />
            <span className="live-tyre-usage"><b>{driver.pitStops !== null && driver.pitStops !== undefined ? `${driver.pitStops} PIT` : `ST${driver.stint || "—"}`}</b><small>{driver.tyreAge} LAP</small></span>
          </div>
        </article>)}
      </div></section>
      <div className={`live-track-slot ${mobilePanel === "track" ? "mobile-active" : ""}`}><TrackReplay event={event} selectedDriverNumber={selectedDriverNumber} liveTrack={snapshot?.track} /></div>
    </div>
    <div className="live-feed-grid">
        <section className={`panel live-feed-panel control-panel ${mobilePanel === "control" ? "mobile-active" : ""}`}><header><div><p className="eyebrow">RACE CONTROL</p><h3>레이스 컨트롤</h3></div><span>{raceControlHistory.length} MESSAGES</span></header><div className="live-message-list">{!raceControlHistory.length && <p className="empty-state">공식 메시지를 기다리고 있습니다.</p>}{raceControlHistory.map((message, index) => <article key={`${value(message, "Utc")}-${value(message, "Message")}-${index}`}><time>{value(message, "Utc").slice(11, 19) || "—"}</time><p>{value(message, "Message") || value(message, "Category")}</p></article>)}</div></section>
        <section className={`panel live-feed-panel radio-panel ${mobilePanel === "radio" ? "mobile-active" : ""}`}><header><div><p className="eyebrow">TEAM RADIO</p><h3>팀 라디오</h3></div><label className="radio-translation-toggle"><span>한국어 번역</span><input checked={radioTranslationEnabled} onChange={(change) => setRadioTranslationEnabled(change.target.checked)} type="checkbox" /><i /></label></header><div className="live-message-list radio-list">{!snapshot?.teamRadio.length && <p className="empty-state">공개된 팀 라디오를 기다리고 있습니다.</p>}{snapshot?.teamRadio.map((radio, index) => {
          const path = value(radio, "Path");
          const sessionPath = value(radio, "SessionPath");
          const audioUrl = value(radio, "AudioUrl");
          const transcript = radioTranscripts[path];
          const isOpen = openRadioPath === path;
          const racingNumber = value(radio, "RacingNumber");
          const driver = snapshot?.drivers.find((item) => item.number === racingNumber);
          const utc = value(radio, "Utc");
          const published = utc ? new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" }).format(new Date(utc)) : "시간 정보 없음";
          return <article className="radio-card" key={`${utc}-${index}`} style={{ "--driver-colour": driver?.colour || "#e10600" } as React.CSSProperties}>
            <button className="radio-card-toggle" type="button" aria-expanded={isOpen} onClick={() => { setOpenRadioPath(isOpen ? "" : path); if (!isOpen && !transcript) loadRadioTranscript(path, sessionPath, audioUrl); }}><span className="radio-driver"><span>#{racingNumber || "—"}</span><span className="radio-driver-name"><small>{driver?.team || "FORMULA 1"}</small><b>{driver?.name || driver?.code || `CAR ${racingNumber || "—"}`}</b></span><time>{published}</time></span><span className="radio-expand-label">{isOpen ? "접기" : transcript?.status === "ready" ? "자막 있음 · 듣기" : "듣기 · 자막 확인"}</span></button>
            {isOpen && <><div className="radio-player">{(transcript?.audioUrl || audioUrl) && <audio controls preload="metadata" src={transcript?.audioUrl || audioUrl}>팀 라디오 오디오</audio>}</div>
            <div className="radio-transcript" role="status">{!transcript && <p>자막 제공 여부를 확인하는 중입니다…</p>}{transcript?.status === "loading" && <p>자막을 확인하는 중입니다…</p>}{transcript?.status === "unavailable" && <p>이 라디오의 자막은 아직 제공되지 않습니다. 음성으로 확인해 주세요.</p>}{transcript?.status === "failed" && <p>자막을 불러오지 못했습니다. 음성으로 확인해 주세요.</p>}{transcript?.status === "ready" && <>{radioTranslationEnabled && transcript.translation && <p className="translated"><i />{transcript.translation}</p>}<p className={radioTranslationEnabled && transcript.translation ? "original" : ""}><i />{transcript.text}</p><small>확인 가능한 발화만 담은 자동 자막입니다. 정확한 내용은 음성으로 확인하세요.</small></>}</div></>}
          </article>;
        })}</div></section>
    </div>
    </>}
    <div className={`live-lap-slot ${mobilePanel === "laps" ? "mobile-active" : ""}`}><LapComparison event={event} /></div>
    <p className="live-disclaimer">F1의 비공식 라이브 타이밍 피드를 사용합니다. 중계 화면보다 지연되거나 일부 항목이 제공되지 않을 수 있습니다. 최종 결과는 경기 종료 후 공식 자료로 보정합니다.</p>
  </section>;
}
