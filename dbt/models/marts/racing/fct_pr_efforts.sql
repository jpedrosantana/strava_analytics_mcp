{#
  Fato dos best efforts por distância-padrão. Grão: 1 linha por
  (activity_id, distance_label). Adiciona:
    - rank dentro da distância (1 = PR atual)
    - is_pr (rank = 1)
    - pace_s_per_km derivado de time_s / distance_m

  Mart consumido pelo Streamlit (página de Provas/PRs) e pelo
  fct_race_performance para projeções Riegel/VDOT.
#}

with efforts as (
    select * from {{ ref('stg_strava__activity_best_efforts') }}
),

activity_meta as (
    select
        activity_id,
        name as activity_name,
        cast(start_date_local as date) as date_key,
        start_date_local,
        distance_m as parent_distance_m,
        moving_time_s as parent_moving_time_s,
        average_heartrate as activity_avg_heartrate
    from {{ ref('stg_strava__activities') }}
)

select
    e.activity_id,
    e.distance_label,
    e.distance_m,
    e.time_s,
    e.time_s / (e.distance_m / 1000.0) as pace_s_per_km,
    e.segment_start_s,
    e.segment_end_s,
    a.date_key,
    a.start_date_local,
    a.activity_name,
    a.parent_distance_m,
    a.parent_moving_time_s,
    a.activity_avg_heartrate,
    -- esforço veio de uma corrida cheia ou de um split dentro de algo maior?
    case
        when a.parent_distance_m > e.distance_m * 1.05 then true
        else false
    end as is_segment,
    -- rank: 1 = PR atual da distância
    row_number() over (
        partition by e.distance_label
        order by e.time_s asc
    ) as effort_rank,
    case
        when row_number() over (
            partition by e.distance_label
            order by e.time_s asc
        ) = 1 then true
        else false
    end as is_pr

from efforts e
join activity_meta a on a.activity_id = e.activity_id
