# Contribuindo

Este é um projeto pessoal mantido por um único autor. Issues são bem-vindas; PRs são aceitos **por convite** após discussão prévia em uma issue.

## Rodando localmente

Pré-requisitos: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), conta Strava com app criado em [developers.strava.com](https://developers.strava.com).

```bash
git clone https://github.com/jpedrosantana/strava_analytics_mcp
cd strava_analytics_mcp
cp .env.example .env       # preencha CLIENT_ID e CLIENT_SECRET
uv sync --all-groups
uv run strava-mcp setup    # OAuth — abre navegador
uv run strava-mcp sync --full --streams --compute
```

Verificações antes de abrir PR:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

A CI (`.github/workflows/ci.yml`) roda exatamente esses três comandos. Se passa local, passa no CI.

## Abrindo issues

Abra uma issue para qualquer um dos casos:
- Bug com passos para reproduzir
- Sugestão de melhoria (analítica, métrica nova, ajuste de tool MCP)
- Dúvida sobre arquitetura ou roadmap (cf. [`docs/STRAVA_MCP_SPEC.md`](docs/STRAVA_MCP_SPEC.md))

Antes de propor algo grande, vale conferir [`docs/BACKLOG.md`](docs/BACKLOG.md) — pode já estar listado.

## Pull requests

PRs são por convite. Se uma issue evoluir para "vamos fazer", o autor convida você a abrir o PR. Caminho:

1. Fork e branch a partir de `master` (`feat/...`, `fix/...`, `docs/...`)
2. Commits seguindo o padrão da próxima seção
3. PR descrevendo: motivação, mudanças, test plan
4. CI verde antes de pedir review

## Padrão de commit

Estilo **imperativo no presente**, sem prefixos de tipo. Três regras:

1. **Imperativo no presente** — primeira palavra completa "Se aplicado, este commit vai ___":
   - ✅ `Add NGP calculation to analytics`
   - ✅ `Fix 429 retry header parsing`
   - ❌ `Added NGP...` / `Adds NGP...` / `Adding NGP...`
2. **Primeira linha ≤ 72 caracteres**, sem ponto final.
3. **Corpo opcional** explicando *por quê* a mudança é necessária — o diff mostra *o quê*. Linha em branco entre subject e corpo.

Exemplo:

```
Document local cron scheduling for sync

CI workflow from Phase 0 already covers lint + format + tests. Phase 9
only needed operational guidance for periodic sync on the author's
machine, per ADR 0003.
```

Se um commit nasceu de uma sessão de pair com Claude Code, o trailer `Co-Authored-By: Claude <noreply@anthropic.com>` é adicionado automaticamente — preserve.

## Padrão de teste

Testes vivem em `tests/`, espelhando a estrutura de `strava_mcp/`. Funções analíticas devem ser testadas com dados sintéticos (fixtures em `tests/conftest.py` ou inline) — não dependa do banco real do autor.

## Código de conduta

Este projeto adota o [Código de Conduta](CODE_OF_CONDUCT.md) baseado no Contributor Covenant 2.1. Reportes para `jpedro.santana@outlook.com`.
