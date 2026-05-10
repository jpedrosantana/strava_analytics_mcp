{#
  Fato no grão de um mês calendário. Análogo a fct_weekly_summary, mas
  agregado por (year, month). Útil para o painel anual / comparação ano-a-ano.
  CTL/ATL/TSB amostrados no último dia do mês com dado disponível em fct_daily_load.
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

activities_with_month as (
    select
        a.*,
        dd.year,
        dd.month
    from activities_enriched a
    join {{ ref('dim_date') }} dd on a.date_key = dd.date
),

monthly_aggregates as (
    select
        year,
        month,

        count(*) as n_activities,
        sum(distance_km) as total_distance_km,
        sum(moving_time_s) / 3600.0 as total_moving_time_h,
        sum(tss) as total_tss,

        count(*) filter (where sport_type = 'Run') as n_runs,
        sum(distance_km) filter (where sport_type = 'Run') as run_distance_km,
        sum(moving_time_s) filter (where sport_type = 'Run') / 3600.0 as run_moving_time_h,
        sum(tss) filter (where sport_type = 'Run') as run_tss,

        count(*) filter (
            where sport_type = 'Run' and moving_time_s >= 3600
        ) as n_long_runs,
        count(*) filter (
            where sport_type = 'Run'
              and coalesce(z4_seconds, 0) + coalesce(z5_seconds, 0) >= 600
        ) as n_quality_sessions

    from activities_with_month
    group by year, month
),

month_boundaries as (
    select
        year,
        month,
        min(date) as month_start_date,
        max(date) as month_end_date
    from {{ ref('dim_date') }}
    group by year, month
),

load_end_of_month as (
    -- Última leitura de CTL/ATL/TSB disponível no intervalo do mês
    select
        mb.year,
        mb.month,
        fdl_last.ctl as ctl_end_of_month,
        fdl_last.atl as atl_end_of_month,
        fdl_last.tsb as tsb_end_of_month
    from month_boundaries mb
    left join lateral (
        select ctl, atl, tsb
        from {{ ref('fct_daily_load') }}
        where date_key between mb.month_start_date and mb.month_end_date
        order by date_key desc
        limit 1
    ) fdl_last on true
)

select
    ma.year,
    ma.month,
    mb.month_start_date,
    mb.month_end_date,

    ma.n_activities,
    ma.total_distance_km,
    ma.total_moving_time_h,
    ma.total_tss,

    ma.n_runs,
    coalesce(ma.run_distance_km, 0) as run_distance_km,
    coalesce(ma.run_moving_time_h, 0) as run_moving_time_h,
    coalesce(ma.run_tss, 0) as run_tss,

    ma.n_long_runs,
    ma.n_quality_sessions,

    le.ctl_end_of_month,
    le.atl_end_of_month,
    le.tsb_end_of_month

from monthly_aggregates ma
join month_boundaries mb using (year, month)
left join load_end_of_month le using (year, month)
