{#
  Fato no grão de uma atividade. Junta as medidas brutas (stg_strava__activities)
  com as métricas analíticas computadas (stg_strava__activity_metrics).
  LEFT join em metrics: atividades sem stream/computado ainda preservam a linha do fato.
#}

with activities as (
    select * from {{ ref('stg_strava__activities') }}
),

metrics as (
    select * from {{ ref('stg_strava__activity_metrics') }}
)

select
    -- chaves
    a.activity_id,
    cast(a.start_date_local as date) as date_key,

    -- timing
    a.start_date_utc,
    a.start_date_local,
    a.moving_time_s,
    a.elapsed_time_s,

    -- distância
    a.distance_m,
    a.distance_m / 1000.0 as distance_km,

    -- velocidade / pace
    a.average_speed_mps,
    a.max_speed_mps,
    case
        when a.distance_m > 0
        then a.moving_time_s / (a.distance_m / 1000.0)
    end as pace_s_per_km,

    -- elevação
    a.elevation_gain_m,

    -- frequência cardíaca
    a.average_heartrate,
    a.max_heartrate,

    -- cadência
    a.average_cadence,

    -- potência (ciclismo)
    a.average_watts,
    a.weighted_average_watts,
    a.kilojoules,

    -- métricas Strava-computed
    a.suffer_score,

    -- geo
    a.start_latlng_lat,
    a.start_latlng_lng,
    a.end_latlng_lat,
    a.end_latlng_lng,

    -- carga de treino (do MCP)
    m.trimp,
    m.hr_tss,
    m.r_tss,
    m.intensity_factor,

    -- aerobic
    m.aerobic_efficiency,
    m.decoupling_pct,
    m.ngp_mps,

    -- tempo em zona (segundos)
    m.z1_seconds,
    m.z2_seconds,
    m.z3_seconds,
    m.z4_seconds,
    m.z5_seconds,

    -- clima (atualmente quase 100% null; populado quando o backlog landing)
    m.weather_temp_c,
    m.weather_humidity_pct,
    m.weather_wind_mps,
    m.weather_precipitation_mm

from activities a
left join metrics m on a.activity_id = m.activity_id
