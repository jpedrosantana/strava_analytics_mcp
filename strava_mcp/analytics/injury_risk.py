"""Injury risk scoring from training-load and efficiency signals.

Three signals are combined into a 0-100 risk score:
  - ACWR (acute:chronic workload ratio) — overload from rapid load increase
  - Volume spike — current week distance vs. 4-week average
  - EF degradation — drop in aerobic efficiency vs. baseline (overreaching marker)
"""
from typing import Any

# ---------------------------------------------------------------------------
# Per-signal scoring
# ---------------------------------------------------------------------------


def acwr_score(acwr: float | None) -> tuple[int, dict[str, Any] | None]:
    """Risk contribution from ACWR.

    Sweet zone: 0.8–1.3. Above 1.5 is high-risk, 1.3–1.5 moderate.
    Returns (points, factor_dict | None).
    """
    if acwr is None:
        return 0, None
    if acwr > 1.5:
        return 40, {
            "factor": "acwr",
            "value": acwr,
            "severity": "high",
            "note": f"ACWR {acwr} > 1.5 indicates high injury risk",
        }
    if acwr > 1.3:
        return 20, {
            "factor": "acwr",
            "value": acwr,
            "severity": "moderate",
            "note": f"ACWR {acwr} approaching danger zone (>1.5)",
        }
    return 0, None


def volume_spike_score(spike_ratio: float | None) -> tuple[int, dict[str, Any] | None]:
    """Risk contribution from weekly volume spike.

    spike_ratio = current_week_volume / avg_4_weeks_volume.
    """
    if spike_ratio is None:
        return 0, None
    if spike_ratio > 1.5:
        return 30, {
            "factor": "volume_spike",
            "value": spike_ratio,
            "severity": "high",
            "note": f"Week volume is {spike_ratio:.1f}x the 4-week average",
        }
    if spike_ratio > 1.25:
        return 15, {
            "factor": "volume_spike",
            "value": spike_ratio,
            "severity": "moderate",
            "note": f"Moderate volume spike ({spike_ratio:.1f}x average)",
        }
    return 0, None


def ef_degradation_score(
    recent_ef: float | None,
    baseline_ef: float | None,
) -> tuple[int, dict[str, Any] | None]:
    """Risk contribution from drop in aerobic efficiency.

    A persistent drop in EF (same speed but higher HR) is a classic marker of
    accumulated fatigue / overreaching.

    drop_pct = (baseline_ef - recent_ef) / baseline_ef × 100
    """
    if not recent_ef or not baseline_ef or baseline_ef <= 0:
        return 0, None
    drop_pct = (baseline_ef - recent_ef) / baseline_ef * 100
    if drop_pct >= 5:
        return 25, {
            "factor": "ef_degradation",
            "value": round(drop_pct, 2),
            "severity": "high",
            "note": (
                f"Aerobic efficiency dropped {drop_pct:.1f}% vs. baseline "
                f"(recent {recent_ef:.4f} vs baseline {baseline_ef:.4f})"
            ),
        }
    if drop_pct >= 2.5:
        return 12, {
            "factor": "ef_degradation",
            "value": round(drop_pct, 2),
            "severity": "moderate",
            "note": (
                f"Aerobic efficiency down {drop_pct:.1f}% vs. baseline — possible "
                f"early fatigue signal"
            ),
        }
    return 0, None


# ---------------------------------------------------------------------------
# Combined assessment
# ---------------------------------------------------------------------------


def risk_level(score: int) -> str:
    """Map numeric risk score to qualitative level."""
    if score < 20:
        return "low"
    if score < 50:
        return "moderate"
    return "high"


def assess_injury_risk(
    acwr: float | None,
    volume_spike: float | None,
    recent_ef: float | None,
    baseline_ef: float | None,
) -> dict[str, Any]:
    """Combine all three signals into an overall risk assessment.

    Returns:
      {
        "risk_score": int (0-100),
        "risk_level": "low" | "moderate" | "high",
        "factors": [ ...contributing factor dicts... ],
      }
    """
    total = 0
    factors: list[dict[str, Any]] = []

    for points, factor in (
        acwr_score(acwr),
        volume_spike_score(volume_spike),
        ef_degradation_score(recent_ef, baseline_ef),
    ):
        total += points
        if factor is not None:
            factors.append(factor)

    total = min(total, 100)
    return {
        "risk_score": total,
        "risk_level": risk_level(total),
        "factors": factors,
    }
