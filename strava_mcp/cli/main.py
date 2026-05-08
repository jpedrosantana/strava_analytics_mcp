import asyncio
import sqlite3
from pathlib import Path

import typer

from strava_mcp.config import settings

app = typer.Typer(
    name="strava-mcp",
    help="Strava Analytics MCP — plataforma pessoal de análise esportiva.",
    no_args_is_help=True,
)


@app.command()
def setup() -> None:
    """Autentica com a Strava API e configura o ambiente local."""
    if not settings.strava_client_id or not settings.strava_client_secret:
        typer.echo(
            "Erro: STRAVA_CLIENT_ID e STRAVA_CLIENT_SECRET devem estar definidos no .env",
            err=True,
        )
        raise typer.Exit(1)

    try:
        from strava_mcp.strava_client.auth import run_oauth_flow

        token_data = run_oauth_flow(
            settings.strava_client_id,
            settings.strava_client_secret,
            settings.strava_db_path,
        )
        athlete = token_data.get("athlete") or {}
        name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
        typer.echo(f"\nAutenticado com sucesso! Olá, {name or 'atleta'}!")
        typer.echo(f"Athlete ID: {athlete.get('id')}")
        typer.echo(f"Tokens salvos em: {settings.strava_db_path}")
    except Exception as e:
        typer.echo(f"Erro na autenticação: {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def sync(
    full: bool = typer.Option(False, "--full", help="Backfill completo do histórico."),
    streams: bool = typer.Option(
        False, "--streams", help="Baixar streams para atividades sem elas (lento)."
    ),
    streams_limit: int = typer.Option(
        50, "--streams-limit", help="Máximo de atividades para baixar streams."
    ),
    compute: bool = typer.Option(
        False, "--compute", help="Recalcular métricas analíticas após sync."
    ),
) -> None:
    """Sincroniza atividades com a Strava API."""
    from strava_mcp.strava_client.client import StravaClient

    client = StravaClient()

    if streams:
        typer.echo("Baixando streams...")
        result = asyncio.run(_run_streams(client, streams_limit))
        typer.echo(
            f"Streams: {result['success']} ok, {result['errors']} erros "
            f"(de {result['processed']} atividades)"
        )
        if compute:
            _run_compute()
        return

    if full:
        typer.echo("Iniciando backfill completo...")

        def progress(page: int, total: int) -> None:
            typer.echo(f"  página {page} — {total} atividades sincronizadas...", nl=False)
            typer.echo("\r", nl=False)

        count = asyncio.run(_run_backfill(client, progress))
        typer.echo(f"\nBackfill completo: {count} atividades sincronizadas.")
    else:
        typer.echo("Iniciando sync incremental...")
        try:
            count = asyncio.run(_run_incremental(client))
            typer.echo(f"Sync incremental completo: {count} atividades novas/atualizadas.")
        except RuntimeError as e:
            typer.echo(f"Erro: {e}", err=True)
            raise typer.Exit(1) from e

    if compute:
        _run_compute()


@app.command()
def compute_metrics() -> None:
    """Recalcula métricas analíticas (TRIMP, TSS, CTL/ATL/TSB) para todas as atividades."""
    _run_compute()


def _run_compute() -> None:
    from strava_mcp.sync.compute_metrics import compute_all_metrics

    typer.echo("Calculando métricas analíticas...")
    processed = [0]

    def progress(current: int, total: int) -> None:
        if current % 50 == 0 or current == total:
            typer.echo(f"  {current}/{total} atividades...", nl=False)
            typer.echo("\r", nl=False)
        processed[0] = current

    result = compute_all_metrics(settings.strava_db_path, progress=progress)
    typer.echo(
        f"\nMétricas: {result['activities']} atividades, {result['daily_rows']} dias calculados."
    )


async def _run_backfill(client, progress=None) -> int:
    from strava_mcp.sync.backfill import run_backfill

    return await run_backfill(settings.strava_db_path, client, progress)


async def _run_incremental(client) -> int:
    from strava_mcp.sync.incremental import run_incremental

    return await run_incremental(settings.strava_db_path, client)


async def _run_streams(client, limit: int) -> dict:
    from strava_mcp.sync.streams import download_streams_batch

    return await download_streams_batch(settings.strava_db_path, client, limit=limit)


@app.command()
def doctor() -> None:
    """Diagnóstico de saúde dos dados: completude, qualidade, último sync."""
    db_path = settings.strava_db_path

    if not Path(db_path).exists():
        typer.echo("Banco não encontrado. Execute `strava-mcp setup` e `strava-mcp sync --full`.")
        raise typer.Exit(1)

    db_size_mb = Path(db_path).stat().st_size / 1_048_576

    with sqlite3.connect(db_path) as conn:
        from strava_mcp.db.repositories import ActivityRepository, SyncStateRepository

        total = ActivityRepository.count(conn)
        by_sport = ActivityRepository.count_by_sport(conn)
        newest = ActivityRepository.get_newest_start_date(conn)
        oldest = ActivityRepository.get_oldest_start_date(conn)
        without_streams = ActivityRepository.count_without_streams(conn)
        last_full = SyncStateRepository.get(conn, "last_full_sync_at")
        last_inc = SyncStateRepository.get(conn, "last_incremental_sync_at")

    typer.echo("\n=== Strava MCP — Diagnóstico ===\n")
    typer.echo(f"Banco:       {db_path} ({db_size_mb:.1f} MB)")
    typer.echo(f"Último full: {last_full or 'nunca'}")
    typer.echo(f"Último inc:  {last_inc or 'nunca'}")
    typer.echo(f"\nAtividades:  {total} total")

    if oldest and newest:
        typer.echo(f"Período:     {oldest[:10]} → {newest[:10]}")

    if by_sport:
        typer.echo("\nPor esporte:")
        for sport, count in by_sport.items():
            typer.echo(f"  {sport}: {count}")

    typer.echo(f"\nSem streams: {without_streams}")

    if total == 0:
        typer.echo("\n⚠  Banco vazio. Execute `strava-mcp sync --full`.")
    elif without_streams == total:
        typer.echo("⚠  Nenhuma atividade tem streams. Use `strava-mcp sync --streams`.")
    else:
        typer.echo("\n✓  Banco saudável.")


@app.command()
def serve() -> None:
    """Inicia o MCP server em modo stdio (para uso com Claude Desktop / Claude Code)."""
    from strava_mcp.mcp_server.server import mcp

    mcp.run(transport="stdio")


if __name__ == "__main__":
    app()
