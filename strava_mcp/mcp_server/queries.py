"""Read-only query helpers for MCP tools. All functions take a sqlite3.Connection."""

import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from strava_mcp.analytics.anomalies import detect_outliers, fit_pace_model
from strava_mcp.analytics.clustering import cluster_routes
from strava_mcp.analytics.injury_risk import assess_injury_risk
from strava_mcp.analytics.narrative import (
    assemble_narrative,
    count_concerns,
    select_highlights,
    summarize_form_change,
)
from strava_mcp.analytics.performance_drivers import fit_driver_model, rank_drivers
from strava_mcp.analytics.plateau import (
    assess_plateau,
    days_since_last_pr,
    ef_trend,
    intensity_variety,
    pace_at_lthr_trend,
)
from strava_mcp.analytics.predictions import predict_race_time as _predict_race_time

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _pace_str(speed_mps: float | None) -> str | None:
    if not speed_mps or speed_mps <= 0:
        return None
    secs_per_km = 1000 / speed_mps
    m, s = divmod(int(secs_per_km), 60)
    return f"{m}:{s:02d}/km"


def _fmt_activity(row: dict[str, Any]) -> dict[str, Any]:
    dist_km = (row.get("distance_m") or 0) / 1000
    dur_min = (row.get("moving_time_s") or 0) / 60
    return {
        "id": row["id"],
        "name": row["name"],
        "date": str(row.get("start_date_local", ""))[:10],
        "sport_type": row.get("sport_type"),
        "distance_km": round(dist_km, 2),
        "duration_min": round(dur_min, 1),
        "pace": _pace_str(row.get("average_speed_mps")),
        "avg_hr": row.get("average_heartrate"),
        "max_hr": row.get("max_heartrate"),
        "elevation_m": row.get("elevation_gain_m"),
        "suffer_score": row.get("suffer_score"),
    }


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# 5.1 Basic reading
# ---------------------------------------------------------------------------


def query_list_activities(
    conn: sqlite3.Connection,
    days_back: int = 30,
    sport_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    cutoff = (datetime.now(UTC) - timedelta(days=days_back)).isoformat()
    rows = _rows(
        conn,
        """
        SELECT id, name, sport_type, start_date_local, start_date_utc,
               distance_m, moving_time_s, average_speed_mps,
               average_heartrate, max_heartrate, elevation_gain_m, suffer_score
        FROM activities
        WHERE start_date_utc >= ?
          AND (sport_type = ? OR ? IS NULL)
        ORDER BY start_date_utc DESC
        LIMIT ?
        """,
        (cutoff, sport_type, sport_type, limit),
    )
    return [_fmt_activity(r) for r in rows]


def query_get_activity(
    conn: sqlite3.Connection,
    activity_id: int,
    include_metrics: bool = False,
) -> dict[str, Any] | None:
    row = _one(conn, "SELECT * FROM activities WHERE id = ?", (activity_id,))
    if not row:
        return None
    result = {
        **row,
        "distance_km": round((row.get("distance_m") or 0) / 1000, 3),
        "duration_min": round((row.get("moving_time_s") or 0) / 60, 1),
        "pace": _pace_str(row.get("average_speed_mps")),
    }
    if include_metrics:
        m = _one(
            conn,
            "SELECT * FROM activity_metrics WHERE activity_id = ?",
            (activity_id,),
        )
        result["metrics"] = m or {}
    return result


def query_search_activities(
    conn: sqlite3.Connection,
    name_contains: str | None = None,
    min_distance_km: float | None = None,
    max_distance_km: float | None = None,
    after_date: str | None = None,
    before_date: str | None = None,
    sport_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    conditions = []
    params: list[Any] = []

    if name_contains:
        conditions.append("name LIKE ?")
        params.append(f"%{name_contains}%")
    if min_distance_km is not None:
        conditions.append("distance_m >= ?")
        params.append(min_distance_km * 1000)
    if max_distance_km is not None:
        conditions.append("distance_m <= ?")
        params.append(max_distance_km * 1000)
    if after_date:
        conditions.append("start_date_utc >= ?")
        params.append(after_date)
    if before_date:
        conditions.append("start_date_utc <= ?")
        params.append(before_date + "T23:59:59")
    if sport_type:
        conditions.append("sport_type = ?")
        params.append(sport_type)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = _rows(
        conn,
        f"""
        SELECT id, name, sport_type, start_date_local,
               distance_m, moving_time_s, average_speed_mps,
               average_heartrate, max_heartrate, elevation_gain_m
        FROM activities
        {where}
        ORDER BY start_date_utc DESC
        LIMIT {limit}
        """,
        tuple(params),
    )
    return [_fmt_activity(r) for r in rows]


# ---------------------------------------------------------------------------
# 5.2 Aggregate stats
# ---------------------------------------------------------------------------


def _period_stats_raw(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
    sport_type: str | None = None,
) -> dict[str, Any]:
    sport_clause = "AND sport_type = ?" if sport_type else ""
    params: tuple = (start_date, end_date, sport_type) if sport_type else (start_date, end_date)
    row = _one(
        conn,
        f"""
        SELECT
            COUNT(*) AS n_activities,
            SUM(distance_m) AS total_distance_m,
            SUM(moving_time_s) AS total_moving_time_s,
            SUM(elevation_gain_m) AS total_elevation_m,
            AVG(average_heartrate) AS avg_hr,
            SUM(distance_m) / NULLIF(SUM(moving_time_s), 0) AS avg_speed_mps
        FROM activities
        WHERE DATE(start_date_utc) BETWEEN ? AND ?
          {sport_clause}
        """,
        params,
    )
    metrics_row = _one(
        conn,
        f"""
        SELECT
            SUM(m.trimp) AS total_trimp,
            SUM(m.hr_tss) AS total_hr_tss,
            SUM(m.z1_seconds) AS z1_seconds,
            SUM(m.z2_seconds) AS z2_seconds,
            SUM(m.z3_seconds) AS z3_seconds,
            SUM(m.z4_seconds) AS z4_seconds,
            SUM(m.z5_seconds) AS z5_seconds
        FROM activity_metrics m
        JOIN activities a ON m.activity_id = a.id
        WHERE DATE(a.start_date_utc) BETWEEN ? AND ?
          {sport_clause}
        """,
        params,
    )
    return {**(row or {}), **(metrics_row or {})}


def query_get_period_stats(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
    sport_type: str | None = None,
) -> dict[str, Any]:
    raw = _period_stats_raw(conn, start_date, end_date, sport_type)
    dist_m = raw.get("total_distance_m") or 0
    time_s = raw.get("total_moving_time_s") or 0
    total_z = sum(raw.get(f"z{i}_seconds") or 0 for i in range(1, 6))
    zone_pct = {}
    if total_z > 0:
        for i in range(1, 6):
            z_s = raw.get(f"z{i}_seconds") or 0
            zone_pct[f"z{i}_pct"] = round(z_s / total_z * 100, 1)

    return {
        "period": {"start": start_date, "end": end_date},
        "sport_type_filter": sport_type,
        "n_activities": raw.get("n_activities") or 0,
        "total_distance_km": round(dist_m / 1000, 2),
        "total_time_hours": round(time_s / 3600, 2),
        "total_elevation_m": round((raw.get("total_elevation_m") or 0), 1),
        "avg_hr": round(raw.get("avg_hr") or 0, 1) or None,
        "avg_pace": _pace_str(raw.get("avg_speed_mps")),
        "total_trimp": round(raw.get("total_trimp") or 0, 1),
        "total_hr_tss": round(raw.get("total_hr_tss") or 0, 1),
        "zone_distribution_pct": zone_pct,
    }


def query_compare_periods(
    conn: sqlite3.Connection,
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
    sport_type: str | None = None,
) -> dict[str, Any]:
    a = query_get_period_stats(conn, period_a_start, period_a_end, sport_type)
    b = query_get_period_stats(conn, period_b_start, period_b_end, sport_type)

    def _delta(key: str) -> dict[str, Any]:
        va = a.get(key) or 0
        vb = b.get(key) or 0
        diff = round(va - vb, 2)
        pct = round((va - vb) / vb * 100, 1) if vb else None
        return {"period_a": va, "period_b": vb, "delta": diff, "delta_pct": pct}

    return {
        "period_a": {"start": period_a_start, "end": period_a_end},
        "period_b": {"start": period_b_start, "end": period_b_end},
        "n_activities": _delta("n_activities"),
        "total_distance_km": _delta("total_distance_km"),
        "total_time_hours": _delta("total_time_hours"),
        "total_elevation_m": _delta("total_elevation_m"),
        "total_trimp": _delta("total_trimp"),
    }


def query_get_weekly_breakdown(
    conn: sqlite3.Connection, weeks_back: int = 12
) -> list[dict[str, Any]]:
    cutoff = (date.today() - timedelta(weeks=weeks_back)).isoformat()
    rows = _rows(
        conn,
        """
        SELECT
            strftime('%Y-W%W', start_date_utc) AS week,
            MIN(DATE(start_date_utc)) AS week_start,
            COUNT(*) AS n_activities,
            SUM(distance_m) AS total_distance_m,
            SUM(moving_time_s) AS total_moving_time_s,
            SUM(elevation_gain_m) AS total_elevation_m,
            sport_type
        FROM activities
        WHERE start_date_utc >= ?
        GROUP BY week, sport_type
        ORDER BY week DESC, n_activities DESC
        """,
        (cutoff,),
    )
    by_week: dict[str, dict[str, Any]] = {}
    for r in rows:
        w = r["week"]
        if w not in by_week:
            by_week[w] = {
                "week": w,
                "week_start": r["week_start"],
                "n_activities": 0,
                "total_distance_km": 0.0,
                "total_time_hours": 0.0,
                "total_elevation_m": 0.0,
                "by_sport": {},
            }
        entry = by_week[w]
        entry["n_activities"] += r["n_activities"]
        entry["total_distance_km"] += round((r["total_distance_m"] or 0) / 1000, 2)
        entry["total_time_hours"] += round((r["total_moving_time_s"] or 0) / 3600, 2)
        entry["total_elevation_m"] += round((r["total_elevation_m"] or 0), 1)
        entry["by_sport"][r["sport_type"]] = {
            "n": r["n_activities"],
            "km": round((r["total_distance_m"] or 0) / 1000, 2),
        }

    return list(by_week.values())


# ---------------------------------------------------------------------------
# 5.3 Training load
# ---------------------------------------------------------------------------


def query_get_current_form(conn: sqlite3.Connection) -> dict[str, Any] | None:
    from strava_mcp.analytics.load import tsb_interpretation

    today_str = date.today().isoformat()
    row = _one(
        conn,
        "SELECT * FROM daily_metrics WHERE date <= ? ORDER BY date DESC LIMIT 1",
        (today_str,),
    )
    if not row:
        return None

    ctl = row["ctl"]
    atl = row["atl"]
    tsb = row["tsb"]
    acwr = round(atl / ctl, 2) if ctl and ctl > 0 else None

    cutoff_14 = (date.today() - timedelta(days=13)).isoformat()
    history = _rows(
        conn,
        "SELECT date, ctl, atl, tsb, daily_tss FROM daily_metrics WHERE date >= ? ORDER BY date",
        (cutoff_14,),
    )

    return {
        "as_of": row["date"],
        "ctl": round(ctl, 1),
        "atl": round(atl, 1),
        "tsb": round(tsb, 1),
        "acwr": acwr,
        "form_status": tsb_interpretation(tsb),
        "interpretation": {
            "ctl": "chronic training load (fitness, 42-day EMA)",
            "atl": "acute training load (fatigue, 7-day EMA)",
            "tsb": "training stress balance (form = CTL - ATL)",
            "acwr": "acute:chronic workload ratio (>1.5 = injury risk)",
        },
        "history_14d": history,
    }


def query_get_load_history(conn: sqlite3.Connection, days_back: int = 90) -> list[dict[str, Any]]:
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    return _rows(
        conn,
        """
        SELECT date, ctl, atl, tsb, daily_tss, n_activities,
               total_distance_m, total_moving_time_s
        FROM daily_metrics
        WHERE date >= ?
        ORDER BY date
        """,
        (cutoff,),
    )


def _ef_window_median(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> float | None:
    """Median EF for Run activities started in [start_iso, end_iso)."""
    rows = _rows(
        conn,
        """
        SELECT m.aerobic_efficiency AS ef
        FROM activity_metrics m
        JOIN activities a ON a.id = m.activity_id
        WHERE a.sport_type IN ('Run', 'TrailRun')
          AND a.start_date_local >= ?
          AND a.start_date_local <  ?
          AND m.aerobic_efficiency IS NOT NULL
        """,
        (start_iso, end_iso),
    )
    values = sorted(r["ef"] for r in rows if r.get("ef"))
    if not values:
        return None
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def query_get_injury_risk(conn: sqlite3.Connection) -> dict[str, Any]:
    today = date.today()

    # ACWR from latest daily_metrics
    latest = _one(
        conn,
        "SELECT ctl, atl, tsb FROM daily_metrics WHERE date <= ? ORDER BY date DESC LIMIT 1",
        (today.isoformat(),),
    )
    ctl = (latest or {}).get("ctl") or 0.0
    atl = (latest or {}).get("atl") or 0.0
    acwr = round(atl / ctl, 2) if ctl > 0 else None

    # Weekly volume spike: current week vs avg of last 4 weeks
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    prev4_start = (today - timedelta(weeks=4)).isoformat()

    current_week_row = _one(
        conn,
        "SELECT SUM(total_distance_m) AS vol FROM daily_metrics WHERE date >= ?",
        (week_start,),
    )
    prev4_row = _one(
        conn,
        """
        SELECT SUM(vol) / 4.0 AS avg_vol
        FROM (
            SELECT strftime('%Y-W%W', date) AS wk, SUM(total_distance_m) AS vol
            FROM daily_metrics
            WHERE date >= ? AND date < ?
            GROUP BY wk
        )
        """,
        (prev4_start, week_start),
    )

    cur_vol = (current_week_row or {}).get("vol") or 0.0
    avg_vol = (prev4_row or {}).get("avg_vol") or 0.0
    volume_spike = round(cur_vol / avg_vol, 2) if avg_vol > 0 else None

    # EF degradation: median EF of last 4 weeks vs prior 8 weeks (baseline).
    # Skipping today: a single bad run shouldn't dominate the recent window.
    recent_start = (today - timedelta(weeks=4)).isoformat()
    baseline_start = (today - timedelta(weeks=12)).isoformat()
    recent_ef = _ef_window_median(conn, recent_start, today.isoformat())
    baseline_ef = _ef_window_median(conn, baseline_start, recent_start)

    assessment = assess_injury_risk(
        acwr=acwr,
        volume_spike=volume_spike,
        recent_ef=recent_ef,
        baseline_ef=baseline_ef,
    )

    return {
        **assessment,
        "acwr": acwr,
        "volume_spike_ratio": volume_spike,
        "current_week_km": round(cur_vol / 1000, 1),
        "avg_prev4_weeks_km": round(avg_vol / 1000, 1),
        "recent_ef_median": round(recent_ef, 5) if recent_ef else None,
        "baseline_ef_median": round(baseline_ef, 5) if baseline_ef else None,
        "sweet_zone_acwr": "0.8 – 1.3",
    }


# ---------------------------------------------------------------------------
# 5.4 Efficiency
# ---------------------------------------------------------------------------


def query_get_aerobic_efficiency_trend(
    conn: sqlite3.Connection, months_back: int = 6
) -> dict[str, Any]:
    cutoff = (date.today() - timedelta(days=months_back * 30)).isoformat()
    rows = _rows(
        conn,
        """
        SELECT strftime('%Y-%m', a.start_date_utc) AS month,
               AVG(m.aerobic_efficiency) AS avg_ef,
               COUNT(*) AS n
        FROM activity_metrics m
        JOIN activities a ON m.activity_id = a.id
        WHERE a.start_date_utc >= ?
          AND a.sport_type = 'Run'
          AND m.aerobic_efficiency IS NOT NULL
          AND m.aerobic_efficiency > 0
        GROUP BY month
        ORDER BY month
        """,
        (cutoff,),
    )
    trend_direction = None
    if len(rows) >= 2:
        first_ef = rows[0]["avg_ef"] or 0
        last_ef = rows[-1]["avg_ef"] or 0
        trend_direction = "improving" if last_ef > first_ef else "declining"

    return {
        "months_analyzed": months_back,
        "monthly_ef": [
            {
                "month": r["month"],
                "avg_ef": round(r["avg_ef"] or 0, 5),
                "n_activities": r["n"],
            }
            for r in rows
        ],
        "trend": trend_direction,
        "interpretation": "EF = pace(m/s) / avg_HR. Higher is better. "
        "Rising EF at same HR means improving aerobic fitness.",
    }


def query_get_decoupling_trend(
    conn: sqlite3.Connection, months_back: int = 6
) -> list[dict[str, Any]]:
    cutoff = (date.today() - timedelta(days=months_back * 30)).isoformat()
    rows = _rows(
        conn,
        """
        SELECT a.id, a.name, DATE(a.start_date_utc) AS date,
               a.distance_m, a.moving_time_s,
               m.decoupling_pct
        FROM activity_metrics m
        JOIN activities a ON m.activity_id = a.id
        WHERE a.start_date_utc >= ?
          AND a.sport_type = 'Run'
          AND a.moving_time_s >= 3600
          AND m.decoupling_pct IS NOT NULL
        ORDER BY a.start_date_utc
        """,
        (cutoff,),
    )
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "date": r["date"],
            "distance_km": round((r["distance_m"] or 0) / 1000, 2),
            "duration_min": round((r["moving_time_s"] or 0) / 60, 1),
            "decoupling_pct": round(r["decoupling_pct"] or 0, 2),
            "grade": (
                "excellent"
                if r["decoupling_pct"] < 5
                else ("adequate" if r["decoupling_pct"] < 10 else "needs_work")
            ),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 5.8 Maintenance
# ---------------------------------------------------------------------------


def query_athlete_doctor(conn: sqlite3.Connection, db_path: str) -> dict[str, Any]:
    from strava_mcp.db.repositories import ActivityRepository, SyncStateRepository

    total = ActivityRepository.count(conn)
    by_sport = ActivityRepository.count_by_sport(conn)
    newest = ActivityRepository.get_newest_start_date(conn)
    oldest = ActivityRepository.get_oldest_start_date(conn)
    without_streams = ActivityRepository.count_without_streams(conn)
    last_full = SyncStateRepository.get(conn, "last_full_sync_at")
    last_inc = SyncStateRepository.get(conn, "last_incremental_sync_at")

    metrics_count = (conn.execute("SELECT COUNT(*) FROM activity_metrics").fetchone() or [0])[0]
    daily_count = (conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone() or [0])[0]
    db_size_mb = round(Path(db_path).stat().st_size / 1_048_576, 2) if Path(db_path).exists() else 0

    issues = []
    if total == 0:
        issues.append("No activities synced. Run: strava-mcp sync --full")
    if without_streams == total and total > 0:
        issues.append("No streams synced. Run: strava-mcp sync --streams")
    if metrics_count == 0 and total > 0:
        issues.append("No metrics computed. Run: strava-mcp compute-metrics")
    if not last_full:
        issues.append("Full sync never run. Run: strava-mcp sync --full")

    return {
        "status": "ok" if not issues else "warnings",
        "issues": issues,
        "database": {"path": db_path, "size_mb": db_size_mb},
        "sync": {"last_full": last_full, "last_incremental": last_inc},
        "activities": {
            "total": total,
            "date_range": {"oldest": (oldest or "")[:10], "newest": (newest or "")[:10]},
            "without_streams": without_streams,
            "by_sport": by_sport,
        },
        "metrics": {
            "activity_metrics_rows": metrics_count,
            "daily_metrics_rows": daily_count,
        },
    }


# ---------------------------------------------------------------------------
# 5.5 Predictions
# ---------------------------------------------------------------------------

# Distâncias-padrão para predições e PRs. Fonte única em analytics.best_efforts,
# também usada pela tabela activity_best_efforts (populada por compute-metrics).
from strava_mcp.analytics.best_efforts import STANDARD_DISTANCES  # noqa: E402
from strava_mcp.db.repositories import BestEffortRepository  # noqa: E402


def query_find_personal_records(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Best time at each standard distance, computed from stream-based efforts.

    Returns the fastest segment ever run covering at least `distance_m` —
    including segments inside longer activities (e.g. a 5K split inside a
    10K run). Backed by `activity_best_efforts` from `compute-metrics`.
    Outdoor runs only (indoor treadmill activities lack a distance stream).
    """
    results: list[dict[str, Any]] = []
    for label, dist_m in STANDARD_DISTANCES:
        best = BestEffortRepository.get_fastest(conn, label)
        if best is None:
            results.append(
                {
                    "distance_label": label,
                    "distance_m": dist_m,
                    "status": "no_record",
                }
            )
            continue
        time_s = best["time_s"]
        pace_mps = dist_m / time_s if time_s > 0 else None
        parent_distance = best.get("parent_distance_m") or 0.0
        results.append(
            {
                "distance_label": label,
                "distance_m": dist_m,
                "status": "ok",
                "activity_id": best["activity_id"],
                "name": best["name"],
                "date": str(best.get("start_date_local", ""))[:10],
                "time_s": round(time_s, 1),
                "time_str": _time_str(time_s),
                "pace": _pace_str(pace_mps),
                "avg_hr": best.get("average_heartrate"),
                "segment_start_s": round(best["segment_start_s"], 1),
                "parent_distance_m": round(parent_distance, 1),
                "is_segment": parent_distance > dist_m * 1.05,
            }
        )
    return results


def _time_str(seconds: float | None) -> str | None:
    """Format seconds as H:MM:SS or MM:SS."""
    if seconds is None or seconds <= 0:
        return None
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _closest_pr_to(prs: list[dict[str, Any]], target_distance_m: float) -> dict[str, Any] | None:
    """Pick the PR whose distance is closest to target — preferring the
    largest race distance not exceeding the target if tied."""
    valid = [p for p in prs if p.get("status") == "ok"]
    if not valid:
        return None
    return min(valid, key=lambda p: abs(p["distance_m"] - target_distance_m))


def query_predict_race_time(
    conn: sqlite3.Connection,
    target_distance_m: float,
    source_activity_id: int | None = None,
) -> dict[str, Any]:
    """Predict race time at target distance using Riegel and VDOT.

    If source_activity_id is given, use that activity. Otherwise, pick the
    PR closest to the target distance.
    """
    if target_distance_m <= 0:
        return {"error": "target_distance_m must be positive"}

    if source_activity_id is not None:
        src = _one(
            conn,
            """
            SELECT id, name, start_date_local, distance_m, moving_time_s
            FROM activities
            WHERE id = ?
            """,
            (source_activity_id,),
        )
        if src is None:
            return {"error": f"Activity {source_activity_id} not found"}
        source_label = "user_specified"
    else:
        prs = query_find_personal_records(conn)
        chosen = _closest_pr_to(prs, target_distance_m)
        if chosen is None:
            return {
                "error": "No personal records available to base prediction on.",
                "hint": "Need at least one Run with distance >= 5K.",
            }
        # Use the best-effort segment (distance_m, time_s) directly — these are
        # the target distance and the fastest contiguous time we ran it in,
        # which is the right input for Riegel/VDOT regardless of whether the
        # segment was inside a longer activity.
        src = {
            "id": chosen["activity_id"],
            "name": chosen["name"],
            "start_date_local": chosen["date"],
            "distance_m": chosen["distance_m"],
            "moving_time_s": chosen["time_s"],
        }
        source_label = f"closest_pr ({chosen['distance_label']})"

    prediction = _predict_race_time(
        known_distance_m=src["distance_m"],
        known_time_s=src["moving_time_s"],
        target_distance_m=target_distance_m,
    )

    return {
        "source": {
            "selection": source_label,
            "activity_id": src["id"],
            "name": src["name"],
            "date": str(src.get("start_date_local", ""))[:10],
            "distance_m": round(src["distance_m"], 1),
            "time_s": src["moving_time_s"],
            "time_str": _time_str(src["moving_time_s"]),
        },
        "target_distance_m": target_distance_m,
        "target_distance_km": round(target_distance_m / 1000.0, 4),
        "riegel": (
            {
                **prediction["riegel"],
                "time_str": _time_str(prediction["riegel"]["time_s"]),
            }
            if prediction["riegel"]
            else None
        ),
        "vdot": (
            {
                **prediction["vdot"],
                "time_str": _time_str(prediction["vdot"]["time_s"]),
            }
            if prediction["vdot"]
            else None
        ),
        "note": (
            "Riegel tends to be optimistic for distances much longer than the source race; "
            "VDOT is generally more conservative for marathon projections from half-marathon data."
        ),
    }


# ---------------------------------------------------------------------------
# 5.6 Anomalies
# ---------------------------------------------------------------------------


def query_find_anomalies(
    conn: sqlite3.Connection,
    days_back: int = 90,
    z_threshold: float = 2.0,
    train_window_days: int = 365,
) -> dict[str, Any]:
    """Detect pace anomalies in recent runs against a learned baseline.

    Trains a regression on runs from the last `train_window_days`, then flags
    activities in the last `days_back` whose actual speed deviates by at least
    `z_threshold` standard deviations from the prediction.
    """
    today = date.today()
    train_start = (today - timedelta(days=train_window_days)).isoformat()
    eval_start = (today - timedelta(days=days_back)).isoformat()

    train_rows = _rows(
        conn,
        """
        SELECT id, name, sport_type, start_date_local,
               distance_m, moving_time_s, average_speed_mps,
               average_heartrate, elevation_gain_m
        FROM activities
        WHERE sport_type IN ('Run', 'TrailRun')
          AND start_date_local >= ?
          AND distance_m > 1000
          AND average_heartrate IS NOT NULL
          AND average_speed_mps IS NOT NULL
        """,
        (train_start,),
    )

    model = fit_pace_model(train_rows)
    if model is None:
        return {
            "error": "insufficient_data",
            "hint": (
                f"Need at least 20 runs with HR data in the last "
                f"{train_window_days} days to fit the model."
            ),
            "n_samples": len(train_rows),
        }

    # TSB lookup for cause hints
    tsb_rows = _rows(
        conn,
        "SELECT date, tsb FROM daily_metrics WHERE date >= ?",
        (eval_start,),
    )
    tsb_by_date = {str(r["date"]): r["tsb"] for r in tsb_rows if r.get("tsb") is not None}

    eval_rows = [r for r in train_rows if r["start_date_local"] >= eval_start]
    outliers = detect_outliers(eval_rows, model, z_threshold=z_threshold, tsb_by_date=tsb_by_date)

    return {
        "model": {
            "n_samples": model["n_samples"],
            "residual_std_mps": round(model["residual_std"], 3),
            "feature_names": list(model["feature_names"]),
        },
        "evaluation": {
            "days_back": days_back,
            "z_threshold": z_threshold,
            "n_evaluated": len(eval_rows),
            "n_outliers": len(outliers),
        },
        "outliers": outliers,
    }


# ---------------------------------------------------------------------------
# 5.6 Route clustering and performance drivers
# ---------------------------------------------------------------------------


def query_get_route_clusters(
    conn: sqlite3.Connection,
    days_back: int = 365,
    min_samples: int = 3,
    eps_m: float = 100.0,
) -> dict[str, Any]:
    """Cluster recent runs by recurring start point + distance bin."""
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    rows = _rows(
        conn,
        """
        SELECT id, name, start_date_local, sport_type,
               distance_m, moving_time_s, average_speed_mps, average_heartrate,
               elevation_gain_m, start_latlng_lat, start_latlng_lng
        FROM activities
        WHERE sport_type IN ('Run', 'TrailRun')
          AND start_date_local >= ?
          AND start_latlng_lat IS NOT NULL
          AND start_latlng_lng IS NOT NULL
        """,
        (cutoff,),
    )
    clusters = cluster_routes(rows, eps_m=eps_m, min_samples=min_samples)
    clusters.sort(key=lambda c: c["n_activities"], reverse=True)
    return {
        "params": {"days_back": days_back, "eps_m": eps_m, "min_samples": min_samples},
        "n_activities_evaluated": len(rows),
        "n_clusters": len(clusters),
        "clusters": clusters,
    }


def query_what_drives_my_performance(
    conn: sqlite3.Connection,
    days_back: int = 90,
) -> dict[str, Any]:
    """Train a Gradient Boosting model on recent runs and rank features by
    importance — answers 'what most affects my pace right now?'"""
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    rows = _rows(
        conn,
        """
        SELECT a.id, a.name, a.start_date_local,
               a.distance_m, a.moving_time_s, a.average_speed_mps,
               a.average_heartrate, a.elevation_gain_m,
               m.weather_temp_c AS temperature_c,
               d.ctl, d.atl, d.tsb
        FROM activities a
        LEFT JOIN activity_metrics m ON m.activity_id = a.id
        LEFT JOIN daily_metrics d ON d.date = DATE(a.start_date_local)
        WHERE a.sport_type IN ('Run', 'TrailRun')
          AND a.start_date_local >= ?
          AND a.distance_m > 1000
        """,
        (cutoff,),
    )

    fitted = fit_driver_model(rows)
    if fitted is None:
        return {
            "error": "insufficient_data",
            "hint": ("Need at least 30 runs with HR data in the selected window to fit the model."),
            "n_samples": len(rows),
        }

    drivers = rank_drivers(fitted)
    return {
        "params": {"days_back": days_back},
        "model": {
            "n_samples": fitted["n_samples"],
            "r2_train": round(fitted["r2_train"], 3),
        },
        "drivers": drivers,
    }


# ---------------------------------------------------------------------------
# 5.7 Narrative and diagnosis
# ---------------------------------------------------------------------------


def _activities_in_period(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    """Activities + their metrics within [start_date, end_date]."""
    return _rows(
        conn,
        """
        SELECT a.id, a.name, a.sport_type, a.start_date_local,
               a.distance_m, a.moving_time_s, a.average_speed_mps,
               a.average_heartrate, a.elevation_gain_m,
               m.trimp, m.hr_tss, m.aerobic_efficiency
        FROM activities a
        LEFT JOIN activity_metrics m ON m.activity_id = a.id
        WHERE DATE(a.start_date_local) BETWEEN ? AND ?
        ORDER BY a.start_date_local
        """,
        (start_date, end_date),
    )


def query_generate_period_narrative(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Build a structured narrative of a training period.

    Output is data-only (numbers, highlights, concerns); the LLM consuming the
    MCP tool is expected to write the prose.
    """
    activities = _activities_in_period(conn, start_date, end_date)
    period_stats = query_get_period_stats(conn, start_date, end_date)

    # Prior period of the same length for comparison
    try:
        d0 = date.fromisoformat(start_date)
        d1 = date.fromisoformat(end_date)
    except ValueError:
        return {"error": "invalid_date_format", "hint": "use YYYY-MM-DD"}
    span = (d1 - d0).days
    prior_start = (d0 - timedelta(days=span + 1)).isoformat()
    prior_end = (d0 - timedelta(days=1)).isoformat()
    prior_stats = query_get_period_stats(conn, prior_start, prior_end)

    highlights = select_highlights(activities)

    load_history = _rows(
        conn,
        "SELECT date, ctl, atl, tsb FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
        (start_date, end_date),
    )
    form_change = summarize_form_change(load_history)

    high_acwr_days = sum(
        1
        for d in load_history
        if (d.get("ctl") or 0) > 0 and ((d.get("atl") or 0) / (d.get("ctl") or 1)) > 1.3
    )

    anomalies = query_find_anomalies(
        conn,
        days_back=max(span + 1, 30),
        z_threshold=2.0,
    )
    anomalies_in_period = [
        o for o in anomalies.get("outliers", []) if start_date <= o["date"] <= end_date
    ]
    concerns = count_concerns(activities, len(anomalies_in_period), high_acwr_days)

    return assemble_narrative(
        period={"start": start_date, "end": end_date, "span_days": span + 1},
        period_stats=period_stats,
        prior_stats=prior_stats,
        highlights=highlights,
        form_change=form_change,
        concerns=concerns,
    )


def _monthly_ef_series(conn: sqlite3.Connection, weeks_back: int) -> list[tuple[int, float]]:
    """Median EF per month over the last `weeks_back` weeks. Indexed 0..N."""
    cutoff = (date.today() - timedelta(weeks=weeks_back)).isoformat()
    rows = _rows(
        conn,
        """
        SELECT strftime('%Y-%m', a.start_date_local) AS month,
               m.aerobic_efficiency AS ef
        FROM activity_metrics m
        JOIN activities a ON a.id = m.activity_id
        WHERE a.sport_type IN ('Run','TrailRun')
          AND a.start_date_local >= ?
          AND m.aerobic_efficiency IS NOT NULL
        """,
        (cutoff,),
    )
    by_month: dict[str, list[float]] = {}
    for r in rows:
        by_month.setdefault(r["month"], []).append(r["ef"])
    months = sorted(by_month.keys())
    out: list[tuple[int, float]] = []
    for i, m in enumerate(months):
        vals = sorted(by_month[m])
        median = (
            vals[len(vals) // 2]
            if len(vals) % 2
            else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        )
        out.append((i, median))
    return out


def _pace_at_lthr_series(
    conn: sqlite3.Connection, weeks_back: int, lthr: float, tolerance: float = 5.0
) -> list[tuple[int, float]]:
    """Average speed for runs whose avg HR is within ±tolerance of LTHR.
    Bucketed by week index (oldest = 0)."""
    cutoff = date.today() - timedelta(weeks=weeks_back)
    rows = _rows(
        conn,
        """
        SELECT a.start_date_local AS dt, a.average_speed_mps AS v, a.average_heartrate AS hr
        FROM activities a
        WHERE a.sport_type IN ('Run','TrailRun')
          AND a.start_date_local >= ?
          AND a.average_heartrate BETWEEN ? AND ?
          AND a.average_speed_mps IS NOT NULL
          AND a.distance_m >= 5000
        ORDER BY a.start_date_local
        """,
        (cutoff.isoformat(), lthr - tolerance, lthr + tolerance),
    )
    if not rows:
        return []

    week_buckets: dict[int, list[float]] = {}
    for r in rows:
        run_date = date.fromisoformat(str(r["dt"])[:10])
        week_idx = (run_date - cutoff).days // 7
        week_buckets.setdefault(week_idx, []).append(r["v"])
    return [(w, sum(v) / len(v)) for w, v in sorted(week_buckets.items())]


def _days_since_last_pr(conn: sqlite3.Connection) -> int | None:
    """Days since the most recent PR (across standard distances)."""
    prs = query_find_personal_records(conn)
    valid_dates = [p["date"] for p in prs if p.get("status") == "ok" and p.get("date")]
    if not valid_dates:
        return None
    most_recent = max(valid_dates)
    try:
        d = date.fromisoformat(most_recent)
    except ValueError:
        return None
    return (date.today() - d).days


def _athlete_lthr(conn: sqlite3.Connection) -> float:
    row = _one(conn, "SELECT value FROM athlete_config WHERE key='lthr'", ())
    if row and row.get("value"):
        try:
            return float(row["value"])
        except (TypeError, ValueError):
            pass
    return 177.0  # fallback to the known athlete LTHR from CLAUDE.md


def query_diagnose_plateau(
    conn: sqlite3.Connection,
    weeks_back: int = 12,
) -> dict[str, Any]:
    """Run all four plateau indicators and return the assembled diagnosis."""
    lthr = _athlete_lthr(conn)

    ef_series = _monthly_ef_series(conn, weeks_back)
    pace_series = _pace_at_lthr_series(conn, weeks_back, lthr)

    # Zone seconds for the analyzed window
    cutoff = (date.today() - timedelta(weeks=weeks_back)).isoformat()
    zone_row = (
        _one(
            conn,
            """
        SELECT
            COALESCE(SUM(m.z1_seconds),0) AS z1_seconds,
            COALESCE(SUM(m.z2_seconds),0) AS z2_seconds,
            COALESCE(SUM(m.z3_seconds),0) AS z3_seconds,
            COALESCE(SUM(m.z4_seconds),0) AS z4_seconds,
            COALESCE(SUM(m.z5_seconds),0) AS z5_seconds
        FROM activity_metrics m
        JOIN activities a ON a.id = m.activity_id
        WHERE a.sport_type IN ('Run','TrailRun')
          AND a.start_date_local >= ?
        """,
            (cutoff,),
        )
        or {}
    )

    diagnosis = assess_plateau(
        ef=ef_trend(ef_series),
        pace_lthr=pace_at_lthr_trend(pace_series),
        pr_age=days_since_last_pr(_days_since_last_pr(conn)),
        intensity=intensity_variety(zone_row),
    )
    diagnosis["params"] = {"weeks_back": weeks_back, "lthr_bpm": lthr}
    return diagnosis
