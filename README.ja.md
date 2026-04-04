# Garmin Personal Coach

**言語:** [English](README.md) | [한국어](README.ko.md) | [Español](README.es.md) | 日本語

Garmin Personal Coach は Garmin-first の AI コーチングエンジンです。

現在使えるインターフェース:

- CLI
- Telegram
- MCP / OpenClaw

現時点では、Web ダッシュボード、モバイルアプリ、写真ベースのカロリー推定は含まれていません。

## 現在できること

- Garmin Connect 連携（主要データソース）
- Strava 補助 sync
- CTL / ATL / TSB ベースのコーチング
- OpenAI / Anthropic / Gemini による任意の AI 強化
- 軽量な個別化 nutrition coaching

## クイックスタート

```bash
pip install garmin-personal-coach[all]
garth login your@email.com
garmin-coach setup
```

Strava を追加する場合:

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

## 現在のリリースに含まれないもの

- Web ダッシュボード
- iMessage
- Nike Run Club
- Apple HealthKit / Apple Watch
- 写真からのカロリー推定

## 現在の nutrition coaching

現在のリリースでは、次をもとに軽量な栄養アドバイスを提供します:

- training load / fatigue
- 体重目標
- 食事スタイル
- 食事制限
- コーチングスタイルの好み

これはガイダンス用であり、本格的な食事記録アプリではありません。
