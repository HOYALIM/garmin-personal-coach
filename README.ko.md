# Garmin Personal Coach

**언어:** [English](README.md) | 한국어 | [Español](README.es.md) | [日本語](README.ja.md)

Garmin Personal Coach는 Garmin-first AI 코칭 엔진입니다.

현재 사용 가능한 인터페이스:

- CLI
- Telegram
- MCP / OpenClaw

현재 릴리즈에는 대시보드, 모바일 앱, 음식 사진 기반 칼로리 계산 기능은 포함되지 않습니다.

## 현재 지원

- Garmin Connect 연동 (기본/권위 있는 데이터 소스)
- Strava 보조 sync
- CTL / ATL / TSB 기반 코칭
- OpenAI / Anthropic / Gemini 기반 AI 코칭 (선택)
- 개인화된 경량 nutrition coaching

## 빠른 시작

```bash
pip install garmin-personal-coach[all]
garth login your@email.com
garmin-coach setup
```

Strava 보조 연동:

```bash
garmin-coach connect-strava
garmin-coach oauth-status
garmin-coach strava-sync --dry-run
```

Telegram:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
garmin-coach-telegram
```

MCP / OpenClaw:

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

## 현재 릴리즈에 없는 것

- Web Dashboard
- iMessage
- Nike Run Club
- Apple HealthKit / Apple Watch
- 음식 사진 업로드 기반 칼로리 계산

## 현재 릴리즈의 Nutrition Coaching

현재는 다음을 기반으로 식단 방향을 제안합니다:

- training load / fatigue
- 체중 목표
- 식단 성향
- 음식 제한
- 선호하는 코칭 스타일

이 기능은 **가이드형 코칭**이며, meal tracking 앱은 아닙니다.
