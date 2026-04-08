# Garmin Personal Coach — PRD v2.0

> **Product Vision**: Garmin, Strava, Nike 등 운동 기록 사용자를 위한 **완벽한 나만의 AI 코치**.
> 개인화된 운동 처방, 건강 컨디션 모니터링, 영양 코칭, 수면 최적화를 하나의 시스템으로 통합.

---

## 1. 프로덕트 원칙

| 원칙 | 설명 |
|------|------|
| **Safety First** | AI 코칭은 절대 사용자를 다치게 하면 안 된다. 안전 가드레일이 LLM 출력보다 항상 우선. |
| **Data-Driven Personalization** | 모든 코칭은 사용자의 실제 데이터에 기반. 추측 금지. |
| **Feedback Loop is the Product** | 코칭 → 실행 → 피드백 → 개선 사이클이 핵심 가치. |
| **Zero Friction** | Telegram에서 운동 끝나고 30초 안에 피드백 받을 수 있어야 함. |

---

## 2. 사용자 페르소나

### Primary: 지구력 운동 선수 (러너/사이클리스트/트라이애슬릿)
- Garmin 워치 착용, 주 4-6회 운동
- 마라톤 서브3, 100km 울트라, 아이언맨 등 구체적 목표 보유
- 트레이닝 피크스나 코치 비용이 부담스러운 아마추어 엘리트

### Secondary: 일반 피트니스 사용자
- Garmin 또는 Strava로 러닝/사이클링 기록
- 건강 유지, 체중 관리, 스트레스 관리 목적
- 전문 코칭까지는 필요 없지만 개인화된 가이드 원함

### Tertiary: 부상 복귀 중인 운동선수
- 의사/물리치료사의 가이드라인 내에서 안전하게 복귀 원함
- 보수적이고 안전한 코칭이 특히 중요

---

## 3. 데이터 아키텍처

### 3.1 Garmin 데이터 수집 매트릭스

모든 데이터는 Garmin Connect API (garminconnect 라이브러리) 또는 Garmin Health API를 통해 수집.

#### Activity Data (운동 데이터)
```
garmin_coach/adapters/garmin/activity.py
```

| 데이터 | 소스 API | 코칭 활용 | 우선순위 |
|--------|---------|----------|---------|
| 운동 타입/거리/시간 | `get_activities()` | 트레이닝 로드 계산, 볼륨 추적 | P0 ✅ 구현됨 |
| 심박수 (avg/max/zones) | `get_activity_hr()` | 강도 분석, Zone 분포, 유산소/무산소 비율 | P0 ✅ 구현됨 |
| 페이스/파워 | `get_activity_details()` | 퍼포먼스 트렌드, 임계 페이스/파워 추정 | P0 ✅ 구현됨 |
| Training Effect (TE) | `get_activity_details()` | 유산소/무산소 TE로 세션 효과 평가 | P0 🔲 미구현 |
| Running Dynamics | `get_activity_details()` | 보폭/케이던스/GCT로 폼 분석 | P1 🔲 미구현 |
| GPS/고도 데이터 | `get_activity_details()` | 경사 훈련 분석, 코스별 퍼포먼스 | P2 🔲 미구현 |

#### Training Load Metrics (트레이닝 로드)
```
garmin_coach/integrations/training_load.py
```

| 메트릭 | 계산 방식 | 코칭 활용 | 우선순위 |
|--------|----------|----------|---------|
| TSS (Training Stress Score) | TRIMP 또는 rTSS 기반 | 일일 부하 정량화 | P0 ✅ 구현됨 |
| CTL (Chronic Training Load) | 42일 지수 이동평균 | 피트니스 레벨 | P0 ✅ 구현됨 |
| ATL (Acute Training Load) | 7일 지수 이동평균 | 피로도 | P0 ✅ 구현됨 |
| TSB (Training Stress Balance) | CTL - ATL | 컨디션/회복 상태 | P0 ✅ 구현됨 |
| Ramp Rate | CTL 주간 변화율 | 과부하 경고 | P0 🔲 미구현 |
| Monotony | 주간 부하 평균 / 표준편차 | 훈련 단조로움 경고 | P1 🔲 미구현 |
| Strain | 주간 부하 합 × Monotony | 과훈련 위험도 | P1 🔲 미구현 |

#### Health & Recovery Data (건강/회복 데이터)
```
garmin_coach/adapters/garmin/health.py  ← 신규 모듈
```

| 데이터 | 소스 API | 코칭 활용 | 우선순위 |
|--------|---------|----------|---------|
| **Sleep Score** | `get_sleep_data()` | 회복 품질 → 당일 강도 조절 | P0 🔲 미구현 |
| **Sleep Stages** | `get_sleep_data()` | 딥슬립/REM 비율 → 회복 평가 | P0 🔲 미구현 |
| **HRV (Heart Rate Variability)** | `get_hrv_data()` | 자율신경 회복도 → 가장 강력한 컨디션 지표 | P0 🔲 미구현 |
| **HRV Status** | `get_hrv_data()` | 7일 HRV 트렌드 → 과훈련 조기 감지 | P0 🔲 미구현 |
| **Body Battery** | `get_body_battery()` | 실시간 에너지 레벨 → 운동 타이밍 추천 | P0 🔲 미구현 |
| **Stress Score** | `get_stress_data()` | 일일 스트레스 → 정신적 부하 반영 | P0 🔲 미구현 |
| **Resting Heart Rate** | `get_rhr_day()` | RHR 트렌드 → 피트니스/오버트레이닝 지표 | P0 🔲 미구현 |
| **SpO2** | `get_spo2_data()` | 혈중 산소 → 고지대 훈련, 수면 무호흡 감지 | P1 🔲 미구현 |
| **Respiration Rate** | `get_respiration_data()` | 호흡수 트렌드 → 회복/스트레스 보조 지표 | P2 🔲 미구현 |
| **Body Composition** | `get_body_composition()` | 체중/체지방 트렌드 → 영양 코칭 연계 | P1 🔲 미구현 |

### 3.2 Readiness Score (컨디션 종합 점수)

Garmin 자체 "Morning Report"를 참고하되, 코칭에 직접 활용 가능한 자체 스코어를 산출.

```
garmin_coach/engine/readiness.py  ← 신규 모듈
```

```python
class ReadinessScore:
    """
    0-100 종합 컨디션 점수.
    각 요소의 가중치는 사용자별로 캘리브레이션됨 (최소 14일 데이터 필요).
    """

    COMPONENTS = {
        "hrv_status":     0.30,  # HRV 7일 기준선 대비 변화
        "sleep_score":    0.25,  # Garmin Sleep Score (0-100)
        "body_battery":   0.15,  # 기상 시 Body Battery
        "rhr_deviation":  0.15,  # RHR 7일 평균 대비 편차
        "tsb":            0.10,  # Training Stress Balance
        "stress_avg":     0.05,  # 전일 평균 스트레스
    }

    THRESHOLDS = {
        "green":  75,   # 정상 훈련 가능
        "yellow": 50,   # 강도 하향 권고
        "red":    30,   # 휴식 또는 경량 회복 세션만
    }
```

**코칭 연계:**
- 🟢 Green (75+): 계획대로 훈련, 하드 세션 OK
- 🟡 Yellow (50-74): 강도 20-40% 하향, 인터벌 → 템포로 변경
- 🔴 Red (<50): 완전 휴식 또는 20분 이하 Zone 1 리커버리만
- 🚨 Critical (<20): 운동 금지, 건강 이상 가능성 알림

### 3.3 Strava 보조 싱크 (기존)

Garmin → Strava 자동 싱크된 데이터의 소셜 레이어(kudos, segments, relative effort)를 보조 활용. Strava가 primary source가 되면 안 됨 (데이터 정밀도가 Garmin보다 낮음).

### 3.4 Nike Run Club (로드맵)

`adapters/nike/` scaffold 유지. Nike API 접근 제한으로 현재 구현 불가. 사용자가 수동 입력하거나 GPX export → import 플로우로 우회 가능.

---

## 4. 온보딩 플로우

### 4.1 설계 원칙

- 한 번에 다 받지 않음. **필수 → 권장 → 선택** 3단계로 나눔
- 각 단계가 끝나면 즉시 "이 정보로 이런 코칭이 가능합니다" 피드백
- 이후에도 언제든 `/settings` 로 수정 가능
- Telegram에서 인라인 키보드로 진행 (타이핑 최소화)

### 4.2 Phase 1: 필수 (첫 시작 시 반드시 완료)

```
garmin_coach/wizard/onboarding.py
```

#### Step 1: Garmin 연동
```
🏃 Garmin Personal Coach에 오신 것을 환영합니다!

먼저 Garmin Connect 계정을 연결할게요.
이메일과 비밀번호를 입력해주세요.
(데이터는 로컬에만 저장되며, 서버로 전송되지 않습니다)

📧 Email: ___
🔑 Password: ___
```

#### Step 2: 기본 프로필
```
📋 기본 정보를 알려주세요.

생년월일: ____-__-__
성별: [남성] [여성] [기타] [응답하지 않음]
키(cm): ___
체중(kg): ___

⚠️ 이 정보는 심박 Zone 계산, 칼로리 추정, 페이스 환산에 사용됩니다.
```

#### Step 3: 운동 목표
```
🎯 주요 운동 목표를 선택해주세요.

[🏃 마라톤/하프마라톤 기록 단축]
[🚴 사이클링 퍼포먼스 향상]
[🏊 트라이애슬론 완주/기록]
[💪 일반 피트니스 & 건강 유지]
[⚖️ 체중 관리]
[🔄 부상 복귀]

👉 선택에 따라 추가 질문이 달라집니다.
```

**마라톤 선택 시 추가:**
```
🏃 마라톤 목표를 구체적으로 알려주세요.

목표 대회: ___ (선택)
목표 시간: __:__:__
대회 날짜: ____-__-__
현재 주간 러닝 거리(km): ___
최근 레이스 기록 (있으면): ___
```

**부상 복귀 선택 시 추가:**
```
🔄 부상 복귀 정보

부상 부위: [무릎] [발목] [아킬레스] [허리] [햄스트링] [기타: ___]
의사/물리치료사 허가: [예, 운동 가능] [제한적 허가] [아직 미확인]
제한 사항: ___ (예: "충격 운동 불가", "심박 150 이하만")

⚠️ 이 정보는 안전 가드레일에 반영됩니다.
   의학적 조언을 대체하지 않습니다.
```

#### Step 4: 현재 피트니스 레벨 자동 감지
```
📊 Garmin 데이터를 분석 중...

최근 30일 데이터 기반:
- 주간 평균 거리: 42km
- 주간 평균 운동 횟수: 4.2회
- 평균 심박 Zone 분포: Z2 60% / Z3 25% / Z4 15%
- 추정 VO2max: 52
- 추정 피트니스 레벨: 중급-고급

이 분석이 맞나요? [네, 맞아요] [아니오, 조정할게요]
```

### 4.3 Phase 2: 권장 (첫 주 내 완료 권장)

#### Step 5: 의료/건강 이력
```
🏥 건강 정보 (선택이지만 안전한 코칭을 위해 권장)

알려진 심장 질환: [없음] [있음: ___]
고혈압: [없음] [있음 (약 복용 중)] [있음 (미치료)]
당뇨: [없음] [1형] [2형]
천식/호흡기: [없음] [있음: ___]
과거 부상 이력: ___ (자유 입력)
현재 복용 약물: ___ (베타차단제 등 심박에 영향주는 약물 중요)
기타 주의사항: ___

⚠️ 이 정보는 안전 가드레일에 반영됩니다.
   절대 외부로 전송되지 않으며, 로컬에만 저장됩니다.
```

> **중요**: 베타차단제 복용자는 심박 기반 Zone 계산이 부정확해짐.
> RPE(체감 강도) 기반 코칭으로 자동 전환 필요.

#### Step 6: 영양/식단 기본 설정
```
🍎 식단 정보

식이 제한: [없음] [채식] [비건] [글루텐프리] [유당불내증] [할랄] [기타: ___]
음식 알레르기: ___ (자유 입력)
현재 식사 패턴: [하루 3끼] [간헐적 단식 16:8] [하루 2끼] [불규칙]
보충제 복용: ___ (프로틴, 크레아틴, 카페인 등)
음주 빈도: [안 마심] [주 1-2회] [주 3-4회] [거의 매일]

💡 이 정보를 기반으로 운동 전후 영양 권장을 제공합니다.
```

#### Step 7: 수면 패턴
```
😴 수면 정보

평균 취침 시간: __:__
평균 기상 시간: __:__
수면 관련 문제: [없음] [불면증] [수면 무호흡] [야간 각성] [기타: ___]

💡 Garmin 수면 데이터와 교차 분석하여 회복 코칭에 반영합니다.
```

### 4.4 Phase 3: 선택 (언제든 추가 가능)

- Strava 연동
- 선호 운동 시간대
- 크로스트레이닝 선호도 (수영, 요가, 웨이트 등)
- 코칭 톤 선호 ([격려형] [팩트형] [엄격한 코치형])
- 알림 빈도 설정
- 단위계 (km/mi, kg/lb)

### 4.5 데이터 모델

```python
# garmin_coach/models/user_profile.py

@dataclass
class UserProfile:
    # Phase 1: 필수
    garmin_credentials: GarminAuth
    birth_date: date
    sex: str                     # "male" | "female" | "other" | "undisclosed"
    height_cm: float
    weight_kg: float
    goal: TrainingGoal
    fitness_level: FitnessLevel  # 자동 감지 + 사용자 확인

    # Phase 2: 권장
    medical: MedicalProfile | None
    nutrition: NutritionProfile | None
    sleep: SleepProfile | None

    # Phase 3: 선택
    preferences: CoachingPreferences | None
    strava_auth: StravaAuth | None

@dataclass
class MedicalProfile:
    cardiac_conditions: list[str]
    hypertension: str            # "none" | "treated" | "untreated"
    diabetes: str                # "none" | "type1" | "type2"
    respiratory: list[str]
    injury_history: list[InjuryRecord]
    current_injuries: list[InjuryRecord]
    medications: list[Medication]
    beta_blocker: bool           # True면 HR 기반 Zone 비활성화
    notes: str

@dataclass
class InjuryRecord:
    body_part: str
    description: str
    date_occurred: date | None
    date_cleared: date | None
    restrictions: list[str]      # 예: ["no_impact", "hr_below_150"]
    medical_clearance: str       # "full" | "limited" | "pending"

@dataclass
class NutritionProfile:
    dietary_restrictions: list[str]
    allergies: list[str]
    meal_pattern: str
    supplements: list[str]
    alcohol_frequency: str
    daily_calorie_target: int | None  # 체중 관리 목표 시 자동 계산

@dataclass
class TrainingGoal:
    type: str                    # "marathon" | "cycling" | "triathlon" | "fitness" | "weight" | "rehab"
    target_event: str | None
    target_time: timedelta | None
    target_date: date | None
    weekly_volume_km: float
    recent_race: RaceResult | None
```

---

## 5. 운동-영양 연계 코칭

### 5.1 아키텍처

```
garmin_coach/nutrition/
├── engine.py           # 영양 코칭 코어 로직
├── macros.py           # 매크로 계산 (탄/단/지)
├── timing.py           # 운동 전후 타이밍 권장
├── hydration.py        # 수분 섭취 가이드
├── recovery_fuel.py    # 회복 영양 전략
└── templates/          # 식단 제안 템플릿
    ├── pre_workout.py
    ├── post_workout.py
    ├── race_day.py
    └── rest_day.py
```

### 5.2 영양 코칭 로직

#### 기본 원칙: **Fuel for the Work Required**

훈련 강도와 볼륨에 따라 탄수화물 섭취량을 조절하는 "Periodized Nutrition" 접근법.

```python
# garmin_coach/nutrition/macros.py

class PeriodizedNutrition:
    """
    운동 강도/볼륨에 따른 일일 매크로 가이드.
    출처: Asker Jeukendrup, ACSM Position Stand, IOC Consensus.
    모든 값은 체중(kg) 기준 g/kg/day.
    """

    CARB_PERIODIZATION = {
        # (운동 강도, 운동 시간) → 탄수화물 g/kg/day
        "rest_day":           (3.0, 5.0),    # 회복일
        "light_session":      (4.0, 6.0),    # Zone 1-2, <60min
        "moderate_session":   (5.0, 7.0),    # Zone 2-3, 60-90min
        "hard_session":       (6.0, 8.0),    # Zone 3-4, 인터벌/템포
        "long_session":       (7.0, 10.0),   # >90min 장거리
        "race_day":           (8.0, 12.0),   # 레이스 또는 레이스 시뮬레이션
    }

    PROTEIN = {
        "endurance":  (1.2, 1.6),   # g/kg/day
        "strength":   (1.6, 2.2),
        "weight_loss": (1.6, 2.4),  # 근손실 방지 위해 높게
        "rehab":      (1.6, 2.0),   # 회복 촉진
    }

    FAT_MINIMUM = 1.0  # g/kg/day, 호르몬 기능 유지를 위한 최소값

    @classmethod
    def calculate_daily_macros(
        cls,
        user: UserProfile,
        today_session: SessionType,
        goal: TrainingGoal,
    ) -> DailyMacros:
        """
        오늘의 운동 타입에 맞는 매크로 범위 계산.
        """
        weight = user.weight_kg
        carb_range = cls.CARB_PERIODIZATION[today_session]
        protein_range = cls.PROTEIN[goal.type]

        return DailyMacros(
            carbs_g=(carb_range[0] * weight, carb_range[1] * weight),
            protein_g=(protein_range[0] * weight, protein_range[1] * weight),
            fat_g=(cls.FAT_MINIMUM * weight, None),  # 상한은 칼로리 잔여로 계산
            total_kcal=cls._estimate_tdee(user, today_session),
        )
```

#### 운동 전후 타이밍 코칭

```python
# garmin_coach/nutrition/timing.py

class NutritionTiming:
    """
    운동 전/중/후 영양 타이밍 가이드.
    """

    PRE_WORKOUT = {
        # 운동까지 남은 시간별 권장
        "3-4h_before": {
            "description": "정상 식사 가능",
            "carbs": "1-2g/kg",
            "protein": "포함",
            "fat": "적당히 OK",
            "fiber": "적당히 OK",
        },
        "1-2h_before": {
            "description": "가벼운 간식",
            "carbs": "0.5-1g/kg",
            "protein": "소량",
            "fat": "최소화",
            "fiber": "최소화",
            "examples": ["바나나 + 꿀", "흰쌀밥 소량", "에너지바", "토스트 + 잼"],
        },
        "30min_before": {
            "description": "빠른 에너지만",
            "carbs": "0.3-0.5g/kg",
            "examples": ["젤 1개", "스포츠 드링크", "바나나 반개"],
        },
    }

    DURING_WORKOUT = {
        # 운동 시간별 권장
        "under_60min": "수분만 (물 또는 전해질)",
        "60_90min": "30-60g 탄수화물/시간 (젤, 스포츠 드링크)",
        "over_90min": "60-90g 탄수화물/시간 (혼합 탄수화물: 포도당+과당)",
        "over_3h": "60-90g 탄수화물/시간 + 소금 보충 필수",
    }

    POST_WORKOUT = {
        # 회복 영양 (운동 후 30-60분 이내)
        "golden_window": {
            "carbs": "1.0-1.2g/kg",
            "protein": "0.3-0.4g/kg (20-40g)",
            "timing": "운동 후 30분 이내 이상적, 60분 이내 권장",
            "examples": [
                "초코우유 500ml",
                "프로틴 쉐이크 + 바나나",
                "밥 + 닭가슴살",
                "그릭 요거트 + 그래놀라 + 과일",
            ],
        },
    }
```

### 5.3 Telegram 연계 예시

**운동 직후 자동 메시지:**
```
🏃‍♂️ 인터벌 세션 완료! 수고했어요.

📊 세션 분석:
- 거리: 10.2km | 시간: 52:34
- 평균 심박: 168bpm (Zone 4: 62%)
- Training Effect: 유산소 4.2 / 무산소 3.1
- TSS: 85

🍽️ 회복 영양 권장:
지금부터 30분 이내에 아래 중 하나를 섭취하세요:
- 🥛 초코우유 500ml + 바나나
- 🥤 프로틴 쉐이크 + 탄수화물 소스
- 🍚 밥 한 공기 + 단백질 반찬

> 오늘은 하드 세션이었으므로 탄수화물 6-8g/kg
> (당신의 체중 기준: 420-560g) 목표로 섭취하세요.

[👍 먹었어요] [⏰ 나중에 먹을게요] [📝 뭘 먹었는지 기록]
```

**"뭘 먹었는지 기록" 선택 시:**
```
📝 식사 기록

사진을 보내주시거나, 텍스트로 입력해주세요.
예: "닭가슴살 200g, 밥 한 공기, 샐러드"

💡 사진을 보내시면 AI가 대략적인 매크로를 추정합니다.
```

### 5.4 수분 섭취 가이드

```python
# garmin_coach/nutrition/hydration.py

class HydrationGuide:
    """
    운동 전후 수분 섭취 가이드.
    환경 온도, 운동 강도, 땀 손실량 기반.
    """

    @staticmethod
    def calculate_sweat_rate(
        pre_weight_kg: float,
        post_weight_kg: float,
        fluid_consumed_ml: float,
        duration_hours: float,
    ) -> float:
        """땀 손실률 계산 (ml/hour)"""
        weight_loss_ml = (pre_weight_kg - post_weight_kg) * 1000
        return (weight_loss_ml + fluid_consumed_ml) / duration_hours

    GENERAL_GUIDELINES = {
        "pre_workout": "운동 2-3시간 전 500ml, 직전 200-300ml",
        "during": "15-20분마다 150-250ml (땀 손실률에 따라 조정)",
        "post": "체중 손실 1kg당 1.5L (과보상 계수)",
        "electrolytes": "60분 이상 또는 고온 환경 시 나트륨 보충 (500-1000mg/L)",
    }
```

---

## 6. 피드백 루프 시스템

### 6.1 설계 원칙

```
코칭 제공 → 운동 실행 → 데이터 수집 → 피드백 수집 → 코칭 개선
     ↑                                              |
     └──────────────────────────────────────────────┘
```

**핵심**: 데이터(객관) + 피드백(주관)을 모두 수집해야 진짜 개인화가 됨.

### 6.2 자동 피드백 수집 (운동 직후)

```
garmin_coach/feedback/
├── collector.py        # 피드백 수집 오케스트레이터
├── auto_analysis.py    # Garmin 데이터 자동 분석
├── subjective.py       # 주관적 피드백 수집
├── photo_analyzer.py   # 사진 기반 분석 (운동 캡쳐, 식단 사진)
└── aggregator.py       # 피드백 종합 → 코칭 모델 업데이트
```

#### 트리거 조건
Garmin에서 새 activity가 감지되면 (폴링 또는 웹훅) 자동으로 시작:

```python
# garmin_coach/feedback/collector.py

class FeedbackCollector:
    """운동 완료 감지 → 자동 분석 + 주관적 피드백 수집"""

    async def on_activity_detected(self, activity: Activity):
        # 1. 자동 분석 (즉시)
        analysis = await self.auto_analyzer.analyze(activity)

        # 2. Telegram으로 분석 결과 + 피드백 요청 전송
        await self.telegram.send_post_workout_summary(
            analysis=analysis,
            feedback_request=self._build_feedback_request(activity),
        )

    def _build_feedback_request(self, activity: Activity) -> FeedbackRequest:
        """운동 타입에 따라 적절한 피드백 질문 생성"""
        questions = [
            # 항상 묻는 질문
            RPEQuestion(),          # 체감 강도 1-10
            FeelingQuestion(),      # 기분 😀😐😫

            # 조건부 질문
            *self._conditional_questions(activity),
        ]
        return FeedbackRequest(questions=questions)

    def _conditional_questions(self, activity: Activity) -> list:
        questions = []

        # 인터벌/템포 세션 후
        if activity.type in ("interval", "tempo"):
            questions.append(CompletionQuestion())  # 세트 완료 여부
            questions.append(PaceQuestion())        # 목표 페이스 달성 여부

        # 장거리 세션 후
        if activity.duration_minutes > 90:
            questions.append(NutritionQuestion())   # 보급 잘 했는지
            questions.append(GIQuestion())          # 위장 문제

        # 부상 복귀 중
        if self.user.medical and self.user.medical.current_injuries:
            questions.append(PainQuestion())         # 통증 발생 여부

        return questions
```

#### 주관적 피드백 Telegram 플로우

```
📋 오늘 운동은 어땠어요?

1️⃣ 체감 강도 (RPE):
[1-2 매우 쉬움] [3-4 쉬움] [5-6 보통] [7-8 힘듦] [9-10 극한]

2️⃣ 전체적인 느낌:
[😀 좋았어요] [😐 보통] [😫 힘들었어요] [🤕 어딘가 아파요]

3️⃣ 특이사항이 있으면 말씀해주세요:
(자유 입력 또는 생략 가능)
```

**🤕 선택 시 추가:**
```
⚠️ 어디가 불편한가요?

부위: [무릎] [발목] [아킬레스] [허리] [햄스트링] [기타: ___]
정도: [약간 불편] [꽤 아픔] [많이 아픔]

💡 통증이 2일 이상 지속되면 전문의 상담을 권합니다.
   다음 세션은 해당 부위에 부담이 가지 않는 운동으로 조정됩니다.
```

### 6.3 사진/캡쳐 기반 피드백

```python
# garmin_coach/feedback/photo_analyzer.py

class PhotoAnalyzer:
    """
    사용자가 보내는 사진을 분석하여 피드백에 반영.
    Vision LLM (GPT-4V / Claude Vision) 활용.
    """

    SUPPORTED_TYPES = {
        "workout_screenshot": "가민/스트라바 앱 캡쳐 → 세션 데이터 보충",
        "food_photo": "식단 사진 → 매크로 대략 추정",
        "injury_photo": "부상 부위 사진 → (주의: 의학적 진단 불가, 기록 목적만)",
        "body_progress": "체형 변화 사진 → 장기 트래킹",
    }

    async def analyze(self, photo: bytes, context: str) -> PhotoAnalysis:
        """
        사진 + 맥락을 Vision LLM에 전달하여 구조화된 분석 반환.

        식단 사진 예시 응답:
        {
            "type": "food_photo",
            "estimated_macros": {
                "calories": 650,
                "protein_g": 35,
                "carbs_g": 80,
                "fat_g": 18,
                "confidence": "medium"
            },
            "items_detected": ["grilled chicken", "rice", "salad"],
            "coaching_note": "운동 후 회복식으로 좋은 구성입니다. 단백질 충분."
        }
        """
        ...
```

**Telegram 플로우:**
```
📸 [사용자가 가민 앱 캡쳐 전송]

🔍 분석 중...

📊 캡쳐 분석 결과:
- 운동: 인터벌 러닝 8x800m
- 평균 랩 페이스: 3:28/km
- 회복 랩: 2:00 조깅
- 평균 심박: 172bpm

💬 이전 인터벌 세션(3/28) 대비:
- 랩 페이스 3초/km 향상 ✅
- 심박은 비슷 → 같은 강도에서 더 빨라짐!
- 마지막 2랩에서 페이스 드랍 있음 → 다음엔 처음 2랩을 보수적으로

[📝 RPE 입력] [💬 코멘트 추가] [👍 확인]
```

### 6.4 피드백 활용 (코칭 개선)

```python
# garmin_coach/feedback/aggregator.py

class FeedbackAggregator:
    """
    수집된 피드백을 코칭 모델에 반영.
    """

    def update_coaching_model(self, feedback: SessionFeedback):
        """
        피드백 기반 조정 로직:

        1. RPE vs Actual Intensity 괴리 분석
           - RPE 8인데 Zone 2였다면 → 컨디션 저하 또는 오버트레이닝 신호
           - RPE 4인데 Zone 4였다면 → 피트니스 향상 반영

        2. 통증 피드백 → 안전 가드레일 업데이트
           - 같은 부위 통증 2회 연속 → 해당 부위 관련 운동 자동 제한

        3. 목표 페이스 달성률 트래킹
           - 최근 5회 인터벌 중 4회 이상 달성 → 목표 페이스 상향

        4. 영양 피드백 → 영양 코칭 조정
           - GI 문제 반복 → 운동 전 식사 가이드 수정
           - 에너지 부족 반복 → 탄수화물 권장량 상향
        """
        ...
```

---

## 7. 주간/월간 리포트

### 7.1 주간 리포트 (매주 일요일 저녁 자동 발송)

```
garmin_coach/reports/
├── weekly.py           # 주간 리포트 생성
├── monthly.py          # 월간 리포트 생성
├── charts.py           # 차트/그래프 생성 (matplotlib 또는 SVG)
└── templates/
    ├── weekly_telegram.py
    └── monthly_telegram.py
```

**Telegram 주간 리포트 예시:**
```
📊 주간 트레이닝 리포트 (3/31 - 4/6)

🏃 이번 주 요약:
━━━━━━━━━━━━━━━━━━
운동 횟수: 5회 (목표: 5회 ✅)
총 거리: 48.3km (지난주: 45.1km, +7.1%)
총 시간: 4시간 22분
평균 페이스: 5:25/km

📈 트레이닝 로드:
- CTL: 52.3 → 54.1 (+1.8) ✅ 안정적 상승
- ATL: 61.2 → 58.5 (-2.7) ✅ 적절한 피로 관리
- TSB: -8.9 → -4.4 🟢 양호한 밸런스
- Ramp Rate: +3.4% ✅ (안전 범위: <5%/주)

[주간 CTL/ATL/TSB 그래프 이미지]

😴 수면 & 회복:
- 평균 수면: 7h 12m (권장: 7-9시간 ✅)
- 평균 Sleep Score: 78/100
- HRV 트렌드: 안정 (기준선 52ms, 이번 주 평균 54ms)
- Body Battery 기상 시 평균: 72/100

🍽️ 영양:
- 기록된 식사: 8/15 (53% 기록률)
- 추정 일일 단백질: 평균 1.4g/kg ✅
- 수분 섭취 알림 응답률: 60%

📝 피드백 요약:
- 평균 RPE: 6.2/10
- 통증 보고: 없음 ✅
- 목표 페이스 달성률: 3/4 인터벌 (75%)

🎯 다음 주 계획:
━━━━━━━━━━━━━━━━━━
월: 이지런 8km (Zone 2)
화: 인터벌 6x1000m @ 4:00/km (Zone 4)
수: 휴식 또는 크로스트레이닝
목: 템포런 6km @ 4:45/km (Zone 3)
금: 이지런 6km (Zone 2)
토: 장거리 18km (Zone 2, 마지막 3km 마라톤 페이스)
일: 완전 휴식

💡 코치 코멘트:
> 이번 주 훌륭했습니다! CTL이 안정적으로 상승 중이고,
> 회복 지표도 양호합니다. 다음 주에는 장거리를
> 2km 늘려봅니다. 토요일 장거리 전날 탄수화물
> 로딩(7-8g/kg)을 잊지 마세요.

[📊 상세 리포트 보기] [✏️ 다음 주 계획 수정] [👍 확인]
```

### 7.2 월간 리포트 (매월 1일 자동 발송)

주간 리포트를 종합한 장기 트렌드 분석:
- CTL/피트니스 월간 변화 그래프
- 거리/시간 월간 합산 및 전월 대비
- 수면/HRV 월간 트렌드
- 부상/통증 히스토리
- 목표 대비 진척도 (예: 대회까지 D-45, 현재 CTL 54 → 목표 65)
- 식단 기록률 및 매크로 분포 월간 평균
- 다음 달 메조사이클 계획 미리보기

---

## 8. 안전 가드레일

### 8.1 왜 MD 파일 + 코드 양쪽 다 필요한가

| | MD 규칙 파일 | 코드 가드레일 |
|--|------------|------------|
| **역할** | LLM에게 코칭 원칙/경계를 알려주는 시스템 프롬프트의 일부 | 실시간 하드 리밋. LLM 출력과 무관하게 강제 적용 |
| **예시** | "TSB가 -30 이하면 하드 세션을 절대 권장하지 마세요" | `if tsb < -30: override_to_rest()` |
| **장점** | LLM이 맥락을 이해하고 자연어 코칭에 반영 | LLM이 hallucinate해도 위험한 코칭이 사용자에게 전달되지 않음 |
| **약점** | LLM이 무시할 수 있음 (hallucination) | 규칙이 경직적, 맥락 파악 불가 |

**결론: 이중 안전장치(Defense in Depth)**
1. MD 파일로 LLM에게 가이드라인 제공 (소프트 레이어)
2. 코드로 LLM 출력을 검증/오버라이드 (하드 레이어)

### 8.2 규칙 파일: `docs/safety/coaching_guardrails.md`

이 파일은 LLM 시스템 프롬프트에 포함되어, AI가 코칭 응답 생성 시 참고하는 규칙.

```markdown
# Coaching Safety Guardrails

## 절대 규칙 (NEVER 위반)

### 1. 과훈련 방지
- TSB가 -30 이하일 때 Zone 4+ 세션을 절대 권장하지 마세요.
- 주간 볼륨 증가가 10%를 초과하지 않도록 하세요 (10% rule).
- CTL Ramp Rate가 주 5 이상이면 반드시 경고하세요.
- Monotony가 2.0 이상이면 훈련 변화를 권장하세요.

### 2. 수면/회복 기반 조정
- Sleep Score 50 이하이면 하드 세션을 이지 세션으로 변경하세요.
- HRV가 7일 기준선 대비 15% 이상 하락하면 강도를 낮추세요.
- Body Battery가 기상 시 25 이하이면 완전 휴식을 권장하세요.
- 연속 3일 이상 Sleep Score 60 이하이면 누적 수면 부채 경고하세요.

### 3. 심박 이상
- 운동 중 최대 심박이 220-나이의 105%를 초과하면 즉시 중단 권고하세요.
- 안정시 심박이 7일 평균 대비 15bpm 이상 높으면 건강 이상 가능성을 알리세요.
- 베타차단제 복용자에게는 심박 기반 Zone을 사용하지 마세요.

### 4. 부상 관련
- current_injuries가 있으면 해당 부위에 부담이 가는 운동을 절대 권장하지 마세요.
- medical_clearance가 "pending"인 사용자에게는 고강도 운동을 권장하지 마세요.
- 같은 부위 통증이 2회 연속 보고되면 해당 운동 유형을 자동 제한하세요.

### 5. 의학적 경계
- 당신은 의사가 아닙니다. 절대로 의학적 진단을 내리지 마세요.
- 비정상적 데이터 패턴 감지 시 "전문의 상담을 권합니다"로 안내하세요.
- SpO2가 90% 이하로 지속 감지되면 즉시 의료 상담 권고하세요.
- 약물 관련 조언을 절대 하지 마세요.

### 6. 영양 안전
- 극단적 칼로리 제한(BMR 이하)을 절대 권장하지 마세요.
- 알레르기로 등록된 식품을 절대 추천하지 마세요.
- 보충제 효능에 대해 의학적 주장을 하지 마세요.
- 식이장애 징후(급격한 체중 감소, 과도한 칼로리 집착)가 감지되면
  전문가 상담을 권하세요.

### 7. 환경 안전
- 기온 35°C 이상 / WBGT 28°C 이상 시 실외 고강도 운동 자제 권고.
- 기온 -15°C 이하 시 실외 운동 주의 권고.
- 미세먼지 "매우 나쁨" 시 실외 운동 자제 권고.

## 톤 & 커뮤니케이션
- 코칭은 격려적이되 정직해야 합니다.
- 휴식 권고 시 "게으른 것이 아니라 현명한 결정"이라는 프레이밍.
- 데이터와 이유를 항상 함께 제시하세요 ("HRV가 평소보다 20% 낮아서...").
- 사용자가 가드레일을 무시하고 강행하겠다고 하면, 위험을 다시 한번 안내하되
  최종 결정은 사용자에게 있음을 존중하세요.
```

### 8.3 코드 가드레일: `garmin_coach/engine/guardrails.py`

LLM 출력이 규칙을 위반하더라도 사용자에게 전달되기 전에 차단/수정하는 하드 레이어.

```python
# garmin_coach/engine/guardrails.py

from dataclasses import dataclass
from enum import Enum

class GuardrailAction(Enum):
    PASS = "pass"               # 이상 없음, 그대로 전달
    MODIFY = "modify"           # 코칭 내용 수정 후 전달
    OVERRIDE = "override"       # 완전히 다른 코칭으로 대체
    BLOCK_AND_ALERT = "block"   # 차단 + 사용자에게 경고

@dataclass
class GuardrailResult:
    action: GuardrailAction
    original_coaching: str
    modified_coaching: str | None
    reason: str
    severity: str               # "info" | "warning" | "critical"

class CoachingGuardrails:
    """
    LLM 코칭 출력을 사용자에게 전달하기 전 검증.
    모든 check는 독립적으로 실행되며, 가장 엄격한 결과가 적용됨.
    """

    def validate(
        self,
        coaching: CoachingResponse,
        user: UserProfile,
        current_metrics: HealthMetrics,
    ) -> GuardrailResult:
        """모든 가드레일 체크를 실행하고 가장 엄격한 결과 반환."""
        results = [
            self._check_overtraining(coaching, current_metrics),
            self._check_sleep_recovery(coaching, current_metrics),
            self._check_heart_rate(coaching, user, current_metrics),
            self._check_injury(coaching, user),
            self._check_medical_claims(coaching),
            self._check_nutrition_safety(coaching, user),
            self._check_ramp_rate(coaching, current_metrics),
        ]
        return self._most_severe(results)

    def _check_overtraining(
        self,
        coaching: CoachingResponse,
        metrics: HealthMetrics,
    ) -> GuardrailResult:
        """
        하드 리밋:
        - TSB < -30 → Zone 4+ 세션 차단
        - Ramp Rate > 5/week → 경고
        - 주간 볼륨 증가 > 10% → 경고
        """
        if metrics.tsb < -30 and coaching.max_zone >= 4:
            return GuardrailResult(
                action=GuardrailAction.OVERRIDE,
                original_coaching=coaching.text,
                modified_coaching=self._generate_rest_coaching(metrics),
                reason=f"TSB={metrics.tsb:.1f} (< -30). 과훈련 위험으로 하드 세션 차단.",
                severity="critical",
            )

        if metrics.ramp_rate > 5.0:
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                original_coaching=coaching.text,
                modified_coaching=coaching.text + self._ramp_rate_warning(metrics),
                reason=f"Ramp Rate={metrics.ramp_rate:.1f} (> 5.0/주). 과부하 경고 추가.",
                severity="warning",
            )

        return GuardrailResult(action=GuardrailAction.PASS, ...)

    def _check_sleep_recovery(
        self,
        coaching: CoachingResponse,
        metrics: HealthMetrics,
    ) -> GuardrailResult:
        """
        - Sleep Score < 50 → 하드 세션 → 이지 세션으로 변경
        - HRV 기준선 대비 -15% 이상 → 강도 하향
        - Body Battery < 25 (기상 시) → 완전 휴식
        """
        if metrics.body_battery_morning < 25:
            return GuardrailResult(
                action=GuardrailAction.OVERRIDE,
                original_coaching=coaching.text,
                modified_coaching=self._generate_full_rest(metrics),
                reason=f"Body Battery={metrics.body_battery_morning} (< 25). 완전 휴식 강제.",
                severity="critical",
            )

        if metrics.sleep_score < 50 and coaching.intensity in ("hard", "interval", "tempo"):
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                original_coaching=coaching.text,
                modified_coaching=self._downgrade_to_easy(coaching, metrics),
                reason=f"Sleep Score={metrics.sleep_score} (< 50). 강도 하향 조정.",
                severity="warning",
            )

        if metrics.hrv_deviation_pct < -15 and coaching.intensity in ("hard", "interval", "tempo"):
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                original_coaching=coaching.text,
                modified_coaching=self._downgrade_to_easy(coaching, metrics),
                reason=f"HRV 기준선 대비 {metrics.hrv_deviation_pct:.0f}%. 강도 하향.",
                severity="warning",
            )

        return GuardrailResult(action=GuardrailAction.PASS, ...)

    def _check_heart_rate(
        self,
        coaching: CoachingResponse,
        user: UserProfile,
        metrics: HealthMetrics,
    ) -> GuardrailResult:
        """
        - 최대 심박 105% 초과 → 경고
        - RHR 기준선 +15bpm → 건강 이상 가능성 알림
        - 베타차단제 복용자 → HR 기반 Zone 비활성화
        """
        if user.medical and user.medical.beta_blocker:
            if coaching.uses_hr_zones:
                return GuardrailResult(
                    action=GuardrailAction.MODIFY,
                    original_coaching=coaching.text,
                    modified_coaching=self._convert_to_rpe_based(coaching),
                    reason="베타차단제 복용자. HR Zone → RPE 기반으로 전환.",
                    severity="info",
                )

        estimated_max_hr = 220 - user.age
        if metrics.rhr_today - metrics.rhr_baseline > 15:
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                original_coaching=coaching.text,
                modified_coaching=self._add_rhr_alert(coaching, metrics),
                reason=f"RHR {metrics.rhr_today}bpm (기준선 {metrics.rhr_baseline}bpm 대비 +{metrics.rhr_today - metrics.rhr_baseline}). 건강 이상 가능성.",
                severity="warning",
            )

        return GuardrailResult(action=GuardrailAction.PASS, ...)

    def _check_injury(
        self,
        coaching: CoachingResponse,
        user: UserProfile,
    ) -> GuardrailResult:
        """
        - 현재 부상 부위 관련 운동 차단
        - 의료 허가 pending → 고강도 차단
        - 연속 통증 보고 → 해당 운동 유형 자동 제한
        """
        if not user.medical or not user.medical.current_injuries:
            return GuardrailResult(action=GuardrailAction.PASS, ...)

        for injury in user.medical.current_injuries:
            if injury.medical_clearance == "pending":
                if coaching.intensity in ("hard", "interval", "tempo", "race"):
                    return GuardrailResult(
                        action=GuardrailAction.OVERRIDE,
                        original_coaching=coaching.text,
                        modified_coaching=self._generate_pending_clearance_coaching(injury),
                        reason=f"부상 부위 '{injury.body_part}' 의료 허가 대기 중. 고강도 차단.",
                        severity="critical",
                    )

            for restriction in injury.restrictions:
                if self._coaching_violates_restriction(coaching, restriction):
                    return GuardrailResult(
                        action=GuardrailAction.MODIFY,
                        original_coaching=coaching.text,
                        modified_coaching=self._apply_restriction(coaching, restriction),
                        reason=f"부상 제한사항 '{restriction}' 위반. 조정 적용.",
                        severity="warning",
                    )

        return GuardrailResult(action=GuardrailAction.PASS, ...)

    def _check_nutrition_safety(
        self,
        coaching: CoachingResponse,
        user: UserProfile,
    ) -> GuardrailResult:
        """
        - 알레르기 식품 추천 차단
        - BMR 이하 칼로리 제한 차단
        - 보충제 의학적 주장 차단
        """
        if user.nutrition and user.nutrition.allergies:
            for allergen in user.nutrition.allergies:
                if allergen.lower() in coaching.text.lower():
                    return GuardrailResult(
                        action=GuardrailAction.MODIFY,
                        original_coaching=coaching.text,
                        modified_coaching=self._remove_allergen(coaching, allergen),
                        reason=f"알레르기 식품 '{allergen}' 감지. 제거.",
                        severity="warning",
                    )

        return GuardrailResult(action=GuardrailAction.PASS, ...)

    def _check_medical_claims(
        self,
        coaching: CoachingResponse,
    ) -> GuardrailResult:
        """
        LLM이 의학적 진단/치료 조언을 하지 않도록 필터링.
        키워드 기반 + LLM 재검증 이중 체크.
        """
        MEDICAL_CLAIM_PATTERNS = [
            r"진단[을를]?\s*내",
            r"(?:이것은|아마도)\s*[가-힣]+(?:증|병|질환)",
            r"약[을를]?\s*(?:먹|복용|처방)",
            r"치료[를]?\s*(?:해야|받아야|권합니다)",
        ]
        ...
```

### 8.4 가드레일 파이프라인

```
사용자 데이터 수집
       ↓
Readiness Score 계산
       ↓
LLM 코칭 생성 (시스템 프롬프트에 coaching_guardrails.md 포함)
       ↓
CoachingGuardrails.validate() ← 하드 레이어
       ↓
  ┌─ PASS → 그대로 전달
  ├─ MODIFY → 수정 후 전달 + 사유 로깅
  ├─ OVERRIDE → 완전 대체 + 사용자에게 사유 설명
  └─ BLOCK → 차단 + 경고 메시지
       ↓
사용자에게 Telegram 전달
```

---

## 9. Telegram Bot UX

### 9.1 핵심 플로우

#### 아침 브리핑 (매일 기상 감지 또는 설정 시간)
```
☀️ 좋은 아침이에요! 오늘의 컨디션 브리핑:

🔋 Readiness Score: 82/100 🟢
- 수면: 7h 35m (Score: 85) ✅
- HRV: 56ms (기준선 52ms, +7.7%) ✅
- Body Battery: 78 ✅
- RHR: 48bpm (기준선 49) ✅
- TSB: -5.2 🟢

🏃 오늘 계획: 인터벌 6x1000m @ 4:00/km
→ 컨디션이 좋으니 계획대로 진행! 화이팅 💪

🍽️ 운동 전 식사 리마인더:
운동 2시간 전까지 탄수화물 위주 가벼운 식사 권장
(예: 바나나 + 토스트 + 꿀)

[✅ 계획대로] [🔄 변경] [⏭️ 내일로 미루기]
```

#### 운동 감지 → 자동 분석 (위 섹션 6 참고)

#### 저녁 체크인 (선택적, 설정 가능)
```
🌙 오늘 하루 수고했어요!

📊 오늘 요약:
- 운동: 인터벌 6x1000m ✅ (목표 달성!)
- 활동 칼로리: 620kcal
- 걸음: 12,340보
- 스트레스: 평균 32 (낮음 ✅)

🍽️ 오늘 식사 기록하셨나요?
[📝 기록하기] [⏭️ 건너뛰기]

😴 내일 아침 인터벌 대비:
취침 시간을 22:30 이전으로 권장합니다.
```

### 9.2 명령어 체계

| 명령어 | 설명 |
|--------|------|
| `/start` | 온보딩 시작 |
| `/today` | 오늘의 컨디션 + 계획 |
| `/week` | 이번 주 계획 보기 |
| `/report` | 즉시 주간 리포트 생성 |
| `/feedback` | 수동 피드백 입력 |
| `/nutrition` | 오늘의 영양 가이드 |
| `/settings` | 프로필/설정 수정 |
| `/goals` | 목표 확인/수정 |
| `/injury` | 부상 보고 |
| `/help` | 도움말 |

### 9.3 사진 처리
- 사진 전송 시 자동으로 타입 감지 (운동 캡쳐 / 식단 사진)
- 감지 실패 시: `[📊 운동 캡쳐] [🍽️ 식단 사진] [📸 기타]` 선택지 제공

---

## 10. 기술 아키텍처 (업데이트)

### 10.1 핵심 설계 원칙: 인터페이스 분리

현재는 Telegram에 집중하지만, 향후 카카오톡/WhatsApp/웹/앱 확장 시
코어 로직을 다시 짜지 않도록 **3-Layer 구조**를 유지한다.

```
┌─────────────────────────────────────────────────┐
│  Interface Layer (채널별 어댑터)                    │
│  telegram/ | cli.py | mcp_server/ | (future: app) │
└────────────────────┬────────────────────────────┘
                     │ CoachingPort (추상 인터페이스)
┌────────────────────▼────────────────────────────┐
│  Flow Layer (비즈니스 플로우, 채널 무관)              │
│  flows/onboarding.py | flows/post_workout.py     │
│  flows/morning_briefing.py | flows/feedback.py   │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  Core Layer (엔진, 채널 무관)                       │
│  engine/ | nutrition/ | feedback/ | reports/      │
└──────────────────────────────────────────────────┘
```

#### CoachingPort (추상 인터페이스)

```python
# garmin_coach/ports.py

from abc import ABC, abstractmethod

class CoachingPort(ABC):
    """
    모든 채널(Telegram, CLI, 웹, 앱)이 구현하는 인터페이스.
    Flow Layer는 이 포트만 바라보고, 채널 구현을 모른다.
    """

    @abstractmethod
    async def send_message(self, user_id: str, text: str, buttons: list[Button] | None = None) -> None:
        """텍스트 메시지 전송. 버튼이 있으면 선택지 포함."""

    @abstractmethod
    async def send_image(self, user_id: str, image: bytes, caption: str | None = None) -> None:
        """이미지 전송 (차트, 리포트 등)."""

    @abstractmethod
    async def request_input(self, user_id: str, prompt: str, input_type: InputType) -> str:
        """사용자 입력 요청. InputType: text, number, date, select, multi_select, photo."""

    @abstractmethod
    async def send_report(self, user_id: str, report: Report) -> None:
        """구조화된 리포트 전송. 채널별로 렌더링 방식이 다름."""
```

#### Flow Layer 예시

```python
# garmin_coach/flows/post_workout.py

class PostWorkoutFlow:
    """
    운동 후 플로우. Telegram이든 앱이든 동일한 로직.
    """
    def __init__(self, port: CoachingPort, engine: CoachingEngine):
        self.port = port
        self.engine = engine

    async def execute(self, user_id: str, activity: Activity):
        # 1. 자동 분석 (Core Layer)
        analysis = self.engine.analyze_activity(activity)
        nutrition = self.engine.get_post_workout_nutrition(activity)

        # 2. 결과 전송 (Interface Layer가 처리)
        await self.port.send_message(user_id, self._format_analysis(analysis, nutrition))

        # 3. 피드백 수집
        rpe = await self.port.request_input(user_id, "체감 강도 (1-10)?", InputType.SELECT)
        feeling = await self.port.request_input(user_id, "전체적인 느낌?", InputType.SELECT)

        # 4. 피드백 반영 (Core Layer)
        self.engine.process_feedback(user_id, activity, rpe, feeling)
```

> **현재 Phase에서는**: `TelegramAdapter(CoachingPort)`만 구현.
> `flows/` 폴더의 로직은 Telegram import가 하나도 없어야 함.
> 나중에 앱 개발 시 `AppAdapter(CoachingPort)`만 추가하면 됨.

### 10.2 디렉토리 구조

```
garmin_coach/
├── ports.py                    # CoachingPort 추상 인터페이스 🔲 신규
│
├── adapters/
│   ├── garmin/
│   │   ├── activity.py         # 운동 데이터 ✅
│   │   ├── health.py           # 수면/HRV/BB/Stress 🔲 신규
│   │   └── auth.py             # 인증 ✅
│   ├── strava/                 # Strava 보조 ✅
│   └── nike/                   # scaffold, 로드맵
│
├── engine/
│   ├── readiness.py            # Readiness Score 🔲 신규
│   ├── coaching.py             # AI 코칭 코어 ✅ 확장 필요
│   ├── guardrails.py           # 안전 가드레일 🔲 신규
│   ├── training_plan.py        # 주간 계획 생성 🔲 신규
│   └── rules.py                # Rule-based fallback ✅ 확장 필요
│
├── flows/                      # 비즈니스 플로우 (채널 무관) 🔲 신규
│   ├── onboarding.py           # 온보딩 3단계 플로우
│   ├── post_workout.py         # 운동 후 분석 + 피드백
│   ├── morning_briefing.py     # 아침 컨디션 브리핑
│   ├── evening_checkin.py      # 저녁 체크인
│   ├── nutrition_log.py        # 식단 기록 플로우
│   └── injury_report.py        # 부상 보고 플로우
│
├── feedback/
│   ├── collector.py            # 피드백 수집 오케스트레이터 🔲 신규
│   ├── auto_analysis.py        # 자동 분석 🔲 신규
│   ├── subjective.py           # 주관적 피드백 🔲 신규
│   ├── photo_analyzer.py       # 사진 분석 🔲 신규
│   └── aggregator.py           # 피드백 종합 🔲 신규
│
├── integrations/
│   ├── training_load.py        # CTL/ATL/TSB ✅
│   └── sync.py                 # 데이터 싱크 ✅
│
├── nutrition/
│   ├── engine.py               # 영양 코칭 코어 🔲 확장
│   ├── macros.py               # 매크로 계산 🔲 신규
│   ├── timing.py               # 운동 전후 타이밍 🔲 신규
│   ├── hydration.py            # 수분 섭취 🔲 신규
│   └── recovery_fuel.py        # 회복 영양 🔲 신규
│
├── reports/
│   ├── weekly.py               # 주간 리포트 🔲 신규
│   ├── monthly.py              # 월간 리포트 🔲 신규
│   └── charts.py               # 시각화 🔲 신규
│
├── wizard/
│   ├── onboarding.py           # 온보딩 데이터 수집 로직 🔲 확장
│   └── settings.py             # 설정 변경 🔲 신규
│
├── models/
│   ├── user_profile.py         # 사용자 프로필 🔲 신규
│   ├── health_metrics.py       # 건강 메트릭 🔲 신규
│   └── feedback.py             # 피드백 모델 🔲 신규
│
├── interfaces/
│   ├── telegram/               # Telegram 어댑터 (현재 메인) ✅ 대폭 확장
│   │   ├── adapter.py          # TelegramAdapter(CoachingPort)
│   │   ├── keyboards.py        # 인라인 키보드 헬퍼
│   │   ├── handlers.py         # 명령어/콜백 핸들러
│   │   └── renderer.py         # 메시지 포매팅 (마크다운 등)
│   └── cli.py                  # CLI (개발용) ✅
│
├── docs/
│   └── safety/
│       └── coaching_guardrails.md  # 안전 규칙 🔲 신규
│
└── mcp_server/                 # MCP 서버 ✅
    ├── server.py
    └── entrypoint.py
```

> **규칙**: `flows/` 폴더의 어떤 파일도 `interfaces/telegram/`을 import하면 안 됨.
> 이 규칙만 지키면 나중에 앱/웹 채널을 붙일 때 `flows/`는 건드릴 필요 없음.

---

## 11. 개발 로드맵

### Phase 1: Foundation (Week 1-3)
> 핵심 데이터 파이프라인 + 안전 가드레일

- [ ] `adapters/garmin/health.py` — 수면/HRV/BB/Stress/RHR 데이터 수집
- [ ] `engine/readiness.py` — Readiness Score 계산
- [ ] `engine/guardrails.py` — 코드 가드레일 구현
- [ ] `docs/safety/coaching_guardrails.md` — 규칙 파일 작성
- [ ] `models/` — 데이터 모델 전체 정의
- [ ] 기존 `training_load.py`에 Ramp Rate, Monotony, Strain 추가

### Phase 2: Onboarding & Profile (Week 3-4)
> 사용자 프로필 시스템 + 온보딩

- [ ] `wizard/onboarding.py` — 3단계 온보딩 플로우
- [ ] `wizard/settings.py` — 설정 변경 UI
- [ ] `models/user_profile.py` — 전체 프로필 모델
- [ ] Telegram 인라인 키보드 온보딩 구현

### Phase 3: Nutrition (Week 4-6)
> 운동-영양 연계 코칭

- [ ] `nutrition/macros.py` — Periodized Nutrition 로직
- [ ] `nutrition/timing.py` — 운동 전/중/후 타이밍
- [ ] `nutrition/hydration.py` — 수분 섭취 가이드
- [ ] `nutrition/recovery_fuel.py` — 회복 영양
- [ ] Telegram 영양 알림/기록 플로우

### Phase 4: Feedback Loop (Week 6-8)
> 피드백 수집 + 코칭 개선 사이클

- [ ] `feedback/collector.py` — 운동 감지 → 자동 피드백 요청
- [ ] `feedback/subjective.py` — RPE/느낌/통증 수집
- [ ] `feedback/photo_analyzer.py` — 사진 분석 (Vision LLM)
- [ ] `feedback/aggregator.py` — 피드백 → 코칭 모델 업데이트
- [ ] Telegram 자동 post-workout 플로우

### Phase 5: Reports & Polish (Week 8-10)
> 리포트 + UX 다듬기

- [ ] `reports/weekly.py` — 주간 리포트 생성
- [ ] `reports/monthly.py` — 월간 리포트 생성
- [ ] `reports/charts.py` — 시각화 (SVG/이미지)
- [ ] 아침 브리핑 / 저녁 체크인 자동화
- [ ] 명령어 체계 전체 구현
- [ ] 에러 핸들링 / 엣지 케이스 처리

### Phase 6: Roadmap
> 향후 확장

- [ ] 카카오톡 / WhatsApp 채널
- [ ] 웹 대시보드
- [ ] Nike Run Club 연동 (API 상황에 따라)
- [ ] Apple Health / Google Fit 연동
- [ ] 크로스트레이닝 (수영, 웨이트) 전용 코칭
- [ ] 레이스 예측 모델 (VO2max + 훈련 데이터 기반)
- [ ] 다국어 지원 (한국어/영어)
- [ ] 커뮤니티 기능 (익명 벤치마크)

---

## 12. 성공 지표

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 온보딩 완료율 | Phase 1 > 90%, Phase 2 > 60% | 온보딩 단계별 완료 트래킹 |
| 일일 활성 사용률 | > 70% | 아침 브리핑 확인율 |
| 피드백 응답률 | > 60% | 운동 후 피드백 요청 대비 응답 |
| 식단 기록률 | > 40% | 일일 식단 기록 횟수 |
| 가드레일 발동률 | < 10% of 코칭 | 가드레일 override/modify 비율 |
| 코칭 만족도 | > 4.0/5.0 | 월간 NPS 서베이 |
| 부상 발생률 | 사용 전 대비 감소 | 통증 보고 빈도 트렌드 |
| 목표 달성률 | > 50% | 대회 목표 시간 달성 비율 |
