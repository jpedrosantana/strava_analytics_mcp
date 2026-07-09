# ADR 0005 — Bloqueio externo: assinatura Strava paga agora exigida para acesso à API

**Status:** Aceito (constatação de bloqueio externo, sem decisão de produto ainda)
**Data:** 2026-07-09

## Contexto

Em 09/07/2026, `uv run strava-mcp sync --full --streams --compute` passou a
falhar com `403 Forbidden`:

```json
{"message":"Forbidden","errors":[{"resource":"Application","field":"Status","code":"Inactive"}]}
```

Investigação (token válido, refresh funcionando, `curl` direto contra
`/athlete/activities` reproduz o mesmo 403) descartou bug no client OAuth
(`strava_mcp/strava_client/`). A causa é uma mudança de política da Strava,
confirmada via busca web em 09/07/2026:

- Desde **30/06/2026**, apps no tier "Standard" da API (caso deste projeto —
  app pessoal/hobby, uso próprio) exigem **assinatura Strava paga ativa**
  (US$ 11,99/mês) vinculada à conta do desenvolvedor para manter acesso.
  A cobrança é por desenvolvedor, não por app.
- Devs ativos elegíveis receberam 3 meses grátis via código por e-mail antes
  do corte — o usuário deste projeto não tem assinatura e não recebeu
  o e-mail com o código.
- Tier "Extended Access" (parceiros grandes, integrações oficiais tipo
  Garmin/Apple) é isento — não se aplica aqui.
- Motivação declarada pela Strava: crescimento de 448% em cadastros de
  apps no programa, atribuído a scraping por empresas de IA e abuso via
  intermediários.

Fontes: [An Update To Our Developer Program](https://communityhub.strava.com/insider-journal-9/an-update-to-our-developer-program-13428),
[Strava API Pricing in 2026](https://appsforstrava.com/blog/strava-developer-program-changes-2026/),
[heise online](https://www.heise.de/en/news/Strava-API-access-only-with-paid-subscription-in-the-future-11315017.html).

### Nota: MCP Connector oficial da Strava (paralelo, não substitui este projeto)

Em 01/06/2026 a Strava lançou seu próprio conector MCP remoto
(`https://mcp.strava.com/mcp`, setup via `claude mcp add --transport http
strava-mcp https://mcp.strava.com/mcp`), somente leitura, cobrindo
histórico de atividades, tendências de fitness, readiness, planejamento de
metas, cross-sport e gear. **Também exige a mesma assinatura Strava** —
não é uma forma de contornar o bloqueio, é o mesmo pagamento dando acesso
a dois produtos diferentes:

- MCP oficial da Strava → métricas prontas deles (Athlete Intelligence).
- Este projeto (`strava-mcp` local) → análises bespoke não disponíveis lá
  (TRIMP, CTL/ATL/TSB, EF/decoupling, marts dbt, Riegel→42K, clusters de
  rota via DBSCAN).

Ou seja: se a assinatura for feita por qualquer motivo, os dois passam a
funcionar — não é decisão de escolher um ou outro.

Fonte: [Strava Help Center — Strava MCP Connector](https://support.strava.com/hc/en-us/articles/46190267796237-Strava-MCP-Connector).

## Decisão

Registrar o bloqueio como constatação (não há solução de código — é
dependência externa de pagamento). Nenhuma mudança de arquitetura é feita
agora. O projeto permanece funcional em modo "somente leitura dos dados já
sincronizados": SQLite (`data/strava.db`) e DuckDB (`data/strava.duckdb`)
não são afetados, dashboard e MCP tools de análise continuam operando sobre
os dados já baixados (337/337 atividades com streams, até 21/06/2026).

O que para de funcionar até resolução:
- `strava-mcp sync` (incremental ou `--full`) — bloqueado em qualquer chamada
  que toque `/athlete/activities` ou endpoints de atividade individual.
- Consequentemente, `compute-metrics` sobre atividades novas fica sem
  insumo (mas continua rodando normalmente sobre o que já existe).

## Alternativas consideradas

- **Assinar Strava (US$ 11,99/mês)**: resolve imediatamente, mas é decisão
  de gasto pessoal do usuário — não tomada nesta conversa. Bônus: destrava
  também o MCP Connector oficial da Strava (ver nota acima), não apenas a
  API deste projeto.
- **Aguardar/disputar elegibilidade ao crédito de 3 meses grátis**: usuário
  já confirmou que não recebeu o e-mail com código; não há caminho claro de
  reclamar isso retroativamente sem contato com suporte Strava.
- **Substituir fonte de dados (ex.: export manual GPX/TCX, Garmin Connect)**:
  não avaliado — mudaria o roadmap de dados inteiro (D1-D7) e o MCP em si,
  que é construído em torno da API Strava. Fora de escopo sem decisão
  explícita do usuário.

## Consequências

- Roadmap (Fases 0-9 concluídas, Fase 10 aguardando fim do BI) não muda —
  o bloqueio é operacional (ingestão de dados novos), não de produto.
- Enquanto não resolvido, qualquer sessão futura que tente `sync` deve
  primeiro checar se a assinatura foi resolvida antes de investigar como
  se fosse bug de código (este ADR documenta que já foi descartado).
- Se o usuário decidir assinar, ou se a Strava mudar a política de novo,
  atualizar o `Status` deste ADR para refletir a resolução.
