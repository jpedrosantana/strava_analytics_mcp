# ADR 0003 — Escopo do CI/CD num projeto local-first

**Status:** Aceito
**Data:** 2026-05-09

## Contexto

A versão original da Fase 9 (Polish e portfólio) incluía um workflow de GitHub Actions agendado (cron diário) executando `sync` + `compute-metrics`, com badge de status no README.

Esse desenho assumia estado remoto compartilhado, mas a arquitetura é deliberadamente **local-first**:
- Banco SQLite em `./data/strava.db` no PC do autor
- Tokens OAuth armazenados na mesma DB
- Single-user, sem servidor

Um sync rodando no GitHub Actions exigiria mover banco e tokens para storage remoto (S3, Artifacts, Secrets encriptados) com lógica de recuperação de estado entre runs efêmeros — alto custo de complexidade para um item cuja função é entregar um badge no README.

## Decisão

**O GitHub Actions da Fase 9 será de CI (lint + testes), não de sync agendado.** O exemplo de agendamento local (systemd timer ou crontab) é documentado no `docs/TROUBLESHOOTING.md` ou seção dedicada, alinhado com a natureza local-first do projeto.

Motivos:
1. Coerência arquitetural — sync é uma tarefa local; agendamento também deve ser
2. Badge "tests passing" é o que faz sentido para um projeto open-source local
3. Reduz custo de manutenção (zero infra remota)
4. Não bloqueia evolução futura — se algum dia o projeto virar multi-user, um workflow remoto pode ser adicionado sem desfazer nada

## Consequências

- Fase 9 substitui o item "GitHub Actions: sync diário" por "GitHub Actions: CI (lint + testes) com badge"
- `docs/TROUBLESHOOTING.md` ganha exemplo de cron/systemd local para agendamento de sync
- O item "Pipeline pós-sync automático" no `BACKLOG.md` continua relevante (independe desta decisão)
- Se a integração climática (cf. [ADR 0002](0002-weather-integration-optional.md)) for retomada com backfill remoto, esta decisão pode ser revisitada
