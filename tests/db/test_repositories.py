import sqlite3
from pathlib import Path

import pytest

from strava_mcp.db.migrations import apply_migrations
from strava_mcp.db.repositories import (
    ActivityRepository,
    AthleteConfigRepository,
    StreamRepository,
    SyncStateRepository,
)
from tests.fixtures.strava_responses import (
    ACTIVITY_NO_HR,
    ACTIVITY_RIDE,
    ACTIVITY_RUN,
    SAMPLE_STREAMS,
)


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = str(tmp_path / "test.db")
    apply_migrations(db)
    c = sqlite3.connect(db)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# ActivityRepository
# ---------------------------------------------------------------------------


class TestActivityRepository:
    def test_upsert_and_count(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        assert ActivityRepository.count(conn) == 1

    def test_upsert_is_idempotent(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        assert ActivityRepository.count(conn) == 1

    def test_upsert_updates_existing(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        updated = {**ACTIVITY_RUN, "name": "Updated Name"}
        ActivityRepository.upsert(conn, updated)
        row = ActivityRepository.get_by_id(conn, ACTIVITY_RUN["id"])
        assert row["name"] == "Updated Name"

    def test_upsert_activity_without_heartrate(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_NO_HR)
        row = ActivityRepository.get_by_id(conn, ACTIVITY_NO_HR["id"])
        assert row is not None
        assert row["has_heartrate"] == 0
        assert row["average_heartrate"] is None

    def test_upsert_activity_with_powermeter(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RIDE)
        row = ActivityRepository.get_by_id(conn, ACTIVITY_RIDE["id"])
        assert row["has_powermeter"] == 1

    def test_count_by_sport(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        ActivityRepository.upsert(conn, ACTIVITY_RIDE)
        by_sport = ActivityRepository.count_by_sport(conn)
        assert by_sport["Run"] == 1
        assert by_sport["Ride"] == 1

    def test_get_date_range(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        ActivityRepository.upsert(conn, ACTIVITY_RIDE)
        newest = ActivityRepository.get_newest_start_date(conn)
        oldest = ActivityRepository.get_oldest_start_date(conn)
        assert newest is not None
        assert oldest is not None
        assert newest >= oldest

    def test_count_without_streams(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        ActivityRepository.upsert(conn, {**ACTIVITY_RUN, "id": 99999})
        assert ActivityRepository.count_without_streams(conn) == 2

    def test_mark_streams_synced(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        ActivityRepository.mark_streams_synced(conn, ACTIVITY_RUN["id"], "2024-01-01T00:00:00")
        assert ActivityRepository.count_without_streams(conn) == 0

    def test_list_ids_without_streams(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        ids = ActivityRepository.list_ids_without_streams(conn)
        assert ACTIVITY_RUN["id"] in ids


# ---------------------------------------------------------------------------
# StreamRepository
# ---------------------------------------------------------------------------


class TestStreamRepository:
    def test_upsert_and_get(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        data = SAMPLE_STREAMS["heartrate"]["data"]
        StreamRepository.upsert(conn, ACTIVITY_RUN["id"], "heartrate", data, "high")
        result = StreamRepository.get(conn, ACTIVITY_RUN["id"], "heartrate")
        assert result == data

    def test_upsert_overwrites(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        StreamRepository.upsert(conn, ACTIVITY_RUN["id"], "heartrate", [100, 110], "high")
        StreamRepository.upsert(conn, ACTIVITY_RUN["id"], "heartrate", [120, 130], "high")
        assert StreamRepository.get(conn, ACTIVITY_RUN["id"], "heartrate") == [120, 130]

    def test_get_missing_returns_none(self, conn: sqlite3.Connection) -> None:
        assert StreamRepository.get(conn, 99999, "heartrate") is None

    def test_get_activity_ids_with_streams(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        StreamRepository.upsert(conn, ACTIVITY_RUN["id"], "time", [0, 1, 2], "high")
        ids = StreamRepository.get_activity_ids_with_streams(conn)
        assert ACTIVITY_RUN["id"] in ids

    def test_compression_roundtrip(self, conn: sqlite3.Connection) -> None:
        ActivityRepository.upsert(conn, ACTIVITY_RUN)
        large_data = list(range(10_000))
        StreamRepository.upsert(conn, ACTIVITY_RUN["id"], "time", large_data, "high")
        assert StreamRepository.get(conn, ACTIVITY_RUN["id"], "time") == large_data


# ---------------------------------------------------------------------------
# SyncStateRepository
# ---------------------------------------------------------------------------


class TestSyncStateRepository:
    def test_set_and_get(self, conn: sqlite3.Connection) -> None:
        SyncStateRepository.set(conn, "last_full_sync_at", "2024-01-01T00:00:00Z")
        assert SyncStateRepository.get(conn, "last_full_sync_at") == "2024-01-01T00:00:00Z"

    def test_get_missing_returns_none(self, conn: sqlite3.Connection) -> None:
        assert SyncStateRepository.get(conn, "nonexistent_key") is None

    def test_set_overwrites(self, conn: sqlite3.Connection) -> None:
        SyncStateRepository.set(conn, "key", "v1")
        SyncStateRepository.set(conn, "key", "v2")
        assert SyncStateRepository.get(conn, "key") == "v2"


# ---------------------------------------------------------------------------
# AthleteConfigRepository
# ---------------------------------------------------------------------------


class TestAthleteConfigRepository:
    def test_set_and_get(self, conn: sqlite3.Connection) -> None:
        AthleteConfigRepository.set(conn, "lthr", "165")
        assert AthleteConfigRepository.get(conn, "lthr") == "165"

    def test_get_all(self, conn: sqlite3.Connection) -> None:
        AthleteConfigRepository.set(conn, "lthr", "165")
        AthleteConfigRepository.set(conn, "hr_max", "185")
        config = AthleteConfigRepository.get_all(conn)
        assert config["lthr"] == "165"
        assert config["hr_max"] == "185"
