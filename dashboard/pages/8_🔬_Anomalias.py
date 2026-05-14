"""Página 8 — Anomalias. Treinos atípicos, sinais de plateau e risco de lesão."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st
from db import query
from theme import tsb_label

from strava_mcp.analytics.anomalies import detect_outliers, fit_pace_model
from strava_mcp.analytics.injury_risk import assess_injury_risk

st.set_page_config(
    page_title="Anomalias — Strava Analytics",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 Anomalias")
st.caption("Treinos atípicos · sinais de plateau · risco de lesão")


def _fmt_pace_from_speed(speed_mps: float | None) -> str:
    if speed_mps is None or pd.isna(speed_mps) or speed_mps <= 0:
        return "—"
    pace = 1000 / speed_mps
    m, s = divmod(int(round(pace)), 60)
    return f"{m}:{s:02d}/km"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Filtros")
    days_back = st.slider("Janela de análise (dias)", 30, 180, 90, step=30)
    z_threshold = st.slider("Z-score mínimo (anomalia)", 1.5, 3.0, 2.0, step=0.25)
    train_window = st.slider("Janela de treino do modelo (dias)", 180, 720, 365, step=30)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

cutoff_test = date.today() - timedelta(days=days_back)
cutoff_train = date.today() - timedelta(days=train_window + days_back)

runs = query(
    f"""
    select
        f.activity_id as id,
        d.activity_name as name,
        f.start_date_local,
        cast(f.start_date_local as date) as date_key,
        f.distance_m,
        f.average_heartrate,
        f.elevation_gain_m,
        f.average_speed_mps,
        f.weather_temp_c as raw_json_temp,
        d.sport_type
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where d.sport_type = 'Run'
      and f.distance_m > 0
      and f.average_heartrate is not null
      and cast(f.start_date_local as date) >= '{cutoff_train}'
    order by f.start_date_local
    """
)

if runs.empty:
    st.warning("Sem corridas no período de treino para fitar o modelo.")
    st.stop()

# DuckDB devolve datetime64[us]; comparar com date precisa de coerce.
runs["date_key"] = pd.to_datetime(runs["date_key"]).dt.date
train_runs_df = runs[runs["date_key"] < cutoff_test]
test_runs_df = runs[runs["date_key"] >= cutoff_test]

# TSB por dia (pra anotar causas plausíveis de outliers)
tsb_rows = query(
    f"""
    select cast(date_key as varchar) as date_key, tsb
    from marts.fct_daily_load
    where date_key >= '{cutoff_test}'
    """
)
tsb_by_date = dict(zip(tsb_rows["date_key"], tsb_rows["tsb"], strict=True))


# ---------------------------------------------------------------------------
# Anomalias
# ---------------------------------------------------------------------------

st.subheader("Treinos atípicos (z-score)")
st.caption(
    "Modelo: regressão linear simples prevendo `velocidade média` a partir de "
    "`log(distância)`, `FC média` e `grade %`. Treinado nos últimos "
    f"**{train_window}** dias (anteriores aos últimos {days_back}). Atividades "
    f"com |z| ≥ **{z_threshold}** entram aqui — pace bem acima/abaixo do esperado "
    "para a combinação distância × FC × terreno."
)

# Convert to list[dict] format expected by fit_pace_model/detect_outliers.
train_activities = train_runs_df.to_dict("records")
test_activities = test_runs_df.to_dict("records")

model = fit_pace_model(train_activities)
if model is None:
    st.warning(
        f"Menos de 20 corridas com FC nos últimos {train_window} dias — "
        "ajuste a janela de treino no sidebar."
    )
else:
    outliers = detect_outliers(
        activities=test_activities,
        model=model,
        z_threshold=z_threshold,
        tsb_by_date=tsb_by_date,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Corridas no teste", len(test_activities))
    c2.metric("Anomalias detectadas", len(outliers))
    c3.metric(
        "Modelo (resíduo σ)",
        f"{model['residual_std']:.3f} m/s",
        delta=f"{model['n_samples']} amostras",
        delta_color="off",
    )

    if not outliers:
        st.success(f"Sem anomalias significativas nos últimos {days_back} dias.")
    else:
        anomalies_df = pd.DataFrame(outliers)
        anomalies_df["pace_real"] = anomalies_df["actual_speed_mps"].apply(_fmt_pace_from_speed)
        anomalies_df["pace_esperado"] = anomalies_df["predicted_speed_mps"].apply(
            _fmt_pace_from_speed
        )
        anomalies_df["sinal"] = anomalies_df["direction"].map(
            {"faster_than_expected": "🚀 acima", "slower_than_expected": "🐌 abaixo"}
        )
        anomalies_df["causas"] = anomalies_df["possible_causes"].map(
            lambda lst: ", ".join(lst) if lst else "—"
        )
        st.dataframe(
            anomalies_df[
                [
                    "date",
                    "name",
                    "distance_km",
                    "pace_real",
                    "pace_esperado",
                    "z_score",
                    "sinal",
                    "causas",
                ]
            ].rename(
                columns={
                    "date": "data",
                    "name": "atividade",
                    "distance_km": "km",
                    "z_score": "z",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Plateau
# ---------------------------------------------------------------------------

st.subheader("Sinais de plateau")
st.caption(
    "4 indicadores (de [`STRAVA_MCP_SPEC.md §3.4`]) ajudam a distinguir descanso "
    "produtivo de estagnação real. Quando 2+ apontam negativo, o atleta tende a "
    "estar em plateau e ajustes de estímulo são indicados."
)

# 1) EF trend nos últimos 6 meses (média mensal)
ef_monthly = query(
    """
    select
        date_trunc('month', f.start_date_local) as mes,
        avg(f.aerobic_efficiency) as ef_medio
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where d.sport_type = 'Run'
      and f.aerobic_efficiency is not null
      and f.start_date_local >= current_date - interval 180 day
    group by 1
    order by 1
    """
)

# 2) Days since last PR
pr_age = query(
    """
    select cast(start_date_local as date) as data
    from marts.fct_pr_efforts
    where is_pr
    order by data desc
    limit 1
    """
)
if pr_age.empty:
    days_since_pr = None
else:
    last_pr_date = pd.to_datetime(pr_age.iloc[0]["data"]).date()
    days_since_pr = (date.today() - last_pr_date).days

# 3) Intensity variety: % de tempo em Z4-Z5 nas últimas 4 semanas
intensity = query(
    """
    select
        sum(coalesce(z1_seconds, 0)) as z1,
        sum(coalesce(z2_seconds, 0)) as z2,
        sum(coalesce(z3_seconds, 0)) as z3,
        sum(coalesce(z4_seconds, 0)) as z4,
        sum(coalesce(z5_seconds, 0)) as z5
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where d.sport_type = 'Run'
      and f.start_date_local >= current_date - interval 28 day
    """
).iloc[0]
total_zone_s = sum(
    [intensity["z1"], intensity["z2"], intensity["z3"], intensity["z4"], intensity["z5"]]
)
high_intensity_pct = (
    100 * (intensity["z4"] + intensity["z5"]) / total_zone_s if total_zone_s > 0 else 0.0
)

# Render
col1, col2, col3, col4 = st.columns(4)

if not ef_monthly.empty and len(ef_monthly) >= 3:
    last_three_ef = ef_monthly.tail(3)["ef_medio"].tolist()
    ef_trend_dir = (
        "↗ subindo"
        if last_three_ef[-1] > last_three_ef[0]
        else "↘ caindo"
        if last_three_ef[-1] < last_three_ef[0]
        else "→ estável"
    )
    col1.metric(
        "EF (3 meses)",
        f"{last_three_ef[-1]:.4f}",
        delta=ef_trend_dir,
        delta_color="off",
    )
else:
    col1.metric("EF (3 meses)", "—")

col2.metric(
    "Dias desde último PR",
    f"{days_since_pr}d" if days_since_pr is not None else "—",
    delta=(
        "stale (>120d)"
        if days_since_pr and days_since_pr > 120
        else "ok"
        if days_since_pr is not None
        else None
    ),
    delta_color="off",
)

col3.metric(
    "Z4-Z5 (28d)",
    f"{high_intensity_pct:.1f}%",
    delta=(
        "baixo (<5%)"
        if high_intensity_pct < 5
        else "ok"
        if high_intensity_pct < 12
        else "alto (>12%)"
    ),
    delta_color="off",
)

# CTL atual (proxy de fitness)
ctl_now = query("select ctl from marts.fct_daily_load order by date_key desc limit 1").iloc[0][
    "ctl"
]
col4.metric("CTL atual", f"{ctl_now:.0f}")

# EF chart
if not ef_monthly.empty:
    ef_monthly["mes"] = pd.to_datetime(ef_monthly["mes"])
    st.line_chart(
        ef_monthly.set_index("mes")["ef_medio"],
        height=240,
    )

st.divider()

# ---------------------------------------------------------------------------
# Risco de lesão
# ---------------------------------------------------------------------------

st.subheader("Risco de lesão atual")
st.caption(
    "Combina 3 sinais: **ACWR** (aguda/crônica), **spike de volume** (7d vs média de 28d) "
    "e **degradação de EF** (recente vs baseline). Score 0-100, com bandas: "
    "<20 baixo · 20-49 moderado · ≥50 alto. Sinais individuais aparecem como factors."
)

# ACWR
today_row = query(
    """
    select ctl, atl, case when ctl > 0 then atl/ctl end as acwr
    from marts.fct_daily_load order by date_key desc limit 1
    """
).iloc[0]
acwr = today_row["acwr"]

# Volume spike: km nos últimos 7d / média semanal nos 28d anteriores
volume = query(
    """
    select
        sum(case when date_key >= current_date - interval 7 day
            then total_distance_m end) / 1000 as last7_km,
        sum(case
            when date_key < current_date - interval 7 day
            and date_key >= current_date - interval 35 day
            then total_distance_m end) / 1000 / 4 as avg_4w_km
    from marts.fct_daily_load
    """
).iloc[0]
volume_spike = (
    volume["last7_km"] / volume["avg_4w_km"]
    if volume["avg_4w_km"] and volume["avg_4w_km"] > 0
    else None
)

# EF recent vs baseline
ef_windows = query(
    """
    select
        avg(case
            when f.start_date_local >= current_date - interval 14 day
            then f.aerobic_efficiency end) as recent_ef,
        avg(case
            when f.start_date_local >= current_date - interval 60 day
            and f.start_date_local < current_date - interval 30 day
            then f.aerobic_efficiency end) as baseline_ef
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where d.sport_type = 'Run' and f.aerobic_efficiency is not null
    """
).iloc[0]

risk = assess_injury_risk(
    acwr=float(acwr) if pd.notna(acwr) else None,
    volume_spike=float(volume_spike) if volume_spike is not None else None,
    recent_ef=float(ef_windows["recent_ef"]) if pd.notna(ef_windows["recent_ef"]) else None,
    baseline_ef=float(ef_windows["baseline_ef"]) if pd.notna(ef_windows["baseline_ef"]) else None,
)

# Colorização: baixo verde · moderado laranja · alto vermelho
level_color = {"low": "#10b981", "moderate": "#f59e0b", "high": "#ef4444"}[risk["risk_level"]]

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Score (0-100)",
    risk["risk_score"],
    delta=risk["risk_level"].upper(),
    delta_color="off",
)
c2.metric("ACWR", f"{acwr:.2f}" if pd.notna(acwr) else "—")
c3.metric(
    "Spike 7d/4w",
    f"{volume_spike:.2f}×" if volume_spike else "—",
)
c4.metric(
    "Δ EF (14d vs 30-60d)",
    f"{ef_windows['recent_ef']:.4f}" if pd.notna(ef_windows["recent_ef"]) else "—",
    delta=(
        f"baseline {ef_windows['baseline_ef']:.4f}" if pd.notna(ef_windows["baseline_ef"]) else None
    ),
    delta_color="off",
)

# Bar visual do score
_bar_outer = "background:#e5e7eb; border-radius:4px; height:14px; width:100%; margin:6px 0 12px 0;"
_bar_inner = (
    f"background:{level_color}; width:{risk['risk_score']}%; height:100%; border-radius:4px;"
)
st.markdown(
    f'<div style="{_bar_outer}"><div style="{_bar_inner}"></div></div>',
    unsafe_allow_html=True,
)

if risk["factors"]:
    st.markdown("**Fatores contribuindo:**")
    for f in risk["factors"]:
        st.markdown(
            f"- **{f.get('factor', '?')}** ({f.get('points', '?')} pts): {f.get('reason', '—')}"
        )
else:
    st.caption("Nenhum fator de risco ativo no momento.")

# TSB atual (sanity check)
tsb_now = today_row.get("atl")  # placeholder to avoid recompute
last_form = query(
    "select date_key, tsb from marts.fct_daily_load order by date_key desc limit 1"
).iloc[0]
st.caption(
    f"TSB atual: **{last_form['tsb']:+.1f}** ({tsb_label(last_form['tsb'])} — "
    f"data: {last_form['date_key']}). TSB muito negativo amplifica todos os sinais acima."
)
