import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from strava_mcp.db.migrations import apply_migrations
from strava_mcp.db.repositories import ActivityRepository, SyncStateRepository
from strava_mcp.sync.incremental import run_incremental
from tests.fixtures.strava_responses import ACTIVITY_RUN, ACTIVITY_RUN_2


def _seed_sync_state(db: str, last_sync: str) -> None:
    apply_migrations(db)
    with sqlite3.connect(db) as conn:
        SyncStateRepository.set(conn, "last_incremental_sync_at", last_sync)


@pytest.mark.asyncio
async def test_incremental_fetches_after_last_sync(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    last_sync = "2024-03-16T00:00:00+00:00"
    _seed_sync_state(db, last_sync)

    client = AsyncMock()
    client.list_activities = AsyncMock(side_effect=[[ACTIVITY_RUN_2], []])

    await run_incremental(db, client)

    expected_after = int(datetime.fromisoformat(last_sync).timestamp())
    client.list_activities.assert_any_call(after=expected_after, page=1, per_page=200)


@pytest.mark.asyncio
async def test_incremental_stores_new_activities(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    _seed_sync_state(db, "2024-03-14T00:00:00+00:00")

    client = AsyncMock()
    client.list_activities = AsyncMock(side_effect=[[ACTIVITY_RUN, ACTIVITY_RUN_2], []])

    count = await run_incremental(db, client)

    assert count == 2
    with sqlite3.connect(db) as conn:
        assert ActivityRepository.count(conn) == 2


@pytest.mark.asyncio
async def test_incremental_updates_sync_state(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    old_sync = "2024-01-01T00:00:00+00:00"
    _seed_sync_state(db, old_sync)

    client = AsyncMock()
    client.list_activities = AsyncMock(return_value=[])

    await run_incremental(db, client)

    with sqlite3.connect(db) as conn:
        new_sync = SyncStateRepository.get(conn, "last_incremental_sync_at")
    assert new_sync != old_sync


@pytest.mark.asyncio
async def test_incremental_raises_without_previous_sync(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    apply_migrations(db)

    client = AsyncMock()
    with pytest.raises(RuntimeError, match="sync --full"):
        await run_incremental(db, client)


@pytest.mark.asyncio
async def test_incremental_no_new_activities(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    _seed_sync_state(db, "2024-03-20T00:00:00+00:00")

    client = AsyncMock()
    client.list_activities = AsyncMock(return_value=[])

    count = await run_incremental(db, client)
    assert count == 0
