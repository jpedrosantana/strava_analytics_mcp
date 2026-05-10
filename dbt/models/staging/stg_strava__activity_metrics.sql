select
    -- fk
    activity_id,

    -- training load
    trimp,
    hr_tss,
    r_tss,
    intensity_factor,

    -- aerobic metrics
    aerobic_efficiency,
    decoupling_pct,
    ngp_mps,

    -- time in zone (seconds)
    z1_seconds,
    z2_seconds,
    z3_seconds,
    z4_seconds,
    z5_seconds,

    -- weather (currently mostly nullable; populated when ADR 0002 follow-up lands)
    weather_temp_c,
    weather_humidity_pct,
    weather_wind_mps,
    weather_precipitation_mm,

    -- meta
    computed_at

from {{ source('strava_raw', 'activity_metrics') }}
