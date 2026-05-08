
from strava_mcp.analytics.efficiency import aerobic_efficiency, decoupling_from_stream


class TestAerobicEfficiency:
    def test_basic(self) -> None:
        ef = aerobic_efficiency(3.0, 150.0)
        assert ef is not None
        assert abs(ef - 0.02) < 0.001

    def test_returns_none_for_zero_hr(self) -> None:
        assert aerobic_efficiency(3.0, 0.0) is None

    def test_returns_none_for_none_ngp(self) -> None:
        assert aerobic_efficiency(None, 150.0) is None  # type: ignore[arg-type]

    def test_higher_speed_same_hr_is_better(self) -> None:
        ef_slow = aerobic_efficiency(2.5, 150.0)
        ef_fast = aerobic_efficiency(3.5, 150.0)
        assert ef_fast > ef_slow  # type: ignore[operator]


class TestDecouplingFromStream:
    def _make_streams(
        self,
        n: int = 300,
        hr_drift: float = 0.0,
        speed: float = 3.0,
        grade: float = 0.0,
    ):
        dist = [speed * i for i in range(n)]
        alt = [grade * speed * i for i in range(n)]
        t = list(range(n))
        # First half HR stable, second half drifts up
        hr = [150.0 + hr_drift * (i / n) for i in range(n)]
        return dist, alt, t, hr

    def test_no_drift_near_zero(self) -> None:
        d, a, t, h = self._make_streams(n=400, hr_drift=0.0)
        result = decoupling_from_stream(d, a, t, h, warmup_seconds=10)
        assert result is not None
        assert abs(result) < 2.0  # effectively zero drift

    def test_drift_gives_positive_decoupling(self) -> None:
        # HR increases 20 bpm over the run = efficiency drops in 2nd half
        d, a, t, h = self._make_streams(n=400, hr_drift=20.0)
        result = decoupling_from_stream(d, a, t, h, warmup_seconds=10)
        assert result is not None
        assert result > 0  # EF drops in second half

    def test_returns_none_for_short_stream(self) -> None:
        d, a, t, h = self._make_streams(n=30)
        assert decoupling_from_stream(d, a, t, h) is None

    def test_returns_none_for_empty(self) -> None:
        assert decoupling_from_stream([], [], [], []) is None
