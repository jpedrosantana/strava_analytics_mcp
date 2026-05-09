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
