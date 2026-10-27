# 상시 라이브 수집기

## 실행 환경과 현재 상태

이 워커는 브라우저와 GitHub 예약 없이 세션 시작 10분 전부터 수집한다. 약 60초마다 세션을 확인하고 활성 세션에서는 최대 4시간 동안 기존 수집기를 실행한다. 직접 연결이 조용하면 HTTPS 스트림으로 전환하고, 스트림 단절 또는 수집 사이클 실패 시 재시도한다. Mac용 LaunchAgent는 로그인 때 시작하고 프로세스가 종료되면 다시 시작한다.

**2026-10-27: 구현 및 자동 테스트 완료, 실제 설치·상시 실행은 저장용 자격 증명 등록 대기.** 운영 Vercel API에는 `SUPABASE_URL`과 읽기용 키만 있고 `SUPABASE_SECRET_KEY`가 없다. GitHub Actions의 저장용 Secret은 읽어낼 수 없으며 추출하지 않는다. 따라서 운영 API의 읽기 키를 저장용 키로 대체하거나 수집 성공을 가장하지 않는다.

Vercel API는 상시 프로세스 호스트로 사용하지 않는다. 이번 구성은 추가 호스팅 비용 없이 Mac에서 실행하는 방식이다. Mac의 전원·네트워크·로그인 세션이 유지돼야 하며 잠자기·로그아웃·전원 종료 중에는 수집을 보장하지 않는다. 항상 켜진 클라우드 호스트로 옮기려면 별도 제공자와 요금 승인이 필요하다. 기존 GitHub 예약 수집은 예비 경로로 유지한다. 두 경로 모두 최신 상태를 upsert하므로 중복 자막 전사를 하지 않는다.

## 비공개 설정

프로젝트의 `backend/.env.live-worker.example`을 **같은 폴더의 `.env.live-worker`**로 복사한다. Supabase 프로젝트 URL과 서버 저장용 키를 로컬 편집기로 넣는다. 키는 채팅·커밋·로그에 넣지 않는다. 공개/브라우저 키로는 저장할 수 없다. 이 파일은 Git에서 제외하며 설치기가 권한을 `0600`으로 제한한다. 워커는 저장소 설정만 사용하며 OpenAI·YouTube 키를 요구하지 않는다.

원래 체크아웃의 backend 폴더에서 실행한다:

```sh
.venv/bin/python scripts/run_live_worker.py --env-file .env.live-worker --once
.venv/bin/python scripts/install_macos_live_worker.py
```

첫 명령은 한 번의 실제 세션 선택 및 연결 확인이다. 세션이 없으면 정상 대기 결과로 종료한다. 세션이 있으면 수집할 수 있으므로 설치 전 설정을 확인한다. 설치는 `.venv/bin/python`과 안정적인 프로젝트 경로를 사용한다. 임시 디렉터리에 설치하지 않는다.

## 상태와 로그

- 상태: `~/Library/Application Support/PaddockBrief/health.json`
- 로그: `~/Library/Logs/PaddockBrief/worker.log`, `worker-error.log`
- LaunchAgent: `~/Library/LaunchAgents/com.paddockbrief.live-worker.plist`

상태 파일의 `heartbeatAt`은 프로세스 생존, `lastCycleAt`은 세션 확인 시작, `lastSuccessfulCollectionAt`은 저장 건수가 있는 사이클 종료를 뜻한다. 마지막 필드는 각 스냅샷 저장 시각이 아니다. 실제 최신 데이터 수신 시각은 운영 라이브 화면과 DB `captured_at`을 확인한다. `snapshotsSaved`는 프로세스 시작 이후 합계이고 재시작하면 초기화된다. `lastError`에는 예외 종류만 남긴다.

```sh
launchctl print gui/$(id -u)/com.paddockbrief.live-worker
```

제거:

```sh
.venv/bin/python scripts/install_macos_live_worker.py --remove
```

제거 시 비공개 설정과 로그를 지우지 않는다. 설치된 프로세스만 중지하고 LaunchAgent 파일을 제거한다.

## 완료한 자동 검증

- 상위 수집기 실패 후 백오프로 재시도하고 정상 상태로 복귀
- 종료 신호 때 진행 중 수집 작업 취소 및 연결 정리
- 세션이 없을 때 반복 요청 폭주 없이 대기
- 상태 파일의 원자적 교체, 비공개 권한 및 오류 내용 비노출
- 설치 파일에 비밀 값 없이 안정적인 실행 경로 지정
- 기존 HTTPS 스트림 503 복구, 무수신 직접 연결의 대체 경로 전환, 오래된 기록·다른 GP 거절

## 멕시코 FP1 실전 확인

1. 로컬 자격 증명 등록과 LaunchAgent 설치를 먼저 완료한다. 설치되지 않았다면 예약 점검에서 이 차단 요인을 명시하고 GitHub 작업을 수동 실행한다.
2. 10월 31일 03:20 KST부터 워커가 FP1을 선택하는지 확인한다. FP1은 03:30~04:30 KST다.
3. 브라우저를 닫은 상태에서 약 15초 간격 저장이 이어지는지 최소 5분 관찰한다.
4. 네트워크를 잠깐 끊었다 복구한 뒤 재접속·저장 재개와 화면 지연 표시를 대조한다.
5. 위치·차량 주제의 실제 제공 여부를 별도로 판단한다. 공개 타이밍 수신 또는 경기 후 리플레이 성공을 실시간 위치 수신 성공으로 간주하지 않는다.
6. FP2 07:15 KST에 FP1 실패 항목을 재검증한다.
