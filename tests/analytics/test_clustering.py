from strava_mcp.analytics.clustering import cluster_routes


def _activity(
    aid: int,
    lat: float,
    lng: float,
    distance_km: float,
    speed_mps: float = 3.0,
    hr: float = 150,
    date_str: str = "2026-01-01T07:00:00",
) -> dict:
    return {
        "id": aid,
        "name": f"Run {aid}",
        "start_date_local": date_str,
        "distance_m": distance_km * 1000,
        "moving_time_s": (distance_km * 1000) / speed_mps,
        "average_speed_mps": speed_mps,
        "average_heartrate": hr,
        "elevation_gain_m": 30,
        "start_latlng_lat": lat,
        "start_latlng_lng": lng,
    }


class TestClusterRoutes:
    def test_groups_nearby_starts_with_same_distance(self) -> None:
        # Five 10K runs from approximately the same point (within 50 m)
        acts = [_activity(i, -23.5556 + i * 0.0001, -46.7261, 10.2) for i in range(5)]
        clusters = cluster_routes(acts)
        assert len(clusters) == 1
        c = clusters[0]
        assert c["n_activities"] == 5
        assert c["distance_bin"] == "9–11 km (10K)"
        assert 9.5 < c["avg_distance_km"] < 10.5

    def test_separates_different_distance_bins(self) -> None:
        # Same start point, but two distinct distance bins
        acts = [
            *[_activity(i, -23.5556, -46.7261, 10.0) for i in range(3)],
            *[_activity(100 + i, -23.5556, -46.7261, 21.1) for i in range(3)],
        ]
        clusters = cluster_routes(acts)
        bins = sorted(c["distance_bin"] for c in clusters)
        assert "9–11 km (10K)" in bins
        assert "17–22 km (Half)" in bins

    def test_returns_empty_when_below_min_samples(self) -> None:
        acts = [_activity(i, -23.5556, -46.7261, 10.0) for i in range(2)]
        assert cluster_routes(acts, min_samples=3) == []

    def test_skips_activities_without_coords(self) -> None:
        acts = [
            _activity(1, -23.5556, -46.7261, 10.0),
            {"id": 2, "distance_m": 10000, "average_speed_mps": 3.0},  # no coords
            _activity(3, -23.5556, -46.7261, 10.0),
            _activity(4, -23.5556, -46.7261, 10.0),
        ]
        clusters = cluster_routes(acts)
        assert len(clusters) == 1
        assert clusters[0]["n_activities"] == 3

    def test_far_apart_starts_form_separate_clusters(self) -> None:
        # São Paulo and a point 5 km away — distinct clusters
        sp = [_activity(i, -23.5556, -46.7261, 10.0) for i in range(3)]
        far = [_activity(100 + i, -23.5100, -46.7261, 10.0) for i in range(3)]
        clusters = cluster_routes([*sp, *far])
        assert len(clusters) == 2
