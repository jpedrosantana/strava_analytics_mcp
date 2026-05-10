# ADR 0004 — Camada de BI vive no mesmo repositório

**Status:** Aceito
**Data:** 2026-05-09

## Contexto

A camada de engenharia de dados (Fases D1–D7 — dbt + Streamlit) está prevista como evolução paralela ao MCP no roadmap principal (`docs/STRAVA_MCP_SPEC.md` § 12). À medida que o projeto se aproxima dessa camada, surgiu a dúvida natural: o trabalho de BI deve viver neste repositório ou em um repositório separado?

## Decisão

A camada de BI **permanece neste mesmo repositório**, com separação interna por módulo.

Estrutura prevista:

```
strava_analytics_mcp/
  strava_mcp/        # código MCP (já existe)
  analytics/         # funções científicas — compartilhadas entre MCP e BI
  dbt/               # modelos dbt (Fase D)
  dashboard/         # app Streamlit (Fase D)
  docs/decisions/    # ADRs centralizados
```

## Razões

1. **Camada de dados é compartilhada.** SQLite + `analytics/` são fundação. Duplicar TRIMP/CTL/EF em outro repo violaria DRY e criaria duas fontes de verdade para os mesmos cálculos científicos.
2. **Narrativa do projeto.** A Fase 10 (Conteúdo público) prevê um post conectando "MCP conversacional → percepção de limitações → BI complementar → plataforma integrada". Um único `git log` torna essa história mais legível e auditável.
3. **O SPEC já antecipa.** As Fases D1–D7 sempre estiveram aqui, paralelas ao roadmap principal — esta ADR formaliza o que era convenção implícita.
4. **CI e PR review unificados.** Uma única pipeline e mesma esteira de revisão.
5. **Custo de saída é baixo.** `git subtree split` permite extrair `dashboard/` ou `dbt/` para um repo separado preservando histórico, caso seja necessário no futuro.

## Gatilhos para revisitar

A decisão deve ser reavaliada se:

- O projeto passar a aceitar dados de **múltiplos atletas** (multi-user)
- O dashboard for **deployado publicamente** com SLA / autenticação
- Equipe externa começar a contribuir no BI sem interesse no MCP
- O `pyproject.toml` ficar dolorosamente pesado mesmo com `dependency-groups`

## Consequências

- Deps do BI (dbt-core, dbt-sqlite/dbt-duckdb, streamlit, plotly) entrarão em um novo `dependency-group` `bi` para não inflar o runtime do MCP.
- Section 12 do SPEC ganha referência a esta ADR.
- O README poderá mencionar (futuramente) o dashboard como "interface complementar" ao MCP, na seção `Documentação`.
