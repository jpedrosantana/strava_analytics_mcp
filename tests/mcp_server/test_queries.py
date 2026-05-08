import sqlite3

from strava_mcp.mcp_server.queries import (
    query_athlete_doctor,
    query_compare_periods,
    query_get_activity,
    query_get_aerobic_efficiency_trend,
    query_get_current_form,
    query_get_decoupling_trend,
    query_get_injury_risk,
    query_get_load_history,
    query_get_period_stats,
    query_get_weekly_breakdown,
    query_list_activities,
    query_search_activities,
)
from tests.fixtures.strava_responses import ACTIVITY_RUN


class TestListActivities:
    def test_returns_list(self, conn: sqlite3.Connection) -> None:
        result = query_list_activities(conn, days_back=9999)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_filters_by_sport(self, conn: sqlite3.Connection) -> None:
        runs = query_list_activities(conn, days_back=9999, sport_type="Run")
        assert all(r["sport_type"] == "Run" for r in runs)

    def test_includes_distance_km(self, conn: sqlite3.Connection) -> None:
        result = query_list_activities(conn, days_back=9999)
        for r in result:
            assert "distance_km" in r
            assert r["distance_km"] >= 0

    def test_limit_respected(self, conn: sqlite3.Connection) -> None:
        result = query_list_activities(conn, days_back=9999, limit=2)
        assert len(result) <= 2

    def test_pace_included_for_runs(self, conn: sqlite3.Connection) -> None:
        runs = query_list_activities(conn, days_back=9999, sport_type="Run")
        for r in runs:
            if r.get("distance_km", 0) > 0:
                assert r["pace"] is not None


class TestGetActivity:
    def test_returns_activity(self, conn: sqlite3.Connection) -> None:
        result = query_get_activity(conn, ACTIVITY_RUN["id"])
        assert result is not None
        assert result["id"] == ACTIVITY_RUN["id"]

    def test_returns_none_for_missing(self, conn: sqlite3.Connection) -> None:
        assert query_get_activity(conn, 99999999) is None

    def test_includes_distance_km(self, conn: sqlite3.Connection) -> None:
        result = query_get_activity(conn, ACTIVITY_RUN["id"])
        assert result is not None
        assert abs(result["distance_km"] - ACTIVITY_RUN["distance"] / 1000) < 0.01

    def test_includes_metrics_when_requested(self, conn: sqlite3.Connection) -> None:
        result = query_get_activity(conn, ACTIVITY_RUN["id"], include_metrics=True)
        assert result is not None
        assert "metrics" in result
        assert isinstance(result["metrics"], dict)


class TestSearchActivities:
    def test_name_filter(self, conn: sqlite3.Connection) -> None:
        result = query_search_activities(conn, name_contains="Run")
        assert all("Run" in r["name"] for r in result)

    def test_distance_filter(self, conn: sqlite3.Connection) -> None:
        result = query_search_activities(conn, min_distance_km=15.0)
        assert all(r["distance_km"] >= 15.0 for r in result)

    def test_sport_type_filter(self, conn: sqlite3.Connection) -> None:
        result = query_search_activities(conn, sport_type="Ride")
        assert len(result) == 1
        assert result[0]["sport_type"] == "Ride"

    def test_no_filters_returns_all(self, conn: sqlite3.Connection) -> None:
        result = query_search_activities(conn)
        assert len(result) > 0


class TestGetPeriodStats:
    def test_returns_dict(self, conn: sqlite3.Connection) -> None:
        result = query_get_period_stats(conn, "2000-01-01", "2099-12-31")
        assert isinstance(result, dict)
        assert "n_activities" in result
        assert "total_distance_km" in result

    def test_counts_activities(self, conn: sqlite3.Connection) -> None:
        result = query_get_period_stats(conn, "2000-01-01", "2099-12-31")
        assert result["n_activities"] == 5

    def test_sport_filter(self, conn: sqlite3.Connection) -> None:
        result = query_get_period_stats(conn, "2000-01-01", "2099-12-31", sport_type="Run")
        # RUN, RUN_2, LONG_RUN, NO_HR all have sport_type="Run"
        assert result["n_activities"] == 4

    def test_has_zone_distribution(self, conn: sqlite3.Connection) -> None:
        result = query_get_period_stats(conn, "2000-01-01", "2099-12-31", sport_type="Run")
        assert "zone_distribution_pct" in result


class TestComparePeriods:
    def test_returns_deltas(self, conn: sqlite3.Connection) -> None:
        result = query_compare_periods(
            conn,
            "2000-01-01", "2099-06-30",
            "2000-01-01", "2099-12-31",
        )
        assert "n_activities" in result
        assert "delta" in result["n_activities"]

    def test_period_info_included(self, conn: sqlite3.Connection) -> None:
        result = query_compare_periods(
            conn, "2024-01-01", "2024-06-30", "2024-07-01", "2024-12-31"
        )
        assert "period_a" in result
        assert "period_b" in result


class TestGetWeeklyBreakdown:
    def test_returns_list(self, conn: sqlite3.Connection) -> None:
        result = query_get_weekly_breakdown(conn, weeks_back=9999)
        assert isinstance(result, list)

    def test_has_week_field(self, conn: sqlite3.Connection) -> None:
        result = query_get_weekly_breakdown(conn, weeks_back=9999)
        for entry in result:
            assert "week" in entry
            assert "n_activities" in entry


class TestGetCurrentForm:
    def test_returns_form_data(self, conn: sqlite3.Connection) -> None:
        result = query_get_current_form(conn)
        assert result is not None
        assert "ctl" in result
        assert "atl" in result
        assert "tsb" in result

    def test_includes_history(self, conn: sqlite3.Connection) -> None:
        result = query_get_current_form(conn)
        assert result is not None
        assert "history_14d" in result
        assert isinstance(result["history_14d"], list)

    def test_includes_interpretation(self, conn: sqlite3.Connection) -> None:
        result = query_get_current_form(conn)
        assert result is not None
        assert "form_status" in result
        assert result["form_status"] in (
            "very_rested", "race_ready", "productive", "loaded", "high_risk"
        )


class TestGetLoadHistory:
    def test_returns_list(self, conn: sqlite3.Connection) -> None:
        result = query_get_load_history(conn, days_back=9999)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_has_ctl_atl_tsb(self, conn: sqlite3.Connection) -> None:
        result = query_get_load_history(conn, days_back=9999)
        for row in result:
            assert "ctl" in row
            assert "atl" in row
            assert "tsb" in row
            assert "date" in row


class TestGetInjuryRisk:
    def test_returns_risk_data(self, conn: sqlite3.Connection) -> None:
        result = query_get_injury_risk(conn)
        assert "risk_score" in result
        assert "risk_level" in result
        assert result["risk_level"] in ("low", "moderate", "high")

    def test_has_factors_list(self, conn: sqlite3.Connection) -> None:
        result = query_get_injury_risk(conn)
        assert "factors" in result
        assert isinstance(result["factors"], list)


class TestGetAerobicEfficiencyTrend:
    def test_returns_dict(self, conn: sqlite3.Connection) -> None:
        result = query_get_aerobic_efficiency_trend(conn, months_back=600)
        assert "monthly_ef" in result
        assert isinstance(result["monthly_ef"], list)

    def test_includes_trend(self, conn: sqlite3.Connection) -> None:
        result = query_get_aerobic_efficiency_trend(conn, months_back=600)
        assert "trend" in result


class TestGetDecouplingTrend:
    def test_returns_list(self, conn: sqlite3.Connection) -> None:
        result = query_get_decoupling_trend(conn, months_back=600)
        assert isinstance(result, list)

    def test_only_long_runs(self, conn: sqlite3.Connection) -> None:
        result = query_get_decoupling_trend(conn, months_back=600)
        for r in result:
            assert r["duration_min"] >= 60.0


class TestAthleteDoctorQuery:
    def test_returns_status(self, conn: sqlite3.Connection, db_path: str) -> None:
        result = query_athlete_doctor(conn, db_path)
        assert "status" in result
        assert result["status"] in ("ok", "warnings")

    def test_includes_activity_count(self, conn: sqlite3.Connection, db_path: str) -> None:
        result = query_athlete_doctor(conn, db_path)
        assert result["activities"]["total"] == 5

    def test_includes_metrics_info(self, conn: sqlite3.Connection, db_path: str) -> None:
        result = query_athlete_doctor(conn, db_path)
        assert result["metrics"]["activity_metrics_rows"] > 0
