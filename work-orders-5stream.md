# Garmin Personal Coach — 작업지시서 v3 (PRD v3.0 기준)

> v2 작업지시서의 5개 스트림(Foundation/Telegram/Onboarding/Nutrition/Feedback)은
> 완료되어 229개 테스트로 커버됨 (상세는 git history 참조).
> v3는 PRD v3.0의 "Speed·Trust·Loop" 축을 구현하는 4개 스트림으로 재편한다.

## 스트림 구조와 의존성

```
S-A: Data Plane (스냅샷/캐시)  ──┬──▶ S-B: 여정 완성도 (브리핑/라벨/트리거)
                                 └──▶ S-D: 리포트 & 트렌드 (캐시-온리)
S-C: 레거시 상환 (독립, 상시)
```

## S-A. Data Plane — 최우선

| 항목 | 상태 | 위치 |
|------|------|------|
| 병렬 스냅샷 fetcher (8지표 1-batch, 지표당 재시도 1회) | ✅ 완료 | `adapters/garmin/snapshot.py` `SnapshotFetcher` |
| 캐시-우선 서비스 (오늘 TTL 30분 / 과거 영구 / 스테일 폴백) | ✅ 완료 | `SnapshotService` |
| `snapshots` 테이블 (레거시 `daily_health`와 격리) | ✅ 완료 | `storage/database.py` |
| 신선도 계약 (라벨 3단계) | ✅ 완료 | `DailySnapshot.freshness_label()` |
| `GarminSyncService.sync_daily_health` 병렬 전환 | ✅ 완료 | `integrations/sync.py` |
| 테스트 13종 (병렬/부분실패/TTL/폴백/직렬화/격리) | ✅ 완료 | `tests/test_snapshot_service.py` |
| `is_authenticated()` 네트워크 콜 제거 | 🔲 | `adapters/garmin/__init__.py:86` |
| `get_time_series` N+1 제거 (스냅샷 캐시로 대체) | 🔲 | `adapters/garmin/__init__.py:255` |

## S-B. 여정 완성도

- 🔲 아침 브리핑 선행-fetch: 스케줄러가 브리핑 N분 전에 `SnapshotService.get(force_refresh=True)` 호출
- 🔲 신선도 라벨을 Telegram 렌더러(`interfaces/telegram/renderer.py`)와 CLI `gc status`에 일괄 적용
- 🔲 스테일 데이터 가드: 24h+ 스냅샷으로 Zone 4+ 신규 권고 금지 (`engine/guardrails.py`에 체크 1개 추가)
- 🔲 활동 폴링 → `flows/post_workout.py` 자동 트리거 배선 점검 (상세 fetch는 새 활동 감지 시에만)

## S-C. 레거시 상환 (빅뱅 금지 — 건드릴 때 이관)

| 레거시 | 정본 | 트리거 |
|--------|------|--------|
| `telegram_bot.py` (1,623줄) | `interfaces/telegram/` | 명령어 수정 시 해당 핸들러부터 |
| `scheduler.py` | `interfaces/telegram/scheduler.py` | S-B 선행-fetch 작업 시 |
| `morning_checkin.py`/`evening_checkin.py` | `flows/` 동명 모듈 | S-B 작업 시 |
| `activity_fetch.py` + `adapters/fetch.py` | Data Plane | S-A 잔여 작업 시 |
| `setup_wizard.py` | `wizard/` | 온보딩 수정 시 |

## S-E. 데이터 접근 & AI 어태치 (2026-07 리서치 반영)

- ✅ garminconnect 0.3.5 → **0.3.6** 업그레이드 (widget+cffi 로그인 전략 — 2026-03 Cloudflare 차단 우회)
- ✅ Garmin 데이터 표 작성 (README §Garmin Data We Can Pull) — 설치된 라이브러리 `dir()` 기준 실측,
  readiness/sleep/activity/body comp는 이미 파이프라인에 연결, training status/steps/floors/gear/PR은 로드맵으로 표시
- ✅ Strava 전체 이력 백필 안전화: `adapters/strava.py`에 429 `Retry-After` 백오프 추가 — 이전엔
  rate limit에 걸리면 **조용히** 페이지네이션이 끊겨 데이터가 소리소문없이 잘렸음 (실제 버그, 수정 완료).
  `garmin-coach strava-sync --days 3650`로 전체 이력 백필 가능 (페이지네이션은 이미 정상 동작 중이었음)
- ✅ zero-config LLM: `ai_cli.py` — 로컬 claude/gemini/codex CLI 자동 감지, `claude -p` 헤드리스 호출,
  `AICoach` provider 체인에 `cli` 추가 (API 키 > CLI > 룰), E2E 검증 완료
  — **버그 수정**: 최초 구현에서 쓴 `--setting-sources ""`는 실제로 CLAUDE.md를 막지 않음(공식 문서 확인).
  올바른 플래그는 `--safe-mode`(OAuth 인증은 유지하면서 CLAUDE.md/hooks/MCP/skills만 차단) + `--allowedTools ""`
  (도구 호출 자체를 봉쇄, 무한 대기 방지). E2E로 개인 CLAUDE.md 유출 사라짐을 재검증함.
- 🔲 `garmin-coach connect-garmin` 최초 로그인 UX 점검 (MFA 프롬프트, 실패 시 안내 문구)
- 🔲 재로그인 루프 방지 가드: 로그인 실패 시 지수 백오프 + "N시간 내 재시도 금지" (계정 단위 429 예방)
- 🔲 Strava: opt-in 유지, 2026-09 엔드포인트 폐기 대응 여부만 모니터링 (신규 투자 없음)
- 🔲 provider 로드맵: gemini/codex도 claude와 같은 "개인 설정 격리" 문제가 있는지 확인 필요.
  gemini-cli는 GEMINI.md를 건너뛰는 공식 플래그를 리서치에서 못 찾음(로드맵 이슈로 보류).
  codex는 `exec`에 `--sandbox read-only --ask-for-approval never` 적용 완료(승인 대기로 인한 행 방지 목적,
  설정 격리 자체는 별도 검증 필요). copilot-cli/cursor-agent 등 추가 프로바이더는 수요 확인 후 추가.

## S-F. iMessage 채널 (신규, 2026-07 리서치 반영 — 실행 전 결정 필요)

`CoachingPort` 구현체 하나 추가로 완결 — Flows/Engine 무수정 원칙은 유지 가능. 단, 채널 자체의
실현 가능성에 **공식 API가 없다는 근본 제약**이 있어 착수 전 방식을 정해야 한다.

### 리서치 결론: 두 가지 길, 한쪽만 현실적

1. **Apple Messages for Business (공식)**: Apple 승인 MSP(메시징 서비스 제공사) 파트너십 필수,
   비즈니스 등록 + 리뷰 절차 필요. 1인 개발자가 단독으로 셀프서브 가입할 방법이 없음 (2026-07 확인).
   → **이 프로젝트 규모에서는 사실상 불가능.**
2. **Mac 한 대 + chat.db 폴링 + AppleScript 발신 (비공식)**: 커뮤니티 표준 패턴(BlueBubbles, imsg CLI 등).
   기술적으로는 동작하고, 같은 Apple ID(=이 Mac)로 여러 지인이 문자를 보내면 발신자별로 구분해
   온보딩·코칭이 가능함 — "친구들이 내 봇에게 문자한다" 시나리오에 딱 맞음.
   ⚠️ **단, Apple 이용약관은 개인 계정에서의 자동화된 메시징을 명시적으로 금지한다.** 개인용(본인 +
   소수 지인)으로 조용히 쓰는 것과, 불특정 다수에게 노출되는 것은 리스크가 다르다.

### 결정: 방식 A 채택 (사용자 확인 완료, ditto[heyditto.ai] 참고)

사용자가 방식 A(Mac+chat.db, ToS 리스크 인지)를 선택, 나아가 **iMessage를 메인 진입점으로 삼는 것**을
목표로 지정. 참고 사례로 언급한 "ditto"는 대학생 대상 소개팅 서비스로, **앱 설치 없이 iMessage 자체가
제품 표면인 UX 패턴**의 실사례(4.2만 사용자 규모로 검증됨) — 단, ditto는 펀딩받은 스타트업이라 공식
Apple Messages for Business/MSP 파트너십을 썼을 가능성이 높고, 1인 개발자는 그 경로를 못 쓴다는
제약은 그대로 유효함. 우리가 가져오는 건 "UX 패턴"이지 "그들의 백엔드 접근 권한"이 아님.

### 구현 완료 (2026-07-13)

- ✅ `interfaces/imessage/applescript.py` — 발신(`osascript`), AppleScript 문자열 이스케이프,
  긴 메시지 청크 분할. `runner` 기본값을 함수 정의 시점에 바인딩하지 않고 호출 시점에
  `subprocess.run`을 조회하도록 설계 — 그렇지 않으면 테스트에서 몽키패치가 무력화됨 (아래 인시던트 참고)
- ✅ `interfaces/imessage/chat_db.py` — 수신 폴링, `message`/`handle` 테이블 조인, ROWID 커서 기반
  증분 읽기, Full Disk Access 실패 시 명확한 `ChatDBPermissionError`. `attributedBody`(서식 있는
  메시지) 폴백은 best-effort 휴리스틱으로 구현 — 완전한 NSKeyedArchiver 파서는 아님, 실패 시
  추측하지 않고 해당 메시지를 건너뛰고 로그만 남김
- ✅ `interfaces/imessage/adapter.py` — `CoachingPort` 구현. 버튼/옵션은 번호 매긴 텍스트로 렌더링,
  다음 답장을 번호/라벨로 역매칭. TelegramAdapter와 동일한 pending-input/asyncio.Event 패턴이라
  Flow 레이어(온보딩 등) 코드 변경 없이 동작 — 단, 실제 온보딩 플로우 연결은 아래 미완료 항목 참고
- ✅ `interfaces/imessage/poller.py` — chat.db 폴링 → (진행 중인 flow가 있으면 그쪽에 전달) →
  없으면 기존 `MessageHandler`(CLI/Telegram/MCP가 이미 쓰는 자연어 코칭 엔진)로 라우팅 → AppleScript
  회신. 발신자(handle)별 세션은 상태 파일(`~/.config/garmin_coach/integrations/imessage_state.json`)로
  격리 — 여러 지인이 같은 Mac으로 문자해도 각자 독립적으로 처리됨
- ✅ 신규 연락처 최초 문자 시 "먼저 `garmin-coach setup` 실행" 안내 (대화형 온보딩 연결 전까지 임시)
- ✅ CLI 엔트리포인트 `garmin-coach-imessage` 추가
- ✅ 테스트 37개 (applescript/chat_db/adapter/poller) — 전부 synthetic sqlite + 주입식 sender로,
  실제 chat.db나 Messages.app을 절대 건드리지 않음

### ⚠️ 개발 중 실제 인시던트 (기록)

`IMessagePoller`가 최초 구현에서 주입된 sender를 안 쓰고 모듈 레벨 `send_imessage`를 직접 호출하는
버그가 있었음 → 테스트가 이걸 못 잡고 실제 로컬 Mac의 `osascript`/Messages.app을 호출해버려서
가짜 테스트 전화번호(`+15551234567`)로 실제 발신을 시도함 (존재하지 않는 연락처라 전송 자체는
실패했을 가능성이 높지만, 실제 subprocess가 여러 차례 실행됨 — 테스트 1회가 105초 걸린 게 단서였음).
수정: poller가 항상 `self.sender`(adapter와 공유)를 쓰도록 강제 + `tests/conftest.py`에
`subprocess.run` 자체를 막는 autouse 가드 추가 (앞으로 같은 클래스의 버그가 나면 행(hang) 대신
즉시 AssertionError로 실패). **교훈**: 함수 시그니처의 기본값으로 `subprocess.run`을 직접 바인딩하면
정의 시점에 고정되어 이후 몽키패치가 안 먹힘 — 함수 본문에서 `runner or subprocess.run`으로
지연 조회해야 테스트로 가로챌 수 있음.

### 추가 구현 완료 (2026-07-13, 2차)

- ✅ **서비스 추출**: `_UserProfileService` + `_scoped_garth_home`를 `garmin_coach/services/user_profile.py`로
  기계적 추출(verbatim 이동, 스크립트로 경계 검증). telegram_bot.py는
  `UserProfileService as _UserProfileService` 별칭으로 re-import — 기존 테스트의 서브클래싱/몽키패치
  전부 무수정 호환. 상태 루트는 `telegram_states/` 경로 그대로 유지(이름은 역사적 유물이지만
  기존 사용자 프로필이 이미 거기 있어서 이관 이득 없음 — services 모듈 docstring에 기록).
- ✅ **대화형 온보딩 배선**: 폴러를 async 루프(`run_async`)로 전환. 신규 연락처 첫 문자 →
  `OnboardingFlow`(Telegram과 동일 플로우, CoachingPort 경유)가 백그라운드 태스크로 시작,
  이후 답장은 pending-input 경로로 플로우에 전달. 온보딩 크래시/프로세스 재시작 후에는
  "시작"/"/start"/"온보딩" 키워드로 저장된 진행상황에서 재개(프로필 존재 검사 대신 명시적
  키워드를 택함 — 러닝 루프 안에서 sync 프로필 검사가 불가능하고, 예측 가능성도 더 좋음).
  이벤트 루프 없는 sync 호출(테스트/원샷 스크립트)에서는 기존 nudge 폴백 유지. 테스트 12종.

### 미완료 (다음 착수 항목)

- 🔲 이미지 전송: AppleScript는 파일 경로만 첨부 가능(원시 bytes 불가) — 임시로 텍스트 안내로 대체 중
- 🔲 사진 수신(`request_photo`): 항상 스킵 처리 중. `attachment` 테이블 연동은 로드맵
- 🔲 스케줄 브리핑 push 경로를 Telegram scheduler와 공유하도록 연결 (→ S-B에서 진행)
- 🔲 **실사용 검증**: Full Disk Access 승인 후 사용자 본인 Mac에서 실제 문자로 왕복 테스트 필요 —
  synthetic 테스트로는 검증 못 하는 부분(실제 Messages.app 동작, 실제 chat.db 스키마 버전 차이,
  실제 Garmin 로그인이 온보딩 중 이뤄지는 경로 등)

## S-D. 리포트 & 트렌드

- 🔲 주간 리포트를 `list_recent_snapshots()` 기반 캐시-온리로 재작성 (API 0콜)
- 🔲 백필 명령 `gc backfill --days 30` (과거 날짜 스냅샷 일괄 수집 — 이후 영구 캐시)

## 완료 정의 (모든 스트림 공통)

1. `pytest` 전체 통과 + `ruff check` 클린
2. Engine/Flows에서 `GarminAdapter` 건강지표 직접 호출 신규 추가 금지 (SnapshotService 경유)
3. 사용자-노출 응답에 신선도 라벨 규칙 적용
