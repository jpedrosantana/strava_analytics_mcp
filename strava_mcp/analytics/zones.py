from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

# Friel zones as (name, lo_pct_lthr, hi_pct_lthr)
_FRIEL_ZONES: list[tuple[str, float, float]] = [
    ("Z1", 0.00, 0.81),
    ("Z2", 0.81, 0.90),
    ("Z3", 0.90, 0.94),
    ("Z4", 0.94, 1.00),
    ("Z5a", 1.00, 1.03),
    ("Z5b", 1.03, 1.07),
    ("Z5c", 1.07, 9.99),
]

# Maps Friel 7-zone schema to 5-zone schema stored in activity_metrics
_ZONE_COLUMN = {
    "Z1": "z1_seconds",
    "Z2": "z2_seconds",
    "Z3": "z3_seconds",
    "Z4": "z4_seconds",
    "Z5a": "z5_seconds",
    "Z5b": "z5_seconds",
    "Z5c": "z5_seconds",
}


def estimate_hrmax(runs_df: pd.DataFrame) -> float | None:
    """99.5th percentile of max_heartrate, excluding implausible values."""
    hr = runs_df[runs_df["max_heartrate"].notna() & (runs_df["max_heartrate"] < 300)][
        "max_heartrate"
    ]
    if len(hr) < 3:
        return None
    return float(np.percentile(hr, 99.5))


def estimate_lthr(runs_df: pd.DataFrame, today: date | None = None) -> float | None:
    """90th percentile of average_heartrate for sustained runs (> 20 min).

    Approximates "tempo effort HR" without needing streams.
    Uses last 90 days first; falls back to all data if fewer than 5 runs.
    """
    if today is None:
        today = date.today()
    cutoff = today - timedelta(days=90)

    mask_base = runs_df["average_heartrate"].notna() & (runs_df["moving_time_s"] > 1200)
    recent = runs_df[mask_base & (pd.to_datetime(runs_df["start_date_utc"]).dt.date >= cutoff)]
    subset = recent if len(recent) >= 5 else runs_df[mask_base]

    if len(subset) < 5:
        return None
    return float(np.percentile(subset["average_heartrate"], 90))


def zone_thresholds(lthr: float) -> list[dict[str, Any]]:
    """Returns zone thresholds in bpm given LTHR."""
    return [
        {"zone": name, "min_bpm": lthr * lo, "max_bpm": lthr * hi} for name, lo, hi in _FRIEL_ZONES
    ]


def classify_hr(hr_bpm: float, lthr: float) -> str:
    """Returns the Friel zone name for a given HR and LTHR."""
    pct = hr_bpm / lthr
    for name, lo, hi in _FRIEL_ZONES:
        if lo <= pct < hi:
            return name
    return "Z5c"


def zone_seconds_from_summary(
    average_heartrate: float,
    moving_time_s: int,
    lthr: float,
) -> dict[str, int]:
    """Approximate zone distribution using only summary HR.

    Assigns all moving time to the zone matching the average HR.
    Use stream-based analysis for precise results.
    """
    zone = classify_hr(average_heartrate, lthr)
    result: dict[str, int] = {
        "z1_seconds": 0,
        "z2_seconds": 0,
        "z3_seconds": 0,
        "z4_seconds": 0,
        "z5_seconds": 0,
    }
    result[_ZONE_COLUMN[zone]] = moving_time_s
    return result


def zone_seconds_from_stream(
    hr_stream: list[float],
    lthr: float,
) -> dict[str, int]:
    """Precise zone distribution from heartrate stream (1-second resolution)."""
    result: dict[str, int] = {
        "z1_seconds": 0,
        "z2_seconds": 0,
        "z3_seconds": 0,
        "z4_seconds": 0,
        "z5_seconds": 0,
    }
    for hr in hr_stream:
        if hr and hr > 0:
            zone = classify_hr(hr, lthr)
            result[_ZONE_COLUMN[zone]] += 1
    return result
