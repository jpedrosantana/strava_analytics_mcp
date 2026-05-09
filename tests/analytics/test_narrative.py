from strava_mcp.analytics.narrative import (
    assemble_narrative,
    count_concerns,
    select_highlights,
    summarize_form_change,
)


def _act(
    aid: int,
    distance_km: float = 10.0,
    speed_mps: float = 3.0,
    sport: str = "Run",
    name: str = "Run",
    trimp: float | None = None,
    hr_tss: float | None = None,
) -> dict:
    return {
        "id": aid,
        "name": name,
        "sport_type": sport,
        "start_date_local": f"2026-01-{(aid % 28) + 1:02d}",
        "distance_m": distance_km * 1000,
        "moving_time_s": (distance_km * 1000) / speed_mps,
        "average_speed_mps": speed_mps,
        "average_heartrate": 155,
        "trimp": trimp,
        "hr_tss": hr_tss,
    }


class TestSelectHighlights:
    def test_picks_longest_run(self) -> None:
        acts = [_act(1, distance_km=8), _act(2, distance_km=21), _act(3, distance_km=12)]
        h = select_highlights(acts)
        assert h["longest"]["id"] == 2
        assert h["longest"]["distance_km"] == 21.0

    def test_fastest_excludes_short_runs(self) -> None:
        # Sub-5K very fast run should NOT win over a longer fast run
        acts = [
            _act(1, distance_km=2.5, speed_mps=5.0),
            _act(2, distance_km=10, speed_mps=3.5),
        ]
        h = select_highlights(acts)
        assert h["fastest_run"]["id"] == 2

    def test_ignores_non_run_for_fastest(self) -> None:
        acts = [
            _act(1, distance_km=10, speed_mps=3.0, sport="Ride"),
            _act(2, distance_km=10, speed_mps=2.5, sport="Run"),
        ]
        h = select_highlights(acts)
        assert h["fastest_run"]["id"] == 2

    def test_highest_load_uses_trimp_or_hrtss(self) -> None:
        acts = [
            _act(1, trimp=80, hr_tss=60),
            _act(2, trimp=200, hr_tss=130),
            _act(3, trimp=100, hr_tss=70),
        ]
        h = select_highlights(acts)
        assert h["highest_load"]["id"] == 2

    def test_returns_none_for_empty(self) -> None:
        h = select_highlights([])
        assert h["longest"] is None
        assert h["fastest_run"] is None
        assert h["highest_load"] is None


class TestSummarizeFormChange:
    def test_computes_deltas(self) -> None:
        history = [
            {"date": "2026-01-01", "ctl": 50, "atl": 45, "tsb": 5},
            {"date": "2026-01-15", "ctl": 60, "atl": 70, "tsb": -10},
        ]
        f = summarize_form_change(history)
        assert f is not None
        assert f["ctl_delta"] == 10
        assert f["tsb_delta"] == -15

    def test_returns_none_for_empty(self) -> None:
        assert summarize_form_change([]) is None


class TestCountConcerns:
    def test_anomalies_concern(self) -> None:
        notes = count_concerns(activities=[], n_anomalies=2, high_acwr_days=0)
        assert any("anomalies" in n.lower() or "padrão" in n.lower() for n in notes)

    def test_acwr_concern(self) -> None:
        notes = count_concerns(activities=[], n_anomalies=0, high_acwr_days=3)
        assert any("acwr" in n.lower() for n in notes)

    def test_no_long_run_concern(self) -> None:
        runs = [_act(i, distance_km=8) for i in range(1, 8)]
        notes = count_concerns(activities=runs, n_anomalies=0, high_acwr_days=0)
        assert any("long" in n.lower() for n in notes)

    def test_no_concern_when_long_run_present(self) -> None:
        runs = [_act(1, distance_km=20)] + [_act(i, distance_km=8) for i in range(2, 7)]
        notes = count_concerns(activities=runs, n_anomalies=0, high_acwr_days=0)
        assert all("long" not in n.lower() for n in notes)


class TestAssembleNarrative:
    def test_returns_all_sections(self) -> None:
        result = assemble_narrative(
            period={"start": "2026-01-01", "end": "2026-01-31"},
            period_stats={"n_activities": 12, "total_distance_km": 80},
            prior_stats={"n_activities": 10, "total_distance_km": 60},
            highlights={"longest": None, "fastest_run": None, "highest_load": None},
            form_change=None,
            concerns=[],
        )
        assert "summary" in result
        assert "comparison_to_prior_period" in result
        assert result["comparison_to_prior_period"]["n_activities"]["delta"] == 2
        assert result["comparison_to_prior_period"]["n_activities"]["pct_change"] == 20.0

    def test_skips_comparison_when_prior_is_none(self) -> None:
        result = assemble_narrative(
            period={"start": "2026-01-01", "end": "2026-01-31"},
            period_stats={"n_activities": 12},
            prior_stats=None,
            highlights={"longest": None, "fastest_run": None, "highest_load": None},
            form_change=None,
            concerns=[],
        )
        assert result["comparison_to_prior_period"] is None
