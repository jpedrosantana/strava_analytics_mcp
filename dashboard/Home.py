"""Landing page do dashboard. Mostra forma atual + últimas atividades."""

import streamlit as st

from db import query
from theme import ACWR_HIGH, ACWR_LOW, tsb_label

st.set_page_config(
    page_title="Strava Analytics",
    page_icon="🏃",
    layout="wide",
)

st.title("🏃 Strava Analytics")
st.caption("Plataforma pessoal de análise esportiva")

# Forma atual (último dia disponível)
form_today = query(
    """
    select
        date_key,
        ctl,
        atl,
        tsb,
        case when ctl > 0 then atl / ctl end as acwr
    from marts.fct_daily_load
    order by date_key desc
    limit 1
    """
).iloc[0]

st.subheader(f"Forma atual — {form_today['date_key']}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("CTL (fitness, 42d)", f"{form_today['ctl']:.1f}")
c2.metric("ATL (fadiga, 7d)", f"{form_today['atl']:.1f}")
c3.metric(
    "TSB (forma)",
    f"{form_today['tsb']:+.1f}",
    delta=tsb_label(form_today["tsb"]),
    delta_color="off",
)
acwr = form_today["acwr"]
acwr_status = "sweet spot" if ACWR_LOW <= acwr <= ACWR_HIGH else "fora do safe"
c4.metric("ACWR", f"{acwr:.2f}", delta=acwr_status, delta_color="off")

st.divider()

# Últimos 7 dias
st.subheader("Últimos 7 dias — TSS diário")

last7 = query(
    """
    select
        date_key,
        round(daily_tss, 0) as tss
    from marts.fct_daily_load
    order by date_key desc
    limit 7
    """
).iloc[::-1]

st.bar_chart(last7.set_index("date_key")["tss"], height=200)

st.divider()

# Últimas 5 atividades
st.subheader("Últimas atividades")
last_acts = query(
    """
    select
        f.date_key as data,
        d.activity_name as nome,
        d.sport_type as esporte,
        round(f.distance_km, 2) as km,
        round(f.moving_time_s / 60.0, 0) as duracao_min,
        round(f.average_heartrate, 0) as fc_media,
        round(coalesce(f.r_tss, f.hr_tss), 0) as tss
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    order by f.start_date_local desc
    limit 5
    """
)
st.dataframe(last_acts, hide_index=True, use_container_width=True)

st.caption("Use a barra lateral para navegar entre páginas.")
