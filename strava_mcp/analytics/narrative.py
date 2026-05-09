"""Period-narrative assembly: turns raw period data into structured insights.

This module is intentionally just data-shaping — no LLM calls. The result is
a dict rich enough that the LLM consuming the MCP tool can write the actual
prose. Keeping the logic deterministic makes testing tractable and behavior
auditable.
"""

from typing import Any


def select_highlights(activities: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    """Pick the most newsworthy sessions of a period.

    Returns:
      {
        "longest": {...} or None,
        "fastest_run": {...} or None,    # fastest pace among Run/TrailRun ≥ 5km
        "highest_load": {...} or None,   # highest TRIMP/hrTSS
      }
    """
    runs = [a for a in activities if a.get("sport_type") in ("Run", "TrailRun")]

    longest = max(runs, key=lambda a: a.get("distance_m") or 0, default=None)
    if longest is not None and (longest.get("distance_m") or 0) <= 0:
        longest = None

    eligible_for_speed = [
        a for a in runs if (a.get("distance_m") or 0) >= 5000 and a.get("average_speed_mps")
    ]
    fastest = max(eligible_for_speed, key=lambda a: a["average_speed_mps"], default=None)

    with_load = [a for a in activities if (a.get("trimp") or a.get("hr_tss"))]
    highest_load = max(
        with_load,
        key=lambda a: (a.get("hr_tss") or 0) + (a.get("trimp") or 0),
        default=None,
    )

    return {
        "longest": _activity_summary(longest) if longest else None,
        "fastest_run": _activity_summary(fastest) if fastest else None,
        "highest_load": _activity_summary(highest_load) if highest_load else None,
    }


def _activity_summary(a: dict[str, Any]) -> dict[str, Any]:
    speed = a.get("average_speed_mps") or 0
    pace_str = None
    if speed > 0:
        secs = 1000 / speed
        pace_str = f"{int(secs) // 60}:{int(secs) % 60:02d}/km"
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        "date": str(a.get("start_date_local", ""))[:10],
        "distance_km": round((a.get("distance_m") or 0) / 1000, 2),
        "duration_min": round((a.get("moving_time_s") or 0) / 60, 1),
        "pace": pace_str,
        "avg_hr": a.get("average_heartrate"),
        "trimp": round(a["trimp"], 1) if a.get("trimp") else None,
        "hr_tss": round(a["hr_tss"], 1) if a.get("hr_tss") else None,
    }


def summarize_form_change(
    load_history: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """CTL/ATL/TSB at start and end of the period, with deltas.

    load_history must be ordered by date ascending. Returns None if empty.
    """
    if not load_history:
        return None
    start = load_history[0]
    end = load_history[-1]
    return {
        "start_date": str(start.get("date", ""))[:10],
        "end_date": str(end.get("date", ""))[:10],
        "ctl_start": round(start.get("ctl") or 0, 1),
        "ctl_end": round(end.get("ctl") or 0, 1),
        "ctl_delta": round((end.get("ctl") or 0) - (start.get("ctl") or 0), 1),
        "tsb_start": round(start.get("tsb") or 0, 1),
        "tsb_end": round(end.get("tsb") or 0, 1),
        "tsb_delta": round((end.get("tsb") or 0) - (start.get("tsb") or 0), 1),
    }


def count_concerns(
    activities: list[dict[str, Any]],
    n_anomalies: int,
    high_acwr_days: int,
) -> list[str]:
    """Plain-language concerns surfaced by the period data."""
    notes: list[str] = []

    if n_anomalies > 0:
        notes.append(
            f"{n_anomalies} corrida(s) com pace fora do padrão histórico — "
            f"investigar via find_anomalies"
        )

    if high_acwr_days > 0:
        notes.append(
            f"{high_acwr_days} dia(s) com ACWR > 1.3 — risco de lesão por aumento abrupto de carga"
        )

    runs = [a for a in activities if a.get("sport_type") in ("Run", "TrailRun")]
    long_runs = [a for a in runs if (a.get("distance_m") or 0) >= 18000]
    if not long_runs and len(runs) >= 6:
        notes.append("Nenhum longão (≥18 km) no período — base aeróbica pode ficar limitada")

    return notes


def assemble_narrative(
    period: dict[str, str],
    period_stats: dict[str, Any],
    prior_stats: dict[str, Any] | None,
    highlights: dict[str, dict[str, Any] | None],
    form_change: dict[str, Any] | None,
    concerns: list[str],
) -> dict[str, Any]:
    """Compose the final narrative dict consumed by the MCP tool."""
    comparison = None
    if prior_stats:
        comparison = _comparison_block(period_stats, prior_stats)

    return {
        "period": period,
        "summary": period_stats,
        "comparison_to_prior_period": comparison,
        "highlights": highlights,
        "form_change": form_change,
        "concerns": concerns,
    }


def _comparison_block(curr: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    """Compute deltas between two period_stats dicts. Skips fields not numeric."""
    keys = (
        "n_activities",
        "total_distance_km",
        "total_moving_time_h",
        "total_elevation_m",
        "total_trimp",
        "total_hr_tss",
    )
    out: dict[str, Any] = {}
    for k in keys:
        c = curr.get(k)
        p = prior.get(k)
        if c is None or p is None:
            continue
        delta = c - p
        pct = (delta / p * 100) if p else None
        out[k] = {
            "current": c,
            "prior": p,
            "delta": round(delta, 2),
            "pct_change": round(pct, 1) if pct is not None else None,
        }
    return out
