# Garmin Personal Coach — PRD v3.0

> **Product Vision**: 매일 아침, 워치를 보기 전에 **"오늘 뭘 해야 하는지" 3초 안에 아는** 개인 AI 코치.
> 데이터 수집이 아니라 **의사결정 속도**가 제품이다. Garmin이 데이터를 모으고, 우리는 결정을 준다.

> v2.0 → v3.0 변경 요지: 기능 나열형 PRD에서 **"속도-신뢰-루프" 3축** 중심으로 재편.
> v2.0이 정의한 기능 대부분(가드레일, 온보딩, 영양, 피드백, 리포트)은 이미 구현되어
> 229개 테스트가 통과 중이므로, v3.0은 **무엇을 만들지**보다 **어떻게 느껴져야 하는지**와
> **데이터를 얼마나 빨리 가져오는지**를 규정한다.

---

## 1. 방향성: 세 개의 축

| 축 | 정의 | 측정 |
|----|------|------|
| **Speed** | 어떤 질문이든 3초 안에 첫 응답. 데이터가 덜 준비됐으면 캐시로 먼저 답하고 뒤에서 갱신 | `/today` p50 < 1s (캐시), < 5s (콜드) |
| **Trust** | 모든 권고에 근거 데이터 + 안전 가드레일. 데이터가 오래됐으면 오래됐다고 표시 | 가드레일 우회 0건, 신선도 라벨 100% |
| **Loop** | 코칭 → 실행 → 자동 감지 → 피드백 → 다음 코칭 반영. 사용자가 뭔가 "입력"하는 순간은 탭 1~2회 | 운동 후 피드백 응답률 > 60% |

### 채널 전략
- **1차 채널 (v3.x)**: Telegram(구현됨) · **iMessage(신규, 방식 결정 필요 — work-orders §S-F 참고)** · MCP(구현됨). CLI는 개발/디버깅용.
- **iMessage 현실**: 공식 API 없음. Apple Messages for Business는 MSP 파트너십이 필요해 1인
  개발자에게 사실상 불가능. 남은 길은 Mac 한 대의 chat.db 폴링 + AppleScript 발신(커뮤니티 표준
  패턴) — 기술적으로 여러 지인이 같은 Mac으로 문자해도 발신자별 분리가 가능하지만, Apple 이용약관은
  개인 계정의 자동화 메시징을 금지한다. **착수 전 사용자 결정 필요** (개인/지인 스코프로 리스크
  감수 / 보류 / SMS 대체).
- **로드맵 (v4)**: 모바일 앱, 웹 대시보드. `CoachingPort` 추상화 덕분에 Flows/Engine 수정 없이
  어댑터만 추가하면 됨 — 이 규칙을 지키는 것이 앱/웹 출시의 선행 조건.

### 무엇이 아닌가 (Non-goals)
- 멀티유저 SaaS 아님. 로컬 우선, 1인용. (스키마는 `user_id`로 이미 멀티유저 대비됨 — 유지만 한다)
- Garmin 지표의 재발명 아님. Garmin Training Readiness가 있으면 **그걸 신뢰하고 가중 45%로 쓴다**
  (현 `engine/readiness.py` 동작 유지). 우리 점수는 Garmin 미지원 워치의 폴백 + TSB 보정 레이어.

---

## 2. 데이터 전략: Daily Snapshot

### 2.0 데이터 접근 현실 (2026-07 리서치 반영)

**Garmin**: 2026년 3월 중순부터 Garmin이 자동화 SSO 로그인을 Cloudflare 차원에서 차단
(TLS 핑거프린팅 + 계정 단위 429). garth는 이로 인해 사망. 현재 유일하게 신뢰 가능한 경로는
**garminconnect ≥ 0.3.6** — `curl_cffi` 브라우저 TLS 임퍼스네이션 + widget 로그인 전략으로 우회.
- 로그인은 드물게, 토큰 재사용은 길게: 최초 1회 `garmin-coach connect-garmin`(MFA 지원) 후
  refresh 토큰으로 ~30일 무재인증. **재로그인 루프는 계정 단위 429를 유발하므로 절대 금지.**
- HTML 파싱 기반이라 깨질 수 있음 → 로그인 실패 시 사용자에게 "라이브러리 업데이트 확인" 안내가
  1차 대응 (garminconnect가 커뮤니티에서 가장 빨리 패치되는 라이브러리).

**Strava**: 2026-06-01부터 Standard tier는 Strava 구독 필수 + 중개 플랫폼 경유 금지,
2026-09-01 일부 엔드포인트 폐기. → **보조 싱크 지위 유지, 신규 투자 중단.** 사용자가 본인
API 앱 + 구독을 가진 경우에만 동작하는 opt-in 기능으로 유지.

**AI (LLM)**: API 키 요구는 마찰. 우선순위 체인으로 zero-config화:
`명시 설정 > 환경변수 API 키 > 로컬 AI CLI 자동 감지(claude/gemini/codex, 구독 인증 재사용) > 룰 기반`.
로컬 CLI는 `claude -p` 헤드리스 모드로 호출 — 사용자는 아무 설정도 하지 않아도 AI 코칭이 붙는다.

### 2.05 데이터 계약 (Data Contract) — 2026-07-25 사고 이후 필수 규칙

건강 지표 파서가 **상상한 스키마**로 작성되었고, 테스트 픽스처도 **같은 상상**으로 작성되어
파서와 테스트가 서로의 거짓을 승인했다. 294개 테스트가 초록불인 채로 프로덕션에서는
수면·스트레스·RHR·Body Battery가 전부 `None`으로 파싱됐고, 그 결과 Readiness 점수는
TSB 하나(가중치 100%)로만 계산되어 사실상 무의미한 기본값을 사용자에게 보여줬다.
**안전 가드레일(수면 부족·BB 고갈 시 하드세션 차단)도 입력이 전부 None이라 한 번도 발동하지 않았다.**

재발 방지 3원칙:

1. **Fixture-from-reality** — 모든 파서는 `tests/fixtures/garmin/`의 **실계정 캡처 픽스처**로만
   검증한다. 픽스처 없이 키 경로를 바꾸지 않는다. 상상으로 쓴 테스트는 상상으로 쓴 파서를
   절대 반증하지 못한다.
2. **값 기준 판정** — "수집 성공"은 객체 존재가 아니라 **핵심 값 존재**로 판정한다.
   빈 껍데기 객체가 "6개 수집, 에러 0건"으로 보고되던 것이 사고를 숨긴 직접 원인이다.
3. **라이브 계약 검사** — `garmin-coach doctor`가 "Garmin이 데이터를 줬는가" 대 "파서가 뽑아냈는가"를
   대조한다. 둘이 어긋나면 `PARSE_MISS`(스키마 드리프트 경보). 이것이 사고 당일 잡아냈어야 할 검사다.

**워치 미동기화는 에러가 아니라 1급 시나리오다.** Garmin은 동기화 안 된 날에도 봉투(envelope)는
보내되 모든 값을 null로 채운다. 이 경우 "가져오지 못했어요"가 아니라 "아직 워치 데이터가 없어요"로
안내해야 하며, 파서는 빈 껍데기 대신 `None`을 반환해야 한다.

**신선도는 계산 날짜가 아니라 마지막 실제 데이터 날짜로 판정한다.** CTL/ATL은 지수감쇠라
4개월 전 입력으로도 "오늘자" 숫자를 만들어낸다. `snapshot.date`는 신선도의 증거가 아니다
(실제로 108일 묵은 데이터가 "0일 전"으로 보고됐다). `last_data_date`를 쓴다.

### 2.1 원칙

1. **하루 = 스냅샷 1개.** 개별 API를 흩어 부르지 않고, 하루치 건강 데이터를 한 번에 병렬로 가져와
   `daily_health` 테이블에 통째로 저장한다.
2. **과거는 불변.** 어제 이전 날짜의 수면/HRV/RHR은 다시 안 바뀐다 → 영구 캐시, 재요청 금지.
3. **오늘은 TTL 30분.** Body Battery/스트레스는 실시간으로 변하므로 오늘 날짜만 TTL을 둔다.
4. **캐시 먼저, 갱신은 뒤에서.** 응답은 항상 캐시에서 즉시. 스테일이면 "N분 전 데이터" 라벨을 붙이고
   백그라운드에서 새로고침.
5. **부분 실패 허용.** 6개 지표 중 4개만 와도 스냅샷은 성립. Readiness 엔진이 이미
   가중치 재분배(누락 성분 제외 정규화)를 지원한다.

### 2.2 P0 스냅샷 구성 (병렬 1-batch)

| 지표 | garminconnect 호출 | 왜 P0인가 |
|------|--------------------|-----------|
| Training Readiness | `get_training_readiness(date)` | Garmin 종합 점수. 있으면 우리 계산의 45% |
| Sleep | `get_sleep_data(date)` | 회복 판단의 25% |
| HRV | `get_hrv_data(date)` | 과훈련 조기 감지. 가드레일 입력 |
| Body Battery | `get_body_battery(date, date)` | 아침 에너지 레벨 |
| Stress | `get_stress_data(date)` | 정신 부하 |
| RHR | `get_rhr_day(date)` | 이상 감지 (기준선 +15bpm 알림) |

+ 활동 목록은 별도 트랙: `get_activities_by_date(start, end)` 1콜로 기간 전체를 받고
활동별 상세(`get_activity_details`)는 **새 활동 감지 시에만** 지연 호출.

P1 (스냅샷에 포함하되 실패해도 무시): SpO2, 체성분.
P2 (요청 시에만): Running Dynamics, GPS/고도.

### 2.3 호출 예산 (Latency Budget)

```
콜드 스타트 (캐시 없음):
  세션 resume 1회 + 병렬 6콜 (ThreadPoolExecutor, max_workers=6)
  = 가장 느린 단일 콜 시간 ≈ 1~3s   (기존: 직렬 6~8콜 × 재시도 3회 = 최악 수십 초)

웜 패스 (오늘 두 번째 질문부터):
  SQLite 조회만 = < 50ms

과거 7일 트렌드 (주간 리포트):
  전부 불변 캐시 히트. 신규 API 콜 0회 (첫 빌드 때만 backfill)
```

재시도는 스냅샷 단위가 아니라 **개별 지표 단위 1회**로 축소한다. 지표 하나가 죽어도
나머지 5개로 코칭하고, 다음 갱신 주기에 자연 복구.

### 2.4 신선도 계약 (Freshness Contract)

모든 사용자-노출 응답은 스냅샷의 `fetched_at`을 기준으로:

- `< 30min`: 라벨 없음
- `30min ~ 24h`: "🕐 N시간 전 데이터" 접미
- `> 24h` 또는 부분 실패: "⚠️ 워치 동기화를 확인해주세요" + 갖고 있는 것으로 코칭

---

## 3. 사용자 편의성: 핵심 여정 4개

페르소나(지구력 선수/일반 피트니스/부상 복귀)는 v2.0 정의를 유지한다. v3.0은 여정을 규정한다.

### J1. 아침: 묻기 전에 알려준다
- 스케줄러가 설정 시각(기본 07:00)에 스냅샷 선행 fetch → 브리핑 push.
- 사용자가 열었을 때는 이미 준비 완료. Readiness + 오늘 세션 + 근거 3줄.
- 버튼: [계획대로] [변경] [미루기] — 탭 1회로 끝.

### J2. 운동 직후: 30초 피드백 루프
- 활동 폴링이 새 activity 감지 → 자동 분석 push (상세는 이때만 fetch).
- RPE/느낌은 인라인 버튼. 타이핑 없이 탭 2회.
- 통증 보고 시 다음 세션 가드레일에 즉시 반영.

### J3. 아무때나: /today는 항상 즉답
- 캐시에서 < 1초 응답. 스테일 라벨 + 백그라운드 갱신 후 필요 시 후속 메시지.
- CLI `gc status`도 동일한 스냅샷 저장소를 읽는다 — 채널 간 데이터 불일치 없음.

### J4. 일요일 저녁: 주간 리뷰
- 캐시된 7일 스냅샷 + 트레이닝 로드로 API 콜 0회 리포트.
- CTL/ATL/TSB 추이 + 다음 주 계획 + 코치 코멘트.

### 편의성 규칙
1. **타이핑은 최후의 수단.** 모든 정기 상호작용은 버튼으로 완결.
2. **push가 pull보다 먼저.** 사용자가 물어보는 것은 시스템이 놓쳤다는 뜻.
3. **에러를 사용자에게 전가하지 않는다.** "가져오지 못했습니다" 대신 "어제 데이터 기준으로는 ~".

---

## 4. 아키텍처

### 4.1 3-Layer 유지 + Data Plane 신설

```
┌──────────────────────────────────────────────────┐
│ Interface: interfaces/telegram | cli | mcp_server │
└────────────────────┬─────────────────────────────┘
                     │ CoachingPort
┌────────────────────▼─────────────────────────────┐
│ Flows: morning_briefing | post_workout | ...      │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────┐
│ Engine: readiness | guardrails | training_plan    │
└────────────────────┬─────────────────────────────┘
                     │ ← 여기가 v3.0 신설 지점
┌────────────────────▼─────────────────────────────┐
│ Data Plane: SnapshotService (cache-first)         │
│   adapters/garmin/snapshot.py ← 병렬 fetch        │
│   storage/database.py         ← SQLite (기존)     │
└──────────────────────────────────────────────────┘
```

**규칙**: Engine/Flows는 `GarminAdapter`를 직접 부르지 않는다. 반드시 `SnapshotService`를 통해
캐시-우선으로 읽는다. 어댑터 직접 호출은 Data Plane 내부에만 존재.

### 4.2 레거시 정리 (v3.0 부채 상환)

| 레거시 (flat) | 정본 (layered) | 조치 |
|---------------|----------------|------|
| `telegram_bot.py` (1,623줄) | `interfaces/telegram/` | 점진 이관 후 삭제 |
| `scheduler.py` | `interfaces/telegram/scheduler.py` | 통합 |
| `morning_checkin.py` / `evening_checkin.py` | `flows/morning_briefing.py` / `flows/evening_checkin.py` | 이관 |
| `activity_fetch.py` + `adapters/fetch.py` | Data Plane `SnapshotService` | 흡수 |
| `setup_wizard.py` | `wizard/` | 통합 |
| root `ports.py` | 유지 (정본) | — |

정리 순서는 "새 기능이 그 파일을 건드릴 때 함께 이관" — 빅뱅 리라이트 금지.

### 4.3 안전 가드레일

v2.0 §8 전체 유지 (구현 완료: `engine/guardrails.py` 594줄 + `docs/safety/coaching_guardrails.md`).
v3.0 추가 규칙 1개: **스테일 데이터 가드** — 24시간 이상 오래된 스냅샷으로는
하드 세션(Zone 4+)을 새로 권고하지 않는다.

---

## 5. 작업 스트림 (v3.0)

### S-A. Data Plane (최우선, 지금)
- [ ] `adapters/garmin/snapshot.py` — 병렬 fetch + 부분 실패 허용
- [ ] `SnapshotService` — 캐시-우선 읽기, TTL(오늘 30분/과거 영구), 신선도 라벨
- [ ] `engine/readiness` · `flows/morning_briefing` 호출 경로를 SnapshotService로 전환
- [ ] `is_authenticated()` 네트워크 콜 제거 (토큰 존재 검사 + 첫 실제 콜에서 판정)

### S-B. 여정 완성도
- [ ] 아침 브리핑 선행-fetch 스케줄 (push 시점에 이미 웜 캐시)
- [ ] 활동 폴링 → post_workout 자동 트리거 배선 점검
- [ ] 신선도 라벨을 Telegram/CLI 렌더러에 일괄 적용

### S-C. 레거시 상환
- [ ] `activity_fetch.py`/`fetch.py` → SnapshotService 흡수
- [ ] `telegram_bot.py` 명령어를 `interfaces/telegram/handlers.py`로 단계 이관

### S-D. 리포트 & 트렌드
- [ ] 주간 리포트를 캐시-온리로 재작성 (API 0콜)
- [ ] 7일 백필 명령 `gc backfill --days 30`

### S-E. 로드맵 (v3.x)
- 사진 기반 식단 분석 (Vision LLM), 카카오톡 채널, 레이스 예측 모델 — v2.0 §11 Phase 6 승계

---

## 6. 성공 지표

| 지표 | v3.0 목표 | 측정 |
|------|-----------|------|
| `/today` 응답 p50 (웜) | < 1s | logfire 트레이스 |
| 아침 브리핑 fetch p50 (콜드) | < 3s | logfire 트레이스 |
| 하루 Garmin API 콜 수 | < 20콜 (기존 무제한 폴링 대비) | fetch 카운터 |
| 스테일 라벨 정확도 | 100% (모든 응답에 신선도 반영) | 테스트 |
| 운동 후 피드백 응답률 | > 60% | feedback 테이블 |
| 가드레일 발동률 | < 10% | guardrail 로그 |

---

## 부록: v2.0에서 승계된 확정 사양

아래는 v2.0에서 정의되고 이미 구현/테스트된 사양으로, v3.0에서도 유효하다.
상세는 git history의 v2.0 문서 참조.

- 온보딩 3단계 (필수/권장/선택) 및 `UserProfile` 데이터 모델 — `flows/onboarding.py`, `models/user_profile.py`
- Periodized Nutrition (Fuel for the Work Required) — `nutrition/`
- 피드백 수집·집계 — `feedback/`, `models/feedback.py`
- 안전 가드레일 이중 레이어 (MD 규칙 + 코드 하드리밋) — `engine/guardrails.py`
- Readiness 가중치: Garmin TR 있으면 45% 우선, 없으면 HRV 30/수면 25/BB 15/RHR 15/TSB 10/스트레스 5
- Telegram 명령어 체계 (`/start` `/today` `/week` `/report` `/feedback` `/nutrition` `/settings` `/goals` `/injury` `/help`)
- Strava는 보조 싱크 전용, Garmin이 유일한 primary source
