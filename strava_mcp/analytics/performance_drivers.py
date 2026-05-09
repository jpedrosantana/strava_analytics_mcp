"""Performance driver analysis: which features explain pace variation.

Fits a Gradient Boosting Regressor predicting average speed (m/s) from the
features available for each activity (distance, elevation, HR, daily form,
temperature, time-of-day). Reports normalized feature importances and
permutation importances as a robustness check.
"""

from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.inspection import permutation_importance

# Stable seed so importance rankings don't shuffle between runs.
_RANDOM_STATE = 42

# Minimum samples to fit the model — gradient boosting needs more rows than
# linear regression to avoid overfitting on a 9-feature space.
_MIN_SAMPLES = 30

# Feature names (must match the order of values built in _row_features).
_FEATURE_NAMES = (
    "distance_km",
    "elevation_gain_m",
    "average_heartrate",
    "ctl",
    "atl",
    "tsb",
    "temperature_c",
    "day_of_week",
    "hour_of_day",
)

_HUMAN_LABELS = {
    "distance_km": "distância da corrida",
    "elevation_gain_m": "ganho de elevação",
    "average_heartrate": "FC média",
    "ctl": "fitness (CTL)",
    "atl": "fadiga (ATL)",
    "tsb": "forma (TSB)",
    "temperature_c": "temperatura",
    "day_of_week": "dia da semana",
    "hour_of_day": "horário do treino",
}


def _row_features(activity: dict[str, Any]) -> list[float] | None:
    """Build the feature vector for one activity. None if essential fields missing."""
    dist = activity.get("distance_m") or 0
    hr = activity.get("average_heartrate")
    if dist <= 0 or not hr:
        return None

    start = str(activity.get("start_date_local") or "")
    if len(start) < 13:
        return None
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(start)
    except ValueError:
        return None

    return [
        dist / 1000.0,
        float(activity.get("elevation_gain_m") or 0),
        float(hr),
        float(activity.get("ctl") or 0),
        float(activity.get("atl") or 0),
        float(activity.get("tsb") or 0),
        float(activity.get("temperature_c") if activity.get("temperature_c") is not None else 22),
        float(dt.weekday()),
        float(dt.hour),
    ]


def fit_driver_model(
    activities: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Fit Gradient Boosting on the dataset and return model + diagnostics.

    Returns:
      {
        "model": GradientBoostingRegressor,
        "feature_names": tuple[str, ...],
        "n_samples": int,
        "r2_train": float,
        "X": np.ndarray,
        "y": np.ndarray,
      }
    None if fewer than _MIN_SAMPLES usable rows.
    """
    rows: list[tuple[list[float], float]] = []
    for a in activities:
        feats = _row_features(a)
        speed = a.get("average_speed_mps")
        if feats is None or not speed or speed <= 0:
            continue
        rows.append((feats, float(speed)))

    if len(rows) < _MIN_SAMPLES:
        return None

    x = np.array([f for f, _ in rows], dtype=float)
    y = np.array([s for _, s in rows], dtype=float)

    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        random_state=_RANDOM_STATE,
    )
    model.fit(x, y)
    r2_train = float(model.score(x, y))

    return {
        "model": model,
        "feature_names": _FEATURE_NAMES,
        "n_samples": len(rows),
        "r2_train": r2_train,
        "X": x,
        "y": y,
    }


def rank_drivers(fitted: dict[str, Any]) -> list[dict[str, Any]]:
    """Return features ranked by importance, with both impurity and permutation
    importance. Permutation is the more honest measure on small datasets."""
    model = fitted["model"]
    names = fitted["feature_names"]

    impurity = np.asarray(model.feature_importances_)

    perm = permutation_importance(
        model,
        fitted["X"],
        fitted["y"],
        n_repeats=20,
        random_state=_RANDOM_STATE,
    )
    perm_mean = perm.importances_mean

    # Normalize each so they sum to ~1 for easier interpretation.
    imp_total = impurity.sum() or 1.0
    perm_total = max(perm_mean.sum(), 1e-9)

    rows = []
    for i, name in enumerate(names):
        rows.append(
            {
                "feature": name,
                "label": _HUMAN_LABELS.get(name, name),
                "importance_impurity": round(float(impurity[i] / imp_total), 4),
                "importance_permutation": round(float(perm_mean[i] / perm_total), 4),
                "permutation_std": round(float(perm.importances_std[i]), 5),
            }
        )

    rows.sort(key=lambda r: r["importance_permutation"], reverse=True)
    return rows
