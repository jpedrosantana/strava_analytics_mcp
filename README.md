# Strava Analytics MCP

Plataforma pessoal de análise esportiva via [Model Context Protocol](https://modelcontextprotocol.io/).
Sincroniza o histórico completo do Strava, aplica modelos de ciência do esporte e expõe insights como tools consumíveis por Claude Code, Claude Desktop ou qualquer cliente MCP compatível.

## O que isso faz

- Cache local SQLite com todo o histórico de atividades (backfill + sync incremental)
- Métricas científicas calculadas localmente: TRIMP, hrTSS, CTL/ATL/TSB, zonas Friel, NGP, eficiência aeróbica, decoupling cardíaco
- 13 tools MCP para o Claude analisar seus dados de treino via linguagem natural
- Risco de lesão baseado em ACWR e spikes de volume
- Roadmap: predições de prova (Riegel/VDOT), clima (Open-Meteo), ML, narrativa gerada por LLM

## Pré-requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Conta Strava com app criado em [developers.strava.com](https://developers.strava.com)

## Instalação

```bash
git clone https://github.com/<seu-usuario>/strava-analytics-mcp
cd strava-analytics-mcp
cp .env.example .env          # preencha com CLIENT_ID e CLIENT_SECRET
uv sync
```

## Uso

```bash
# 1. Autenticar com a Strava API (abre navegador)
uv run strava-mcp setup

# 2. Baixar histórico completo
uv run strava-mcp sync --full

# 3. Calcular métricas analíticas (TRIMP, CTL/ATL/TSB, zonas...)
uv run strava-mcp compute-metrics

# 4. Verificar saúde dos dados
uv run strava-mcp doctor

# Outros comandos
uv run strava-mcp sync                    # sync incremental (novidades desde último sync)
uv run strava-mcp sync --streams          # baixar streams de FC/pace/altitude
uv run strava-mcp sync --full --compute   # backfill + recalcular métricas
```

## Integração com Claude Code

Crie o arquivo `.mcp.json` na raiz do projeto (já está no `.gitignore` — cada máquina configura o próprio):

```json
{
  "mcpServers": {
    "strava-analytics": {
      "command": "uv",
      "args": ["run", "strava-mcp", "serve"],
      "cwd": "/caminho/absoluto/para/strava_analytics_mcp"
    }
  }
}
```

O `.claude/settings.json` do repositório já contém `enableAllProjectMcpServers: true`, que aprova automaticamente o servidor ao abrir o projeto. Reinicie o Claude Code e o servidor estará disponível.

> **Nota:** Se `uv` não estiver no PATH do Claude Code, use o caminho completo do executável (ex: `/home/user/.local/bin/uv`).

Exemplos de perguntas:

- *"Como foi meu treino esta semana comparado à semana passada?"*
- *"Qual minha forma atual? Estou pronto para um treino pesado amanhã?"*
- *"Minha eficiência aeróbica está melhorando nos últimos 3 meses?"*
- *"Qual o risco de lesão considerando minha carga recente?"*
- *"Liste as corridas longas do último mês com pace e FC média."*

## Tools MCP disponíveis

| Tool | Descrição |
|------|-----------|
| `list_activities` | Atividades dos últimos N dias com pace, FC, distância |
| `get_activity` | Detalhes de uma atividade (+ métricas calculadas opcionais) |
| `search_activities` | Busca por nome, distância, data, esporte |
| `get_period_stats` | Totais e médias de um período (distância, tempo, TSS, zonas) |
| `compare_periods` | Comparação lado-a-lado entre dois períodos |
| `get_weekly_breakdown` | Volume semana-a-semana das últimas N semanas |
| `get_current_form` | CTL, ATL, TSB e ACWR de hoje com histórico de 14 dias |
| `get_load_history` | Série histórica diária de carga de treino |
| `get_injury_risk_assessment` | Score de risco de lesão (ACWR + spikes de volume + degradação de EF) |
| `find_anomalies` | Detecta corridas com pace fora do esperado via regressão sobre o histórico |
| `get_aerobic_efficiency_trend` | Tendência mensal de EF em corridas |
| `get_decoupling_trend` | Decoupling cardíaco em corridas longas (≥60min) |
| `find_personal_records` | Melhores tempos em distâncias-padrão (5K, 10K, 21K, maratona...) |
| `predict_race_time` | Projeção de tempo via Riegel + VDOT em qualquer distância |
| `sync_now` | Dispara sync incremental (ou full) via tool |
| `athlete_doctor` | Diagnóstico de completude e qualidade dos dados |

## Configuração do atleta

Algumas métricas (TRIMP, zonas, hrTSS) são mais precisas com parâmetros configurados:

```bash
sqlite3 data/strava.db "
INSERT OR REPLACE INTO athlete_config VALUES ('lthr',    '165', datetime('now'));
INSERT OR REPLACE INTO athlete_config VALUES ('hr_max',  '187', datetime('now'));
INSERT OR REPLACE INTO athlete_config VALUES ('hr_rest', '50',  datetime('now'));
INSERT OR REPLACE INTO athlete_config VALUES ('sex',     'male', datetime('now'));
"
```

Se não configurados, LTHR e FCmáx são estimados automaticamente do histórico de corridas.

## Documentação

- [Métricas de Treinamento](docs/METRICS.md) — explicação de TRIMP, hrTSS, EF, Decoupling, CTL, ATL, TSB, ACWR e Status

## Roadmap

| Fase | Descrição | Status |
|------|-----------|--------|
| 0 | Fundação: estrutura, tooling, CI | ✅ |
| 1 | Cliente Strava + OAuth | ✅ |
| 2 | Banco SQLite + sync (backfill, incremental, streams) | ✅ |
| 3 | Analytics core (TRIMP, CTL/ATL/TSB, zonas, NGP, EF) | ✅ |
| 4 | MCP server v0.1 — 13 tools, usável no Claude | ✅ |
| 5 | Predições (Riegel, VDOT); clima opcional ([ADR 0002](docs/decisions/0002-weather-integration-optional.md)) | ✅ |
| 6 | ML e análises avançadas (anomalies, clustering, performance drivers) | 🚧 |
| 7 | Narrativa e diagnóstico gerado por LLM | — |
| 8 | Polish e portfólio | — |

## Stack

Python 3.11 · FastMCP · SQLite · httpx · pandas · numpy · uv · ruff
