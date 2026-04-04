# Garmin Personal Coach

**Idiomas:** [English](README.md) | [한국어](README.ko.md) | Español | [日本語](README.ja.md)

Garmin Personal Coach es un motor de coaching AI con enfoque Garmin-first.

Interfaces disponibles hoy:

- CLI
- Telegram
- MCP / OpenClaw

No incluye todavía dashboard web, app móvil ni análisis de calorías por foto.

## Funciona hoy

- Integración con Garmin Connect como fuente principal
- Sync suplementario con Strava
- Coaching con CTL / ATL / TSB
- AI opcional con OpenAI / Anthropic / Gemini
- Coaching nutricional ligero y personalizado

## Inicio rápido

```bash
pip install garmin-personal-coach[all]
garth login your@email.com
garmin-coach setup
```

Strava opcional:

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

## No incluido en este release

- Dashboard web
- iMessage
- Nike Run Club
- Apple HealthKit / Apple Watch
- Cálculo de calorías por foto

## Nutrition coaching actual

La versión actual ofrece orientación ligera basada en:

- carga de entrenamiento / fatiga
- objetivo de peso
- estilo alimentario
- restricciones alimentarias
- estilo preferido de coaching

Es una capa de guía, no una app completa de tracking nutricional.
