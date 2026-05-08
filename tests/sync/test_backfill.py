import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from strava_mcp.db.repositories import ActivityRepository, SyncStateRepository
from strava_mcp.sync.backfill import run_backfill
from tests.fixtures.strava_responses import SAMPLE_ACTIVITIES_PAGE_1, SAMPLE_ACTIVITIES_PAGE_2


def _make_client(pages: list[list]) -> AsyncMock:
    client = AsyncMock()
    # Append empty list to signal end of pagination
    client.list_activities = AsyncMock(side_effect=[*pages, []])
    return client


@pytest.mark.asyncio
async def test_backfill_stores_all_activities(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    client = _make_client([SAMPLE_ACTIVITIES_PAGE_1, SAMPLE_ACTIVITIES_PAGE_2])

    count = await run_backfill(db, client)

    assert count == len(SAMPLE_ACTIVITIES_PAGE_1) + len(SAMPLE_ACTIVITIES_PAGE_2)
    with sqlite3.connect(db) as conn:
        assert ActivityRepository.count(conn) == count


@pytest.mark.asyncio
async def test_backfill_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")

    client1 = _make_client([SAMPLE_ACTIVITIES_PAGE_1])
    await run_backfill(db, client1)

    client2 = _make_client([SAMPLE_ACTIVITIES_PAGE_1])
    await run_backfill(db, client2)

    with sqlite3.connect(db) as conn:
        assert ActivityRepository.count(conn) == len(SAMPLE_ACTIVITIES_PAGE_1)


@pytest.mark.asyncio
async def test_backfill_updates_sync_state(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    client = _make_client([SAMPLE_ACTIVITIES_PAGE_1])

    await run_backfill(db, client)

    with sqlite3.connect(db) as conn:
        assert SyncStateRepository.get(conn, "last_full_sync_at") is not None
        assert SyncStateRepository.get(conn, "last_incremental_sync_at") is not None


@pytest.mark.asyncio
async def test_backfill_empty_history(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    client = _make_client([[]])  # side_effect will be [[], []]

    count = await run_backfill(db, client)

    assert count == 0


@pytest.mark.asyncio
async def test_backfill_calls_progress(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    client = _make_client([SAMPLE_ACTIVITIES_PAGE_1])

    calls: list[tuple] = []
    await run_backfill(db, client, progress=lambda p, t: calls.append((p, t)))

    assert len(calls) == 1
    assert calls[0] == (1, len(SAMPLE_ACTIVITIES_PAGE_1))
