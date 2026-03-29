import os
import json
import time
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs


CONFIG_DIR = os.path.expanduser("~/.config/garmin_coach")


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
        client_id: str, client_secret: str, redirect_port: int = 8080
    ) -> Optional[dict]:
        auth_url = f"https://www.strava.com/oauth/authorize?{
            urlencode(
                {
                    'client_id': client_id,
                    'response_type': 'code',
                    'redirect_uri': f'http://localhost:{redirect_port}/callback',
                    'scope': 'read,activity:read',
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
        thread.start()

        while OAuthCallbackHandler.received_params is None:
            time.sleep(0.5)

        code = OAuthCallbackHandler.received_params.get("code", [None])[0]
        server.server_close()

        if not code:
            return None

        import requests

        token_resp = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )

        if token_resp.status_code == 200:
            return token_resp.json()
        return None

    @staticmethod
    def check_strava_token() -> bool:
        token_file = os.path.join(CONFIG_DIR, "strava_token.json")
        if not os.path.exists(token_file):
            return False
        try:
            with open(token_file) as f:
                token = json.load(f)
            if token.get("expires_at", 0) < time.time():
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def save_strava_token(token_data: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        token_file = os.path.join(CONFIG_DIR, "strava_token.json")
        with open(token_file, "w") as f:
            json.dump(token_data, f)


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
