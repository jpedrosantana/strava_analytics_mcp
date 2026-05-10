#!/usr/bin/env bash
# Inicia o dashboard Streamlit local.
# Uso: ./scripts/dashboard.sh
# Acesse http://localhost:8501 (Ctrl+C para parar).
#
# Requer warehouse construído: ./scripts/transform.sh build
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --group dashboard streamlit run dashboard/Home.py
