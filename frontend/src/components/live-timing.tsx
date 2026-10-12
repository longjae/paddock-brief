"use client";

import { useEffect, useMemo, useState } from "react";
import type { EventDetail, LiveTimingSnapshot } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const STATUS_LABEL: Record<LiveTimingSnapshot["connection"], string> = { disabled: "수집기 대기", offline: "오프라인", connecting: "연결 중", reconnecting: "재연결 중", live: "실시간" };
const TRACK_LABEL: Record<string, string> = { "1": "트랙 정상", "2": "황기", "4": "세이프티카", "5": "적기", "6": "가상 세이프티카", "7": "VSC 종료 중" };
type RadioTranscript = { status: "loading" | "ready" | "failed"; text?: string | null; translation?: string | null; audioUrl?: string };

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
  const [streamState, setStreamState] = useState<"opening" | "open" | "retrying">("opening");
  const [radioTranscripts, setRadioTranscripts] = useState<Record<string, RadioTranscript>>({});
  const [radioTranslationEnabled, setRadioTranslationEnabled] = useState(true);
  const [raceControlHistory, setRaceControlHistory] = useState<LiveTimingSnapshot["raceControl"]>([]);

  const acceptSnapshot = (state: LiveTimingSnapshot) => {
    setSnapshot(state);
    setRaceControlHistory((current) => {
      const merged = mergeRaceControl(current, state.raceControl ?? []);
      try { window.localStorage.setItem(`race-control:${event.slug}`, JSON.stringify(merged)); } catch { /* storage is optional */ }
      return merged;
    });
  };

  const loadRadioTranscript = (path: string, sessionPath: string, audioUrl: string) => {
    if (!path || radioTranscripts[path]) return;
    setRadioTranscripts((current) => ({ ...current, [path]: { status: "loading", audioUrl } }));
    fetch(`${API_BASE}/team-radio/transcript?path=${encodeURIComponent(path)}&sessionPath=${encodeURIComponent(sessionPath)}`)
      .then((response) => { if (!response.ok) throw new Error("transcript unavailable"); return response.json() as Promise<{ audioUrl: string; transcript?: string | null; translation?: string | null }>; })
      .then((result) => setRadioTranscripts((current) => ({ ...current, [path]: { status: "ready", text: result.transcript, translation: result.translation, audioUrl: result.audioUrl } })))
      .catch(() => setRadioTranscripts((current) => ({ ...current, [path]: { status: "failed" } })));
  };

  useEffect(() => {
    let active = true;
    try {
      const stored = window.localStorage.getItem(`race-control:${event.slug}`);
      setRaceControlHistory(stored ? JSON.parse(stored) as LiveTimingSnapshot["raceControl"] : []);
    } catch { setRaceControlHistory([]); }
    fetch(`${API_BASE}/events/${event.slug}/race-state`, { cache: "no-store" })
      .then((response) => { if (!response.ok) throw new Error("live state unavailable"); return response.json() as Promise<LiveTimingSnapshot>; })
      .then((state) => active && acceptSnapshot(state))
      .catch(() => active && setStreamState("retrying"));
    const stream = new EventSource(`${API_BASE}/events/${event.slug}/live-stream`);
    stream.addEventListener("open", () => active && setStreamState("open"));
    stream.addEventListener("timing", (message) => {
      if (!active) return;
      try { acceptSnapshot(JSON.parse((message as MessageEvent<string>).data) as LiveTimingSnapshot); setStreamState("open"); }
      catch { setStreamState("retrying"); }
    });
    stream.addEventListener("error", () => active && setStreamState("retrying"));
    return () => { active = false; stream.close(); };
  }, [event.slug]);

  useEffect(() => {
    for (const radio of snapshot?.teamRadio ?? []) {
      const path = value(radio, "Path");
      if (!path || radioTranscripts[path]) continue;
      loadRadioTranscript(path, value(radio, "SessionPath"), value(radio, "AudioUrl"));
    }
  }, [snapshot?.teamRadio, radioTranscripts]);

  const updatedLabel = useMemo(() => !snapshot?.updatedAt ? "아직 수신된 라이브 신호가 없습니다" : `${new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Seoul" }).format(new Date(snapshot.updatedAt))} KST 갱신`, [snapshot?.updatedAt]);
  const connection = snapshot?.connection ?? (streamState === "retrying" ? "reconnecting" : "connecting");
  const feedAgeSeconds = snapshot?.updatedAt ? Math.max(0, Math.floor((Date.now() - new Date(snapshot.updatedAt).getTime()) / 1000)) : null;
  const feedStale = snapshot?.isLive && feedAgeSeconds !== null && feedAgeSeconds > 30;
  const statusLabel = feedStale ? "데이터 갱신 지연" : connection === "live" && !snapshot?.isLive ? "피드 연결 · 세션 대기" : STATUS_LABEL[connection];
  const weather = snapshot?.weather ?? {};

  return <section className="section-page live-page" id="live">
    <div className="page-heading live-heading"><div><p className="eyebrow">LIVE TIMING</p><h2>{event.name}<small>{snapshot?.session.name || "세션 연결 중"}</small></h2></div><div className={`live-connection ${feedStale ? "stale" : snapshot?.isLive ? "connected" : connection}`} role="status"><span /><div><b>{statusLabel}</b><small>{updatedLabel}{feedStale ? ` · ${feedAgeSeconds}초 전` : ""}</small></div></div></div>
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
    <div className="live-grid">
      <section className="panel live-tower"><header><div><p className="eyebrow">TIMING TOWER</p><h3>실시간 순위</h3></div><span>{snapshot?.drivers.length ?? 0} DRIVERS</span></header>
        <div className="live-sector-meta"><strong>타이밍 · 미니섹터</strong><p className="mini-sector-legend"><span className="yellow" />일반 기록 <span className="green" />개인 최고 <span className="purple" />전체 최고 <span className="unknown" />상태 없음</p></div>
        <p className="mini-sector-help">막대 상태와 섹터 시간은 별도 신호입니다. 한쪽만 들어올 수 있습니다. 회색 막대는 구간 상태 미제공, ‘—’는 섹터 시간 미제공입니다.{snapshot?.session.remaining === "00:00:00" ? " 현재는 종료된 세션의 마지막 수신값을 보여줍니다." : ""}</p>
        <div className="live-tower-head"><span>POS</span><span>DRIVER</span><span>LAST</span><span>BEST</span><span>INTERVAL</span><span>GAP</span><span>MINI SECTORS · S1 / S2 / S3</span><span>TYRE / STINT</span></div><div className="live-tower-list">
        {!snapshot?.drivers.length && <p className="empty-state">세션이 시작되면 실시간 순위가 표시됩니다. 현재는 라이브 수집기 연결을 기다리고 있습니다.</p>}
        {snapshot?.drivers.map((driver) => <article className={`${driver.inPit ? "in-pit" : ""} ${driver.retired ? "retired" : ""}`} key={driver.number} style={{ "--driver-colour": driver.colour } as React.CSSProperties}>
          <b>{driver.position}</b>
          <div className="live-driver-name"><i /><strong>{driver.code}</strong><small>{driver.team}</small></div>
          <time>{driver.lastLap}</time><time>{driver.bestLap}</time>
          <em>{driver.inPit ? "PIT" : driver.interval}</em><em>{driver.retired ? "OUT" : driver.gap}</em>
          <div className="mini-sector-dashboard" aria-label={`${driver.code} 미니섹터와 섹터 시간`}>
            {[0, 1, 2].map((index) => <div className="mini-sector-group" key={index} aria-label={`${index + 1}섹터: ${driver.currentSectors?.[index] && driver.currentSectors[index] !== "—" ? driver.currentSectors[index] : "시간 미제공"}, ${driver.miniSectors?.[index]?.length ? "구간 상태 수신" : "구간 상태 미제공"}`}>
              <div className="mini-sector-bars" aria-label={`${index + 1}섹터 구간 상태`}>
                {driver.miniSectors?.[index]?.length ? driver.miniSectors[index].map((colour, segment) => <span className={colour} key={segment} title={`${index + 1}섹터 ${segment + 1}구간: ${colour === "unknown" ? "피드 상태 미제공" : colour}`} />) : <span className="unknown" title="구간 상태 미제공" />}
              </div>
              <span className={`mini-sector-time ${driver.sectorFlags?.[index]?.overallFastest ? "purple" : driver.sectorFlags?.[index]?.personalFastest ? "green" : ""}`} title={driver.currentSectors?.[index] && driver.currentSectors[index] !== "—" ? `${index + 1}섹터 ${driver.currentSectors[index]}` : `${index + 1}섹터 시간 미제공`}>{driver.currentSectors?.[index] || "—"}</span>
            </div>)}
          </div>
          <div className="live-tyre-dashboard" title={(driver.tyreHistory ?? []).map((tyre) => `${tyre.compound} ${tyre.laps}랩`).join(" → ")} aria-label={`${driver.compound} 타이어, ${driver.stint || 0}번째 스틴트, ${driver.tyreAge}랩 사용`}>
            <span className={`live-tyre-ring ${driver.compound.toLowerCase()}`}><b>{driver.compound.slice(0, 1)}</b></span>
            <span className="live-tyre-usage"><b>{driver.pitStops !== null && driver.pitStops !== undefined ? `${driver.pitStops} PIT` : `ST${driver.stint || "—"}`}</b><small>{driver.tyreAge} LAP</small></span>
          </div>
        </article>)}
      </div></section>
      <aside className="live-side-column">
        <section className="panel live-feed-panel"><header><div><p className="eyebrow">RACE CONTROL</p><h3>레이스 컨트롤</h3></div><span>{raceControlHistory.length} MESSAGES</span></header><div className="live-message-list">{!raceControlHistory.length && <p className="empty-state">공식 메시지를 기다리고 있습니다.</p>}{raceControlHistory.map((message, index) => <article key={`${value(message, "Utc")}-${value(message, "Message")}-${index}`}><time>{value(message, "Utc").slice(11, 19) || "—"}</time><p>{value(message, "Message") || value(message, "Category")}</p></article>)}</div></section>
        <section className="panel live-feed-panel radio-panel"><header><div><p className="eyebrow">TEAM RADIO</p><h3>팀 라디오</h3></div><label className="radio-translation-toggle"><span>한국어 번역</span><input checked={radioTranslationEnabled} onChange={(change) => setRadioTranslationEnabled(change.target.checked)} type="checkbox" /><i /></label></header><div className="live-message-list radio-list">{!snapshot?.teamRadio.length && <p className="empty-state">공개된 팀 라디오를 기다리고 있습니다.</p>}{snapshot?.teamRadio.map((radio, index) => {
          const path = value(radio, "Path");
          const sessionPath = value(radio, "SessionPath");
          const audioUrl = value(radio, "AudioUrl");
          const transcript = radioTranscripts[path];
          const racingNumber = value(radio, "RacingNumber");
          const driver = snapshot?.drivers.find((item) => item.number === racingNumber);
          const utc = value(radio, "Utc");
          const published = utc ? new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" }).format(new Date(utc)) : "시간 정보 없음";
          return <article className="radio-card" key={`${utc}-${index}`} style={{ "--driver-colour": driver?.colour || "#e10600" } as React.CSSProperties}>
            <div className="radio-driver"><span>#{racingNumber || "—"}</span><div><small>{driver?.team || "FORMULA 1"}</small><b>{driver?.name || driver?.code || `CAR ${racingNumber || "—"}`}</b></div><time>{published}</time></div>
            <div className="radio-player">{(transcript?.audioUrl || audioUrl) && <audio controls preload="metadata" src={transcript?.audioUrl || audioUrl}>팀 라디오 오디오</audio>}</div>
            <div className="radio-transcript" role="status">{!transcript && <p>팀 라디오 내용을 불러오는 중입니다…</p>}{transcript?.status === "loading" && <p>팀 라디오 음성을 텍스트로 변환하고 있습니다…</p>}{transcript?.status === "failed" && <p>텍스트 변환에 실패했습니다. 위 재생 버튼으로 음성을 들을 수 있습니다.</p>}{transcript?.status === "ready" && <>{radioTranslationEnabled && transcript.translation && <p className="translated"><i />{transcript.translation}</p>}<p className={radioTranslationEnabled && transcript.translation ? "original" : ""}><i />{transcript.text || "명확한 발화를 인식하지 못했습니다."}</p></>}</div>
          </article>;
        })}</div></section>
      </aside>
    </div>
    <p className="live-disclaimer">F1의 비공식 라이브 타이밍 피드를 사용합니다. 중계 화면보다 지연되거나 일부 항목이 제공되지 않을 수 있습니다. 최종 결과는 경기 종료 후 공식 자료로 보정합니다.</p>
  </section>;
}
