from datetime import date

from strava_mcp.analytics.load import (
    best_tss_for_activity,
    compute_ctl_atl_tsb,
    hr_tss,
    trimp,
    tsb_interpretation,
)

HR_REST = 50.0
HR_MAX = 187.0
LTHR = 165.0


class TestTrimp:
    def test_moderate_run(self) -> None:
        result = trimp(3600, 152.0, HR_REST, HR_MAX, sex="male")
        assert result is not None
        assert result > 0

    def test_harder_run_yields_higher_trimp(self) -> None:
        easy = trimp(3600, 130.0, HR_REST, HR_MAX)
        hard = trimp(3600, 170.0, HR_REST, HR_MAX)
        assert hard > easy  # type: ignore[operator]

    def test_longer_run_yields_higher_trimp(self) -> None:
        short = trimp(1800, 152.0, HR_REST, HR_MAX)
        long_ = trimp(3600, 152.0, HR_REST, HR_MAX)
        assert long_ > short  # type: ignore[operator]

    def test_female_coeff_differs(self) -> None:
        male = trimp(3600, 152.0, HR_REST, HR_MAX, sex="male")
        female = trimp(3600, 152.0, HR_REST, HR_MAX, sex="female")
        assert male != female

    def test_returns_none_without_hr(self) -> None:
        assert trimp(3600, 0.0, HR_REST, HR_MAX) is None

    def test_returns_none_without_hrmax(self) -> None:
        assert trimp(3600, 152.0, HR_REST, 0.0) is None

    def test_returns_none_if_hrmax_equals_hrrest(self) -> None:
        assert trimp(3600, 152.0, HR_REST, HR_REST) is None


class TestHrTss:
    def test_easy_run_below_100(self) -> None:
        # Easy 1h run at 85% LTHR
        result = hr_tss(3600, 140.0, LTHR)
        assert result is not None
        assert result < 100

    def test_threshold_1h_equals_100(self) -> None:
        # 1h exactly at LTHR should give TSS = 100
        result = hr_tss(3600, LTHR, LTHR)
        assert result is not None
        assert abs(result - 100.0) < 0.01

    def test_returns_none_without_lthr(self) -> None:
        assert hr_tss(3600, 152.0, 0.0) is None

    def test_returns_none_without_hr(self) -> None:
        assert hr_tss(3600, 0.0, LTHR) is None


class TestComputeCtlAtlTsb:
    def _make_dates(self, n: int) -> list[date]:
        from datetime import timedelta
        start = date(2024, 1, 1)
        return [start + timedelta(days=i) for i in range(n)]

    def test_basic_output_shape(self) -> None:
        tss = [50.0] * 10
        dates = self._make_dates(10)
        result = compute_ctl_atl_tsb(tss, dates)
        assert len(result) == 10
        for row in result:
            assert "ctl" in row
            assert "atl" in row
            assert "tsb" in row

    def test_tsb_equals_ctl_minus_atl(self) -> None:
        tss = [60.0] * 30
        dates = self._make_dates(30)
        result = compute_ctl_atl_tsb(tss, dates)
        for row in result:
            assert abs(row["tsb"] - (row["ctl"] - row["atl"])) < 0.01

    def test_high_tss_increases_atl_faster_than_ctl(self) -> None:
        # After 14 days of high training, ATL > CTL → TSB negative
        tss = [100.0] * 14
        dates = self._make_dates(14)
        result = compute_ctl_atl_tsb(tss, dates)
        # By the end, ATL should respond faster
        last = result[-1]
        assert last["atl"] >= last["ctl"]

    def test_returns_empty_for_empty_input(self) -> None:
        assert compute_ctl_atl_tsb([], []) == []

    def test_custom_init_values(self) -> None:
        tss = [0.0] * 5
        dates = self._make_dates(5)
        result = compute_ctl_atl_tsb(tss, dates, init_ctl=50.0, init_atl=70.0)
        assert result[0]["ctl"] == 50.0
        assert result[0]["atl"] == 70.0


class TestTsbInterpretation:
    def test_very_rested(self) -> None:
        assert tsb_interpretation(30.0) == "very_rested"

    def test_race_ready(self) -> None:
        assert tsb_interpretation(10.0) == "race_ready"

    def test_productive(self) -> None:
        assert tsb_interpretation(-5.0) == "productive"

    def test_loaded(self) -> None:
        assert tsb_interpretation(-20.0) == "loaded"

    def test_high_risk(self) -> None:
        assert tsb_interpretation(-40.0) == "high_risk"


class TestBestTssForActivity:
    def _run(self) -> dict:
        return {"sport_type": "Run"}

    def _strength(self) -> dict:
        return {"sport_type": "WeightTraining"}

    def test_rtss_preferred_for_run(self) -> None:
        assert best_tss_for_activity(self._run(), 50.0, 60.0, 70.0) == 70.0

    def test_falls_back_to_hrtss_when_no_rtss(self) -> None:
        assert best_tss_for_activity(self._run(), 50.0, 60.0, None) == 60.0

    def test_falls_back_to_trimp_when_no_hrtss(self) -> None:
        assert best_tss_for_activity(self._run(), 50.0, None, None) == 50.0

    def test_strength_training_uses_trimp_not_rtss(self) -> None:
        # rTSS not valid for weight training
        assert best_tss_for_activity(self._strength(), 50.0, 60.0, 70.0) == 60.0

    def test_returns_none_when_all_none(self) -> None:
        assert best_tss_for_activity(self._run(), None, None, None) is None
