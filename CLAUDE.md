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
Streams: 100% completos (301/301 atividades). Último download: 10/05/2026.
`athlete_config`: populado (LTHR, FCmáx, FCrest, threshold_pace_mps, sex).
`compute-metrics` (último run em 11/05/2026) computa via stream:
- EF e decoupling (efficiency)
- Zonas Z1-Z5 (fix #16 — antes usava só FC média e jogava tudo numa zona)
- `r_tss` populado em 100% das 194 corridas (fix #18 — antes 0%)
- `weather_temp_c` extraído do `raw_json.average_temp` em 64% das corridas
  (fix #19 — antes 0%; indoor naturalmente sem cobertura)

## Roadmap em execução
Fases 0-9 do roadmap principal: concluídas. Fase 10 (post público) aguarda fim do projeto de BI.

Camada de dados (cf. [ADR 0004](docs/decisions/0004-data-layer-duckdb-and-sequencing.md)):

```
D1 ✅ → D2 ✅ → D5 páginas 1-2 ✅ → D3 ✅ → D5 página 3 ✅ → bundle pré-D4 [2/3] ⬅️ → D4 → D6 → D7
```

Bundle pré-D4 (3 itens [Alta] do `BACKLOG.md`):
- ✅ `r_tss=NULL` (PR #18)
- ✅ `average_temp` do `raw_json` (PR #19)
- ⏳ Best efforts via streams — pré-requisito direto do `fct_pr_efforts` em D4

Stack: SQLite (operational, MCP) + DuckDB (analytics, dbt).
