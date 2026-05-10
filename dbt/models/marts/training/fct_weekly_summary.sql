{#
  Fato no grão de uma semana ISO. Agrega volume, carga e qualidade da semana.
  Coluna `*_run` separa corridas de cross-training (musculação/funcional) — relevante
  para o ciclo de maratona, onde o volume de corrida é o KPI primário.
  CTL/ATL/TSB são amostrados no último dia da semana (domingo) via fct_daily_load.
#}

with activities_enriched as (
    select
        f.activity_id,
        f.date_key,
        f.distance_km,
        f.moving_time_s,
        f.z4_seconds,
        f.z5_seconds,
        coalesce(f.r_tss, f.hr_tss) as tss,
        d.sport_type
    from {{ ref('fct_activity') }} f
    left join {{ ref('dim_activity') }} d using (activity_id)
),

activities_with_week as (
    select
        a.*,
        dd.iso_year_week,
        dd.iso_year,
        dd.iso_week
    from activities_enriched a
    join {{ ref('dim_date') }} dd on a.date_key = dd.date
),

weekly_aggregates as (
    select
        iso_year_week,
        any_value(iso_year) as iso_year,
        any_value(iso_week) as iso_week,

        -- volume total (todos os esportes)
        count(*) as n_activities,
        sum(distance_km) as total_distance_km,
        sum(moving_time_s) / 3600.0 as total_moving_time_h,
        sum(tss) as total_tss,

        -- volume de corrida
        count(*) filter (where sport_type = 'Run') as n_runs,
        sum(distance_km) filter (where sport_type = 'Run') as run_distance_km,
        sum(moving_time_s) filter (where sport_type = 'Run') / 3600.0 as run_moving_time_h,
        sum(tss) filter (where sport_type = 'Run') as run_tss,

        -- qualidade (definições travadas no plano D3)
        count(*) filter (
            where sport_type = 'Run' and moving_time_s >= 3600
        ) as n_long_runs,
        count(*) filter (
            where sport_type = 'Run'
              and coalesce(z4_seconds, 0) + coalesce(z5_seconds, 0) >= 600
        ) as n_quality_sessions

    from activities_with_week
    group by iso_year_week
),

week_boundaries as (
    -- Min/max date e o domingo (iso_day_of_week=7) de cada semana ISO
    select
        iso_year_week,
        min(date) as week_start_date,
        max(date) as week_end_date,
        max(date) filter (where iso_day_of_week = 7) as week_sunday
    from {{ ref('dim_date') }}
    group by iso_year_week
),

load_end_of_week as (
    -- CTL/ATL/TSB no domingo da semana. Se o domingo ainda não chegou
    -- (semana corrente), usa o último dia disponível em fct_daily_load.
    select
        wb.iso_year_week,
        coalesce(fdl_sun.ctl, fdl_last.ctl) as ctl_end_of_week,
        coalesce(fdl_sun.atl, fdl_last.atl) as atl_end_of_week,
        coalesce(fdl_sun.tsb, fdl_last.tsb) as tsb_end_of_week
    from week_boundaries wb
    left join {{ ref('fct_daily_load') }} fdl_sun
        on wb.week_sunday = fdl_sun.date_key
    left join lateral (
        select ctl, atl, tsb
        from {{ ref('fct_daily_load') }}
        where date_key between wb.week_start_date and wb.week_end_date
        order by date_key desc
        limit 1
    ) fdl_last on true
)

select
    -- chave
    wa.iso_year_week,
    wa.iso_year,
    wa.iso_week,
    wb.week_start_date,
    wb.week_end_date,

    -- volume total
    wa.n_activities,
    wa.total_distance_km,
    wa.total_moving_time_h,
    wa.total_tss,

    -- volume de corrida
    wa.n_runs,
    coalesce(wa.run_distance_km, 0) as run_distance_km,
    coalesce(wa.run_moving_time_h, 0) as run_moving_time_h,
    coalesce(wa.run_tss, 0) as run_tss,

    -- qualidade
    wa.n_long_runs,
    wa.n_quality_sessions,

    -- carga fim de semana (snapshot domingo)
    le.ctl_end_of_week,
    le.atl_end_of_week,
    le.tsb_end_of_week

from weekly_aggregates wa
join week_boundaries wb using (iso_year_week)
left join load_end_of_week le using (iso_year_week)
