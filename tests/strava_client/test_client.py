import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from unittest.mock import MagicMock as MM

import httpx
import httpx as _httpx
import pytest

from strava_mcp.config import settings
from strava_mcp.strava_client.auth import store_tokens
from strava_mcp.strava_client.client import StravaClient
from strava_mcp.strava_client.rate_limit import RateLimiter

_FAST_LIMITER = RateLimiter(per_15min=1000, per_day=10000)


def _setup_db(tmp_path: Path, expires_in: int = 3600) -> str:
    db = str(tmp_path / "test.db")
    store_tokens(
        db,
        {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "expires_at": int(time.time()) + expires_in,
            "athlete": {"id": 1},
        },
    )
    return db


def _mock_http(response_data: dict, status: int = 200) -> tuple:
    """Returns (mock_client, patcher) for patching httpx.AsyncClient."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status
    mock_response.json.return_value = response_data
    mock_response.headers = {}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    patcher = patch("strava_mcp.strava_client.client.httpx.AsyncClient", return_value=mock_client)
    return mock_client, patcher


@pytest.mark.asyncio
async def test_get_athlete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup_db(tmp_path)
    monkeypatch.setattr(settings, "strava_db_path", db)

    athlete_data = {"id": 1, "firstname": "Test", "lastname": "Athlete"}
    mock_client, patcher = _mock_http(athlete_data)

    with patcher:
        result = await StravaClient(rate_limiter=_FAST_LIMITER).get_athlete()

    assert result == athlete_data
    call_kwargs = mock_client.get.call_args
    assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer test_token"


@pytest.mark.asyncio
async def test_get_athlete_refreshes_expired_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _setup_db(tmp_path, expires_in=-10)  # already expired
    monkeypatch.setattr(settings, "strava_db_path", db)
    monkeypatch.setattr(settings, "strava_client_id", 123)
    monkeypatch.setattr(settings, "strava_client_secret", "secret")

    new_token_data = {
        "access_token": "refreshed_token",
        "refresh_token": "new_refresh",
        "expires_at": int(time.time()) + 3600,
    }

    def mock_post(url: str, data: dict | None = None, timeout: int | None = None) -> MM:
        m = MM(spec=_httpx.Response)
        m.json.return_value = new_token_data
        m.raise_for_status.return_value = None
        return m

    monkeypatch.setattr(_httpx, "post", mock_post)

    athlete_data = {"id": 1}
    mock_client, patcher = _mock_http(athlete_data)

    with patcher:
        result = await StravaClient(rate_limiter=_FAST_LIMITER).get_athlete()

    assert result == athlete_data
    call_kwargs = mock_client.get.call_args
    assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer refreshed_token"


@pytest.mark.asyncio
async def test_list_activities_passes_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _setup_db(tmp_path)
    monkeypatch.setattr(settings, "strava_db_path", db)

    mock_client, patcher = _mock_http([{"id": 1}, {"id": 2}])

    with patcher:
        result = await StravaClient(rate_limiter=_FAST_LIMITER).list_activities(
            after=1000, before=2000, page=2, per_page=50
        )

    assert len(result) == 2
    call_params = mock_client.get.call_args.kwargs["params"]
    assert call_params["after"] == 1000
    assert call_params["before"] == 2000
    assert call_params["page"] == 2
    assert call_params["per_page"] == 50


@pytest.mark.asyncio
async def test_get_activity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup_db(tmp_path)
    monkeypatch.setattr(settings, "strava_db_path", db)

    mock_client, patcher = _mock_http({"id": 999, "name": "Morning Run"})

    with patcher:
        result = await StravaClient(rate_limiter=_FAST_LIMITER).get_activity(999)

    assert result["id"] == 999
    call_url = mock_client.get.call_args.args[0]
    assert "/activities/999" in call_url


@pytest.mark.asyncio
async def test_get_streams(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup_db(tmp_path)
    monkeypatch.setattr(settings, "strava_db_path", db)

    streams_data = {"heartrate": {"data": [120, 130]}, "time": {"data": [0, 1]}}
    mock_client, patcher = _mock_http(streams_data)

    with patcher:
        result = await StravaClient(rate_limiter=_FAST_LIMITER).get_streams(
            999, ["heartrate", "time"]
        )

    assert "heartrate" in result
    call_params = mock_client.get.call_args.kwargs["params"]
    assert "heartrate" in call_params["keys"]
    assert call_params["key_by_type"] == "true"


@pytest.mark.asyncio
async def test_429_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _setup_db(tmp_path)
    monkeypatch.setattr(settings, "strava_db_path", db)

    mock_429 = MagicMock(spec=httpx.Response)
    mock_429.status_code = 429
    mock_429.headers = {"Retry-After": "0"}

    mock_200 = MagicMock(spec=httpx.Response)
    mock_200.status_code = 200
    mock_200.json.return_value = {"id": 1}
    mock_200.headers = {}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_429, mock_200])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("strava_mcp.strava_client.client.httpx.AsyncClient", return_value=mock_client),
        patch("strava_mcp.strava_client.client.asyncio.sleep"),
    ):
        result = await StravaClient(rate_limiter=_FAST_LIMITER).get_athlete()

    assert result == {"id": 1}
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_raises_when_not_authenticated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "strava_db_path", str(tmp_path / "nonexistent.db"))
    client = StravaClient(rate_limiter=_FAST_LIMITER)
    with pytest.raises(RuntimeError, match="Não autenticado"):
        await client.get_athlete()
