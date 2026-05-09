from strava_mcp.analytics.injury_risk import (
    acwr_score,
    assess_injury_risk,
    ef_degradation_score,
    risk_level,
    volume_spike_score,
)


class TestAcwrScore:
    def test_safe_zone(self) -> None:
        points, factor = acwr_score(1.0)
        assert points == 0
        assert factor is None

    def test_high_risk_above_1_5(self) -> None:
        points, factor = acwr_score(1.6)
        assert points == 40
        assert factor is not None
        assert factor["severity"] == "high"

    def test_moderate_risk_1_3_to_1_5(self) -> None:
        points, factor = acwr_score(1.4)
        assert points == 20
        assert factor is not None
        assert factor["severity"] == "moderate"

    def test_none_returns_no_score(self) -> None:
        points, factor = acwr_score(None)
        assert points == 0
        assert factor is None


class TestVolumeSpikeScore:
    def test_safe(self) -> None:
        assert volume_spike_score(1.0) == (0, None)

    def test_high_spike(self) -> None:
        points, factor = volume_spike_score(1.6)
        assert points == 30
        assert factor and factor["severity"] == "high"

    def test_moderate_spike(self) -> None:
        points, factor = volume_spike_score(1.3)
        assert points == 15
        assert factor and factor["severity"] == "moderate"


class TestEfDegradationScore:
    def test_no_drop(self) -> None:
        # Recent slightly higher than baseline = no degradation
        points, factor = ef_degradation_score(0.020, 0.0195)
        assert points == 0
        assert factor is None

    def test_moderate_drop(self) -> None:
        # 3% drop
        points, factor = ef_degradation_score(0.0194, 0.0200)
        assert points == 12
        assert factor and factor["severity"] == "moderate"

    def test_high_drop(self) -> None:
        # 6% drop
        points, factor = ef_degradation_score(0.0188, 0.0200)
        assert points == 25
        assert factor and factor["severity"] == "high"

    def test_missing_data_returns_zero(self) -> None:
        assert ef_degradation_score(None, 0.02) == (0, None)
        assert ef_degradation_score(0.02, None) == (0, None)
        assert ef_degradation_score(0.02, 0) == (0, None)


class TestRiskLevel:
    def test_low(self) -> None:
        assert risk_level(0) == "low"
        assert risk_level(19) == "low"

    def test_moderate(self) -> None:
        assert risk_level(20) == "moderate"
        assert risk_level(49) == "moderate"

    def test_high(self) -> None:
        assert risk_level(50) == "high"
        assert risk_level(100) == "high"


class TestAssessInjuryRisk:
    def test_all_safe(self) -> None:
        result = assess_injury_risk(acwr=1.0, volume_spike=1.0, recent_ef=0.02, baseline_ef=0.02)
        assert result["risk_score"] == 0
        assert result["risk_level"] == "low"
        assert result["factors"] == []

    def test_combined_factors_capped_at_100(self) -> None:
        # ACWR high (40) + spike high (30) + EF high (25) = 95
        result = assess_injury_risk(
            acwr=1.7, volume_spike=1.6, recent_ef=0.0188, baseline_ef=0.0200
        )
        assert result["risk_score"] == 95
        assert result["risk_level"] == "high"
        assert len(result["factors"]) == 3

    def test_score_never_exceeds_100(self) -> None:
        # Construct an extreme case
        result = assess_injury_risk(
            acwr=2.0, volume_spike=3.0, recent_ef=0.01, baseline_ef=0.02
        )
        assert result["risk_score"] <= 100
