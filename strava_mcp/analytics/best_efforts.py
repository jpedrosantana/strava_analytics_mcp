"""Best efforts em distâncias-padrão via janela deslizante sobre streams.

Strava's time stream is moving time (paused periods excluded), so the best
effort returned here aligns with how Strava itself reports best efforts —
it's the moving time over the fastest segment that covers `target_m`.
"""

from typing import Any

# Tighter than any human world record (1K WR ≈ 7.58 m/s for ~131 s). Used to
# clamp per-sample velocity, neutralising GPS jumps (tunnels, signal loss)
# before the sliding window runs. The broader data-quality layer described
# in BACKLOG.md will revisit this with race-distance overrides etc.; for now
# this single ceiling is enough to keep best-effort PRs physically plausible.
_MAX_PLAUSIBLE_MPS = 7.5


def _clamp_gps_jumps(
    distance_stream: list[float],
    time_stream: list[int] | list[float],
) -> list[float]:
    """Return distance_stream with impossibly-fast samples clamped.

    For each adjacent pair (j-1, j), if `(d[j]-d[j-1]) / (t[j]-t[j-1])` exceeds
    `_MAX_PLAUSIBLE_MPS`, the excess is removed and all subsequent samples are
    shifted by the same amount. The time stream is left intact — this preserves
    the relative time progression while wiping bogus distance jumps.
    """
    n = len(distance_stream)
    if n != len(time_stream) or n < 2:
        return list(distance_stream)
    out = [distance_stream[0]]
    shift = 0.0
    for j in range(1, n):
        dt = time_stream[j] - time_stream[j - 1]
        raw_dd = distance_stream[j] - distance_stream[j - 1]
        if dt > 0 and raw_dd > 0:
            max_dd = dt * _MAX_PLAUSIBLE_MPS
            if raw_dd > max_dd:
                shift += raw_dd - max_dd
        out.append(distance_stream[j] - shift)
    return out


# Standard distances for PRs and predictions. Single source of truth — also
# imported by mcp_server.queries. 1K added (spec D4 requires it; intervalados
# gravitate around it); 25K/30K kept since the athlete has those as race
# targets before the marathon.
STANDARD_DISTANCES: list[tuple[str, float]] = [
    ("1K", 1000.0),
    ("5K", 5000.0),
    ("10K", 10000.0),
    ("15K", 15000.0),
    ("Half Marathon", 21097.5),
    ("25K", 25000.0),
    ("30K", 30000.0),
    ("Marathon", 42195.0),
]


def best_effort(
    distance_stream: list[float],
    time_stream: list[int] | list[float],
    target_m: float,
) -> dict[str, Any] | None:
    """Fastest contiguous segment that covers at least `target_m` meters.

    Algorithm: two-pointer over a monotonically non-decreasing `distance_stream`.
    For each end anchor j, we keep i as the latest start sample still covering
    `target_m` between i and j. We then interpolate the start position linearly
    within [i, i+1] so the segment covers exactly `target_m` (the end is left
    on the sample boundary — see implementation note below).

    Why interpolate only the start: the minimum of the elapsed-time function
    over (start_time, end_time) pairs is always reached at an end-sample
    boundary (the function is piecewise-linear in the end position and
    monotonic within each piece), so interpolating the end would not improve
    the optimum — only the start needs interpolation for sub-sample precision.

    Returns dict with `time_s`, `segment_start_s`, `segment_end_s`,
    `start_idx`, `end_idx`, or None if streams are too short / inconsistent.
    """
    n = len(distance_stream)
    if n < 2 or len(time_stream) != n or target_m <= 0:
        return None
    distance_stream = _clamp_gps_jumps(distance_stream, time_stream)
    if distance_stream[-1] - distance_stream[0] < target_m:
        return None

    best_dt: float | None = None
    best_t_start: float = 0.0
    best_t_end: float = 0.0
    best_i: int = 0
    best_j: int = 0

    i = 0
    for j in range(1, n):
        # Advance i as long as the [i+1, j] window still covers the target.
        while i + 1 < j and (distance_stream[j] - distance_stream[i + 1]) >= target_m:
            i += 1
        if distance_stream[j] - distance_stream[i] < target_m:
            continue

        seg = distance_stream[i + 1] - distance_stream[i]
        excess = (distance_stream[j] - distance_stream[i]) - target_m
        if seg <= 0:
            # Athlete paused at sample i — start can slide to time[i+1] for free.
            t_start = float(time_stream[i + 1])
        else:
            frac = min(1.0, max(0.0, excess / seg))
            t_start = time_stream[i] + frac * (time_stream[i + 1] - time_stream[i])

        t_end = float(time_stream[j])
        dt = t_end - t_start
        if dt <= 0:
            continue
        if best_dt is None or dt < best_dt:
            best_dt = dt
            best_t_start = t_start
            best_t_end = t_end
            best_i = i
            best_j = j

    if best_dt is None:
        return None
    return {
        "time_s": best_dt,
        "segment_start_s": best_t_start,
        "segment_end_s": best_t_end,
        "start_idx": best_i,
        "end_idx": best_j,
    }


def best_efforts_for_activity(
    distance_stream: list[float] | None,
    time_stream: list[int] | list[float] | None,
    distances: list[tuple[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """Compute best efforts for all `distances` on a single activity.

    Returns a list of {distance_label, distance_m, time_s, segment_start_s,
    segment_end_s, start_idx, end_idx} dicts. Distances longer than the
    activity (or impossible to cover) are skipped.
    """
    if not distance_stream or not time_stream:
        return []
    targets = distances or STANDARD_DISTANCES

    results: list[dict[str, Any]] = []
    for label, dist_m in targets:
        eff = best_effort(distance_stream, time_stream, dist_m)
        if eff is None:
            continue
        results.append(
            {
                "distance_label": label,
                "distance_m": dist_m,
                **eff,
            }
        )
    return results
