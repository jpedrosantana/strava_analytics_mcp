# Strava Analytics MCP

> Plataforma pessoal de análise esportiva via Model Context Protocol. Sincroniza histórico do Strava, aplica modelos de ciência do esporte e expõe insights via MCP server consumível por Claude Desktop / Claude Code / qualquer cliente MCP compatível.

---

## 1. Contexto e motivação

O Strava entrega métricas brutas (distância, pace, FC) e algumas análises proprietárias caixa-preta (Suffer Score, Fitness/Freshness no Premium). Falta:

- Modelos de carga de treino transparentes e configuráveis (TSS/TRIMP, CTL/ATL/TSB)
- Análises de eficiência aeróbica e decoupling cardíaco
- Cruzamento com variáveis externas (clima, sono, etc.)
- Capacidade preditiva (tempos de prova, risco de lesão, plateaus)
- Interface conversacional para explorar os dados

Este projeto preenche essa lacuna como um **MCP server** que:

1. Mantém um cache local SQLite com histórico completo do atleta
2. Sincroniza incrementalmente com a Strava API
3. Expõe tools analíticas para LLMs (Claude, etc.)
4. Aplica modelos validados de sports science

**Caso de uso primário:** atleta amador conversa com Claude no formato "como foi minha última semana?" / "estou pronto para correr uma meia em 8 semanas?" / "minha forma está caindo, o que mudou?" e recebe respostas baseadas em todos os seus dados, não apenas no que cabe num resumo manual.

**Perfil do atleta de referência:** corredor amador entrando em ciclo de maratona, com ~1.5 anos de histórico no Strava, 7 meias-maratonas completadas e provas menores. Os exemplos e prioridades do projeto refletem esse contexto.

---

## 2. Decisões de arquitetura (com justificativas)

### 2.1 Stack

- **Linguagem:** Python 3.11+
- **Razão:** SDK MCP maduro (`mcp` no PyPI), ecossistema de dados (pandas, numpy, scipy, scikit-learn) muito superior ao TS para esse domínio
- **Framework MCP:** `FastMCP` (parte do SDK oficial — ergonomia melhor que o servidor low-level)
- **Banco:** SQLite via `sqlite3` stdlib + `sqlalchemy` para queries complexas
- **Razão:** zero infra, single-file, performance excelente para o volume esperado (até ~10k atividades), permite distribuir o "banco" como um arquivo se necessário
- **HTTP client:** `httpx` (async-ready, mais moderno que requests)
- **Configuração:** `pydantic-settings` lendo `.env`
- **Testes:** `pytest` + `pytest-asyncio`
- **Lint/format:** `ruff` (replace black + isort + flake8)
- **Gerenciador de pacotes:** `uv` (rápido, moderno, padrão emergente)

### 2.2 Arquitetura de dados: cache local + sync periódico + fetch sob demanda

```
┌─────────────────────────────────────────────────┐
│  SQLite local (histórico completo)              │
│  ↑                                               │
│  └── sync.py: backfill inicial + sync incremental│
│       (cron diário ou GitHub Actions)            │
└─────────────────────────────────────────────────┘
                  ↑
                  │ leitura padrão (rápida)
                  │
            ┌─────┴─────┐
            │ MCP server│
            └─────┬─────┘
                  │ fallback: refresh sob demanda
                  ↓
        ┌──────────────────┐
        │  Strava API      │
        └──────────────────┘
```

**Razão:** análises históricas profundas (12+ meses) ficam inviáveis se cada chamada do MCP precisar paginar a API (rate limit de 200 req/15min, 2000/dia, latência alta). Cache resolve isso. Mas perder dados de uma atividade recém-postada é frustrante — daí o fallback explícito via tool `sync_now()`.

### 2.3 Separação de responsabilidades

```
strava_mcp/
├── strava_client/      # Camada de API: OAuth, fetch, rate limiting
├── db/                 # Schema, migrations, repositories
├── sync/               # Backfill e sync incremental
├── analytics/          # Modelos de sports science (puros, testáveis)
│   ├── load.py         # TSS, TRIMP, CTL/ATL/TSB
│   ├── efficiency.py   # Decoupling, EF, aerobic decoupling
│   ├── zones.py        # Cálculo de zonas a partir de dados
│   ├── predictions.py  # Riegel, VDOT, modelos próprios
│   └── weather.py      # Integração Open-Meteo + correlações
├── mcp_server/         # FastMCP server expondo tools
└── cli/                # Comandos: setup, sync, doctor
```

**Razão:** o módulo `analytics` deve ser puramente funcional (input: DataFrames, output: dicts/DataFrames). Isso o torna reusável fora do MCP (notebook Jupyter, CLI, dbt via Python models, etc.) e trivialmente testável.

### 2.4 Filosofia de tools MCP

Tools devem ser **semanticamente úteis para um LLM**, não meros wrappers de queries SQL. Princípios:

- **Granularidade média**: nem `execute_sql(query)` (genérico demais, LLM erra), nem `get_decoupling_for_long_runs_in_zone_2()` (específico demais)
- **Sempre retornar contexto suficiente**: junto com o número, retornar período analisado, n de atividades, possíveis caveats
- **Composabilidade**: tools menores que o LLM combina, em vez de tools monolíticas
- **Determinismo**: mesma entrada → mesma saída. Cálculos não-determinísticos (ML com aleatoriedade) devem fixar seed

---

## 3. Modelos analíticos (especificação)

Seção que serve de referência canônica para implementação. Cada subseção descreve **o que calcular**, **como** e **caveats**.

### 3.1 Zonas de FC personalizadas

Strava usa zonas baseadas em FCmáx estimada (220-idade), notoriamente imprecisa. Implementar:

**Estimativa de FC de limiar (LTHR):**
- Estratégia 1: pegar FC média dos últimos 30min de qualquer corrida ≥40min em ritmo "tempo" (definido como pace 5-15s/km mais lento que 10K PR)
- Estratégia 2: percentil 95 da FC em corridas tempo (mais robusto)
- Usar mediana das estimativas dos últimos 90 dias

**Zonas (Friel, baseadas em LTHR):**
- Z1: < 81% LTHR
- Z2: 81-89%
- Z3: 90-93%
- Z4: 94-99%
- Z5a: 100-102%
- Z5b: 103-106%
- Z5c: > 106%

**FCmáx real:**
- Percentil 99.5 da FC observada nos últimos 12 meses (filtrando spikes inválidos: jumps de >40bpm em 1s)

### 3.2 Carga de treino

**TRIMP (Banister)** — preferido para corrida sem potenciômetro:

```
TRIMP = duração_min × ΔHR_ratio × 0.64 × e^(1.92 × ΔHR_ratio)   [homens]
TRIMP = duração_min × ΔHR_ratio × 0.86 × e^(1.67 × ΔHR_ratio)   [mulheres]

onde ΔHR_ratio = (FC_média - FC_repouso) / (FCmáx - FC_repouso)
```

FC_repouso: pegar percentil 5 da FC em atividades muito leves (Z1) ou permitir override em config.

**hrTSS (TrainingPeaks)** — para quando há dados de FC mas não potência:

```
hrTSS = (duração_segundos × IF² × 100) / 3600
IF = NP_HR / LTHR  (aproximado por FC_média / LTHR para esforços contínuos)
```

**rTSS (running TSS, Daniels-based)** — quando há GPS confiável:

```
rTSS = (duração_segundos × NGP_IF² × 100) / 3600
NGP = pace ajustado por elevação (Normalized Graded Pace)
NGP_IF = NGP / threshold_pace
```

**CTL / ATL / TSB:**

```
CTL_hoje = CTL_ontem + (TSS_hoje - CTL_ontem) / 42
ATL_hoje = ATL_ontem + (TSS_hoje - ATL_ontem) / 7
TSB_hoje = CTL_ontem - ATL_ontem
```

Inicialização: CTL[0] = ATL[0] = média do TSS dos primeiros 14 dias do dataset.

**Interpretação de TSB:**
- TSB > +25: muito descansado (possível detraining se sustentado)
- +5 a +25: forma de prova
- -10 a +5: produtivo, treinando bem
- -30 a -10: carregado, treinando duro
- < -30: risco elevado, considerar deload

### 3.3 Eficiência aeróbica e decoupling

**Aerobic Efficiency (EF):**
```
EF = NGP_metros_por_segundo / FC_média
```
Tracker mensal: subir = ganhando fitness aeróbico. Cair em treinos fáceis = fadiga ou perda de base.

**Aerobic Decoupling (Pa:HR):**
Para corridas longas (≥60min) em ritmo aeróbico (Z1-Z2):
```
1. Dividir o treino em duas metades (excluindo aquecimento de 10min)
2. Calcular EF em cada metade
3. Decoupling % = (EF_1ª_metade - EF_2ª_metade) / EF_1ª_metade × 100
```
- < 5%: excelente base aeróbica
- 5-10%: adequado
- > 10%: base aeróbica deficiente, priorizar Z2

### 3.4 Predição de tempos de prova

**Riegel (clássica):**
```
T2 = T1 × (D2/D1)^1.06
```
Boa para extrapolar dentro de fator 2x (e.g., 5K → 10K).

**VDOT (Daniels):** tabelas/fórmulas que estimam VO2máx equivalente a partir de qualquer prova e projetam outras distâncias. Implementar como lookup table interpolada.

**Modelo próprio (v0.3):**
Treinar regressão (gradient boosting) com features dos 60 dias anteriores à prova:
- volume semanal médio, max, mediana
- distribuição por zona
- número de treinos > limiar
- TSB no dia da prova
- CTL na semana da prova
- consistência (desvio padrão de volume semanal)

Target: tempo na prova. Treinar no histórico do próprio atleta + modelos populacionais como prior bayesiano.

### 3.5 Análise de clima

API: Open-Meteo Historical Weather (gratuita, sem chave). Para cada atividade:
- Temperatura média durante o treino
- Umidade relativa
- Velocidade do vento
- Precipitação
- Heat index calculado

Análises:
- Regressão pace × temperatura (controlando por TSB e tipo de treino)
- "Pace adjustment factor" por faixa de temperatura
- Identificação de PR conditions (em quais condições você performa no topo)

### 3.6 Detecção de risco de lesão

Regra clássica do "10% rule" + métricas de carga aguda:crônica:

**Acute:Chronic Workload Ratio (ACWR):**
```
ACWR = ATL / CTL
```
- ACWR > 1.5: risco elevado (pico de carga)
- ACWR < 0.8: undertraining
- 0.8-1.3: zona "doce"

**Spike de volume:**
```
spike = volume_semana_atual / mean(volume_4_semanas_anteriores)
```
spike > 1.5 = aumento abrupto, risco.

**Combinação para "injury risk score":** ACWR + spike + decoupling crescente em treinos fáceis + queda de eficiência aeróbica → score 0-100.

### 3.7 Detecção de anomalias

Por tipo de treino, treinar modelo de "performance esperada" (regressão simples: pace ~ distância + elevação + temperatura + TSB + CTL). Atividades com resíduo > 2 desvios padrão = anomalias. Categorizar:
- Outliers positivos: condições especiais ou breakthrough
- Outliers negativos: doença, fadiga oculta, problemas de execução

### 3.8 Narrativa generativa

Tool `generate_period_narrative(start_date, end_date)` que retorna **dados estruturados** (não prosa pronta — deixar a prosa para o LLM):
- Marcos do período (PRs, treinos-chave, semanas de pico, deloads)
- Tendências de CTL, EF, pace médio
- Padrões detectados (gaps, mudanças de rotina, sazonalidade)
- Comparação com período anterior de mesma duração

O LLM consumidor (Claude) gera a prosa a partir disso.

---

## 4. Schema do banco

```sql
-- Atividades resumidas (uma linha por atividade)
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,                  -- Strava activity ID
    name TEXT NOT NULL,
    sport_type TEXT NOT NULL,                -- Run, Ride, etc
    workout_type INTEGER,                    -- 1 = race; útil para identificação de provas
    start_date_utc TIMESTAMP NOT NULL,
    start_date_local TIMESTAMP NOT NULL,
    timezone TEXT,
    distance_m REAL,
    moving_time_s INTEGER,
    elapsed_time_s INTEGER,
    elevation_gain_m REAL,
    average_speed_mps REAL,
    max_speed_mps REAL,
    average_heartrate REAL,
    max_heartrate REAL,
    average_cadence REAL,
    average_watts REAL,
    weighted_average_watts REAL,
    kilojoules REAL,
    suffer_score INTEGER,
    has_heartrate BOOLEAN,
    has_powermeter BOOLEAN,
    trainer BOOLEAN,
    commute BOOLEAN,
    manual BOOLEAN,
    start_latlng_lat REAL,
    start_latlng_lng REAL,
    end_latlng_lat REAL,
    end_latlng_lng REAL,
    map_polyline TEXT,                       -- summary polyline encoded
    raw_json TEXT NOT NULL,                  -- payload completo da API
    synced_at TIMESTAMP NOT NULL,
    streams_synced_at TIMESTAMP              -- NULL se streams ainda não baixados
);

CREATE INDEX idx_activities_start_date ON activities(start_date_utc);
CREATE INDEX idx_activities_sport ON activities(sport_type);
CREATE INDEX idx_activities_workout_type ON activities(workout_type);

-- Streams (séries temporais) por atividade — armazenadas como JSON comprimido
CREATE TABLE activity_streams (
    activity_id INTEGER NOT NULL,
    stream_type TEXT NOT NULL,               -- 'time', 'heartrate', 'velocity_smooth', 'altitude', 'cadence', 'watts', 'latlng'
    data BLOB NOT NULL,                      -- gzip(json_encoded_array)
    resolution TEXT NOT NULL,                -- 'high', 'medium', 'low'
    PRIMARY KEY (activity_id, stream_type),
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);

-- Métricas calculadas (cache de análises caras)
CREATE TABLE activity_metrics (
    activity_id INTEGER PRIMARY KEY,
    trimp REAL,
    hr_tss REAL,
    r_tss REAL,
    aerobic_efficiency REAL,
    decoupling_pct REAL,
    ngp_mps REAL,                            -- normalized graded pace
    intensity_factor REAL,
    z1_seconds INTEGER,
    z2_seconds INTEGER,
    z3_seconds INTEGER,
    z4_seconds INTEGER,
    z5_seconds INTEGER,
    weather_temp_c REAL,
    weather_humidity_pct REAL,
    weather_wind_mps REAL,
    weather_precipitation_mm REAL,
    computed_at TIMESTAMP NOT NULL,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);

-- Métricas diárias (CTL/ATL/TSB)
CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,
    daily_tss REAL NOT NULL DEFAULT 0,
    ctl REAL NOT NULL,
    atl REAL NOT NULL,
    tsb REAL NOT NULL,
    n_activities INTEGER NOT NULL DEFAULT 0,
    total_distance_m REAL NOT NULL DEFAULT 0,
    total_moving_time_s INTEGER NOT NULL DEFAULT 0
);

-- Configurações do atleta
CREATE TABLE athlete_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
-- chaves: lthr, hr_max, hr_rest, threshold_pace_mps, weight_kg, sex, birth_year

-- Estado de sincronização
CREATE TABLE sync_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
-- chaves: last_full_sync_at, last_incremental_sync_at, oldest_synced_activity_date

-- Tokens OAuth (criptografados em produção; em local pode ser texto)
CREATE TABLE oauth_tokens (
    id INTEGER PRIMARY KEY DEFAULT 1,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    athlete_id INTEGER,
    CHECK (id = 1)                           -- single-row table
);
```

---

## 5. Tools do MCP server

Cada tool listada com nome, assinatura, descrição (que vira a docstring que o LLM lê) e exemplo de retorno.

### 5.1 Tools de leitura básica

```python
@mcp.tool()
def list_activities(
    days_back: int = 30,
    sport_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Lista atividades dos últimos N dias, opcionalmente filtradas por esporte.
    
    Retorna campos resumidos: id, name, date, distance_km, duration_min,
    avg_pace_per_km, avg_hr, elevation_m, sport_type.
    """

@mcp.tool()
def get_activity(activity_id: int, include_streams: bool = False) -> dict:
    """Detalhes completos de uma atividade. Se include_streams=True, inclui
    séries temporais (FC, pace, elevação ponto a ponto)."""

@mcp.tool()
def search_activities(
    name_contains: str | None = None,
    min_distance_km: float | None = None,
    max_distance_km: float | None = None,
    after_date: str | None = None,    # ISO date
    before_date: str | None = None,
    sport_type: str | None = None,
) -> list[dict]:
    """Busca avançada de atividades por filtros combinados."""
```

### 5.2 Tools de estatísticas agregadas

```python
@mcp.tool()
def get_period_stats(
    start_date: str,
    end_date: str,
    sport_type: str | None = None,
) -> dict:
    """Estatísticas agregadas de um período: total de distância, tempo,
    elevação, número de atividades, distribuição por zona, TSS total,
    pace médio (ponderado por distância), FC média (ponderada por tempo)."""

@mcp.tool()
def compare_periods(
    period_a_start: str, period_a_end: str,
    period_b_start: str, period_b_end: str,
    sport_type: str | None = None,
) -> dict:
    """Comparação lado-a-lado entre dois períodos. Retorna deltas absolutos
    e percentuais para todas as métricas relevantes."""

@mcp.tool()
def get_weekly_breakdown(weeks_back: int = 12) -> list[dict]:
    """Breakdown semana-a-semana das últimas N semanas: volume, TSS,
    distribuição de zonas, número de treinos por tipo."""
```

### 5.3 Tools de carga de treino

```python
@mcp.tool()
def get_current_form() -> dict:
    """Estado atual de forma: CTL, ATL, TSB, ACWR de hoje. Inclui
    interpretação textual ('produtivo', 'sobrecarregado', etc) e
    histórico dos últimos 14 dias para contexto."""

@mcp.tool()
def get_load_history(days_back: int = 90) -> list[dict]:
    """Série histórica diária de CTL, ATL, TSB e TSS. Útil para
    visualizações e análise de tendência."""

@mcp.tool()
def get_injury_risk_assessment() -> dict:
    """Avaliação de risco de lesão baseada em ACWR, spikes de volume,
    decoupling em treinos fáceis, queda de eficiência. Retorna score
    0-100 + breakdown dos fatores contribuintes."""
```

### 5.4 Tools de eficiência

```python
@mcp.tool()
def get_aerobic_efficiency_trend(months_back: int = 6) -> dict:
    """Tendência mensal de eficiência aeróbica em treinos Z1-Z2.
    Retorna série temporal + slope da regressão linear (positivo = melhorando)."""

@mcp.tool()
def get_decoupling_trend(months_back: int = 6) -> list[dict]:
    """Decoupling % de cada corrida longa (≥60min) em ordem cronológica.
    Permite ver se base aeróbica está melhorando."""
```

### 5.5 Tools preditivas

```python
@mcp.tool()
def predict_race_time(distance_km: float, target_date: str | None = None) -> dict:
    """Predição de tempo de prova em distância arbitrária. Combina
    Riegel, VDOT e (se houver dados suficientes) modelo próprio.
    Se target_date fornecida, projeta CTL esperada considerando trajetória atual.
    Retorna estimativa central + intervalo de confiança."""

@mcp.tool()
def find_personal_records() -> dict:
    """PRs em distâncias padrão (1K, 5K, 10K, meia, maratona) baseados
    em melhores efforts dentro de qualquer atividade (não só corridas
    inteiras nessa distância). Inclui data e contexto do PR."""

@mcp.tool()
def what_drives_my_performance() -> dict:
    """Análise de quais features de treino dos últimos 60 dias mais
    correlacionam com bom desempenho. Útil para identificar padrões
    pessoais (você responde mais a volume? a intensidade? a long runs?)."""
```

### 5.6 Tools contextuais

```python
@mcp.tool()
def analyze_weather_impact() -> dict:
    """Análise de como condições climáticas afetam sua performance.
    Retorna pace adjustment por faixa de temperatura, umidade, etc."""

@mcp.tool()
def get_route_clusters(min_activities: int = 3) -> list[dict]:
    """Agrupa atividades por rota (clustering de coordenadas).
    Para cada rota recorrente, retorna evolução de tempo e pace ao longo do histórico."""

@mcp.tool()
def find_anomalies(days_back: int = 90) -> list[dict]:
    """Treinos com performance significativamente acima ou abaixo
    do esperado. Inclui possível causa (fadiga acumulada, clima, etc.)."""
```

### 5.7 Tools de narrativa

```python
@mcp.tool()
def generate_period_narrative(start_date: str, end_date: str) -> dict:
    """Estrutura de dados rica para o LLM gerar prosa sobre o período:
    marcos, tendências, padrões, comparações. Não retorna prosa pronta."""

@mcp.tool()
def diagnose_plateau() -> dict:
    """Se o usuário está estagnado, retorna hipóteses ranqueadas:
    estímulo monótono, volume insuficiente, polarização errada,
    recuperação inadequada, etc., cada uma com evidências dos dados."""
```

### 5.8 Tools de manutenção

```python
@mcp.tool()
def sync_now(full: bool = False) -> dict:
    """Dispara sincronização. full=True faz backfill completo (raro);
    False faz incremental (default). Retorna n de atividades novas."""

@mcp.tool()
def athlete_doctor() -> dict:
    """Diagnóstico de saúde dos dados: completude, qualidade,
    último sync, configs faltando. Útil para debug."""
```

---

## 6. Fluxo OAuth e gestão de tokens

1. **Setup inicial** via CLI: `strava-mcp setup`
   - Pede `CLIENT_ID` e `CLIENT_SECRET` (do app criado em developers.strava.com)
   - Abre navegador automaticamente na URL de autorização com scope `read,activity:read_all`
   - Levanta servidor HTTP local efêmero em `localhost:8765` para capturar o `code` do redirect
   - Troca `code` por tokens
   - Salva no SQLite (`oauth_tokens`) e no `.env`

2. **Refresh automático**: cliente verifica `expires_at` antes de cada chamada; se < 5min de buffer, faz refresh e atualiza DB.

3. **Recuperação**: se refresh falha (ex: usuário revogou), CLI deve guiar reauth com mensagem clara.

---

## 7. Rate limiting

Strava: **200 req / 15 min** + **2000 req / dia**, ambos contados por aplicação (não por usuário).

Implementar:
- Decorator que respeita ambas as janelas usando `asyncio.Semaphore` + timestamps
- Em caso de 429, ler header `X-RateLimit-Limit` e `X-RateLimit-Usage` para calibrar e fazer backoff exponencial
- Logging de uso para alertar quando próximo do limite

---

## 8. Roadmap de implementação

Cada fase tem critério de aceitação claro. **Implementar fase a fase, não pular.** Cada fase deve estar 100% testada e funcional antes de partir para a próxima.

### Fase 0 — Fundação (objetivo: estrutura limpa)

- [ ] Estrutura de pastas conforme seção 2.3
- [ ] `pyproject.toml` com `uv`, dependências mínimas
- [ ] `ruff` configurado (linha 100 chars, regras: E, F, I, B, UP, SIM)
- [ ] `pytest` configurado com `pytest-asyncio`
- [ ] CI no GitHub Actions: lint + testes em push
- [ ] `README.md` esqueleto (preencher conforme avança)
- [ ] `.gitignore` cobrindo `.env`, `*.db`, `__pycache__`, `.venv`
- [ ] CLI esqueleto com `typer`: comandos `setup`, `sync`, `doctor`, `serve`

**Aceitação:** `uv run pytest` passa (mesmo sem testes ainda); `uv run strava-mcp --help` lista comandos.

### Fase 1 — Cliente Strava + OAuth (objetivo: conseguir buscar dados)

- [ ] `strava_client/auth.py`: fluxo OAuth completo via servidor local efêmero
- [ ] `strava_client/client.py`: wrapper httpx async com refresh automático
- [ ] `strava_client/rate_limit.py`: decorator de rate limiting respeitando ambas as janelas
- [ ] Métodos: `get_athlete()`, `list_activities(after, before, page, per_page)`, `get_activity(id)`, `get_streams(id, types)`
- [ ] CLI `setup` funcional ponta-a-ponta
- [ ] Testes unitários com mock de httpx (cobrir refresh, 429, paginação)

**Aceitação:** `uv run strava-mcp setup` autentica; `python -c "from strava_mcp.strava_client import client; print(client.get_athlete())"` retorna dados reais.

### Fase 2 — Banco e sync (objetivo: histórico local completo)

- [ ] `db/schema.sql` conforme seção 4
- [ ] `db/migrations.py`: aplicação idempotente de schema
- [ ] `db/repositories.py`: ActivityRepository, StreamRepository, etc. (CRUD limpo)
- [ ] `sync/backfill.py`: backfill completo, paginando do mais antigo ao mais novo
- [ ] `sync/incremental.py`: sync delta usando `last_incremental_sync_at`
- [ ] `sync/streams.py`: download de streams sob demanda (não automático no backfill — caro)
- [ ] CLI `sync --full` e `sync` (incremental)
- [ ] CLI `doctor`: relatório de completude, atividades sem streams, gaps de data
- [ ] Testes com fixtures de payloads reais do Strava (anonimizados)

**Aceitação:** após `setup` + `sync --full`, banco contém todas as atividades do atleta. Re-rodar `sync` é idempotente. `doctor` reporta tudo verde.

### Fase 3 — Analytics core (objetivo: métricas científicas básicas)

- [ ] `analytics/zones.py`: estimativa de LTHR e FCmáx; cálculo de zonas; tempo em zona por atividade
- [ ] `analytics/load.py`: TRIMP, hrTSS, rTSS por atividade; CTL/ATL/TSB diários
- [ ] `analytics/efficiency.py`: EF e decoupling
- [ ] `analytics/ngp.py`: Normalized Graded Pace (precisa de stream de altitude)
- [ ] `sync/compute_metrics.py`: pipeline que recalcula `activity_metrics` e `daily_metrics` após sync
- [ ] Testes com dados sintéticos cobrindo casos limite (treino sem FC, treino curto, etc.)

**Aceitação:** após sync, queries `SELECT * FROM activity_metrics LIMIT 10` e `SELECT * FROM daily_metrics ORDER BY date DESC LIMIT 30` retornam valores plausíveis. Validar 2-3 atividades manualmente contra cálculo em planilha.

### Fase 4 — MCP server v0.1 (objetivo: usável no Claude Desktop)

- [ ] `mcp_server/server.py`: FastMCP setup
- [ ] Tools da seção 5.1, 5.2, 5.3, 5.4 implementadas
- [ ] Tools 5.8 (`sync_now`, `athlete_doctor`)
- [ ] Documentação inline (docstrings) que serve de "system prompt" para o LLM
- [ ] CLI `serve` que inicia o MCP em stdio
- [ ] `claude_desktop_config.example.json` no repo
- [ ] README com instruções de adicionar ao Claude Desktop
- [ ] Testes de cada tool (entrada → saída esperada com fixture de DB)

**Aceitação:** Claude Desktop consegue invocar pelo menos 5 tools diferentes em uma conversa real e retornar respostas coerentes baseadas nos dados reais do atleta. Validar com prompts da seção 11.1.

**🎯 Marco postável no LinkedIn — versão "MCP que aplica sports science nos seus dados do Strava"**

### Fase 5 — Predições e clima (objetivo: insights que o Strava não dá)

- [ ] `analytics/predictions.py`: Riegel, VDOT (com tabela), find_personal_records via efforts
- [ ] `analytics/weather.py`: integração Open-Meteo (gratuita, sem chave, rate limit generoso)
- [ ] Migration: backfill de weather para atividades existentes (paginado, respeitando rate limit)
- [ ] Tools 5.5 (`predict_race_time`, `find_personal_records`)
- [ ] Tools 5.6 (`analyze_weather_impact`)

**Aceitação:** `predict_race_time(21.0975)` retorna tempo plausível com IC. `analyze_weather_impact` mostra correlação real entre temperatura e pace. Validar com prompts da seção 11.2.

### Fase 6 — ML e análises avançadas (objetivo: diferencial real)

- [ ] `analytics/anomalies.py`: regressão de pace esperado, detecção de outliers
- [ ] `analytics/clustering.py`: clustering de rotas via DBSCAN em coordenadas
- [ ] `analytics/performance_drivers.py`: feature importance via gradient boosting nos últimos 60 dias
- [ ] `analytics/injury_risk.py`: ACWR + spikes + degradação de eficiência
- [ ] Tools 5.5 (`what_drives_my_performance`)
- [ ] Tools 5.6 (`get_route_clusters`, `find_anomalies`)
- [ ] Tools 5.3 (`get_injury_risk_assessment`)

**Aceitação:** análises produzem outputs interpretáveis e validáveis. Documentar no README 2-3 insights reais descobertos pelo próprio autor usando o sistema. Validar com prompts da seção 11.3.

### Fase 7 — Narrativa e diagnóstico (objetivo: experiência conversacional)

- [ ] Tools 5.7 (`generate_period_narrative`, `diagnose_plateau`)
- [ ] Refinamento de docstrings para guiar uso conjunto pelo LLM
- [ ] Exemplos de "system prompts" para configurar Claude como coach pessoal usando essas tools

**Aceitação:** conversa com Claude usando o MCP produz análises tipo "como foi meu trimestre?" com qualidade de coach experiente. Validar com prompts da seção 11.4.

### Fase 8 — Ajustes finos pós-review (objetivo: consolidar feedback externo antes do polish público)

**Contexto:** após a Fase 7, o projeto passou por revisões externas que convergiram em pontos relacionados a qualidade da série temporal, clareza arquitetural e mensurabilidade dos critérios de polish. Esta fase consolida implementação, verificação e expansão do backlog em uma única passagem antes da Fase 9.

**Implementação (entregar):**
- [ ] Diagrama de arquitetura no README (Mermaid: `setup → sync → compute-metrics → serve → Claude`)
- [ ] `docs/TROUBLESHOOTING.md` com cenários: OAuth expirado, 429 da Strava API, sync interrompido no meio, gaps de stream, reset do banco
- [ ] Reescrever os critérios da Fase 9 de forma mensurável no próprio SPEC (badges, ≥3 screenshots, link de post publicado, etc.)

**Verificação (auditoria do código atual; corrigir e anotar no commit se houver gap):**
- [ ] CTL/ATL/TSB tratam dias sem atividade como TSS=0? Se não, decay quebra em períodos de descanso/lesão
- [ ] Existe cache persistente para Open-Meteo? Backfill de 2 anos sem cache esgota rate limit
- [ ] Há sanitização atual de FC spikes ou GPS jumps no `compute-metrics`?

**Expansão do backlog (registrar em `docs/BACKLOG.md`, sem implementar):**
- [ ] **Data Quality Layer** — expandir o item de GPS corrompido para englobar HR spikes, gaps de stream, pace impossível, mismatch moving vs elapsed time
- [ ] `compare_cycles()` — tool comparando ciclo atual com melhor meia anterior
- [ ] Versões `summary`/`detailed` em `generate_period_narrative` e `what_drives_my_performance`
- [ ] Schemas MCP padronizados (envelope `{status, data, warnings, confidence}`)
- [ ] Cross-validation + Spearman para validar `what_drives_my_performance`
- [ ] Reorganização de `analytics/` em sub-pastas (`features/`, `metrics/`, `models/`, `diagnostics/`)

**Aceitação:** README com diagrama legível; `TROUBLESHOOTING.md` cobrindo ≥4 cenários; checklist da Fase 9 reescrito de forma mensurável; cada item de Verificação fechado (correção implementada com nota no commit, ou commit explicando que não há gap); `BACKLOG.md` expandido com os 6 itens acima.

### Fase 9 — Polish e portfólio (objetivo: projeto público forte)

- [ ] README profissional: diagrama de arquitetura, screenshots de conversas reais, lista de análises, instruções claras de setup
- [ ] Notebook Jupyter de exemplo (`examples/exploration.ipynb`) que exercita as funções de analytics fora do MCP
- [ ] GitHub Actions: sync diário automatizado (opcional, para o autor)
- [ ] Post de blog/LinkedIn descrevendo arquitetura e aprendizados
- [ ] Licença MIT, CONTRIBUTING.md, CODE_OF_CONDUCT.md

**Aceitação:** repo público apresentável; alguém estranho ao projeto consegue rodar tudo seguindo o README.

---

## 9. Diretrizes para o Claude Code implementador

Esta seção fala diretamente com a instância de Claude Code que vai trabalhar no repo.

### Princípios

1. **Implementar fase a fase, em ordem.** Não saltar. Cada fase tem critério de aceitação — só passar para a próxima quando atendido.
2. **Testes antes de tools.** Cada função de `analytics/` deve ter teste unitário com dados sintéticos antes de ser exposta como tool MCP.
3. **Nunca fabricar dados.** Se uma análise precisa de dado que não existe (ex: peso do atleta para potência), retornar tool result com `status: "missing_config"` indicando o que falta. Não chutar valores.
4. **Determinismo.** Modelos com aleatoriedade fixam seed = 42. Cálculos baseados em "hoje" recebem `today` como parâmetro injetável (default: `date.today()`) para tornar testes determinísticos.
5. **Erros explícitos.** Tool MCP nunca lança exceção pro cliente — captura, retorna `{"error": "...", "details": "..."}`. Logging em arquivo separado.
6. **Não otimizar prematuramente.** SQLite, queries simples, pandas. Só otimizar com profiling em mãos.
7. **Documentar decisões.** Se você (Claude Code) precisar tomar decisão não coberta neste documento, registrar em `docs/decisions/NNNN-titulo.md` (formato ADR — Architecture Decision Record).

### Convenções

- Nomes em inglês no código, comentários podem ser em português (este é projeto pessoal lusófono)
- Tipos: anotações de tipo obrigatórias em todo código de produção
- Datas: sempre `datetime` com timezone explícito; nunca `datetime.now()` (use `datetime.now(UTC)`)
- Unidades: SI no banco (metros, segundos, m/s); conversão para apresentação (km, min/km) só na camada de tools
- Logs: `structlog` com formato JSON em produção, console em dev

### Coisas a NÃO fazer

- Não criar dashboard antes da Fase D5 do roadmap de dados (escopo creep)
- Não implementar webhook do Strava (complica deploy desnecessariamente)
- Não usar ORM pesado (SQLAlchemy Core sim, ORM declarativo não — overhead injustificado pra esse projeto)
- Não cachear na memória do server MCP — sempre ler do SQLite (server pode reiniciar, dados na memória se perdem)
- Não chamar API do Strava de dentro de tools de leitura "normais" — só `sync_now()` deve fazer isso

### Quando perguntar

Em geral, seguir o documento. Mas pedir confirmação ao usuário se:

- Decisão arquitetural conflitante com o documento (com justificativa)
- Dado faltando bloqueia o progresso (ex: nenhuma atividade tem FC)
- Modelo de sports science tem implementação ambígua na literatura

---

## 10. Variáveis de ambiente

```bash
# .env.example
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_DB_PATH=./data/strava.db
LOG_LEVEL=INFO
LOG_PATH=./logs/strava-mcp.log
```

---

## 11. Prompts de exemplo (testes de aceitação conversacionais)

Esta seção descreve perguntas reais que o atleta faria ao Claude usando o MCP. Servem como **testes funcionais end-to-end**: ao final de cada fase relevante, validar que essas conversas produzem respostas úteis. Contexto do atleta na seção 1.

### 11.1 Perguntas "pulso" (uso diário, validar Fase 4)

Devem responder em segundos, baseadas só no cache:

- "Como foi minha semana?"
- "Estou descansado o suficiente para fazer um treino forte amanhã?"
- "Quanto eu corri esse mês comparado ao mês passado?"
- "Qual foi meu treino mais duro dos últimos 30 dias?"
- "Estou correndo mais ou menos do que no mesmo período do ano passado?"
- "Mostra os meus 5 long runs mais recentes."

**Tools envolvidas:** `list_activities`, `get_period_stats`, `compare_periods`, `get_current_form`, `get_weekly_breakdown`.

### 11.2 Perguntas de ciclo de maratona (validar Fase 5)

Específicas do contexto do atleta. Devem ativar várias tools e produzir resposta com prosa analítica:

- "Estou começando um ciclo de maratona de 16 semanas. Que volume devo estar fazendo nas semanas de pico baseado no meu histórico?"
  - Esperado: análise de CTL atual, CTL típica em momentos de boa forma do histórico, sugestão de progressão
- "Baseado nas minhas 7 meias, qual seria um tempo realista de maratona usando Riegel? E com VDOT?"
  - Esperado: lista das meias com tempos, projeções pelos dois métodos, discussão da diferença e por que VDOT tende a ser mais conservador em distâncias maiores
- "Quais das minhas meias eu performei melhor relativo à minha forma na época?"
  - Esperado: para cada meia, comparar tempo real com tempo esperado dada a CTL/eficiência aeróbica do período → identificar "overperformances" (corridas em que a forma rendeu mais que o esperado)
- "Olhando para as condições das minhas meias passadas (clima, elevação, TSB), em que cenário eu corro melhor?"
  - Esperado: cruzamento de PRs com clima e forma → padrões (ex: "todas suas top-3 meias foram em dias < 18°C com TSB entre +5 e +15")
- "Qual foi a periodização que me levou à minha melhor meia? Quero replicar para a maratona."
  - Esperado: identificar a melhor meia, recortar 12-16 semanas anteriores, descrever estrutura semanal típica, distribuição de zonas, progressão de long runs, semanas de deload
- "Estou na semana 4 do ciclo de maratona com long run de 28km marcado pra domingo. Meu corpo aguenta dado o que fiz nas últimas 3 semanas?"
  - Esperado: análise de ACWR, TSB projetada para domingo, decoupling em long runs recentes → recomendação fundamentada (manter, reduzir 2-3km, ou trocar de dia)
- "Quantos long runs ≥30km eu fiz no histórico? Como meu pace neles evoluiu?"
  - Esperado: filtragem + análise temporal de pace nesses treinos, controlado por clima

**Tools envolvidas:** `predict_race_time`, `find_personal_records`, `analyze_weather_impact`, `get_load_history`, `compare_periods`, `generate_period_narrative`, `get_decoupling_trend`.

### 11.3 Perguntas diagnósticas (validar Fase 6)

Mais profundas, dependem de modelos:

- "Sinto que estou estagnando há uns 2 meses. O que os dados mostram?"
  - Esperado: `diagnose_plateau` retorna hipóteses ranqueadas; Claude prioriza a mais provável com evidências
- "Que tipo de treino historicamente me faz performar melhor 2-3 semanas depois?"
  - Esperado: `what_drives_my_performance` identifica padrões pessoais (mais resposta a volume? a tempo runs? a long runs com finish forte?)
- "Tem algum treino recente que foi muito atípico? Pode ter sido sinal de algo?"
  - Esperado: `find_anomalies` lista outliers, Claude contextualiza (clima ruim? TSB negativa? possível doença?)
- "Como minha base aeróbica evoluiu nesses 18 meses?"
  - Esperado: `get_aerobic_efficiency_trend` + `get_decoupling_trend` → narrativa de evolução com pontos de inflexão
- "Estou em risco de lesão? Estou aumentando volume rápido demais?"
  - Esperado: `get_injury_risk_assessment` com breakdown dos fatores e recomendação concreta
- "Quais rotas eu corro com mais frequência e como meu pace nelas evoluiu?"
  - Esperado: `get_route_clusters` + análise temporal por rota (pace controlado por clima)

### 11.4 Perguntas de prescrição (validar Fase 7)

Conversacionais, geralmente combinam várias tools + julgamento do LLM:

- "Monte uma estrutura de semana para mim considerando minha forma atual e o objetivo de maratona em 12 semanas."
- "Devo correr a meia que tem daqui 5 semanas como rojão ou usar como treino?"
  - Esperado: análise de TSB projetada, impacto na CTL para o pico da maratona, recomendação fundamentada
- "Daqui a quantas semanas devo começar o taper se quero chegar fresco com CTL próxima do pico?"
- "Meu pace de Z2 deveria estar onde para eu mirar maratona em 3h30?"
  - Esperado: projeção reversa via VDOT, comparação com pace Z2 atual
- "Qual o pace ideal de maratona para mim hoje? E qual eu poderia fazer se completasse o ciclo bem?"
  - Esperado: projeção atual + projeção considerando ganho típico de fitness em ciclo de 12-16 semanas

### 11.5 Perguntas exploratórias / curiosidade (qualquer fase)

- "Qual foi o treino mais difícil que eu já fiz?"
- "Em que dia da semana eu costumo correr melhor?"
- "Quantos km eu já corri na vida no Strava?"
- "Qual foi o mês em que eu mais corri?"
- "Quais foram meus 10 long runs mais rápidos?"
- "Em quais provas eu negative-split (segunda metade mais rápida que a primeira)?"

### 11.6 Como usar como teste de aceitação

Para cada fase concluída, rodar 3-5 prompts da seção correspondente em uma conversa real com Claude Desktop. Critério:
- Tools certas são chamadas (verificável no log do MCP)
- Resposta do Claude é coerente e usa os dados retornados
- Nenhuma alucinação detectável (números batem com queries diretas no SQLite)

Documentar essas conversas em `docs/conversations/` como evidência funcional do projeto — bônus para o portfólio (mostra o produto em uso).

---

## 12. Camada de engenharia de dados e dashboard

Camada complementar ao MCP. **Não bloqueia o roadmap principal** (Fases 0-8) e tem seu próprio roadmap (Fases D1-D7). Pode ser implementada em paralelo ou após Fase 4 do principal.

### 12.1 Motivação

O SQLite cumpre bem o papel de **operational store** do MCP (leituras pontuais, baixa latência, dados quentes). Mas para análise exploratória, dashboard e portfólio de engenharia de dados, faz sentido ter uma camada modelada com práticas de DW:

- Modelos versionados e testados (não queries soltas)
- Star schema com fatos e dimensões claras
- Materialização de métricas pesadas
- Linhagem visível
- Dashboard navegável para uso fora do contexto conversacional

Isso transforma o projeto de "MCP server pessoal" em "**plataforma de dados esportivos pessoal end-to-end**", com narrativa muito mais forte para perfil profissional de dados.

### 12.2 Stack proposta (otimizada para rodar localmente)

```
SQLite (raw)  ──> dbt ──> SQLite (analytics) ──> Streamlit
                  │
                  └──> testes, docs, lineage
```

**Por que esses componentes:**

- **dbt-core** com adapter `dbt-sqlite`: leve, gratuito, padrão de mercado para modelagem analítica. Roda local sem warehouse externo.
- **SQLite como warehouse**: pragmático para o volume (alguns milhares de atividades). Schemas separados (`raw`, `staging`, `marts`) via attaches ou prefixos de tabelas.
- **Streamlit**: melhor custo-benefício para dashboard local em Python. Multi-página, hot reload, integração trivial com pandas/plotly.
- **DuckDB como alternativa**: se quiser experimentar, dbt-duckdb é mais rápido e tem features modernas (window functions ricas, suporte a Parquet). Para esse projeto, SQLite é suficiente; deixar DuckDB como escolha futura se o volume crescer.

### 12.3 Modelagem dimensional

**Camadas dbt:**

```
models/
├── staging/                    # 1:1 com tabelas raw, casts e renomeações
│   ├── stg_strava__activities.sql
│   ├── stg_strava__streams.sql
│   ├── stg_strava__activity_metrics.sql
│   ├── stg_strava__daily_metrics.sql
│   └── stg_weather__observations.sql
├── intermediate/               # joins e enriquecimentos reutilizáveis
│   ├── int_activities_enriched.sql        -- atividades + métricas + clima
│   ├── int_activities_with_zones.sql      -- com tempo em zona já calculado
│   └── int_activities_with_route_cluster.sql
└── marts/
    ├── core/
    │   ├── dim_date.sql                   -- calendário com semana ISO, mês, ano, dia da semana
    │   ├── dim_activity.sql               -- dimensão atividade (slowly changing — tipo 1)
    │   ├── dim_route.sql                  -- rotas clusterizadas
    │   ├── fct_activity.sql               -- fato grão = 1 atividade
    │   └── fct_daily_load.sql             -- fato grão = 1 dia (CTL/ATL/TSB)
    ├── training/
    │   ├── fct_weekly_summary.sql         -- agregação semanal
    │   ├── fct_monthly_summary.sql
    │   ├── fct_zone_distribution.sql      -- tempo em zona por semana
    │   └── fct_long_runs.sql              -- recorte de long runs com decoupling
    └── racing/
        ├── dim_race.sql                   -- atividades marcadas como prova
        ├── fct_race_performance.sql       -- inclui CTL/TSB no dia, clima, projeções
        └── fct_pr_efforts.sql             -- best efforts em distâncias padrão
```

**Convenções:**
- `fct_*`: fatos (eventos, grão definido)
- `dim_*`: dimensões (atributos, normalmente baixa cardinalidade)
- Naming `snake_case`, prefixos consistentes
- Nenhum `select *` em produção
- Toda tabela final tem `dbt test` mínimo: `not_null` em PKs, `unique` em chaves naturais, `accepted_values` em enums

### 12.4 Identificação de provas

Provas precisam ser distintas de treinos para análise correta. Estratégia em camadas:

1. **Heurística automática:** atividade marcada como `workout_type = 1` (race) na API do Strava
2. **Regex no nome:** padrões "meia", "10k", "maratona", nomes de eventos conhecidos
3. **Override manual:** tabela seed `seeds/manual_races.csv` onde o atleta lista IDs de atividades que são provas e metadados (oficial? distância oficial? PR?)
4. Combinação: `dim_race` faz union dessas fontes com prioridade para override manual.

Schema sugerido do seed:

```csv
activity_id,is_race,distance_official_km,race_name,is_official,objective
12345678,true,21.0975,"Meia de São Paulo 2024",true,"target_pr"
23456789,true,10.0,"Corrida do CCBB 2024",true,"training_race"
```

Crítico para `fct_race_performance` — sem isso, predições e análises de pacing ficam contaminadas por treinos. Para o atleta de referência, as 7 meias devem ser todas catalogadas no seed na primeira execução.

### 12.5 Testes dbt obrigatórios

```yaml
# Exemplos
models:
  - name: fct_activity
    columns:
      - name: activity_id
        tests: [unique, not_null]
      - name: sport_type
        tests:
          - accepted_values:
              values: [Run, Ride, Swim, Walk, Hike, Workout]
      - name: distance_m
        tests:
          - dbt_utils.expression_is_true:
              expression: ">= 0"
  - name: fct_daily_load
    columns:
      - name: date
        tests: [unique, not_null]
      - name: ctl
        tests:
          - dbt_utils.expression_is_true:
              expression: ">= 0 and <= 300"  # range plausível
```

### 12.6 Orquestração

Para projeto pessoal, basta um **Makefile** ou script shell simples:

```makefile
sync:
	uv run strava-mcp sync

transform:
	cd dbt && dbt build

dashboard:
	uv run streamlit run dashboard/Home.py

pipeline: sync transform
	@echo "Pipeline completa. Rode 'make dashboard' para visualizar."
```

Para automação verdadeira, **GitHub Actions** com cron diário:
1. Sync incremental
2. dbt build
3. Commit do `target/` (manifest, run results) + dados em branch `data-snapshots`
4. Build de site estático com docs do dbt + último estado dos marts

Isso dá um repo "vivo" — bom para portfólio.

### 12.7 Dashboard Streamlit

**Estrutura multi-página:**

```
dashboard/
├── Home.py                          # overview: forma atual, últimas atividades, alerts
├── pages/
│   ├── 1_📅_Visao_Geral.py          # heatmap de calendário, totais, distribuição
│   ├── 2_📊_Carga_e_Forma.py        # CTL/ATL/TSB, ACWR, gráfico clássico de PMC
│   ├── 3_❤️_Eficiencia.py           # EF e decoupling no tempo, distribuição de zonas
│   ├── 4_🏁_Provas.py               # tabela de provas, comparações, predições
│   ├── 5_🌦️_Clima.py                # impacto de temperatura/umidade no pace
│   ├── 6_🗺️_Rotas.py                # clusters, evolução por rota, mapa
│   ├── 7_🎯_Ciclo_Atual.py          # dashboard específico do bloco de maratona
│   └── 8_🔬_Anomalias.py            # treinos atípicos, plateaus, alerts
└── components/                      # gráficos reutilizáveis
    ├── pmc_chart.py                 # Performance Management Chart
    ├── zone_distribution.py
    └── activity_table.py
```

**Princípios de design:**
- Cada página responde a 1-3 perguntas claras (não um amontoado de gráficos)
- Filtros consistentes no sidebar (período, tipo de atividade)
- Cores: paleta sóbria, semântica para forma (TSB > 5 verde, < -30 vermelho)
- Plotly para interatividade (zoom, hover detalhado)
- Cache de queries com `@st.cache_data(ttl=3600)` lendo dos marts

**Página de "Ciclo Atual" (especial pro contexto do atleta):**
- Input: data alvo da maratona, tempo objetivo
- Output:
  - Progressão de CTL atual vs trajetória ideal pra atingir CTL alvo no taper
  - Long runs feitos vs progressão recomendada (até ~32-35km)
  - Distribuição de zonas das últimas 4 semanas vs polarização recomendada (~80/20)
  - Predição de tempo atualizada semanalmente (baseada em treinos do ciclo)
  - Comparação com o ciclo da melhor meia anterior (replicar periodização vencedora)
  - Risco de lesão atual e tendência

Essa página por si só justifica o projeto e gera bons screenshots para LinkedIn.

### 12.8 Roadmap da camada de dados (paralelo às fases principais)

#### Fase D1 — Setup dbt (após Fase 2 do roadmap principal)

- [ ] `dbt_project.yml`, `profiles.yml` apontando para mesmo SQLite
- [ ] Schemas separados via prefixo de tabela (`stg_`, `int_`, `mart_`) ou attach databases
- [ ] Models de staging completos com testes básicos
- [ ] `dbt docs generate` rodando, lineage visível
- [ ] Comando `make transform` funcional

**Aceitação:** `dbt build` passa todos os testes. `dbt docs serve` mostra lineage de todas as tabelas.

#### Fase D2 — Marts core (após Fase 3 do principal)

- [ ] `dim_date`, `dim_activity`, `fct_activity`, `fct_daily_load`
- [ ] Dimensões e fatos cobrindo 100% das atividades sem perda de dados
- [ ] Testes de integridade referencial entre fato e dimensões
- [ ] Documentação de cada coluna no `schema.yml`

**Aceitação:** `count(*) from fct_activity == count(*) from raw activities`. Nenhum órfão entre fato e dimensões.

#### Fase D3 — Marts de treino (após Fase 5 do principal)

- [ ] `fct_weekly_summary`, `fct_monthly_summary`
- [ ] `fct_zone_distribution`
- [ ] `fct_long_runs` (com decoupling, NGP, etc)

**Aceitação:** queries de exemplo respondem em < 100ms.

#### Fase D4 — Marts de prova (após Fase 5 do principal)

- [ ] `dim_race` com lógica de identificação combinada
- [ ] `seeds/manual_races.csv` populado com as 7 meias do atleta + outras provas
- [ ] `fct_race_performance` enriquecido com forma, clima, projeções
- [ ] `fct_pr_efforts` em distâncias padrão (1K, 5K, 10K, 15K, 21.0975K, 42.195K)

**Aceitação:** todas as 7 meias aparecem em `dim_race`; `fct_race_performance` mostra para cada uma: tempo, pace, CTL/TSB no dia, clima, posição relativa entre as 7.

#### Fase D5 — Streamlit MVP (após Fase 4 do principal)

- [ ] Páginas 1-3 (Visão Geral, Carga e Forma, Eficiência)
- [ ] Cache funcionando, latência < 1s para mudança de filtro
- [ ] Deploy local via `make dashboard`

**Aceitação:** dashboard usável no dia-a-dia para acompanhar treinos sem precisar do Strava.

#### Fase D6 — Streamlit completo (após Fase 6 do principal)

- [ ] Páginas 4-8
- [ ] Página de Ciclo Atual configurável (data alvo, tempo objetivo)
- [ ] Screenshots reais no README

**Aceitação:** alguém olhando o dashboard sem contexto entende o que está vendo. Página de Ciclo Atual é informativa para o atleta no ciclo de maratona em andamento.

#### Fase D7 — Automação (opcional, após D6)

- [ ] GitHub Actions: sync diário + dbt build + deploy de docs do dbt como GitHub Pages
- [ ] Streamlit Community Cloud: deploy gratuito do dashboard (com auth básica para dados pessoais)
- [ ] Alternativa: continuar local-first, sem deploy público

### 12.9 Observação sobre stack

Este projeto deliberadamente usa stack mais leve que stacks profissionais comuns (Cube + Next.js + Cloud Run, por exemplo) por motivos:

1. **Local-first**: dados pessoais sensíveis, deploy local elimina questões de privacidade
2. **Foco no diferencial**: o valor não está na stack de visualização, mas na profundidade analítica (sports science, MCP, modelos preditivos). Stack simples deixa esse valor mais visível
3. **Reusabilidade de aprendizados**: dbt + SQLite/DuckDB + Streamlit é um stack mais comum em projetos open source / data engineering portfolios; replicação por terceiros é mais provável
4. **Complementaridade com perfil profissional**: se você já demonstrou stack pesada em projetos de empresa, demonstrar stack leve aqui mostra range — capacidade de escolher ferramenta certa para cada problema

Se em algum momento o projeto evoluir para multi-tenant (vários atletas), aí sim faria sentido migrar para Postgres + Cube/Metabase + Next.js — o roadmap pode prever isso como Fase D8 sem invalidar nada anterior.

---

## 13. Referências

- Strava API docs: https://developers.strava.com/docs/reference/
- Open-Meteo Historical: https://open-meteo.com/en/docs/historical-weather-api
- Banister model (TRIMP, CTL/ATL/TSB): Banister, E. W. (1991). Modeling elite athletic performance.
- TrainingPeaks TSS: https://www.trainingpeaks.com/learn/articles/normalized-power-intensity-factor-training-stress/
- Friel zones: Joe Friel, *The Triathlete's Training Bible*
- Daniels VDOT: Jack Daniels, *Daniels' Running Formula*
- ACWR: Gabbett, T. J. (2016). The training-injury prevention paradox.
- MCP spec: https://modelcontextprotocol.io/
- FastMCP docs: https://github.com/jlowin/fastmcp
- dbt-sqlite: https://github.com/jwills/dbt-sqlite
- Streamlit multi-page: https://docs.streamlit.io/library/get-started/multipage-apps
