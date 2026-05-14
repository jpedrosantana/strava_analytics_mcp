"""Página 5 — Clima. Impacto da temperatura no pace e na eficiência."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from db import query

st.set_page_config(
    page_title="Clima — Strava Analytics",
    page_icon="🌦️",
    layout="wide",
)

st.title("🌦️ Clima")
st.caption("Como a temperatura afeta o pace e a eficiência aeróbica")


def _fmt_pace(pace_s_per_km: float | None) -> str:
    if pace_s_per_km is None or pd.isna(pace_s_per_km) or pace_s_per_km <= 0:
        return "—"
    m, s = divmod(int(round(pace_s_per_km)), 60)
    return f"{m}:{s:02d}/km"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Filtros")
    only_easy = st.checkbox(
        "Apenas corridas fáceis (pace > 5:00/km)",
        value=False,
        help=(
            "Corridas duras (intervalado, prova) confundem o sinal — o pace já é "
            "atípico por desenho. Filtrar facilita ver o efeito da temperatura "
            "sobre o ritmo natural."
        ),
    )
    min_distance_km = st.slider("Distância mínima (km)", 0, 15, 5)


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------

base_filter = (
    f"f.weather_temp_c is not null and d.sport_type = 'Run' and f.distance_km >= {min_distance_km}"
)
if only_easy:
    base_filter += " and f.pace_s_per_km > 300"

df = query(
    f"""
    select
        f.activity_id,
        cast(f.start_date_local as date) as data,
        d.activity_name as nome,
        f.distance_km,
        f.pace_s_per_km,
        f.average_heartrate as fc_media,
        f.aerobic_efficiency,
        f.weather_temp_c as temp_c,
        d.is_race
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where {base_filter}
    order by f.start_date_local
    """
)

# Cobertura
total_runs = query(
    f"""
    select count(*) as n
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where d.sport_type='Run' and f.distance_km >= {min_distance_km}
    """
).iloc[0]["n"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Corridas no filtro", len(df))
c2.metric(
    "Cobertura temp",
    f"{len(df)}/{int(total_runs)}",
    delta=f"{100 * len(df) / max(total_runs, 1):.0f}%",
    delta_color="off",
)
if not df.empty:
    c3.metric("Temp média", f"{df['temp_c'].mean():.1f}°C")
    c4.metric(
        "Range temp",
        f"{df['temp_c'].min():.0f}–{df['temp_c'].max():.0f}°C",
    )

if df.empty:
    st.info(
        "Sem corridas no filtro com `weather_temp_c` populado. "
        "Tente reduzir a distância mínima ou desmarcar 'apenas fáceis'."
    )
    st.stop()

st.caption(
    f"Cobertura geral: temp do relógio Garmin/Strava está em **64%** das corridas "
    f"(indoor naturalmente sem sensor de temperatura). Range observado: "
    f"**{df['temp_c'].min():.0f}–{df['temp_c'].max():.0f}°C**, "
    f"refletindo clima tropical (São Paulo)."
)

st.divider()

# ---------------------------------------------------------------------------
# Pace vs temperatura
# ---------------------------------------------------------------------------

st.subheader("Pace × temperatura")
st.caption(
    "Cada ponto é uma corrida. Provas em vermelho destacam outliers de esforço. "
    "Linha de tendência OLS mostra a inclinação média do pace com calor: "
    "a literatura de fisiologia espera **~+2-5 s/km por °C** acima de 15°C "
    "para corridas em ritmo aeróbico."
)

df_plot = df.copy()
df_plot["pace_str"] = df_plot["pace_s_per_km"].apply(_fmt_pace)
df_plot["tipo"] = df_plot["is_race"].map({True: "prova", False: "treino"})

fig = px.scatter(
    df_plot,
    x="temp_c",
    y="pace_s_per_km",
    color="tipo",
    color_discrete_map={"prova": "#dc2626", "treino": "#2563eb"},
    hover_data={
        "nome": True,
        "data": True,
        "distance_km": ":.1f",
        "pace_str": True,
        "temp_c": ":.1f",
        "pace_s_per_km": False,
        "tipo": False,
    },
    labels={
        "temp_c": "Temperatura (°C)",
        "pace_s_per_km": "Pace (s/km)",
        "tipo": "Tipo",
    },
)
fig.update_traces(marker=dict(size=9, opacity=0.7), selector=dict(mode="markers"))

# Trendline manual via polyfit — evita dependência de statsmodels.
slope_pace = intercept_pace = None
if len(df) >= 5:
    slope_pace, intercept_pace = np.polyfit(df["temp_c"], df["pace_s_per_km"], 1)
    x_trend = np.array([df["temp_c"].min(), df["temp_c"].max()])
    fig.add_trace(
        go.Scatter(
            x=x_trend,
            y=slope_pace * x_trend + intercept_pace,
            mode="lines",
            line=dict(color="#1f2937", width=2, dash="dash"),
            name="Tendência (OLS)",
            hovertemplate=(
                f"Slope: {slope_pace:+.1f} s/km/°C<br>"
                f"Intercept: {intercept_pace:.1f} s/km<extra></extra>"
            ),
        )
    )

fig.update_yaxes(
    autorange="reversed",
    tickvals=[240, 270, 300, 330, 360, 390, 420],
    ticktext=["4:00", "4:30", "5:00", "5:30", "6:00", "6:30", "7:00"],
)
fig.update_layout(height=440, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

if slope_pace is not None:
    direction = "mais lento" if slope_pace > 0 else "mais rápido"
    st.caption(
        f"**Inclinação observada:** pace fica **{abs(slope_pace):.1f} s/km {direction}** "
        f"a cada **+1°C**. Pace estimado a 20°C: "
        f"**{_fmt_pace(20 * slope_pace + intercept_pace)}**, "
        f"a 30°C: **{_fmt_pace(30 * slope_pace + intercept_pace)}**."
    )

st.divider()

# ---------------------------------------------------------------------------
# Boxplot por faixa de temperatura
# ---------------------------------------------------------------------------

st.subheader("Pace por faixa de temperatura")
st.caption(
    "Distribuição (mediana, quartis, outliers) do pace agrupado por faixa "
    "térmica. Útil pra estimar pace-alvo em prova dependendo da temp esperada."
)


def temp_bucket(t: float) -> str:
    if t < 20:
        return "< 20°C"
    if t < 23:
        return "20-23°C"
    if t < 26:
        return "23-26°C"
    if t < 29:
        return "26-29°C"
    return "≥ 29°C"


df["faixa_temp"] = df["temp_c"].apply(temp_bucket)
order = ["< 20°C", "20-23°C", "23-26°C", "26-29°C", "≥ 29°C"]

box_fig = px.box(
    df,
    x="faixa_temp",
    y="pace_s_per_km",
    category_orders={"faixa_temp": order},
    points="all",
    color_discrete_sequence=["#2563eb"],
    labels={"faixa_temp": "Faixa de temperatura", "pace_s_per_km": "Pace (s/km)"},
)
box_fig.update_yaxes(
    autorange="reversed",
    tickvals=[240, 270, 300, 330, 360, 390],
    ticktext=["4:00", "4:30", "5:00", "5:30", "6:00", "6:30"],
)
box_fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
st.plotly_chart(box_fig, use_container_width=True)

# Tabela-resumo
summary = (
    df.groupby("faixa_temp", as_index=False)
    .agg(
        n=("pace_s_per_km", "count"),
        pace_mediano_s=("pace_s_per_km", "median"),
    )
    .sort_values("faixa_temp", key=lambda s: s.map({k: i for i, k in enumerate(order)}))
)
summary["pace_mediano"] = summary["pace_mediano_s"].apply(_fmt_pace)
st.dataframe(
    summary[["faixa_temp", "n", "pace_mediano"]].rename(
        columns={"faixa_temp": "faixa", "n": "corridas", "pace_mediano": "pace mediano"}
    ),
    hide_index=True,
    use_container_width=True,
)

st.divider()

# ---------------------------------------------------------------------------
# EF vs temperatura
# ---------------------------------------------------------------------------

st.subheader("Eficiência aeróbica × temperatura")
st.caption(
    "EF = NGP_mps / FC_média. Se o calor está cobrando, EF cai junto: o atleta "
    "precisa de mais batimentos para sustentar o mesmo pace ajustado por terreno. "
    "Sinal complementar ao pace — EF não depende do volume de treino do dia."
)

df_ef = df.dropna(subset=["aerobic_efficiency"])
if not df_ef.empty:
    fig_ef = px.scatter(
        df_ef,
        x="temp_c",
        y="aerobic_efficiency",
        color="tipo" if "tipo" in df_ef.columns else None,
        color_discrete_map={"prova": "#dc2626", "treino": "#10b981"},
        hover_data={"nome": True, "data": True, "distance_km": ":.1f"},
        labels={"temp_c": "Temperatura (°C)", "aerobic_efficiency": "EF (m/s ÷ bpm)"},
    )
    fig_ef.update_traces(marker=dict(size=9, opacity=0.7), selector=dict(mode="markers"))

    if len(df_ef) >= 5:
        slope_ef, intercept_ef = np.polyfit(df_ef["temp_c"], df_ef["aerobic_efficiency"], 1)
        x_trend = np.array([df_ef["temp_c"].min(), df_ef["temp_c"].max()])
        fig_ef.add_trace(
            go.Scatter(
                x=x_trend,
                y=slope_ef * x_trend + intercept_ef,
                mode="lines",
                line=dict(color="#1f2937", width=2, dash="dash"),
                name="Tendência (OLS)",
            )
        )
    fig_ef.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_ef, use_container_width=True)
else:
    st.info("Sem EF computada nas corridas filtradas.")
