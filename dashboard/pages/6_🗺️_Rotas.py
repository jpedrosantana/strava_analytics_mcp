"""Página 6 — Rotas. Clusters geográficos via DBSCAN + mapa + tabela."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from db import query
from sklearn.cluster import DBSCAN

st.set_page_config(
    page_title="Rotas — Strava Analytics",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ Rotas")
st.caption(
    "Onde você corre. DBSCAN agrupa atividades outdoor pelo ponto de partida "
    "(lat/lng), revelando bairros/parques recorrentes. Clusters não recebem "
    "nome automático — listamos centroide + atividade mais comum como rótulo. "
    "Pontos cinza são outliers (rotas únicas, fora de qualquer cluster denso)."
)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
EARTH_RADIUS_M = 6_371_000

with st.sidebar:
    st.header("Filtros")
    period_options = {"90 dias": 90, "180 dias": 180, "365 dias": 365, "Tudo": None}
    period_label = st.selectbox("Período", list(period_options.keys()), index=3)
    period_days = period_options[period_label]

    st.header("Parâmetros DBSCAN")
    eps_m = st.slider(
        "Raio do cluster (eps, metros)",
        min_value=100,
        max_value=2000,
        value=500,
        step=100,
        help="Distância máxima entre dois pontos pra entrarem no mesmo cluster. "
        "Menor = clusters mais granulares (bairros), maior = clusters regionais.",
    )
    min_samples = st.slider(
        "Mín. atividades por cluster",
        min_value=2,
        max_value=10,
        value=3,
        help="Quantas atividades um ponto precisa ter próximas para formar cluster.",
    )

period_filter = (
    f"and f.date_key >= current_date - interval {period_days} day" if period_days else ""
)

# ─── Carrega atividades outdoor com coords ────────────────────────────────────
df = query(
    f"""
    select
        f.activity_id,
        f.date_key,
        d.activity_name,
        f.start_latlng_lat as lat,
        f.start_latlng_lng as lng,
        f.distance_km,
        f.pace_s_per_km,
        f.average_heartrate
    from marts.fct_activity f
    join marts.dim_activity d using (activity_id)
    where d.sport_type = 'Run'
      and f.start_latlng_lat is not null
      and f.start_latlng_lng is not null
      {period_filter}
    order by f.date_key
    """
)

if df.empty:
    st.info("Sem corridas outdoor com coordenadas no período.")
    st.stop()

# ─── DBSCAN com métrica haversine ─────────────────────────────────────────────
# eps em radianos: distância na superfície da Terra / raio terrestre
eps_rad = eps_m / EARTH_RADIUS_M
coords_rad = np.radians(df[["lat", "lng"]].values)
labels = DBSCAN(
    eps=eps_rad,
    min_samples=min_samples,
    metric="haversine",
    algorithm="ball_tree",
).fit_predict(coords_rad)

df["cluster_id"] = labels
df["is_outlier"] = labels == -1

n_total = len(df)
n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_outliers = int(df["is_outlier"].sum())
pct_clustered = 100.0 * (n_total - n_outliers) / n_total if n_total > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Corridas com GPS", f"{n_total}")
c2.metric("Clusters identificados", f"{n_clusters}")
c3.metric("Em algum cluster", f"{pct_clustered:.0f}%")
c4.metric("Outliers (rotas únicas)", f"{n_outliers}")

st.divider()

# ─── Tabela: top clusters ─────────────────────────────────────────────────────
st.subheader("Clusters por frequência")
st.caption(
    "Cada linha = um cluster, ordenado por número de atividades. **Atividade típica** "
    "é o nome mais frequente dentro do cluster — bom proxy quando o usuário nomeia "
    "as corridas pelo lugar (ex.: 'Ibirapuera matinal')."
)

clustered = df[~df["is_outlier"]].copy()
if not clustered.empty:
    cluster_stats = (
        clustered.groupby("cluster_id")
        .agg(
            n_runs=("activity_id", "count"),
            total_km=("distance_km", "sum"),
            avg_km=("distance_km", "mean"),
            avg_pace=("pace_s_per_km", "mean"),
            avg_hr=("average_heartrate", "mean"),
            centroid_lat=("lat", "mean"),
            centroid_lng=("lng", "mean"),
            first_date=("date_key", "min"),
            last_date=("date_key", "max"),
        )
        .reset_index()
    )

    # Atividade típica (nome mais frequente) por cluster
    typical_name = (
        clustered.groupby("cluster_id")["activity_name"]
        .agg(lambda s: s.mode().iat[0] if not s.mode().empty else s.iat[0])
        .reset_index(name="typical_name")
    )
    cluster_stats = cluster_stats.merge(typical_name, on="cluster_id").sort_values(
        "n_runs", ascending=False
    )

    def fmt_pace(s_per_km: float) -> str:
        if pd.isna(s_per_km):
            return "—"
        m, s = divmod(int(round(s_per_km)), 60)
        return f"{m}:{s:02d}/km"

    table = pd.DataFrame(
        {
            "Cluster": cluster_stats["cluster_id"].apply(lambda x: f"#{x}"),
            "Atividade típica": cluster_stats["typical_name"],
            "Corridas": cluster_stats["n_runs"],
            "Total (km)": cluster_stats["total_km"].round(1),
            "Média (km)": cluster_stats["avg_km"].round(1),
            "Pace médio": cluster_stats["avg_pace"].apply(fmt_pace),
            "FC média": cluster_stats["avg_hr"].apply(
                lambda x: f"{int(round(x))} bpm" if pd.notna(x) else "—"
            ),
            "Centroide": cluster_stats.apply(
                lambda r: f"{r['centroid_lat']:.4f}, {r['centroid_lng']:.4f}", axis=1
            ),
            "Primeira": pd.to_datetime(cluster_stats["first_date"]),
            "Última": pd.to_datetime(cluster_stats["last_date"]),
        }
    )
    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Primeira": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
            "Última": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
        },
    )
else:
    st.info("Nenhum cluster denso com os parâmetros atuais — ajuste eps/min_samples.")

st.divider()

# ─── Mapa interativo ──────────────────────────────────────────────────────────
st.subheader("Mapa")
st.caption(
    "Pontos coloridos por cluster (escala discreta). Outliers ficam em cinza. "
    "Hover mostra a atividade. Use o seletor abaixo para focar num cluster."
)


# Rótulo amigável para legendas
def cluster_label(cid: int) -> str:
    if cid == -1:
        return "Outlier"
    return f"Cluster #{cid}"


df["cluster_label"] = df["cluster_id"].apply(cluster_label)
df["pace_str"] = df["pace_s_per_km"].apply(
    lambda s: f"{int(s // 60)}:{int(s % 60):02d}/km" if pd.notna(s) else "—"
)
df["date_str"] = pd.to_datetime(df["date_key"]).dt.strftime("%d/%m/%Y")

# Filtro de cluster
if not clustered.empty:
    cluster_options = ["Todos"] + [f"Cluster #{c}" for c in cluster_stats["cluster_id"].tolist()]
    selected = st.selectbox("Focar em", cluster_options, index=0)
    if selected != "Todos":
        cid = int(selected.split("#")[1])
        df_map = df[df["cluster_id"] == cid]
    else:
        df_map = df
else:
    df_map = df

# Plotly scatter_map (MapLibre, sem token, tile open-street-map)
fig = px.scatter_map(
    df_map,
    lat="lat",
    lon="lng",
    color="cluster_label",
    hover_data={
        "activity_name": True,
        "date_str": True,
        "distance_km": ":.1f",
        "pace_str": True,
        "lat": False,
        "lng": False,
        "cluster_label": False,
    },
    zoom=9 if len(df_map) > 5 else 11,
    height=520,
    map_style="open-street-map",
)
fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    legend=dict(orientation="h", y=1.04, x=0.5, xanchor="center", title=None),
)
fig.update_traces(marker=dict(size=10, opacity=0.85))
st.plotly_chart(fig, use_container_width=True)
