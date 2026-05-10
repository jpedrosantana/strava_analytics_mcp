#!/usr/bin/env bash
# Gera e serve a documentação do projeto dbt.
# Uso: ./scripts/dbt_docs.sh
# Acesse http://localhost:8080 (Ctrl+C para parar).
set -euo pipefail
cd "$(dirname "$0")/../dbt"
uv run --group dbt dbt docs generate
exec uv run --group dbt dbt docs serve
