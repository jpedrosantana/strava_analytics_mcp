import numpy as np

from strava_mcp.analytics.performance_drivers import (
    fit_driver_model,
    rank_drivers,
)


def _synthetic_runs(n: int, seed: int = 42, hr_dominant: bool = True) -> list[dict]:
    """Build runs where speed depends primarily on HR (when hr_dominant)."""
    rng = np.random.default_rng(seed)
    runs = []
    for i in range(n):
        dist = rng.uniform(5000, 18000)
        hr = rng.uniform(140, 180)
        gain = rng.uniform(0, 200)
        ctl = rng.uniform(40, 80)
        atl = rng.uniform(40, 80)
        tsb = ctl - atl
        temp = rng.uniform(15, 32)

        if hr_dominant:
            speed = 1.0 + 0.012 * hr - 0.05 * (gain / 100) + rng.normal(0, 0.05)
        else:
            speed = 2.0 + 0.05 * tsb + rng.normal(0, 0.05)

        runs.append(
            {
                "id": i,
                "start_date_local": f"2026-01-{(i % 28) + 1:02d}T07:30:00",
                "distance_m": dist,
                "average_speed_mps": speed,
                "average_heartrate": hr,
                "elevation_gain_m": gain,
                "ctl": ctl,
                "atl": atl,
                "tsb": tsb,
                "temperature_c": temp,
            }
        )
    return runs


class TestFitDriverModel:
    def test_fits_with_enough_samples(self) -> None:
        runs = _synthetic_runs(50)
        fitted = fit_driver_model(runs)
        assert fitted is not None
        assert fitted["n_samples"] == 50
        assert fitted["r2_train"] > 0.5

    def test_returns_none_below_min_samples(self) -> None:
        runs = _synthetic_runs(20)
        assert fit_driver_model(runs) is None

    def test_skips_rows_without_hr(self) -> None:
        runs = _synthetic_runs(40)
        for r in runs[:25]:
            r["average_heartrate"] = None
        # Only 15 valid → below 30-sample threshold
        assert fit_driver_model(runs) is None


class TestRankDrivers:
    def test_returns_all_features(self) -> None:
        runs = _synthetic_runs(80)
        fitted = fit_driver_model(runs)
        assert fitted is not None
        drivers = rank_drivers(fitted)
        feature_names = {d["feature"] for d in drivers}
        # All declared features should be present
        expected = {
            "distance_km",
            "elevation_gain_m",
            "average_heartrate",
            "ctl",
            "atl",
            "tsb",
            "temperature_c",
            "day_of_week",
            "hour_of_day",
        }
        assert feature_names == expected

    def test_dominant_feature_ranks_first(self) -> None:
        runs = _synthetic_runs(120, hr_dominant=True)
        fitted = fit_driver_model(runs)
        assert fitted is not None
        drivers = rank_drivers(fitted)
        assert drivers[0]["feature"] == "average_heartrate"

    def test_drivers_sorted_by_permutation_importance(self) -> None:
        runs = _synthetic_runs(80)
        fitted = fit_driver_model(runs)
        assert fitted is not None
        drivers = rank_drivers(fitted)
        perms = [d["importance_permutation"] for d in drivers]
        assert perms == sorted(perms, reverse=True)

    def test_importances_normalized_to_unit_sum(self) -> None:
        runs = _synthetic_runs(80)
        fitted = fit_driver_model(runs)
        assert fitted is not None
        drivers = rank_drivers(fitted)
        impurity_sum = sum(d["importance_impurity"] for d in drivers)
        assert abs(impurity_sum - 1.0) < 0.01
