"""Interactive Garmin Connect login (replaces the dead ``garth login`` CLI)."""

from __future__ import annotations

import getpass

from garmin_coach.adapters.garmin.auth import SSOPasswordAuth
from garmin_coach.adapters.garmin.client import default_token_dir


def _prompt_mfa() -> str:
    return input("MFA code (from your email or authenticator app): ").strip()


def setup_garmin_login(email: str | None = None, force: bool = False) -> bool:
    """Log into Garmin Connect and persist tokens for later sessions.

    Returns True when a working session exists afterwards.
    """
    token_dir = default_token_dir()
    strategy = SSOPasswordAuth()

    if not force and strategy.resume(token_dir):
        print(f"✓ Garmin session already active (tokens in {token_dir})")
        print("  Use 'garmin-coach connect-garmin --force' to log in again.")
        return True

    print("Garmin Connect login")
    print("(credentials are sent to Garmin only; tokens are stored locally)")
    email = email or input("Garmin email: ").strip()
    if not email:
        print("No email given — aborting.")
        return False
    password = getpass.getpass("Garmin password: ")
    if not password:
        print("No password given — aborting.")
        return False

    try:
        ok = strategy.login(
            {"email": email, "password": password},
            token_dir,
            mfa_callback=_prompt_mfa,
        )
    except Exception as exc:
        print(f"✗ Garmin login failed: {exc}")
        return False

    if ok:
        print(f"✓ Garmin connected! Tokens saved to {token_dir}")
    else:
        print("✗ Garmin login failed (missing credentials).")
    return ok
