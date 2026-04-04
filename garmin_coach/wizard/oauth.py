import os
import json
import secrets
import time
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs

from garmin_coach.logging_config import log_warning


CONFIG_DIR = os.path.expanduser("~/.config/garmin_coach")
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
TOKEN_REFRESH_WINDOW_SECONDS = 300
CALLBACK_TIMEOUT_SECONDS = 180


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    received_params = None

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>Authentication Successful</h1><p>You may close this window.</p></body></html>"
        )
        parsed = urlparse(self.path)
        OAuthCallbackHandler.received_params = parse_qs(parsed.query)

    def log_message(self, format, *args):
        pass


class OAuthFlow:
    @staticmethod
    def strava_auth(
        client_id: str,
        client_secret: str,
        redirect_port: int = 8080,
        scope: str = "read,activity:read",
    ) -> Optional[dict]:
        state = secrets.token_urlsafe(16)
        auth_url = f"https://www.strava.com/oauth/authorize?{
            urlencode(
                {
                    'client_id': client_id,
                    'response_type': 'code',
                    'redirect_uri': f'http://localhost:{redirect_port}/callback',
                    'scope': scope,
                    'approval_prompt': 'auto',
                    'state': state,
                }
            )
        }"

        print(f"\nOpening Strava authorization page...")
        print(f"If browser doesn't open, go to: {auth_url}\n")
        webbrowser.open(auth_url)

        server = HTTPServer(("localhost", redirect_port), OAuthCallbackHandler)
        OAuthCallbackHandler.received_params = None

        def wait_for_code():
            server.handle_request()

        thread = threading.Thread(target=wait_for_code)
        if hasattr(thread, "daemon"):
            thread.daemon = True
        thread.start()

        deadline = time.time() + CALLBACK_TIMEOUT_SECONDS
        while OAuthCallbackHandler.received_params is None and time.time() < deadline:
            time.sleep(0.5)

        if OAuthCallbackHandler.received_params is None:
            server.server_close()
            return None

        params = OAuthCallbackHandler.received_params
        returned_state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]
        code = params.get("code", [None])[0]
        accepted_scope_values = params.get("scope") or []
        accepted_scope = accepted_scope_values[0] if accepted_scope_values else ""

        server.server_close()
        if hasattr(thread, "join"):
            thread.join(timeout=0.1)

        if error or returned_state != state or not code:
            return None

        accepted_scopes = {s for s in accepted_scope.split(",") if s}
        if accepted_scopes and not accepted_scopes.intersection(
            {"activity:read", "activity:read_all"}
        ):
            return None

        import requests

        token_resp = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )

        if token_resp.status_code == 200:
            token_data = token_resp.json()
            token_data.update(
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "requested_scope": scope,
                    "accepted_scope": accepted_scope,
                }
            )
            return token_data
        return None

    @staticmethod
    def refresh_strava_token() -> Optional[dict]:
        token_file = os.path.join(CONFIG_DIR, "strava_token.json")
        if not os.path.exists(token_file):
            return None
        try:
            with open(token_file) as f:
                token = json.load(f)

            refresh_token = token.get("refresh_token")
            client_id = token.get("client_id")
            client_secret = token.get("client_secret")
            if not all([refresh_token, client_id, client_secret]):
                return None

            import requests

            token_resp = requests.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=10,
            )
            if token_resp.status_code != 200:
                return None

            refreshed = dict(token)
            refreshed.update(token_resp.json())
            OAuthFlow.save_strava_token(refreshed)
            return refreshed
        except Exception as exc:
            log_warning(f"Failed to refresh Strava token from {token_file}", exc=exc)
            return None

    @staticmethod
    def check_strava_token() -> bool:
        token_file = os.path.join(CONFIG_DIR, "strava_token.json")
        if not os.path.exists(token_file):
            return False
        try:
            with open(token_file) as f:
                token = json.load(f)
            if not token.get("access_token"):
                if token.get("refresh_token"):
                    refreshed = OAuthFlow.refresh_strava_token()
                    return bool(refreshed and refreshed.get("access_token"))
                return False
            expires_at = token.get("expires_at", 0)
            if expires_at and expires_at <= time.time() + TOKEN_REFRESH_WINDOW_SECONDS:
                refreshed = OAuthFlow.refresh_strava_token()
                return bool(refreshed and refreshed.get("access_token"))
            return True
        except Exception as exc:
            log_warning(f"Failed to read Strava token from {token_file}", exc=exc)
            return False

    @staticmethod
    def save_strava_token(token_data: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        token_file = os.path.join(CONFIG_DIR, "strava_token.json")
        with open(token_file, "w") as f:
            json.dump(token_data, f)
        os.chmod(token_file, 0o600)


def setup_strava_oauth():
    client_id = input("Strava Client ID: ").strip()
    client_secret = input("Strava Client Secret: ").strip()

    result = OAuthFlow.strava_auth(client_id, client_secret)
    if result:
        OAuthFlow.save_strava_token(result)
        print("\nStrava authentication successful!")
        return True
    else:
        print("\nStrava authentication failed.")
        return False


def check_oauth_status() -> dict:
    from garmin_coach.adapters.garmin import GarminAdapter
    from garmin_coach.adapters.strava import StravaAdapter

    status = {}
    garmin = GarminAdapter()
    status["garmin"] = garmin.is_authenticated()
    status["strava"] = OAuthFlow.check_strava_token()
    return status
