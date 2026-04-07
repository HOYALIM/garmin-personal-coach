from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


SENSITIVE_KEYS = {
    "password",
    "access_token",
    "refresh_token",
    "token",
    "client_secret",
    "authorization",
}


def ensure_secure_directory(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def redact_sensitive_fields(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    return _redact_value(payload)


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            lowered = key.lower()
            if lowered in SENSITIVE_KEYS or any(
                token in lowered for token in ("password", "token", "secret")
            ):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = _redact_value(nested)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def validate_auth_input(credentials: Mapping[str, Any] | None) -> tuple[str | None, str | None]:
    if not credentials:
        return None, None
    email = credentials.get("email") or credentials.get("username")
    password = credentials.get("password")
    return (str(email) if email else None, str(password) if password else None)


def validate_token_store(garth_module: Any, garth_home: str) -> bool:
    ensure_secure_directory(garth_home)
    garth_module.resume(garth_home)
    return True


def authenticate_credentials(
    garth_module: Any,
    garth_home: str,
    credentials: dict[str, Any] | None,
) -> bool:
    email, password = validate_auth_input(credentials)
    if not email or not password:
        return False
    ensure_secure_directory(garth_home)
    login = getattr(garth_module, "login", None)
    if not callable(login):
        return False
    login(email, password)
    try:
        if hasattr(garth_module, "save"):
            garth_module.save(garth_home)
    except Exception:
        pass
    return True


def token_paths(garth_home: str) -> list[Path]:
    root = Path(garth_home).expanduser()
    return [root / "oauth1_token.json", root / "oauth2_token.json", root / "session.json"]
