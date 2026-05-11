"""Seed athlete_config com valores fisiológicos do atleta.

Os valores aqui sobrescrevem qualquer entrada existente. Atualize conforme
um novo teste de FCmáx, LTHR (média de FC em meias maratonas de prova),
ou medição refinada de FCrest. Reexecute `compute-metrics --recompute`
após mudar valores para reprocessar os marts.

Valores atuais (cf. CLAUDE.md > Perfil do atleta):
    FCmáx  = 201 bpm  (Teste de 6Km em 28/02/2026)
    LTHR   = 177 bpm  (média das FC em meias maratonas de prova: 173-179 bpm)
    FCrest = 50 bpm   (placeholder; medir ao acordar para refinar)
    sex    = male

Não populamos threshold_pace_mps aqui — gap separado tracked no BACKLOG.md
como [Alta] "Investigar r_tss sempre NULL".
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "strava.db"

ENTRIES: dict[str, str] = {
    "lthr": "177",
    "hr_max": "201",
    "hr_rest": "50",
    "sex": "male",
}


def main(db_path: Path = DEFAULT_DB) -> None:
    if not db_path.exists():
        print(f"erro: banco não encontrado em {db_path}", file=sys.stderr)
        sys.exit(1)

    now = datetime.utcnow().isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for key, value in ENTRIES.items():
            conn.execute(
                """
                INSERT INTO athlete_config (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
        conn.commit()

        print("athlete_config após seed:")
        for row in conn.execute("SELECT key, value, updated_at FROM athlete_config ORDER BY key"):
            print(f"  {row[0]:20s} = {row[1]:<10s} (updated {row[2]})")


if __name__ == "__main__":
    db_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    main(db_arg)
