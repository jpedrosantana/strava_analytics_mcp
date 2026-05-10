"""Página 3 — Eficiência. EF, decoupling e distribuição de zonas."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from db import query

st.set_page_config(
    page_title="Eficiência — Strava Analytics",
    page_icon="❤️",
    layout="wide",
)

st.title("❤️ Eficiência")
st.caption(
    "Eficiência aeróbica (EF), decoupling em longões e distribuição em zonas. "
    "Os números respondem: minha aptidão aeróbica melhora? Os longões cansam mais "
    "que deveriam? Estou treinando polarizado?"
)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filtros")
    period_options = {"90 dias": 90, "180 dias": 180, "365 dias": 365, "Tudo": None}
    period_label = st.selectbox("Período", list(period_options.keys()), index=1)
    period_days = period_options[period_label]

# ─── Cards: últimas 4 semanas vs 4 anteriores ────────────────────────────────
# Janela atual = [today-28, today]; anterior = [today-56, today-28)
cards = query(
    """
    with windows as (
        select
            current_date - interval 28 day  as cur_start,
            current_date - interval 56 day  as prev_start,
            current_date                    as cur_end
    ),
    ef_cur as (
        select avg(f.aerobic_efficiency) as ef
        from marts.fct_activity f
        join marts.dim_activity d using (activity_id), windows w
        where d.sport_type = 'Run'
          and f.aerobic_efficiency is not null
          and f.date_key >= w.cur_start
    ),
    ef_prev as (
        select avg(f.aerobic_efficiency) as ef
        from marts.fct_activity f
        join marts.dim_activity d using (activity_id), windows w
        where d.sport_type = 'Run'
          and f.aerobic_efficiency is not null
          and f.date_key >= w.prev_start and f.date_key < w.cur_start
    ),
    dec_cur as (
        select avg(decoupling_pct) as decoup
        from marts.fct_long_runs, windows w
        where decoupling_pct is not null
          and date_key >= w.cur_start
    ),
    dec_prev as (
        select avg(decoupling_pct) as decoup
        from marts.fct_long_runs, windows w
        where decoupling_pct is not null
          and date_key >= w.prev_start and date_key < w.cur_start
    ),
    -- Para % Z1+Z2 e n_quality, agrego direto das atividades para honrar a janela
    -- exata de 28 dias (fct_zone_distribution é semanal, fica granuloso).
    pol_cur as (
        select
            sum(coalesce(f.z1_seconds, 0) + coalesce(f.z2_seconds, 0)) as low,
            sum(coalesce(f.z1_seconds, 0) + coalesce(f.z2_seconds, 0)
                + coalesce(f.z3_seconds, 0) + coalesce(f.z4_seconds, 0)
                + coalesce(f.z5_seconds, 0)) as total,
            count(*) filter (
                where coalesce(f.z4_seconds, 0) + coalesce(f.z5_seconds, 0) >= 600
            ) as n_quality
        from marts.fct_activity f
        join marts.dim_activity d using (activity_id), windows w
        where d.sport_type = 'Run'
          and f.date_key >= w.cur_start
    ),
    pol_prev as (
        select
            sum(coalesce(f.z1_seconds, 0) + coalesce(f.z2_seconds, 0)) as low,
            sum(coalesce(f.z1_seconds, 0) + coalesce(f.z2_seconds, 0)
                + coalesce(f.z3_seconds, 0) + coalesce(f.z4_seconds, 0)
                + coalesce(f.z5_seconds, 0)) as total,
            count(*) filter (
                where coalesce(f.z4_seconds, 0) + coalesce(f.z5_seconds, 0) >= 600
            ) as n_quality
        from marts.fct_activity f
        join marts.dim_activity d using (activity_id), windows w
        where d.sport_type = 'Run'
          and f.date_key >= w.prev_start and f.date_key < w.cur_start
    )
    select
        ef_cur.ef            as ef_cur,
        ef_prev.ef           as ef_prev,
        dec_cur.decoup       as dec_cur,
        dec_prev.decoup      as dec_prev,
        case when pol_cur.total  > 0 then 100.0 * pol_cur.low  / pol_cur.total  end as pct_low_cur,
        case when pol_prev.total > 0 then 100.0 * pol_prev.low / pol_prev.total end as pct_low_prev,
        pol_cur.n_quality    as nq_cur,
        pol_prev.n_quality   as nq_prev
    from ef_cur, ef_prev, dec_cur, dec_prev, pol_cur, pol_prev
    """
).iloc[0]


def fmt_delta(cur, prev, fmt="{:+.2f}", invert=False):
    """Formata delta para st.metric. invert=True quando aumentar é ruim (decoupling)."""
    if cur is None or prev is None or pd.isna(cur) or pd.isna(prev):
        return None
    diff = cur - prev
    if invert:
        diff = -diff  # streamlit pinta positivo de verde; invertemos pra decoupling
    return fmt.format(diff)


st.subheader("Últimas 4 semanas")
c1, c2, c3, c4 = st.columns(4)

ef_cur = cards["ef_cur"]
c1.metric(
    "EF médio (corridas)",
    f"{ef_cur:.2f}" if pd.notna(ef_cur) else "—",
    delta=fmt_delta(cards["ef_cur"], cards["ef_prev"]),
    help="Aerobic Efficiency = NGP / FC. Mais alto = mais eficiente. "
    "Comparado às 4 semanas anteriores.",
)

dec_cur = cards["dec_cur"]
c2.metric(
    "Decoupling médio longões",
    f"{dec_cur:.1f}%" if pd.notna(dec_cur) else "—",
    delta=fmt_delta(cards["dec_cur"], cards["dec_prev"], fmt="{:+.1f}%", invert=True),
    help="Aerobic decoupling Pa:HR nos longões (≥60min). "
    "≤5% saudável, >10% sugere fadiga aeróbica. Delta invertido (queda = melhora).",
)

pct_cur = cards["pct_low_cur"]
c3.metric(
    "% Z1+Z2 corrida",
    f"{pct_cur:.0f}%" if pd.notna(pct_cur) else "—",
    delta=fmt_delta(cards["pct_low_cur"], cards["pct_low_prev"], fmt="{:+.0f}pp"),
    help="Tempo em zona baixa como fração do tempo classificado. "
    "Polarização recomendada: ~80% em Z1+Z2.",
)

nq_cur = cards["nq_cur"]
nq_prev = cards["nq_prev"]
nq_delta = (
    f"{int(nq_cur - nq_prev):+d}" if pd.notna(nq_cur) and pd.notna(nq_prev) else None
)
c4.metric(
    "Sessões de quality",
    f"{int(nq_cur) if pd.notna(nq_cur) else 0}",
    delta=nq_delta,
    help="Corridas com ≥10min somados em Z4+Z5.",
)

st.divider()

# ─── Gráfico 1 — EF trend ─────────────────────────────────────────────────────
st.subheader("Eficiência aeróbica no tempo")
st.caption(
    "Cada ponto é uma corrida com EF computado (precisa de stream de pace + FC). "
    "**EF = NGP / FC média.** A linha cinza é a média móvel de 28 dias — tendência "
    "ascendente significa que o motor aeróbico está melhorando."
)

where_period = (
    f"f.date_key >= current_date - interval {period_days} day" if period_days else "1=1"
)

ef_df = query(
    f"""
    select f.date_key, f.aerobic_efficiency, f.distance_km, d.sport_type
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where d.sport_type = 'Run'
      and f.aerobic_efficiency is not null
      and {where_period}
    order by f.date_key
    """
)

if not ef_df.empty:
    ef_df["date_key"] = pd.to_datetime(ef_df["date_key"])
    ef_df["ef_ma28"] = (
        ef_df.set_index("date_key")["aerobic_efficiency"]
        .rolling("28D", min_periods=3)
        .mean()
        .values
    )

    fig_ef = go.Figure()
    fig_ef.add_trace(
        go.Scatter(
            x=ef_df["date_key"],
            y=ef_df["aerobic_efficiency"],
            mode="markers",
            name="EF por corrida",
            marker=dict(color="#2563eb", size=7, opacity=0.55),
            hovertemplate=(
                "%{x|%d %b %Y}<br>EF: %{y:.2f}<br>km: %{customdata:.1f}<extra></extra>"
            ),
            customdata=ef_df["distance_km"],
        )
    )
    fig_ef.add_trace(
        go.Scatter(
            x=ef_df["date_key"],
            y=ef_df["ef_ma28"],
            mode="lines",
            name="Média móvel 28d",
            line=dict(color="#6b7280", width=2.5),
        )
    )
    fig_ef.update_layout(
        height=380,
        yaxis_title="EF (NGP_mps / FC)",
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        hovermode="closest",
    )
    st.plotly_chart(fig_ef, use_container_width=True)
else:
    st.info("Sem corridas com EF computado no período.")

st.divider()

# ─── Gráfico 2 — Decoupling dos longões ───────────────────────────────────────
st.subheader("Decoupling dos longões")
st.caption(
    "**Decoupling Pa:HR** mede quanto o pace cai (relativo à FC) na 2ª metade de um "
    "longão. Valores ≤5% indicam boa resistência aeróbica (banda verde); >10% "
    "(banda vermelha) sugere fadiga acumulada ou base aeróbica insuficiente. "
    "Tamanho do ponto = distância. Hover mostra contexto."
)

dec_df = query(
    f"""
    select
        date_key,
        decoupling_pct,
        distance_km,
        moving_time_h,
        pace_s_per_km,
        aerobic_efficiency,
        ctl_on_date,
        tsb_on_date
    from marts.fct_long_runs
    where decoupling_pct is not null
      and {where_period.replace('f.date_key', 'date_key')}
    order by date_key
    """
)

if not dec_df.empty:
    dec_df["date_key"] = pd.to_datetime(dec_df["date_key"])
    dec_df["pace_str"] = dec_df["pace_s_per_km"].apply(
        lambda s: f"{int(s // 60)}:{int(s % 60):02d}/km" if pd.notna(s) else "—"
    )
    dec_df["dec_ma"] = (
        dec_df.set_index("date_key")["decoupling_pct"]
        .rolling("56D", min_periods=2)
        .mean()
        .values
    )

    fig_dec = go.Figure()

    # Bandas semânticas
    fig_dec.add_hrect(
        y0=-30, y1=5,
        fillcolor="rgba(16,185,129,0.10)", line_width=0,
        annotation_text="saudável (≤5%)", annotation_position="bottom right",
    )
    fig_dec.add_hrect(
        y0=10, y1=40,
        fillcolor="rgba(239,68,68,0.10)", line_width=0,
        annotation_text="alerta (>10%)", annotation_position="top right",
    )

    fig_dec.add_trace(
        go.Scatter(
            x=dec_df["date_key"],
            y=dec_df["decoupling_pct"],
            mode="markers",
            name="Longão",
            marker=dict(
                size=dec_df["distance_km"],
                sizemode="area",
                sizeref=2.0 * dec_df["distance_km"].max() / (35.0**2),
                sizemin=4,
                color="#1f2937",
                opacity=0.65,
            ),
            customdata=dec_df[
                ["distance_km", "pace_str", "aerobic_efficiency", "ctl_on_date", "tsb_on_date"]
            ].values,
            hovertemplate=(
                "%{x|%d %b %Y}<br>"
                "decoupling: %{y:.1f}%<br>"
                "%{customdata[0]:.1f} km · %{customdata[1]}<br>"
                "EF: %{customdata[2]:.2f}<br>"
                "CTL: %{customdata[3]:.0f} · TSB: %{customdata[4]:+.0f}"
                "<extra></extra>"
            ),
        )
    )
    fig_dec.add_trace(
        go.Scatter(
            x=dec_df["date_key"],
            y=dec_df["dec_ma"],
            mode="lines",
            name="Média móvel 8 semanas",
            line=dict(color="#6b7280", width=2, dash="dot"),
        )
    )
    fig_dec.update_layout(
        height=380,
        yaxis_title="Decoupling (%)",
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        hovermode="closest",
    )
    st.plotly_chart(fig_dec, use_container_width=True)
else:
    st.info("Sem longões com decoupling computado no período.")

st.divider()

# ─── Gráfico 3 — Distribuição de zonas por semana ────────────────────────────
st.subheader("Distribuição em zonas por semana")
st.caption(
    "Tempo em cada zona como % do tempo classificado (com FC). Padrão polarizado "
    "saudável: **~80% em Z1+Z2** e o restante quase todo em Z4+Z5, com pouco "
    "tempo em Z3 ('zona cinza')."
)

scope = st.radio(
    "Escopo",
    options=["Só corrida", "Todas as atividades"],
    horizontal=True,
    index=0,
)
run_prefix = "run_" if scope == "Só corrida" else ""

# Para o filtro de período no semanal, uso o week_start_date do dim_date via subquery
where_week = (
    f"week_start_date >= current_date - interval {period_days} day"
    if period_days
    else "1=1"
)

zones_df = query(
    f"""
    select
        w.iso_year_week,
        w.week_start_date,
        w.week_end_date,
        z.{run_prefix}z1_seconds as z1,
        z.{run_prefix}z2_seconds as z2,
        z.{run_prefix}z3_seconds as z3,
        z.{run_prefix}z4_seconds as z4,
        z.{run_prefix}z5_seconds as z5,
        z.{run_prefix}total_with_hr_seconds as total_hr
    from marts.fct_zone_distribution z
    join marts.fct_weekly_summary w using (iso_year_week)
    where {where_week}
    order by w.week_start_date
    """
)

if not zones_df.empty and zones_df["total_hr"].sum() > 0:
    zones_df["week_start_date"] = pd.to_datetime(zones_df["week_start_date"])
    zones_df["week_end_date"] = pd.to_datetime(zones_df["week_end_date"])
    # Rótulo do eixo X cobrindo o intervalo da semana ISO (ex: "04–10 mai")
    zones_df["week_label"] = zones_df.apply(
        lambda r: f"{r['week_start_date'].strftime('%d')}–"
        f"{r['week_end_date'].strftime('%d %b').lower()}",
        axis=1,
    )

    # Normaliza para %
    long_df = zones_df.melt(
        id_vars=["iso_year_week", "week_label", "week_start_date", "total_hr"],
        value_vars=["z1", "z2", "z3", "z4", "z5"],
        var_name="zone",
        value_name="seconds",
    )
    long_df["pct"] = (long_df["seconds"] / long_df["total_hr"] * 100).where(
        long_df["total_hr"] > 0
    )
    long_df["minutes"] = (long_df["seconds"] / 60).round(0)
    long_df = long_df.dropna(subset=["pct"])

    zone_colors = {
        "z1": "#bbf7d0",  # verde claro — recuperação
        "z2": "#86efac",  # verde — endurance
        "z3": "#fde68a",  # amarelo — tempo
        "z4": "#fb923c",  # laranja — threshold
        "z5": "#ef4444",  # vermelho — VO2max
    }
    zone_labels = {
        "z1": "Z1 (recuperação)",
        "z2": "Z2 (endurance)",
        "z3": "Z3 (tempo)",
        "z4": "Z4 (threshold)",
        "z5": "Z5 (VO2max)",
    }
    long_df["zone_label"] = long_df["zone"].map(zone_labels)

    # Preserva ordem cronológica das semanas no eixo X
    week_order = (
        zones_df.sort_values("week_start_date")["week_label"].tolist()
    )

    fig_z = px.bar(
        long_df,
        x="week_label",
        y="pct",
        color="zone_label",
        category_orders={
            "week_label": week_order,
            "zone_label": [zone_labels[z] for z in ["z1", "z2", "z3", "z4", "z5"]],
        },
        color_discrete_map={zone_labels[z]: c for z, c in zone_colors.items()},
        labels={"week_label": "Semana (seg–dom)", "pct": "% do tempo em zona"},
        custom_data=["iso_year_week", "minutes"],
    )
    fig_z.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b> (%{x})<br>"
            "%{fullData.name}: %{y:.0f}%  ·  %{customdata[1]:.0f} min"
            "<extra></extra>"
        )
    )
    # Referência 80% (z1+z2 ideal): linha horizontal
    fig_z.add_hline(
        y=80,
        line_dash="dot",
        line_color="#16a34a",
        annotation_text="alvo Z1+Z2 ≈ 80%",
        annotation_position="top right",
    )
    fig_z.update_layout(
        barmode="stack",
        height=420,
        yaxis=dict(ticksuffix="%", range=[0, 100]),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center", title=None),
        hovermode="x unified",
    )
    st.plotly_chart(fig_z, use_container_width=True)
else:
    st.info("Sem dados de zona no período (atividades sem stream de FC).")
