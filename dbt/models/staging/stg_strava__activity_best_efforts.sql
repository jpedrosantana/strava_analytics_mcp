{#
  Staging para best efforts em distâncias-padrão calculados pelo
  compute-metrics (PR #22). Grão: 1 linha por (activity_id, distance_label).
#}

select
    activity_id,
    distance_label,
    distance_m,
    time_s,
    segment_start_s,
    segment_end_s,
    start_idx,
    end_idx,
    computed_at

from {{ source('strava_raw', 'activity_best_efforts') }}
