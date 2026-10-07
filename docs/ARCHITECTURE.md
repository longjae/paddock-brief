# 아키텍처

```text
Jolpica / FastF1 batch / OpenF1 fallback / YouTube / FIA
                    │
                    ▼
          FastAPI provider adapters
                    │
          normalize · classify · dedupe
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   Supabase Postgres      Redis (live, later)
          │                   │
          └─────────┬─────────┘
                    ▼
             FastAPI REST/SSE
                    ▼
              Next.js client
```

## 경계

- 프론트엔드는 FastAPI만 호출한다.
- Supabase secret/service-role 키와 외부 공급자 키는 백엔드에만 둔다.
- 공급자 응답은 내부 모델로 정규화해 UI가 특정 공급자에 묶이지 않게 한다.
- 실시간 원본을 모두 Postgres에 저장하지 않는다. 최신 상태는 메모리/Redis에 두고 필요한 스냅샷과 세션 결과만 저장한다.

## 주요 엔티티

- `events`: 그랑프리 주말
- `sessions`: 연습, 예선, 스프린트, 레이스
- `sources`: FIA, Formula 1, 팀, YouTube 채널, 데이터 API
- `videos`: 임베드 또는 외부 링크 가능한 영상 메타데이터
- `interviews`: 인터뷰 원문 위치와 한국어 요약
- `interview_segments`: 화자별 원문·번역·타임코드
- `tyre_allocations`: 주말 지정 컴파운드
- `race_state_snapshots`: 저주기 레이스 상태 보관

## API 초안

- `GET /api/v1/health`
- `GET /api/v1/events`
- `GET /api/v1/events/{slug}`
- `GET /api/v1/events/{slug}/videos`
- `GET /api/v1/events/{slug}/interviews`
- `GET /api/v1/events/{slug}/race-state`
