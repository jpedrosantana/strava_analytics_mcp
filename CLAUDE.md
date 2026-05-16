# Instruções para Claude Code

Leia `docs/STRAVA_MCP_SPEC.md` integralmente antes de qualquer ação.

Implemente fase a fase, em ordem (Fases 0-8 do roadmap principal,
Fases D1-D7 do roadmap de dados em paralelo após Fase 2).

Pare ao fim de cada fase para confirmação humana antes de prosseguir.

Critérios de aceitação por fase estão no SPEC — atendê-los é obrigatório.

Decisões não cobertas: registrar em `docs/decisions/NNNN-titulo.md`
no formato ADR.

Melhorias futuras identificadas mas não priorizadas: registrar em
`docs/BACKLOG.md`. Antes de iniciar qualquer item dali, confirmar com
o usuário e mover para o roadmap principal ou criar ADR específico.

## Perfil do atleta

Parâmetros estimados pelo histórico de corridas (não de teste laboratorial).
Valores ao vivo em `athlete_config` (populados via `scripts/seed_athlete_config.py`):

- FCmáx: 201 bpm (registrado no Teste de 6Km em 28/02/2026)
- LTHR: 177 bpm (média das FC em meias maratonas de prova: 173–179 bpm)
- FCrest: 50 bpm (placeholder — medir ao acordar para refinar)
- Threshold pace: 3,663 m/s ≈ 4:33/km (estimado via Daniels VDOT a partir
  da meia 1:40:09 em 15/03/2026; revisitar após próxima prova oficial)
- Sexo: masculino
  
## Contexto de Treino/Objetivo Atual
Faço corrida e musculação há quase 1 ano e meio, minha rotina de treinos de musculação são de 2-3x na semana (sendo 2 de funcional e 1 musculação) e de corrida é de 3-4x na semana (normalmente 2 treinos de rodage, 1 intervalado/fartlek e 1 longão de sábado). Meu objetivo atual é melhorar minha performance na corrida, atualmente estou me preparando para uma maratona em Julho. Meu histórico de provas tem destaque com as meias maratonas, completei 7 até o momento e até a maratona tenho mais uma prova de 21Km e outra de 25Km para fazer.

## Status atual dos dados
Streams: 100% completos (306/306 atividades). Último download: 16/05/2026.
`athlete_config`: populado (LTHR, FCmáx, FCrest, threshold_pace_mps, sex).
`compute-metrics` (último run em 16/05/2026) computa via stream:
- EF e decoupling (efficiency)
- Zonas Z1-Z5 (fix #16 — antes usava só FC média e jogava tudo numa zona)
- `r_tss` populado em 100% das 198 corridas (fix #18 — antes 0%)
- `weather_temp_c` extraído do `raw_json.average_temp` em ~64% das corridas
  (127/198; fix #19 — antes 0%; indoor naturalmente sem cobertura)
- `activity_best_efforts` populado em 186 corridas outdoor / 516 esforços
  em 1K–Meia (PR #22 — antes a tabela não existia)
- 159 corridas outdoor têm lat/lng (alimenta D6 página de Rotas)

## Roadmap em execução
Fases 0-9 do roadmap principal: concluídas. Fase 10 (post público) aguarda
fim do projeto de BI — com D6 concluída e D7 opcional, o BI está pronto.

Camada de dados (cf. [ADR 0004](docs/decisions/0004-data-layer-duckdb-and-sequencing.md)):

```
D1 ✅ → D2 ✅ → D5 p.1-2 ✅ → D3 ✅ → D5 p.3 ✅ → bundle pré-D4 ✅ → D4 ✅ → D6 ✅ → D7 (opcional)
```

Bundle pré-D4 (3 itens [Alta] do `BACKLOG.md`): concluído.
- ✅ `r_tss=NULL` (PR #18)
- ✅ `average_temp` do `raw_json` (PR #19)
- ✅ Best efforts via streams (PR #22)

D4 (marts de prova): concluído.
- ✅ `seeds/manual_races.csv` (12 provas, 7 meias completadas)
- ✅ `dim_race` (identificação combinada: seed + workout_type=1)
- ✅ `fct_pr_efforts` (best efforts ranked, is_pr/is_segment)
- ✅ `fct_race_performance` (tempo/pace/CTL/TSB/clima/Riegel→42K/rank entre meias)

D6 (Streamlit completo): conteúdo 100%. Falta só screenshots no README.
- ✅ Página 4 (Provas) — PR #24, parte do bundle PR-A
- ✅ Página 5 (Clima) — PR #24
- ✅ Página 8 (Anomalias) — PR #24
- ✅ Página 7 (Ciclo Atual) — PR #26: trajetória de CTL vs ideal,
  progressão de longos Pfitzinger-style, configurável por data alvo e
  CTL alvo no peak
- ✅ Página 6 (Rotas) — PR #27: DBSCAN haversine, mapa MapLibre com 5
  estilos selecionáveis, bolhas proporcionais à frequência do cluster
- ⬜ Screenshots no README (critério de aceitação D6)

Ciclo atual de maratona: NB Porto Alegre em 12/07/2026. Hoje (16/05/2026)
estamos na semana 8 de 16, CTL ~58. Página 7 mostra a trajetória.

Stack: SQLite (operational, MCP) + DuckDB (analytics, dbt).

## Workflows comuns

Comandos canônicos do projeto. Use estes antes de inventar variações.

```bash
# Pipeline analytics (recalcula activity_metrics + daily_metrics)
uv run strava-mcp compute-metrics

# Popular athlete_config (LTHR, FCmáx, FCrest, threshold_pace, sex)
uv run python scripts/seed_athlete_config.py

# Rodar dbt (build padrão; aceita qualquer subcomando dbt)
./scripts/transform.sh                          # = dbt build
./scripts/transform.sh test
./scripts/transform.sh build --select fct_weekly_summary

# Dashboard Streamlit
./scripts/dashboard.sh

# Lint / format (replica o que a CI roda)
uv run --group dev ruff format --check .
uv run --group dev ruff check .
```

**Regra operacional crítica:** o Streamlit segura o lock do arquivo
`data/strava.duckdb` enquanto está aberto. Qualquer `dbt build`
falha com `IOException: Could not set lock on file`. **Sempre pedir
para o usuário parar o dashboard antes de qualquer `dbt build` ou
`compute-metrics` que escreva no DuckDB.** Não tentar matar o
processo do usuário.

`uv run` sem `--group <nome>` pode resolver para dependências
erradas (ex.: `uv run dbt` traz `dbt-fusion`, que não suporta DuckDB).
Sempre especificar o group: `dbt`, `dashboard`, `dev`, `notebook`.

## Checklist antes de abrir PR

Antes de pushed/abrir PR, validar localmente o que a CI vai checar e
o que a infra exige:

1. `uv run --group dev ruff format --check .` passa (CI bloqueia se não)
2. `uv run --group dev ruff check <arquivos modificados>` passa
3. Se mudou pipeline analytics (`compute_metrics`, `analytics/`,
   `repositories`): rodar `uv run strava-mcp compute-metrics` para
   confirmar que processa as 306 atividades sem erro
4. Se mudou marts dbt ou pipeline upstream: parar Streamlit do usuário,
   rodar `./scripts/transform.sh` (espera 131 testes PASS)
5. Spot-check empírico do impacto: query rápida no DuckDB ou amostra
   no SQLite que mostre o antes/depois (não basta "código compila")
6. PR description: descrever **por que** e **impacto numérico**, não
   só **o que** — replicar formato dos PRs anteriores (#16, #18, #19)
