"""Tests for the sliding-window best-effort algorithm."""

from strava_mcp.analytics.best_efforts import (
    best_effort,
    best_efforts_for_activity,
)


def test_constant_pace_5k_inside_10k():
    """5K segment inside a 10K run at constant 4:00/km should yield 1200s."""
    # 10000 m at 4 m/s = 2500 s, sampled every second.
    n = 2501
    distance_stream = [i * 4.0 for i in range(n)]
    time_stream = list(range(n))

    result = best_effort(distance_stream, time_stream, 5000.0)
    assert result is not None
    # 5000m / 4 m/s = 1250s exactly
    assert abs(result["time_s"] - 1250.0) < 0.01
    assert result["start_idx"] >= 0
    assert result["end_idx"] > result["start_idx"]


def test_fast_segment_in_middle():
    """A 5K-fast burst inside a slower run should be picked as the best.

    Higher m/s = faster pace. We sandwich a fast 4 m/s (4:10/km) burst
    between slow 3 m/s (5:33/km) segments; the best 5K should land
    fully inside the fast burst.
    """
    samples = []
    t = 0
    d = 0.0
    samples.append((t, d))
    # First slow segment: 2000 m at 3 m/s → 667 samples
    for _ in range(667):
        t += 1
        d += 3.0
        samples.append((t, d))
    # Fast burst: 5000 m at 4 m/s → 1250 samples
    for _ in range(1250):
        t += 1
        d += 4.0
        samples.append((t, d))
    # Final slow segment: 2000 m at 3 m/s → 667 samples
    for _ in range(667):
        t += 1
        d += 3.0
        samples.append((t, d))

    time_stream = [s[0] for s in samples]
    distance_stream = [s[1] for s in samples]
    result = best_effort(distance_stream, time_stream, 5000.0)
    assert result is not None
    # The 5K fast segment should be the best; ~1250s, with sub-second tolerance.
    assert 1249.0 <= result["time_s"] <= 1251.0


def test_target_longer_than_activity_returns_none():
    distance_stream = [i * 4.0 for i in range(100)]  # 396 m total
    time_stream = list(range(100))
    assert best_effort(distance_stream, time_stream, 1000.0) is None


def test_handles_paused_samples():
    """Samples where the athlete didn't move shouldn't crash the start interpolation."""
    # 2000 m of pause-then-run-then-pause pattern. Keep it simple: same distance
    # for a few samples in the middle.
    distance_stream = [0.0, 100.0, 200.0, 200.0, 200.0, 300.0, 400.0, 500.0]
    time_stream = [0, 25, 50, 60, 70, 100, 130, 160]
    # Target 300m: should find the fastest 300m window covering [200, 500].
    result = best_effort(distance_stream, time_stream, 300.0)
    assert result is not None
    assert result["time_s"] > 0


def test_inconsistent_stream_lengths_returns_none():
    assert best_effort([0.0, 100.0], [0], 50.0) is None


def test_interpolation_precision_at_5k_boundary():
    """When the 5K boundary falls between samples, interpolation should match."""
    # 4 m/s constant. After sample i, distance is 4i meters.
    # 5000m is reached between samples 1250 (5000m exact) — start at sample 0.
    # Try off-grid: 5001 meters → between samples 1250 and 1251.
    n = 2001
    distance_stream = [i * 4.0 for i in range(n)]
    time_stream = list(range(n))

    result = best_effort(distance_stream, time_stream, 5001.0)
    assert result is not None
    # 5001/4 = 1250.25 s
    assert abs(result["time_s"] - 1250.25) < 0.01


def test_best_efforts_for_activity_skips_distances_above_total():
    n = 100
    distance_stream = [i * 4.0 for i in range(n)]  # ~396 m total
    time_stream = list(range(n))
    out = best_efforts_for_activity(distance_stream, time_stream)
    # Only distances <= 396m should be considered. STANDARD_DISTANCES starts at 1K.
    assert out == []


def test_best_efforts_for_activity_returns_multiple():
    """A long-enough activity yields multiple distance entries."""
    # 6 km at 4 m/s → 1500 s, sampled per second.
    n = 1501
    distance_stream = [i * 4.0 for i in range(n)]
    time_stream = list(range(n))
    out = best_efforts_for_activity(distance_stream, time_stream)
    labels = {r["distance_label"] for r in out}
    assert "1K" in labels and "5K" in labels
    assert "10K" not in labels  # 6km < 10K


def test_empty_streams_returns_empty_list():
    assert best_efforts_for_activity(None, None) == []
    assert best_efforts_for_activity([], [0]) == []


def test_gps_jump_rejected_by_speed_ceiling():
    """A 1km distance jump in 1 second (GPS spike) should be ignored."""
    # 5km at a normal 4 m/s, but with one sample where distance jumps 1000m
    # in 1s — simulating tunnel/sign-loss noise.
    distance_stream = [0.0]
    time_stream = [0]
    for i in range(1, 1251):
        distance_stream.append(i * 4.0)
        time_stream.append(i)
    # Inject the spike: at sample 600, distance jumps by an extra 1000m.
    for k in range(600, 1251):
        distance_stream[k] += 1000.0

    result = best_effort(distance_stream, time_stream, 1000.0)
    # The 1km best effort must NOT take advantage of the bogus 1s jump.
    assert result is not None
    # A real 1km at 4 m/s = 250s. The jump segment would give 1s. Verify we
    # picked the realistic one.
    assert result["time_s"] > 100, "GPS spike best effort leaked through"
