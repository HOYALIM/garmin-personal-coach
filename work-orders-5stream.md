# Garmin Personal Coach — 병렬 작업지시서 v2 (5 Streams)

## 스트림 구조

```
Stream 1: Foundation / Data / Safety
Stream 2: Flow Architecture / Telegram
Stream 3: Onboarding / Profile / Settings
Stream 4: Nutrition
Stream 5: Feedback + Reports
```

### 의존성 그래프

```
Week 1       Week 2       Week 3       Week 4       Week 5       Week 6       Week 7-10
┌────────────────────────────────────────────────────────────────────────────────────┐
│ S1: Foundation / Data / Safety                                                     │
│ [models+auth] [health.py] [readiness] [guardrails] [training_plan] [tuning]       │
└──┬─────────────┬───────────────────────┬───────────────────────────────────────────┘
   │             │                       │
   │ models/     │ health data           │ guardrails API
   │ 확정        │ 사용 가능             │ 확정
   │             │                       │
┌──▼─────────────▼───────────────────────▼───────────────────────────────────────────┐
│ S2: Flow Architecture / Telegram                                                    │
│ [ports.py] [adapter] [keyboards] [renderer] [handlers] [scheduler] [polish]        │
└──┬──────────────────────────────────────────────────────────────────────────────────┘
   │
   │ ports.py + adapter 확정
   │
┌──▼─────────────────────────────────────────────────────────────────────┐
│ S3: Onboarding / Profile / Settings                                    │
│      [profile models] [Phase1] [Phase2] [Phase3] [settings] [test]    │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ S4: Nutrition                                                          │
│      [macros] [timing] [hydration] [recovery] [photo食단] [integrate] │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ S5: Feedback + Reports                                                 │
│      [collector] [auto_analysis] [subjective] [photo운동] [aggregator]│
│      [weekly] [monthly] [charts] [integrate]                          │
└────────────────────────────────────────────────────────────────────────┘
```

### 병렬성 요약

| | S1 | S2 | S3 | S4 | S5 |
|--|----|----|----|----|-----|
| **Week 1** | ✅ 시작 | ✅ 시작 | ⏳ S2 ports 대기 | ⏳ S1 models 대기 | ⏳ S1 models 대기 |
| **Week 2** | 진행 | 진행 | ✅ 시작 | ✅ 시작 | ✅ 시작 |
| **Week 3+** | 진행 | 진행 | 진행 | 진행 | 진행 |

- S1과 S2는 **Week 1부터 동시 시작** (서로 독립)
- S3, S4, S5는 **Week 2부터 동시 시작** (S1 models + S2 ports 확정 후)
- S3/S4/S5는 서로 **완전 독립** (병렬도 최대)

---

## 작업 전 공통 규칙 (모든 스트림 필독)

### 1. 인터페이스 계약 (Contract-First)

**각 스트림은 구현 전에 인터페이스부터 합의한다.**

```python
# 이 파일들이 모든 스트림의 "계약서" 역할
garmin_coach/
├── ports.py                 # S2가 정의, 모두가 참조
├── models/
│   ├── user_profile.py      # S1이 정의, S3이 주 소비자
│   ├── health_metrics.py    # S1이 정의, S4/S5가 소비
│   ├── coaching.py          # S1이 정의, S4/S5가 소비
│   └── feedback.py          # S5가 정의, S1/S3이 참조
└── engine/
    └── interfaces.py        # S1이 정의, S4/S5가 참조
```

**규칙**: 계약 파일을 수정하면 반드시 다른 스트림에 알린다. PR 리뷰 필수.

### 2. 브랜치 전략

```
main
├── stream-1/foundation-data-safety
├── stream-2/flow-telegram
├── stream-3/onboarding-profile
├── stream-4/nutrition
└── stream-5/feedback-reports
```

- 각 스트림은 자기 브랜치에서 작업
- `models/`, `ports.py`, `engine/interfaces.py` 수정 시 main에 먼저 머지 후 다른 스트림이 rebase
- 주 1회 이상 main에 머지 (충돌 최소화)

### 3. 테스트 원칙

- 각 스트림은 자기 영역의 유닛 테스트를 반드시 작성
- 외부 의존성(Garmin API, Telegram API, LLM)은 mock 처리
- 통합 테스트는 Week 5부터 별도 진행

### 4. 코드 스타일

- Python 3.11+, type hints 필수
- dataclass 또는 Pydantic v2 사용 (모델)
- async/await 기본 (Telegram 호환)
- ruff 포맷터 + mypy strict

### 5. flows/ 격리 규칙

```bash
# CI에서 강제 체크 — 0 결과여야 빌드 통과
grep -r "telegram" garmin_coach/flows/ && exit 1
grep -r "from garmin_coach.interfaces" garmin_coach/flows/ && exit 1
```

flows/ 안의 모든 파일은 `ports.py`의 `CoachingPort`만 import 가능. 채널 구현체를 직접 참조하면 안 됨.

---

## Stream 1: Foundation / Data / Safety

> 모든 스트림의 기반. 데이터 모델, 건강 데이터 수집, Readiness Score,
> 안전 가드레일, 코칭 엔진 코어를 담당.

### 담당 범위

```
garmin_coach/
├── models/                   # 🔲 전체 데이터 모델 정의
│   ├── user_profile.py
│   ├── health_metrics.py
│   └── coaching.py
├── adapters/garmin/
│   ├── auth.py               # ✅ 기존 확인/업데이트
│   ├── activity.py           # ✅ 기존 확장
│   └── health.py             # 🔲 수면/HRV/BB/Stress/RHR/SpO2
├── adapters/strava/          # ✅ 기존 확인
├── integrations/
│   ├── training_load.py      # ✅ 확장 (Ramp Rate, Monotony, Strain)
│   └── sync.py               # ✅ 확장 (이벤트 발행)
├── engine/
│   ├── interfaces.py         # 🔲 엔진 인터페이스 정의
│   ├── readiness.py          # 🔲 Readiness Score
│   ├── coaching.py           # ✅ 확장 (Readiness 기반)
│   ├── guardrails.py         # 🔲 안전 가드레일 (하드 레이어)
│   ├── training_plan.py      # 🔲 주간 계획 생성
│   └── rules.py              # ✅ Rule-based fallback 확장
├── storage/                  # 🔲 데이터 저장 레이어
│   └── database.py
└── docs/safety/
    └── coaching_guardrails.md  # 🔲 안전 규칙 파일 (소프트 레이어)
```

### PRD 참조

- 섹션 3: 데이터 아키텍처 전체
- 섹션 3.1: Garmin 데이터 수집 매트릭스
- 섹션 3.2: Readiness Score
- 섹션 8: 안전 가드레일 전체

### 상세 작업 항목

#### Phase 1-1: 모델 + 인증 (Week 1) ⚡ 크리티컬 패스

**1-1-A: 데이터 모델 전체 정의**
```
목표: 모든 스트림이 참조할 데이터 모델 확정

산출물:
- models/user_profile.py
  → UserProfile, MedicalProfile, InjuryRecord, NutritionProfile,
    TrainingGoal, CoachingPreferences, SleepProfile
  → (PRD 섹션 4.5 데이터 모델 그대로 구현)

- models/health_metrics.py
  → HealthMetrics (daily snapshot — 하루치 건강 데이터 통합 뷰)
  → SleepData (score, stages, duration, deep/rem/light/awake 각 분)
  → HRVData (value_ms, status, baseline_ms, deviation_pct)
  → BodyBatteryData (morning_value, current_value, charged, drained)
  → StressData (avg, max, rest_avg, time_in_high)
  → RHRData (value_bpm, baseline_bpm, deviation_bpm)
  → SpO2Data (avg_pct, min_pct)
  → ReadinessScore (score 0-100, level green/yellow/red/critical, components dict)
  → TrainingLoad (ctl, atl, tsb, ramp_rate, monotony, strain)
  → ActivitySummary (type, distance, duration, avg_hr, max_hr, zones, tss,
    training_effect_aerobic, training_effect_anaerobic, laps)

- models/coaching.py
  → CoachingResponse (text, intensity, max_zone, uses_hr_zones,
    session_type, guardrail_applied, guardrail_reason)
  → SessionType enum (REST, EASY, MODERATE, HARD, LONG, INTERVAL, TEMPO, RACE)
  → WorkoutAnalysis (summary, zone_distribution, comparison_to_recent,
    pace_drift, coaching_notes)
  → WeeklyPlan (days: list[DayPlan], total_tss, notes)
  → DayPlan (date, session_type, description, target_tss)

⚠️ 반드시 Week 1 금요일까지 PR → main 머지.
   S3, S4, S5는 이 모델 기반으로 Week 2부터 작업 시작.
```

**1-1-B: 엔진 인터페이스 정의**
```
목표: S4, S5가 코칭 엔진을 호출하는 인터페이스 확정

산출물: engine/interfaces.py

class CoachingEngine(ABC):
    """모든 코칭 요청의 진입점. S4/S5는 이 인터페이스만 바라봄."""

    async def generate_daily_coaching(
        user: UserProfile, metrics: HealthMetrics, readiness: ReadinessScore,
    ) -> CoachingResponse

    async def generate_workout_analysis(
        user: UserProfile, activity: ActivitySummary,
    ) -> WorkoutAnalysis

    async def generate_weekly_plan(
        user: UserProfile, current_load: TrainingLoad,
        readiness_trend: list[ReadinessScore], feedback_history: list[SessionFeedback],
    ) -> WeeklyPlan

    async def answer_question(
        user: UserProfile, question: str, context: CoachingContext,
    ) -> CoachingResponse

⚠️ Week 1 끝나기 전에 main에 머지.
```

**1-1-C: 인증 레이어 확인/업데이트**
```
목표: Garmin Connect 인증이 최신 방식으로 동작하는지 확인

확인사항:
- python-garminconnect 최신 버전 (garth 기반 → 모바일 SSO 전환됨)
- 토큰 자동 갱신(auto-refresh) 동작
- MFA 대응 여부
- 토큰 저장 경로 및 보안 (chmod 700)

산출물:
- adapters/garmin/auth.py 업데이트 (필요 시)
- 인증 + 토큰 갱신 테스트 코드
```

#### Phase 1-2: 건강 데이터 수집 (Week 2-3)

**1-2-A: health.py — 건강/회복 데이터 수집기**
```
목표: Garmin Connect에서 P0 건강 데이터 전체 수집

구현할 메서드 + API 매핑:
- get_sleep_data(date) → SleepData
  API: api.get_sleep_data(date_str)
- get_hrv_data(date) → HRVData
  API: api.get_hrv_data(date_str)
- get_body_battery(start, end) → list[BodyBatteryData]
  API: api.get_body_battery(start_str, end_str)
- get_stress_data(date) → StressData
  API: api.get_stress_data(date_str)
- get_rhr_day(date) → RHRData
  API: api.get_resting_heart_rate(date_str)
- get_spo2_data(date) → SpO2Data
  API: api.get_spo2_data(date_str)
- get_body_composition(date) → BodyCompositionData
  API: api.get_body_composition(date_str)
- get_training_readiness(date) → TrainingReadinessData
  API: api.get_training_readiness(date_str)

에러 처리:
- API rate limit → 지수 백오프 재시도 (최대 3회, 1s/2s/4s)
- 데이터 없음 (워치 미착용 등) → None 반환 + 로깅
- 인증 만료 → 자동 토큰 갱신 후 재시도
- 네트워크 장애 → 마지막 성공 데이터 캐시 반환 + 경고

산출물: adapters/garmin/health.py + tests/test_garmin_health.py
```

**1-2-B: activity.py 확장**
```
목표: 기존 운동 데이터에 Training Effect, Running Dynamics, 랩 데이터 추가

추가 필드:
- Training Effect (유산소 0.0-5.0 / 무산소 0.0-5.0)
- Running Dynamics (케이던스, GCT, 보폭) — 지원 기기에서만, 없으면 None
- 랩 데이터 (인터벌 세션: 랩별 페이스, HR, 회복시간)

산출물: adapters/garmin/activity.py 확장 + 테스트
```

#### Phase 1-3: Training Load 확장 + Readiness Score (Week 3-4)

**1-3-A: training_load.py 확장**
```
목표: Ramp Rate, Monotony, Strain 추가

Ramp Rate:
- ramp_rate = CTL_today - CTL_7days_ago
- 경고 임계값: > 5.0/주

Monotony:
- monotony = weekly_load_avg / weekly_load_stddev
- 경고 임계값: > 2.0

Strain:
- strain = weekly_load_sum × monotony
- 경고 임계값: strain > CTL × 2

산출물: integrations/training_load.py 확장 + 테스트
```

**1-3-B: readiness.py — Readiness Score**
```
목표: PRD 섹션 3.2 구현

입력: HealthMetrics (당일)
출력: ReadinessScore (score 0-100, level, components)

가중치:
- HRV Status: 0.30 (7일 기준선 대비 편차 %)
- Sleep Score: 0.25 (Garmin 0-100)
- Body Battery: 0.15 (기상 시)
- RHR Deviation: 0.15 (7일 평균 대비 bpm 편차)
- TSB: 0.10
- Stress Avg: 0.05 (전일)

각 컴포넌트 정규화:
- 0-100 스케일이 아닌 것은 정규화 필요
  (예: TSB -30~+30 → 0-100, HRV 편차 -30%~+30% → 0-100)

임계값: Green ≥75 | Yellow 50-74 | Red 30-49 | Critical <30

캘리브레이션:
- 최소 14일 데이터 → 기준선 산출
- <14일 → 가용 데이터로만 계산 + confidence: "low" 표시
- 컴포넌트 데이터 없으면 (예: 워치 미착용) 해당 가중치 재분배

산출물: engine/readiness.py + tests/test_readiness.py
```

#### Phase 1-4: 안전 가드레일 (Week 3-5)

**1-4-A: coaching_guardrails.md — 소프트 레이어**
```
목표: LLM 시스템 프롬프트에 포함될 규칙 파일 작성

PRD 섹션 8.2 내용 그대로 작성:
1. 과훈련 방지 (TSB, Ramp Rate, 주간 볼륨, Monotony)
2. 수면/회복 기반 조정 (Sleep Score, HRV, Body Battery)
3. 심박 이상 (최대 심박 초과, RHR 급상승, 베타차단제)
4. 부상 관련 (현재 부상, 의료 허가, 연속 통증)
5. 의학적 경계 (진단 금지, 비정상 패턴 시 전문의 안내, SpO2, 약물)
6. 영양 안전 (극단적 칼로리 제한, 알레르기, 보충제, 식이장애 징후)
7. 환경 안전 (기온, 미세먼지)
8. 톤 & 커뮤니케이션 가이드

작성 원칙:
- "~이면 ~하세요" 패턴 (명확한 조건문)
- 모호한 표현 금지 ("적절히" → 구체적 수치)
- LLM 토큰 효율 고려 (2000토큰 이내)

산출물: docs/safety/coaching_guardrails.md
```

**1-4-B: guardrails.py — 하드 레이어**
```
목표: PRD 섹션 8.3 전체 구현. LLM이 뭘 출력하든 위험한 코칭 차단.

핵심:
class CoachingGuardrails:
    def validate(coaching, user, metrics) → GuardrailResult

체크 함수 7개:
_check_overtraining:
  - TSB < -30 + Zone 4+ → OVERRIDE to rest
  - Ramp Rate > 5/주 → MODIFY + warning
  - 주간 볼륨 > 10% 증가 → MODIFY + warning

_check_sleep_recovery:
  - Body Battery < 25 (기상 시) → OVERRIDE to full rest
  - Sleep Score < 50 + hard session → MODIFY to easy
  - HRV 기준선 대비 -15% + hard → MODIFY to easy
  - 연속 3일 Sleep Score < 60 → 누적 수면 부채 경고 추가

_check_heart_rate:
  - 베타차단제 복용자 + HR zone 코칭 → MODIFY to RPE 기반
  - RHR +15bpm above 기준선 → MODIFY + 건강 이상 가능성 알림

_check_injury:
  - current_injuries 부위와 관련된 운동 → OVERRIDE
  - medical_clearance "pending" + 고강도 → OVERRIDE
  - 같은 부위 통증 2회 연속 보고 → 해당 운동 유형 auto-restrict

_check_nutrition_safety:
  - 알레르기 식품 텍스트에서 감지 → MODIFY (제거)
  - BMR 이하 칼로리 권장 → BLOCK

_check_medical_claims:
  - 진단/처방/치료 키워드 regex → MODIFY (제거 + disclaimer)

_check_ramp_rate:
  - 주간 볼륨 관점 별도 체크 (TSS뿐 아니라 km 기준도)

GuardrailAction: PASS | MODIFY | OVERRIDE | BLOCK_AND_ALERT
→ 모든 체크 실행, 가장 엄격한 결과 적용
→ GuardrailResult에 항상 reason 포함 (S2/S3이 사용자에게 표시)

필수 테스트 케이스 (최소 20개):
- TSB -35 + LLM이 인터벌 → OVERRIDE 확인
- Sleep Score 42 + 하드 세션 → easy 다운그레이드
- 알레르기(땅콩) + LLM이 땅콩버터 추천 → 제거
- 베타차단제 + HR Zone 4 → RPE로 전환
- Body Battery 20 → 완전 휴식 강제
- HRV -20% + 템포런 → easy로 다운그레이드
- RHR +18bpm → 건강 이상 경고 추가
- 무릎 부상(pending) + 인터벌 → OVERRIDE
- 같은 부위 통증 3회차 → auto-restrict 확인
- LLM이 "아킬레스건염 진단" 문구 → 제거 + disclaimer
- BMR 이하 칼로리 → BLOCK
- Ramp Rate 6.2 → 경고 추가
- 주간 km 15% 증가 → 경고 추가
- 연속 3일 Sleep < 60 → 수면 부채 경고
- SpO2 < 90% → 의료 상담 경고
- 모든 지표 정상 → PASS 확인
- 복합 조건 (TSB -25 + Sleep 55 + HRV -10%) → 가장 엄격한 것 적용
- rule-based fallback에도 가드레일 적용 확인
- 가드레일 reason 메시지가 한국어로 자연스러운지
- 빈 metrics (워치 미착용) → 가드레일이 crash하지 않고 PASS

산출물: engine/guardrails.py + tests/test_guardrails.py
```

#### Phase 1-5: 코칭 엔진 + 주간 계획 (Week 4-6)

**1-5-A: coaching.py 확장 — Readiness 기반 코칭**
```
목표: Readiness Score에 따른 코칭 강도 자동 조절 + LLM 호출 파이프라인

파이프라인:
1. 사용자 데이터 + Readiness Score 수집
2. Readiness Level에 따른 강도 프리셋 결정
   Green → 계획대로
   Yellow → 강도 20-40% 하향 (인터벌→템포, 템포→이지)
   Red → 이지 or 20분 이하 Zone 1
   Critical → 완전 휴식 + 건강 이상 가능성 알림
3. LLM 호출 (시스템 프롬프트에 guardrails.md + 사용자 컨텍스트)
4. CoachingResponse 파싱
5. guardrails.validate() 통과
6. 반환

LLM 프롬프트 설계:
- 시스템: guardrails.md + 코치 페르소나
- 사용자 컨텍스트: 프로필 요약, 현재 메트릭, 최근 5세션 피드백
- 토큰 효율: 시스템 2000 + 컨텍스트 1500 + 응답 500 = ~4000

산출물: engine/coaching.py 확장
```

**1-5-B: training_plan.py — 주간 계획 생성**
```
목표: 주간 트레이닝 계획 자동 생성

입력:
- UserProfile (목표, 피트니스 레벨)
- 현재 TrainingLoad (CTL, ATL, TSB)
- Readiness 트렌드 (최근 7일)
- 피드백 히스토리 (최근 2주)

출력: WeeklyPlan (7일 DayPlan)

로직:
1. 목표에 맞는 주간 구조 결정
   마라톤: 하드2 / 이지3 / 장거리1 / 휴식1
   일반피트니스: 하드1 / 이지2 / 장거리1 / 크로스1 / 휴식2
2. 현재 CTL 기반 적정 주간 TSS 범위 산출
3. Readiness 트렌드 반영 (하락 추세면 보수적)
4. 최근 피드백 반영 (RPE 높았으면 다음 주 하향)
5. LLM으로 구체적 세션 생성 → 가드레일 통과

산출물: engine/training_plan.py + tests/
```

**1-5-C: rules.py 확장 — Rule-based fallback**
```
목표: LLM 없이도 기본 코칭 동작

LLM 사용 불가 시:
- Readiness Score → 오늘의 세션 타입 결정
- 템플릿 코칭 메시지 생성 (세션 타입별 5-10개 템플릿)
- 가드레일 동일 적용
- "AI 코칭 서비스가 일시적으로 불가합니다" 안내 포함

산출물: engine/rules.py 확장
```

#### Phase 1-6: 데이터 저장 + 자동 싱크 (Week 4-5)

**1-6-A: storage/database.py — SQLite 저장**
```
목표: 수집 데이터의 로컬 저장

SQLite 선택 근거: 주간/월간 리포트에 히스토리 쿼리 필수

테이블:
- daily_health: 날짜별 건강 메트릭 (SleepData, HRV 등 JSON 컬럼)
- activities: 운동 기록 (ActivitySummary)
- training_load: 일별 CTL/ATL/TSB/RampRate
- readiness: 일별 ReadinessScore
- feedback: 세션별 피드백 (S5가 사용)
- nutrition_log: 식단 기록 (S4가 사용)

마이그레이션: 스키마 버전 관리 (향후 컬럼 추가 대비)

산출물: storage/database.py + tests/
```

**1-6-B: sync.py 확장 — 이벤트 발행**
```
목표: 데이터 싱크 + 새 activity 감지 이벤트

동작:
- 15분 간격 폴링 (새 activity 감지)
- 일 1회 전체 건강 데이터 싱크 (수면, HRV 등은 기상 후 확정)
- 새 activity 감지 시 이벤트 발행

이벤트 시스템:
- 간단한 Observer 패턴 또는 asyncio.Event
- on_new_activity(activity: ActivitySummary) → S5가 구독
- on_daily_health_updated(metrics: HealthMetrics) → S2 아침 브리핑이 구독

산출물: integrations/sync.py 확장
```

### 완료 기준

- [ ] models/ 전체 정의 완료, 다른 스트림에서 import 가능 (Week 1)
- [ ] engine/interfaces.py 확정 (Week 1)
- [ ] 모든 P0 건강 데이터 수집 동작 (Week 3)
- [ ] Readiness Score 계산 정확 (14일+ 데이터) (Week 4)
- [ ] 가드레일 20개 테스트 케이스 전체 통과 (Week 5)
- [ ] coaching_guardrails.md 완성 (Week 3)
- [ ] LLM 코칭 + 가드레일 파이프라인 end-to-end (Week 5)
- [ ] 주간 계획 생성 동작 (Week 6)
- [ ] Rule-based fallback 동작 (Week 6)
- [ ] SQLite 저장 + 이벤트 발행 동작 (Week 5)

### ⚠️ 유의사항

1. **Week 1 금요일이 전체 프로젝트의 가장 중요한 데드라인**.
   models/ + interfaces.py가 확정되지 않으면 S3/S4/S5 전부 지연.
2. **가드레일 테스트 > 코칭 로직 테스트**. 안전이 프로덕트 원칙 1번.
3. **Garmin API rate limit 주의**. 테스트는 mock 기반, 실제 API 하루 1-2회.
4. **python-garminconnect 인증 방식 변경 확인 필수** (garth → 모바일 SSO).
5. **Readiness Score 가중치는 초기값 그대로, 튜닝은 Week 8+**.
6. **이벤트 시스템은 단순하게**. Kafka 같은 건 필요 없음. asyncio 수준으로.

---

## Stream 2: Flow Architecture / Telegram

> 채널 추상화(ports.py), 비즈니스 플로우(flows/), Telegram 어댑터를 담당.
> 다른 스트림의 로직을 사용자에게 "전달"하는 레이어.

### 담당 범위

```
garmin_coach/
├── ports.py                  # 🔲 CoachingPort 추상 인터페이스
├── flows/                    # 🔲 비즈니스 플로우 (채널 무관)
│   ├── morning_briefing.py
│   ├── post_workout.py
│   ├── evening_checkin.py
│   ├── nutrition_log.py
│   └── injury_report.py
└── interfaces/telegram/
    ├── adapter.py            # 🔲 TelegramAdapter(CoachingPort)
    ├── keyboards.py          # 🔲 인라인 키보드 헬퍼
    ├── handlers.py           # 🔲 명령어/콜백 핸들러
    ├── renderer.py           # 🔲 메시지 포매팅
    └── scheduler.py          # 🔲 자동 발송 스케줄러
```

> ⚠️ 온보딩/프로필/설정은 S3 담당. 이 스트림은 "인프라 + 일상 플로우"만.

### PRD 참조

- 섹션 9: Telegram Bot UX
- 섹션 10.1: 3-Layer 구조 (인터페이스 분리)

### 상세 작업 항목

#### Phase 2-1: 기반 구조 (Week 1-2) ⚡ 크리티컬 패스

**2-1-A: ports.py — CoachingPort 정의**
```
목표: 모든 채널이 구현할 추상 인터페이스 확정

class CoachingPort(ABC):
    # 메시지 전송
    async def send_message(user_id: str, text: str,
                           buttons: list[Button] | None = None) -> None
    async def send_image(user_id: str, image: bytes,
                         caption: str | None = None) -> None
    async def send_report(user_id: str, report: Report) -> None

    # 입력 수집
    async def request_text(user_id: str, prompt: str) -> str
    async def request_number(user_id: str, prompt: str,
                             min_val: float | None, max_val: float | None) -> float
    async def request_date(user_id: str, prompt: str) -> date
    async def request_select(user_id: str, prompt: str,
                             options: list[Option]) -> str
    async def request_multi_select(user_id: str, prompt: str,
                                   options: list[Option]) -> list[str]
    async def request_photo(user_id: str, prompt: str) -> bytes | None

@dataclass
class Button:
    label: str
    callback_data: str

@dataclass
class Option:
    label: str
    value: str
    emoji: str | None = None

class InputType(Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    PHOTO = "photo"

⚠️ Week 1 끝나기 전에 main에 머지. S3/S4/S5가 이걸 참조.
```

**2-1-B: TelegramAdapter(CoachingPort)**
```
목표: CoachingPort를 python-telegram-bot v20+으로 구현

매핑:
- send_message → bot.send_message(chat_id, text, reply_markup, parse_mode="MarkdownV2")
- send_image → bot.send_photo(chat_id, photo, caption)
- send_report → 텍스트 + 이미지들 순차 전송 (긴 메시지 자동 분할)
- request_text → 텍스트 입력 대기 (ConversationHandler)
- request_number → 텍스트 수신 → float 파싱 → 실패 시 재요청
- request_date → 텍스트 수신 → date 파싱 → 실패 시 재요청
- request_select → InlineKeyboardMarkup + CallbackQuery 대기
- request_multi_select → 토글 키보드 + "완료" 버튼
- request_photo → 사진 수신 대기 (타임아웃 5분)

Telegram 제약 처리:
- 메시지 4096자 제한 → 자동 분할 (문단 단위)
- 콜백 데이터 64바이트 제한 → short ID 매핑
- MarkdownV2 특수문자 이스케이프 유틸

산출물: interfaces/telegram/adapter.py + tests/
```

**2-1-C: flows/ 스켈레톤**
```
목표: 모든 비즈니스 플로우의 구조와 step 정의 (스텁)

각 flow 구조:
class XxxFlow:
    def __init__(self, port: CoachingPort, engine: CoachingEngine, ...):
        self.port = port
        self.engine = engine
    async def execute(self, user_id: str, **kwargs) -> None:
        # step 1: ...
        # step 2: ...
        pass

스텁이지만 각 step을 주석으로 명확히 기술.
S4/S5가 로직 채우고, S2가 통합.

산출물: flows/ 전체 스켈레톤 (5개 파일)
```

#### Phase 2-2: 키보드 + 렌더러 (Week 2-3)

**2-2-A: keyboards.py — 인라인 키보드 헬퍼**
```
목표: 재사용 가능한 Telegram 키보드 컴포넌트 라이브러리

구현:
- single_select(options: list[Option]) → InlineKeyboardMarkup
- multi_select(options: list[Option], selected: set) → InlineKeyboardMarkup
- number_scale(min, max, step) → InlineKeyboardMarkup (예: RPE 1-10)
- emoji_select(options: list[tuple[str, str]]) → InlineKeyboardMarkup
  (예: [("😀", "good"), ("😐", "neutral"), ("😫", "bad"), ("🤕", "pain")])
- confirm_cancel() → InlineKeyboardMarkup
- pagination(items, page, page_size) → InlineKeyboardMarkup

디자인 원칙:
- 한 행에 최대 3개 버튼
- 현재 선택 상태 표시 (✅ 접두사)
- 모든 키보드에 "취소" 옵션

산출물: interfaces/telegram/keyboards.py + tests/
```

**2-2-B: renderer.py — 메시지 포매팅**
```
목표: 데이터를 Telegram 읽기 좋은 형태로 변환

구현:
- render_readiness(score: ReadinessScore) → str
  "🔋 Readiness: 82/100 🟢\n- 수면: 85 ✅\n- HRV: +7.7% ✅ ..."
- render_workout_analysis(analysis: WorkoutAnalysis) → str
- render_nutrition_advice(advice: NutritionAdvice) → str
- render_weekly_report(report: WeeklyReport) → list[str]  # 분할 가능
- render_weekly_plan(plan: WeeklyPlan) → str
- render_guardrail_notice(result: GuardrailResult) → str
  "⚠️ 코치가 오늘의 계획을 조정했습니다:\nTSB가 -32로 회복이 필요합니다..."
- escape_markdown_v2(text: str) → str  # Telegram 특수문자 이스케이프

스타일:
- 이모지 일관성 (🏃운동, 😴수면, 💪피트니스, 🍽️영양, ⚠️경고)
- 숫자는 소수점 1자리
- 긴 메시지는 "더보기" 패턴보다 핵심만 전송

산출물: interfaces/telegram/renderer.py + tests/
```

#### Phase 2-3: 핵심 플로우 구현 (Week 3-6)

**2-3-A: flows/morning_briefing.py**
```
목표: PRD 섹션 9.1 아침 브리핑

트리거: 스케줄러 (사용자 설정 시간, 기본 07:00)

순서:
1. S1 engine에서 ReadinessScore + HealthMetrics 가져오기
2. S1 engine.generate_daily_coaching() 호출
3. S4 NutritionTiming.get_pre_workout_advice() (운동 예정 시)
4. renderer로 포매팅
5. port.send_message() + 버튼 [계획대로] [변경] [내일로]
6. 사용자 응답 처리
   - "변경" → port.request_select(session_types)
   - "내일로" → 오늘 = 휴식, 내일로 이동

의존성: S1 (engine, readiness), S4 (nutrition timing)
```

**2-3-B: flows/post_workout.py**
```
목표: 운동 감지 → 자동 분석 → 피드백 수집

트리거: S1 sync의 on_new_activity 이벤트

순서:
1. S5 auto_analysis.analyze(activity) 호출
2. S4 recovery_fuel.get_advice(activity, user) 호출
3. renderer로 분석 결과 + 영양 권장 포매팅
4. port.send_message()
5. S5 subjective 질문 실행 (RPE, 느낌, 조건부 추가)
6. 응답 수집 → S5 aggregator에 전달

의존성: S1 (sync 이벤트), S4 (recovery fuel), S5 (analysis, feedback)
```

**2-3-C: flows/evening_checkin.py**
```
트리거: 스케줄러 (사용자 설정 시간, 기본 21:00)

순서:
1. 오늘 요약 (운동, 활동 칼로리, 걸음, 스트레스)
2. 식단 기록 프롬프트 → S4 nutrition_log flow로 핸드오프
3. 내일 세션 대비 취침 시간 권고
```

**2-3-D: flows/nutrition_log.py**
```
목표: 식단 기록 플로우

순서:
1. port.request_select(["📝 텍스트 입력", "📸 사진 촬영", "⏭️ 건너뛰기"])
2. 텍스트 → 직접 기록
3. 사진 → S4 photo_analyzer 호출 → 매크로 추정 표시 → 확인/수정
4. 저장 (S1 storage)
```

**2-3-E: flows/injury_report.py**
```
목표: 부상 보고 플로우

순서:
1. port.request_select(부위 목록)
2. port.request_select(통증 정도: 약간/꽤/많이)
3. port.request_text(추가 설명, 선택)
4. 사용자 프로필에 반영 → S1 가드레일 연동
5. "통증이 2일 이상 지속되면 전문의 상담을 권합니다" 안내
```

#### Phase 2-4: 명령어 + 스케줄러 (Week 5-7)

**2-4-A: handlers.py — 명령어 체계**
```
/start    → S3 온보딩 flow 시작
/today    → morning_briefing flow (수동)
/week     → S1 engine.generate_weekly_plan() + renderer
/report   → S5 weekly.generate() + renderer
/feedback → S5 subjective 질문 수동 실행
/nutrition → S4 오늘의 영양 가이드
/settings  → S3 설정 변경 flow
/goals    → S3 목표 확인/수정
/injury   → injury_report flow
/help     → 도움말 메시지

사진 처리:
- 사진 수신 → 자동 타입 감지 시도 (운동 캡쳐 vs 식단)
- 실패 시: [📊 운동 캡쳐] [🍽️ 식단 사진] [📸 기타]
- 운동 캡쳐 → S5 photo_analyzer
- 식단 사진 → S4 photo_analyzer

자유 텍스트 (명령어가 아닌 메시지):
- S1 engine.answer_question() 으로 전달
- "오늘 뭐 먹으면 좋아?", "내 CTL 어때?" 등 자연어 질의

산출물: interfaces/telegram/handlers.py
```

**2-4-B: scheduler.py — 자동 발송**
```
구현: APScheduler 또는 python-telegram-bot JobQueue

스케줄:
- 아침 브리핑: 사용자별 설정 시간 (기본 07:00)
- 저녁 체크인: 사용자별 설정 시간 (기본 21:00)
- 주간 리포트: 매주 일요일 20:00
- 월간 리포트: 매월 1일 09:00
- 운동 후 분석: on_new_activity 이벤트 즉시 (스케줄 아님, 이벤트)

타임존: 사용자 프로필의 timezone (기본 Asia/Seoul)

산출물: interfaces/telegram/scheduler.py
```

#### Phase 2-5: 에러 핸들링 + 마감 (Week 7-10)

```
- Garmin 데이터 없을 때 (워치 미착용) → "오늘 워치 데이터가 없어 제한된 분석입니다"
- LLM 응답 실패 → rule-based fallback 안내
- 온보딩 중간 이탈 후 복귀 → 마지막 단계부터 재개
- 비정상 입력 → 친절한 재요청
- Telegram API 장애 → 재시도 (최대 3회)
- 동시 메시지 수신 → 큐잉으로 순차 처리
```

### 완료 기준

- [ ] ports.py main 머지 (Week 1)
- [ ] TelegramAdapter 전체 메서드 동작 (Week 2)
- [ ] 아침 브리핑 자동 발송 (Week 5)
- [ ] 운동 감지 → 자동 분석 → 피드백 수집 전체 플로우 (Week 6)
- [ ] 10개 명령어 전체 동작 (Week 7)
- [ ] 주간 리포트 자동 발송 (Week 8)
- [ ] flows/ 폴더에 telegram import 0건 (CI 체크)

### ⚠️ 유의사항

1. **ports.py가 전체 프로젝트의 가장 중요한 산출물 중 하나**. Week 1 확정.
2. **flows/와 interfaces/telegram/ 분리 절대 유지**. CI로 강제 체크.
3. **ConversationHandler 상태 관리**: 온보딩 같은 다단계 플로우는 S3이 flow로 작성, S2는 어댑터만.
4. **Telegram 4096자 제한**: 주간 리포트 등 긴 메시지 분할 로직 필요.
5. **콜백 데이터 64바이트 제한**: 콜백에 긴 문자열 불가. UUID→short ID 매핑.
6. **S1의 이벤트 시스템과 S2의 스케줄러 연결이 Week 5 핵심 통합 포인트**.

---

## Stream 3: Onboarding / Profile / Settings

> 사용자 프로필 수집, 3단계 온보딩, 설정 변경을 담당.
> S2의 ports.py를 통해 사용자와 상호작용하되, Telegram을 직접 모름.

### 담당 범위

```
garmin_coach/
├── flows/
│   ├── onboarding.py         # 🔲 3단계 온보딩 플로우
│   └── settings.py           # 🔲 설정 변경 플로우
└── wizard/
    ├── onboarding_logic.py   # 🔲 온보딩 비즈니스 로직
    ├── profile_manager.py    # 🔲 프로필 CRUD
    └── fitness_detector.py   # 🔲 피트니스 레벨 자동 감지
```

### PRD 참조

- 섹션 4: 온보딩 플로우 전체
- 섹션 4.2: Phase 1 (필수)
- 섹션 4.3: Phase 2 (권장)
- 섹션 4.4: Phase 3 (선택)
- 섹션 4.5: 데이터 모델

### 상세 작업 항목

#### Phase 3-1: 온보딩 Phase 1 — 필수 (Week 2-3)

**3-1-A: flows/onboarding.py — 온보딩 플로우 오케스트레이터**
```
목표: 3단계 온보딩의 전체 흐름 관리

class OnboardingFlow:
    def __init__(self, port: CoachingPort, profile_mgr: ProfileManager):
        ...

    async def execute(self, user_id: str) -> UserProfile:
        # Phase 1: 필수
        profile = await self._phase1_essential(user_id)
        await self.port.send_message(user_id,
            "✅ 기본 설정 완료! 이제 트레이닝 코칭을 받을 수 있습니다.")

        # Phase 2 안내
        proceed = await self.port.request_select(user_id,
            "더 정확한 코칭을 위해 건강/영양 정보를 추가할까요?",
            [Option("네, 지금 할게요", "yes"), Option("나중에", "later")])
        if proceed == "yes":
            await self._phase2_recommended(user_id, profile)

        # Phase 3 안내 (Phase 2 완료 후 또는 나중에)
        ...

        return profile

    async def resume(self, user_id: str, last_step: str) -> UserProfile:
        """온보딩 중간 이탈 후 복귀 시 마지막 단계부터 재개"""
        ...
```

**3-1-B: Step 1 — Garmin 연동**
```
순서:
1. port.send_message("Garmin Connect 계정을 연결할게요...")
2. email = await port.request_text("📧 Garmin 이메일:")
3. password = await port.request_text("🔑 비밀번호:")
   (⚠️ Telegram에서는 비밀번호가 채팅에 보임 — 보안 안내 필수:
    "입력 후 메시지를 삭제해주세요. 비밀번호는 로컬에만 저장됩니다.")
4. 인증 시도 → 성공/실패 피드백
5. 실패 시 재시도 (최대 3회) + MFA 안내

산출물: wizard/onboarding_logic.py (garmin_connect)
```

**3-1-C: Step 2 — 기본 프로필**
```
순서:
1. birth_date = await port.request_date("생년월일:")
2. sex = await port.request_select("성별:",
   [("남성", "male"), ("여성", "female"), ("기타", "other"), ("응답 안 함", "undisclosed")])
3. height = await port.request_number("키(cm):", min=100, max=250)
4. weight = await port.request_number("체중(kg):", min=30, max=200)

유효성 검증:
- 범위 밖 → 재요청
- 비상식적 조합 (키 100cm + 체중 200kg) → 확인 질문
```

**3-1-D: Step 3 — 운동 목표**
```
순서:
1. goal_type = await port.request_select("주요 목표:",
   [("🏃 마라톤/하프 기록단축", "marathon"),
    ("🚴 사이클링 향상", "cycling"),
    ("🏊 트라이애슬론", "triathlon"),
    ("💪 일반 피트니스", "fitness"),
    ("⚖️ 체중 관리", "weight"),
    ("🔄 부상 복귀", "rehab")])

2. 목표별 추가 질문:
   marathon:
     - target_event = await port.request_text("목표 대회명 (선택):")
     - target_time = await port.request_text("목표 시간 (예: 3:30:00):")
     - target_date = await port.request_date("대회 날짜:")
     - weekly_km = await port.request_number("현재 주간 러닝 거리(km):")
     - recent_race = await port.request_text("최근 레이스 기록 (선택):")

   rehab:
     - body_part = await port.request_select("부상 부위:", [...])
     - clearance = await port.request_select("의사 허가:",
       [("운동 가능", "full"), ("제한적", "limited"), ("미확인", "pending")])
     - restrictions = await port.request_text("제한 사항:")
     ⚠️ clearance가 "pending"이면 → S1 가드레일에서 고강도 자동 차단
```

**3-1-E: Step 4 — 피트니스 레벨 자동 감지**
```
목표: Garmin 30일 데이터 분석 → 자동 레벨 판정

wizard/fitness_detector.py:
class FitnessDetector:
    async def detect(self, garmin_adapter, days=30) -> FitnessLevel:
        activities = await garmin_adapter.get_activities(last_n_days=days)
        return FitnessLevel(
            weekly_avg_distance_km=...,
            weekly_avg_sessions=...,
            avg_zone_distribution=...,
            estimated_vo2max=...,
            level="intermediate_advanced",  # beginner/intermediate/advanced/elite
        )

사용자에게 결과 표시 + 확인:
"📊 최근 30일 분석: 주 42km, 4.2회, VO2max 52 → 중급-고급
 맞나요? [네] [조정할게요]"

"조정" 선택 시 → 수동 레벨 선택
```

#### Phase 3-2: 온보딩 Phase 2 — 권장 (Week 3-4)

**3-2-A: Step 5 — 의료/건강 이력**
```
순서:
1. cardiac = await port.request_select("심장 질환:", [("없음", "none"), ("있음", "yes")])
   → "있음" → port.request_text("구체적으로:")
2. hypertension = await port.request_select("고혈압:",
   [("없음", "none"), ("약 복용 중", "treated"), ("미치료", "untreated")])
3. diabetes = await port.request_select("당뇨:",
   [("없음", "none"), ("1형", "type1"), ("2형", "type2")])
4. respiratory = await port.request_select("천식/호흡기:",
   [("없음", "none"), ("있음", "yes")])
5. injury_history = await port.request_text("과거 부상 이력 (자유 입력, 없으면 '없음'):")
6. medications = await port.request_text("현재 복용 약물:")
   ⚠️ "베타차단제" 관련 키워드 감지 → beta_blocker = True 자동 설정
      → S1 가드레일에서 HR Zone → RPE 전환

7. port.send_message("⚠️ 이 정보는 안전 가드레일에 반영됩니다. "
                     "의학적 조언을 대체하지 않습니다.")
```

**3-2-B: Step 6 — 영양/식단**
```
순서:
1. restrictions = await port.request_multi_select("식이 제한:",
   [채식, 비건, 글루텐프리, 유당불내증, 할랄, 기타])
   → "기타" → port.request_text()
2. allergies = await port.request_text("음식 알레르기 (없으면 '없음'):")
3. meal_pattern = await port.request_select("식사 패턴:",
   [하루3끼, 간헐적단식16:8, 하루2끼, 불규칙])
4. supplements = await port.request_text("보충제 (없으면 '없음'):")
5. alcohol = await port.request_select("음주:",
   [안마심, 주1-2회, 주3-4회, 거의매일])

→ S4 영양 코칭에서 allergies/restrictions 참조
→ S1 가드레일에서 알레르기 식품 차단
```

**3-2-C: Step 7 — 수면 패턴**
```
순서:
1. bedtime = await port.request_text("평균 취침 시간 (예: 23:00):")
2. wakeup = await port.request_text("평균 기상 시간 (예: 06:30):")
3. sleep_issues = await port.request_multi_select("수면 문제:",
   [없음, 불면증, 수면무호흡, 야간각성, 기타])

→ S1 Readiness Score에서 수면 데이터 교차 분석
→ S2 스케줄러에서 아침 브리핑 시간 자동 설정 (기상 시간 기준)
```

#### Phase 3-3: 온보딩 Phase 3 — 선택 + 설정 (Week 4-5)

**3-3-A: Phase 3 선택 항목**
```
- Strava 연동 (OAuth)
- 선호 운동 시간대 (아침/점심/저녁/상관없음)
- 크로스트레이닝 선호 (수영, 요가, 웨이트 등)
- 코칭 톤 ([격려형] [팩트형] [엄격한 코치형])
- 알림 빈도 ([매번] [하루 1회 요약] [주간만])
- 단위계 (km/mi, kg/lb)
- 타임존
```

**3-3-B: flows/settings.py — 설정 변경 플로우**
```
목표: /settings 명령어로 프로필/설정 언제든 수정 가능

class SettingsFlow:
    async def execute(self, user_id: str):
        category = await self.port.request_select(user_id, "무엇을 변경할까요?",
            [("📋 기본 정보", "profile"),
             ("🎯 목표", "goals"),
             ("🏥 건강 정보", "medical"),
             ("🍎 식단 정보", "nutrition"),
             ("😴 수면 정보", "sleep"),
             ("⚙️ 알림/기타", "preferences")])

        if category == "profile":
            field = await self.port.request_select(...)
            # 해당 필드만 수정
        elif category == "goals":
            # 목표 변경 → 주간 계획 재생성 필요 알림
            ...

⚠️ 목표 변경 시 S1 training_plan 재계산 트리거
⚠️ 의료 정보 변경 시 S1 가드레일 즉시 반영
```

**3-3-C: wizard/profile_manager.py — 프로필 CRUD**
```
목표: UserProfile의 저장/조회/수정/삭제

구현:
- save_profile(user_id, profile) → storage에 저장
- get_profile(user_id) → UserProfile | None
- update_field(user_id, field_path, value) → 단일 필드 업데이트
- is_onboarding_complete(user_id) → bool (Phase 1 완료 여부)
- get_onboarding_progress(user_id) → (current_step, total_steps)

저장: S1의 storage/database.py 활용

산출물: wizard/profile_manager.py + tests/
```

### 완료 기준

- [ ] 온보딩 Phase 1 전체 동작 (Garmin 연동 → 프로필 → 목표 → 레벨 감지)
- [ ] 온보딩 Phase 2 전체 동작 (의료 → 영양 → 수면)
- [ ] Phase 3 선택 항목 동작
- [ ] /settings로 모든 항목 수정 가능
- [ ] 온보딩 중간 이탈 → 복귀 시 마지막 단계에서 재개
- [ ] 베타차단제 감지 → S1 가드레일 연동 확인
- [ ] 알레르기 입력 → S1/S4 연동 확인
- [ ] 피트니스 레벨 자동 감지 동작

### 추가 완료 게이트 (반드시 PASS)

- [ ] timeout / cancel / skip이 정상 비즈니스 값으로 저장되지 않음
- [ ] Garmin 인증 실패 시 Phase 1 완료 처리 금지, 부분 프로필 오염 금지
- [ ] 온보딩 resume가 마지막 단계부터 정확히 재개되고 중복 저장/중복 질문이 없음
- [ ] /settings 변경은 저장 성공 후에만 side effect 이벤트(S1/S4 재계산)가 발행됨
- [ ] 민감 의료/영양 정보가 로그에 남지 않음
- [ ] flows/onboarding.py, flows/settings.py는 Telegram import 0건 유지

### ⚠️ 유의사항

1. **Telegram에서 비밀번호 입력 문제**. 채팅에 비밀번호가 남으므로
   "입력 후 메시지를 삭제해주세요" 안내 필수. 장기적으로 OAuth 전환 검토.
2. **온보딩은 한 번에 다 받지 않음**. Phase 1만 완료해도 코칭 시작 가능.
   Phase 2/3은 "더 정확한 코칭을 위해" 유도.
3. **flows/onboarding.py는 telegram을 import하면 안 됨**.
   ports.py의 CoachingPort만 사용.
4. **의료 정보는 민감**. 로컬 저장만, 로깅에 포함되지 않도록 주의.
5. **목표 변경 시 side effect** 처리: S1 training_plan 재계산,
   S4 영양 가이드 재계산 필요. 이벤트로 전파.
6. **Phase 1 Step 4 (피트니스 감지)는 S1의 Garmin 데이터가 필요**.
   S1에서 adapters/garmin/activity.py가 동작해야 함. Week 2 의존.
7. **timeout/cancel은 명시적 상태로만 처리**. 빈 문자열, 오늘 날짜, 첫 옵션 같은 값으로
   조용히 치환하면 안 됨.
8. **Garmin 비밀번호/토큰은 장기 프로필 필드에 남으면 안 됨**. 인증 과정의 임시값과
   저장된 프로필/설정 상태를 분리.

---

## Stream 4: Nutrition

> 운동-영양 연계 코칭 전담. Periodized Nutrition, 타이밍, 수분, 회복 영양,
> 식단 사진 분석을 담당.

### 담당 범위

```
garmin_coach/
└── nutrition/
    ├── engine.py             # 🔲 영양 코칭 오케스트레이터
    ├── macros.py             # 🔲 Periodized Nutrition (매크로 계산)
    ├── timing.py             # 🔲 운동 전/중/후 타이밍 권장
    ├── hydration.py          # 🔲 수분 섭취 가이드
    ├── recovery_fuel.py      # 🔲 회복 영양 전략
    └── photo_food.py         # 🔲 식단 사진 분석 (Vision LLM)
```

### PRD 참조

- 섹션 5: 운동-영양 연계 코칭 전체
- 섹션 5.2: 영양 코칭 로직
- 섹션 5.3: Telegram 연계 예시
- 섹션 5.4: 수분 섭취 가이드

### 상세 작업 항목

#### Phase 4-1: 매크로 계산 (Week 2-3)

**4-1-A: macros.py — Periodized Nutrition**
```
목표: PRD 섹션 5.2의 PeriodizedNutrition 전체 구현

CARB_PERIODIZATION (세션 타입 → g/kg/day):
  REST_DAY:          3.0 - 5.0
  EASY (Z1-2, <60m): 4.0 - 6.0
  MODERATE (Z2-3, 60-90m): 5.0 - 7.0
  HARD (Z3-4, 인터벌/템포): 6.0 - 8.0
  LONG (>90m):       7.0 - 10.0
  RACE:              8.0 - 12.0

PROTEIN (목표별 g/kg/day):
  endurance: 1.2 - 1.6
  strength:  1.6 - 2.2
  weight_loss: 1.6 - 2.4  (근손실 방지)
  rehab:     1.6 - 2.0

FAT_MINIMUM: 1.0 g/kg/day (호르몬 기능 유지)

calculate_daily_macros(user, today_session, goal) → DailyMacros:
  1. 체중 기반 탄/단/지 범위 계산
  2. TDEE 추정 (Mifflin-St Jeor + 활동계수 + 운동 칼로리)
  3. 체중 관리 목표 시 칼로리 조정 (-300~-500kcal/day, BMR 이하 금지)

@dataclass
class DailyMacros:
    carbs_g: tuple[float, float]     # (min, max)
    protein_g: tuple[float, float]
    fat_g: tuple[float, float]
    total_kcal: tuple[float, float]
    session_type: SessionType
    rationale: str                    # "인터벌 세션이므로 탄수화물 상향"

테스트:
- 70kg 러너 + 인터벌 → 탄수 420-560g 확인
- 체중 감량 목표 → 칼로리 적자 but BMR 이상 확인
- 부상 복귀 → 단백질 상향 확인

산출물: nutrition/macros.py + tests/test_macros.py
```

#### Phase 4-2: 타이밍 + 수분 + 회복 (Week 3-5)

**4-2-A: timing.py — 운동 전/중/후 영양 타이밍**
```
목표: PRD 섹션 5.2의 NutritionTiming 구현

get_pre_workout_advice(hours_until: float, session_type: SessionType, user: UserProfile):
  → PreWorkoutAdvice (description, carbs, examples, restrictions_applied)

  3-4h 전: 정상 식사, 탄수 1-2g/kg
  1-2h 전: 가벼운 간식, 탄수 0.5-1g/kg
    examples: ["바나나 + 꿀", "흰쌀밥 소량", "에너지바", "토스트 + 잼"]
  30min 전: 빠른 에너지만, 탄수 0.3-0.5g/kg
    examples: ["젤 1개", "스포츠 드링크", "바나나 반개"]

  ⚠️ user.nutrition.allergies 체크하여 알레르기 식품 제외
  ⚠️ user.nutrition.dietary_restrictions 반영 (비건이면 꿀 제외 등)

get_during_advice(duration_min: int, session_type: SessionType):
  <60min: 수분만
  60-90min: 30-60g 탄수/시간
  >90min: 60-90g 탄수/시간 (혼합 탄수화물: 포도당+과당)
  >180min: 60-90g/h + 소금 보충 필수

get_post_workout_advice(session_type: SessionType, user: UserProfile):
  → PostWorkoutAdvice (timing, carbs, protein, examples)
  golden window: 운동 후 30분 이내
  carbs: 1.0-1.2g/kg
  protein: 0.3-0.4g/kg (20-40g)
  examples (한국 음식 포함):
    ["초코우유 500ml", "프로틴 쉐이크 + 바나나",
     "밥 + 닭가슴살", "그릭 요거트 + 그래놀라",
     "김밥 + 우유", "떡 + 프로틴 쉐이크"]

산출물: nutrition/timing.py + tests/
```

**4-2-B: hydration.py — 수분 섭취**
```
get_hydration_plan(session_type, duration_min, temp_celsius=None):
  pre: "2-3시간 전 500ml, 직전 200-300ml"
  during: "15-20분마다 150-250ml" (고온 시 상향)
  post: "체중 손실 1kg당 1.5L"
  electrolytes: 60min+ 또는 30°C+ 시 나트륨 보충

calculate_sweat_rate(pre_weight, post_weight, fluid_consumed, duration_h):
  → ml/hour (사용자가 데이터 제공 시)

산출물: nutrition/hydration.py + tests/
```

**4-2-C: recovery_fuel.py — 회복 영양**
```
get_recovery_advice(activity: ActivitySummary, user: UserProfile):
  → RecoveryAdvice (priority, timing, macros, food_examples, hydration)

세션 강도별 회복 우선순위:
  HARD/INTERVAL: 탄수 우선 → 글리코겐 보충
  LONG: 탄수 + 전해질 → 에너지 + 나트륨
  EASY: 단백질 위주 → 근회복
  REST_DAY: 일반 식사

food_examples에 user의 식단 제한/알레르기 반영:
  비건 → 두부, 템페, 식물성 프로틴
  유당불내증 → 우유 제외, 두유/오트밀크 대체

산출물: nutrition/recovery_fuel.py + tests/
```

#### Phase 4-3: 식단 사진 분석 (Week 5-6)

**4-3-A: photo_food.py — 식단 사진 분석**
```
목표: 사진 → 매크로 대략 추정

class FoodPhotoAnalyzer:
    async def analyze(self, photo: bytes, user: UserProfile) -> FoodAnalysis:
        """
        Vision LLM 호출하여 식단 사진 분석.

        프롬프트:
        "이 식단 사진을 분석하세요. JSON으로만 응답:
         {items: [...], estimated_macros: {calories, protein_g, carbs_g, fat_g},
          confidence: low/medium/high}"
        """
        ...

@dataclass
class FoodAnalysis:
    items_detected: list[str]       # ["닭가슴살", "밥", "샐러드"]
    estimated_macros: EstimatedMacros
    confidence: str                 # "low" | "medium" | "high"
    coaching_note: str              # "운동 후 회복식으로 좋은 구성. 단백질 충분."
    allergen_warning: str | None    # user 알레르기와 교차 확인

비용 관리:
- 사진 해상도 제한 (1024px max)
- 하루 분석 횟수 제한 (10회)
- confidence "low"면 "정확하지 않을 수 있습니다" 안내

산출물: nutrition/photo_food.py + tests/
```

#### Phase 4-4: 영양 엔진 통합 (Week 6-7)

**4-4-A: engine.py — 영양 코칭 오케스트레이터**
```
class NutritionEngine:
    """S2 flows에서 호출하는 영양 코칭 진입점."""

    def __init__(self, macros, timing, hydration, recovery, photo_analyzer):
        ...

    async def get_today_guide(self, user, today_session) -> DailyNutritionGuide:
        """오늘의 전체 영양 가이드 (매크로 + 타이밍 + 수분)"""
        ...

    async def get_pre_workout(self, user, session, hours_until) -> PreWorkoutAdvice:
        ...

    async def get_post_workout(self, user, activity) -> RecoveryAdvice:
        ...

    async def analyze_food_photo(self, photo, user) -> FoodAnalysis:
        ...

    async def log_meal(self, user_id, meal_data) -> None:
        """식단 기록 저장 (S1 storage 활용)"""
        ...

산출물: nutrition/engine.py
```

### 완료 기준

- [ ] calculate_daily_macros가 세션 타입별로 정확한 매크로 반환
- [ ] 알레르기/식단 제한이 모든 음식 예시에서 필터링됨
- [ ] 운동 전/중/후 타이밍 가이드 동작
- [ ] 식단 사진 → 매크로 추정 동작
- [ ] 수분 섭취 가이드 동작
- [ ] NutritionEngine 통합 API로 S2에서 호출 가능

### 추가 완료 게이트 (반드시 PASS)

- [ ] timeout / cancel / low-confidence 사진 분석이 실제 식단 로그로 저장되지 않음
- [ ] 어떤 경로에서도 BMR 이하 칼로리 권장이 반환되지 않음 (fallback 포함)
- [ ] 알레르기/식단 제한 필터가 템플릿, 예시 음식, 사진 분석 보정 결과까지 모두 적용됨
- [ ] Vision 분석 confidence가 낮을 때는 추정치임을 명시하고 확정값처럼 저장하지 않음
- [ ] nutrition 모듈 출력은 구조화 데이터만 반환하고 Telegram 포맷 문자열을 만들지 않음
- [ ] 같은 식단 사진/같은 meal_id 재처리 시 중복 로그가 쌓이지 않음

### ⚠️ 유의사항

1. **알레르기 필터링이 절대 규칙**. 추천 음식 목록에 알레르기 식품이
   하나라도 포함되면 안 됨. S1 가드레일과 이중 체크.
2. **칼로리 하한선 = BMR**. 체중 감량 목표여도 BMR 이하 절대 권장 금지.
3. **Vision LLM 비용 관리**. photo_food.py 호출마다 $0.01-0.03.
   하루 10회 제한, 이미지 리사이즈 필수.
4. **음식 예시에 한국 음식 포함 필수** (김밥, 떡, 바나나우유 등).
   user locale 기반으로 향후 확장 가능하게 구조화.
5. **nutrition 모듈은 Telegram을 모름**. 모든 출력은 구조화된 데이터,
   S2 renderer가 Telegram 포맷으로 변환.
6. **사진 분석 실패/저신뢰는 명시적으로 실패 처리**. 가짜 매크로 기본값 저장 금지.
7. **식단 로그 저장은 idempotent해야 함**. 같은 입력이 재전송돼도 중복 기록이 쌓이면 안 됨.

---

## Stream 5: Feedback + Reports

> 운동 후 피드백 수집, 자동 분석, 사진(운동 캡쳐) 분석,
> 피드백 종합→코칭 개선, 주간/월간 리포트를 담당.

### 담당 범위

```
garmin_coach/
├── feedback/
│   ├── collector.py          # 🔲 피드백 수집 오케스트레이터
│   ├── auto_analysis.py      # 🔲 자동 운동 분석
│   ├── subjective.py         # 🔲 주관적 피드백 (RPE, 느낌, 통증)
│   ├── photo_workout.py      # 🔲 운동 캡쳐 분석 (Vision LLM)
│   ├── aggregator.py         # 🔲 피드백 종합 → 코칭 개선
│   └── models.py             # 🔲 피드백 데이터 모델
├── reports/
│   ├── weekly.py             # 🔲 주간 리포트
│   ├── monthly.py            # 🔲 월간 리포트
│   └── charts.py             # 🔲 시각화 (matplotlib)
└── models/
    └── feedback.py           # 🔲 피드백 모델 (S1 models에 추가)
```

### PRD 참조

- 섹션 6: 피드백 루프 시스템 전체
- 섹션 7: 주간/월간 리포트

### 상세 작업 항목

#### Phase 5-1: 피드백 모델 + 자동 분석 (Week 2-3)

**5-1-A: feedback/models.py — 피드백 데이터 모델**
```
@dataclass
class SessionFeedback:
    activity_id: str
    timestamp: datetime
    rpe: int                        # 1-10
    feeling: str                    # "good" | "neutral" | "bad" | "pain"
    completion: str | None          # "full" | "partial" | "abandoned"
    target_pace_met: bool | None    # 인터벌/템포 세션용
    nutrition_ok: bool | None       # 장거리 세션용
    gi_issues: bool | None          # 장거리 세션용
    pain: PainReport | None
    free_text: str | None
    photo_analysis: PhotoAnalysis | None

@dataclass
class PainReport:
    body_part: str
    severity: str                   # "mild" | "moderate" | "severe"
    description: str | None
    consecutive_count: int          # 같은 부위 연속 보고 횟수

@dataclass
class RPEIntensityGap:
    """RPE vs 실제 강도 괴리 분석"""
    rpe: int
    actual_avg_hr_pct: float        # 최대심박 대비 %
    expected_rpe_range: tuple[int, int]
    gap_direction: str              # "under" | "match" | "over"
    significance: str               # "normal" | "notable" | "concerning"

⚠️ 이 모델은 S1의 models/feedback.py로 최종 위치.
   Week 2에 PR로 main 머지.
```

**5-1-B: auto_analysis.py — 자동 운동 분석**
```
class AutoAnalyzer:
    async def analyze(self, activity: ActivitySummary,
                      user: UserProfile, history: list[ActivitySummary]) -> WorkoutAutoAnalysis:
        ...

@dataclass
class WorkoutAutoAnalysis:
    summary: str                    # "인터벌 8x800m 완료"
    zone_distribution: dict         # {Z1: 10%, Z2: 25%, Z3: 30%, Z4: 35%}
    training_effect: dict           # {aerobic: 4.2, anaerobic: 3.1}
    tss_contribution: float
    comparison: SessionComparison | None  # 최근 유사 세션 비교
    pace_drift: PaceDrift | None    # 장거리용 페이스 드리프트
    coaching_notes: list[str]       # ["마지막 2랩 드랍 → 보수적 시작 권장"]

분석 항목:
1. 기본 요약 (거리, 시간, 평균 심박, Zone 분포)
2. Training Effect (유산소/무산소)
3. TSS 기여도
4. 유사 세션 비교 (같은 타입, 최근 30일 내)
   → 페이스 변화, 심박 변화 (같은 페이스에 심박 낮아졌으면 → 피트니스 향상)
5. 인터벌: 랩별 페이스 분석 (드랍 패턴, 일관성)
6. 장거리: 페이스/심박 드리프트 (cardiac drift)
7. coaching_notes: 데이터 기반 구체적 피드백 (LLM 보조 가능)

산출물: feedback/auto_analysis.py + tests/
```

#### Phase 5-2: 주관적 피드백 + 사진 (Week 3-5)

**5-2-A: subjective.py — 주관적 피드백 수집**
```
class SubjectiveFeedback:
    """운동 타입에 맞는 피드백 질문 생성 + 수집"""

    def build_questions(self, activity: ActivitySummary,
                        user: UserProfile) -> list[FeedbackQuestion]:
        questions = [
            RPEQuestion(),          # 항상
            FeelingQuestion(),      # 항상
        ]

        # 인터벌/템포
        if activity.session_type in (INTERVAL, TEMPO):
            questions.append(CompletionQuestion())   # 세트 완료?
            questions.append(TargetPaceQuestion())    # 목표 페이스 달성?

        # 장거리 (>90분)
        if activity.duration_minutes > 90:
            questions.append(NutritionDuringQuestion())  # 보급 잘 했나?
            questions.append(GIQuestion())               # 위장 문제?

        # 부상 복귀 중
        if user.medical and user.medical.current_injuries:
            questions.append(PainQuestion())          # 통증?

        questions.append(FreeTextQuestion())           # 자유 입력 (항상, 선택)

        return questions

@dataclass
class FeedbackQuestion:
    key: str
    prompt: str
    input_type: InputType
    options: list[Option] | None
    required: bool
    condition: str | None           # 이전 답변 조건

구체적 질문:
- RPEQuestion: "체감 강도 (1-10):" + 5개 버튼 [1-2 매우쉬움] [3-4 쉬움] ...
- FeelingQuestion: "느낌:" + [😀] [😐] [😫] [🤕]
- CompletionQuestion: "세트 완수:" + [전부] [일부] [중단]
- TargetPaceQuestion: "목표 페이스:" + [달성] [근접] [미달]
- PainQuestion: → "어디:" + 부위 선택 → "정도:" + [약간] [꽤] [많이]

🤕 선택 시 추가 로직:
  → PainReport 생성
  → consecutive_count 계산 (같은 부위 이전 피드백 조회)
  → 2회 연속 → S1 가드레일 auto-restrict 트리거
  → "통증이 2일 이상 지속되면 전문의 상담을 권합니다" 안내

산출물: feedback/subjective.py + tests/
```

**5-2-B: photo_workout.py — 운동 캡쳐 분석**
```
class WorkoutPhotoAnalyzer:
    """가민/스트라바 앱 캡쳐 → 세션 데이터 추출 + 분석 보충"""

    async def analyze(self, photo: bytes, existing_activity: ActivitySummary | None) -> WorkoutPhotoAnalysis:
        """
        Vision LLM에 캡쳐 전달.

        프롬프트:
        "이 운동 앱 캡쳐를 분석하세요. JSON 응답:
         {app: garmin/strava/nike, workout_type: ...,
          metrics: {distance, time, pace, hr_avg, ...},
          laps: [...] (인터벌이면)}"
        """

    async def compare_with_garmin(self, photo_data: dict,
                                   garmin_data: ActivitySummary) -> str:
        """캡쳐 데이터와 Garmin 자동 수집 데이터 비교 → 보충 분석"""
        ...

@dataclass
class WorkoutPhotoAnalysis:
    app_detected: str               # "garmin" | "strava" | "nike" | "unknown"
    metrics_extracted: dict
    laps_extracted: list[dict] | None
    comparison_notes: str | None    # Garmin 데이터와 비교 결과
    additional_insights: str        # 캡쳐에만 있는 추가 정보

비용 관리: S4 photo_food.py와 동일 (해상도 제한, 일일 횟수 제한)

산출물: feedback/photo_workout.py + tests/
```

#### Phase 5-3: 피드백 종합 (Week 5-6)

**5-3-A: collector.py — 피드백 수집 오케스트레이터**
```
class FeedbackCollector:
    """새 activity 감지 → 자동 분석 + 피드백 수집 → 저장"""

    def __init__(self, port: CoachingPort, auto_analyzer, subjective, aggregator):
        ...

    async def on_activity_detected(self, user_id: str, activity: ActivitySummary):
        # 1. 자동 분석
        analysis = await self.auto_analyzer.analyze(activity, ...)

        # 2. S2 post_workout flow가 이걸 사용자에게 보여줌
        # (collector는 직접 port를 호출하지 않음 — flow가 오케스트레이션)

        return analysis

    async def collect_subjective(self, user_id: str, activity: ActivitySummary) -> SessionFeedback:
        """S2 post_workout flow에서 호출. 질문 생성 + 응답 수집"""
        questions = self.subjective.build_questions(activity, user)
        # ... port를 통해 질문하고 응답 수집 ...
        feedback = SessionFeedback(...)
        await self.aggregator.process(feedback)
        return feedback
```

**5-3-B: aggregator.py — 피드백 → 코칭 개선**
```
class FeedbackAggregator:
    """피드백을 분석하여 코칭 모델에 반영"""

    async def process(self, feedback: SessionFeedback):
        # 1. RPE vs Intensity 괴리 분석
        gap = self._analyze_rpe_gap(feedback)
        if gap.significance == "concerning":
            # RPE 높은데 Zone 낮다 → 컨디션 저하 or 오버트레이닝 신호
            await self._flag_potential_overtraining(feedback.user_id)

        # 2. 통증 피드백 → 가드레일 업데이트
        if feedback.pain and feedback.pain.consecutive_count >= 2:
            await self._auto_restrict_exercise(
                feedback.user_id, feedback.pain.body_part)

        # 3. 목표 페이스 달성률 트래킹
        if feedback.target_pace_met is not None:
            rate = await self._get_pace_achievement_rate(feedback.user_id, last_n=5)
            if rate >= 0.8:  # 5회 중 4회 이상 달성
                await self._suggest_pace_upgrade(feedback.user_id)

        # 4. 영양 피드백 → S4 조정
        if feedback.gi_issues:
            await self._flag_gi_pattern(feedback.user_id)
            # GI 문제 2회 이상 → S4 운동 전 식사 가이드 보수적으로

        # 5. 저장
        await self.storage.save_feedback(feedback)

    def get_feedback_summary(self, user_id, days=14) -> FeedbackSummary:
        """최근 N일 피드백 요약 — S1 training_plan에서 활용"""
        return FeedbackSummary(
            avg_rpe=...,
            pain_reports=...,
            pace_achievement_rate=...,
            rpe_intensity_gaps=...,
        )

산출물: feedback/aggregator.py + tests/
```

#### Phase 5-4: 리포트 (Week 6-9)

**5-4-A: weekly.py — 주간 리포트**
```
class WeeklyReportGenerator:
    async def generate(self, user_id: str, week_start: date) -> WeeklyReport:
        ...

@dataclass
class WeeklyReport:
    period: tuple[date, date]

    # 운동 요약
    total_sessions: int
    total_distance_km: float
    total_duration_min: float
    goal_sessions: int              # 목표 대비
    distance_change_pct: float      # 전주 대비

    # 트레이닝 로드
    ctl_start: float
    ctl_end: float
    ctl_change: float
    atl_start: float
    atl_end: float
    tsb_current: float
    ramp_rate: float

    # 수면 & 회복
    avg_sleep_duration: timedelta
    avg_sleep_score: float
    hrv_trend: str                  # "stable" | "improving" | "declining"
    avg_body_battery_morning: float

    # 영양
    meals_logged: int
    meals_expected: int             # 기대 기록 수 (하루 3끼 × 7일 = 21)
    avg_protein_g_per_kg: float | None

    # 피드백
    avg_rpe: float
    pain_reports: list[PainReport]
    pace_achievement_rate: float | None

    # 다음 주 계획
    next_week_plan: WeeklyPlan

    # 코치 코멘트 (LLM 생성)
    coach_comment: str

    # 차트 이미지들
    charts: list[ChartImage]

생성 로직:
1. S1 storage에서 주간 데이터 쿼리
2. 메트릭 계산 (전주 대비 변화 등)
3. S1 engine.generate_weekly_plan() 호출 (다음 주 계획)
4. S1 engine으로 코치 코멘트 생성 (LLM)
5. charts.py로 차트 이미지 생성
6. WeeklyReport 조립

스케줄: 매주 일요일 (S2 scheduler가 트리거)

산출물: reports/weekly.py + tests/
```

**5-4-B: monthly.py — 월간 리포트**
```
class MonthlyReportGenerator:
    async def generate(self, user_id: str, month: date) -> MonthlyReport:
        ...

@dataclass
class MonthlyReport:
    period: tuple[date, date]

    # 월간 합산
    total_sessions: int
    total_distance_km: float
    total_duration_min: float
    prev_month_comparison: dict     # 전월 대비 변화 %

    # CTL/피트니스 트렌드
    ctl_trend: list[float]          # 일별 CTL (30개)
    fitness_change: float           # 월초 → 월말

    # 수면/HRV 월간 트렌드
    sleep_score_trend: list[float]
    hrv_trend: list[float]

    # 목표 진척도
    goal_progress: GoalProgress     # 예: "D-45, CTL 54→65 필요, 현재 62%"

    # 부상/통증 히스토리
    pain_history: list[PainReport]
    injury_changes: list[str]

    # 식단 기록률
    nutrition_logging_rate: float

    # 다음 달 메조사이클 미리보기
    next_month_preview: str

    # 차트
    charts: list[ChartImage]

산출물: reports/monthly.py + tests/
```

**5-4-C: charts.py — 시각화**
```
라이브러리: matplotlib

차트 목록:
1. ctl_atl_tsb_chart(data, period) → bytes (PNG)
   - CTL/ATL 선 그래프 + TSB 영역 (양수=녹색, 음수=빨강)
   - 800x400px

2. zone_distribution_chart(zones: dict) → bytes
   - 심박 Zone 누적 막대 (Z1-Z5, 색상 구분)

3. weekly_volume_chart(distances: list, durations: list) → bytes
   - 주간 거리/시간 막대 그래프

4. hrv_trend_chart(hrv_values: list, baseline: float) → bytes
   - HRV 선 그래프 + 기준선 점선

5. readiness_trend_chart(scores: list) → bytes
   - Readiness Score 영역 차트 (Green/Yellow/Red 색상)

6. pace_trend_chart(sessions: list) → bytes
   - 인터벌/템포 세션 페이스 추이

스타일:
- 다크 배경 (#1a1a2e) + 밝은 글씨 (#eaeaea)
  (Telegram 다크모드 친화)
- 800x400px (Telegram 가로 표시 최적)
- 한글 폰트 (Noto Sans KR 또는 시스템 기본)
- 범례 최소화, 직접 라벨링 선호

산출물: reports/charts.py + tests/
```

### 완료 기준

- [ ] 운동 후 자동 분석이 유사 세션 대비 비교를 포함
- [ ] RPE + 느낌 + 조건부 질문 전체 동작
- [ ] 통증 2회 연속 → auto-restrict 동작
- [ ] RPE vs Intensity 괴리 감지 동작
- [ ] 피드백 → 다음 코칭 반영 확인 (S1 training_plan 연동)
- [ ] 주간 리포트 생성 (텍스트 + 차트 6종) 동작
- [ ] 월간 리포트 생성 동작
- [ ] 운동 캡쳐 사진 분석 동작

### 추가 완료 게이트 (반드시 PASS)

- [ ] 동일 activity/event가 재처리되어도 feedback, pain count, auto-restrict가 중복 반영되지 않음
- [ ] subjective timeout / cancel / skip이 정상 피드백 값(RPE 0, empty string 등)으로 저장되지 않음
- [ ] auto-restrict는 실제 연속 통증 기준으로만 발동하고 단일 이벤트 중복/재전송으로 발동하지 않음
- [ ] 리포트 수치(CTL/ATL/TSB, 수면, HRV, 거리, 로그율)는 코드 계산값만 사용하고 추정/환각 숫자를 만들지 않음
- [ ] 데이터 일부가 비어 있어도 리포트 생성이 crash하지 않고, 누락 사실을 명시한 축약 버전으로 내려감
- [ ] S1 training_plan에 전달하는 feedback summary가 typed contract로 고정됨

### ⚠️ 유의사항

1. **피드백 루프가 이 프로덕트의 핵심 가치**. collector → analysis →
   subjective → aggregator 파이프라인에 가장 많은 시간 투자.
2. **aggregator의 auto-restrict는 S1 가드레일과 연동**.
   pain.consecutive_count ≥ 2 → S1 UserProfile.current_injuries에 추가
   → 가드레일이 이후 세션에서 자동 적용.
3. **주간 리포트의 "코치 코멘트"만 LLM**. 나머지 데이터는 전부 코드 계산.
4. **차트 다크모드 스타일 통일**. 사용자가 Telegram 라이트/다크 상관없이
   읽기 좋도록 다크 배경 + 밝은 색상.
5. **photo_workout.py vs S4의 photo_food.py**: 사진 타입에 따라
   다른 분석기로 라우팅. S2 handlers.py가 타입 감지 후 분기.
6. **월간 리포트의 goal_progress는 목표 유형에 따라 다름**:
   마라톤 → D-day + 필요 CTL vs 현재 CTL
   체중 → 시작 체중 → 현재 → 목표 까지 남은 kg
7. **collector/aggregator는 idempotent해야 함**. 동일 activity_id 중복 처리 시 통계/제한이 두 번 반영되면 안 됨.
8. **리포트는 숫자를 꾸며내면 안 됨**. 계산 불가한 값은 None 또는 '데이터 부족'으로 표시.

---

## 통합 마일스톤

| 주차 | 마일스톤 | 스트림 | 검증 |
|------|---------|--------|------|
| **W1 금** | models/ + ports.py main 머지 | S1, S2 | 다른 스트림에서 import 성공 |
| **W2** | engine/interfaces.py 머지 | S1 | S4/S5에서 참조 가능 |
| **W2** | TelegramAdapter 기본 동작 | S2 | send_message + request_select 동작 |
| **W3** | 건강 데이터 수집 e2e | S1 | 수면+HRV+BB 실제 데이터 확인 |
| **W3** | 온보딩 Phase 1 동작 | S3 | Garmin 연동 → 프로필 → 목표 |
| **W3** | macros.py 동작 | S4 | 세션별 매크로 계산 정확 |
| **W4** | Readiness Score 동작 | S1 | 14일 데이터 기반 스코어 |
| **W4** | 온보딩 Phase 2 동작 | S3 | 의료+영양+수면 수집 |
| **W5** | 가드레일 20개 테스트 통과 | S1 | 위험 시나리오 전체 차단 |
| **W5** | 아침 브리핑 자동 발송 | S2+S1+S4 | 실제 Telegram 수신 |
| **W5** | 피드백 수집 파이프라인 | S5+S2 | 운동 후 RPE+느낌 수집 |
| **W6** | 운동 감지→분석→영양→피드백 e2e | S1+S2+S4+S5 | 전체 post-workout 플로우 |
| **W7** | 식단 사진 분석 | S4 | 사진→매크로 추정 |
| **W7** | 피드백→코칭 개선 루프 | S5+S1 | auto-restrict, 페이스 상향 |
| **W8** | 주간 리포트 자동 발송 | S5+S2 | 일요일 리포트 수신 |
| **W9** | 월간 리포트 | S5 | 월간 트렌드 + 목표 진척도 |
| **W10** | 전체 e2e 1주일 실사용 | ALL | 실제 운동+코칭 사이클 |

---

## 스트림 간 커뮤니케이션 규칙

### 매일 (비동기)
- 작업 시작/종료 시 상태 공유 (Slack 또는 GitHub Issues)
- 블로커 즉시 공유

### 주 1회 (동기)
- 5개 스트림 합동 싱크 (30분)
- 통합 마일스톤 확인
- 인터페이스 변경 리뷰
- 다음 주 통합 작업 합의

### 인터페이스 변경 시 (즉시)
- models/, ports.py, engine/interfaces.py 변경 → PR + 전체 스트림 알림
- 변경 사유 + 영향 범위 + 마이그레이션 가이드 명시
- 24시간 내 리뷰 + 머지
