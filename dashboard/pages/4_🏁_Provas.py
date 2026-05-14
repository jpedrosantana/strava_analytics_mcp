"""Página 4 — Provas. Histórico de provas, PRs por distância e projeções."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from db import query

st.set_page_config(
    page_title="Provas — Strava Analytics",
    page_icon="🏁",
    layout="wide",
)

st.title("🏁 Provas")
st.caption("Histórico de provas + PRs em distâncias-padrão + projeções")


def _fmt_time(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds) or seconds <= 0:
        return "—"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _fmt_pace(pace_s_per_km: float | None) -> str:
    if pace_s_per_km is None or pd.isna(pace_s_per_km) or pace_s_per_km <= 0:
        return "—"
    m, s = divmod(int(round(pace_s_per_km)), 60)
    return f"{m}:{s:02d}/km"


# ---------------------------------------------------------------------------
# KPIs no topo
# ---------------------------------------------------------------------------

half_pr = query(
    """
    select time_s, pace_s_per_km, projected_marathon_time_s, race_date, race_name
    from marts.fct_race_performance
    where distance_label = 'Half Marathon' and completed
    order by time_s asc
    limit 1
    """
)

total_races = query("select count(*) as n from marts.fct_race_performance").iloc[0]["n"]
n_halves = query(
    """
    select count(*) as n
    from marts.fct_race_performance
    where distance_label = 'Half Marathon' and completed
    """
).iloc[0]["n"]

c1, c2, c3, c4 = st.columns(4)
if not half_pr.empty:
    row = half_pr.iloc[0]
    c1.metric(
        "PR de meia",
        _fmt_time(row["time_s"]),
        delta=f"{_fmt_pace(row['pace_s_per_km'])} · {row['race_date']:%d/%m/%Y}",
        delta_color="off",
    )
    c2.metric(
        "Projeção 42K (Riegel)",
        _fmt_time(row["projected_marathon_time_s"]),
        delta=f"do PR de meia ({row['race_name'][:30]})",
        delta_color="off",
    )
else:
    c1.metric("PR de meia", "—")
    c2.metric("Projeção 42K", "—")

c3.metric("Provas totais", int(total_races))
c4.metric("Meias completadas", int(n_halves))

st.divider()

# ---------------------------------------------------------------------------
# Ranking das meias
# ---------------------------------------------------------------------------

st.subheader("Ranking das meias completadas")
st.caption(
    "Pace usa `distance_official_km`, corrigindo GPS inflado/truncado. "
    "**Riegel** projeta o tempo desta meia para 42 km com expoente 1.06 — "
    "indica que ritmo dessa prova sustentaria por toda a maratona."
)

halves = query(
    """
    select
        rank_in_distance as "#",
        race_date as data,
        race_name as prova,
        time_s,
        pace_s_per_km,
        ctl_on_race_day as ctl,
        tsb_on_race_day as tsb,
        weather_temp_c as temp_c,
        projected_marathon_time_s as projecao_42k_s
    from marts.fct_race_performance
    where distance_label = 'Half Marathon' and completed
    order by rank_in_distance
    """
)

if not halves.empty:
    halves_display = halves.assign(
        tempo=halves["time_s"].apply(_fmt_time),
        pace=halves["pace_s_per_km"].apply(_fmt_pace),
        projecao_42k=halves["projecao_42k_s"].apply(_fmt_time),
        ctl=halves["ctl"].round(0),
        tsb=halves["tsb"].round(0).map(lambda v: f"{v:+.0f}" if pd.notna(v) else "—"),
        temp_c=halves["temp_c"].map(lambda v: f"{v:.0f}°C" if pd.notna(v) else "—"),
    )[["#", "data", "prova", "tempo", "pace", "ctl", "tsb", "temp_c", "projecao_42k"]]
    st.dataframe(halves_display, hide_index=True, use_container_width=True)
else:
    st.info("Sem meias completadas registradas.")

st.divider()

# ---------------------------------------------------------------------------
# Evolução do pace nas meias
# ---------------------------------------------------------------------------

st.subheader("Evolução do pace nas meias")
st.caption(
    "Cada ponto é uma meia, ordenada cronologicamente. A tendência abaixo "
    "responde se o atleta está melhorando provas oficiais na distância — "
    "complementar ao PR isolado, que pode ser um pico não-sustentado."
)

if not halves.empty:
    halves_by_date = halves.sort_values("data").copy()
    halves_by_date["pace_str"] = halves_by_date["pace_s_per_km"].apply(_fmt_pace)
    halves_by_date["tempo_str"] = halves_by_date["time_s"].apply(_fmt_time)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=halves_by_date["data"],
            y=halves_by_date["pace_s_per_km"],
            mode="markers+lines",
            marker=dict(size=12, color="#2563eb"),
            line=dict(color="#2563eb", width=1, dash="dot"),
            customdata=halves_by_date[["prova", "pace_str", "tempo_str"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Pace: %{customdata[1]}<br>"
                "Tempo: %{customdata[2]}<br>"
                "Data: %{x|%d/%m/%Y}<extra></extra>"
            ),
            name="Pace",
        )
    )
    fig.update_yaxes(
        title_text="Pace (s/km)",
        autorange="reversed",  # pace menor = melhor, desenhar pra cima
        tickvals=[260, 280, 300, 320, 340],
        ticktext=["4:20", "4:40", "5:00", "5:20", "5:40"],
    )
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# PRs por distância (best efforts via streams)
# ---------------------------------------------------------------------------

st.subheader("PRs por distância (best efforts)")
st.caption(
    "Calculados via janela deslizante sobre `distance` + `time` streams (PR #22) — "
    "um PR pode vir de um **segmento** dentro de uma corrida maior (flag SEG). "
    "Strava reporta best efforts da mesma forma."
)

prs = query(
    """
    select
        distance_label,
        time_s,
        pace_s_per_km,
        is_segment,
        cast(start_date_local as date) as data,
        activity_name,
        parent_distance_m / 1000.0 as corrida_total_km
    from marts.fct_pr_efforts
    where is_pr
    order by distance_m
    """
)

if not prs.empty:
    prs_display = prs.assign(
        tempo=prs["time_s"].apply(_fmt_time),
        pace=prs["pace_s_per_km"].apply(_fmt_pace),
        tipo=prs["is_segment"].map({True: "segmento", False: "corrida-cheia"}),
        corrida_total_km=prs["corrida_total_km"].round(1),
    )[["distance_label", "tempo", "pace", "data", "activity_name", "tipo", "corrida_total_km"]]
    prs_display.columns = ["distância", "tempo", "pace", "data", "atividade", "tipo", "total_km"]
    st.dataframe(prs_display, hide_index=True, use_container_width=True)
else:
    st.info("Sem best efforts computados. Rode `compute-metrics`.")

st.divider()

# ---------------------------------------------------------------------------
# Distribuição de pace por prova (todas, não só meias)
# ---------------------------------------------------------------------------

st.subheader("Pace por prova vs distância")
st.caption(
    "Visualização rápida pra detectar fora-da-curva: provas mais curtas devem "
    "ter pace menor (mais rápido). Cores indicam o objetivo declarado no seed."
)

all_races = query(
    """
    select
        distance_official_km as dist_km,
        time_s,
        pace_s_per_km,
        race_name,
        objective,
        race_date as data,
        completed
    from marts.fct_race_performance
    where completed and distance_official_km is not null
    order by dist_km
    """
)

if not all_races.empty:
    all_races["tempo_str"] = all_races["time_s"].apply(_fmt_time)
    all_races["pace_str"] = all_races["pace_s_per_km"].apply(_fmt_pace)

    fig3 = px.scatter(
        all_races,
        x="dist_km",
        y="pace_s_per_km",
        color="objective",
        hover_data={
            "race_name": True,
            "data": True,
            "tempo_str": True,
            "pace_str": True,
            "pace_s_per_km": False,
            "dist_km": False,
            "objective": False,
        },
        labels={
            "dist_km": "Distância oficial (km)",
            "pace_s_per_km": "Pace (s/km)",
            "objective": "Objetivo",
        },
    )
    fig3.update_traces(marker=dict(size=14))
    fig3.update_yaxes(
        autorange="reversed",
        tickvals=[240, 270, 300, 330, 360],
        ticktext=["4:00", "4:30", "5:00", "5:30", "6:00"],
    )
    fig3.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig3, use_container_width=True)
