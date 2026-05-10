{#
  Dimensão de atividade — atributos descritivos (categóricos / identificadores).
  SCD tipo 1: sobrescreve. Histórico não é mantido aqui (qualquer mudança no Strava
  reflete na próxima sincronização).
#}

select
    activity_id,

    -- nome livre dado pelo atleta
    name as activity_name,

    -- categoria do esporte (vocabulário Strava: Run, Ride, Swim, etc.)
    sport_type,

    -- subtipo Strava
    workout_type,
    workout_type = 1 as is_race,
    workout_type = 2 as is_long_run_flagged,
    workout_type = 3 as is_workout_session,

    -- contexto de captura
    timezone,
    has_heartrate,
    has_powermeter,

    -- flags de modalidade
    trainer,
    commute,
    manual

from {{ ref('stg_strava__activities') }}
