import sqlite3
from pathlib import Path

from strava_mcp.db.migrations import apply_migrations

_EXPECTED_TABLES = {
    "activities",
    "activity_streams",
    "activity_metrics",
    "daily_metrics",
    "athlete_config",
    "sync_state",
    "oauth_tokens",
}


def _get_tables(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def test_apply_migrations_creates_all_tables(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    apply_migrations(db)
    assert _EXPECTED_TABLES.issubset(_get_tables(db))


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    apply_migrations(db)
    apply_migrations(db)  # second call must not raise
    assert _EXPECTED_TABLES.issubset(_get_tables(db))


def test_apply_migrations_creates_parent_dirs(tmp_path: Path) -> None:
    db = str(tmp_path / "nested" / "dir" / "test.db")
    apply_migrations(db)
    assert Path(db).exists()


def test_apply_migrations_preserves_existing_tokens(tmp_path: Path) -> None:
    """Migration must not destroy oauth_tokens created by auth.py in Phase 1."""
    import time

    from strava_mcp.strava_client.auth import store_tokens

    db = str(tmp_path / "test.db")
    store_tokens(
        db,
        {
            "access_token": "existing",
            "refresh_token": "existing_refresh",
            "expires_at": int(time.time()) + 3600,
        },
    )

    apply_migrations(db)

    from strava_mcp.strava_client.auth import load_tokens

    tokens = load_tokens(db)
    assert tokens is not None
    assert tokens["access_token"] == "existing"
