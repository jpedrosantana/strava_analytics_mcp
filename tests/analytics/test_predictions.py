from strava_mcp.analytics.predictions import (
    predict_race_time,
    riegel_predict,
    vdot_from_race,
    vdot_predict,
)


class TestRiegel:
    def test_basic_projection(self) -> None:
        # 10K in 45:00 (2700s) projecting to half marathon
        t = riegel_predict(10000, 2700, 21097.5)
        assert t is not None
        # Riegel: 2700 * (21097.5/10000)^1.06 ≈ 5926s
        assert 5800 < t < 6050

    def test_same_distance_returns_same_time(self) -> None:
        t = riegel_predict(10000, 2700, 10000)
        assert t is not None
        assert abs(t - 2700) < 0.01

    def test_shorter_target_is_faster(self) -> None:
        t_5k = riegel_predict(10000, 2700, 5000)
        t_10k = riegel_predict(10000, 2700, 10000)
        assert t_5k is not None and t_10k is not None
        assert t_5k < t_10k

    def test_longer_target_is_slower(self) -> None:
        t_10k = riegel_predict(10000, 2700, 10000)
        t_42k = riegel_predict(10000, 2700, 42195)
        assert t_10k is not None and t_42k is not None
        assert t_42k > t_10k * 4  # marathon takes more than 4× the 10K time

    def test_invalid_inputs_return_none(self) -> None:
        assert riegel_predict(0, 2700, 21097.5) is None
        assert riegel_predict(10000, 0, 21097.5) is None
        assert riegel_predict(10000, 2700, 0) is None
        assert riegel_predict(-1000, 2700, 21097.5) is None


class TestVdotFromRace:
    def test_known_reference_values(self) -> None:
        # Daniels' tables: 5K in 20:00 ≈ VDOT 49.8
        v = vdot_from_race(5000, 1200)
        assert v is not None
        assert 49 < v < 51

    def test_marathon_in_3h_is_vdot_around_53(self) -> None:
        # Daniels' tables: marathon in 3:00:00 ≈ VDOT 53
        v = vdot_from_race(42195, 10800)
        assert v is not None
        assert 52 < v < 54

    def test_faster_time_higher_vdot(self) -> None:
        v_slow = vdot_from_race(10000, 3600)  # 1h 10K
        v_fast = vdot_from_race(10000, 2400)  # 40min 10K
        assert v_slow is not None and v_fast is not None
        assert v_fast > v_slow

    def test_invalid_inputs_return_none(self) -> None:
        assert vdot_from_race(0, 1200) is None
        assert vdot_from_race(5000, 0) is None


class TestVdotPredict:
    def test_round_trip(self) -> None:
        # VDOT inferred from a race, then projected back to same distance,
        # should reproduce the original time within tight tolerance.
        v = vdot_from_race(10000, 2700)
        assert v is not None
        t = vdot_predict(v, 10000)
        assert t is not None
        assert abs(t - 2700) < 1.0

    def test_known_marathon_projection(self) -> None:
        # Half in 1:30:00 → VDOT ≈ 50, marathon ≈ 3:08–3:13 by Daniels
        v = vdot_from_race(21097.5, 5400)
        assert v is not None
        t = vdot_predict(v, 42195)
        assert t is not None
        assert 11200 < t < 11700  # ~3:06:40 to 3:15:00

    def test_invalid_inputs_return_none(self) -> None:
        assert vdot_predict(0, 21097.5) is None
        assert vdot_predict(50, 0) is None


class TestPredictRaceTime:
    def test_returns_both_models(self) -> None:
        result = predict_race_time(21097.5, 5400, 42195)
        assert result["riegel"] is not None
        assert result["vdot"] is not None
        assert "time_s" in result["riegel"]
        assert "pace_min_per_km" in result["riegel"]
        assert "vdot_score" in result["vdot"]

    def test_target_distance_preserved(self) -> None:
        result = predict_race_time(10000, 2700, 21097.5)
        assert result["target_distance_m"] == 21097.5

    def test_pace_is_consistent_with_time(self) -> None:
        result = predict_race_time(10000, 2700, 21097.5)
        riegel = result["riegel"]
        assert riegel is not None
        # pace_min_per_km × distance_km should ≈ time_min
        expected_pace = (riegel["time_s"] / 60) / 21.0975
        assert abs(riegel["pace_min_per_km"] - expected_pace) < 0.01
