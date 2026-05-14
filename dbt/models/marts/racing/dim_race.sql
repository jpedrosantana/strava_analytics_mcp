{#
  Dimensão de prova. Identificação em camadas (spec §12.4):
    1. Override manual via seed `manual_races` (prioridade máxima)
    2. Heurística automática: workout_type = 1 no Strava

  Quando uma atividade aparece nos dois, o seed vence em todos os campos
  porque ele tem distância oficial e objetivo (informação que o Strava não
  carrega). Activities marcadas como race no Strava mas ausentes do seed
  entram com defaults conservadores (completed=true, is_official=false,
  distance_official derivada da distance_m do clock).

  Mapeia distance_official_km para o vocabulário de distance_label de
  best_efforts quando a distância oficial cai numa das padrão — assim
  `fct_race_performance` pode juntar diretamente com best efforts daquela
  distância sem regex.
#}

with seed as (
    select * from {{ ref('manual_races') }} where is_race
),

workout_type_races as (
    select
        activity_id,
        name as activity_name,
        distance_m / 1000.0 as heuristic_distance_km
    from {{ ref('stg_strava__activities') }}
    where workout_type = 1
),

combined as (
    select
        coalesce(s.activity_id, w.activity_id) as activity_id,
        coalesce(s.race_name, w.activity_name) as race_name,
        coalesce(s.distance_official_km, w.heuristic_distance_km) as distance_official_km,
        coalesce(s.is_official, false) as is_official,
        coalesce(s.completed, true) as completed,
        s.objective,
        case
            when s.activity_id is not null then 'seed'
            else 'workout_type'
        end as detection_source
    from seed s
    full outer join workout_type_races w on s.activity_id = w.activity_id
),

with_label as (
    select
        c.*,
        case
            when abs(c.distance_official_km - 1.0) < 0.05 then '1K'
            when abs(c.distance_official_km - 5.0) < 0.1 then '5K'
            when abs(c.distance_official_km - 10.0) < 0.1 then '10K'
            when abs(c.distance_official_km - 15.0) < 0.1 then '15K'
            when abs(c.distance_official_km - 21.0975) < 0.1 then 'Half Marathon'
            when abs(c.distance_official_km - 25.0) < 0.1 then '25K'
            when abs(c.distance_official_km - 30.0) < 0.1 then '30K'
            when abs(c.distance_official_km - 42.195) < 0.1 then 'Marathon'
            else null
        end as distance_label
    from combined c
)

select
    w.activity_id,
    cast(a.start_date_local as date) as race_date,
    w.race_name,
    w.distance_official_km,
    w.distance_label,
    w.is_official,
    w.completed,
    w.objective,
    w.detection_source
from with_label w
join {{ ref('stg_strava__activities') }} a on a.activity_id = w.activity_id
