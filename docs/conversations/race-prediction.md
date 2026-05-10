# Predição de prova e progresso da preparação

Conversa real com o Claude usando o MCP `strava-analytics`. Data: 10/05/2026.

---

> **Estou me preparando para uma maratona em julho. Pega meu melhor 21K do histórico, projeta o tempo de maratona usando Riegel e VDOT, e me diz se minha tendência de eficiência aeróbica dos últimos meses sustenta esse pace.**

## Melhor 21K do histórico

**Mizuno Athenas Run Faster** — 15/03/2026

- Distância: 21.224 km · Tempo: **1:40:11** · Pace: **4:43/km** · FC média: 175 (≈ 99% do LTHR de 177)

## Projeções de maratona (a partir desse 21K)

| Modelo | Tempo | Pace |
|---|---|---|
| **Riegel** (k=1.06) | **3:27:33** | 4:55/km |
| **VDOT 45.36** | **3:26:52** | 4:54/km |

⚠️ Nota do próprio modelo: Riegel costuma ser **otimista** para alvos muito maiores que a corrida-fonte. VDOT é mais conservador, mas ambos assumem **base aeróbica preparada** para 42 km — coisa que uma meia não comprova.

## Tendência de eficiência aeróbica (6 meses)

| Mês | EF | n |
|---|---|---|
| Nov/25 | 0.01904 | 7 |
| Dez/25 | 0.01811 | 14 |
| **Jan/26** (canelite) | 0.01804 | 11 |
| Fev/26 | 0.01865 | 11 |
| **Mar/26** (PR meia) | **0.01922** | 11 |
| Abr/26 | 0.01873 | 17 |
| Mai/26 (parcial) | 0.01915 | 4 |

**Trend: improving** — recuperou da canelite e está em alta, ~+6% desde jan.

## A EF sustenta o pace projetado? **Provavelmente não, ainda.**

O que o pace de 4:54/km exige:

- Pace 4:54/km = **3.40 m/s**
- Uma maratona realista corre-se em **85–90% LTHR** (≈ 150–160 bpm pro LTHR 177)
- EF necessária para 3.40 m/s a FC 155: **~0.0219**
- EF necessária para 3.40 m/s a FC 160: **~0.0213**

**EF atual (~0.019) está ~12–15% abaixo do que o pace VDOT exige em FC de maratona.**

Para referência, na própria prova de 15/03 a EF foi ≈ 0.0202, mas a 175 bpm — intensidade de meia, **insustentável por 42 km**.

## Síntese realista

- **Riegel/VDOT (3:27)**: otimistas. Pressupõem que a aeróbica já está em nível de marathon, o que a EF ainda não confirma.
- **Faixa mais provável hoje**: **3:35–3:45** (pace 5:05–5:20/km). Considera EF atual + zero histórico de >25 km + janeiro perdido.
- **A favor**: tendência clara de melhora, CTL no maior nível recente (70.9), sem sinais de risco.
- **O que pode mudar isso até julho** (~9 semanas): sustentar progressão de EF até ~0.021, encarar bem o 21K e o 25K como "ensaios" de pace de maratona, e ter pelo menos 2–3 longões ≥ 28 km com pace alvo no fim.

## Sugestão de pace para a maratona

| Cenário | Pace | Tempo | Como tratar |
|---|---|---|---|
| **A (cauteloso)** | 5:15/km | 3:41:34 | Pace alvo padrão até km 30, libera depois |
| **B (realista)** | 5:05/km | 3:34:39 | Só se EF subir para ~0.0205 e longões confirmarem |
| **C (VDOT)** | 4:54/km | 3:26:52 | Não justificado pelos dados atuais |

**Para validar/ajustar:** rodar os 21K e 25K que faltam **em pace de maratona-alvo** (não em ritmo de prova de meia) e medir o decoupling — se o HR drift ficar < 5% num longão de 25–28 km no pace B, ganha argumento pra ir mais agressivo.

---

**Tools MCP usadas:** `find_personal_records`, `predict_race_time`, `get_aerobic_efficiency_trend`.
