# Diagnóstico de forma e prontidão

Conversa real com o Claude usando o MCP `strava-analytics`. Data: 09/05/2026.

---

> **Qual minha forma atual e o risco de lesão considerando a carga das últimas semanas? Estou pensando em puxar forte amanhã, faz sentido ou seria melhor um treino regenerativo?**

## Forma atual (09/05)

| Métrica | Valor | Leitura |
|---|---|---|
| CTL (fitness) | **69.5** | Alta — subiu de 47 em fev p/ 69 (ganho consistente) |
| ATL (fadiga) | 68.6 | Despencou de 96.6 (01/05) → 68.6 hoje |
| **TSB (forma)** | **+0.9** | "Productive" — saiu do vermelho |
| ACWR | 0.99 | Sweet spot (0.8–1.3) |
| Risk score | **0 / low** | Sem fatores de risco |
| Volume spike | 1.05 | Estável (38.6km vs média 4 sem 36.9) |

**EF mediano** recente (0.0194) levemente acima do baseline (0.0190) — sinal de que o motor aeróbico está respondendo, não fadigado.

## A história das últimas semanas

Você passou por um bloco de **carga alta sustentada** entre 13/04 e 04/05:
- TSB ficou abaixo de −15 por **17 dias seguidos**
- Pico de fadiga em 01/05 com ATL=96.6 e TSB=−25 (zona de alarme)
- Atravessou o pico sem lesão, e a W18 funcionou como deload natural — ATL caiu de 96.6 → 68.6 em 8 dias

Hoje você está pela primeira vez em maio com TSB positivo. Mas — atenção — esse +0.9 ainda **não computou o longão de 16 km de hoje** (130 TSS). Amanhã, com o longão entrando no ATL, TSB volta para ~−10.

## Puxar forte amanhã faz sentido?

**Não. Recomendo regenerativo ou descanso.**

Razões:

1. **Você acabou de fazer 86 min em Z3 hoje** — microdano muscular e glicogênio depletado. Isso não aparece no TSB ainda (entra na conta amanhã).
2. **TSB +0.9 é "productive", não "fresh"**. Para puxar forte com janela ótima de adaptação, idealmente quer TSB entre −5 e +5 *após* contabilizada a sessão anterior. Empilhar sábado-pesado + domingo-pesado vai te jogar de volta para TSB ~−15.
3. **Histórico em janeiro:** canelite com padrão semelhante de empilhamento. ACWR está ok agora, mas a lesão veio de carga consecutiva sem janela aeróbica/recuperação adequada.
4. **Calendário:** sua maratona é em julho, com prova de 21 km e 25 km antes. Você tem 8+ semanas — não há pressa de meter qualidade dois dias seguidos.

## Sugestão para os próximos dias

| Dia | Recomendação |
|---|---|
| **Dom 10/05** | **Regenerativo 5–7 km Z1/Z2** (FC <140, pace ~6:00–6:30) **ou** descanso |
| Seg 11/05 | Musculação leve / descanso |
| **Ter 12/05** | **Sessão de qualidade** (intervalado/tempo) — TSB já confortavelmente positivo, janela ótima |
| Qua 13/05 | Rodagem fácil |
| Sáb 17/05 | Longão progressivo |

Se você está **muito** querendo um estímulo intenso, segunda também serve — um dia entre longão e qualidade ainda é ok. Mas terça é a janela boa.

A boa notícia: você está em **excelente forma** (CTL 69 é seu maior valor de 2026), saiu do bloco de fadiga inteiro sem lesão e o motor está respondendo. Não jogue isso fora amanhã.

---

**Tools MCP usadas:** `get_current_form`, `get_injury_risk_assessment`, `get_load_history`.
