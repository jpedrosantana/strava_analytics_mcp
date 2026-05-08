import sqlite3
from pathlib import Path

from strava_mcp.db.migrations import apply_migrations
from strava_mcp.db.repositories import ActivityRepository, MetricsRepository
from strava_mcp.sync.compute_metrics import compute_all_metrics
from tests.fixtures.strava_responses import (
    ACTIVITY_LONG_RUN,
    ACTIVITY_NO_HR,
    ACTIVITY_RIDE,
    ACTIVITY_RUN,
    ACTIVITY_RUN_2,
)

# Need ≥ 3 runs with HR for estimate_hrmax; use this set throughout tests that need TRIMP
_RUNS_WITH_HR = [ACTIVITY_RUN, ACTIVITY_RUN_2, ACTIVITY_LONG_RUN]


def _seed(db: str, activities: list[dict]) -> None:
    apply_migrations(db)
    with sqlite3.connect(db) as conn:
        for a in activities:
            ActivityRepository.upsert(conn, a)


class TestComputeAllMetrics:
    def test_returns_activity_count(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _seed(db, [ACTIVITY_RUN, ACTIVITY_RUN_2])
        result = compute_all_metrics(db)
        assert result["activities"] == 2

    def test_stores_activity_metrics(self, tmp_path: Path) -> None:
        # Need ≥ 3 runs so estimate_hrmax can produce a valid value for TRIMP
        db = str(tmp_path / "test.db")
        _seed(db, _RUNS_WITH_HR)
        compute_all_metrics(db)
        with sqlite3.connect(db) as conn:
            m = MetricsRepository.get_activity_metrics(conn, ACTIVITY_RUN["id"])
        assert m is not None
        assert m["trimp"] is not None

    def test_hrtss_when_lthr_configured(self, tmp_path: Path) -> None:
        # hr_tss requires LTHR; pre-configure it so estimation is skipped
        from strava_mcp.db.repositories import AthleteConfigRepository

        db = str(tmp_path / "test.db")
        _seed(db, _RUNS_WITH_HR)
        with sqlite3.connect(db) as conn:
            AthleteConfigRepository.set(conn, "lthr", "165.0")
            AthleteConfigRepository.set(conn, "hr_max", "187.0")
        compute_all_metrics(db)
        with sqlite3.connect(db) as conn:
            m = MetricsRepository.get_activity_metrics(conn, ACTIVITY_RUN["id"])
        assert m is not None
        assert m["hr_tss"] is not None

    def test_no_hr_activity_has_null_trimp(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _seed(db, [ACTIVITY_NO_HR])
        compute_all_metrics(db)
        with sqlite3.connect(db) as conn:
            m = MetricsRepository.get_activity_metrics(conn, ACTIVITY_NO_HR["id"])
        assert m is not None
        assert m["trimp"] is None
        assert m["hr_tss"] is None

    def test_stores_daily_metrics(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _seed(db, [ACTIVITY_RUN, ACTIVITY_RUN_2])
        result = compute_all_metrics(db)
        assert result["daily_rows"] > 0
        with sqlite3.connect(db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
        assert count > 0

    def test_daily_metrics_has_ctl_atl_tsb(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _seed(db, [ACTIVITY_RUN, ACTIVITY_RUN_2])
        compute_all_metrics(db)
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT ctl, atl, tsb FROM daily_metrics ORDER BY date LIMIT 1"
            ).fetchone()
        assert row is not None
        ctl, atl, tsb = row
        assert abs(tsb - (ctl - atl)) < 0.01

    def test_idempotent(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _seed(db, [ACTIVITY_RUN, ACTIVITY_RUN_2])
        compute_all_metrics(db)
        compute_all_metrics(db)
        with sqlite3.connect(db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM activity_metrics").fetchone()[0]
        assert count == 2

    def test_empty_db_returns_zero(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        apply_migrations(db)
        result = compute_all_metrics(db)
        assert result["activities"] == 0
        assert result["daily_rows"] == 0

    def test_progress_callback_called(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _seed(db, [ACTIVITY_RUN, ACTIVITY_RUN_2])
        calls = []
        compute_all_metrics(db, progress=lambda cur, tot: calls.append((cur, tot)))
        assert len(calls) == 2
        assert calls[-1] == (2, 2)

    def test_ride_activity_included(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _seed(db, [ACTIVITY_RIDE])
        result = compute_all_metrics(db)
        assert result["activities"] == 1
        with sqlite3.connect(db) as conn:
            m = MetricsRepository.get_activity_metrics(conn, ACTIVITY_RIDE["id"])
        assert m is not None
