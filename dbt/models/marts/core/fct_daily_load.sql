{#
  Fato no grão de um dia. Roll-up diário de carga e volume.
  Já vem agregado de daily_metrics (compute-metrics constrói série contínua entre
  primeira e última atividade — dias sem treino entram com daily_tss = 0).
#}

select
    -- chave
    date as date_key,

    -- carga
    daily_tss,
    ctl,
    atl,
    tsb,

    -- volume
    n_activities,
    total_distance_m,
    total_distance_m / 1000.0 as total_distance_km,
    total_moving_time_s,
    total_moving_time_s / 3600.0 as total_moving_time_h

from {{ ref('stg_strava__daily_metrics') }}
