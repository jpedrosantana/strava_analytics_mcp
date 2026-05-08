import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def apply_migrations(db_path: str) -> None:
    """Apply schema idempotently. Safe to call multiple times."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    schema = _SCHEMA_PATH.read_text()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
