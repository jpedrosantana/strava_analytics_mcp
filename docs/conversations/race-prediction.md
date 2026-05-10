# Predição de prova e progresso da preparação

Conversa real com o Claude usando o MCP `strava-analytics`. Data: 09/05/2026.

---

> **Estou me preparando para uma maratona em julho. Pega meu melhor 21K do histórico, projeta o tempo de maratona usando Riegel e VDOT, e me diz se minha tendência de eficiência aeróbica dos últimos meses sustenta esse pace.**

## Melhor 21K do histórico

**Mizuno Athenas Run Faster — 15/03/2026** (8 semanas atrás)

- 21.22 km em **1:40:11** (pace 4:43/km)
- avgHR 175 (≈99% LTHR), maxHR 189
- **Decoupling −1.48%** (excellent — FC/pace mantiveram paridade até o fim)
- **EF na prova: 0.0202**

## Projeções de maratona

**Riegel** (T₂ = T₁ × (D₂/D₁)^1.06):

- 6011s × (42.195/21.224)^1.06 = 6011 × 2.0716 ≈ **12.453s → 3:27:33** (pace **4:55/km**)

**VDOT** (Daniels):

- HM 1:40:11 ≈ **VDOT 44–45**
- Marathon equivalente: **3:21:38–3:25:46** (pace 4:46–4:53/km)

**Faixa realista para 1ª maratona: 3:25–3:35 (4:52–5:05/km)**

Riegel/VDOT assumem endurance perfeitamente escalável. Para primeira maratona, é prudente adicionar **+5 a +10 min** sobre Riegel se a base de longões >28 km não estiver consolidada — e esse é o seu caso (mais sobre isso abaixo).

## EF sustenta esse pace?

**EF mensal (treinos):**

| Mês | EF | Contexto |
|---|---|---|
| Nov 2025 | 0.0193 | Mês da Brasília 21K |
| Dez 2025 | 0.0181 | — |
| **Jan 2026** | **0.0180** | Canelite |
| Fev 2026 | 0.0187 | — |
| Mar 2026 | 0.0192 | Mês do PR |
| Abr 2026 | 0.0187 | CTL alto (carga) |
| Mai 2026 | 0.0192 | (4 atividades) |

A flag "declining" do tool é miopia recente — olhando 6 meses, **EF está estável em ~0.019**, com a queda de jan totalmente recuperada.

**EF necessário para sustentar pace projetado (FC alvo Z3, 168–172):**

| Pace alvo | Velocidade | EF necessário (HR 170) |
|---|---|---|
| 4:50/km | 3.45 m/s | **0.0203** |
| 4:55/km | 3.39 m/s | **0.0199** |
| 5:00/km | 3.33 m/s | **0.0196** |

**Veredicto sobre EF:** Atualmente em treino você roda em **0.0192**. Em prova você comprime para **0.0202** (visto na PR). Ou seja:

- Pace 4:55/km (Riegel) está **no limite** do que seu motor sustenta hoje — viável **se em modo prova** + carb loading + ambiente fresco.
- Pace 4:50/km (VDOT) exige um EF que você **ainda não demonstrou** em distância > 21K.
- Pace 5:00/km é a zona segura — sustentável com EF atual mesmo descontando fadiga do segundo tempo.

## Endurance específico — o ponto fraco

| Longão recente | Distância | Decoupling | Grade |
|---|---|---|---|
| 28/03 | 18.0 km | +11.5% | needs_work |
| 12/04 | **23.0 km** | −14.4% | excellent |
| 18/04 | 16.25 km | +5.2% | adequate |
| 09/05 | 16.0 km | +3.3% | excellent |

O único longão >21 km nos últimos 3 meses foi o de **23 km em 12/04**, e foi excelente. Mas para maratona, você precisa de **2–3 longões na faixa de 28–32 km** (com últimos km em pace de prova) para validar empiricamente que o motor não desmonta após ~25 km. Isso é o que falta no histórico.

## Resposta direta

- **Pace alvo realista: 4:55–5:00/km (3:27–3:31 finish)** — Riegel é o teto, não o piso.
- **EF sustenta 4:55? Sim, no limite.** Sustenta 5:00 com folga. Não sustenta 4:50 sem upside extra que ainda não está no histórico.
- **Decoupling em 16–23 km é ótimo**, mas faltam longões longos para validar endurance maratona.
- **Plano para fechar o gap (8 semanas até julho):**
  1. Reintroduzir 1 sessão de qualidade/semana (limiar @ 4:35–4:45 ou MP @ 4:55)
  2. Progressão de longões: 25 → 28 → 30 → 32 km (com últimos 6–8 km em pace de prova)
  3. Subir CTL para ~75–78 antes do tapper de 2 semanas
  4. Usar a prova de 21K e a de 25K como rehearsal de pace e fueling

Se executar o bloco específico, **3:25–3:30 é palpável**. Sem ele, **3:30–3:40** é mais honesto.

---

**Tools MCP usadas:** `find_personal_records`, `search_activities`, `get_aerobic_efficiency_trend`, `get_decoupling_trend`, `get_activity`.
