"""Página 1 — Visão Geral. Volume e distribuição de atividades."""

import pandas as pd
import plotly.express as px
import streamlit as st
from db import query

st.set_page_config(
    page_title="Visão Geral — Strava Analytics",
    page_icon="📅",
    layout="wide",
)

st.title("📅 Visão Geral")
st.caption("Volume e distribuição de atividades")

# Sidebar — filtros
with st.sidebar:
    st.header("Filtros")
    period_options = {
        "30 dias": 30,
        "90 dias": 90,
        "180 dias": 180,
        "365 dias": 365,
        "Tudo": None,
    }
    period_label = st.selectbox("Período", list(period_options.keys()), index=2)
    period_days = period_options[period_label]

if period_days:
    where_period = f"f.date_key >= current_date - interval {period_days} day"
    daily_filter = f"date_key >= current_date - interval {period_days} day"
else:
    where_period = "1=1"
    daily_filter = "1=1"

# KPIs
totals = query(
    f"""
    select
        count(*) as n_activities,
        round(sum(f.distance_km), 1) as total_km,
        round(sum(f.moving_time_s) / 3600.0, 1) as total_hours,
        round(sum(f.elevation_gain_m), 0) as total_elev_m
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where {where_period}
    """
).iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Atividades", int(totals["n_activities"] or 0))
c2.metric("Distância total", f"{totals['total_km'] or 0} km")
c3.metric("Tempo total", f"{totals['total_hours'] or 0} h")
c4.metric("Elevação", f"{int(totals['total_elev_m'] or 0)} m")

st.divider()

# Calendar heatmap
st.subheader("Calendário de carga diária")
st.caption(
    "Cada célula é um dia: **linhas** = dia da semana, **colunas** = semanas. "
    "**Cor mais escura = mais carga (TSS)** naquele dia. Passe o mouse para ver o valor."
)

daily = query(
    f"""
    select date_key, daily_tss
    from marts.fct_daily_load
    where {daily_filter}
    order by date_key
    """
)

if not daily.empty and daily["daily_tss"].sum() > 0:
    daily["date_key"] = pd.to_datetime(daily["date_key"])
    daily["weekday_num"] = daily["date_key"].dt.weekday  # 0=Mon
    daily["week_start"] = daily["date_key"] - pd.to_timedelta(daily["weekday_num"], unit="d")

    pivot = (
        daily.pivot_table(
            index="weekday_num",
            columns="week_start",
            values="daily_tss",
            aggfunc="sum",
        )
        .reindex(range(7))
        .fillna(0)
    )

    weekday_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    fig = px.imshow(
        pivot.values,
        labels=dict(x="Semana de", y="Dia", color="TSS"),
        x=[d.strftime("%d/%m") for d in pivot.columns],
        y=weekday_labels,
        color_continuous_scale="Greens",
        aspect="auto",
    )
    fig.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=10, b=10),
        coloraxis_colorbar=dict(title="TSS"),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sem dados de carga no período.")

st.divider()

# Sport breakdown
col_left, col_right = st.columns([1, 1])

by_sport = query(
    f"""
    select
        d.sport_type as esporte,
        count(*) as atividades,
        round(sum(f.distance_km), 1) as km,
        round(sum(f.moving_time_s) / 3600.0, 1) as horas
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where {where_period}
    group by d.sport_type
    order by atividades desc
    """
)

with col_left:
    st.subheader("Distribuição por esporte")
    st.dataframe(by_sport, hide_index=True, use_container_width=True)

with col_right:
    st.subheader("Distribuição por esporte (atividades)")
    if not by_sport.empty and by_sport["atividades"].sum() > 0:
        fig_pie = px.pie(by_sport, names="esporte", values="atividades", hole=0.4)
        fig_pie.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="v"),
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Sem atividades no período.")

st.divider()

# Atividades recentes
st.subheader("Atividades recentes")
acts = query(
    f"""
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
    where {where_period}
    order by f.start_date_local desc
    limit 30
    """
)
st.dataframe(acts, hide_index=True, use_container_width=True)
