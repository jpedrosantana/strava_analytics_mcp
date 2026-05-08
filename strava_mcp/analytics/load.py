import math
from datetime import date
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# TRIMP (Banister)
# ---------------------------------------------------------------------------

_TRIMP_COEFF = {
    "male": (0.64, 1.92),
    "female": (0.86, 1.67),
}


def trimp(
    moving_time_s: int,
    average_heartrate: float,
    hr_rest: float,
    hr_max: float,
    sex: str = "male",
) -> float | None:
    """Banister TRIMP score.

    sex: 'male' or 'female'
    Returns None if HR data is insufficient.
    """
    if not average_heartrate or not hr_max or hr_max <= hr_rest:
        return None
    duration_min = moving_time_s / 60.0
    delta_hr = (average_heartrate - hr_rest) / (hr_max - hr_rest)
    delta_hr = max(0.0, min(delta_hr, 1.0))
    a, b = _TRIMP_COEFF.get(sex, _TRIMP_COEFF["male"])
    return duration_min * delta_hr * a * math.exp(b * delta_hr)


# ---------------------------------------------------------------------------
# hrTSS (TrainingPeaks heart-rate based TSS)
# ---------------------------------------------------------------------------


def hr_tss(
    moving_time_s: int,
    average_heartrate: float,
    lthr: float,
) -> float | None:
    """Heart-rate TSS approximation for continuous efforts.

    IF ≈ avg_hr / LTHR  (valid for sub-threshold sustained work).
    """
    if not average_heartrate or not lthr or lthr <= 0:
        return None
    if_ = average_heartrate / lthr
    return (moving_time_s * if_**2 * 100) / 3600


# ---------------------------------------------------------------------------
# CTL / ATL / TSB  (Banister Performance Model)
# ---------------------------------------------------------------------------

_CTL_TC = 42  # days
_ATL_TC = 7   # days


def _exp_decay(tc: int) -> float:
    return math.exp(-1.0 / tc)


def build_daily_load(
    metrics_df: pd.DataFrame,
    start_date: date,
    end_date: date,
    tss_column: str = "trimp",
) -> pd.DataFrame:
    """Aggregate daily TSS from activity_metrics rows.

    metrics_df must have columns: activity_date (date), <tss_column>
    Returns DataFrame with date, daily_tss.
    """
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    daily = (
        metrics_df.groupby("activity_date")[tss_column]
        .sum()
        .reindex(pd.DatetimeIndex(dates).date)
        .fillna(0.0)
        .reset_index()
    )
    daily.columns = ["date", "daily_tss"]
    return daily


def compute_ctl_atl_tsb(
    daily_tss: list[float],
    dates: list[date],
    init_ctl: float | None = None,
    init_atl: float | None = None,
) -> list[dict[str, Any]]:
    """Compute CTL, ATL and TSB for a sequence of daily TSS values.

    Initialization: if init values not given, use mean of first 14 non-zero days
    (or all days if fewer than 14 available).
    """
    if not daily_tss:
        return []

    if init_ctl is None or init_atl is None:
        seed = [t for t in daily_tss[:14] if t > 0]
        seed_val = sum(seed) / len(seed) if seed else 0.0
        init_ctl = seed_val
        init_atl = seed_val

    ctl_decay = _exp_decay(_CTL_TC)
    atl_decay = _exp_decay(_ATL_TC)

    results: list[dict[str, Any]] = []
    ctl = init_ctl
    atl = init_atl

    for d, tss in zip(dates, daily_tss, strict=False):
        tsb = ctl - atl
        results.append(
            {
                "date": d,
                "daily_tss": tss,
                "ctl": round(ctl, 2),
                "atl": round(atl, 2),
                "tsb": round(tsb, 2),
            }
        )
        ctl = ctl * ctl_decay + tss * (1 - ctl_decay)
        atl = atl * atl_decay + tss * (1 - atl_decay)

    return results


def tsb_interpretation(tsb: float) -> str:
    """Human-readable TSB interpretation."""
    if tsb > 25:
        return "very_rested"
    if tsb > 5:
        return "race_ready"
    if tsb > -10:
        return "productive"
    if tsb > -30:
        return "loaded"
    return "high_risk"


def best_tss_for_activity(
    activity: dict[str, Any],
    trimp_val: float | None,
    hr_tss_val: float | None,
    r_tss_val: float | None,
) -> float | None:
    """Pick the best available TSS metric for a given activity.

    Priority: rTSS (most precise) > hrTSS > TRIMP > None.
    rTSS only used for GPS-based Run/Ride activities.
    """
    sport = activity.get("sport_type", "")
    is_gps = sport in ("Run", "Ride", "VirtualRide", "TrailRun")

    if is_gps and r_tss_val is not None:
        return r_tss_val
    if hr_tss_val is not None:
        return hr_tss_val
    return trimp_val
