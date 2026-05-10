select
    -- pk
    date,

    -- training load
    daily_tss,
    ctl,
    atl,
    tsb,

    -- volume
    n_activities,
    total_distance_m,
    total_moving_time_s

from {{ source('strava_raw', 'daily_metrics') }}
