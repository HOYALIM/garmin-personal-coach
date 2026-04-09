# Garmin Personal Coach

**언어:** [English](README.md) | 한국어 | [Español](README.es.md) | [日本語](README.ja.md)

Garmin Personal Coach는 지구력 운동 사용자를 위한 **Garmin-first AI 코칭 엔진**입니다.

현재 다음 인터페이스로 사용할 수 있습니다.

- CLI
- Telegram
- MCP / OpenClaw

현재 릴리즈에는 **대시보드, 모바일 앱, 음식 사진 기반 칼로리 계산 기능**이 포함되지 않습니다.

---

## 현재 가능한 것

- Garmin Connect를 **기본이자 권위 있는 데이터 소스**로 사용
- Strava를 **보조 sync 소스**로 지원
- Training load(CTL / ATL / TSB) 계산
- CLI, Telegram, MCP/OpenClaw를 통한 코칭 안내
- OpenAI, Anthropic, Gemini 기반 AI 코칭(선택)
- 경량 개인화 영양 코칭

---

## 빠른 시작

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

현재 릴리즈에서 Strava는 **보조 기능**입니다. Garmin이 여전히 기본 source of truth입니다.

동기화 상태 확인:

```bash
garmin-coach oauth-status
garmin-coach strava-sync --dry-run
```

---

## 지원 인터페이스

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

---

## AI 코칭

AI 강화 응답은 선택 사항입니다.

```bash
export OPENAI_API_KEY="sk-..."
# 또는
export ANTHROPIC_API_KEY="sk-ant-..."
# 또는
export GEMINI_API_KEY="..."
```

API 키가 없어도 제품은 **rule-based coaching**으로 동작합니다.

---

## 영양 코칭

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

## 이번 릴리즈의 제품 경계

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

---

## 아키텍처 개요

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

## 설정 파일

- 메인 프로필/설정: `~/.config/garmin_coach/config.yaml`
- Strava 토큰: `~/.config/garmin_coach/strava_token.json`

---

## 릴리즈 포지셔닝

현재 릴리즈는 **로컬 / 파워유저 중심의 정직한 베타**로 이해하는 것이 맞습니다.

- Garmin-first
- CLI, Telegram, MCP/OpenClaw로 바로 사용 가능
- 더 넓은 소비자 UX 관점에서는 아직 초기 단계

---

## 라이선스

MIT
