# Garmin Personal Coach

**언어:** [English](README.md) | 한국어 | [Español](README.es.md) | [日本語](README.ja.md)

> **Garmin 데이터를 읽고, 매일의 훈련 결정을 더 똑똑하게 바꿔주는 개인 코치.**

Garmin Personal Coach는 단순한 운동 기록 조회 도구가 아닙니다.  
Garmin 데이터를 기반으로 **훈련 부하, 회복 상태, 영양 가이드, 피드백 루프, 주간 리포트**를 연결해,
사용자가 매일 **무엇을 해야 하는지 / 왜 그렇게 해야 하는지**를 더 빠르게 이해하게 만드는
**Garmin-first AI 코칭 시스템**입니다.

현재 다음 인터페이스로 사용할 수 있습니다.

- CLI
- Telegram
- MCP / OpenClaw

현재 릴리즈에는 **Web 대시보드, 모바일 앱, 음식 사진 기반 칼로리 추정**은 포함되지 않습니다.

---

## What it does

지금 이 제품으로 할 수 있는 핵심은 다음과 같습니다.

- Garmin Connect를 **기본이자 권위 있는 데이터 소스**로 사용
- Strava를 **보조 sync 소스**로 연동
- Training Load 계산 (CTL / ATL / TSB)
- CLI, Telegram, MCP/OpenClaw를 통한 코칭 응답 제공
- OpenAI / Anthropic / Gemini 기반 AI 코칭 사용 가능(선택)
- 경량 개인화 영양 코칭 제공

즉, 사용자는 더 이상 Garmin 데이터를 “보기만” 하는 것이 아니라,
그 데이터를 바탕으로 **오늘의 훈련 강도, 회복 행동, 다음 계획 수정안**까지 받을 수 있습니다.

---

## Why it matters

Garmin Personal Coach가 풀고자 하는 문제는 단순합니다.

많은 러너/사이클리스트는 데이터를 꾸준히 쌓지만,
정작 중요한 순간에 이런 질문에 바로 답을 얻지 못합니다.

- 오늘 강하게 해도 되는가?
- 지금 쉬어야 하는가?
- 운동 직후 뭘 먹어야 하는가?
- 이번 주 훈련이 잘 되고 있는가?
- 다음 주 계획은 무엇이 달라져야 하는가?

이 제품은 그 질문에 대해,
**데이터 + 이유 + 행동 권고**를 같이 돌려주는 것을 목표로 합니다.

한마디로 정리하면:

> **운동 데이터를 기록하는 제품이 아니라, 운동 결정을 더 잘 내리게 해주는 제품**입니다.

---

## Quick Start

### 1. 설치

권장:

```bash
pip install garmin-personal-coach[all]
```

소스에서 설치:

```bash
git clone https://github.com/HOYALIM/garmin-personal-coach.git
cd garmin-personal-coach
pip install -e .[all]
```

### 2. Garmin 연결

```bash
garth login your@email.com
```

### 3. 초기 설정 실행

```bash
garmin-coach setup
```

### 4. (선택) Strava 연결

Strava API 앱을 만든 뒤 다음을 실행하세요.

```bash
garmin-coach connect-strava
```

동기화 상태 확인:

```bash
garmin-coach oauth-status
garmin-coach strava-sync --dry-run
```

현재 릴리즈에서 Strava는 **보조 기능**입니다. Garmin이 여전히 기본 source of truth입니다.

---

## Interfaces

### CLI

```bash
garmin-coach status
garmin-coach log
garmin-coach oauth-status
garmin-coach garmin-sync --dry-run
garmin-coach strava-sync --dry-run
garmin-coach --version
garmin-coach --check-updates
```

CLI는 로컬에서 가장 빠르게 상태를 확인하고, sync/설정/기본 코칭 동작을 점검하는 데 적합합니다.

### Telegram

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
garmin-coach-telegram
```

Telegram 봇 토큰 생성 방법:

1. Telegram에서 **@BotFather** 열기
2. 새 봇 만들기
3. 발급된 토큰 복사
4. `TELEGRAM_BOT_TOKEN` 환경 변수에 넣기

기본 명령어:

- `/start`
- `/status`
- `/plan`
- `/help`

자연어 예시:

- `오늘 컨디션 어때?`
- `운동 끝났어`
- `내일 뭐 하면 돼?`

Telegram은 현재 가장 사용자 친화적인 인터페이스입니다.  
아침 브리핑, 운동 직후 피드백, 간단한 질의응답은 Telegram이 가장 자연스럽습니다.

### MCP / OpenClaw

권장 MCP 설정:

```json
{
  "mcpServers": {
    "garmin-coach": {
      "command": "garmin-coach-mcp",
      "args": []
    }
  }
}
```

fallback 설정:

```json
{
  "mcpServers": {
    "garmin-coach": {
      "command": "python",
      "args": ["-m", "mcp_server"]
    }
  }
}
```

사용 가능한 MCP 도구:

- `get_training_status`
- `get_user_profile`
- `get_recent_activities`
- `handle_natural_language`
- `health`
- `get_training_plan`

MCP/OpenClaw는 이 제품을 **AI 워크플로우 안에서 코칭 백엔드처럼 활용**하고 싶은 사용자에게 적합합니다.

---

## AI Coaching

AI 강화 응답은 선택 사항입니다.

```bash
export OPENAI_API_KEY="sk-..."
# 또는
export ANTHROPIC_API_KEY="sk-ant-..."
# 또는
export GEMINI_API_KEY="..."
```

API 키가 없어도 제품은 **rule-based coaching**으로 동작합니다.  
즉, AI는 “필수”가 아니라 **더 자연스럽고 더 문맥적인 코칭을 위한 강화 레이어**입니다.

---

## Nutrition Coaching

현재 릴리즈는 다음 정보를 기반으로 **경량 개인화 영양 코칭**을 제공합니다.

- training load / fatigue context
- 체중 목표 (`maintain`, `lose`, `gain`)
- 식단 성향 (`omnivore`, `vegetarian`, `vegan`, `other`)
- 음식 제한 / 회피 식품
- 선호 코칭 스타일 (`brief`, `detailed`, `macros`)

현재는 **가이드형 코칭**이며, 아래 기능은 아직 포함되지 않습니다.

- 식사 기록
- 바코드 스캔
- 이미지 업로드
- 음식 사진 기반 칼로리 추정

### 향후 확장

향후 업데이트에서는 음식 사진 업로드 → 칼로리 추정 → 식단 제안으로 확장될 수 있습니다.  
하지만 이 기능은 **현재 릴리즈 범위가 아닙니다.**

---

## Product Boundaries

### 현재 포함됨

- Garmin-first coaching engine
- Strava supplemental sync
- CLI / Telegram / MCP 사용
- 경량 nutrition coaching

### 현재 포함되지 않음

- Web dashboard
- iMessage integration
- Nike Run Club integration
- Apple HealthKit / Apple Watch integration
- 완전한 meal tracking 또는 photo-calorie workflow

이 구분은 중요합니다.  
Garmin Personal Coach는 **이미 사용 가능한 베타**지만,
아직 “모든 것을 갖춘 소비자용 앱”은 아닙니다.

---

## Architecture Snapshot

```text
garmin_coach/
├── adapters/          # Garmin/Strava 데이터 접근, Nike는 scaffold만 존재
├── handler/           # 자연어 코칭 코어
├── integrations/      # Garmin / Strava sync-to-load 흐름
├── wizard/            # interactive setup
├── nutrition/         # 영양 가이드 로직
├── telegram_bot.py    # Telegram runtime
└── cli.py             # CLI entrypoint

mcp_server/
├── server.py          # MCP handlers
└── entrypoint.py      # MCP stdio entrypoint
```

---

## Configuration

- 메인 프로필/설정: `~/.config/garmin_coach/config.yaml`
- Strava 토큰: `~/.config/garmin_coach/strava_token.json`

---

## Release Positioning

현재 릴리즈는 **로컬 / 파워유저 중심의 정직한 베타**로 이해하는 것이 맞습니다.

- Garmin-first
- CLI, Telegram, MCP/OpenClaw로 바로 사용 가능
- 훈련 데이터 활용과 의사결정 보조에 강점
- 더 넓은 소비자 UX 관점에서는 아직 초기 단계

즉, 지금 이 제품은

> **운동 데이터를 저장하는 앱**이라기보다,
> **운동 결정을 더 잘 내리게 해주는 코치 베이스**에 가깝습니다.

---

## 앞으로의 브랜드 확장

이 README는 이후 다음 자산으로 확장될 수 있는 구조를 염두에 두고 작성되었습니다.

- 브랜드 로고 / 로고 락업
- Telegram / CLI / MCP 사용 예시 스크린샷
- 사용자 여정 중심의 웹 사용설명서
- PRD 기반 day-in-the-life / week-in-the-life 문서
- 릴리즈별 제품 포지셔닝 페이지

즉 지금은 README가 제품의 입구이고,
앞으로는 이 구조가 **웹 문서 / 브랜드 페이지 / 온보딩 자산**으로 확장될 수 있습니다.

---

## 라이선스

MIT
