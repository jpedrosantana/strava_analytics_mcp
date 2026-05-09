"""Pace anomaly detection via linear regression on training history.

The model predicts expected speed (m/s) from distance, heart rate and
elevation gain. Activities whose actual speed deviates significantly from the
prediction are flagged as outliers.
"""
from typing import Any

import numpy as np

# Minimum training samples to fit a meaningful model.
_MIN_SAMPLES = 20

# Features used in the regression. Keep order stable — used to slice the
# coefficient vector when scoring new activities.
_FEATURES = ("log_distance_km", "avg_hr", "grade_pct")


def _features_from_activity(activity: dict[str, Any]) -> list[float] | None:
    """Extract feature vector from an activity dict. None if data missing."""
    dist = activity.get("distance_m") or 0.0
    hr = activity.get("average_heartrate") or 0.0
    gain = activity.get("elevation_gain_m") or 0.0
    if dist <= 0 or hr <= 0:
        return None
    return [
        float(np.log(dist / 1000.0)),
        float(hr),
        float(gain) / float(dist) * 100.0,  # grade %
    ]


def fit_pace_model(activities: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Fit a linear model predicting average_speed_mps from features.

    Uses numpy.linalg.lstsq with an intercept column. Returns:
      {
        "coefficients": np.ndarray (4,),  # [intercept, log_distance, hr, grade]
        "residual_std": float,
        "n_samples": int,
        "feature_names": tuple[str, ...],
      }
    None if fewer than _MIN_SAMPLES usable rows.
    """
    rows: list[tuple[list[float], float]] = []
    for a in activities:
        feats = _features_from_activity(a)
        speed = a.get("average_speed_mps")
        if feats is None or not speed or speed <= 0:
            continue
        rows.append((feats, float(speed)))

    if len(rows) < _MIN_SAMPLES:
        return None

    x = np.array([[1.0, *f] for f, _ in rows], dtype=float)
    y = np.array([s for _, s in rows], dtype=float)

    coeffs, *_ = np.linalg.lstsq(x, y, rcond=None)
    predictions = x @ coeffs
    residuals = y - predictions
    residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0

    return {
        "coefficients": coeffs,
        "residual_std": residual_std,
        "n_samples": len(rows),
        "feature_names": _FEATURES,
    }


def predict_speed(model: dict[str, Any], activity: dict[str, Any]) -> float | None:
    """Apply the fitted model to a single activity. None if features missing."""
    feats = _features_from_activity(activity)
    if feats is None:
        return None
    coeffs = model["coefficients"]
    x = np.array([1.0, *feats], dtype=float)
    return float(x @ coeffs)


def _possible_causes(
    activity: dict[str, Any],
    z_score: float,
    daily_tsb: float | None,
    avg_temp: float | None,
) -> list[str]:
    """Heuristic hints for why a run was anomalous."""
    causes: list[str] = []
    if z_score < -1.5:
        if daily_tsb is not None and daily_tsb < -15:
            causes.append("possible fatigue (TSB strongly negative)")
        if avg_temp is not None and avg_temp >= 28:
            causes.append(f"hot conditions ({avg_temp:.0f}°C)")
        dist_km = (activity.get("distance_m") or 0) / 1000
        if dist_km >= 18:
            causes.append("long distance (typical pace fade)")
    elif z_score > 1.5:
        if daily_tsb is not None and daily_tsb > 5:
            causes.append("freshness (TSB positive)")
        sport = activity.get("sport_type", "")
        if sport == "Run" and "interval" in (activity.get("name") or "").lower():
            causes.append("interval session (high-intensity bias)")
    return causes


def detect_outliers(
    activities: list[dict[str, Any]],
    model: dict[str, Any],
    z_threshold: float = 2.0,
    tsb_by_date: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Return activities whose actual speed deviates by ≥ z_threshold std.

    tsb_by_date: optional map of 'YYYY-MM-DD' → TSB on that day, used for the
    cause-hint heuristic.
    """
    sigma = model["residual_std"]
    if sigma <= 0:
        return []

    out: list[dict[str, Any]] = []
    for a in activities:
        actual = a.get("average_speed_mps")
        predicted = predict_speed(model, a)
        if not actual or predicted is None:
            continue
        residual = actual - predicted
        z = residual / sigma
        if abs(z) < z_threshold:
            continue

        date_key = str(a.get("start_date_local", ""))[:10]
        avg_temp = (a.get("raw_json_temp") or None)
        causes = _possible_causes(
            activity=a,
            z_score=z,
            daily_tsb=(tsb_by_date or {}).get(date_key),
            avg_temp=avg_temp,
        )
        out.append(
            {
                "activity_id": a.get("id"),
                "name": a.get("name"),
                "date": date_key,
                "distance_km": round((a.get("distance_m") or 0) / 1000, 2),
                "actual_speed_mps": round(actual, 3),
                "predicted_speed_mps": round(predicted, 3),
                "residual_mps": round(residual, 3),
                "z_score": round(z, 2),
                "direction": "faster_than_expected" if z > 0 else "slower_than_expected",
                "possible_causes": causes,
            }
        )

    out.sort(key=lambda r: abs(r["z_score"]), reverse=True)
    return out
