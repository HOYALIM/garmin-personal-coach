"""Garmin Connect client facade backed by garminconnect.

garth is deprecated (Garmin's 2026 TLS-fingerprinting/Cloudflare changes
broke its mobile auth). This module presents the small garth-like surface
the rest of the codebase relies on — ``resume()`` / ``login()`` / ``save()``
/ ``connectapi()`` plus named ``get_*`` data methods — while delegating to
``garminconnect.Garmin``, which ships its own working auth engine.

Clients are cached per token-store directory so per-user scoped homes
(e.g. telegram_bot's ``_scoped_garth_home``) map to independent sessions.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Callable, Optional

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
)

TOKEN_FILE_NAME = "garmin_tokens.json"


def default_token_dir() -> str:
    return os.path.expanduser(
        os.getenv("GARMINTOKENS") or os.getenv("GARTH_HOME") or "~/.garminconnect"
    )

# garth method names still used by callers → garminconnect equivalents.
_METHOD_ALIASES = {
    "get_resting_heart_rate": "get_rhr_day",
}


class GarminClientFacade:
    """garth-compatible stateful facade over garminconnect sessions.

    Mirrors garth's module-global usage pattern (``resume(home)`` followed by
    ``connectapi(...)``/typed getters) so existing call sites and test
    monkeypatches keep working unchanged.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[str, Garmin] = {}
        self._active: Optional[Garmin] = None

    # -- session management (garth-compatible names) ---------------------

    def resume(self, token_dir: str) -> Garmin:
        """Restore a session from ``token_dir``; raises if no valid tokens."""
        key = os.path.expanduser(token_dir)
        with self._lock:
            client = self._clients.get(key)
        if client is None:
            client = Garmin()
            needs_mfa, _ = client.login(key)
            if needs_mfa:
                raise GarminConnectAuthenticationError(
                    "Stored Garmin session requires MFA re-login"
                )
            with self._lock:
                self._clients[key] = client
        self._active = client
        return client

    def login(
        self,
        email: str,
        password: str,
        prompt_mfa: Callable[[], str] | None = None,
    ) -> Garmin:
        """Fresh credential login (MFA via ``prompt_mfa`` callback)."""
        client = Garmin(email=email, password=password, prompt_mfa=prompt_mfa)
        client.login()
        self._active = client
        return client

    def save(self, token_dir: str) -> None:
        """Persist the active session; future token refreshes auto-persist."""
        if self._active is None:
            raise GarminConnectAuthenticationError("No active Garmin session to save")
        key = os.path.expanduser(token_dir)
        self._active.client.dump(key)
        with self._lock:
            self._clients[key] = self._active

    def logout(self, token_dir: str | None = None) -> None:
        if token_dir is not None:
            key = os.path.expanduser(token_dir)
            with self._lock:
                client = self._clients.pop(key, None)
            if client is self._active:
                self._active = None
            if client is not None:
                client.logout(key)
        else:
            self._active = None

    # -- data access ------------------------------------------------------

    def connectapi(self, path: str, **kwargs: Any) -> Any:
        return self._require_active().connectapi(path, **kwargs)

    def _require_active(self) -> Garmin:
        if self._active is None:
            raise GarminConnectAuthenticationError(
                "No Garmin session. Call resume() or login() first."
            )
        return self._active

    def __getattr__(self, name: str) -> Any:
        # Delegate get_* data methods to the active garminconnect client.
        target = _METHOD_ALIASES.get(name, name)
        client = self.__dict__.get("_active")
        if client is not None and hasattr(client, target):
            return getattr(client, target)
        raise AttributeError(name)


garmin_client = GarminClientFacade()

__all__ = [
    "Garmin",
    "GarminClientFacade",
    "GarminConnectAuthenticationError",
    "TOKEN_FILE_NAME",
    "garmin_client",
]
