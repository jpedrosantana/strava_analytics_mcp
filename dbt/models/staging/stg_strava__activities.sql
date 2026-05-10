select
    -- ids
    id as activity_id,

    -- attributes
    name,
    sport_type,
    workout_type,

    -- timing
    start_date_utc,
    start_date_local,
    timezone,
    moving_time_s,
    elapsed_time_s,

    -- distance
    distance_m,
    average_speed_mps,
    max_speed_mps,

    -- elevation
    elevation_gain_m,

    -- heart rate
    has_heartrate,
    average_heartrate,
    max_heartrate,

    -- power (cycling)
    has_powermeter,
    average_watts,
    weighted_average_watts,
    kilojoules,

    -- cadence
    average_cadence,

    -- strava-computed
    suffer_score,

    -- flags
    trainer,
    commute,
    manual,

    -- geo
    start_latlng_lat,
    start_latlng_lng,
    end_latlng_lat,
    end_latlng_lng,
    map_polyline,

    -- meta
    synced_at,
    streams_synced_at

from {{ source('strava_raw', 'activities') }}
