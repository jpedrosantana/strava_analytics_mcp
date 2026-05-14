"""Full analytics compute pipeline: activity_metrics + daily_metrics."""

import json
import sqlite3
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from strava_mcp.analytics.best_efforts import best_efforts_for_activity
from strava_mcp.analytics.efficiency import activity_efficiency_metrics
from strava_mcp.analytics.load import (
    best_tss_for_activity,
    compute_ctl_atl_tsb,
    hr_tss,
    trimp,
)
from strava_mcp.analytics.ngp import activity_ngp_metrics
from strava_mcp.analytics.zones import (
    estimate_hrmax,
    estimate_lthr,
    zone_seconds_from_stream,
    zone_seconds_from_summary,
)
from strava_mcp.db.migrations import apply_migrations
from strava_mcp.db.repositories import (
    AthleteConfigRepository,
    BestEffortRepository,
    MetricsRepository,
    StreamRepository,
)

_DEFAULT_HR_REST = 50.0
_DEFAULT_SEX = "male"


def _parse_date(iso: str) -> date:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()


def _load_config(conn: sqlite3.Connection) -> dict[str, Any]:
    cfg = AthleteConfigRepository.get_all(conn)
    return {
        "hr_rest": float(cfg.get("hr_rest") or _DEFAULT_HR_REST),
        "hr_max": float(cfg["hr_max"]) if cfg.get("hr_max") else None,
        "lthr": float(cfg["lthr"]) if cfg.get("lthr") else None,
        "threshold_pace_mps": (
            float(cfg["threshold_pace_mps"]) if cfg.get("threshold_pace_mps") else None
        ),
        "sex": cfg.get("sex") or _DEFAULT_SEX,
    }


def _runs_df(activities: list[dict[str, Any]]) -> pd.DataFrame:
    runs = [a for a in activities if a.get("sport_type") == "Run"]
    if not runs:
        return pd.DataFrame()
    df = pd.DataFrame(runs)
    df["start_date_utc"] = pd.to_datetime(df["start_date_utc"], utc=True)
    return df


def compute_activity_metrics(
    activity: dict[str, Any],
    hr_rest: float,
    hr_max: float | None,
    lthr: float | None,
    threshold_pace_mps: float | None,
    sex: str = "male",
    distance_stream: list[float] | None = None,
    altitude_stream: list[float] | None = None,
    time_stream: list[int] | None = None,
    hr_stream: list[float] | None = None,
) -> dict[str, Any]:
    """Compute all per-activity metrics, using streams when available."""
    avg_hr = activity.get("average_heartrate")
    moving_time = activity.get("moving_time_s") or 0

    trimp_val = (
        trimp(moving_time, avg_hr, hr_rest, hr_max, sex)
        if (avg_hr and hr_max and moving_time)
        else None
    )
    hr_tss_val = hr_tss(moving_time, avg_hr, lthr) if (avg_hr and lthr and moving_time) else None

    ngp_metrics = activity_ngp_metrics(activity, threshold_pace_mps)
    eff_metrics = activity_efficiency_metrics(
        activity,
        distance_stream=distance_stream,
        altitude_stream=altitude_stream,
        time_stream=time_stream,
        hr_stream=hr_stream,
    )

    zone_secs: dict[str, int] = {
        "z1_seconds": 0,
        "z2_seconds": 0,
        "z3_seconds": 0,
        "z4_seconds": 0,
        "z5_seconds": 0,
    }
    if lthr:
        # Preferir cálculo amostra-a-amostra quando há stream de FC; cai no
        # fallback de média só quando o stream estiver indisponível (atividades
        # antigas sem download de streams).
        if hr_stream:
            zone_secs = zone_seconds_from_stream(hr_stream, lthr)
        elif avg_hr and moving_time:
            zone_secs = zone_seconds_from_summary(avg_hr, moving_time, lthr)

    # Strava entrega average_temp dentro do raw_json (sensor do Garmin/relógio).
    # Cobre ~64% das corridas (atividades indoor / sem sensor de temp ficam None).
    # Sem essa extração, weather_temp_c fica NULL no banco e what_drives_my_performance
    # reporta importância ~0 para temperatura mesmo havendo sinal disponível.
    weather_temp_c: float | None = None
    raw_json_str = activity.get("raw_json")
    if raw_json_str:
        try:
            raw = json.loads(raw_json_str)
            temp = raw.get("average_temp")
            if temp is not None:
                weather_temp_c = float(temp)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return {
        "trimp": trimp_val,
        "hr_tss": hr_tss_val,
        "r_tss": ngp_metrics.get("r_tss"),
        "ngp_mps": ngp_metrics.get("ngp_mps"),
        "intensity_factor": ngp_metrics.get("intensity_factor"),
        "aerobic_efficiency": eff_metrics.get("aerobic_efficiency"),
        "decoupling_pct": eff_metrics.get("decoupling_pct"),
        "weather_temp_c": weather_temp_c,
        **zone_secs,
    }


def compute_all_metrics(
    db_path: str,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, int]:
    """Recompute activity_metrics and daily_metrics for all activities.

    Returns {'activities': N, 'daily_rows': M}.
    """
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        activities = MetricsRepository.get_all_activities_for_metrics(conn)
        cfg = _load_config(conn)

    if not activities:
        return {"activities": 0, "daily_rows": 0}

    runs_df = _runs_df(activities)

    hr_max = cfg["hr_max"]
    lthr = cfg["lthr"]
    if not runs_df.empty:
        if hr_max is None:
            hr_max = estimate_hrmax(runs_df)
        if lthr is None:
            lthr = estimate_lthr(runs_df)

    hr_rest = cfg["hr_rest"]
    threshold_pace_mps = cfg["threshold_pace_mps"]
    sex = cfg["sex"]

    total = len(activities)
    daily_tss_by_date: dict[date, float] = defaultdict(float)
    daily_distance_by_date: dict[date, float] = defaultdict(float)
    daily_time_by_date: dict[date, int] = defaultdict(int)
    daily_count_by_date: dict[date, int] = defaultdict(int)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        activity_ids_with_streams = StreamRepository.get_activity_ids_with_streams(conn)
        for idx, activity in enumerate(activities):
            distance_stream = altitude_stream = time_stream = hr_stream = None
            if activity.get("sport_type") == "Run" and activity["id"] in activity_ids_with_streams:
                distance_stream = StreamRepository.get(conn, activity["id"], "distance")
                altitude_stream = StreamRepository.get(conn, activity["id"], "altitude")
                time_stream = StreamRepository.get(conn, activity["id"], "time")
                hr_stream = StreamRepository.get(conn, activity["id"], "heartrate")

            metrics = compute_activity_metrics(
                activity,
                hr_rest=hr_rest,
                hr_max=hr_max,
                lthr=lthr,
                threshold_pace_mps=threshold_pace_mps,
                sex=sex,
                distance_stream=distance_stream,
                altitude_stream=altitude_stream,
                time_stream=time_stream,
                hr_stream=hr_stream,
            )
            MetricsRepository.upsert_activity_metrics(conn, activity["id"], metrics)

            if activity.get("sport_type") == "Run" and distance_stream and time_stream:
                efforts = best_efforts_for_activity(distance_stream, time_stream)
                BestEffortRepository.upsert_many(conn, activity["id"], efforts)

            act_date = _parse_date(activity["start_date_utc"])
            tss = best_tss_for_activity(
                activity,
                metrics.get("trimp"),
                metrics.get("hr_tss"),
                metrics.get("r_tss"),
            )
            daily_tss_by_date[act_date] += tss or 0.0
            daily_distance_by_date[act_date] += activity.get("distance_m") or 0.0
            daily_time_by_date[act_date] += activity.get("moving_time_s") or 0
            daily_count_by_date[act_date] += 1

            if progress:
                progress(idx + 1, total)

    all_dates = sorted(daily_tss_by_date.keys())
    if not all_dates:
        return {"activities": total, "daily_rows": 0}

    date_range = [
        all_dates[0] + timedelta(days=i) for i in range((all_dates[-1] - all_dates[0]).days + 1)
    ]
    daily_tss_seq = [daily_tss_by_date.get(d, 0.0) for d in date_range]

    ctl_atl_tsb = compute_ctl_atl_tsb(daily_tss_seq, date_range)

    daily_rows = []
    for row in ctl_atl_tsb:
        d = row["date"]
        daily_rows.append(
            {
                "date": str(d),
                "daily_tss": row["daily_tss"],
                "ctl": row["ctl"],
                "atl": row["atl"],
                "tsb": row["tsb"],
                "n_activities": daily_count_by_date.get(d, 0),
                "total_distance_m": daily_distance_by_date.get(d, 0.0),
                "total_moving_time_s": daily_time_by_date.get(d, 0),
            }
        )

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        MetricsRepository.upsert_daily_metrics(conn, daily_rows)

    return {"activities": total, "daily_rows": len(daily_rows)}
