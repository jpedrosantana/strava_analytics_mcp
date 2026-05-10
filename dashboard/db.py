"""Helper de conexão e queries cacheadas pro warehouse DuckDB."""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "strava.duckdb"


@st.cache_resource(show_spinner=False)
def get_connection() -> duckdb.DuckDBPyConnection:
    """Conexão read-only ao warehouse. Reusada via cache_resource."""
    if not DB_PATH.exists():
        st.error(
            f"Warehouse não encontrado em `{DB_PATH}`. "
            "Rode `./scripts/transform.sh build` primeiro."
        )
        st.stop()
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(ttl=3600, show_spinner=False)
def query(sql: str) -> pd.DataFrame:
    """Executa SQL e retorna DataFrame. Cacheado por 1h."""
    return get_connection().execute(sql).df()
