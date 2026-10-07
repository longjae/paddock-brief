# Paddock Brief

그랑프리 캘린더, 공식 인터뷰 영상, 한국어 요약, 타이어와 레이스 정보를 한 화면에서 보는 개인용 레이스 컴패니언입니다.

## 기술 구성

- `frontend`: Next.js App Router + React + TypeScript
- `backend`: FastAPI + Pydantic + Supabase Python client
- `supabase`: PostgreSQL 스키마와 RLS 마이그레이션
- 데이터 공급자 어댑터: Jolpica F1, FastF1, OpenF1 폴백, YouTube Data API, FIA/Pirelli 메타데이터

Jolpica F1의 무료 API로 캘린더·세션·공식 결과를 불러옵니다. 종료된 레이스는 FastF1 배치가 마지막 타이어, 타이어 사용 랩과 최종 분류를 보강해 Supabase 스냅샷으로 저장합니다. 공급자 장애 시에는 OpenF1과 저장된 Supabase 데이터로 폴백합니다.

## 배포 주소

- 웹: https://paddock-brief-five.vercel.app
- API: https://paddock-brief-api.vercel.app
- API 문서: https://paddock-brief-api.vercel.app/docs

현재 프로덕션은 왼쪽 시즌 캘린더에서 전체 라운드를 선택할 수 있으며, OpenF1 일정/트랙맵과 Formula 1·FIA 공식 영상, Pirelli 공식 타이어 배정 출처를 연결합니다. 2026 세팡 라운드는 공식 영상 6개, FIA 인터뷰 4개, 한국어 요약, 타이어 배정과 최종 상위 5명 데이터를 테스트 자료로 제공합니다.

모든 그랑프리의 인터뷰 수집 창은 결승일을 기준으로 계산한 레이스 주 목요일 00시(개최지 현지시간)에 자동으로 열립니다. 목요일 전에는 공개 예정일을 안내하고, 이후에는 공식 인터뷰와 팀 코멘트가 게시되는 대로 노출할 수 있는 상태로 전환됩니다.
첫 화면의 대표 라운드는 다음 그랑프리의 목요일 미디어 창이 열리기 전까지 가장 최근에 열린 그랑프리를 유지하며, 목요일이 되면 다음 라운드로 자동 전환됩니다.

세팡에는 11개 팀별 Formula 1 코멘트와 Red Bull 팀 영상, Sky Sports F1 인터뷰 기사도 수집되어 있습니다. 팀·선수 통합 패독에서 팀 버튼은 팀 콘텐츠를, 팀 안의 선수 버튼은 개인 결과와 관련 자료를 보여줍니다. 콘텐츠 카드를 누르면 원문의 흐름을 배경·핵심 내용·평가로 나눈 상세 한국어 요약과 원문 링크가 모달로 열립니다. 외부 콘텐츠는 전문을 복제하지 않고 제목·참여자·출처 링크·한국어 요약과 허용된 임베드만 저장합니다.

미디어 라운드업은 Formula 1, Sky Sports F1, Motorsport.com, Autosport, The Race, PlanetF1, RacingNews365, Crash.net 기사를 매체별로 필터링합니다. URL 단위로 중복을 제거하고 기사 전문 대신 한국어 요약과 원문 링크를 제공합니다.

선수별 정보에는 라운드 출전 선수의 번호·국적·팀·결승 결과가 표시되며, 선수를 선택하면 참여자로 태깅된 팀 코멘트, 공식 영상과 미디어 기사를 함께 모아 보여줍니다.
선수 탭의 기사·팀 코멘트·영상 카드도 모두 상세 모달로 열리며, 기사에는 한눈에 보기와 소제목별 상세 한국어 요약, 원문 링크가 제공됩니다.

Supabase 프로젝트 `paddock-brief` (`lxekfxyjctcyptbjrzgu`, Seoul)은 연결되어 있습니다. 프로덕션 API는 공개 읽기 RLS 정책을 통과한 `approved` 영상과 `published` 인터뷰만 OpenF1 일정에 합쳐 반환합니다.

## 빠른 시작

### 백엔드

```bash
cd backend
cp .env.example .env
uv sync
uv run fastapi dev app/main.py --port 8000
```

### 프론트엔드

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

브라우저에서 `http://localhost:3000`을 엽니다. API 문서는 `http://localhost:8000/docs`에서 볼 수 있습니다.

## Supabase 연결

1. Supabase 프로젝트를 만든 뒤 SQL Editor에서 `supabase/migrations/0001_initial_schema.sql`을 실행합니다.
2. 백엔드 `.env`에 `SUPABASE_URL`과 `SUPABASE_PUBLISHABLE_KEY`를 넣습니다. 검수 데이터 쓰기 워커를 추가할 때만 서버 전용 `SUPABASE_SECRET_KEY`를 사용합니다.
3. `APP_USE_SAMPLE_DATA=false`로 바꿉니다.

Secret/service-role 키는 절대로 `NEXT_PUBLIC_` 환경 변수나 프론트엔드 코드에 넣지 않습니다.

## 자동 수집 배치

`.github/workflows/collect-f1-content.yml`은 모든 레이스 주의 목요일부터 결승 다음 날인 월요일까지 매시간 실행됩니다. Formula 1 공식 레이스 허브와 프레스 컨퍼런스 아카이브에서 새 기사 URL을 찾고, 이벤트 관련성을 확인한 뒤 한국어 제목·한눈에 보기·소제목별 상세 요약·팀/선수 코드를 생성합니다. URL 기준 중복 자료는 건너뛰며, 정상 처리된 공식 자료만 `approved`로 저장됩니다.

GitHub 저장소의 Actions secrets에 `SUPABASE_URL`, 서버 전용 `SUPABASE_SECRET_KEY`, `OPENAI_API_KEY`를 등록해야 합니다. 모델은 저장소 변수 `OPENAI_SUMMARY_MODEL`로 바꿀 수 있습니다. Actions 화면에서는 이벤트 slug, 드라이런, pending 저장 여부를 선택해 수동 실행할 수도 있습니다.

로컬 수동 실행 예시:

```bash
cd backend
uv run python scripts/collect_weekend_content.py --event-slug 2026-singapore --dry-run --max-articles 5
```

FastF1 결과·타이어 동기화는 별도 의존성 그룹으로 설치하고 실행합니다. 공식 일정과 저장된 이벤트의 국가·서킷이 일치하지 않으면 잘못된 레이스가 섞이지 않도록 자동으로 건너뜁니다.

```bash
cd backend
uv sync --group collector
uv run python scripts/sync_race_data.py --event-slug 2026-singapore --dry-run
```

GitHub Actions의 `sync-race-data.yml`은 매시간 실행되지만, 최근 7일 이내 종료된 레이스 중 아직 스냅샷이 없는 이벤트만 FastF1로 처리합니다.

세팡 테스트 자료는 `supabase/seeds/2026_sepang.sql`에 있으며 반복 실행해도 같은 레코드를 갱신하도록 구성했습니다.

상세 일정은 [개발 플랜](docs/DEVELOPMENT_PLAN.md), 데이터 흐름은 [아키텍처](docs/ARCHITECTURE.md)를 참고하세요.
