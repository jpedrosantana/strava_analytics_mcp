# Troubleshooting

Cenários comuns ao operar o `strava-mcp` e como resolvê-los. Cada seção traz **sintoma**, **causa** e **ação**.

> Antes de qualquer diagnóstico, rode `uv run strava-mcp doctor`. O comando mostra: caminho do banco, último sync (full/incremental), total de atividades, período coberto, distribuição por esporte e quantas atividades estão sem streams.

---

## 1. OAuth expirado ou falha de autenticação

**Sintoma:** `setup` falha; ou `sync` retorna `401 Unauthorized` / `Invalid refresh token`.

**Causa:** o token de acesso da Strava expira a cada 6h. O cliente refaz o refresh automaticamente quando faltam <5min, usando o `refresh_token` armazenado em `oauth_tokens` (SQLite). Se o refresh token foi revogado (ex.: o app foi desautorizado em [strava.com/settings/apps](https://www.strava.com/settings/apps)) ou as credenciais do `.env` mudaram, o refresh falha.

**Ação:**
1. Confirme `STRAVA_CLIENT_ID` e `STRAVA_CLIENT_SECRET` no `.env` batem com o app em [developers.strava.com](https://developers.strava.com).
2. Re-autorize: `uv run strava-mcp setup` — o `UPSERT` em `oauth_tokens` sobrescreve o token antigo.
3. Se persistir, apague apenas a linha de token (sem perder o histórico):
   ```bash
   sqlite3 data/strava.db "DELETE FROM oauth_tokens;"
   uv run strava-mcp setup
   ```

---

## 2. 429 Too Many Requests (rate limit)

**Sintoma:** sync trava por longos períodos ou levanta `RuntimeError: Máximo de N tentativas atingido`.

**Causa:** Strava limita 200 requisições por 15 minutos e 2000 por dia. O cliente aplica:
- **Rate limiter proativo** — para de enviar requisições antes de bater o limite e dorme até a janela abrir.
- **Retry reativo no 429** — respeita o header `Retry-After` (default 60s) e tenta até 3 vezes.

Mesmo com isso, um backfill de 2 anos (≈ 1500-2000 atividades) consome o limite diário só pelas listagens, e cada `sync --streams` faz +1 requisição por atividade.

**Ação:**
- **Backfill grande:** rode em mais de um dia. O sync é idempotente (UPSERTs em todas as tabelas), pode parar e retomar.
- **Streams:** use `sync --streams --streams-limit 200` para baixar em lotes.
- Se um sync acabar com `RuntimeError`, espere 15-60min e rode `uv run strava-mcp sync` (incremental) ou `sync --full` de novo.

---

## 3. Sync interrompido no meio

**Sintoma:** `Ctrl+C` durante backfill, queda de rede, processo morto.

**Causa:** atividades já baixadas estão no banco (UPSERT por página). Mas o watermark `last_incremental_sync_at` só é gravado ao final do backfill — se a execução não chegou ao fim, sync incremental seguinte pode pegar mais dados do que o necessário.

**Ação:**
- **Backfill (`--full`) interrompido:** rode `sync --full` de novo. Atividades já presentes são UPSERT (custa requisição mas não duplica linhas).
- **Sync incremental interrompido:** rode `sync` de novo. Idempotente.
- Confirme com `doctor` — `Período: oldest → newest` deve cobrir o intervalo esperado.

---

## 4. Métricas faltantes (sem streams)

**Sintoma:** `get_aerobic_efficiency_trend` ou `get_decoupling_trend` retornam vazio. `compute-metrics` rodou mas `EF` / decoupling continuam nulos.

**Causa:** EF e decoupling cardíaco são calculados sobre os streams (séries temporais de FC + distância + tempo). Sem streams, só métricas agregadas (TRIMP, hrTSS, zonas baseadas em médias) são computadas.

**Ação:**
1. Verifique quantas atividades estão sem streams:
   ```bash
   uv run strava-mcp doctor   # campo "Sem streams: N"
   ```
2. Baixe os streams:
   ```bash
   uv run strava-mcp sync --streams
   ## em lotes para evitar 429:
   uv run strava-mcp sync --streams --streams-limit 200
   ```
3. Recalcule:
   ```bash
   uv run strava-mcp compute-metrics
   ```

---

## 5. Reset do banco

Não há comando dedicado de reset. Escolha o nível conforme o problema:

**Reset total** (perde histórico, tokens OAuth, métricas):
```bash
rm data/strava.db
uv run strava-mcp setup
uv run strava-mcp sync --full --streams --compute
```

**Recomputar apenas as métricas** (preserva atividades e streams):
```bash
sqlite3 data/strava.db "DELETE FROM activity_metrics; DELETE FROM training_load_daily;"
uv run strava-mcp compute-metrics
```

**Re-baixar uma atividade específica** (corrompida no Strava ou alterada manualmente):
```bash
sqlite3 data/strava.db "DELETE FROM activities WHERE id = <ACTIVITY_ID>; \
                        DELETE FROM activity_streams WHERE activity_id = <ACTIVITY_ID>; \
                        DELETE FROM activity_metrics WHERE activity_id = <ACTIVITY_ID>;"
uv run strava-mcp sync          # incremental — só pega o delta após o último sync, ajustar se necessário
```

---

## 6. Agendamento local com cron

Como o projeto é local-first (banco SQLite + tokens OAuth na máquina do autor — cf. [ADR 0003](decisions/0003-ci-scope-local-first.md)), o sync diário roda direto no seu computador. Exemplo de entrada em crontab para sincronizar todo dia às 06:00 e recalcular as métricas:

```cron
# m h dom mon dow command
0 6 * * * cd /caminho/absoluto/para/strava_analytics_mcp && /home/SEU_USUARIO/.local/bin/uv run strava-mcp sync && /home/SEU_USUARIO/.local/bin/uv run strava-mcp compute-metrics >> /tmp/strava-sync.log 2>&1
```

Edite com `crontab -e`. Pontos de atenção:
- Use **caminho absoluto do `uv`** (`which uv` para descobrir) — o crontab roda com PATH mínimo.
- O `cd` é necessário porque os comandos esperam encontrar `data/strava.db` relativo ao diretório do projeto.
- Streams (`sync --streams`) não estão no comando porque são mais pesados; rode-os semanalmente ou sob demanda.
- Para diagnosticar falhas: `cat /tmp/strava-sync.log` ou troque `2>&1` por `mailto:` no topo do crontab para receber por e-mail local.
