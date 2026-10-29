"use client";

import { useEffect, useState } from "react";

type Collector = {
  kind: "news" | "videos" | "radio";
  status: "succeeded" | "partial" | "failed" | "skipped" | "unknown";
  eventSlug: string | null;
  finishedAt: string | null;
  lastSuccessAt: string | null;
  processed: number | null;
  failed: number;
  unavailable: number;
  translationMissing: number;
  pending: number;
  metadataUnverified: number;
  delayed: boolean;
};
type Health = { collectors: Collector[]; unavailable: boolean; teamCoverage: { configured: string[]; total: number | null } };
const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const NAMES = { news: "기사", videos: "영상", radio: "팀 라디오" };
const LABELS = { succeeded: "수집 실행 완료", partial: "일부 확인 제한", failed: "수집 실패", skipped: "수집 대기", unknown: "실행 기록 없음" };

function time(value: string | null): string {
  return value && Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" }).format(new Date(value)) + " KST" : "확인 기록 없음";
}

export function CollectionHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch(`${API}/collection-health`, { signal: controller.signal });
        if (!response.ok) throw new Error("Health unavailable");
        const data = await response.json() as Health;
        if (!Array.isArray(data.collectors)) throw new Error("Invalid health response");
        if (!controller.signal.aborted) { setHealth(data); setError(data.unavailable); }
      } catch { if (!controller.signal.aborted) setError(true); }
    };
    void load();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void load(); }, 60_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, []);
  const issues = health?.collectors.filter(item => item.status === "failed" || item.status === "partial" || item.delayed).length ?? 0;
  const unknown = health?.collectors.some(item => item.status === "unknown");
  return <details className="collection-health">
    <summary><strong>수집기 상태</strong><span className={error || issues ? "health-warning" : ""}>{error ? "상태 조회 확인 필요" : !health ? "확인 중" : issues ? `${issues}개 항목 확인 필요` : unknown ? "일부 실행 기록 없음" : "최근 실행 정상"}</span><small>기사 · 영상 · 라디오</small></summary>
    <div className="collection-health-content">
      <p>전체 GP 수집기의 마지막 실행 기준입니다. 원문 발행일이나 실시간 데이터 지연을 뜻하지 않습니다. 수집 실행 완료와 영상 요약·한국어 번역 완료는 별개입니다.</p>
      {error && <p role="status">현재 상태를 조회하지 못했습니다. 아래 기록이 있으면 마지막으로 확인한 값입니다.</p>}
      <div className="collection-health-grid">{health?.collectors.map(item => <article key={item.kind}>
        <header><b>{NAMES[item.kind]}</b><span className={item.status === "failed" || item.status === "partial" || item.delayed ? "health-warning" : ""}>{item.delayed && item.status === "succeeded" ? "최근 실행 확인 필요" : LABELS[item.status]}</span></header>
        <dl><dt>마지막 실행</dt><dd>{time(item.finishedAt)}</dd><dt>마지막 정상 완료</dt><dd>{time(item.lastSuccessAt)}</dd>{item.processed !== null && <><dt>이번 처리</dt><dd>{item.processed}건</dd></>}</dl>
        {item.eventSlug && <small>대상 GP: {item.eventSlug}</small>}
        {item.failed > 0 && <p className="health-warning">처리·상세 확인 오류 {item.failed}건</p>}
        {item.metadataUnverified > 0 && <p>영상 상세 정보 미확인 {item.metadataUnverified}건 · 공식 외부 링크 제공</p>}
        {item.pending > 0 && <p>공개 자막·한국어 요약 대기 {item.pending}건</p>}
        {item.unavailable > 0 && <p>{item.kind === "radio" ? "사용 가능한 음성 없음" : "공개 자막 제공 제한"} {item.unavailable}건</p>}
        {item.translationMissing > 0 && <p className="health-warning">한국어 번역 대기 {item.translationMissing}건 · 영어 자막 유지</p>}
      </article>)}</div>
      <p>팀 공식 홈페이지 직접 수집: {health?.teamCoverage.configured.length ?? "—"} / {health?.teamCoverage.total ?? "—"}팀. {health?.teamCoverage.configured.join(" · ")}. 나머지 팀의 일반 보도와 공식 홈페이지 직접 수집은 구분됩니다. 전체 팀 확대는 준비 중입니다.</p>
    </div>
  </details>;
}
