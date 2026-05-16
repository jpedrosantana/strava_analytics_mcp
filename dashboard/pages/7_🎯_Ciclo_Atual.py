"""Página 7 — Ciclo Atual. Trajetória de CTL e progressão de longos rumo à prova alvo."""

from datetime import date, time, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from db import query

st.set_page_config(
    page_title="Ciclo Atual — Strava Analytics",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Ciclo Atual")
st.caption(
    "Onde estou na preparação? A página cruza CTL histórico contra uma trajetória "
    "ideal até a prova e plota os longos feitos vs a progressão recomendada "
    "(Pfitzinger/Hudson para amador). Inputs configuráveis no sidebar; nenhum "
    "número aqui é prescrição, é referência."
)

# ─── Sidebar: configuração do ciclo ───────────────────────────────────────────
with st.sidebar:
    st.header("Configuração do ciclo")
    target_date = st.date_input(
        "Data da prova alvo",
        value=date(2026, 7, 12),
        min_value=date.today(),
        help="Default: Maratona New Balance Porto Alegre (12/07/2026).",
    )
    target_time_obj = st.time_input(
        "Tempo objetivo",
        value=time(3, 28, 52),
        step=60,
        help="Default deriva da projeção Riegel atual baseada na meia PR.",
    )
    target_ctl = st.number_input(
        "CTL alvo no peak",
        min_value=40,
        max_value=120,
        value=80,
        step=5,
        help="Pico de CTL atingido 3 semanas antes da prova. Faixa típica: "
        "sub-3:30 ≈ 75-85, sub-3:00 ≈ 85-100.",
    )
    cycle_weeks = st.number_input(
        "Tamanho do ciclo (semanas)",
        min_value=8,
        max_value=24,
        value=16,
        step=1,
        help="Janela considerada como 'ciclo de preparação'. Padrão: 16 semanas.",
    )

today = date.today()
cycle_start = target_date - timedelta(weeks=int(cycle_weeks))
peak_date = target_date - timedelta(days=21)  # taper começa 3 semanas antes
days_to_race = (target_date - today).days
target_seconds = target_time_obj.hour * 3600 + target_time_obj.minute * 60 + target_time_obj.second

# Versões Timestamp para passar pro Plotly. add_vline calcula a média de [x, x]
# para posicionar a annotation, e isso falha com datetime.date puro.
today_ts = pd.Timestamp(today)
peak_ts = pd.Timestamp(peak_date)
target_ts = pd.Timestamp(target_date)

# ─── KPIs no topo ─────────────────────────────────────────────────────────────
ctl_today = query(
    f"""
    select ctl, atl, tsb
    from marts.fct_daily_load
    where date_key <= date '{today}'
    order by date_key desc
    limit 1
    """
)
if ctl_today.empty:
    st.error("Sem dado de CTL recente — rode `compute-metrics`.")
    st.stop()

ctl_now = float(ctl_today.iloc[0]["ctl"])
tsb_now = float(ctl_today.iloc[0]["tsb"])
week_in_cycle = max(1, int((today - cycle_start).days / 7) + 1) if today >= cycle_start else 0
ctl_gap = target_ctl - ctl_now

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Dias até a prova",
    f"{days_to_race}",
    delta=f"{days_to_race / 7:.1f} semanas",
    delta_color="off",
)
c2.metric(
    "Semana do ciclo",
    f"{week_in_cycle} / {int(cycle_weeks)}",
    delta=(
        "antes do início"
        if today < cycle_start
        else (
            "no taper" if today >= peak_date else f"até o peak: {(peak_date - today).days // 7} sem"
        )
    ),
    delta_color="off",
)
c3.metric(
    "CTL atual",
    f"{ctl_now:.1f}",
    delta=f"{ctl_gap:+.1f} até alvo ({target_ctl})",
    delta_color="off",
)
c4.metric(
    "TSB atual",
    f"{tsb_now:+.1f}",
    delta="fresco" if tsb_now > 5 else ("carregado" if tsb_now < -10 else "produtivo"),
    delta_color="off",
)

st.divider()

# ─── Bloco 1: Trajetória CTL vs ideal ─────────────────────────────────────────
st.subheader("Trajetória de CTL")
st.caption(
    "Linha azul = CTL histórico. Linha tracejada cinza = trajetória ideal: "
    "subida linear até o peak (3 semanas antes da prova) atingindo o alvo "
    "configurado, depois decay de ~15% durante o taper. Banda sombreada = "
    "±5 unidades de tolerância. Estar dentro da banda significa que o ritmo "
    "de carga está coerente com o objetivo."
)

# Histórico real do CTL dentro da janela do ciclo + um buffer pra contexto
ctl_hist = query(
    f"""
    select date_key, ctl, tsb
    from marts.fct_daily_load
    where date_key >= date '{cycle_start - timedelta(weeks=4)}'
      and date_key <= date '{today}'
    order by date_key
    """
)
ctl_hist["date_key"] = pd.to_datetime(ctl_hist["date_key"])

# CTL inicial: valor real no início do ciclo (ou 0 se não tem)
start_match = ctl_hist[ctl_hist["date_key"].dt.date == cycle_start]
if not start_match.empty:
    ctl_at_start = float(start_match.iloc[0]["ctl"])
else:
    # Pega o mais próximo dentro da janela
    closest = ctl_hist.iloc[(ctl_hist["date_key"].dt.date - cycle_start).abs().argsort()[:1]]
    ctl_at_start = float(closest.iloc[0]["ctl"]) if not closest.empty else 0.0

# Trajetória ideal: 3 segmentos lineares
# (cycle_start, ctl_at_start) → (peak_date, target_ctl) → (target_date, target_ctl * 0.85)
ideal_points = pd.DataFrame(
    [
        {"date": cycle_start, "ctl": ctl_at_start},
        {"date": peak_date, "ctl": float(target_ctl)},
        {"date": target_date, "ctl": float(target_ctl) * 0.85},
    ]
)
# Interpola dia a dia pra desenhar uma linha lisa
ideal_dates = pd.date_range(cycle_start, target_date, freq="D")
ideal_ctl = np.interp(
    [d.toordinal() for d in ideal_dates],
    [pd.Timestamp(d).toordinal() for d in ideal_points["date"]],
    ideal_points["ctl"].values,
)
ideal_df = pd.DataFrame({"date": ideal_dates, "ctl": ideal_ctl})

fig_ctl = go.Figure()

# Banda de tolerância
fig_ctl.add_trace(
    go.Scatter(
        x=list(ideal_df["date"]) + list(ideal_df["date"][::-1]),
        y=list(ideal_df["ctl"] + 5) + list(ideal_df["ctl"][::-1] - 5),
        fill="toself",
        fillcolor="rgba(148, 163, 184, 0.18)",
        line=dict(width=0),
        name="Banda ±5",
        hoverinfo="skip",
        showlegend=True,
    )
)
# Trajetória ideal
fig_ctl.add_trace(
    go.Scatter(
        x=ideal_df["date"],
        y=ideal_df["ctl"],
        mode="lines",
        line=dict(color="#94a3b8", width=2, dash="dash"),
        name="Trajetória ideal",
        hovertemplate="%{x|%d %b}<br>Ideal: %{y:.1f}<extra></extra>",
    )
)
# CTL histórico
fig_ctl.add_trace(
    go.Scatter(
        x=ctl_hist["date_key"],
        y=ctl_hist["ctl"],
        mode="lines",
        line=dict(color="#2563eb", width=2.5),
        name="CTL real",
        hovertemplate="%{x|%d %b %Y}<br>CTL: %{y:.1f}<extra></extra>",
    )
)
# Marcadores: hoje, peak, prova. annotation_* do add_vline quebra com
# datas (bug do Plotly em _mean), então adicionamos as labels separadamente.
for x_ts, color, label in [
    (today_ts, "#0f172a", "hoje"),
    (peak_ts, "#dc2626", "peak"),
    (target_ts, "#059669", "prova"),
]:
    fig_ctl.add_vline(x=x_ts, line_dash="dot", line_color=color)
    fig_ctl.add_annotation(
        x=x_ts,
        y=1.0,
        yref="paper",
        text=label,
        showarrow=False,
        yanchor="bottom",
        font=dict(color=color, size=11),
    )

fig_ctl.update_layout(
    height=400,
    yaxis_title="CTL",
    xaxis_title=None,
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(orientation="h", y=1.10, x=0.5, xanchor="center"),
    hovermode="x unified",
)
st.plotly_chart(fig_ctl, use_container_width=True)

# Diagnóstico curto
ideal_today = float(
    np.interp(today.toordinal(), [d.toordinal() for d in ideal_df["date"]], ideal_df["ctl"])
)
gap_today = ctl_now - ideal_today
if abs(gap_today) <= 5:
    st.success(
        f"**Dentro da banda:** CTL ideal pra hoje = {ideal_today:.1f}, real = {ctl_now:.1f} "
        f"(Δ {gap_today:+.1f}). Ritmo de carga consistente com o alvo de {target_ctl} no peak."
    )
elif gap_today < -5:
    st.warning(
        f"**Abaixo da banda:** CTL ideal pra hoje = {ideal_today:.1f}, real = {ctl_now:.1f} "
        f"(Δ {gap_today:+.1f}). Precisa de mais volume/intensidade nas próximas semanas "
        f"para alcançar CTL {target_ctl} no peak."
    )
else:
    st.info(
        f"**Acima da banda:** CTL ideal pra hoje = {ideal_today:.1f}, real = {ctl_now:.1f} "
        f"(Δ {gap_today:+.1f}). Está acima do necessário — observe TSB e sinais de fadiga."
    )

st.divider()

# ─── Bloco 2: Longos do ciclo vs progressão recomendada ──────────────────────
st.subheader("Longos do ciclo vs progressão recomendada")
st.caption(
    "Cada ponto azul é um longo (≥ 14 km ou ≥ 90 min) feito no ciclo. A linha "
    "tracejada é a progressão recomendada para maratona amadora: subida linear "
    "de ~14 km no início até ~32 km no peak (3 semanas antes), depois taper "
    "agressivo (26 / 21 / 16 km nas 3 semanas finais). Hover mostra pace e decoupling."
)

long_runs = query(
    f"""
    select date_key, distance_km, pace_s_per_km, decoupling_pct, moving_time_h
    from marts.fct_long_runs
    where date_key >= date '{cycle_start}'
      and date_key <= date '{today}'
      and (distance_km >= 14 or moving_time_h >= 1.5)
    order by date_key
    """
)
long_runs["date_key"] = pd.to_datetime(long_runs["date_key"])


def recommended_long_km(d: date) -> float | None:
    """Progressão Pfitzinger-style. Antes do ciclo ou depois da prova: None."""
    if d < cycle_start or d > target_date:
        return None
    days_to_peak = (peak_date - d).days
    if days_to_peak >= 0:
        # Subida linear desde cycle_start até peak: 14 → 32 km
        total = (peak_date - cycle_start).days
        progress = 1.0 - days_to_peak / total if total > 0 else 1.0
        return 14.0 + (32.0 - 14.0) * progress
    # Taper: peak +0w = 32, +1w = 26, +2w = 21, +3w = race day (skip)
    weeks_after_peak = -days_to_peak / 7
    if weeks_after_peak < 1:
        return 32.0
    if weeks_after_peak < 2:
        return 26.0
    if weeks_after_peak < 3:
        return 21.0
    return 16.0


# Gera a curva de progressão semana a semana
rec_dates = pd.date_range(cycle_start, target_date, freq="W-SAT")  # longão típico no sábado
rec_km = [recommended_long_km(d.date()) for d in rec_dates]
rec_df = pd.DataFrame({"date": rec_dates, "km": rec_km}).dropna()

fig_long = go.Figure()
fig_long.add_trace(
    go.Scatter(
        x=rec_df["date"],
        y=rec_df["km"],
        mode="lines+markers",
        line=dict(color="#94a3b8", width=2, dash="dash"),
        marker=dict(size=6, color="#94a3b8"),
        name="Recomendado",
        hovertemplate="%{x|%d %b}<br>Recomendado: %{y:.0f} km<extra></extra>",
    )
)

if not long_runs.empty:
    long_runs["pace_str"] = long_runs["pace_s_per_km"].apply(
        lambda s: f"{int(s // 60)}:{int(s % 60):02d}/km" if pd.notna(s) else "—"
    )
    long_runs["dec_str"] = long_runs["decoupling_pct"].apply(
        lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
    )
    fig_long.add_trace(
        go.Scatter(
            x=long_runs["date_key"],
            y=long_runs["distance_km"],
            mode="markers",
            marker=dict(size=11, color="#2563eb", opacity=0.85),
            name="Longos feitos",
            customdata=long_runs[["pace_str", "dec_str", "moving_time_h"]].values,
            hovertemplate=(
                "%{x|%d %b %Y}<br>"
                "%{y:.1f} km · %{customdata[2]:.1f}h<br>"
                "pace: %{customdata[0]}<br>"
                "decoupling: %{customdata[1]}"
                "<extra></extra>"
            ),
        )
    )

for x_ts, color, label in [
    (today_ts, "#0f172a", "hoje"),
    (peak_ts, "#dc2626", "peak"),
    (target_ts, "#059669", "prova"),
]:
    fig_long.add_vline(x=x_ts, line_dash="dot", line_color=color)
    fig_long.add_annotation(
        x=x_ts,
        y=1.0,
        yref="paper",
        text=label,
        showarrow=False,
        yanchor="bottom",
        font=dict(color=color, size=11),
    )

fig_long.update_layout(
    height=380,
    yaxis_title="Distância (km)",
    xaxis_title=None,
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(orientation="h", y=1.10, x=0.5, xanchor="center"),
    hovermode="closest",
)
st.plotly_chart(fig_long, use_container_width=True)

# Resumo curto
n_longs = len(long_runs)
longest = long_runs["distance_km"].max() if n_longs > 0 else 0.0
days_to_peak = (peak_date - today).days
st.caption(
    f"**Ciclo até aqui:** {n_longs} longos feitos · maior = {longest:.1f} km · "
    f"faltam {days_to_peak} dias até o peak (alvo recomendado nessa data: "
    f"{recommended_long_km(peak_date):.0f} km)."
)

# Nota sobre pace alvo
goal_pace_s = target_seconds / 42.195
goal_pace_str = f"{int(goal_pace_s // 60)}:{int(goal_pace_s % 60):02d}/km"
st.info(
    f"**Pace alvo para {target_time_obj.strftime('%H:%M:%S')}:** {goal_pace_str}. "
    "Longos em MP (marathon pace) ou MP+10-20s/km nos longos com finish rápido "
    "são as sessões-chave para validar esse ritmo."
)
