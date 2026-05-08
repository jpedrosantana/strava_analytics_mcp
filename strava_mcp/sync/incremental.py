import logging
import sqlite3
from datetime import UTC, datetime

from strava_mcp.db.migrations import apply_migrations
from strava_mcp.db.repositories import ActivityRepository, SyncStateRepository
from strava_mcp.strava_client.client import StravaClient

logger = logging.getLogger(__name__)

_PER_PAGE = 200


async def run_incremental(db_path: str, client: StravaClient) -> int:
    """Download activities created since the last sync and upsert into the local DB.

    Raises RuntimeError if no previous sync exists — run `sync --full` first.
    Returns count of new/updated activities.
    """
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        last_sync = SyncStateRepository.get(conn, "last_incremental_sync_at")

    if last_sync is None:
        raise RuntimeError(
            "Nenhum sync anterior encontrado. Execute `strava-mcp sync --full` primeiro."
        )

    after_dt = datetime.fromisoformat(last_sync)
    if after_dt.tzinfo is None:
        after_dt = after_dt.replace(tzinfo=UTC)
    after_ts = int(after_dt.timestamp())

    total = 0
    page = 1

    while True:
        activities = await client.list_activities(after=after_ts, page=page, per_page=_PER_PAGE)
        if not activities:
            break

        with sqlite3.connect(db_path) as conn:
            for activity in activities:
                ActivityRepository.upsert(conn, activity)

        total += len(activities)
        logger.info("incremental page=%d fetched=%d total=%d", page, len(activities), total)

        page += 1

    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        SyncStateRepository.set(conn, "last_incremental_sync_at", now)

    logger.info("incremental complete total=%d", total)
    return total
