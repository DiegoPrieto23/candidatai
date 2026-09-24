"""Servidor MCP de Job Hunter. De momento, un stub (se implementa en la fase 04)."""

import io
import sys


def main() -> None:
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding="utf-8")
    print(
        "jh-mcp: el servidor MCP aún no está implementado (fase 04). "
        "Mientras tanto, usa la CLI: `uv run jh --help`.",
        file=sys.stderr,
    )
    sys.exit(1)
