#!/usr/bin/env bash
# Roda o pipeline dbt do projeto BI.
# Uso: ./scripts/transform.sh [comando-dbt opcional, default: build]
#   ./scripts/transform.sh                # dbt build
#   ./scripts/transform.sh debug          # dbt debug
#   ./scripts/transform.sh test            # dbt test
#   ./scripts/transform.sh run --select stg_strava__activities
set -euo pipefail
cd "$(dirname "$0")/../dbt"
exec uv run --group dbt dbt "${@:-build}"
