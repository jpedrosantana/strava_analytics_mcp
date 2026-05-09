# Instruções para Claude Code

Leia `docs/STRAVA_MCP_SPEC.md` integralmente antes de qualquer ação.

Implemente fase a fase, em ordem (Fases 0-8 do roadmap principal,
Fases D1-D7 do roadmap de dados em paralelo após Fase 2).

Pare ao fim de cada fase para confirmação humana antes de prosseguir.

Critérios de aceitação por fase estão no SPEC — atendê-los é obrigatório.

Decisões não cobertas: registrar em `docs/decisions/NNNN-titulo.md`
no formato ADR.

Melhorias futuras identificadas mas não priorizadas: registrar em
`docs/BACKLOG.md`. Antes de iniciar qualquer item dali, confirmar com
o usuário e mover para o roadmap principal ou criar ADR específico.

## Perfil do atleta

Parâmetros estimados pelo histórico de corridas (não de teste laboratorial):

- FCmáx: 201 bpm (registrado no Teste de 6Km em 28/02/2026)
- LTHR: 177 bpm (média das FC em meias maratonas de prova: 173–179 bpm)
- FCrest: 50 bpm (placeholder — medir ao acordar para refinar)
- Sexo: masculino
  
## Contexto de Treino/Objetivo Atual
Faço corrida e musculação há quase 1 ano e meio, minha rotina de treinos de musculação são de 2-3x na semana (sendo 2 de funcional e 1 musculação) e de corrida é de 3-4x na semana (normalmente 2 treinos de rodage, 1 intervalado/fartlek e 1 longão de sábado). Meu objetivo atual é melhorar minha performance na corrida, atualmente estou me preparando para uma maratona em Julho. Meu histórico de provas tem destaque com as meias maratonas, completei 7 até o momento e até a maratona tenho mais uma prova de 21Km e outra de 25Km para fazer.

## Status atual dos dados
Streams: 100% completos (299/299 atividades). Último download: 08/05/2026.
compute-metrics: executado em 08/05/2026 com streams 100% completos (EF e decoupling calculados via stream).
