"""Uso de una ejecución en segundo plano (fase 25.4): las mismas claves para todos los agentes.

Cada lector de `agent_output.py` rellena lo que da su agente; lo que falta no se estima. Las filas
de antes de la fase usaban otros nombres y `normalize_usage` los traduce al leer.
"""

from typing import Any

# Claves comunes del uso de una ejecución. `cached_tokens`: los de entrada leídos de caché.
USAGE_KEYS = ("input_tokens", "output_tokens", "cached_tokens", "turns", "duration_ms", "cost_usd")
# Nombres de antes de la fase 25.4 (filas ya guardadas).
LEGACY_USAGE_KEYS = {
    "num_turns": "turns",
    "total_cost_usd": "cost_usd",
    "cache_read_tokens": "cached_tokens",
}


def normalize_usage(raw: dict[str, Any] | None) -> dict[str, int | float]:
    """Solo las claves comunes con un número (las de antes, traducidas). Vacío si no hay uso."""
    out: dict[str, int | float] = {}
    for key, value in (raw or {}).items():
        name = LEGACY_USAGE_KEYS.get(key, key)
        if name in USAGE_KEYS and isinstance(value, int | float) and not isinstance(value, bool):
            out.setdefault(name, value)
    return out
