
from strava_mcp.analytics.ngp import (
    grade_factor,
    intensity_factor,
    ngp_from_stream,
    ngp_from_summary,
    r_tss,
)


class TestGradeFactor:
    def test_flat_is_one(self) -> None:
        assert abs(grade_factor(0.0) - 1.0) < 0.01

    def test_uphill_greater_than_one(self) -> None:
        assert grade_factor(0.05) > 1.0

    def test_mild_downhill_less_than_one(self) -> None:
        assert grade_factor(-0.05) < 1.0


class TestNgpFromSummary:
    def test_flat_run_equals_avg_speed(self) -> None:
        # No elevation → NGP ≈ average speed
        ngp = ngp_from_summary(10000.0, 3600, 0.0)
        assert ngp is not None
        assert abs(ngp - 10000 / 3600) < 0.01

    def test_hilly_run_higher_than_flat(self) -> None:
        flat = ngp_from_summary(10000.0, 3600, 0.0)
        hilly = ngp_from_summary(10000.0, 3600, 200.0)
        assert hilly > flat  # type: ignore[operator]

    def test_returns_none_for_zero_distance(self) -> None:
        assert ngp_from_summary(0.0, 3600, 0.0) is None

    def test_returns_none_for_zero_time(self) -> None:
        assert ngp_from_summary(10000.0, 0, 0.0) is None


class TestNgpFromStream:
    def _simple_streams(self, n: int = 10, speed_mps: float = 3.0, grade: float = 0.0):
        distance = [i * speed_mps for i in range(n)]
        altitude = [grade * i * speed_mps for i in range(n)]
        time_ = list(range(n))
        return distance, altitude, time_

    def test_flat_run_close_to_avg_speed(self) -> None:
        d, a, t = self._simple_streams(100, speed_mps=3.0, grade=0.0)
        ngp = ngp_from_stream(d, a, t)
        assert ngp is not None
        assert abs(ngp - 3.0) < 0.1

    def test_uphill_higher_than_avg_speed(self) -> None:
        d, a, t = self._simple_streams(100, speed_mps=3.0, grade=0.05)
        ngp = ngp_from_stream(d, a, t)
        assert ngp is not None
        assert ngp > 3.0

    def test_returns_none_for_empty(self) -> None:
        assert ngp_from_stream([], [], []) is None

    def test_returns_none_for_single_point(self) -> None:
        assert ngp_from_stream([0.0], [0.0], [0]) is None


class TestRTss:
    def test_1h_at_threshold_equals_100(self) -> None:
        threshold = 3.5  # m/s (~4:46/km)
        # 1h exactly at threshold pace → IF=1 → rTSS=100
        result = r_tss(3600, threshold, threshold)
        assert result is not None
        assert abs(result - 100.0) < 0.01

    def test_easy_run_below_100(self) -> None:
        result = r_tss(3600, 2.8, 3.5)
        assert result is not None
        assert result < 100

    def test_returns_none_with_zero_threshold(self) -> None:
        assert r_tss(3600, 3.0, 0.0) is None


class TestIntensityFactor:
    def test_at_threshold_equals_one(self) -> None:
        assert abs(intensity_factor(3.5, 3.5) - 1.0) < 0.001

    def test_below_threshold(self) -> None:
        assert intensity_factor(3.0, 3.5) < 1.0  # type: ignore[operator]

    def test_returns_none_zero_threshold(self) -> None:
        assert intensity_factor(3.0, 0.0) is None
