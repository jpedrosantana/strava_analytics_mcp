"""Cores semânticas e thresholds usados em mais de uma página."""

# Paleta semântica para TSB (Training Stress Balance / forma).
# Interpretação clássica do PMC chart.
TSB_FRESH = "#10b981"        # > +5: descansado / forma de prova
TSB_PRODUCTIVE = "#9ca3af"   # -10 a +5: produtivo, treinando bem
TSB_LOADED = "#f59e0b"       # -30 a -10: carregado
TSB_RISK = "#ef4444"         # < -30: risco / deload sugerido

TSB_FRESH_THRESHOLD = 5
TSB_PRODUCTIVE_THRESHOLD = -10
TSB_LOADED_THRESHOLD = -30

# ACWR (Acute:Chronic Workload Ratio) — sweet spot da literatura.
ACWR_LOW = 0.8
ACWR_HIGH = 1.3


def tsb_color(tsb: float) -> str:
    if tsb > TSB_FRESH_THRESHOLD:
        return TSB_FRESH
    if tsb > TSB_PRODUCTIVE_THRESHOLD:
        return TSB_PRODUCTIVE
    if tsb > TSB_LOADED_THRESHOLD:
        return TSB_LOADED
    return TSB_RISK


def tsb_label(tsb: float) -> str:
    if tsb > TSB_FRESH_THRESHOLD:
        return "Fresh"
    if tsb > TSB_PRODUCTIVE_THRESHOLD:
        return "Productive"
    if tsb > TSB_LOADED_THRESHOLD:
        return "Carregado"
    return "Risco"
