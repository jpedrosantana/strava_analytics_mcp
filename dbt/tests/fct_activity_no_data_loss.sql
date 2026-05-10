{#
  Acceptance da Fase D2: count(fct_activity) == count(stg_strava__activities).
  Falha se alguma atividade do staging não chegar ao fato.
  Retorna o(s) activity_id(s) órfão(s); teste passa quando 0 linhas.
#}

select stg.activity_id
from {{ ref('stg_strava__activities') }} stg
left join {{ ref('fct_activity') }} fa
    on fa.activity_id = stg.activity_id
where fa.activity_id is null
