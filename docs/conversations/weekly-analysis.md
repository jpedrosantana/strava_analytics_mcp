# Análise da semana

Conversa real com o Claude usando o MCP `strava-analytics`. Data: 09/05/2026.

---

> **Como foi minha semana de treino comparada à semana anterior? Quero ver volume total, distribuição por zona, principais sessões e se algo se destacou — pra cima ou pra baixo.**

## Semana atual (04–10/05, W18) vs Semana anterior (27/04–03/05, W17)

Dados via `compare_periods` + detalhes por atividade (LTHR=177, zonas estimadas pela avg HR).

### Volume agregado

| Métrica | W18 (atual) | W17 (anterior) | Δ |
|---|---|---|---|
| Atividades | 5 | 8 | **−37%** |
| Corridas (km) | 38.6 | 42.3 | −8.7% |
| Tempo total (h) | 5.6 | 10.6 | **−47%** |
| TRIMP | 404 | 694 | **−42%** |
| Elev. acum. (m) | 100 | 64 | +56% |

A queda no tempo/TRIMP **não veio da corrida** (volume quase igual) — veio da musculação: você passou de 4 sessões (incluindo duas funcionais longas: 122min e 147min) para 2 sessões curtas (60min cada).

### Distribuição por zona — corridas

**W18 (atual)** — 3 corridas, todas em base aeróbica:
- 04/05 — 10.59 km @ 6:00/km, avgHR 145 → **Z2** (rodagem leve, perfeita)
- 06/05 — 12.01 km @ 5:26/km, avgHR 147 → **Z2/Z3 baixa**
- 09/05 — 16.02 km @ 5:23/km, avgHR 160, maxHR 181 → **Z3** (longão sólido)

**W17 (anterior)** — 4 corridas, com 1 sessão de qualidade:
- 27/04 — 10.02 km @ 5:30/km, avgHR 150 → Z3 baixa
- 29/04 — 10.21 km @ 5:53/km, avgHR 145 → Z2/Z3
- 30/04 — 10.04 km @ 5:58/km, avgHR 148 (esteira) → Z3 baixa
- **02/05 — 12.03 km @ 5:30/km, avgHR 174, maxHR 192 → Z4 (limiar)** ← sessão de qualidade

### Destaques

**Pra cima**
- **Longão de hoje (16 km @ 5:23, FC 160)** — mais longo desde a corrida de 23 km em 12/04, e em ritmo controlado. Bom estímulo aeróbico pra base da maratona.
- **04/05** — rodagem regenerativa textbook (6:00/km @ FC 145). Dose certa.

**Pra baixo**
- **Sumiu a sessão de qualidade na corrida.** Semana anterior teve um Z4 forte (02/05). Esta semana foi 100% Z2/Z3 — para preparação de maratona em julho, esperado ter ao menos 1 estímulo de limiar/intervalado por semana.
- **Musculação caiu de 4→2 sessões**, e as duas foram curtas/leves (avgHR ~105). Foge do padrão habitual (2-3 funcional + 1 musc). Se foi planejado, ok; se não, vale resgatar.
- Nenhum *two-a-day* esta semana (W17 teve 3).

### Leitura curta

A semana foi **mais leve em carga total**, mas **a corrida em si manteve volume**. O que faltou foi intensidade na corrida e regularidade na força. Se a próxima semana tem prova ou bloco-chave, faz sentido; se não, sugiro reintroduzir 1 sessão de limiar/fartlek e fechar a base de força.

---

**Tools MCP usadas:** `compare_periods`, `get_weekly_breakdown`, `list_activities`, `get_activity` (×7).
