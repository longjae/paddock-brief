"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { officialTrackMap } from "@/lib/official-track-maps";
import type { EventDetail } from "@/lib/types";

export function OfficialCircuitMap({ event }: { event: EventDetail }) {
  const [view, setView] = useState<"layout" | "straight">("layout");
  const map = officialTrackMap(event.slug);

  useEffect(() => setView("layout"), [event.slug]);

  if (!map) return <p className="track-replay-note">이 GP의 공식 트랙맵을 확인하는 중입니다.</p>;

  return <div className="official-circuit-map">
    <div className="official-map-tabs" role="group" aria-label="트랙맵 표시 선택">
      <button type="button" aria-pressed={view === "layout"} onClick={() => setView("layout")}>F1 서킷맵</button>
      <button type="button" aria-pressed={view === "straight"} disabled={!map.fiaDocumentUrl} onClick={() => setView("straight")}>FIA 직선 모드 구간</button>
    </div>
    <div className="official-map-viewport">
      {view === "straight" && map.fiaMapImageUrl
        ? <Image src={map.fiaMapImageUrl} alt={`${event.name} FIA 2026 서킷맵과 직선 모드 구간`} width={1400} height={1800} sizes="(max-width: 640px) 100vw, 40vw" />
        : <Image src={map.imageUrl} alt={`${event.circuit} 2026 공식 트랙맵. 코너 번호, 섹터와 스피드 트랩 표시`} width={1200} height={700} sizes="(max-width: 640px) 100vw, 40vw" />}
    </div>
    <div className="official-map-sources">
      <p>{map.fiaDocumentUrl ? "직선 모드 구간은 FIA 경기별 서킷맵 2쪽에서 확인할 수 있습니다." : "이 GP의 FIA 2026 직선 모드 구간 자료는 아직 확인되지 않았습니다. 현재는 F1 공식 서킷맵을 보여줍니다."}</p>
      <span><a href={map.sourceUrl} target="_blank" rel="noreferrer">F1 원문 ↗</a>{map.fiaDocumentUrl && <a href={`${map.fiaDocumentUrl}#page=2`} target="_blank" rel="noreferrer">FIA 원문 ↗</a>}</span>
    </div>
  </div>;
}
