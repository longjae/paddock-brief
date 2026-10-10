"use client";

import { useEffect, useMemo, useState } from "react";
import type { EventDetail, LiveTimingSnapshot } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const STATUS_LABEL: Record<LiveTimingSnapshot["connection"], string> = { disabled: "수집기 대기", offline: "오프라인", connecting: "연결 중", reconnecting: "재연결 중", live: "실시간" };
const TRACK_LABEL: Record<string, string> = { "1": "트랙 정상", "2": "황기", "4": "세이프티카", "5": "적기", "6": "가상 세이프티카", "7": "VSC 종료 중" };
type RadioTranscript = { status: "loading" | "ready" | "failed"; text?: string | null; audioUrl?: string };

function value(item: Record<string, string | number | boolean | null>, key: string): string {
  return item[key] === null || item[key] === undefined ? "" : String(item[key]);
}

export function LiveTiming({ event }: { event: EventDetail }) {
  const [snapshot, setSnapshot] = useState<LiveTimingSnapshot | null>(null);
  const [streamState, setStreamState] = useState<"opening" | "open" | "retrying">("opening");
  const [radioTranscripts, setRadioTranscripts] = useState<Record<string, RadioTranscript>>({});

  const loadRadioTranscript = (path: string, sessionPath: string, audioUrl: string) => {
    if (!path || radioTranscripts[path]) return;
    setRadioTranscripts((current) => ({ ...current, [path]: { status: "loading", audioUrl } }));
    fetch(`${API_BASE}/team-radio/transcript?path=${encodeURIComponent(path)}&sessionPath=${encodeURIComponent(sessionPath)}`)
      .then((response) => { if (!response.ok) throw new Error("transcript unavailable"); return response.json() as Promise<{ audioUrl: string; transcript?: string | null }>; })
      .then((result) => setRadioTranscripts((current) => ({ ...current, [path]: { status: "ready", text: result.transcript, audioUrl: result.audioUrl } })))
      .catch(() => setRadioTranscripts((current) => ({ ...current, [path]: { status: "failed" } })));
  };

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/events/${event.slug}/race-state`, { cache: "no-store" })
      .then((response) => { if (!response.ok) throw new Error("live state unavailable"); return response.json() as Promise<LiveTimingSnapshot>; })
      .then((state) => active && setSnapshot(state))
      .catch(() => active && setStreamState("retrying"));
    const stream = new EventSource(`${API_BASE}/events/${event.slug}/live-stream`);
    stream.addEventListener("open", () => active && setStreamState("open"));
    stream.addEventListener("timing", (message) => {
      if (!active) return;
      try { setSnapshot(JSON.parse((message as MessageEvent<string>).data) as LiveTimingSnapshot); setStreamState("open"); }
      catch { setStreamState("retrying"); }
    });
    stream.addEventListener("error", () => active && setStreamState("retrying"));
    return () => { active = false; stream.close(); };
  }, [event.slug]);

  const updatedLabel = useMemo(() => !snapshot?.updatedAt ? "아직 수신된 라이브 신호가 없습니다" : `${new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Seoul" }).format(new Date(snapshot.updatedAt))} KST 갱신`, [snapshot?.updatedAt]);
  const connection = snapshot?.connection ?? (streamState === "retrying" ? "reconnecting" : "connecting");
  const statusLabel = connection === "live" && !snapshot?.isLive ? "피드 연결 · 세션 대기" : STATUS_LABEL[connection];
  const weather = snapshot?.weather ?? {};

  return <section className="section-page live-page" id="live">
    <div className="page-heading live-heading"><div><p className="eyebrow">LIVE TIMING</p><h2>{snapshot?.session.name || "세션 연결 중"}</h2><p>순위, 랩 타임, 타이어, 트랙 상태와 레이스 컨트롤 메시지를 2초 간격으로 갱신합니다.</p></div><div className={`live-connection ${snapshot?.isLive ? "connected" : connection}`} role="status"><span /><div><b>{statusLabel}</b><small>{updatedLabel}</small></div></div></div>
    <div className="live-summary-strip">
      <article><span>LAP</span><b>{snapshot?.session.lap || "—"}<small> / {snapshot?.session.totalLaps || "—"}</small></b></article>
      <article><span>TIME REMAINING</span><b>{snapshot?.session.remaining || "—"}</b></article>
      <article className={`track-${snapshot?.trackStatus.code || "unknown"}`}><span>TRACK STATUS</span><b>{TRACK_LABEL[snapshot?.trackStatus.code || ""] || snapshot?.trackStatus.message || "정보 대기"}</b></article>
      <article><span>AIR / TRACK</span><b>{String(weather.AirTemp ?? "—")}° <small>/ {String(weather.TrackTemp ?? "—")}°</small></b></article>
    </div>
    <div className="live-grid">
      <section className="panel live-tower"><header><div><p className="eyebrow">TIMING TOWER</p><h3>실시간 순위</h3></div><span>{snapshot?.drivers.length ?? 0} DRIVERS</span></header><div className="live-tower-head"><span>POS</span><span>DRIVER</span><span>TYRE</span><span>LAST</span><span>BEST</span><span>INTERVAL</span><span>GAP</span></div><div className="live-tower-list">
        {!snapshot?.drivers.length && <p className="empty-state">세션이 시작되면 실시간 순위가 표시됩니다. 현재는 라이브 수집기 연결을 기다리고 있습니다.</p>}
        {snapshot?.drivers.map((driver) => <article className={`${driver.inPit ? "in-pit" : ""} ${driver.retired ? "retired" : ""}`} key={driver.number} style={{ "--driver-colour": driver.colour } as React.CSSProperties}><b>{driver.position}</b><div><i /><strong>{driver.code}</strong><small>{driver.team}</small></div><span className={`live-compound ${driver.compound.toLowerCase()}`}>{driver.compound.slice(0, 1)}<small>{driver.tyreAge}L</small></span><time>{driver.lastLap}</time><time>{driver.bestLap}</time><em>{driver.inPit ? "PIT" : driver.interval}</em><em>{driver.retired ? "OUT" : driver.gap}</em></article>)}
      </div></section>
      <aside className="live-side-column">
        <section className="panel live-feed-panel"><header><div><p className="eyebrow">RACE CONTROL</p><h3>레이스 컨트롤</h3></div></header><div className="live-message-list">{!snapshot?.raceControl.length && <p className="empty-state">공식 메시지를 기다리고 있습니다.</p>}{snapshot?.raceControl.map((message, index) => <article key={`${value(message, "Utc")}-${index}`}><time>{value(message, "Utc").slice(11, 19) || "—"}</time><p>{value(message, "Message") || value(message, "Category")}</p></article>)}</div></section>
        <section className="panel live-feed-panel"><header><div><p className="eyebrow">TEAM RADIO</p><h3>팀 라디오</h3></div></header><div className="live-message-list radio-list">{!snapshot?.teamRadio.length && <p className="empty-state">공개된 팀 라디오를 기다리고 있습니다.</p>}{snapshot?.teamRadio.map((radio, index) => {
          const path = value(radio, "Path");
          const sessionPath = value(radio, "SessionPath");
          const audioUrl = value(radio, "AudioUrl");
          const transcript = radioTranscripts[path];
          return <article key={`${value(radio, "Utc")}-${index}`} onFocus={() => loadRadioTranscript(path, sessionPath, audioUrl)} onMouseEnter={() => loadRadioTranscript(path, sessionPath, audioUrl)} tabIndex={0}><b>#{value(radio, "RacingNumber") || "—"}</b><p>마우스를 올리면 음성과 내용을 확인할 수 있습니다.</p><time>{value(radio, "Utc").slice(11, 19)}</time><div className="radio-transcript" role="status">{transcript?.status === "loading" && <><p>팀 라디오 음성을 텍스트로 변환 중입니다…</p>{transcript.audioUrl && <audio controls preload="none" src={transcript.audioUrl}>팀 라디오 오디오</audio>}</>}{transcript?.status === "failed" && <><p>텍스트 변환에 실패했습니다. 음성은 직접 재생할 수 있습니다.</p>{audioUrl && <audio controls preload="none" src={audioUrl}>팀 라디오 오디오</audio>}</>}{transcript?.status === "ready" && <><p>{transcript.text || "음성은 재생할 수 있지만 명확한 발화를 인식하지 못했습니다."}</p>{transcript.audioUrl && <audio controls preload="none" src={transcript.audioUrl}>팀 라디오 오디오</audio>}</>}</div></article>;
        })}</div></section>
      </aside>
    </div>
    <p className="live-disclaimer">F1의 비공식 라이브 타이밍 피드를 사용합니다. 중계 화면보다 지연되거나 일부 항목이 제공되지 않을 수 있습니다. 최종 결과는 경기 종료 후 공식 자료로 보정합니다.</p>
  </section>;
}
