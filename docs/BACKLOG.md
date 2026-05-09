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
