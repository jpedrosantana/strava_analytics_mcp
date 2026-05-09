"""Race time prediction models: Riegel and VDOT (Daniels)."""

from typing import Any

# ---------------------------------------------------------------------------
# Riegel
# ---------------------------------------------------------------------------

# Peter Riegel (1981): T2 = T1 * (D2/D1)^k. Default k=1.06 for trained runners
# on distances up to the marathon. The exponent grows for ultra-long races.
_RIEGEL_DEFAULT_EXPONENT = 1.06


def riegel_predict(
    known_distance_m: float,
    known_time_s: float,
    target_distance_m: float,
    exponent: float = _RIEGEL_DEFAULT_EXPONENT,
) -> float | None:
    """Predict race time using the Riegel formula.

    T_target = T_known * (D_target / D_known) ** exponent

    Returns predicted time in seconds. None if inputs are invalid.
    """
    if known_distance_m <= 0 or known_time_s <= 0 or target_distance_m <= 0:
        return None
    return known_time_s * (target_distance_m / known_distance_m) ** exponent


# ---------------------------------------------------------------------------
# VDOT (Jack Daniels)
# ---------------------------------------------------------------------------

# Daniels' VDOT model: VO2max-equivalent score. Two equations:
#   1. Velocity (m/min) -> VO2 demand (ml/kg/min)
#   2. Race intensity (% VO2max) as a function of duration
# Combined, they let us back out VDOT from any race time, then project times
# at other distances.
#
# Reference: Daniels, J. (2014). Daniels' Running Formula, 3rd ed.


def _vo2_demand(velocity_m_per_min: float) -> float:
    """Aerobic demand (ml/kg/min) for a given running velocity (m/min)."""
    v = velocity_m_per_min
    return -4.60 + 0.182258 * v + 0.000104 * v * v


def _intensity_fraction(duration_min: float) -> float:
    """Fraction of VO2max sustainable for a given race duration (min)."""
    t = duration_min
    return 0.8 + 0.1894393 * pow(2.71828, -0.012778 * t) + 0.2989558 * pow(2.71828, -0.1932605 * t)


def vdot_from_race(distance_m: float, time_s: float) -> float | None:
    """Estimate VDOT from a single race performance.

    VDOT = VO2_demand(velocity) / intensity_fraction(duration).
    Result is a Daniels-equivalent VO2max score in ml/kg/min.
    """
    if distance_m <= 0 or time_s <= 0:
        return None
    duration_min = time_s / 60.0
    velocity = distance_m / duration_min  # m/min
    demand = _vo2_demand(velocity)
    intensity = _intensity_fraction(duration_min)
    if intensity <= 0:
        return None
    return demand / intensity


def vdot_predict(
    vdot: float,
    target_distance_m: float,
) -> float | None:
    """Predict race time at target distance for a given VDOT.

    Solves for time t such that:
      VDOT * intensity_fraction(t) = VO2_demand(distance/t)

    Uses bisection over t (60s..36000s = 1min..10h). The residual is monotonic
    in t over this range, so convergence is guaranteed.
    """
    if vdot <= 0 or target_distance_m <= 0:
        return None

    def residual(t_seconds: float) -> float:
        t_min = t_seconds / 60.0
        velocity = target_distance_m / t_min
        return _vo2_demand(velocity) - vdot * _intensity_fraction(t_min)

    lo, hi = 60.0, 36000.0
    f_lo, f_hi = residual(lo), residual(hi)
    if f_lo * f_hi > 0:
        return None

    for _ in range(80):
        mid = (lo + hi) / 2
        f_mid = residual(mid)
        if abs(f_mid) < 1e-6 or (hi - lo) < 1e-3:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


# ---------------------------------------------------------------------------
# Combined predictor
# ---------------------------------------------------------------------------


def predict_race_time(
    known_distance_m: float,
    known_time_s: float,
    target_distance_m: float,
) -> dict[str, Any]:
    """Return Riegel + VDOT projections for target distance.

    Output schema:
      {
        "target_distance_m": float,
        "riegel": {"time_s": float, "pace_min_per_km": float} | None,
        "vdot":   {"time_s": float, "pace_min_per_km": float, "vdot_score": float} | None,
      }
    """
    riegel_t = riegel_predict(known_distance_m, known_time_s, target_distance_m)
    vdot_score = vdot_from_race(known_distance_m, known_time_s)
    vdot_t = vdot_predict(vdot_score, target_distance_m) if vdot_score else None

    def _pace(time_s: float | None) -> float | None:
        if time_s is None or target_distance_m <= 0:
            return None
        return (time_s / 60.0) / (target_distance_m / 1000.0)

    return {
        "target_distance_m": target_distance_m,
        "riegel": (
            {"time_s": round(riegel_t, 1), "pace_min_per_km": round(_pace(riegel_t) or 0, 3)}
            if riegel_t is not None
            else None
        ),
        "vdot": (
            {
                "time_s": round(vdot_t, 1),
                "pace_min_per_km": round(_pace(vdot_t) or 0, 3),
                "vdot_score": round(vdot_score, 2) if vdot_score else None,
            }
            if vdot_t is not None
            else None
        ),
    }
