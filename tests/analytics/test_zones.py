from datetime import date, timedelta

import pandas as pd

from strava_mcp.analytics.zones import (
    classify_hr,
    estimate_hrmax,
    estimate_lthr,
    zone_seconds_from_stream,
    zone_seconds_from_summary,
    zone_thresholds,
)

LTHR = 165.0


def _runs_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["start_date_utc"] = pd.to_datetime(df["start_date_utc"], utc=True)
    return df


def _make_run(avg_hr: float, max_hr: float, moving_time_s: int = 1800, days_ago: int = 10) -> dict:
    d = date.today() - timedelta(days=days_ago)
    return {
        "average_heartrate": avg_hr,
        "max_heartrate": max_hr,
        "moving_time_s": moving_time_s,
        "start_date_utc": f"{d}T10:00:00Z",
    }


class TestClassifyHr:
    def test_z1(self) -> None:
        assert classify_hr(130.0, LTHR) == "Z1"  # 130/165 = 78.8% < 81%

    def test_z2(self) -> None:
        assert classify_hr(145.0, LTHR) == "Z2"  # 145/165 = 87.9%

    def test_z3(self) -> None:
        assert classify_hr(151.0, LTHR) == "Z3"  # 151/165 = 91.5%

    def test_z4(self) -> None:
        assert classify_hr(158.0, LTHR) == "Z4"  # 158/165 = 95.8%

    def test_z5a(self) -> None:
        assert classify_hr(166.0, LTHR) == "Z5a"  # 166/165 = 100.6%

    def test_z5b(self) -> None:
        assert classify_hr(172.0, LTHR) == "Z5b"  # 172/165 = 104.2%

    def test_z5c(self) -> None:
        assert classify_hr(180.0, LTHR) == "Z5c"  # 180/165 = 109%


class TestZoneThresholds:
    def test_returns_7_zones(self) -> None:
        zones = zone_thresholds(LTHR)
        assert len(zones) == 7

    def test_z1_starts_at_zero(self) -> None:
        zones = zone_thresholds(LTHR)
        assert zones[0]["min_bpm"] == 0.0

    def test_zone_names(self) -> None:
        zones = zone_thresholds(LTHR)
        assert [z["zone"] for z in zones] == ["Z1", "Z2", "Z3", "Z4", "Z5a", "Z5b", "Z5c"]


class TestZoneSecondsFromSummary:
    def test_easy_run_goes_to_z2(self) -> None:
        result = zone_seconds_from_summary(145.0, 3600, LTHR)
        assert result["z2_seconds"] == 3600
        assert result["z1_seconds"] == 0

    def test_tempo_run_goes_to_z4(self) -> None:
        result = zone_seconds_from_summary(158.0, 1800, LTHR)
        assert result["z4_seconds"] == 1800

    def test_z5a_z5b_z5c_map_to_z5(self) -> None:
        for hr in [166.0, 172.0, 180.0]:
            result = zone_seconds_from_summary(hr, 60, LTHR)
            assert result["z5_seconds"] == 60


class TestZoneSecondsFromStream:
    def test_basic_stream(self) -> None:
        hr_stream = [130.0, 145.0, 151.0, 158.0, 166.0]
        result = zone_seconds_from_stream(hr_stream, LTHR)
        assert result["z1_seconds"] == 1
        assert result["z2_seconds"] == 1
        assert result["z3_seconds"] == 1
        assert result["z4_seconds"] == 1
        assert result["z5_seconds"] == 1

    def test_zero_and_none_ignored(self) -> None:
        result = zone_seconds_from_stream([0, None, 145.0], LTHR)  # type: ignore[list-item]
        assert result["z2_seconds"] == 1
        total = sum(result.values())
        assert total == 1


class TestEstimateHrmax:
    def test_returns_percentile(self) -> None:
        rows = [_make_run(150, 180 + i) for i in range(20)]
        df = _runs_df(rows)
        hrmax = estimate_hrmax(df)
        assert hrmax is not None
        assert hrmax >= 180

    def test_returns_none_with_few_runs(self) -> None:
        rows = [_make_run(150, 180), _make_run(145, 175)]
        df = _runs_df(rows)
        assert estimate_hrmax(df) is None

    def test_ignores_implausible_values(self) -> None:
        rows = [_make_run(150, 300)] + [_make_run(150, 185) for _ in range(10)]
        df = _runs_df(rows)
        hrmax = estimate_hrmax(df)
        assert hrmax is not None
        assert hrmax < 300


class TestEstimateLthr:
    def test_uses_recent_runs(self) -> None:
        # 6 runs in last 90 days with avg_hr ~160
        rows = [_make_run(160, 185, moving_time_s=2400, days_ago=5) for _ in range(6)]
        df = _runs_df(rows)
        lthr = estimate_lthr(df, today=date.today())
        assert lthr is not None
        assert 155 <= lthr <= 165

    def test_falls_back_to_all_data(self) -> None:
        # Only 3 recent, 5 total
        rows = [_make_run(158, 185, moving_time_s=2400, days_ago=100) for _ in range(5)]
        df = _runs_df(rows)
        lthr = estimate_lthr(df, today=date.today())
        assert lthr is not None

    def test_returns_none_if_not_enough_data(self) -> None:
        rows = [_make_run(155, 180, moving_time_s=2400) for _ in range(3)]
        df = _runs_df(rows)
        assert estimate_lthr(df) is None

    def test_excludes_short_runs(self) -> None:
        # Short runs (< 20min) should be ignored
        rows = [_make_run(155, 180, moving_time_s=600) for _ in range(10)]
        df = _runs_df(rows)
        assert estimate_lthr(df) is None
