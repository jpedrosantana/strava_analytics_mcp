{#
  Fato de performance em prova. Grão: 1 linha por prova de `dim_race`.

  Junta:
    - tempo, pace, FC da atividade-fonte (`fct_activity`)
    - forma do dia: CTL/ATL/TSB de `fct_daily_load` na data da prova
    - clima registrado no relógio (`weather_temp_c` do activity_metrics)
    - rank dentro da mesma distance_label (só corridas completas entram)
    - projeção Riegel para a maratona (expoente 1.06) — para o atleta no ciclo
      atual, isso responde "se eu rodei essa meia em X, qual é minha maratona
      projetada por esse desempenho?"

  Pace usa `distance_official_km` quando o seed/heurística dá a oficial; do
  contrário cai no `distance_m` do clock. Isso corrige casos como o
  "Revezamento Maratona Fila" onde o relógio gravou 20,76 km mas a distância
  real foi 21,0975 km.
#}

with races as (
    select * from {{ ref('dim_race') }}
),

activity_full as (
    select * from {{ ref('fct_activity') }}
),

daily_load as (
    select date_key, ctl, atl, tsb from {{ ref('fct_daily_load') }}
),

joined as (
    select
        r.activity_id,
        r.race_date,
        r.race_name,
        r.distance_official_km,
        r.distance_label,
        r.is_official,
        r.completed,
        r.objective,
        r.detection_source,

        a.moving_time_s as time_s,
        a.distance_m as gps_distance_m,
        case
            when r.distance_official_km is not null
                then a.moving_time_s / r.distance_official_km
            when a.distance_m > 0
                then a.moving_time_s / (a.distance_m / 1000.0)
        end as pace_s_per_km,

        a.average_heartrate,
        a.r_tss,
        a.hr_tss,
        a.weather_temp_c,

        d.ctl as ctl_on_race_day,
        d.atl as atl_on_race_day,
        d.tsb as tsb_on_race_day
    from races r
    join activity_full a on a.activity_id = r.activity_id
    left join daily_load d on d.date_key = r.race_date
)

select
    *,
    -- Riegel: T2 = T1 * (D2/D1)^1.06. Projeta o tempo desta prova para 42.195 km.
    -- Null quando não temos distância oficial — preferimos NULL a um número
    -- ruidoso vindo do GPS inflado.
    case
        when distance_official_km > 0 and time_s > 0 then
            time_s * power(42.195 / distance_official_km, 1.06)
    end as projected_marathon_time_s,

    -- Rank entre provas completadas da mesma distância. NULL fora desse universo.
    case
        when completed and distance_label is not null then
            row_number() over (
                partition by distance_label, completed
                order by time_s asc
            )
    end as rank_in_distance,

    case
        when completed and distance_label is not null then
            count(*) over (partition by distance_label, completed)
    end as total_in_distance

from joined
