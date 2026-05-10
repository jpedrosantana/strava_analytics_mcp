from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from strava_mcp.db.migrations import apply_migrations
from strava_mcp.sync.streams import download_streams_batch


@pytest.mark.asyncio
async def test_empty_batch_returns_normalized_shape(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    apply_migrations(db)

    client = AsyncMock()

    result = await download_streams_batch(db, client, limit=50)

    assert result["processed"] == 0
    assert result["success"] == 0
    assert result["errors"] == 0
    assert "message" in result
    client.get_streams.assert_not_called()
