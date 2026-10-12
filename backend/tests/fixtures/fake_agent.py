"""Agente falso para los tests de «En segundo plano» (fase 19): imita `claude -p --output-format
stream-json` sin red ni LLM. El modo sale de `FAKE_AGENT_MODE`; si hay `FAKE_AGENT_LOG`, escribe ahí
sus argumentos y si ve las variables que se debían quitar.

Modos: `ok`, `question`, `error`, `denied`, `hang`, `nomcp`, `crash`, `garbage` (líneas que no son
JSON), `linger` (responde y no sale) y `child` (lanza un hijo que se queda colgado y deja su pid en
`FAKE_AGENT_CHILD`).
"""

import json
import os
import subprocess
import sys
import time

SESSION = "0f7c2d1e-aaaa-bbbb-cccc-123456789abc"


def emit(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def assistant(*blocks: dict, parent: str | None = None) -> None:
    emit(
        {
            "type": "assistant",
            "session_id": SESSION,
            "parent_tool_use_id": parent,
            "message": {"content": list(blocks)},
        }
    )


def result(text: str, subtype: str = "success", **extra: object) -> None:
    emit(
        {
            "type": "result",
            "subtype": subtype,
            "is_error": subtype != "success",
            "result": text,
            "session_id": SESSION,
            "num_turns": 4,
            "duration_ms": 1234,
            "total_cost_usd": 0.0,
            **extra,
        }
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # como el agente real, aunque la consola sea cp1252
    mode = os.environ.get("FAKE_AGENT_MODE", "ok")
    if log := os.environ.get("FAKE_AGENT_LOG"):
        with open(log, "w", encoding="utf-8") as fh:
            json.dump({"argv": sys.argv[1:], "api_key": "ANTHROPIC_API_KEY" in os.environ}, fh)
    if mode == "crash":
        print("boom: algo ha ido mal", file=sys.stderr, flush=True)
        return 3
    status = "failed" if mode == "nomcp" else "connected"
    emit(
        {
            "type": "system",
            "subtype": "init",
            "session_id": SESSION,
            "mcp_servers": [{"name": "jobhunter", "status": status}],
            "tools": ["Skill", "Agent", "mcp__jobhunter__list_jobs"],
        }
    )
    if mode == "nomcp":
        time.sleep(30)  # el runner debe pararlo antes
        return 0
    if mode == "garbage":
        print("Aviso: esto no es JSON", flush=True)
        print("{roto", flush=True)
        print("[1, 2]", flush=True)
    if mode == "child":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with open(os.environ["FAKE_AGENT_CHILD"], "w", encoding="utf-8") as fh:
            fh.write(str(child.pid))
    assistant({"type": "text", "text": "Voy a procesar las ofertas pendientes."})
    assistant(
        {"type": "tool_use", "id": "t1", "name": "mcp__jobhunter__list_jobs", "input": {}},
        {"type": "tool_use", "id": "t2", "name": "Agent", "input": {"subagent_type": "extractor"}},
    )
    assistant(
        {
            "type": "tool_use",
            "id": "t3",
            "name": "mcp__jobhunter__get_job",
            "input": {"job_id": 1, "secreto": "TEXTO DE LA OFERTA"},
        },
        parent="t2",
    )
    emit(
        {
            "type": "user",
            "session_id": SESSION,
            "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "[]"}]},
        }
    )
    if mode in ("hang", "child"):
        time.sleep(60)
        return 0
    if mode == "question":
        result(
            "No he podido terminar.\n\n"
            "- PREGUNTA: La oferta 3 parece cerrada, ¿redacto igualmente?\n"
            "**PREGUNTA:** ¿Con foto o sin foto?"
        )
    elif mode == "error":
        result("Se acabaron los turnos", subtype="error_max_turns")
    elif mode == "denied":
        result(
            "Hecho a medias.",
            permission_denials=[{"tool_name": "Bash", "tool_use_id": "t9", "tool_input": {}}],
        )
    else:
        result("Procesadas 2 ofertas, 0 fallidas.")
    if mode == "linger":
        time.sleep(60)  # el runner debe pararlo tras el resultado
    return 0


if __name__ == "__main__":
    sys.exit(main())
