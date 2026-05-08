"""Shared fixtures for MCP server query tests."""
import sqlite3
from pathlib import Path

import pytest

from strava_mcp.db.migrations import apply_migrations
from strava_mcp.db.repositories import ActivityRepository
from strava_mcp.sync.compute_metrics import compute_all_metrics
from tests.fixtures.strava_responses import (
    ACTIVITY_LONG_RUN,
    ACTIVITY_NO_HR,
    ACTIVITY_RIDE,
    ACTIVITY_RUN,
    ACTIVITY_RUN_2,
)


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test.db")
    apply_migrations(path)
    activities = [ACTIVITY_RUN, ACTIVITY_RUN_2, ACTIVITY_LONG_RUN, ACTIVITY_NO_HR, ACTIVITY_RIDE]
    with sqlite3.connect(path) as conn:
        for a in activities:
            ActivityRepository.upsert(conn, a)
    # Pre-configure LTHR and hr_max so metrics are fully computed
    _cfg_sql = (
        "INSERT OR REPLACE INTO athlete_config (key, value, updated_at) "
        "VALUES (?, ?, datetime('now'))"
    )
    with sqlite3.connect(path) as conn:
        conn.execute(_cfg_sql, ("lthr", "165.0"))
        conn.execute(_cfg_sql, ("hr_max", "187.0"))
    compute_all_metrics(path)
    return path


@pytest.fixture()
def conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path)
    yield c
    c.close()
