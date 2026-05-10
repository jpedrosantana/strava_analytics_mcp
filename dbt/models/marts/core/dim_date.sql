{#
  Dimensão de calendário. Range fixo cobrindo histórico Strava + buffer.
  Atualizar o intervalo se o atleta começar a usar o app antes de 2024
  ou se o projeto for ativo após 2030.
#}

with date_spine as (
    select range::date as date
    from range(timestamp '2024-01-01', timestamp '2031-01-01', interval 1 day)
)

select
    date,

    -- componentes principais
    extract(year from date)::integer as year,
    extract(quarter from date)::integer as quarter,
    extract(month from date)::integer as month,
    monthname(date) as month_name,
    extract(day from date)::integer as day_of_month,

    -- ISO week (segunda = 1, domingo = 7)
    extract(isodow from date)::integer as iso_day_of_week,
    dayname(date) as day_name,
    extract(week from date)::integer as iso_week,
    extract(isoyear from date)::integer as iso_year,
    cast(extract(isoyear from date) as varchar)
        || '-W'
        || lpad(cast(extract(week from date) as varchar), 2, '0') as iso_year_week,

    -- flags úteis
    extract(isodow from date) >= 6 as is_weekend,
    extract(day from date) = 1 as is_month_start,
    last_day(date) = date as is_month_end

from date_spine
