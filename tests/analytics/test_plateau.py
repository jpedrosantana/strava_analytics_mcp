from strava_mcp.analytics.plateau import (
    assess_plateau,
    days_since_last_pr,
    ef_trend,
    intensity_variety,
    pace_at_lthr_trend,
)


class TestEfTrend:
    def test_improving(self) -> None:
        # Clear upward trend in EF
        series = [(0, 0.0190), (1, 0.0195), (2, 0.0200), (3, 0.0210)]
        r = ef_trend(series)
        assert r["flag"] == "improving"
        assert r["slope_per_month"] is not None
        assert r["slope_per_month"] > 0

    def test_declining(self) -> None:
        series = [(0, 0.0210), (1, 0.0200), (2, 0.0190), (3, 0.0180)]
        r = ef_trend(series)
        assert r["flag"] == "declining"

    def test_flat(self) -> None:
        series = [(0, 0.0200), (1, 0.0200), (2, 0.0200), (3, 0.0200)]
        r = ef_trend(series)
        assert r["flag"] == "flat"

    def test_insufficient_data(self) -> None:
        assert ef_trend([])["flag"] == "insufficient_data"
        assert ef_trend([(0, 0.02), (1, 0.02)])["flag"] == "insufficient_data"


class TestPaceAtLthrTrend:
    def test_improving(self) -> None:
        series = [(0, 3.0), (1, 3.05), (2, 3.10), (3, 3.15)]
        r = pace_at_lthr_trend(series)
        assert r["flag"] == "improving"

    def test_declining(self) -> None:
        series = [(0, 3.15), (1, 3.10), (2, 3.05), (3, 3.00)]
        r = pace_at_lthr_trend(series)
        assert r["flag"] == "declining"


class TestDaysSinceLastPr:
    def test_fresh(self) -> None:
        assert days_since_last_pr(15)["flag"] == "fresh"

    def test_warming(self) -> None:
        assert days_since_last_pr(80)["flag"] == "warming"

    def test_stale(self) -> None:
        assert days_since_last_pr(150)["flag"] == "stale"

    def test_no_prs(self) -> None:
        assert days_since_last_pr(None)["flag"] == "no_prs_recorded"


class TestIntensityVariety:
    def test_low_intensity(self) -> None:
        zones = {
            "z1_seconds": 0,
            "z2_seconds": 5000,
            "z3_seconds": 5000,
            "z4_seconds": 100,
            "z5_seconds": 0,
        }
        r = intensity_variety(zones)
        assert r["flag"] == "low"

    def test_balanced(self) -> None:
        zones = {
            "z1_seconds": 0,
            "z2_seconds": 5000,
            "z3_seconds": 3000,
            "z4_seconds": 600,
            "z5_seconds": 200,
        }
        r = intensity_variety(zones)
        assert r["flag"] in ("ok", "high")

    def test_empty_returns_insufficient(self) -> None:
        assert (
            intensity_variety(
                {
                    "z1_seconds": 0,
                    "z2_seconds": 0,
                    "z3_seconds": 0,
                    "z4_seconds": 0,
                    "z5_seconds": 0,
                }
            )["flag"]
            == "insufficient_data"
        )


class TestAssessPlateau:
    def _flag_dicts(self, ef_flag, pace_flag, pr_flag, intensity_flag):
        return {
            "ef": {"slope_per_month": 0.0, "flag": ef_flag, "n_months": 4},
            "pace": {"slope_per_week_mps": 0.0, "flag": pace_flag, "n_efforts": 10},
            "pr": {"days_since_last_pr": 100, "flag": pr_flag},
            "intensity": {
                "high_intensity_pct": 4.0,
                "flag": intensity_flag,
                "total_zone_seconds": 1000,
            },
        }

    def test_diagnoses_plateau_when_two_negative(self) -> None:
        flags = self._flag_dicts("flat", "flat", "fresh", "ok")
        d = assess_plateau(flags["ef"], flags["pace"], flags["pr"], flags["intensity"])
        assert d["is_plateauing"] is True
        assert len(d["evidence"]) >= 2

    def test_clean_state_no_plateau(self) -> None:
        flags = self._flag_dicts("improving", "improving", "fresh", "ok")
        d = assess_plateau(flags["ef"], flags["pace"], flags["pr"], flags["intensity"])
        assert d["is_plateauing"] is False
        assert d["evidence"] == []

    def test_low_intensity_triggers_specific_suggestion(self) -> None:
        flags = self._flag_dicts("flat", "improving", "fresh", "low")
        d = assess_plateau(flags["ef"], flags["pace"], flags["pr"], flags["intensity"])
        assert any("intervalado" in s.lower() or "tempo run" in s.lower() for s in d["suggestions"])
