# Análise da semana

Conversa real com o Claude usando o MCP `strava-analytics`. Data: 10/05/2026.

---

> **Como foi minha semana de treino comparada à semana anterior? Quero ver volume total, distribuição por zona, principais sessões e se algo se destacou — pra cima ou pra baixo.**

## Comparação W18 (atual) vs W17 (anterior)

| Métrica | W17 (27/04–03/05) | W18 (04/05–10/05) | Δ |
|---|---|---|---|
| Atividades | 8 (4 corrida + 4 muscul.) | 6 (3 corrida + 3 muscul.) | **−2 (−25%)** |
| Distância (corrida) | 42.31 km | 38.62 km | −3.69 km (−8.7%) |
| Tempo total | 10.62 h | 7.88 h | **−2.74 h (−25.8%)** |
| Elevação | 64 m | 100 m | +36 m (+56%) |
| TRIMP | 693.7 | 528.6 | **−165 (−23.8%)** |
| HR-TSS | 660.9 | 504.8 | −156 (−23.6%) |
| CTL (fim) | 72.3 → 71.2 | 72.3 → **70.9** | −1.3 |
| TSB (fim) | −22.3 (sexta) | **−5.9** | **+16.4** |

**Leitura macro:** semana de **alívio** (−24% de carga, −26% de tempo). Era o esperado: você vinha de TSB −22 e agora está em −5.9 — recuperação saudável sem perder fitness (CTL caiu só 1.3).

## Distribuição por zona (W18)

| Zona | % | Observação |
|---|---|---|
| Z1 | **54.4%** | Alta — musculação puxa muito Z1 |
| Z2 | 27.3% | Saudável (rodage) |
| Z3 | **0%** | ⚠️ Zero estímulo de tempo/aeróbico-forte |
| Z4 | 18.3% | Vem do longão (FC 160 = limiar baixo) |
| Z5 | **0%** | Zero estímulo neuromuscular/VO2 |

## Sessões da W18

| Dia | Sessão | km | Pace | FC | TRIMP/Suffer |
|---|---|---|---|---|---|
| 04/05 seg | Rodage leve | 10.59 | 6:00/km | 145 | 127 |
| 05/05 ter | Musculação 60 min | — | — | 103 | 18 |
| 06/05 qua | Rodage moderado | 12.01 | 5:26/km | 147 | 155 |
| 07/05 qui | Musculação 60 min | — | — | 107 | 18 |
| **09/05 sáb** | **Longão 16k** | **16.02** | **5:23/km** | **160** | **313** |
| 10/05 dom | Musculação 137 min | — | — | 128 | 124 |

## O que se destacou

**Pra cima** ✅
- **Longão de 16 km a pace 5:23/km / FC 160** — sessão mais bem executada da semana. FC ≈ 90% LTHR, dentro de faixa de meia-tempo, e pace abaixo das projeções de maratona. Foi o treino "rainha" e justifica a recuperação rápida de TSB depois.
- **Elevação +56%** vs semana anterior (mas em valor absoluto ainda modesto).
- **Recuperação de forma**: TSB saltou de −22 para −6 sem perder CTL.

**Pra baixo** ⚠️
- **Sumiu o estímulo de qualidade**: Z3 e Z5 zerados. Na semana anterior houve a corrida de **02/05 (12 km, FC 174.7)** — claramente um tempo/intervalado forte que essa semana não teve equivalente.
- **Uma corrida a menos** (3 vs 4) e tempo total caiu 26% — boa parte por uma sessão de musculação mais curta também.
- **1 dia com ACWR > 1.3** sinalizado (provavelmente 09/05, dia do longão, quando ATL deu pulo). Nada crítico — voltou pra 1.08.

## Síntese

Semana de **descarga relativa bem calibrada**: você reduziu carga (−24% TRIMP) sem desmontar a base (CTL −1.3) e ainda entregou um longão sólido. O contrassenso é que sumiu o trabalho de qualidade — pra maratona em julho, é preciso pelo menos um intervalado/tempo por semana, e a W18 ficou só com Z2/longão.

A combinação "TSB recuperado + intervalado em falta" é exatamente o cenário em que faz sentido a próxima semana abrir com uma sessão de qualidade (terça, depois do regenerativo de segunda).

---

**Tools MCP usadas:** `compare_periods`, `get_weekly_breakdown`, `generate_period_narrative`, `list_activities`.
