"""Página 2 — Carga e Forma. Performance Management Chart + ACWR."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from db import query
from plotly.subplots import make_subplots
from theme import (
    ACWR_HIGH,
    ACWR_LOW,
    TSB_FRESH_THRESHOLD,
    TSB_LOADED_THRESHOLD,
    TSB_PRODUCTIVE_THRESHOLD,
    tsb_color,
    tsb_label,
)

st.set_page_config(
    page_title="Carga e Forma — Strava Analytics",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Carga e Forma")
st.caption("Performance Management Chart (CTL / ATL / TSB) e ACWR")

# Sidebar
with st.sidebar:
    st.header("Filtros")
    period_options = {"90 dias": 90, "180 dias": 180, "365 dias": 365, "Tudo": None}
    period_label = st.selectbox("Período", list(period_options.keys()), index=1)
    period_days = period_options[period_label]

# Forma atual
today = query(
    """
    select date_key, ctl, atl, tsb,
           case when ctl > 0 then atl / ctl end as acwr
    from marts.fct_daily_load
    order by date_key desc limit 1
    """
).iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("CTL (fitness)", f"{today['ctl']:.1f}")
c2.metric("ATL (fadiga)", f"{today['atl']:.1f}")
c3.metric(
    "TSB (forma)",
    f"{today['tsb']:+.1f}",
    delta=tsb_label(today["tsb"]),
    delta_color="off",
)
acwr = today["acwr"]
in_safe = ACWR_LOW <= acwr <= ACWR_HIGH
c4.metric(
    "ACWR",
    f"{acwr:.2f}",
    delta=("sweet spot" if in_safe else "fora do safe"),
    delta_color="off",
)

st.divider()

# PMC chart
st.subheader("Performance Management Chart")
st.caption(
    "**CTL** (linha azul) é fitness — média exponencial de 42 dias do TSS, "
    "sobe e cai devagar. **ATL** (linha vermelha tracejada) é fadiga, mesma "
    "lógica em janela de 7 dias, reage rápido. **TSB = CTL − ATL** (barras) "
    "é a forma do dia: positivo = descansado, negativo = carregado."
)

where_pmc = (
    f"date_key >= current_date - interval {period_days} day"
    if period_days
    else "1=1"
)

pmc = query(
    f"""
    select date_key, daily_tss, ctl, atl, tsb
    from marts.fct_daily_load
    where {where_pmc}
    order by date_key
    """
)

if not pmc.empty:
    pmc["date_key"] = pd.to_datetime(pmc["date_key"])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    tsb_colors = [tsb_color(v) for v in pmc["tsb"]]
    fig.add_trace(
        go.Bar(
            x=pmc["date_key"],
            y=pmc["tsb"],
            name="TSB (forma)",
            marker_color=tsb_colors,
            opacity=0.55,
        ),
        secondary_y=True,
    )

    fig.add_trace(
        go.Scatter(
            x=pmc["date_key"],
            y=pmc["ctl"],
            mode="lines",
            name="CTL (fitness)",
            line=dict(color="#2563eb", width=2.5),
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=pmc["date_key"],
            y=pmc["atl"],
            mode="lines",
            name="ATL (fadiga)",
            line=dict(color="#dc2626", width=1.5, dash="dash"),
        ),
        secondary_y=False,
    )

    fig.update_yaxes(title_text="CTL / ATL (TSS)", secondary_y=False)
    fig.update_yaxes(
        title_text="TSB",
        secondary_y=True,
        zerolinecolor="#9ca3af",
        zerolinewidth=1,
    )
    fig.update_layout(
        height=480,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sem dados de carga no período.")

st.caption(
    f"Zonas TSB: **fresh** (>+{TSB_FRESH_THRESHOLD}) · "
    f"**produtivo** ({TSB_PRODUCTIVE_THRESHOLD} a +{TSB_FRESH_THRESHOLD}) · "
    f"**carregado** ({TSB_LOADED_THRESHOLD} a {TSB_PRODUCTIVE_THRESHOLD}) · "
    f"**risco** (<{TSB_LOADED_THRESHOLD})"
)

st.divider()

# ACWR chart
st.subheader("ACWR ao longo do tempo")
st.caption(
    "**ACWR = ATL / CTL** — razão entre carga aguda e crônica. A literatura "
    "sugere **0,8–1,3** como zona segura (banda verde): abaixo, subtreinamento; "
    "acima, risco aumentado de lesão por progressão rápida demais."
)

if not pmc.empty:
    acwr_df = pmc.copy()
    acwr_df["acwr"] = (acwr_df["atl"] / acwr_df["ctl"]).where(acwr_df["ctl"] > 0)

    fig2 = go.Figure()

    fig2.add_hrect(
        y0=ACWR_LOW,
        y1=ACWR_HIGH,
        fillcolor="rgba(16,185,129,0.12)",
        line_width=0,
        annotation_text="safe (0.8–1.3)",
        annotation_position="top right",
    )

    fig2.add_trace(
        go.Scatter(
            x=acwr_df["date_key"],
            y=acwr_df["acwr"],
            mode="lines",
            name="ACWR",
            line=dict(color="#1f2937", width=2),
        )
    )

    fig2.update_layout(
        height=300,
        yaxis_title="ACWR",
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode="x unified",
    )
    st.plotly_chart(fig2, use_container_width=True)
