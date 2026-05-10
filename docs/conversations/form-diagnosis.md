# Diagnóstico de forma e prontidão

Conversa real com o Claude usando o MCP `strava-analytics`. Data: 10/05/2026.

---

> **Qual minha forma atual e o risco de lesão considerando a carga das últimas semanas? Estou pensando em fazer um treino intervalado amanhã, faz sentido ou seria melhor um treino regenerativo?**

## Forma atual (10/05/2026)

| Métrica | Valor | Leitura |
|---|---|---|
| **CTL** (fitness, 42d) | 70.9 | Maior nível das últimas 6 semanas — base subindo |
| **ATL** (fadiga, 7d) | 76.8 | Ainda elevada |
| **TSB** (forma) | **−5.9** | "Productive" — levemente fatigado, mas zona de adaptação |
| **ACWR** | 1.08 | Sweet zone (0.8–1.3) |

## Risco de lesão: **BAIXO** (score 0)

- Sem fatores de risco ativos
- Volume da semana: **38.6 km** vs média 4 sem anteriores 34.8 km → spike de apenas 1.11x (saudável)
- EF recente (0.0195) levemente acima do baseline (0.0189) — eficiência aeróbica preservada

## Contexto das últimas semanas

- **20–22/04**: pico de fadiga (TSB chegou a **−29.6**) — semana muito pesada
- **01/05**: dia de descanso → recuperação parcial
- **09/05** (ontem): longão de 16 km (TSS 130)
- **10/05** (hoje): TSS 132 sem GPS (musculação/funcional)
- TSB veio de −22 (04/05) para −5.9 hoje — recuperação clara, mas ATL ainda em 76.8

## Recomendação para amanhã

**Regenerativo é a escolha mais sensata.** Razões objetivas:

1. **ATL ainda em 76.8** com longão de 16 km nas últimas 24h + carga forte hoje. Intervalado de qualidade pede pernas frescas — você pegaria o treino "cansado" e o estímulo neuromuscular ficaria abaixo do potencial.
2. **TSB −5.9 e caindo de novo** (subiu hoje por causa do TSS 132). Para puxar bom intervalado, ideal é TSB entre −3 e +5 com ATL baixando, não subindo.
3. **Maratona em julho**: você está construindo CTL (70.9, máxima recente). Não vale arriscar qualidade de uma sessão chave por insistência no calendário.

## Sugestão de microciclo

| Dia | Recomendação |
|---|---|
| **Seg 11/05** | Regenerativo 6–8 km Z1–Z2 (PA leve, FC < 145) |
| **Ter 12/05** | Intervalado com pernas restauradas — TSB deve estar perto de 0 |

Se quiser fazer algo amanhã que não seja totalmente passivo mas também não comprometa a terça, o regenerativo zona 1 cumpre exatamente esse papel.

---

**Tools MCP usadas:** `get_current_form`, `get_injury_risk_assessment`, `get_load_history`.
