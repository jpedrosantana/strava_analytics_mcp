"""Seed athlete_config com valores fisiológicos do atleta.

Os valores aqui sobrescrevem qualquer entrada existente. Atualize conforme
um novo teste de FCmáx, LTHR, threshold pace, ou medição refinada de FCrest.
Reexecute `compute-metrics` após mudar valores para reprocessar os marts.

Valores atuais:
    FCmáx              = 201 bpm    (Teste de 6Km em 28/02/2026)
    LTHR               = 177 bpm    (média das FC em meias maratonas de
                                     prova: 173-179 bpm)
    FCrest             = 50 bpm     (placeholder; medir ao acordar)
    threshold_pace_mps = 3.663 m/s  (4:33/km; ritmo sustentável por ~1h)
    sex                = male

Como o threshold pace foi estimado:
- Melhor meia recente: Mizuno Athenas 15/03/2026 — 21,22 km em 1:40:09
  (pace 4:43/km, FC média 175 ≈ LTHR 177)
- Tabela Daniels para HM 1:40 → VDOT ~48.4 → T-pace ~4:25/km
- Regra empírica HM_pace - 10s/km → 4:33/km
- Conversão 12km a 4:55 → 10K ~4:48 → T-pace ~4:35/km
- Convergência: ~4:30-4:35/km. Adotado meio-termo de 4:33/km = 3.663 m/s.

Revisitar após próxima meia oficial ou teste de campo (TT 3K / 30min).
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
    "threshold_pace_mps": "3.663",
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
