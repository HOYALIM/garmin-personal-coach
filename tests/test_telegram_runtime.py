from garmin_coach.telegram_bot import TelegramRuntimeConfig


def test_telegram_runtime_config_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_MODE", "webhook")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://example.com")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_HOST", "127.0.0.1")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_PORT", "9443")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_PATH", "coach/hook")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret-1")

    cfg = TelegramRuntimeConfig.from_env()

    assert cfg.mode == "webhook"
    assert cfg.webhook_host == "127.0.0.1"
    assert cfg.webhook_port == 9443
    assert cfg.normalized_webhook_path() == "/coach/hook"
    assert cfg.resolved_webhook_url() == "https://example.com/coach/hook"
    cfg.validate()


def test_telegram_runtime_config_requires_webhook_url():
    cfg = TelegramRuntimeConfig(mode="webhook", webhook_url=None)

    try:
        cfg.validate()
        assert False, "expected validate() to require webhook URL"
    except ValueError as exc:
        assert "TELEGRAM_WEBHOOK_URL" in str(exc)


def test_telegram_runtime_config_requires_webhook_secret():
    cfg = TelegramRuntimeConfig(
        mode="webhook", webhook_url="https://example.com", webhook_secret=None
    )

    try:
        cfg.validate()
        assert False, "expected validate() to require webhook secret"
    except ValueError as exc:
        assert "TELEGRAM_WEBHOOK_SECRET" in str(exc)


def test_telegram_runtime_config_defaults_to_polling():
    cfg = TelegramRuntimeConfig()

    cfg.validate()
    assert cfg.mode == "polling"
    assert cfg.normalized_webhook_path() == "/telegram/webhook"
