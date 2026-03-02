#!/usr/bin/env python3
"""Tiny dev server for the Cortana demo dashboard.

Usage:
    python demo_server.py                    # reads .env.seller
    ENV_FILE=.env.customer python demo_server.py

Endpoints:
    GET /              → serves demo.html (with LIVEKIT_URL injected)
    GET /api/rooms     → lists active LiveKit rooms as JSON
    GET /api/token     → generates a participant join token
                         ?room=<name>&identity=<id>
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = os.environ.get("ENV_FILE", "envs/.env.customer")
load_dotenv(ENV_FILE)

LIVEKIT_WS_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_HTTP_URL = LIVEKIT_WS_URL.replace("wss://", "https://").replace("ws://", "http://")
API_KEY = os.getenv("LIVEKIT_API_KEY", "")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
AGENT_NAME = os.getenv("AGENT_NAME", "customer")
PORT = int(os.environ.get("PORT", 8080))
HERE = Path(__file__).parent


def _admin_token() -> str:
    from livekit.api import AccessToken, VideoGrants
    return (
        AccessToken(api_key=API_KEY, api_secret=API_SECRET)
        .with_identity("demo-server")
        .with_grants(VideoGrants(room_list=True, room_admin=True))
        .to_jwt()
    )


def _participant_token(room: str, identity: str) -> str:
    from livekit.api import AccessToken, VideoGrants, RoomConfiguration, RoomAgentDispatch
    return (
        AccessToken(api_key=API_KEY, api_secret=API_SECRET)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        ))
        .with_room_config(RoomConfiguration(
            agents=[RoomAgentDispatch(agent_name=AGENT_NAME)],
        ))
        .to_jwt()
    )


def _list_rooms() -> list:
    token = _admin_token()
    url = f"{LIVEKIT_HTTP_URL}/twirp/livekit.RoomService/ListRooms"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read()
    data = json.loads(body)
    return data.get("rooms", [])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default per-request logs

    def _send_json(self, code: int, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if path == "/":
            html = (HERE / "demo.html").read_bytes()
            html = html.replace(b"{{LIVEKIT_URL}}", LIVEKIT_WS_URL.encode())
            self._send_html(html)

        elif path == "/api/rooms":
            try:
                rooms = _list_rooms()
                self._send_json(200, {"rooms": rooms})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        elif path == "/api/token":
            room_name = params.get("room", "")
            identity = params.get("identity", "demo-user")
            if not room_name:
                self._send_json(400, {"error": "room parameter required"})
                return
            try:
                token = _participant_token(room_name, identity)
                self._send_json(200, {"token": token})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    if not API_KEY or not API_SECRET:
        print(
            f"[ERROR] LIVEKIT_API_KEY or LIVEKIT_API_SECRET not set "
            f"(loaded from {ENV_FILE})",
            file=sys.stderr,
        )
        sys.exit(1)

    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"Cortana demo  →  http://localhost:{PORT}")
    print(f"LiveKit       →  {LIVEKIT_HTTP_URL}")
    print(f"Env file      →  {ENV_FILE}")
    server.serve_forever()
