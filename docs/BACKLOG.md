# Backlog de Melhorias

Ideias e melhorias identificadas durante o uso do sistema, ainda não priorizadas no roadmap principal. Cada item descreve **o que**, **por que** e **como** poderia ser resolvido.

## Convenção de prioridade

Cada item é taggeado no título com uma das seguintes prioridades:

- **[Alta]** — bloqueia ou afeta diretamente algo já no roadmap (D1-D7 / Fase 10) ou contamina narrativa pública. Tem prazo implícito.
- **[Média]** — melhoria com impacto demonstrado, mas pode rodar em paralelo sem cravar timeline.
- **[Baixa]** — ergonomia, organização interna, ou domínio fora de trabalho atual. Entra quando virar incômodo.

Itens **[Alta]** já agendados em um roadmap em execução trazem nota explícita ao fim do bloco apontando para a fase em que entrarão.

---

## Analytics

### [Alta] Best efforts via streams em `find_personal_records`

**Problema:** o cálculo atual considera apenas a distância **total** da atividade, dentro de uma janela de [target × 0,98, target × 1,05]. Isso exclui melhores esforços contidos dentro de corridas mais longas.

**Exemplo real:** o "Teste de 6Km" (28/02/2026, 6,03 km a 4:14/km) provavelmente contém um 5K mais rápido (~4:13/km) que o PR registrado de 5K na "Corrida do Pão" (4:27/km). Como a atividade total tem 6 km, ela é excluída da janela de 5K (4900–5250 m).

**Solução proposta:**
- Carregar `distance_stream` + `time_stream` da atividade
- Calcular o melhor segmento contínuo (janela deslizante) para cada distância-padrão
- Persistir os best efforts em uma tabela própria (`activity_best_efforts`)
- O PR finder consulta essa tabela em vez de filtrar por `distance_m` total

**Impacto:** PRs verdadeiros, captura de "bombadas" dentro de longões, base mais sólida para predições.

> **Status:** agendado para execução antes da Fase D4 (roadmap de dados, spec §12.8). Mart `fct_pr_efforts` consome o resultado.

### [Média] Features de elevação mais ricas em `find_anomalies`

**Problema:** a feature de inclinação no modelo de anomalias é apenas `elevation_gain_m / distance_m`, que perde informação importante quando o trajeto tem perfil assimétrico (descida + subida pesada).

**Exemplo real:** Morning Run de 21/02/2026 — 16 km na Estrada Velha de Santos (Caminhos do Mar), com 8 km descendo e 8 km subindo a serra (685 m de variação de altitude, ~8,5% de grade na subida). O modelo viu apenas grade médio = 4,22%, previu pace de 5:20/km e marcou a corrida real (6:27/km) como outlier de −2,11σ. Não é uma anomalia de desempenho — é o modelo subestimando a dificuldade do trajeto.

**Solução proposta:**
- Usar **NGP** (Normalized Graded Pace) — já implementado em `analytics/ngp.py` — como target em vez de `average_speed_mps`. NGP já compensa o efeito da inclinação.
- Alternativa mais simples: adicionar `elev_delta` (high − low de altitude) e/ou `max_grade` extraído dos streams como features adicionais.

**Impacto:** menos falsos positivos em trajetos com perfil acidentado, classificação mais justa de "rotas duras" vs. "dia ruim".

### [Média] Camada de qualidade de dados (Data Quality Layer)

**Problema:** múltiplas classes de erro nos streams entram direto nos cálculos sem qualquer defensivo. Auditoria da Fase 8 confirmou que o único filtro existente é `np.clip(grade, ±0.45)` em NGP e drop de HR=0 em EF — qualquer outro tipo de ruído contamina métricas downstream. Categorias relevantes:

- **GPS inflado** (túneis, perda de sinal, drift): infla `distance_m` → pace artificialmente otimista, contamina PRs, EF, predict_race_time, comparações de período
- **HR spikes** (cinta perdendo contato, interferência elétrica): valores ≥220 bpm entram em EF, decoupling e médias sem filtragem
- **Stream gaps** (sensor pausado, falha de sync): segmentos sem dados distorcem médias móveis e cumulativos
- **Pace impossível** (split de 2:30/km em terreno plano)
- **Mismatch moving vs elapsed**: paradas longas inflam um sem afetar o outro

**Exemplo real:** meia maratona em 12/04/2026 registrou 23 km no Strava (kms 17–19 com pace inconsistente por perda de sinal em túnel). Aparece como `longest` + `fastest_run` + `highest_load` no `generate_period_narrative` das últimas 4 semanas, com pace de 5:09/km — artificialmente otimista (distância real ≈ 21,1 km).

**Solução proposta (camada com 3 frentes complementares):**
- **Flag manual**: campo `data_quality` em `activities` (`gps_corrupt`, `hr_corrupt`, `race_official_distance` etc.) marcado pelo usuário; analytics filtram ou ajustam
- **Detector automático**: heurísticas em batch sobre streams — variação anômala entre splits adjacentes, gap entre `moving_time` e `elapsed_time`, jump de altitude/lat-lng, FC fora de [30, 220], pace fora de [2:30, 12:00]/km. Marcar `data_quality` automaticamente
- **Distância oficial em provas**: quando atividade tem `workout_type=race`, permitir sobrescrita por valor oficial (5K, 10K, 21,0975, 42,195) e recalcular pace

**Impacto:** highlights, PRs, EF, decoupling, predict_race_time deixam de ser contaminados. Especialmente importante em provas, onde o erro coincide com a sessão de maior carga e intensidade do período.

### [Baixa] Inferência de cidade em `get_route_clusters`

**Problema:** os clusters retornam apenas `centroid_lat` / `centroid_lng`. Não há tradução automática para nome de cidade — para descobrir que (-22,99, -43,22) é Rio de Janeiro, o usuário/LLM precisa cruzar com o nome da atividade ou ter conhecimento prévio de coordenadas.

**Exemplo real:** corridas em Rio de Janeiro (jun/2025), Igaratá (set/2025) e Brasília (nov/2025) não aparecem como clusters porque cada cidade tem só 1–2 atividades, abaixo do `min_samples=3` do DBSCAN. Mesmo se aparecessem, precisaríamos olhar para a lat/lng e adivinhar a cidade.

**Soluções possíveis (a decidir quando priorizar):**
- **Bounding box local**: lookup hardcoded de cidades-chave (SP, Rio, Brasília, etc.) com seus bbox. Rápido, zero dependências, mas restrito ao que está cadastrado.
- **Reverse geocoding via Nominatim/OSM**: cobertura mundial, gratuito mas com rate limit (1 req/s) e latência. Bom candidato para cache local por (lat, lng) arredondado.

**Impacto:** clusters passam a ter um `city` ou `location_label` legível, e atividades em viagens (mesmo isoladas) podem ser agrupadas por cidade em vez de descartadas como ruído do DBSCAN.

### [Média] `compare_cycles()` — comparar ciclo atual com ciclo de prova anterior

**Problema:** atualmente é trabalhoso comparar a janela de preparação atual com ciclos passados que terminaram em meias bem-sucedidas. O usuário precisa montar manualmente as datas e cruzar `get_period_stats`, `get_load_history` e `get_aerobic_efficiency_trend`.

**Solução proposta:** tool `compare_cycles(reference_race_id, current_window_days=84)` que:
- Identifica o ciclo da prova de referência (ex.: 12 semanas antes da data da prova)
- Define a janela atual (mesmos N dias contados de hoje para trás)
- Retorna comparação lado a lado: km totais, distribuição por zona, picos de CTL/ATL, número de longões, decoupling médio, sessões de quality (Z4-Z5)

**Impacto:** responde diretamente "estou treinando melhor que para a meia X?" — útil na calibração da maratona contra o melhor ciclo anterior.

### [Média] Validação cruzada do `what_drives_my_performance`

**Problema:** com poucas atividades e features correlacionadas, gradient boosting pode reportar feature importance instável (overfitting). Não há diagnóstico atual confirmando que as importâncias são robustas.

**Solução proposta:**
- Cross-validation 5-fold reportando R² médio e desvio
- Comparar top features do GB com Spearman correlation simples — divergência forte sinaliza overfitting
- Expor metadado `confidence: low|medium|high` na resposta da tool (baseado em N atividades, R² CV, estabilidade do ranking)

**Impacto:** tool deixa de "vender" insights frágeis; LLM tem sinal explícito para moderar interpretação quando o modelo está pouco confiável.

---

## Arquitetura e MCP

### [Média] Envelope padronizado para tools MCP

**Problema:** cada tool retorna estrutura própria, sem campos meta padronizados (warnings, confidence, units, status). LLM consumidor lida com formatos heterogêneos e não tem canal padrão para sinalizar "este resultado tem ressalvas".

**Solução proposta:** wrapper de retorno comum, aplicado via decorator em `mcp_server/server.py`:
```json
{
  "status": "ok | warning | empty",
  "data": { ... payload específico da tool },
  "warnings": ["dado parcial: 8 dias sem stream", ...],
  "confidence": "low | medium | high",
  "units": { "distance": "km", "pace": "/km" }
}
```
Retrocompatível: o campo `data` preserva o payload anterior.

**Impacto:** LLM propaga warnings e confidence de forma consistente; tool calls mais auditáveis.

### [Baixa] Versões `summary`/`detailed` em tools narrativas

**Problema:** `generate_period_narrative` e `what_drives_my_performance` retornam payload grande que pode estourar contexto em períodos longos ou modelos de janela menor.

**Solução proposta:** parâmetro `detail_level: "summary" | "detailed"` (default: `"detailed"` para preservar comportamento atual):
- `summary`: estatísticas agregadas + top 1 highlight + concerns
- `detailed`: payload completo

**Impacto:** ergonomia em conversas longas; granularidade escolhida conforme a pergunta.

### [Baixa] Reorganização de `analytics/` em sub-pastas

**Problema:** o módulo mistura granularidades — métricas determinísticas (`load`, `ngp`, `efficiency`, `zones`), feature engineering, modelos preditivos (`anomalies`, `performance_drivers`, `plateau`, `race_prediction`) e diagnostics (`injury_risk`, `narrative`).

**Solução proposta:**
```
analytics/
  metrics/      → load, ngp, efficiency, zones
  features/     → extração de features para modelos
  models/       → anomalies, performance_drivers, race_prediction, plateau
  diagnostics/  → injury_risk, narrative
```

**Impacto:** apenas organizacional. Sem ganho funcional imediato — fazer só quando a navegação ficar dolorosa.

---

## Sincronização

### [Baixa] Pipeline pós-sync automático

**Problema:** após `sync_now`, é necessário rodar manualmente `sync --streams` e `compute-metrics`. Atividades novas ficam sem métricas computadas até o usuário rodar os comandos.

**Solução proposta:** flag opcional em `sync_now(auto_compute=True)` que dispara stream download + compute-metrics apenas para as atividades novas (delta), evitando reprocessar todo o histórico.

---

## Dados climáticos

### [Baixa] Integração com Open-Meteo (opcional)

Decisão atual em [ADR 0002](decisions/0002-weather-integration-optional.md): postergada. Reavaliar se a análise de impacto climático ganhar prioridade. Nesse caso, o approach seria usar Open-Meteo apenas como fallback para atividades sem `average_temp` no `raw_json` do Strava.

---

## Concluído

Itens originalmente listados aqui que já foram executados. Mantidos como histórico para rastreabilidade do "porquê" das mudanças no pipeline.

### [Alta] Extrair `average_temp` do `raw_json` para coluna própria — PR #19 (11/05/2026)

`compute-metrics` agora parsea `raw_json.average_temp` e grava em `activity_metrics.weather_temp_c`. Cobertura: 0/194 → 124/194 corridas (64%). Indoor (Pilates/WeightTraining) seguem sem cobertura como esperado. Habilita coluna populada em `fct_race_performance` (D4) e o modelo de `what_drives_my_performance` passa a ter sinal real de temperatura.

### [Alta] Investigar `r_tss` sempre NULL — PR #18 (11/05/2026)

Causa confirmada: `analytics/ngp.py:r_tss()` retornava `None` quando `threshold_pace_mps` era ausente — e `athlete_config` estava vazio (preenchido só parcialmente em PR #16, sem o pace). Fix: adicionar `threshold_pace_mps = 3.663 m/s` (4:33/km, estimado via Daniels a partir da meia 1:40:09 em 15/03/2026) ao `scripts/seed_athlete_config.py`. Cobertura: 0/194 → 194/194 corridas (100%). `r_tss` médio é ~17% menor que `hr_tss` — diferença esperada (`hr_tss` superestima em esteira, dia quente, residual de intervalado). `coalesce(r_tss, hr_tss)` nos marts D3 herda o sinal melhor automaticamente.

### [Alta] Zonas Z1-Z5 calculadas via FC média (não listado originalmente) — PR #16 (10/05/2026)

Descoberto durante validação visual da página D5p3: `compute_metrics` chamava sempre `zone_seconds_from_summary` (joga 100% do `moving_time` na zona da FC média), nunca `zone_seconds_from_stream` (amostra-a-amostra). 300/301 atividades tinham todo o tempo concentrado em uma zona só. Fix: usar `_from_stream` quando `hr_stream` disponível; popular `athlete_config` (LTHR=177, FCmáx=201, FCrest=50) via `scripts/seed_athlete_config.py` (`threshold_pace_mps` ficou de fora, fixado depois em PR #18). Multi-zona: 1/301 → 193/301 atividades. Sem esse fix, toda a análise de polarização e a página D5p3 seriam enganosas.

---

## Convenções

- Itens descritos aqui são **não comprometidos** — viram trabalho só após decisão explícita
- Cada item carrega tag de prioridade no título (`[Alta]`, `[Média]`, `[Baixa]`) conforme rubric no início do arquivo. Reavaliar quando algo mudar de fase
- Quando um item entra em execução, mover para o roadmap principal (`docs/STRAVA_MCP_SPEC.md`) ou criar ADR específico
- Quando um item é concluído, mover para a seção "Concluído" preservando o resumo do que mudou e número do PR
- Se uma melhoria for decidida e descartada, mover para o final como histórico
