# Garmin Personal Coach — 병렬 작업지시서

## 왜 4개인가

```
Track A: 데이터 파이프라인 + 모델     ← 모든 트랙의 기반
Track B: 코칭 엔진 + 가드레일         ← A의 모델을 소비
Track C: 영양 + 피드백 + 리포트       ← A의 모델과 B의 엔진을 소비
Track D: Telegram UX + 온보딩         ← 모든 트랙의 결과물을 사용자에게 전달
```

### 의존성 그래프

```
Week 1-2     Week 2-3     Week 3-5      Week 5-7      Week 7-10
┌─────┐
│  A  │─────────────────────────────────────────────────────►
└──┬──┘
   │ models/ 확정 (Week 2)
   │
┌──▼──┐
│  B  │──────────────────────────────────────────────►
└──┬──┘
   │ engine API 확정 (Week 3)
   │
┌──▼──┐
│  C  │────────────────────────────────────────►
└─────┘
┌─────┐
│  D  │─────────────────────────────────────────────────────►
└─────┘  (Week 1부터 독립 시작, Week 3부터 B/C와 통합)
```

### 병렬 가능한 이유

- **A와 D는 Week 1부터 동시 시작 가능**: D는 ports.py + flows/ 스켈레톤 + Telegram 키보드를 먼저 만들고, 실제 데이터 연결은 나중에
- **B는 Week 2부터**: A가 models/를 확정하면 바로 시작. 가드레일은 모델 의존이지 데이터 의존이 아님
- **C는 Week 3부터**: A의 데이터 + B의 엔진 API 시그니처만 있으면 시작 가능

---

## 작업 전 공통 규칙 (모든 트랙 필독)

### 1. 인터페이스 계약 (Contract-First)

**각 트랙은 구현 전에 인터페이스부터 합의한다.**

```python
# 이 파일들이 모든 트랙의 "계약서" 역할
garmin_coach/
├── ports.py                 # Track D가 정의, 모두가 참조
├── models/
│   ├── user_profile.py      # Track A가 정의, 모두가 참조
│   ├── health_metrics.py    # Track A가 정의, B/C가 참조
│   ├── feedback.py          # Track C가 정의, B/D가 참조
│   └── coaching.py          # Track B가 정의, C/D가 참조
└── engine/
    └── interfaces.py        # Track B가 정의, C/D가 참조
```

**규칙**: 계약 파일을 수정하면 반드시 다른 트랙에 알린다. PR 리뷰 필수.

### 2. 브랜치 전략

```
main
├── track-a/data-pipeline
├── track-b/coaching-engine
├── track-c/nutrition-feedback-reports
└── track-d/telegram-ux
```

- 각 트랙은 자기 브랜치에서 작업
- `models/`와 `ports.py` 수정 시 main에 먼저 머지 후 다른 트랙이 rebase
- 주 1회 이상 main에 머지 (충돌 최소화)

### 3. 테스트 원칙

- 각 트랙은 자기 영역의 유닛 테스트를 반드시 작성
- 외부 의존성(Garmin API, Telegram API)은 mock 처리
- 통합 테스트는 Week 5부터 별도 진행

### 4. 코드 스타일

- Python 3.11+, type hints 필수
- dataclass 또는 Pydantic v2 사용 (모델)
- async/await 기본 (Telegram 호환)
- ruff 포맷터 + mypy strict

---

## Track A: 데이터 파이프라인 + 모델

### 담당 범위

```
garmin_coach/
├── adapters/garmin/          # Garmin Connect 데이터 수집
│   ├── activity.py           # ✅ 기존 확장
│   ├── health.py             # 🔲 신규 (수면/HRV/BB/Stress/RHR/SpO2)
│   └── auth.py               # ✅ 기존 확인/업데이트
├── adapters/strava/          # ✅ 기존 확인
├── integrations/
│   ├── training_load.py      # ✅ 기존 확장 (Ramp Rate, Monotony, Strain)
│   └── sync.py               # ✅ 기존 확장
├── engine/
│   └── readiness.py          # 🔲 Readiness Score 계산
└── models/                   # 🔲 전체 데이터 모델 정의
    ├── user_profile.py
    ├── health_metrics.py
    └── coaching.py           # 코칭 응답 모델 (Track B와 협의)
```

### PRD 참조 섹션

- 섹션 3: 데이터 아키텍처 전체
- 섹션 3.1: Garmin 데이터 수집 매트릭스
- 섹션 3.2: Readiness Score

### 상세 작업 항목

#### Phase A-1: 인증 + 모델 정의 (Week 1)

**A-1-1: 인증 레이어 확인/업데이트**
```
목표: Garmin Connect 인증이 최신 방식으로 작동하는지 확인

확인사항:
- python-garminconnect 최신 버전인지 (garth 기반 → 모바일 SSO 전환됨)
- 토큰 자동 갱신(auto-refresh) 동작 확인
- MFA 대응 여부
- 토큰 저장 경로 및 보안 (chmod 700)

산출물:
- adapters/garmin/auth.py 업데이트 (필요 시)
- 인증 테스트 코드
- 토큰 만료/갱신 시나리오별 테스트
```

**A-1-2: 데이터 모델 전체 정의**
```
목표: 모든 트랙이 참조할 데이터 모델 확정

산출물:
- models/user_profile.py
  → UserProfile, MedicalProfile, InjuryRecord, NutritionProfile,
    TrainingGoal, CoachingPreferences (PRD 섹션 4.5 참조)

- models/health_metrics.py
  → HealthMetrics (daily snapshot)
  → SleepData, HRVData, BodyBatteryData, StressData, RHRData, SpO2Data
  → ReadinessScore (PRD 섹션 3.2 참조)
  → TrainingLoad (CTL, ATL, TSB, RampRate, Monotony, Strain)

- models/coaching.py
  → CoachingResponse (text, intensity, max_zone, uses_hr_zones 등)
  → SessionType enum (rest_day, light, moderate, hard, long, race)
  → FeedbackRequest, SessionFeedback (Track C와 협의)

⚠️ 중요: 이 파일들은 Week 1 끝나기 전에 PR로 main에 머지.
         다른 트랙은 이 모델을 기반으로 작업 시작.
```

#### Phase A-2: 건강 데이터 수집 (Week 2-3)

**A-2-1: health.py — 건강/회복 데이터 수집기**
```
목표: Garmin Connect에서 수면, HRV, Body Battery, Stress, RHR, SpO2 수집

구현할 메서드:
- get_sleep_data(date) → SleepData
- get_hrv_data(date) → HRVData
- get_body_battery(start, end) → list[BodyBatteryData]
- get_stress_data(date) → StressData
- get_rhr_day(date) → RHRData
- get_spo2_data(date) → SpO2Data
- get_body_composition(date) → BodyCompositionData
- get_training_readiness(date) → TrainingReadinessData

API 매핑 (python-garminconnect 메서드명 참조):
- 수면: api.get_sleep_data(date_str)
- HRV: api.get_hrv_data(date_str)
- Body Battery: api.get_body_battery(start_str, end_str)
- Stress: api.get_stress_data(date_str)
- RHR: api.get_resting_heart_rate(date_str)
- SpO2: api.get_spo2_data(date_str)
- 체성분: api.get_body_composition(date_str)
- Training Readiness: api.get_training_readiness(date_str)

에러 처리:
- API rate limit → 지수 백오프 재시도 (최대 3회)
- 데이터 없음 (워치 미착용 등) → None 반환, 로깅
- 인증 만료 → 자동 토큰 갱신 후 재시도

테스트:
- 각 메서드별 mock 응답 기반 유닛 테스트
- 실제 API 호출 통합 테스트 (CI에서는 skip, 로컬에서만)

산출물: adapters/garmin/health.py + tests/test_garmin_health.py
```

**A-2-2: activity.py 확장**
```
목표: 기존 운동 데이터에 Training Effect, Running Dynamics 추가

추가 수집:
- Training Effect (유산소/무산소)
- Running Dynamics (케이던스, GCT, 보폭) — 지원 기기에서만
- 랩 데이터 (인터벌 세션 분석용)

산출물: adapters/garmin/activity.py 확장 + 테스트
```

#### Phase A-3: Training Load + Readiness Score (Week 3-4)

**A-3-1: training_load.py 확장**
```
목표: 기존 CTL/ATL/TSB에 Ramp Rate, Monotony, Strain 추가

추가 메트릭:
- Ramp Rate: CTL 주간 변화율 (포인트/주)
  → ramp_rate = (CTL_today - CTL_7days_ago)
  → 경고 임계값: > 5.0/주

- Monotony: 주간 일일 부하의 단조로움
  → monotony = weekly_load_avg / weekly_load_stddev
  → 경고 임계값: > 2.0

- Strain: 과훈련 위험 지표
  → strain = weekly_load_sum × monotony
  → 경고 임계값: strain > CTL × 2

산출물: integrations/training_load.py 확장 + 테스트
```

**A-3-2: readiness.py — Readiness Score**
```
목표: PRD 섹션 3.2의 Readiness Score 구현

입력: HealthMetrics (당일 수면, HRV, BB, RHR, TSB, Stress)
출력: ReadinessScore (0-100, green/yellow/red/critical)

가중치:
- HRV Status: 30% (7일 기준선 대비 변화)
- Sleep Score: 25%
- Body Battery: 15% (기상 시)
- RHR Deviation: 15% (7일 평균 대비)
- TSB: 10%
- Stress Avg: 5%

임계값:
- Green: 75+ | Yellow: 50-74 | Red: 30-49 | Critical: <30

캘리브레이션:
- 최소 14일 데이터 필요 (기준선 산출)
- 데이터 부족 시 가용 데이터로만 계산 + 신뢰도 표시

산출물: engine/readiness.py + tests/test_readiness.py
```

#### Phase A-4: 데이터 저장 + 싱크 (Week 4-5)

**A-4-1: 데이터 저장 전략**
```
목표: 수집 데이터의 로컬 저장 구현

선택지 (하나 결정):
- Option 1: SQLite (GarminDB 패턴) — 쿼리 유연, 히스토리 분석 강점
- Option 2: JSON 파일 + 메모리 캐시 — 단순, 디버깅 쉬움
→ 권장: SQLite. 주간/월간 리포트에 히스토리 쿼리 필수.

스키마: GarminDB 참조하되 우리 모델에 맞게 단순화
- daily_health: 날짜별 건강 메트릭 스냅샷
- activities: 운동 기록
- training_load: 일별 CTL/ATL/TSB
- readiness: 일별 Readiness Score

산출물: storage/ 모듈 + 마이그레이션 스크립트
```

**A-4-2: 자동 싱크 스케줄러**
```
목표: 주기적으로 Garmin 데이터를 가져와 로컬 DB 업데이트

동작:
- 15분 간격 폴링 (새 activity 감지)
- 일 1회 전체 건강 데이터 싱크 (수면, HRV 등은 기상 후 확정)
- 새 activity 감지 시 이벤트 발행 → Track C의 피드백 수집기가 수신

산출물: integrations/sync.py 확장 + 이벤트 시스템
```

### 완료 기준

- [ ] 모든 P0 건강 데이터 수집 동작 확인
- [ ] Readiness Score가 14일 이상 데이터로 정확히 계산됨
- [ ] Training Load 메트릭 (Ramp Rate, Monotony, Strain) 동작
- [ ] models/ 전체 정의 완료, 다른 트랙에서 import 가능
- [ ] 유닛 테스트 커버리지 > 80%

### ⚠️ 유의사항

1. **models/ 변경은 반드시 다른 트랙에 공유**. 이 파일들은 공유 계약서.
2. **Garmin API rate limit 주의**. 개발 중 과도한 호출 시 IP 차단 가능.
   테스트는 mock 기반, 실제 API는 하루 1-2회만.
3. **python-garminconnect 인증 방식 변경 확인 필수**.
   garth 직접 사용 vs python-garminconnect 경유 결정 먼저.
4. **Readiness Score 가중치는 나중에 튜닝**. 초기값은 PRD 그대로,
   실제 데이터로 캘리브레이션은 Phase 5에서.

---

## Track B: 코칭 엔진 + 가드레일

### 담당 범위

```
garmin_coach/
├── engine/
│   ├── coaching.py           # AI 코칭 코어 (LLM 호출 + 응답 생성)
│   ├── guardrails.py         # 🔲 안전 가드레일 (하드 레이어)
│   ├── training_plan.py      # 🔲 주간 계획 생성
│   ├── rules.py              # ✅ Rule-based fallback 확장
│   └── interfaces.py         # 🔲 엔진 인터페이스 정의
├── handler/                  # 자연어 코칭 코어 (기존)
└── docs/safety/
    └── coaching_guardrails.md  # 🔲 안전 규칙 파일
```

### PRD 참조 섹션

- 섹션 8: 안전 가드레일 전체
- 섹션 3.2: Readiness Score → 코칭 연계
- 섹션 1: 프로덕트 원칙 (Safety First)

### 상세 작업 항목

#### Phase B-1: 엔진 인터페이스 + 규칙 파일 (Week 2)

**B-1-1: 엔진 인터페이스 정의**
```
목표: 다른 트랙(C, D)이 코칭 엔진을 호출하는 인터페이스 확정

산출물: engine/interfaces.py

class CoachingEngine(ABC):
    async def generate_daily_coaching(
        user: UserProfile,
        metrics: HealthMetrics,
        readiness: ReadinessScore,
    ) -> CoachingResponse

    async def generate_workout_analysis(
        user: UserProfile,
        activity: Activity,
    ) -> WorkoutAnalysis

    async def generate_weekly_plan(
        user: UserProfile,
        current_load: TrainingLoad,
        readiness_trend: list[ReadinessScore],
    ) -> WeeklyPlan

    async def answer_question(
        user: UserProfile,
        question: str,
        context: CoachingContext,
    ) -> CoachingResponse

⚠️ Week 2 끝나기 전에 이 인터페이스를 main에 머지.
   Track C, D는 이 인터페이스를 기반으로 작업.
```

**B-1-2: coaching_guardrails.md 작성**
```
목표: PRD 섹션 8.2의 규칙 파일 작성

산출물: docs/safety/coaching_guardrails.md

내용 (PRD 섹션 8.2 그대로):
- 절대 규칙 7개 카테고리
  1. 과훈련 방지
  2. 수면/회복 기반 조정
  3. 심박 이상
  4. 부상 관련
  5. 의학적 경계
  6. 영양 안전
  7. 환경 안전
- 톤 & 커뮤니케이션 가이드

이 파일은 LLM 시스템 프롬프트에 포함되므로:
- 명확하고 구체적인 조건문 형태로 작성
- "~하면 ~하세요" 패턴 유지
- 모호한 표현 금지 (예: "적절히" → 구체적 수치)
```

#### Phase B-2: 가드레일 코드 구현 (Week 3-4)

**B-2-1: guardrails.py — 하드 레이어**
```
목표: PRD 섹션 8.3의 CoachingGuardrails 전체 구현

핵심 클래스: CoachingGuardrails

메서드:
- validate(coaching, user, metrics) → GuardrailResult
- _check_overtraining(coaching, metrics)
  → TSB < -30 + Zone 4+ = OVERRIDE to rest
  → Ramp Rate > 5 = MODIFY with warning
  → 주간 볼륨 > 10% 증가 = MODIFY with warning

- _check_sleep_recovery(coaching, metrics)
  → Body Battery < 25 = OVERRIDE to full rest
  → Sleep Score < 50 + hard session = MODIFY to easy
  → HRV -15% below baseline + hard = MODIFY to easy

- _check_heart_rate(coaching, user, metrics)
  → 베타차단제 복용 = MODIFY HR zones → RPE
  → RHR +15bpm above baseline = MODIFY + alert

- _check_injury(coaching, user)
  → current_injuries + related exercise = OVERRIDE
  → pending clearance + high intensity = OVERRIDE
  → 연속 통증 2회 = auto-restrict

- _check_nutrition_safety(coaching, user)
  → allergen detected in text = MODIFY (remove)
  → BMR 이하 칼로리 = BLOCK

- _check_medical_claims(coaching)
  → 진단/처방 키워드 regex 매칭 = MODIFY (remove + disclaimer)

- _check_ramp_rate(coaching, metrics)
  → 이미 _check_overtraining에 포함되지만, 주간 볼륨 관점 별도 체크

GuardrailAction enum: PASS, MODIFY, OVERRIDE, BLOCK_AND_ALERT
→ 가장 엄격한 결과가 최종 적용

테스트 케이스 (필수):
- TSB -35인 상태에서 LLM이 인터벌 세션 추천 → OVERRIDE 확인
- 알레르기(땅콩) 등록 + LLM이 땅콩 추천 → MODIFY 확인
- 베타차단제 복용자 + HR Zone 코칭 → RPE 전환 확인
- Sleep Score 45 + LLM이 하드 세션 → easy로 다운그레이드 확인
- 의학적 진단 문구 포함 → 제거 + disclaimer 확인

산출물: engine/guardrails.py + tests/test_guardrails.py (최소 15개 케이스)
```

#### Phase B-3: 코칭 엔진 확장 (Week 4-6)

**B-3-1: coaching.py 확장 — Readiness 기반 코칭**
```
목표: Readiness Score에 따른 코칭 강도 자동 조절

로직:
1. Readiness Score 확인
2. Green → 계획대로
3. Yellow → 강도 20-40% 하향 (인터벌 → 템포, 템포 → 이지)
4. Red → 이지 세션 또는 20분 이하 Zone 1만
5. Critical → 완전 휴식 + 건강 이상 가능성 알림

LLM 호출 시:
- 시스템 프롬프트에 coaching_guardrails.md 포함
- 사용자 컨텍스트 (프로필, 현재 메트릭, 최근 피드백) 주입
- 응답을 CoachingResponse로 파싱
- guardrails.validate() 통과 후 반환

산출물: engine/coaching.py 확장
```

**B-3-2: training_plan.py — 주간 계획 생성**
```
목표: 주간 트레이닝 계획 자동 생성

입력:
- UserProfile (목표, 피트니스 레벨)
- 현재 TrainingLoad
- Readiness 트렌드 (최근 7일)
- 피드백 히스토리 (최근 2주)

출력: WeeklyPlan (7일, 각 날짜별 세션 or 휴식)

로직:
1. 목표에 맞는 주간 구조 결정 (하드2/이지3/장거리1/휴식1 같은)
2. 현재 CTL 기반 적정 주간 TSS 범위 산출
3. Readiness 트렌드 반영 (하락 추세면 보수적)
4. 최근 피드백 반영 (RPE 높았으면 다음 주 하향)
5. LLM으로 구체적 세션 생성 → 가드레일 통과

산출물: engine/training_plan.py + tests/
```

**B-3-3: rules.py 확장 — Rule-based fallback**
```
목표: LLM 없이도 기본 코칭이 동작하도록

LLM 사용 불가 시 (API 장애, 키 미설정):
- Readiness Score 기반 오늘의 세션 타입 결정
- 간단한 템플릿 코칭 메시지 생성
- 가드레일은 동일하게 적용

산출물: engine/rules.py 확장
```

### 완료 기준

- [ ] 가드레일이 15개 이상의 위험 시나리오를 정확히 차단
- [ ] LLM 코칭 + 가드레일 파이프라인 end-to-end 동작
- [ ] Readiness Score → 코칭 강도 자동 조절 동작
- [ ] 주간 계획 생성 동작
- [ ] LLM 없이 rule-based fallback 동작
- [ ] coaching_guardrails.md 완성

### ⚠️ 유의사항

1. **가드레일 테스트가 이 트랙의 핵심**. 코칭 로직보다 가드레일에 더 많은
   테스트를 작성할 것. 안전이 프로덕트의 1번 원칙.
2. **LLM 시스템 프롬프트 설계가 중요**. coaching_guardrails.md를 포함하되,
   토큰 효율도 고려. 너무 길면 코칭 품질 저하.
3. **GuardrailResult에 reason을 항상 포함**. 사용자에게 "왜 변경되었는지"
   설명할 수 있어야 함 (Track D가 이걸 표시).
4. **Track A의 models/ 확정을 기다린 후 시작**. 특히 HealthMetrics와
   CoachingResponse 모델이 중요.

---

## Track C: 영양 + 피드백 + 리포트

### 담당 범위

```
garmin_coach/
├── nutrition/
│   ├── engine.py             # 영양 코칭 코어
│   ├── macros.py             # 🔲 Periodized Nutrition
│   ├── timing.py             # 🔲 운동 전/중/후 타이밍
│   ├── hydration.py          # 🔲 수분 섭취 가이드
│   └── recovery_fuel.py      # 🔲 회복 영양
├── feedback/
│   ├── collector.py          # 🔲 피드백 수집 오케스트레이터
│   ├── auto_analysis.py      # 🔲 자동 운동 분석
│   ├── subjective.py         # 🔲 주관적 피드백 (RPE 등)
│   ├── photo_analyzer.py     # 🔲 사진 분석 (Vision LLM)
│   └── aggregator.py         # 🔲 피드백 종합 → 코칭 개선
├── reports/
│   ├── weekly.py             # 🔲 주간 리포트
│   ├── monthly.py            # 🔲 월간 리포트
│   └── charts.py             # 🔲 시각화
└── models/
    └── feedback.py           # 🔲 피드백 관련 모델
```

### PRD 참조 섹션

- 섹션 5: 운동-영양 연계 코칭
- 섹션 6: 피드백 루프 시스템
- 섹션 7: 주간/월간 리포트

### 상세 작업 항목

#### Phase C-1: 영양 코칭 (Week 3-5)

**C-1-1: macros.py — Periodized Nutrition**
```
목표: PRD 섹션 5.2의 PeriodizedNutrition 클래스 구현

구현:
- CARB_PERIODIZATION 테이블 (세션 타입별 탄수화물 g/kg/day)
- PROTEIN 테이블 (목표별 단백질 g/kg/day)
- FAT_MINIMUM (1.0 g/kg/day)
- calculate_daily_macros(user, today_session, goal) → DailyMacros
- TDEE 추정 (기초대사량 + 활동계수 + 운동 칼로리)

의존성:
- Track A: UserProfile (체중, 목표)
- Track B: SessionType (오늘의 세션 타입)

산출물: nutrition/macros.py + tests/
```

**C-1-2: timing.py — 운동 전/중/후 타이밍**
```
목표: PRD 섹션 5.2의 NutritionTiming 구현

구현:
- PRE_WORKOUT: 3-4h / 1-2h / 30min 전 각각 권장
- DURING_WORKOUT: <60min / 60-90min / >90min / >3h 각각
- POST_WORKOUT: golden window (30-60분 이내)
- get_pre_workout_advice(time_until_workout, session_type)
- get_during_advice(session_duration, session_type)
- get_post_workout_advice(session_type, user)

산출물: nutrition/timing.py + tests/
```

**C-1-3: hydration.py + recovery_fuel.py**
```
목표: 수분 섭취 + 회복 영양 가이드

hydration.py:
- 일반 가이드라인 (운동 전/중/후)
- 땀 손실률 계산 (체중 변화 기반, 선택적)
- 환경 온도 기반 조정 (Track B 환경 안전 연계)

recovery_fuel.py:
- 세션 타입별 회복 영양 전략
- 구체적 음식 예시 (한국 음식 포함)
- 사용자 식단 제한 반영 (NutritionProfile)

산출물: nutrition/hydration.py, recovery_fuel.py + tests/
```

#### Phase C-2: 피드백 루프 (Week 5-7)

**C-2-1: collector.py — 피드백 수집 오케스트레이터**
```
목표: PRD 섹션 6.2의 FeedbackCollector 구현

동작:
1. 새 activity 감지 이벤트 수신 (Track A의 sync에서 발행)
2. auto_analysis로 자동 분석 실행
3. 운동 타입에 맞는 피드백 질문 생성
4. Track D의 port를 통해 사용자에게 전달

핵심: collector는 ports.py의 CoachingPort를 통해 메시지를 보냄.
      Telegram을 직접 import하지 않음.

산출물: feedback/collector.py
```

**C-2-2: auto_analysis.py — 자동 운동 분석**
```
목표: Garmin 데이터 기반 자동 분석

분석 항목:
- 세션 요약 (거리, 시간, 평균 심박, Zone 분포)
- Training Effect (유산소/무산소)
- TSS 기여도
- 이전 유사 세션 대비 비교
  (같은 타입의 최근 세션과 페이스/심박 비교)
- 페이스/파워 드리프트 분석 (장거리 세션)

산출물: feedback/auto_analysis.py + tests/
```

**C-2-3: subjective.py — 주관적 피드백 수집**
```
목표: RPE, 느낌, 통증 등 주관적 데이터 수집 로직

구현:
- RPEQuestion, FeelingQuestion, CompletionQuestion 등
- 운동 타입별 조건부 질문 로직 (PRD 섹션 6.2 참조)
  → 인터벌 후: 세트 완료 여부, 목표 페이스 달성
  → 장거리 후: 보급 상태, GI 문제
  → 부상 복귀 중: 통증 여부

산출물: feedback/subjective.py + tests/
```

**C-2-4: photo_analyzer.py — 사진 분석**
```
목표: PRD 섹션 6.3의 PhotoAnalyzer 구현

지원 타입:
- workout_screenshot: 가민/스트라바 캡쳐 → 데이터 추출
- food_photo: 식단 → 매크로 추정

구현:
- Vision LLM (Claude Vision 또는 GPT-4V) 호출
- 구조화된 응답 파싱 (JSON)
- 매크로 추정 신뢰도 표시 (low/medium/high)

⚠️ 주의: injury_photo, body_progress는 v1에서 제외.
         의학적 해석 위험 + 개인정보 민감도.

산출물: feedback/photo_analyzer.py + tests/
```

**C-2-5: aggregator.py — 피드백 → 코칭 개선**
```
목표: PRD 섹션 6.4의 FeedbackAggregator 구현

로직:
1. RPE vs Actual Intensity 괴리 분석
   → RPE 높은데 Zone 낮으면 = 컨디션 저하 신호
2. 통증 피드백 → 부상 가드레일 업데이트
   → 같은 부위 2회 연속 → auto-restrict
3. 목표 페이스 달성률 트래킹
   → 5회 중 4회 달성 → 상향 제안
4. 영양 피드백 → 영양 코칭 조정
   → GI 문제 반복 → 운동 전 식사 가이드 수정

저장: 피드백 히스토리를 DB에 저장 (Track A의 storage 활용)

산출물: feedback/aggregator.py + tests/
```

#### Phase C-3: 리포트 (Week 7-9)

**C-3-1: weekly.py — 주간 리포트**
```
목표: PRD 섹션 7.1의 주간 리포트 생성

내용:
- 주간 운동 요약 (횟수, 거리, 시간)
- CTL/ATL/TSB 변화 + Ramp Rate
- 수면 & 회복 평균
- 영양 기록 요약
- 피드백 요약 (평균 RPE, 통증, 달성률)
- 다음 주 계획 미리보기
- 코치 코멘트 (LLM 생성)

출력 형식: 구조화된 ReportData → Track D가 채널별로 렌더링

산출물: reports/weekly.py + tests/
```

**C-3-2: monthly.py — 월간 리포트**
```
목표: 주간 리포트 4개를 종합한 장기 트렌드 분석

추가 내용:
- CTL/피트니스 월간 그래프 데이터
- 목표 대비 진척도
- 부상/통증 히스토리 월간 트렌드
- 다음 달 메조사이클 미리보기

산출물: reports/monthly.py + tests/
```

**C-3-3: charts.py — 시각화**
```
목표: 리포트에 들어갈 차트/그래프 이미지 생성

라이브러리: matplotlib (PNG 이미지 생성, Telegram 전송 가능)

차트 목록:
- CTL/ATL/TSB 주간 추이 (선 그래프)
- 심박 Zone 분포 (막대 그래프)
- 주간 거리/시간 (막대 그래프)
- HRV 트렌드 (선 그래프)
- Readiness Score 주간 추이 (색상 영역 차트)

산출물: reports/charts.py + tests/
```

### 완료 기준

- [ ] 영양 코칭이 세션 타입에 따라 다른 매크로 권장
- [ ] 운동 후 자동 분석 + 피드백 수집 파이프라인 동작
- [ ] 사진 분석 (캡쳐, 식단) 동작
- [ ] 피드백이 다음 코칭에 반영되는 루프 확인
- [ ] 주간 리포트 생성 동작
- [ ] 차트 이미지 생성 동작

### ⚠️ 유의사항

1. **피드백 루프가 이 프로덕트의 핵심 가치**. collector → analysis →
   subjective → aggregator 파이프라인에 가장 많은 시간 투자.
2. **영양 코칭의 알레르기/식단 제한 필터는 Track B 가드레일과 연동**.
   nutrition 모듈이 자체 필터 + Track B 가드레일 이중 체크.
3. **photo_analyzer는 Vision LLM 비용 주의**. 매 사진마다 호출하면
   비용 급증. 캐싱이나 로컬 추론 고려.
4. **리포트의 "코치 코멘트"는 Track B의 engine을 호출**하여 생성.
   리포트 자체를 LLM으로 생성하는 게 아니라, 데이터 요약은 코드로,
   코멘트만 LLM으로.
5. **charts.py는 Telegram에서 보기 좋은 크기/비율**로 생성.
   800x400px 정도, 다크모드 호환 색상.

---

## Track D: Telegram UX + 온보딩

### 담당 범위

```
garmin_coach/
├── ports.py                  # 🔲 CoachingPort 추상 인터페이스
├── flows/                    # 🔲 비즈니스 플로우 (채널 무관)
│   ├── onboarding.py
│   ├── post_workout.py
│   ├── morning_briefing.py
│   ├── evening_checkin.py
│   ├── nutrition_log.py
│   └── injury_report.py
├── interfaces/telegram/      # Telegram 구현
│   ├── adapter.py            # TelegramAdapter(CoachingPort)
│   ├── keyboards.py          # 인라인 키보드 헬퍼
│   ├── handlers.py           # 명령어/콜백 핸들러
│   └── renderer.py           # 메시지 포매팅
└── wizard/
    ├── onboarding.py         # 온보딩 데이터 수집 로직
    └── settings.py           # 설정 변경
```

### PRD 참조 섹션

- 섹션 4: 온보딩 플로우 전체
- 섹션 9: Telegram Bot UX
- 섹션 10.1: 인터페이스 분리 (3-Layer 구조)

### 상세 작업 항목

#### Phase D-1: 기반 구조 (Week 1-2)

**D-1-1: ports.py — CoachingPort 정의**
```
목표: 모든 채널이 구현할 추상 인터페이스 정의

메서드:
- send_message(user_id, text, buttons?) → None
- send_image(user_id, image, caption?) → None
- request_input(user_id, prompt, input_type) → str
- request_select(user_id, prompt, options) → str
- request_multi_select(user_id, prompt, options) → list[str]
- request_photo(user_id, prompt) → bytes
- send_report(user_id, report) → None

InputType enum: TEXT, NUMBER, DATE, SELECT, MULTI_SELECT, PHOTO

⚠️ Week 1 끝나기 전에 main에 머지. 다른 트랙이 이걸 참조.

산출물: ports.py
```

**D-1-2: flows/ 스켈레톤**
```
목표: 모든 비즈니스 플로우의 인터페이스와 스텁 구현

각 flow 파일의 구조:
class XxxFlow:
    def __init__(self, port: CoachingPort, engine: CoachingEngine):
        ...
    async def execute(self, user_id: str, **kwargs):
        ...

스텁으로 시작하되, 각 flow의 step을 주석으로 명확히 기술.
실제 로직은 Track B/C의 코드가 준비되면 채움.

⚠️ 핵심 규칙: flows/ 안의 어떤 파일도
   interfaces/telegram/을 import하면 안 됨.
   반드시 ports.py의 CoachingPort만 사용.

산출물: flows/ 전체 스켈레톤
```

**D-1-3: TelegramAdapter(CoachingPort) 구현**
```
목표: CoachingPort를 Telegram Bot API로 구현

구현:
- send_message → bot.send_message (MarkdownV2 포매팅)
- send_image → bot.send_photo
- request_input → 텍스트 입력 대기 (ConversationHandler)
- request_select → InlineKeyboardMarkup + CallbackQuery 대기
- request_multi_select → 다중 선택 키보드
- request_photo → 사진 수신 대기
- send_report → 텍스트 + 이미지 조합

라이브러리: python-telegram-bot v20+ (async 기반)

산출물: interfaces/telegram/adapter.py
```

#### Phase D-2: 온보딩 (Week 2-4)

**D-2-1: wizard/onboarding.py — 온보딩 데이터 수집**
```
목표: PRD 섹션 4의 3단계 온보딩 전체 구현

Phase 1 (필수):
1. Garmin 연동 (이메일/비밀번호)
2. 기본 프로필 (생년월일, 성별, 키, 체중)
3. 운동 목표 (선택지 + 조건부 추가 질문)
4. 현재 피트니스 레벨 자동 감지 (Garmin 30일 데이터 분석)

Phase 2 (권장):
5. 의료/건강 이력 (심장질환, 고혈압, 당뇨, 부상, 약물)
   ⚠️ 베타차단제 → beta_blocker 플래그 → Track B 가드레일 연동
6. 영양/식단 (식이제한, 알레르기, 식사패턴, 보충제)
7. 수면 패턴 (취침/기상, 수면 문제)

Phase 3 (선택):
8. Strava 연동
9. 선호 운동 시간대
10. 코칭 톤 선호
11. 알림 빈도

각 Phase 완료 시 즉시 피드백:
"이 정보로 [X] 코칭이 가능합니다"

산출물: wizard/onboarding.py + tests/
```

**D-2-2: keyboards.py — Telegram 인라인 키보드**
```
목표: 온보딩 + 일상 상호작용용 키보드 헬퍼

구현:
- 단일 선택 키보드 (예: 운동 목표)
- 다중 선택 키보드 (예: 식이 제한)
- 숫자 입력 키보드 (예: 목표 시간)
- 날짜 선택 키보드 (예: 대회 날짜)
- RPE 1-10 스케일 키보드
- 이모지 느낌 키보드 (😀😐😫🤕)
- 확인/취소 키보드

디자인 원칙:
- 타이핑 최소화 (탭으로 해결)
- 한 화면에 4개 이하 선택지
- 현재 단계 표시 (예: "3/7단계")

산출물: interfaces/telegram/keyboards.py
```

#### Phase D-3: 핵심 UX 플로우 (Week 4-7)

**D-3-1: flows/morning_briefing.py — 아침 브리핑**
```
목표: PRD 섹션 9.1의 아침 브리핑

트리거: 매일 설정된 기상 시간 (또는 Body Battery 상승 감지)

내용:
1. Readiness Score + 세부 지표 (수면, HRV, BB, RHR)
2. 오늘의 계획 (세션 타입 + 구체적 내용)
3. 영양 리마인더 (운동 전 식사)
4. 선택지: [계획대로] [변경] [내일로]

의존성:
- Track A: ReadinessScore, HealthMetrics
- Track B: CoachingEngine.generate_daily_coaching()
- Track C: NutritionTiming.get_pre_workout_advice()

산출물: flows/morning_briefing.py
```

**D-3-2: flows/post_workout.py — 운동 후 플로우**
```
목표: PRD 섹션 6.2 + 9.1의 운동 후 자동 분석 + 피드백

트리거: 새 activity 감지 (Track A sync 이벤트)

순서:
1. 자동 분석 결과 전송 (Track C auto_analysis)
2. 영양 회복 권장 전송 (Track C recovery_fuel)
3. RPE 질문 (Track C subjective)
4. 느낌 질문
5. 조건부 추가 질문 (통증 등)
6. "뭘 먹었는지 기록" 선택 시 → 사진 또는 텍스트 수신

산출물: flows/post_workout.py
```

**D-3-3: flows/evening_checkin.py — 저녁 체크인**
```
목표: 선택적 저녁 체크인

내용:
- 오늘 요약 (운동, 활동 칼로리, 걸음, 스트레스)
- 식단 기록 프롬프트
- 내일 아침 세션 대비 취침 시간 권고

산출물: flows/evening_checkin.py
```

**D-3-4: handlers.py — 명령어 체계**
```
목표: PRD 섹션 9.2의 명령어 전체 구현

/start → 온보딩 시작
/today → 아침 브리핑 (수동 호출)
/week → 이번 주 계획
/report → 즉시 주간 리포트 (Track C weekly.py)
/feedback → 수동 피드백 입력
/nutrition → 오늘의 영양 가이드 (Track C macros + timing)
/settings → 프로필/설정 수정
/goals → 목표 확인/수정
/injury → 부상 보고 (flows/injury_report.py)
/help → 도움말

사진 처리:
- 사진 수신 시 자동 타입 감지 시도
- 실패 시: [📊 운동 캡쳐] [🍽️ 식단 사진] [📸 기타]

자유 텍스트:
- 명령어 아닌 텍스트 → Track B의 answer_question()으로 전달
  (자연어 질의응답: "오늘 뭐 먹으면 좋아?", "내 CTL 어때?" 등)

산출물: interfaces/telegram/handlers.py
```

**D-3-5: renderer.py — 메시지 포매팅**
```
목표: 각종 데이터를 Telegram 읽기 좋은 형태로 포매팅

구현:
- Readiness Score → 이모지 + 수치 포매팅
- 운동 분석 결과 → 구조화된 메시지
- 주간 리포트 → 텍스트 + 차트 이미지 조합
- 영양 권장 → 음식 이모지 + 구체적 예시
- 에러 메시지 → 친절한 안내

Telegram MarkdownV2 주의사항:
- 특수문자 이스케이프 필수 (., -, !, ( 등)
- 4096자 제한 → 긴 메시지 분할

산출물: interfaces/telegram/renderer.py
```

#### Phase D-4: 자동화 + 마감 (Week 7-10)

**D-4-1: 스케줄러 통합**
```
목표: 자동 메시지 발송 스케줄링

- 아침 브리핑: 사용자별 설정 시간 (기본 07:00)
- 저녁 체크인: 사용자별 설정 시간 (기본 21:00)
- 주간 리포트: 매주 일요일 저녁 (기본 20:00)
- 월간 리포트: 매월 1일 (기본 09:00)
- 운동 후 분석: activity 감지 후 즉시

구현: APScheduler 또는 python-telegram-bot의 JobQueue

산출물: interfaces/telegram/scheduler.py
```

**D-4-2: 에러 핸들링 + 엣지 케이스**
```
- Garmin 데이터 없을 때 (워치 미착용, 충전 중)
- LLM 응답 실패 시 (rule-based fallback 안내)
- 사용자가 온보딩 중간에 이탈 후 복귀
- 비정상 입력 (숫자 요청에 텍스트 입력 등)
- Telegram API 장애 시 재시도 로직
- 여러 메시지 동시 수신 처리

산출물: 각 모듈에 에러 핸들링 추가
```

### 완료 기준

- [ ] 온보딩 3단계 전체 Telegram에서 동작
- [ ] 아침 브리핑 자동 발송 동작
- [ ] 운동 감지 → 자동 분석 → 피드백 수집 전체 플로우 동작
- [ ] 사진 전송 → 분석 동작
- [ ] 10개 명령어 전체 동작
- [ ] 주간 리포트 자동 발송 동작
- [ ] flows/ 폴더에 telegram import 없음 (이거 CI로 체크)

### ⚠️ 유의사항

1. **ports.py가 이 트랙의 가장 중요한 산출물**. Week 1에 확정.
   이게 확정되어야 Track C의 피드백 수집이 진행됨.
2. **flows/와 interfaces/telegram/ 분리를 반드시 유지**.
   테스트 또는 CI에서 `grep -r "telegram" garmin_coach/flows/`가
   0 결과여야 함.
3. **Telegram 메시지 길이 제한 (4096자) 주의**. 주간 리포트 등
   긴 메시지는 분할 전송 로직 필요.
4. **인라인 키보드 콜백 데이터 64바이트 제한**. 콜백 데이터에
   긴 문자열 못 넣음. ID 기반으로 처리.
5. **ConversationHandler 상태 관리 복잡**. 온보딩처럼 다단계
   플로우는 상태 머신 패턴으로 깔끔하게 구현.
6. **Track A의 sync 이벤트 → D의 post_workout 트리거 연결**이
   Week 5에 반드시 통합되어야 함. 이벤트 시스템 사전 합의 필요.

---

## 통합 마일스톤

| 주차 | 마일스톤 | 관련 트랙 | 검증 방법 |
|------|---------|---------|----------|
| Week 1 끝 | models/ + ports.py main 머지 | A, D | 다른 트랙에서 import 성공 |
| Week 2 끝 | engine/interfaces.py main 머지 | B | Track C, D에서 참조 가능 |
| Week 3 | 건강 데이터 수집 end-to-end | A | 수면+HRV+BB 실제 데이터 확인 |
| Week 4 | 온보딩 Phase 1 Telegram 동작 | D + A | 실제 봇에서 Garmin 연동까지 |
| Week 5 | 가드레일 + 코칭 파이프라인 | B + A | 위험 시나리오 15개 테스트 통과 |
| Week 5 | 운동 감지 → Telegram 자동 분석 | A + C + D | 실제 운동 후 메시지 수신 |
| Week 7 | 영양 코칭 + 피드백 루프 통합 | C + D | 운동 후 영양 권장 + RPE 수집 |
| Week 8 | 주간 리포트 자동 발송 | C + D | 일요일 저녁 자동 리포트 수신 |
| Week 10 | 전체 플로우 end-to-end | ALL | 1주일 실사용 테스트 통과 |

---

## 트랙 간 커뮤니케이션 규칙

### 매일 (비동기)
- 각 트랙은 작업 시작/종료 시 간단히 상태 공유
- 블로커가 있으면 즉시 공유

### 주 1회 (동기)
- 4개 트랙 합동 싱크
- 통합 마일스톤 확인
- 인터페이스 변경 사항 리뷰
- 다음 주 통합 작업 계획

### 인터페이스 변경 시 (즉시)
- models/, ports.py, engine/interfaces.py 변경 → PR 올리고 모든 트랙에 알림
- 변경 사유 + 영향 범위 명시
- 24시간 내 리뷰 + 머지
