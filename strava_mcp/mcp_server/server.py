"""Strava Analytics MCP server — exposes sports science tools to LLMs."""
import sqlite3
from typing import Any

from mcp.server.fastmcp import FastMCP

from strava_mcp.config import settings
from strava_mcp.mcp_server.queries import (
    query_athlete_doctor,
    query_compare_periods,
    query_find_personal_records,
    query_get_activity,
    query_get_aerobic_efficiency_trend,
    query_get_current_form,
    query_get_decoupling_trend,
    query_get_injury_risk,
    query_get_load_history,
    query_get_period_stats,
    query_get_weekly_breakdown,
    query_list_activities,
    query_predict_race_time,
    query_search_activities,
)

mcp = FastMCP(
    "strava-analytics",
    instructions=(
        "You have access to the athlete's complete Strava history with sports science metrics "
        "(TRIMP, CTL/ATL/TSB, aerobic efficiency, HR zones). Use these tools to answer training "
        "questions, spot trends, and give evidence-based coaching insights. Always cite data "
        "periods and activity counts in your analysis. When data is missing (no streams, no "
        "metrics computed), say so explicitly and suggest running compute-metrics."
    ),
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.strava_db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# 5.1 Basic reading
# ---------------------------------------------------------------------------


@mcp.tool()
def list_activities(
    days_back: int = 30,
    sport_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Lista atividades dos últimos N dias, opcionalmente filtradas por esporte.

    sport_type: 'Run', 'Ride', 'WeightTraining', etc. None = todos.
    Retorna campos resumidos: id, name, date, distance_km, duration_min,
    pace (min/km para corridas), avg_hr, elevation_m.
    """
    with _conn() as conn:
        return query_list_activities(conn, days_back, sport_type, limit)


@mcp.tool()
def get_activity(activity_id: int, include_metrics: bool = False) -> dict[str, Any]:
    """Detalhes completos de uma atividade.

    include_metrics=True: inclui TRIMP, TSS, zonas de FC, EF, decoupling calculados.
    Retorna None se a atividade não existir.
    """
    with _conn() as conn:
        result = query_get_activity(conn, activity_id, include_metrics)
    if result is None:
        return {"error": f"Activity {activity_id} not found"}
    return result


@mcp.tool()
def search_activities(
    name_contains: str | None = None,
    min_distance_km: float | None = None,
    max_distance_km: float | None = None,
    after_date: str | None = None,
    before_date: str | None = None,
    sport_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Busca avançada de atividades com filtros combinados.

    after_date / before_date: formato 'YYYY-MM-DD'.
    sport_type: 'Run', 'Ride', 'WeightTraining', 'TrailRun', etc.
    Útil para encontrar todas as corridas longas, treinos em uma semana específica, etc.
    """
    with _conn() as conn:
        return query_search_activities(
            conn,
            name_contains=name_contains,
            min_distance_km=min_distance_km,
            max_distance_km=max_distance_km,
            after_date=after_date,
            before_date=before_date,
            sport_type=sport_type,
            limit=limit,
        )


# ---------------------------------------------------------------------------
# 5.2 Aggregate stats
# ---------------------------------------------------------------------------


@mcp.tool()
def get_period_stats(
    start_date: str,
    end_date: str,
    sport_type: str | None = None,
) -> dict[str, Any]:
    """Estatísticas agregadas de um período de treino.

    Retorna: total de distância (km), tempo (h), elevação (m), número de atividades,
    FC média, pace médio, TRIMP total, hrTSS total, distribuição % por zona de FC.
    start_date / end_date: formato 'YYYY-MM-DD'.
    Nota: métricas de zona e TSS requerem compute-metrics ter sido executado.
    """
    with _conn() as conn:
        return query_get_period_stats(conn, start_date, end_date, sport_type)


@mcp.tool()
def compare_periods(
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
    sport_type: str | None = None,
) -> dict[str, Any]:
    """Comparação lado-a-lado entre dois períodos de treino.

    Retorna deltas absolutos e percentuais de volume, distância, tempo,
    elevação e carga de treino (TRIMP). Útil para comparar semanas, meses
    ou bloco atual vs bloco anterior.
    Datas: formato 'YYYY-MM-DD'.
    """
    with _conn() as conn:
        return query_compare_periods(
            conn, period_a_start, period_a_end, period_b_start, period_b_end, sport_type
        )


@mcp.tool()
def get_weekly_breakdown(weeks_back: int = 12) -> list[dict[str, Any]]:
    """Breakdown semana-a-semana das últimas N semanas.

    Para cada semana: número de atividades, distância total (km), tempo total (h),
    elevação, breakdown por esporte. Útil para visualizar progressão de volume
    e consistência de treino.
    """
    with _conn() as conn:
        return query_get_weekly_breakdown(conn, weeks_back)


# ---------------------------------------------------------------------------
# 5.3 Training load
# ---------------------------------------------------------------------------


@mcp.tool()
def get_current_form() -> dict[str, Any]:
    """Estado atual de forma física: CTL, ATL, TSB e ACWR.

    CTL (Chronic Training Load): fitness de longo prazo, média exponencial 42 dias.
    ATL (Acute Training Load): fadiga recente, média exponencial 7 dias.
    TSB (Training Stress Balance): forma = CTL - ATL.
    ACWR: razão agudo/crônico — >1.5 indica risco de lesão.
    Inclui interpretação textual e histórico dos últimos 14 dias.
    Requer compute-metrics ter sido executado.
    """
    with _conn() as conn:
        result = query_get_current_form(conn)
    if result is None:
        return {
            "error": "No training load data available. Run: strava-mcp compute-metrics",
        }
    return result


@mcp.tool()
def get_load_history(days_back: int = 90) -> list[dict[str, Any]]:
    """Série histórica diária de CTL, ATL, TSB e TSS dos últimos N dias.

    Cada entrada contém: date, ctl, atl, tsb, daily_tss, n_activities,
    total_distance_m, total_moving_time_s.
    Útil para visualizar tendências de forma e identificar blocos de treino.
    Requer compute-metrics ter sido executado.
    """
    with _conn() as conn:
        return query_get_load_history(conn, days_back)


@mcp.tool()
def get_injury_risk_assessment() -> dict[str, Any]:
    """Avaliação de risco de lesão baseada em indicadores de carga de treino.

    Analisa: ACWR (agudo:crônico), spikes de volume semanal.
    Retorna: score 0-100, nível de risco (low/moderate/high),
    lista de fatores contribuintes com severidade.
    Zona segura: ACWR entre 0.8 e 1.3.
    Requer compute-metrics ter sido executado.
    """
    with _conn() as conn:
        return query_get_injury_risk(conn)


# ---------------------------------------------------------------------------
# 5.4 Efficiency
# ---------------------------------------------------------------------------


@mcp.tool()
def get_aerobic_efficiency_trend(months_back: int = 6) -> dict[str, Any]:
    """Tendência mensal de eficiência aeróbica (EF) em corridas.

    EF = pace(m/s) / FC_média. Valor maior = mais rápido à mesma FC = melhor.
    Agrega por mês e indica tendência (improving/declining).
    Nota: EF de summary (sem streams) é aproximada. Streams melhoram a precisão.
    Requer compute-metrics ter sido executado.
    """
    with _conn() as conn:
        return query_get_aerobic_efficiency_trend(conn, months_back)


@mcp.tool()
def get_decoupling_trend(months_back: int = 6) -> list[dict[str, Any]]:
    """Decoupling cardíaco (Pa:HR) de corridas longas (≥60min) em ordem cronológica.

    Decoupling = queda de eficiência da 1ª para a 2ª metade de um treino longo.
    <5%: excelente base aeróbica. 5-10%: adequado. >10%: priorizar Z2.
    Requer streams baixados (sync --streams) e compute-metrics executado.
    """
    with _conn() as conn:
        return query_get_decoupling_trend(conn, months_back)


# ---------------------------------------------------------------------------
# 5.5 Predictions
# ---------------------------------------------------------------------------


@mcp.tool()
def find_personal_records() -> list[dict[str, Any]]:
    """Melhores tempos do atleta em distâncias-padrão de corrida.

    Retorna PRs em 5K, 10K, 15K, Meia (21.0975K), 25K, 30K e Maratona.
    Para cada distância, considera corridas dentro da janela [target × 0.98,
    target × 1.05] e seleciona a com menor moving_time. Distâncias sem
    registro retornam status "no_record".
    """
    with _conn() as conn:
        return query_find_personal_records(conn)


@mcp.tool()
def predict_race_time(
    target_distance_km: float,
    source_activity_id: int | None = None,
) -> dict[str, Any]:
    """Projeta tempo de prova em uma distância arbitrária via Riegel e VDOT.

    target_distance_km: distância da prova-alvo (ex.: 42.195 para maratona).
    source_activity_id: opcional. Se fornecido, usa essa atividade como base.
                        Caso contrário, escolhe automaticamente o PR mais
                        próximo da distância-alvo.

    Retorna projeções de Riegel (clássica) e VDOT (Daniels), com pace e tempo
    formatado, além da atividade-fonte usada.
    """
    target_m = target_distance_km * 1000.0
    with _conn() as conn:
        return query_predict_race_time(conn, target_m, source_activity_id)


# ---------------------------------------------------------------------------
# 5.8 Maintenance
# ---------------------------------------------------------------------------


@mcp.tool()
async def sync_now(full: bool = False) -> dict[str, Any]:
    """Sincroniza atividades com a Strava API.

    full=False (default): sync incremental desde o último sync.
    full=True: backfill completo (lento, use raramente).
    Retorna número de atividades novas/atualizadas.
    Nota: não baixa streams nem recalcula métricas automaticamente.
    """
    from strava_mcp.strava_client.client import StravaClient

    client = StravaClient()
    try:
        if full:
            from strava_mcp.sync.backfill import run_backfill

            count = await run_backfill(settings.strava_db_path, client)
            return {"synced": count, "type": "full"}
        else:
            from strava_mcp.sync.incremental import run_incremental

            count = await run_incremental(settings.strava_db_path, client)
            return {"synced": count, "type": "incremental"}
    except RuntimeError as e:
        return {"error": str(e), "hint": "Run strava-mcp sync --full first"}


@mcp.tool()
def athlete_doctor() -> dict[str, Any]:
    """Diagnóstico de saúde dos dados: completude, qualidade, status de sync.

    Retorna: total de atividades, período coberto, atividades sem streams,
    métricas computadas, tamanho do banco, problemas encontrados.
    Útil para verificar se os dados estão completos antes de análises.
    """
    with _conn() as conn:
        return query_athlete_doctor(conn, settings.strava_db_path)
