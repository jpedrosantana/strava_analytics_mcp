"""Route clustering: group activities that share a recurring start point.

DBSCAN over (start_lat, start_lng) with the haversine metric. Within each
start cluster, activities are sub-grouped by distance bin (5K, 10K, 15K, 21K,
30K, 42K) — two runs sharing a start point but differing in length are
treated as different routes.
"""

import math
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN

# DBSCAN tuning. eps is in meters when using haversine on (lat, lng) in radians
# scaled by Earth radius. We pass radians + metric="haversine" and convert eps
# to radians before fitting.
_EARTH_RADIUS_M = 6_371_000.0
_DEFAULT_EPS_M = 100.0
_DEFAULT_MIN_SAMPLES = 3

# Distance bins used to split activities at the same start point. Activities
# whose distance falls within a bin are grouped together.
_DISTANCE_BINS_KM: list[tuple[str, float, float]] = [
    ("≤ 6 km", 0, 6),
    ("6–9 km", 6, 9),
    ("9–11 km (10K)", 9, 11),
    ("11–14 km", 11, 14),
    ("14–17 km (15K)", 14, 17),
    ("17–22 km (Half)", 17, 22),
    ("22–30 km", 22, 30),
    ("30–45 km (Marathon+)", 30, 45),
]


def _bin_label_for(distance_km: float) -> str:
    for label, lo, hi in _DISTANCE_BINS_KM:
        if lo <= distance_km < hi:
            return label
    return f"{int(distance_km)} km"


def _haversine_distance_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Great-circle distance in meters between two (lat, lng) pairs."""
    lat1, lng1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lng2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def cluster_routes(
    activities: list[dict[str, Any]],
    eps_m: float = _DEFAULT_EPS_M,
    min_samples: int = _DEFAULT_MIN_SAMPLES,
) -> list[dict[str, Any]]:
    """Cluster activities by start point and distance bin.

    Activities missing start coordinates are silently skipped.
    Each returned cluster is a dict with:
      - cluster_id, distance_bin
      - n_activities, sample_activity_ids (up to 5)
      - centroid_lat, centroid_lng
      - avg_distance_km, avg_pace_str, avg_hr
      - first_seen, last_seen (YYYY-MM-DD)
    """
    valid = [
        a
        for a in activities
        if a.get("start_latlng_lat") is not None
        and a.get("start_latlng_lng") is not None
        and (a.get("distance_m") or 0) > 0
    ]
    if len(valid) < min_samples:
        return []

    coords_rad = np.radians([[a["start_latlng_lat"], a["start_latlng_lng"]] for a in valid])
    eps_rad = eps_m / _EARTH_RADIUS_M

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine", algorithm="ball_tree")
    labels = db.fit_predict(coords_rad)

    # Group: (start_label, distance_bin) -> list of activities
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for label, activity in zip(labels, valid, strict=True):
        if label == -1:  # DBSCAN noise — not part of any cluster
            continue
        dist_km = activity["distance_m"] / 1000
        key = (int(label), _bin_label_for(dist_km))
        grouped.setdefault(key, []).append(activity)

    return [_summarize_cluster(cid, dbin, acts) for (cid, dbin), acts in grouped.items()]


def _summarize_cluster(
    cluster_id: int,
    distance_bin: str,
    activities: list[dict[str, Any]],
) -> dict[str, Any]:
    lats = [a["start_latlng_lat"] for a in activities]
    lngs = [a["start_latlng_lng"] for a in activities]
    distances = [a["distance_m"] for a in activities]
    speeds = [a["average_speed_mps"] for a in activities if a.get("average_speed_mps")]
    hrs = [a["average_heartrate"] for a in activities if a.get("average_heartrate")]
    dates = sorted(str(a.get("start_date_local", ""))[:10] for a in activities)

    avg_speed = sum(speeds) / len(speeds) if speeds else None
    if avg_speed:
        secs_per_km = 1000 / avg_speed
        m, s = divmod(int(secs_per_km), 60)
        pace_str = f"{m}:{s:02d}/km"
    else:
        pace_str = None

    return {
        "cluster_id": cluster_id,
        "distance_bin": distance_bin,
        "n_activities": len(activities),
        "centroid_lat": round(sum(lats) / len(lats), 6),
        "centroid_lng": round(sum(lngs) / len(lngs), 6),
        "avg_distance_km": round(sum(distances) / len(distances) / 1000, 2),
        "avg_pace_str": pace_str,
        "avg_hr": round(sum(hrs) / len(hrs), 1) if hrs else None,
        "first_seen": dates[0],
        "last_seen": dates[-1],
        "sample_activity_ids": [a["id"] for a in activities[:5]],
    }
