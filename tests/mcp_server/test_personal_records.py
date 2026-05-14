"""End-to-end test: streams → compute_metrics → query_find_personal_records.

Demonstrates the headline win of the new pipeline: a 5K segment inside a
longer run wins over a slower full-5K activity.
"""

import sqlite3
from pathlib import Path

from strava_mcp.db.migrations import apply_migrations
from strava_mcp.db.repositories import ActivityRepository, StreamRepository
from strava_mcp.mcp_server.queries import query_find_personal_records
from strava_mcp.sync.compute_metrics import compute_all_metrics
from tests.fixtures.strava_responses import ACTIVITY_RUN


def _make_run(id_: int, name: str, date: str, distance: float, moving_time: int) -> dict:
    return {
        **ACTIVITY_RUN,
        "id": id_,
        "name": name,
        "start_date": f"{date}T09:00:00Z",
        "start_date_local": f"{date}T06:00:00Z",
        "distance": distance,
        "moving_time": moving_time,
        "elapsed_time": moving_time + 60,
    }


def _seed_athlete(conn: sqlite3.Connection) -> None:
    sql = (
        "INSERT OR REPLACE INTO athlete_config (key, value, updated_at) "
        "VALUES (?, ?, datetime('now'))"
    )
    conn.execute(sql, ("lthr", "177.0"))
    conn.execute(sql, ("hr_max", "201.0"))
    conn.execute(sql, ("threshold_pace_mps", "3.663"))
    conn.execute(sql, ("sex", "male"))


def test_5k_segment_inside_longer_run_beats_slow_full_5k(tmp_path: Path):
    """A 5K split at 4 m/s inside a 10K run should beat a slower 5K activity."""
    db_path = str(tmp_path / "test.db")
    apply_migrations(db_path)

    slow_5k = _make_run(
        id_=1001,
        name="Slow 5K",
        date="2024-03-01",
        distance=5050.0,
        moving_time=1300,  # ~3.88 m/s → 4:18/km
    )
    fast_10k = _make_run(
        id_=1002,
        name="Tempo 10K with fast 5K split",
        date="2024-03-15",
        distance=10000.0,
        moving_time=2500,  # 4 m/s avg, but the first 5K is genuinely faster
    )

    # Streams: slow 5K at constant 3.88 m/s (1300s for ~5050m).
    slow_n = 1301
    slow_distance = [i * (5050.0 / 1300) for i in range(slow_n)]
    slow_time = list(range(slow_n))

    # Fast 10K: first 5K at 4.2 m/s (1190s), second 5K at 3.85 m/s (1300s).
    fast_distance: list[float] = [0.0]
    fast_time: list[int] = [0]
    for i in range(1, 1191):
        fast_distance.append(i * 4.2)
        fast_time.append(i)
    last_d = fast_distance[-1]
    for k in range(1, 1301):
        fast_distance.append(last_d + k * 3.85)
        fast_time.append(1190 + k)

    with sqlite3.connect(db_path) as conn:
        _seed_athlete(conn)
        for act in (slow_5k, fast_10k):
            ActivityRepository.upsert(conn, act)
        StreamRepository.upsert(conn, 1001, "distance", slow_distance, "high")
        StreamRepository.upsert(conn, 1001, "time", slow_time, "high")
        StreamRepository.upsert(conn, 1002, "distance", fast_distance, "high")
        StreamRepository.upsert(conn, 1002, "time", fast_time, "high")

    compute_all_metrics(db_path)

    with sqlite3.connect(db_path) as conn:
        prs = query_find_personal_records(conn)

    by_label = {p["distance_label"]: p for p in prs}

    five_k = by_label["5K"]
    assert five_k["status"] == "ok"
    assert five_k["activity_id"] == 1002, "5K PR should be the segment inside the tempo 10K"
    assert five_k["is_segment"] is True
    assert five_k["parent_distance_m"] >= 9999.0
    # First 5K at 4.2 m/s ≈ 1190s — faster than the 1300s of the slow full 5K.
    assert five_k["time_s"] < 1200

    ten_k = by_label["10K"]
    assert ten_k["status"] == "ok"
    assert ten_k["activity_id"] == 1002
    assert ten_k["is_segment"] is False  # the 10K covered the full activity


def test_no_record_when_no_runs_long_enough(tmp_path: Path):
    """If no run covers the target distance, status='no_record'."""
    db_path = str(tmp_path / "test.db")
    apply_migrations(db_path)

    short_run = _make_run(
        id_=2001,
        name="Short jog",
        date="2024-03-01",
        distance=900.0,
        moving_time=300,
    )
    with sqlite3.connect(db_path) as conn:
        _seed_athlete(conn)
        ActivityRepository.upsert(conn, short_run)
        StreamRepository.upsert(conn, 2001, "distance", [i * 3.0 for i in range(301)], "high")
        StreamRepository.upsert(conn, 2001, "time", list(range(301)), "high")

    compute_all_metrics(db_path)

    with sqlite3.connect(db_path) as conn:
        prs = query_find_personal_records(conn)
    statuses = {p["distance_label"]: p["status"] for p in prs}
    # 900m run covers nothing.
    assert all(s == "no_record" for s in statuses.values())
