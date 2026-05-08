import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from strava_mcp.strava_client.auth import (
    exchange_code,
    load_tokens,
    refresh_tokens,
    store_tokens,
)


def _token_data(expires_in: int = 3600, with_athlete: bool = True) -> dict:
    data = {
        "access_token": "test_access",
        "refresh_token": "test_refresh",
        "expires_at": int(time.time()) + expires_in,
    }
    if with_athlete:
        data["athlete"] = {"id": 42, "firstname": "Test", "lastname": "Athlete"}
    return data


def test_store_and_load_tokens(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    store_tokens(db, _token_data())
    loaded = load_tokens(db)
    assert loaded is not None
    assert loaded["access_token"] == "test_access"
    assert loaded["refresh_token"] == "test_refresh"
    assert loaded["athlete_id"] == 42


def test_store_tokens_overwrites_existing(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    store_tokens(db, _token_data())
    updated = {**_token_data(), "access_token": "new_access", "refresh_token": "new_refresh"}
    store_tokens(db, updated)
    loaded = load_tokens(db)
    assert loaded["access_token"] == "new_access"
    assert loaded["refresh_token"] == "new_refresh"


def test_store_tokens_without_athlete(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    store_tokens(db, _token_data(with_athlete=False))
    loaded = load_tokens(db)
    assert loaded is not None
    assert loaded["athlete_id"] is None


def test_load_tokens_missing_db(tmp_path: Path) -> None:
    assert load_tokens(str(tmp_path / "nonexistent.db")) is None


def test_load_tokens_empty_table(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.db")
    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TABLE oauth_tokens (
                id INTEGER PRIMARY KEY DEFAULT 1,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                athlete_id INTEGER,
                CHECK (id = 1)
            )
        """)
    assert load_tokens(db) is None


def test_load_tokens_missing_table(tmp_path: Path) -> None:
    db = str(tmp_path / "no_table.db")
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
    assert load_tokens(db) is None


def test_store_tokens_creates_parent_dirs(tmp_path: Path) -> None:
    db = str(tmp_path / "nested" / "dir" / "test.db")
    store_tokens(db, _token_data())
    assert Path(db).exists()


def test_exchange_code(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def mock_post(url: str, data: dict | None = None, timeout: int | None = None) -> MagicMock:
        captured["url"] = url
        captured["data"] = data
        mock = MagicMock(spec=httpx.Response)
        mock.json.return_value = _token_data()
        mock.raise_for_status.return_value = None
        return mock

    monkeypatch.setattr(httpx, "post", mock_post)
    result = exchange_code(123, "secret", "auth_code")

    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code"] == "auth_code"
    assert result["access_token"] == "test_access"


def test_refresh_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def mock_post(url: str, data: dict | None = None, timeout: int | None = None) -> MagicMock:
        captured["data"] = data
        mock = MagicMock(spec=httpx.Response)
        mock.json.return_value = {**_token_data(), "access_token": "refreshed_access"}
        mock.raise_for_status.return_value = None
        return mock

    monkeypatch.setattr(httpx, "post", mock_post)
    result = refresh_tokens(123, "secret", "old_refresh")

    assert captured["data"]["grant_type"] == "refresh_token"
    assert captured["data"]["refresh_token"] == "old_refresh"
    assert result["access_token"] == "refreshed_access"
