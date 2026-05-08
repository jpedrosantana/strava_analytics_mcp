# 0001 — Token storage na Fase 1

## Status
Accepted

## Contexto
A Fase 1 implementa o cliente OAuth. Os tokens (`access_token`, `refresh_token`, `expires_at`) precisam ser persistidos. A infraestrutura completa de banco de dados (incluindo migrations e todos os repositórios) é implementada na Fase 2.

## Decisão
Criar a tabela `oauth_tokens` diretamente em `auth.py` via `CREATE TABLE IF NOT EXISTS`. O schema é idêntico ao definido na seção 4 do SPEC. As migrations da Fase 2 usarão `IF NOT EXISTS` também, portanto são idempotentes — a tabela já existindo não gera conflito.

## Alternativas consideradas
- **JSON file** (`.strava_tokens.json`): fora do SPEC, cria um arquivo temporário para remover na Fase 2.
- **Bloquear Fase 1 na Fase 2**: inverter a ordem viola o princípio fase-a-fase do roadmap.

## Consequências
- As migrations da Fase 2 devem usar `CREATE TABLE IF NOT EXISTS` para `oauth_tokens` (obrigatório de qualquer forma para idempotência).
- Os tokens já estão exatamente onde o SPEC diz que devem estar desde o primeiro `setup`.
- Nenhum arquivo temporário para limpar.
