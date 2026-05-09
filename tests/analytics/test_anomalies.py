import numpy as np

from strava_mcp.analytics.anomalies import (
    detect_outliers,
    fit_pace_model,
    predict_speed,
)


def _synthetic_runs(n: int = 50, seed: int = 42) -> list[dict]:
    """Build synthetic run activities with realistic feature relationships."""
    rng = np.random.default_rng(seed)
    runs = []
    for i in range(n):
        dist = rng.uniform(5000, 20000)
        hr = rng.uniform(140, 180)
        gain = rng.uniform(0, 200)
        # True relationship: speed depends on hr, distance and gain
        speed = (
            2.5
            - 0.3 * np.log(dist / 1000)
            + 0.005 * hr
            - 0.01 * (gain / dist * 100)
            + rng.normal(0, 0.05)  # noise
        )
        runs.append(
            {
                "id": 1000 + i,
                "name": f"Run {i}",
                "sport_type": "Run",
                "start_date_local": f"2026-01-{(i % 28) + 1:02d}T07:00:00",
                "distance_m": dist,
                "moving_time_s": dist / speed,
                "average_speed_mps": speed,
                "average_heartrate": hr,
                "elevation_gain_m": gain,
            }
        )
    return runs


class TestFitPaceModel:
    def test_fits_model_with_enough_samples(self) -> None:
        runs = _synthetic_runs(n=50)
        model = fit_pace_model(runs)
        assert model is not None
        assert model["n_samples"] == 50
        assert model["residual_std"] > 0
        assert len(model["coefficients"]) == 4  # intercept + 3 features

    def test_returns_none_below_min_samples(self) -> None:
        runs = _synthetic_runs(n=10)
        assert fit_pace_model(runs) is None

    def test_skips_rows_without_hr(self) -> None:
        runs = _synthetic_runs(n=30)
        # Knock out HR for most of them, leaving 15 valid (< 20 threshold)
        for r in runs[:15]:
            r["average_heartrate"] = None
        model = fit_pace_model(runs)
        assert model is None

    def test_residuals_are_close_to_zero_on_synthetic(self) -> None:
        runs = _synthetic_runs(n=100)
        model = fit_pace_model(runs)
        assert model is not None
        # Synthetic noise σ = 0.05, so the fitted residual_std should be near that
        assert 0.03 < model["residual_std"] < 0.08


class TestPredictSpeed:
    def test_predicts_within_reasonable_range(self) -> None:
        runs = _synthetic_runs(n=50)
        model = fit_pace_model(runs)
        assert model is not None
        prediction = predict_speed(
            model, {"distance_m": 10000, "average_heartrate": 160, "elevation_gain_m": 50}
        )
        assert prediction is not None
        assert 1.5 < prediction < 4.5  # plausible m/s for a run

    def test_returns_none_for_missing_features(self) -> None:
        runs = _synthetic_runs(n=50)
        model = fit_pace_model(runs)
        assert model is not None
        assert predict_speed(model, {"distance_m": 0, "average_heartrate": 160}) is None


class TestDetectOutliers:
    def test_no_outliers_in_clean_data(self) -> None:
        runs = _synthetic_runs(n=100)
        model = fit_pace_model(runs)
        assert model is not None
        # Threshold of 3.5σ on synthetic gaussian noise → nearly no outliers
        outliers = detect_outliers(runs, model, z_threshold=3.5)
        assert len(outliers) <= 1

    def test_detects_planted_outlier(self) -> None:
        runs = _synthetic_runs(n=100)
        # Plant an obvious outlier — same features but very slow speed
        runs.append(
            {
                "id": 99999,
                "name": "Bad day",
                "sport_type": "Run",
                "start_date_local": "2026-02-15T07:00:00",
                "distance_m": 10000,
                "moving_time_s": 4500,
                "average_speed_mps": 1.5,  # absurdly slow given features
                "average_heartrate": 160,
                "elevation_gain_m": 50,
            }
        )
        model = fit_pace_model(runs)
        assert model is not None
        outliers = detect_outliers(runs, model, z_threshold=2.0)
        ids = {o["activity_id"] for o in outliers}
        assert 99999 in ids

    def test_outliers_sorted_by_abs_zscore(self) -> None:
        runs = _synthetic_runs(n=80)
        model = fit_pace_model(runs)
        assert model is not None
        outliers = detect_outliers(runs, model, z_threshold=0.5)
        if len(outliers) >= 2:
            zs = [abs(o["z_score"]) for o in outliers]
            assert zs == sorted(zs, reverse=True)

    def test_cause_hint_for_negative_tsb(self) -> None:
        runs = _synthetic_runs(n=80)
        model = fit_pace_model(runs)
        assert model is not None
        # Plant a slow run on a date with very negative TSB
        slow = {
            "id": 88888,
            "name": "Bad day",
            "sport_type": "Run",
            "start_date_local": "2026-03-10T07:00:00",
            "distance_m": 10000,
            "moving_time_s": 5000,
            "average_speed_mps": 1.5,
            "average_heartrate": 160,
            "elevation_gain_m": 50,
        }
        outliers = detect_outliers(
            [*runs, slow], model, z_threshold=2.0, tsb_by_date={"2026-03-10": -25.0}
        )
        match = next((o for o in outliers if o["activity_id"] == 88888), None)
        assert match is not None
        assert any("fatigue" in c for c in match["possible_causes"])
