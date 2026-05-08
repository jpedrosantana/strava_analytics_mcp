import logging
import sqlite3
from datetime import UTC, datetime
from typing import Any

from strava_mcp.db.repositories import ActivityRepository, StreamRepository
from strava_mcp.strava_client.client import StravaClient

logger = logging.getLogger(__name__)

_DEFAULT_STREAM_TYPES = [
    "time",
    "heartrate",
    "velocity_smooth",
    "altitude",
    "cadence",
    "watts",
    "latlng",
]


async def download_streams_for_activity(
    activity_id: int,
    db_path: str,
    client: StravaClient,
    types: list[str] | None = None,
) -> dict[str, Any]:
    """Download and store streams for a single activity.

    Returns a dict with stream types successfully stored.
    """
    requested = types or _DEFAULT_STREAM_TYPES
    try:
        streams_data = await client.get_streams(activity_id, requested)
    except Exception as e:
        logger.warning("streams fetch failed activity_id=%d error=%s", activity_id, e)
        return {"error": str(e), "activity_id": activity_id}

    now = datetime.now(UTC).isoformat()
    stored: list[str] = []

    with sqlite3.connect(db_path) as conn:
        for stream_type, stream in streams_data.items():
            if not isinstance(stream, dict) or "data" not in stream:
                continue
            resolution = stream.get("resolution", "high")
            StreamRepository.upsert(conn, activity_id, stream_type, stream["data"], resolution)
            stored.append(stream_type)

        ActivityRepository.mark_streams_synced(conn, activity_id, now)

    logger.info("streams stored activity_id=%d types=%s", activity_id, stored)
    return {"activity_id": activity_id, "stored_types": stored}


async def download_streams_batch(
    db_path: str,
    client: StravaClient,
    limit: int = 50,
    types: list[str] | None = None,
) -> dict[str, Any]:
    """Download streams for activities that don't have them yet.

    limit: max number of activities to process in this batch.
    Returns summary of results.
    """
    with sqlite3.connect(db_path) as conn:
        activity_ids = ActivityRepository.list_ids_without_streams(conn, limit=limit)

    if not activity_ids:
        return {"processed": 0, "message": "Todas as atividades já têm streams."}

    success = 0
    errors = 0

    for activity_id in activity_ids:
        result = await download_streams_for_activity(activity_id, db_path, client, types)
        if "error" in result:
            errors += 1
        else:
            success += 1

    return {"processed": len(activity_ids), "success": success, "errors": errors}
