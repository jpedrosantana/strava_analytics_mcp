# Backlog de Melhorias

Ideias e melhorias identificadas durante o uso do sistema, ainda não priorizadas no roadmap principal. Cada item descreve **o que**, **por que** e **como** poderia ser resolvido.

---

## Analytics

### Best efforts via streams em `find_personal_records`

**Problema:** o cálculo atual considera apenas a distância **total** da atividade, dentro de uma janela de [target × 0,98, target × 1,05]. Isso exclui melhores esforços contidos dentro de corridas mais longas.

**Exemplo real:** o "Teste de 6Km" (28/02/2026, 6,03 km a 4:14/km) provavelmente contém um 5K mais rápido (~4:13/km) que o PR registrado de 5K na "Corrida do Pão" (4:27/km). Como a atividade total tem 6 km, ela é excluída da janela de 5K (4900–5250 m).

**Solução proposta:**
- Carregar `distance_stream` + `time_stream` da atividade
- Calcular o melhor segmento contínuo (janela deslizante) para cada distância-padrão
- Persistir os best efforts em uma tabela própria (`activity_best_efforts`)
- O PR finder consulta essa tabela em vez de filtrar por `distance_m` total

**Impacto:** PRs verdadeiros, captura de "bombadas" dentro de longões, base mais sólida para predições.

### Features de elevação mais ricas em `find_anomalies`

**Problema:** a feature de inclinação no modelo de anomalias é apenas `elevation_gain_m / distance_m`, que perde informação importante quando o trajeto tem perfil assimétrico (descida + subida pesada).

**Exemplo real:** Morning Run de 21/02/2026 — 16 km na Estrada Velha de Santos (Caminhos do Mar), com 8 km descendo e 8 km subindo a serra (685 m de variação de altitude, ~8,5% de grade na subida). O modelo viu apenas grade médio = 4,22%, previu pace de 5:20/km e marcou a corrida real (6:27/km) como outlier de −2,11σ. Não é uma anomalia de desempenho — é o modelo subestimando a dificuldade do trajeto.

**Solução proposta:**
- Usar **NGP** (Normalized Graded Pace) — já implementado em `analytics/ngp.py` — como target em vez de `average_speed_mps`. NGP já compensa o efeito da inclinação.
- Alternativa mais simples: adicionar `elev_delta` (high − low de altitude) e/ou `max_grade` extraído dos streams como features adicionais.

**Impacto:** menos falsos positivos em trajetos com perfil acidentado, classificação mais justa de "rotas duras" vs. "dia ruim".

### Extrair `average_temp` do `raw_json` para coluna própria

**Problema:** o `what_drives_my_performance` consulta `activity_metrics.weather_temp_c`, que está sempre nulo (nunca populamos esse campo). Resultado: a feature de temperatura tem importância ~0 no modelo, mesmo que ~41% das atividades tenham temperatura no `raw_json` do Strava.

**Solução proposta:** durante o `compute-metrics`, ler `raw_json.average_temp` (do sensor do Garmin) e gravar em `activity_metrics.weather_temp_c`. Sem precisar de Open-Meteo (cf. ADR 0002).

**Impacto:** o modelo de drivers passa a refletir o impacto real da temperatura no pace.

### Detecção/correção de atividades com GPS corrompido

**Problema:** atividades com erro de GPS (túneis, perda de sinal, drift em prédios altos) inflam `distance_m` e, por consequência, deflacionam o pace calculado como `distance/time`. Isso contamina toda a stack analítica: `total_distance_km` de períodos, `longest`/`fastest_run` em highlights, baseline de PRs, EF, predict_race_time e qualquer comparação histórica.

**Exemplo real:** meia maratona em 12/04/2026 registrou 23 km no Strava (kms 17–19 com pace zoado por túnel). A atividade aparece como `longest` + `fastest_run` + `highest_load` no `generate_period_narrative` das últimas 4 semanas, com pace de 5:09/km — que está artificialmente otimista, já que a distância real foi ~21,1 km.

**Soluções possíveis (a decidir quando priorizar):**
- **Flag manual**: campo `data_quality` em `activities` (ex: `gps_corrupt`, `race_official_distance`) que o usuário marca em atividades específicas. Analytics filtram ou ajustam baseado no flag.
- **Detector automático**: heurísticas sobre os streams — variação anômala entre splits adjacentes, gap suspeito entre `moving_time` e `elapsed_time`, jump de altitude/lat-lng. Marcar `data_quality` automaticamente.
- **Distância oficial em provas**: quando atividade tem `workout_type=race` (ou tag manual), permitir sobrescrita da distância pelo valor oficial (5K, 10K, 21,0975, 42,195). Pace é recalculado.

**Impacto:** highlights, PRs e médias de período deixam de ser contaminados por dados ruins. Particularmente importante para provas, onde o erro tende a vir junto com a sessão de maior carga e maior intensidade do período.

### Inferência de cidade em `get_route_clusters`

**Problema:** os clusters retornam apenas `centroid_lat` / `centroid_lng`. Não há tradução automática para nome de cidade — para descobrir que (-22,99, -43,22) é Rio de Janeiro, o usuário/LLM precisa cruzar com o nome da atividade ou ter conhecimento prévio de coordenadas.

**Exemplo real:** corridas em Rio de Janeiro (jun/2025), Igaratá (set/2025) e Brasília (nov/2025) não aparecem como clusters porque cada cidade tem só 1–2 atividades, abaixo do `min_samples=3` do DBSCAN. Mesmo se aparecessem, precisaríamos olhar para a lat/lng e adivinhar a cidade.

**Soluções possíveis (a decidir quando priorizar):**
- **Bounding box local**: lookup hardcoded de cidades-chave (SP, Rio, Brasília, etc.) com seus bbox. Rápido, zero dependências, mas restrito ao que está cadastrado.
- **Reverse geocoding via Nominatim/OSM**: cobertura mundial, gratuito mas com rate limit (1 req/s) e latência. Bom candidato para cache local por (lat, lng) arredondado.

**Impacto:** clusters passam a ter um `city` ou `location_label` legível, e atividades em viagens (mesmo isoladas) podem ser agrupadas por cidade em vez de descartadas como ruído do DBSCAN.

---

## Sincronização

### Pipeline pós-sync automático

**Problema:** após `sync_now`, é necessário rodar manualmente `sync --streams` e `compute-metrics`. Atividades novas ficam sem métricas computadas até o usuário rodar os comandos.

**Solução proposta:** flag opcional em `sync_now(auto_compute=True)` que dispara stream download + compute-metrics apenas para as atividades novas (delta), evitando reprocessar todo o histórico.

---

## Dados climáticos

### Integração com Open-Meteo (opcional)

Decisão atual em [ADR 0002](decisions/0002-weather-integration-optional.md): postergada. Reavaliar se a análise de impacto climático ganhar prioridade. Nesse caso, o approach seria usar Open-Meteo apenas como fallback para atividades sem `average_temp` no `raw_json` do Strava.

---

## Convenções

- Itens descritos aqui são **não comprometidos** — viram trabalho só após decisão explícita
- Quando um item entra em execução, mover para o roadmap principal (`docs/STRAVA_MCP_SPEC.md`) ou criar ADR específico
- Se uma melhoria for decidida e descartada, mover para o final como histórico
