"""Agente falso para los tests de «En segundo plano» (fase 19): imita `claude -p --output-format
stream-json` sin red ni LLM o, si su primer argumento es `run` (fase 24.5), `opencode run --format
json`. El modo sale de `FAKE_AGENT_MODE`; si hay `FAKE_AGENT_LOG`, escribe ahí sus
argumentos, si ve las variables que se debían quitar, su `CAI_CLIENT_NAME` y la configuración que
recibe en `OPENCODE_CONFIG_CONTENT`.

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
OC_SESSION = "ses_0f7c2d1eaaaaBBBBcccc12"
OC_CHILD = "ses_1a2b3c4dddddEEEEffff34"


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
            seen = {
                "argv": sys.argv[1:],
                "api_key": "ANTHROPIC_API_KEY" in os.environ,
                "client_name": os.environ.get("CAI_CLIENT_NAME"),
                "opencode_config": os.environ.get("OPENCODE_CONFIG_CONTENT"),
                "data_dir": os.environ.get("CAI_DATA_DIR"),
                "opencode_env": sorted(
                    k
                    for k in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR", "OPENCODE_PERMISSION")
                    if k in os.environ
                ),
            }
            json.dump(seen, fh)
    if mode == "crash":
        print("boom: algo ha ido mal", file=sys.stderr, flush=True)
        return 3
    if sys.argv[1:2] == ["run"]:  # como `opencode run`
        return opencode(mode)
    status = "failed" if mode == "nomcp" else "connected"
    emit(
        {
            "type": "system",
            "subtype": "init",
            "session_id": SESSION,
            "mcp_servers": [{"name": "candidatai", "status": status}],
            "tools": ["Skill", "Agent", "mcp__candidatai__list_jobs"],
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
        {"type": "tool_use", "id": "t1", "name": "mcp__candidatai__list_jobs", "input": {}},
        {"type": "tool_use", "id": "t2", "name": "Agent", "input": {"subagent_type": "extractor"}},
    )
    assistant(
        {
            "type": "tool_use",
            "id": "t3",
            "name": "mcp__candidatai__get_job",
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


def oc(kind: str, part: dict | None = None, session: str = OC_SESSION, **extra: object) -> None:
    emit(
        {
            "type": kind,
            "timestamp": 1792164979000 + int(time.time() * 1000) % 1000,
            "sessionID": session,
            **({"part": {"sessionID": session, **part}} if part is not None else {}),
            **extra,
        }
    )


def oc_tool(
    tool: str, status: str = "completed", session: str = OC_SESSION, **data: object
) -> None:
    state: dict[str, object] = {"status": status, "input": data}
    if status == "error":
        state["error"] = "The user rejected permission to use this specific tool call."
    else:
        state["output"] = "TEXTO DE LA OFERTA"  # nunca debe llegar al progreso
    oc("tool_use", {"type": "tool", "tool": tool, "state": state}, session)


def oc_finish(reason: str, session: str = OC_SESSION) -> None:
    tokens = {"total": 120, "input": 100, "output": 15, "reasoning": 5, "cache": {"read": 40}}
    oc(
        "step_finish",
        {"type": "step-finish", "reason": reason, "tokens": tokens, "cost": 0.01},
        session,
    )


def opencode(mode: str) -> int:
    """`opencode run --format json`: pasos, herramientas, texto y `step_finish` con su uso."""
    if mode == "garbage":
        print("Aviso: esto no es JSON", flush=True)
        print("{roto", flush=True)
    if mode == "child":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with open(os.environ["FAKE_AGENT_CHILD"], "w", encoding="utf-8") as fh:
            fh.write(str(child.pid))
    if mode == "error":
        oc(
            "error",
            error={"name": "APIError", "data": {"message": "El proveedor rechaza el modelo"}},
        )
        return 1
    oc("step_start", {"type": "step-start"})
    oc("text", {"type": "text", "text": "Voy a procesar las ofertas pendientes."})
    oc_tool("skill", name="process-jobs")
    oc_tool("candidatai_list_jobs")
    oc_tool("task", subagent_type="extractor", prompt="TEXTO DE LA OFERTA")
    oc_tool("candidatai_get_job", session=OC_CHILD, job_id=1)
    oc_finish("tool-calls", OC_CHILD)
    if mode == "denied":
        oc_tool("candidatai_add_event", status="error", job_id=1)
    oc_finish("tool-calls")
    if mode in ("hang", "child"):
        time.sleep(60)
        return 0
    if mode == "denied":
        print("! permission requested: candidatai_add_event (*); auto-rejecting", file=sys.stderr)
        return 0  # OpenCode se para tras una denegación, sin paso final
    oc("step_start", {"type": "step-start"})
    if mode == "question":
        text = "No he podido terminar.\n\nPREGUNTA: ¿Con foto o sin foto?"
    else:
        text = "Procesadas 2 ofertas, 0 fallidas."
    oc("text", {"type": "text", "text": text})
    oc_finish("stop")
    if mode == "linger":
        time.sleep(60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
