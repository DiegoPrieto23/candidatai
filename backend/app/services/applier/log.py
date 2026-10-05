"""Registro detallado de cada intento en `data/logs/applier/<intento>.jsonl`, un paso por línea.

Nunca guarda valores personales (correo, teléfono, respuestas): solo pasos, etiquetas de los campos
(texto de la web), tiempos y errores.
"""

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.models.base import utcnow


def log_path(attempt_id: int) -> Path:
    return get_settings().logs_dir / "applier" / f"{attempt_id}.jsonl"


class AttemptLog:
    def __init__(self, attempt_id: int) -> None:
        self.path = log_path(attempt_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, step: str, ok: bool = True, **info: Any) -> None:
        line = {"at": utcnow().isoformat(timespec="milliseconds"), "step": step, "ok": ok, **info}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")

    @contextmanager
    def step(self, step: str, **info: Any) -> Iterator[None]:
        """Registra el paso con su duración, y el error si falla (y lo deja pasar)."""
        start = time.monotonic()
        try:
            yield
        except Exception as exc:
            ms = round((time.monotonic() - start) * 1000)
            self.write(step, ok=False, ms=ms, error=f"{type(exc).__name__}: {exc}"[:500], **info)
            raise
        self.write(step, ms=round((time.monotonic() - start) * 1000), **info)
