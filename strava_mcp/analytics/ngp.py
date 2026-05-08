from typing import Any

import numpy as np


def _minetti_cost(grade: float) -> float:
    """Metabolic cost [W/kg per m/s] at a given grade (Minetti et al. 2002).

    grade: fraction (e.g. 0.05 for 5% uphill, -0.05 for 5% downhill)
    Polynomial fit valid for -0.45 ≤ grade ≤ +0.45.
    """
    g = np.clip(grade, -0.45, 0.45)
    return 155.4 * g**5 - 30.4 * g**4 - 43.3 * g**3 + 46.3 * g**2 + 19.5 * g + 3.6


_FLAT_COST = _minetti_cost(0.0)


def grade_factor(grade_fraction: float) -> float:
    """Cost ratio relative to flat running (grade as fraction, e.g. 0.05)."""
    return _minetti_cost(grade_fraction) / _FLAT_COST


def ngp_from_summary(
    distance_m: float,
    moving_time_s: int,
    elevation_gain_m: float,
) -> float | None:
    """NGP in m/s from activity summary (approximation, positive gain only).

    Uses net elevation gain over total distance as an average grade.
    For stream-based NGP see ngp_from_stream.
    """
    if not distance_m or not moving_time_s or distance_m < 100:
        return None
    speed_mps = distance_m / moving_time_s
    net_grade = (elevation_gain_m or 0.0) / distance_m
    gf = grade_factor(net_grade)
    return speed_mps * gf


def ngp_from_stream(
    distance_stream: list[float],
    altitude_stream: list[float],
    time_stream: list[int],
) -> float | None:
    """NGP in m/s from per-second activity streams (precise).

    Segments < 5 m are skipped to reduce noise.
    """
    if not distance_stream or not altitude_stream or not time_stream:
        return None
    if len(distance_stream) < 2:
        return None

    weighted_sum = 0.0
    total_time = 0.0

    for i in range(1, len(distance_stream)):
        seg_dist = distance_stream[i] - distance_stream[i - 1]
        seg_time = time_stream[i] - time_stream[i - 1]
        seg_alt = altitude_stream[i] - altitude_stream[i - 1]
        if seg_dist <= 0 or seg_time <= 0:
            continue
        seg_grade = seg_alt / seg_dist
        seg_speed = seg_dist / seg_time
        gf = grade_factor(seg_grade)
        weighted_sum += seg_speed * gf * seg_time
        total_time += seg_time

    if total_time <= 0:
        return None
    return weighted_sum / total_time


def intensity_factor(ngp_mps: float, threshold_pace_mps: float) -> float | None:
    """Intensity Factor = NGP / threshold pace (both in m/s)."""
    if not threshold_pace_mps or threshold_pace_mps <= 0:
        return None
    return ngp_mps / threshold_pace_mps


def r_tss(
    moving_time_s: int,
    ngp_mps: float,
    threshold_pace_mps: float,
) -> float | None:
    """Running TSS from NGP and threshold pace."""
    if_ = intensity_factor(ngp_mps, threshold_pace_mps)
    if if_ is None:
        return None
    return (moving_time_s * if_**2 * 100) / 3600


def activity_ngp_metrics(
    activity: dict[str, Any],
    threshold_pace_mps: float | None,
    distance_stream: list[float] | None = None,
    altitude_stream: list[float] | None = None,
    time_stream: list[int] | None = None,
) -> dict[str, float | None]:
    """Compute NGP, IF and rTSS for an activity."""
    dist = activity.get("distance_m") or 0.0
    time_ = activity.get("moving_time_s") or 0
    gain = activity.get("elevation_gain_m") or 0.0

    if distance_stream and altitude_stream and time_stream:
        ngp = ngp_from_stream(distance_stream, altitude_stream, time_stream)
    else:
        ngp = ngp_from_summary(dist, time_, gain)

    if_ = intensity_factor(ngp, threshold_pace_mps) if (ngp and threshold_pace_mps) else None
    rtss = r_tss(time_, ngp, threshold_pace_mps) if (ngp and threshold_pace_mps and time_) else None

    return {"ngp_mps": ngp, "intensity_factor": if_, "r_tss": rtss}
