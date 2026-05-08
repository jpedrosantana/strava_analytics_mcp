from typing import Any

from strava_mcp.analytics.ngp import ngp_from_stream, ngp_from_summary


def aerobic_efficiency(ngp_mps: float, average_heartrate: float) -> float | None:
    """Aerobic Efficiency = NGP (m/s) / avg HR (bpm).

    Higher is better: same HR at faster pace = better aerobic fitness.
    """
    if not ngp_mps or not average_heartrate or average_heartrate <= 0:
        return None
    return ngp_mps / average_heartrate


def _ef_from_half(
    distance_stream: list[float],
    altitude_stream: list[float],
    time_stream: list[int],
    hr_stream: list[float],
    start_idx: int,
    end_idx: int,
) -> float | None:
    d = distance_stream[start_idx:end_idx]
    a = altitude_stream[start_idx:end_idx]
    t = time_stream[start_idx:end_idx]
    h = hr_stream[start_idx:end_idx]
    if len(d) < 2:
        return None
    ngp = ngp_from_stream(d, a, t)
    valid_hr = [x for x in h if x and x > 0]
    if ngp is None or not valid_hr:
        return None
    avg_hr = sum(valid_hr) / len(valid_hr)
    return aerobic_efficiency(ngp, avg_hr)


def decoupling_from_stream(
    distance_stream: list[float],
    altitude_stream: list[float],
    time_stream: list[int],
    hr_stream: list[float],
    warmup_seconds: int = 600,
) -> float | None:
    """Aerobic decoupling (Pa:HR) from per-second streams.

    Splits the run (after warmup) in two equal halves; computes EF in each.
    Returns (EF_first - EF_second) / EF_first × 100.
    Positive = cardiac drift (fitness cost); negative = warming up / unusual.
    """
    if not time_stream or len(time_stream) < 60:
        return None

    start_t = time_stream[0] + warmup_seconds
    core_start = next((i for i, t in enumerate(time_stream) if t >= start_t), None)
    if core_start is None or core_start >= len(time_stream) - 2:
        return None

    core_len = len(time_stream) - core_start
    mid = core_start + core_len // 2

    ef1 = _ef_from_half(distance_stream, altitude_stream, time_stream, hr_stream, core_start, mid)
    ef2 = _ef_from_half(
        distance_stream, altitude_stream, time_stream, hr_stream, mid, len(time_stream)
    )

    if ef1 is None or ef2 is None or ef1 == 0:
        return None
    return (ef1 - ef2) / ef1 * 100


def decoupling_from_summary(
    activity: dict[str, Any],
    lthr: float | None,
) -> float | None:
    """Approximate decoupling from summary data.

    Not meaningful without streams — returns None to signal unavailability.
    Only stream-based decoupling is reliable.
    """
    return None


def activity_efficiency_metrics(
    activity: dict[str, Any],
    distance_stream: list[float] | None = None,
    altitude_stream: list[float] | None = None,
    time_stream: list[int] | None = None,
    hr_stream: list[float] | None = None,
) -> dict[str, float | None]:
    """Compute EF and decoupling for an activity."""
    dist = activity.get("distance_m") or 0.0
    time_ = activity.get("moving_time_s") or 0
    gain = activity.get("elevation_gain_m") or 0.0
    avg_hr = activity.get("average_heartrate")

    has_streams = all(
        s is not None for s in [distance_stream, altitude_stream, time_stream, hr_stream]
    )

    if has_streams:
        assert distance_stream and altitude_stream and time_stream and hr_stream
        ngp = ngp_from_stream(distance_stream, altitude_stream, time_stream)
        ef = aerobic_efficiency(ngp, avg_hr) if (ngp and avg_hr) else None
        decoupling = decoupling_from_stream(
            distance_stream, altitude_stream, time_stream, hr_stream
        )
    else:
        ngp = ngp_from_summary(dist, time_, gain)
        ef = aerobic_efficiency(ngp, avg_hr) if (ngp and avg_hr) else None
        decoupling = None

    return {"aerobic_efficiency": ef, "decoupling_pct": decoupling}
