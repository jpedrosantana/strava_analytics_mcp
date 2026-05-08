import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from strava_mcp.db.migrations import apply_migrations
from strava_mcp.db.repositories import ActivityRepository, SyncStateRepository
from strava_mcp.strava_client.client import StravaClient

logger = logging.getLogger(__name__)

_PER_PAGE = 200


async def run_backfill(
    db_path: str,
    client: StravaClient,
    progress: Callable[[int, int], None] | None = None,
) -> int:
    """Download all activities from Strava and upsert into the local DB.

    progress(page, total_so_far) is called after each page if provided.
    Returns total number of activities upserted.
    """
    apply_migrations(db_path)

    total = 0
    page = 1

    while True:
        activities = await client.list_activities(page=page, per_page=_PER_PAGE)
        if not activities:
            break

        with sqlite3.connect(db_path) as conn:
            for activity in activities:
                ActivityRepository.upsert(conn, activity)

        total += len(activities)
        logger.info("backfill page=%d fetched=%d total=%d", page, len(activities), total)

        if progress:
            progress(page, total)

        page += 1

    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        SyncStateRepository.set(conn, "last_full_sync_at", now)
        SyncStateRepository.set(conn, "last_incremental_sync_at", now)

    logger.info("backfill complete total=%d", total)
    return total
