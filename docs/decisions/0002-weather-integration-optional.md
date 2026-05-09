# ADR 0002 — Integração climática como opcional

**Status:** Aceito  
**Data:** 2026-05-09

## Contexto

O spec original da Fase 5 incluía integração com Open-Meteo para enriquecer atividades com dados de clima (temperatura, umidade, vento, precipitação) e uma tool `analyze_weather_impact`.

Ao investigar o payload da API do Strava, verificou-se que o campo `average_temp` já está disponível nativamente — vindo do sensor do dispositivo (Garmin). Cobertura: 124/300 atividades (41%), somente temperatura.

## Decisão

A integração com Open-Meteo é **postergada e marcada como opcional**. A Fase 5 será implementada focando exclusivamente em predições de prova (Riegel, VDOT, personal records).

Motivos:
1. O `average_temp` do Strava já cobre o dado mais relevante para 41% do histórico
2. Para o objetivo atual (maratona em julho), predição de tempo tem impacto direto; análise climática não
3. Open-Meteo adicionaria complexidade de backfill paginado sem retorno imediato

## Consequências

- `analytics/weather.py` e a tool `analyze_weather_impact` **não serão implementados** na Fase 5
- O campo `average_temp` do `raw_json` pode ser extraído para coluna própria oportunamente, sem dependência externa
- Se implementado no futuro: usar Open-Meteo apenas como fallback para atividades sem `average_temp`
