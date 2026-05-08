import sqlite3
import threading
import webbrowser
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

OAUTH_PORT = 8765
REDIRECT_URI = f"http://localhost:{OAUTH_PORT}/callback"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
SCOPE = "read,activity:read_all"


class _CallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None
    _done: threading.Event

    def do_GET(self) -> None:  # noqa: N802
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _CallbackHandler.code = params["code"][0]
            self._respond(200, b"Autenticado com sucesso! Pode fechar esta aba.")
        else:
            _CallbackHandler.error = params.get("error", ["desconhecido"])[0]
            self._respond(400, f"Erro: {_CallbackHandler.error}".encode())
        _CallbackHandler._done.set()

    def _respond(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


def _build_auth_url(client_id: int) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "approval_prompt": "auto",
    }
    return f"{STRAVA_AUTH_URL}?{urlencode(params)}"


def run_oauth_flow(client_id: int, client_secret: str, db_path: str) -> dict[str, Any]:
    """Full browser-based OAuth dance. Blocks until complete or timeout (120s)."""
    done = threading.Event()
    _CallbackHandler._done = done
    _CallbackHandler.code = None
    _CallbackHandler.error = None

    server = HTTPServer(("localhost", OAUTH_PORT), _CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    auth_url = _build_auth_url(client_id)
    print(f"\nAbrindo navegador para autorização Strava:\n{auth_url}\n")
    webbrowser.open(auth_url)
    print("Aguardando autorização (timeout: 120s)...")

    done.wait(timeout=120)
    server.shutdown()

    if _CallbackHandler.error:
        raise RuntimeError(f"Autorização negada: {_CallbackHandler.error}")
    if not _CallbackHandler.code:
        raise TimeoutError("Timeout: autorização não completada em 120 segundos.")

    token_data = exchange_code(client_id, client_secret, _CallbackHandler.code)
    store_tokens(db_path, token_data)
    return token_data


def exchange_code(client_id: int, client_secret: str, code: str) -> dict[str, Any]:
    response = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_tokens(client_id: int, client_secret: str, refresh_token: str) -> dict[str, Any]:
    response = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def store_tokens(db_path: str, token_data: dict[str, Any]) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id INTEGER PRIMARY KEY DEFAULT 1,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                athlete_id INTEGER,
                CHECK (id = 1)
            )
        """)
        expires_at = datetime.fromtimestamp(token_data["expires_at"], tz=UTC).isoformat()
        athlete = token_data.get("athlete")
        athlete_id = athlete.get("id") if isinstance(athlete, dict) else None
        conn.execute(
            """
            INSERT INTO oauth_tokens (id, access_token, refresh_token, expires_at, athlete_id)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                athlete_id = excluded.athlete_id
            """,
            (token_data["access_token"], token_data["refresh_token"], expires_at, athlete_id),
        )


def load_tokens(db_path: str) -> dict[str, Any] | None:
    if not Path(db_path).exists():
        return None
    with sqlite3.connect(db_path) as conn:
        # table may not exist yet if DB was created by another process
        try:
            row = conn.execute(
                "SELECT access_token, refresh_token, expires_at, athlete_id "
                "FROM oauth_tokens WHERE id = 1"
            ).fetchone()
        except sqlite3.OperationalError:
            return None
    if not row:
        return None
    return {
        "access_token": row[0],
        "refresh_token": row[1],
        "expires_at": row[2],
        "athlete_id": row[3],
    }
