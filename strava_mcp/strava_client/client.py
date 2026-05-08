import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from strava_mcp.config import settings
from strava_mcp.strava_client.auth import load_tokens, refresh_tokens, store_tokens
from strava_mcp.strava_client.rate_limit import RateLimiter

BASE_URL = "https://www.strava.com/api/v3"


class StravaClient:
    """Async client for the Strava API with automatic token refresh and rate limiting."""

    def __init__(self, rate_limiter: RateLimiter | None = None) -> None:
        self._limiter = rate_limiter or RateLimiter()

    async def _get_token(self) -> str:
        tokens = load_tokens(settings.strava_db_path)
        if tokens is None:
            raise RuntimeError("Não autenticado. Execute `strava-mcp setup` primeiro.")

        expires_at = datetime.fromisoformat(tokens["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at - datetime.now(UTC) < timedelta(minutes=5):
            if not settings.strava_client_id or not settings.strava_client_secret:
                raise RuntimeError("STRAVA_CLIENT_ID e STRAVA_CLIENT_SECRET ausentes no .env.")
            refreshed = refresh_tokens(
                settings.strava_client_id,
                settings.strava_client_secret,
                tokens["refresh_token"],
            )
            store_tokens(settings.strava_db_path, refreshed)
            return refreshed["access_token"]

        return tokens["access_token"]

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> Any:
        for attempt in range(max_retries):
            await self._limiter.acquire()
            token = await self._get_token()
            async with httpx.AsyncClient() as http:
                response = await http.get(
                    f"{BASE_URL}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30,
                )
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_after)
                    continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(f"Máximo de {max_retries} tentativas atingido para {path}")

    async def get_athlete(self) -> dict[str, Any]:
        return await self._get("/athlete")

    async def list_activities(
        self,
        after: int | None = None,
        before: int | None = None,
        page: int = 1,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if after is not None:
            params["after"] = after
        if before is not None:
            params["before"] = before
        return await self._get("/athlete/activities", params=params)

    async def get_activity(self, activity_id: int) -> dict[str, Any]:
        return await self._get(f"/activities/{activity_id}")

    async def get_streams(self, activity_id: int, types: list[str]) -> dict[str, Any]:
        return await self._get(
            f"/activities/{activity_id}/streams",
            params={"keys": ",".join(types), "key_by_type": "true"},
        )
