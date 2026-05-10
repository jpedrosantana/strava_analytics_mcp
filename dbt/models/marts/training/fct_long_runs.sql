{#
  Recorte de longões. Definição: sport_type='Run' AND moving_time_s >= 3600
  (mesmo limiar usado em compute_decoupling).
  Enriquecido com CTL/ATL/TSB do dia para responder "decoupling caminhando junto com
  fadiga acumulada?".
#}

with long_runs as (
    select
        f.activity_id,
        f.date_key,
        f.start_date_local,
        f.distance_km,
        f.moving_time_s,
        f.pace_s_per_km,
        f.average_heartrate,
        f.elevation_gain_m,
        coalesce(f.r_tss, f.hr_tss) as tss,
        f.aerobic_efficiency,
        f.decoupling_pct,
        f.ngp_mps,
        f.z1_seconds,
        f.z2_seconds,
        f.z3_seconds,
        f.z4_seconds,
        f.z5_seconds,
        da.sport_type,
        da.is_race
    from {{ ref('fct_activity') }} f
    left join {{ ref('dim_activity') }} da using (activity_id)
    where da.sport_type = 'Run'
      and f.moving_time_s >= 3600
)

select
    lr.activity_id,
    lr.date_key,
    lr.start_date_local,
    lr.is_race,

    -- métricas próprias do longão
    lr.distance_km,
    lr.moving_time_s,
    lr.moving_time_s / 3600.0 as moving_time_h,
    lr.pace_s_per_km,
    lr.average_heartrate,
    lr.elevation_gain_m,
    lr.tss,
    lr.aerobic_efficiency,
    lr.decoupling_pct,
    lr.ngp_mps,

    -- distribuição em zona (só por conveniência — útil pra ver se foi long em Z2 puro
    -- ou se teve trechos de quality)
    lr.z1_seconds,
    lr.z2_seconds,
    lr.z3_seconds,
    lr.z4_seconds,
    lr.z5_seconds,

    -- contexto de forma no dia (carga acumulada que o atleta estava carregando)
    fdl.ctl as ctl_on_date,
    fdl.atl as atl_on_date,
    fdl.tsb as tsb_on_date

from long_runs lr
left join {{ ref('fct_daily_load') }} fdl on lr.date_key = fdl.date_key
