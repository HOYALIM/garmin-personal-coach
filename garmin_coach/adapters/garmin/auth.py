from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from .client import TOKEN_FILE_NAME, garmin_client

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
    return [
        root / TOKEN_FILE_NAME,
        # Legacy garth token files, kept for cleanup of old installs.
        root / "oauth1_token.json",
        root / "oauth2_token.json",
        root / "session.json",
    ]


# ---------------------------------------------------------------------------
# Auth strategies
#
# The product roadmap swaps the unofficial SSO login for the official Garmin
# Developer Program OAuth at the public phase. Strategies keep that swap
# contained to this module.
# ---------------------------------------------------------------------------


@runtime_checkable
class GarminAuthStrategy(Protocol):
    """A way of establishing a Garmin Connect session."""

    name: str

    def resume(self, token_dir: str) -> bool:
        """Restore a previously saved session. Returns False if unavailable."""
        ...

    def login(
        self,
        credentials: Mapping[str, Any],
        token_dir: str,
        mfa_callback: Callable[[], str] | None = None,
    ) -> bool:
        """Authenticate with fresh credentials and persist tokens."""
        ...


class SSOPasswordAuth:
    """Unofficial Garmin SSO login (email/password + optional MFA).

    Backed by garminconnect's native auth engine; tokens persist to
    ``token_dir`` and auto-refresh on subsequent API calls.
    """

    name = "sso_password"

    def __init__(self, client=garmin_client):
        self._client = client

    def resume(self, token_dir: str) -> bool:
        try:
            self._client.resume(token_dir)
            return True
        except Exception:
            return False

    def login(
        self,
        credentials: Mapping[str, Any],
        token_dir: str,
        mfa_callback: Callable[[], str] | None = None,
    ) -> bool:
        email, password = validate_auth_input(credentials)
        if not email or not password:
            return False
        self._client.login(email, password, prompt_mfa=mfa_callback)
        ensure_secure_directory(os.path.expanduser(token_dir))
        self._client.save(token_dir)
        return True


def default_auth_strategy() -> GarminAuthStrategy:
    return SSOPasswordAuth()
