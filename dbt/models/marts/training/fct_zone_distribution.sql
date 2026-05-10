{#
  Tempo em zonas de FC (Z1-Z5) agregado por semana ISO, formato wide.
  total_with_hr_seconds = soma das zonas, separa "sem FC registrada" de "tempo em Z0".
  total_moving_seconds inclui atividades sem FC — diferença com total_with_hr ajuda
  a auditar cobertura do stream de FC.
#}

with activities_with_week as (
    select
        f.activity_id,
        f.moving_time_s,
        coalesce(f.z1_seconds, 0) as z1_seconds,
        coalesce(f.z2_seconds, 0) as z2_seconds,
        coalesce(f.z3_seconds, 0) as z3_seconds,
        coalesce(f.z4_seconds, 0) as z4_seconds,
        coalesce(f.z5_seconds, 0) as z5_seconds,
        case
            when f.z1_seconds is not null then 1
            else 0
        end as has_zone_data,
        dd.iso_year_week,
        dd.iso_year,
        dd.iso_week,
        da.sport_type
    from {{ ref('fct_activity') }} f
    join {{ ref('dim_date') }} dd on f.date_key = dd.date
    left join {{ ref('dim_activity') }} da using (activity_id)
)

select
    iso_year_week,
    any_value(iso_year) as iso_year,
    any_value(iso_week) as iso_week,

    sum(z1_seconds) as z1_seconds,
    sum(z2_seconds) as z2_seconds,
    sum(z3_seconds) as z3_seconds,
    sum(z4_seconds) as z4_seconds,
    sum(z5_seconds) as z5_seconds,

    sum(z1_seconds + z2_seconds + z3_seconds + z4_seconds + z5_seconds)
        as total_with_hr_seconds,
    sum(moving_time_s) as total_moving_seconds,

    -- recorte só de corrida: mesmas colunas mas filtradas
    sum(z1_seconds) filter (where sport_type = 'Run') as run_z1_seconds,
    sum(z2_seconds) filter (where sport_type = 'Run') as run_z2_seconds,
    sum(z3_seconds) filter (where sport_type = 'Run') as run_z3_seconds,
    sum(z4_seconds) filter (where sport_type = 'Run') as run_z4_seconds,
    sum(z5_seconds) filter (where sport_type = 'Run') as run_z5_seconds,

    sum(z1_seconds + z2_seconds + z3_seconds + z4_seconds + z5_seconds)
        filter (where sport_type = 'Run')
        as run_total_with_hr_seconds,
    sum(moving_time_s) filter (where sport_type = 'Run')
        as run_total_moving_seconds,

    sum(has_zone_data) as n_activities_with_hr,
    count(*) as n_activities

from activities_with_week
group by iso_year_week
