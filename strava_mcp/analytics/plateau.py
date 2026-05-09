"""Plateau diagnosis: is the athlete stagnating? Why?

Combines four indicators over a configurable window:
  1. Aerobic efficiency (EF) trend slope
  2. Pace at near-LTHR drift over time
  3. Days since last personal best
  4. Intensity variety — share of time in higher zones (Z3-5)

Each indicator returns a numeric measure plus a qualitative flag. The final
diagnosis combines flags into is_plateauing, evidence list, possible causes
and concrete suggestions.
"""

from typing import Any

import numpy as np


def _linear_slope(xs: list[float], ys: list[float]) -> float | None:
    """Slope of a least-squares line. None if degenerate."""
    if len(xs) < 3 or len(set(xs)) < 2:
        return None
    a, _ = np.polyfit(xs, ys, 1)
    return float(a)


def ef_trend(monthly_ef: list[tuple[int, float]]) -> dict[str, Any]:
    """Trend of monthly aerobic efficiency.

    monthly_ef: list of (month_index, ef_value), oldest to newest.
    A positive slope means EF is improving (which is good).
    """
    xs = [float(m) for m, _ in monthly_ef]
    ys = [float(v) for _, v in monthly_ef]
    slope = _linear_slope(xs, ys)
    if slope is None:
        return {"slope_per_month": None, "flag": "insufficient_data"}

    # EF is in m/s/bpm — typical values around 0.018–0.022. A slope of +0.0001
    # per month is meaningful improvement; below ±0.00005 is essentially flat.
    if slope < -0.00005:
        flag = "declining"
    elif slope > 0.00005:
        flag = "improving"
    else:
        flag = "flat"
    return {"slope_per_month": round(slope, 6), "flag": flag, "n_months": len(monthly_ef)}


def pace_at_lthr_trend(
    pace_at_lthr_series: list[tuple[int, float]],
) -> dict[str, Any]:
    """Trend of pace (m/s) at near-LTHR efforts.

    pace_at_lthr_series: list of (week_index, speed_mps), oldest to newest.
    A positive slope means you're getting faster at the same effort = good.
    """
    xs = [float(w) for w, _ in pace_at_lthr_series]
    ys = [float(v) for _, v in pace_at_lthr_series]
    slope = _linear_slope(xs, ys)
    if slope is None:
        return {"slope_per_week_mps": None, "flag": "insufficient_data"}

    # ~0.005 m/s/week ≈ 4 sec/km/month at 5:00/km — meaningful gain.
    if slope < -0.002:
        flag = "declining"
    elif slope > 0.002:
        flag = "improving"
    else:
        flag = "flat"
    return {
        "slope_per_week_mps": round(slope, 5),
        "flag": flag,
        "n_efforts": len(pace_at_lthr_series),
    }


def days_since_last_pr(days_since: int | None) -> dict[str, Any]:
    """Flag based on time since last personal record."""
    if days_since is None:
        return {"days_since_last_pr": None, "flag": "no_prs_recorded"}
    if days_since > 120:
        flag = "stale"
    elif days_since > 60:
        flag = "warming"
    else:
        flag = "fresh"
    return {"days_since_last_pr": days_since, "flag": flag}


def intensity_variety(zone_seconds: dict[str, int]) -> dict[str, Any]:
    """Share of time in higher zones. Low share signals a 'gray zone' habit
    (always running easy/medium, never hard) — a classic plateau cause."""
    total = sum(zone_seconds.values())
    if total <= 0:
        return {"high_intensity_pct": None, "flag": "insufficient_data"}

    high = zone_seconds.get("z4_seconds", 0) + zone_seconds.get("z5_seconds", 0)
    pct = high / total * 100

    if pct < 5:
        flag = "low"  # likely the issue
    elif pct < 12:
        flag = "ok"
    else:
        flag = "high"
    return {"high_intensity_pct": round(pct, 1), "flag": flag, "total_zone_seconds": total}


def assess_plateau(
    ef: dict[str, Any],
    pace_lthr: dict[str, Any],
    pr_age: dict[str, Any],
    intensity: dict[str, Any],
) -> dict[str, Any]:
    """Combine the four indicators into a final diagnosis."""
    evidence: list[str] = []
    causes: list[str] = []
    suggestions: list[str] = []

    if ef["flag"] == "declining":
        evidence.append("EF mensal em queda")
    elif ef["flag"] == "flat":
        evidence.append("EF mensal estagnado")

    if pace_lthr["flag"] == "declining":
        evidence.append("Pace em FC de limiar piorando ao longo do tempo")
    elif pace_lthr["flag"] == "flat":
        evidence.append("Pace em FC de limiar sem evolução")

    if pr_age["flag"] == "stale":
        evidence.append(f"Sem PR há {pr_age['days_since_last_pr']} dias (>120 dias é sinal forte)")
    elif pr_age["flag"] == "warming":
        evidence.append(f"Sem PR há {pr_age['days_since_last_pr']} dias")

    if intensity["flag"] == "low":
        evidence.append(f"Apenas {intensity['high_intensity_pct']}% do tempo em Z4-Z5 (zona cinza)")
        causes.append(
            "Falta de estímulo de alta intensidade — treino predominantemente "
            "em Z2-Z3 sem polarização"
        )
        suggestions.append(
            "Adicionar 1 sessão semanal de intervalado (Z4-Z5) ou tempo run sustentado"
        )

    if ef["flag"] == "flat" and intensity["flag"] != "low":
        causes.append(
            "Carga aeróbica suficiente, mas variedade de estímulos pode estar baixa "
            "(rotas/distâncias muito repetitivas)"
        )
        suggestions.append("Variar terreno, ritmos e durações ao longo das semanas")

    if ef["flag"] == "declining" or pace_lthr["flag"] == "declining":
        causes.append(
            "Possível fadiga acumulada ou recuperação inadequada — checar TSB recente "
            "e consistência do sono"
        )
        suggestions.append("Considerar uma semana de descarga (-30% volume)")

    n_negative = sum(
        1
        for f in [ef["flag"], pace_lthr["flag"], pr_age["flag"], intensity["flag"]]
        if f in ("declining", "flat", "stale", "low")
    )
    is_plateauing = n_negative >= 2

    return {
        "is_plateauing": is_plateauing,
        "indicators": {
            "ef_trend": ef,
            "pace_at_lthr_trend": pace_lthr,
            "pr_age": pr_age,
            "intensity_variety": intensity,
        },
        "evidence": evidence,
        "possible_causes": causes,
        "suggestions": suggestions,
    }
