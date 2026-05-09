# Métricas de Treinamento

Referência das métricas calculadas pelo sistema, organizadas por categoria.

---

## Carga de Treino por Sessão

### TRIMP — Training Impulse

Carga cardiovascular bruta de uma sessão. Multiplica duração × intensidade relativa da FC. Serve como "peso" absoluto do treino para o sistema cardiovascular.

### hrTSS — Heart Rate Training Stress Score

Versão normalizada do TRIMP. Compara o esforço da sessão com "1 hora completa no limiar anaeróbico (LTHR)" = 100 pontos. Permite somar e comparar cargas entre sessões de tipos e durações diferentes.

> Regra prática: uma hora fácil gera ~40–50 hrTSS; uma hora no limiar gera ~100; uma corrida intensa de 90 min pode passar de 130.

---

## Eficiência e Controle Aeróbico

### EF — Eficiência Aeróbica

Velocidade produzida por batimento cardíaco, calculada como:

```
EF = NGP (m/s) ÷ FC média (bpm)
```

Quanto mais alto, mais econômico é o esforço aeróbico. Sobe progressivamente com o condicionamento e é uma das melhores métricas de evolução a longo prazo.

> NGP (Normalized Graded Pace) ajusta a velocidade pela inclinação do terreno, tornando corridas em terrenos variados comparáveis.

### Decoupling

Compara a EF da primeira metade com a da segunda metade de uma sessão:

```
Decoupling = (EF_1a_metade - EF_2a_metade) / EF_1a_metade × 100
```

Indica o quanto a FC "derivou" (cardiac drift) em relação à velocidade ao longo do tempo.

| Valor | Interpretação |
|-------|---------------|
| < 5% | Esforço aerobicamente controlado — boa base |
| 5–8% | Drift moderado — calor, fadiga ou pace acima do limiar aeróbico |
| > 8% | Drift alto — esforço além da capacidade aeróbica atual |

---

## Forma e Condição Física (PMC)

O modelo PMC (*Performance Management Chart*) usa três indicadores derivados do histórico de hrTSS para representar fitness, fadiga e forma.

### CTL — Chronic Training Load (Fitness)

Média exponencial ponderada dos últimos **42 dias** de TSS. Representa a base aeróbica construída com consistência ao longo do tempo.

- Sobe lentamente com treino regular
- Cai lentamente durante descanso prolongado
- Meta para maratona: 85–100+

### ATL — Acute Training Load (Fadiga)

Média exponencial ponderada dos últimos **7 dias** de TSS. Reflete a fadiga acumulada recentemente.

- Sobe rapidamente após treinos pesados
- Cai rapidamente após descanso (2–3 dias)

### TSB — Training Stress Balance (Forma)

```
TSB = CTL - ATL
```

O equilíbrio entre fitness e fadiga. Indica se você está em condições de competir ou treinar no nível máximo.

| TSB | Status | Interpretação |
|-----|--------|---------------|
| < −20 | Fatigued | Sobrecarga — risco de overtraining |
| −10 a +5 | Productive | Zona ideal de treino e assimilação |
| +5 a +15 | Fresh | Ótimo para competir |
| > +15 | Detraining | Fresco demais — fitness pode estar caindo |

### ACWR — Acute:Chronic Workload Ratio

```
ACWR = ATL ÷ CTL
```

Mede se a carga recente está proporcional à base construída. Principal indicador de risco de lesão por aumento abrupto de volume ou intensidade.

| ACWR | Zona | Interpretação |
|------|------|---------------|
| < 0,8 | Subestimulado | Volume abaixo do potencial |
| 0,8–1,3 | Segura | Progressão adequada |
| 1,3–1,5 | Atenção | Aumento acelerado |
| > 1,5 | Risco | Alta probabilidade de lesão |

### Status de Forma

Interpretação qualitativa do TSB atual:

| Status | Condição |
|--------|----------|
| **Fatigued** | TSB muito negativo — priorizar recuperação |
| **Productive** | Zona de treino e absorção de carga |
| **Fresh** | Pronto para competir ou treino de qualidade |
| **Detraining** | Descanso excessivo — retomar progressão |

---

## Predição de Tempos de Prova

### Riegel

Fórmula clássica de extrapolação proposta por Peter Riegel (1981):

```
T_alvo = T_conhecido × (D_alvo / D_conhecida) ^ k
```

Com `k = 1.06` para corredores treinados em distâncias até a maratona. Tende a ser **otimista** para projeções muito longas (ex: maratona a partir de 5K).

### VDOT (Daniels)

Modelo de Jack Daniels que estima o VO2máx-equivalente a partir de qualquer corrida. Combina duas equações:

1. **Demanda aeróbica** em função da velocidade
2. **Fração sustentável de VO2máx** em função da duração

A partir do VDOT inferido, projeta tempos em qualquer distância. Em geral **mais conservador** que Riegel para distâncias longas — tende a ser mais realista para projeções de maratona a partir de meias maratonas.

### Quando usar cada um?

| Situação | Modelo recomendado |
|----------|---------------------|
| Projeção curta (5K → 10K) | Riegel ou VDOT (resultados similares) |
| Projeção longa (meia → maratona) | VDOT (mais conservador e realista) |
| Comparação entre atletas | VDOT (escala absoluta de VO2máx) |
| Cálculo rápido manual | Riegel (fórmula simples) |

A tool `predict_race_time` sempre retorna ambos os modelos para que você possa comparar.

---

## Referências dos Parâmetros do Atleta

Os cálculos de zona e intensidade usam os parâmetros definidos no `CLAUDE.md`:

| Parâmetro | Valor |
|-----------|-------|
| FCmáx | 201 bpm |
| LTHR | 177 bpm |
| FC repouso | 50 bpm |
