# ADR 0004 — Camada de dados: DuckDB como warehouse + sequenciamento híbrido das fases D

**Status:** Aceito
**Data:** 2026-05-10

## Contexto

A seção 12 do spec define a camada de engenharia de dados complementar ao MCP. Duas escolhas previamente cravadas no spec foram revisadas no planejamento da Fase D1:

1. **Stack do warehouse (§12.2):** spec recomendava `dbt-sqlite` por simplicidade (mesmo banco do MCP, sem migração). DuckDB era citado como alternativa futura.
2. **Sequenciamento (§12.8):** spec listava ordem linear D1 → D2 → ... → D7, com cada fase referenciando dependências contra o roadmap principal.

Ao planejar a execução, três fatos pesaram na revisão:

- Todas as dependências do principal (Fases 2-6) já estão fechadas — qualquer ordem dentro de D1-D7 é viável agora.
- As páginas 1 e 2 do dashboard (D5: Visão Geral, Carga e Forma) dependem apenas de `fct_activity` + `fct_daily_load` (D2). Postergá-las até D3-D4 estarem prontos atrasa o feedback visual sem ganho real.
- DuckDB tem window functions e percentile aggregates ricos, leitura nativa de Parquet via extension `sqlite_scanner` para ler do operational store, e narrativa de portfólio mais alinhada a vagas modernas de analytics engineering.

## Decisão

### (a) DuckDB como warehouse analítico

Adotar `dbt-duckdb` desde D1, substituindo a recomendação de `dbt-sqlite` no spec §12.2. SQLite continua sendo o **operational store** do MCP (leitura/gravação pelos comandos `sync`, `compute-metrics`, `serve`). DuckDB lê do SQLite via extension `sqlite_scanner` e materializa os marts em `data/strava.duckdb`.

Trade-offs aceitos:
- Pipeline ganha um segundo arquivo de banco em `data/`.
- Models de staging usam leitura cross-engine (resolvido nativamente pelo `sqlite_scanner`).

Trade-offs ganhos:
- Window functions, percentile aggregates, ARRAY/STRUCT types nativos.
- Suporte a Parquet abre porta para snapshots versionados em branch separada (cf. spec §12.6).
- Stack mais comum em projetos open source de analytics engineering — replicação por terceiros mais provável.

### (b) Sequenciamento híbrido das fases D

Substitui a ordem linear de §12.8 pela seguinte:

```
D1 → D2 → D5 (páginas 1-2) → D3 → D5 (página 3) → [Backlog: best-efforts via streams + average_temp] → D4 → D6 → D7
```

Justificativa:
- Páginas 1-2 do dashboard dependem só de `fct_activity` + `fct_daily_load` (D2) → trazê-las antes de D3 entrega feedback visual ~1 sessão mais cedo.
- Página 3 (Eficiência) precisa de `fct_zone_distribution` (D3) → fica em segundo bloco do D5.
- Marts de prova (D4) ficam mais íntegros se best-efforts-via-streams e `average_temp` forem extraídos antes (cf. itens [Alta] no `BACKLOG.md`, agendados antes de D4).
- D6 (Streamlit completo + página *Ciclo Atual*) entra por último, depois que todos os marts e correções estão prontos.

## Consequências

- **Spec §12.2 e §12.8** ganham nota apontando para este ADR como source of truth do que está em execução.
- **Spec §12.6 (orquestração)** referências a "SQLite (analytics)" passam a ser DuckDB implicitamente.
- **`pyproject.toml`** ganha `dbt-core` e `dbt-duckdb` como dev deps no início de D1.
- **`CLAUDE.md`** ganha linha em "Status atual" apontando o sequenciamento ativo, para sessões futuras pegarem o contexto sem releitura desta conversa.
- **Backlog itens [Alta]** (`Best efforts via streams`, `Extrair average_temp`) confirmam o agendamento "antes de D4" registrado em seus Status.
- Se em algum momento exportar snapshots versionados (spec §12.6), DuckDB já trata Parquet nativamente — sem custo adicional.
