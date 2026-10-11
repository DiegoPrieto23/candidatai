# Fase 19 · Lote en segundo plano y cola de encargos

Plan 13-22 (`docs/ROADMAP.md`). Rama `fase/19-lote-segundo-plano`. Es la fase 2 que dejó abierta la
ADR-024; inspirada en `batch`, `pipeline` y `agent-inbox` de career-ops.

## Contexto
Lee `docs/DECISIONS.md` ADR-001, ADR-012 y ADR-024, `services/agent_launch.py`, `services/worker.py`
y `docs/AGENTS_COMPAT.md`.

## Objetivo
Que los skills que no necesitan preguntarte (procesar ofertas, evaluar encaje, CV sin skills que
falten) se ejecuten sin abrir ventana, con el progreso en la UI, y sin coste de API.

## Alcance
1. **`launch.headless`** en `.agents/manifest.yaml` por agente (p. ej. Claude Code:
   `[claude, -p, "{prompt}", --output-format, stream-json, --allowedTools, "mcp__jobhunter__*"]`;
   Codex: `codex exec …`), con el mismo `unset_env`. Solo herramientas del MCP de la app: sin
   terminal, ficheros ni web (el texto de las ofertas no es de fiar).
2. **Tarea del worker** `agent_run` (tabla `agent_runs`, migración): lanza el proceso, lee la
   salida en streaming, guarda progreso, resultado y errores; tiempo máximo y cancelación. Una
   sola ejecución a la vez.
3. **Qué puede ir en segundo plano**: `procesar-ofertas`, `evaluar-encaje` y `generar-cv` (si
   `get_match` no tiene obligatorias ausentes que pregunten). Si el skill necesita algo del
   usuario, termina y deja la pregunta en la UI («Abrir en terminal» para seguir).
4. **Cola de encargos** (`agent-inbox`): encargos que la UI deja para la próxima sesión
   interactiva del agente; herramienta `list_agent_requests` / `complete_agent_request`.
5. **UI**: en cada botón ADR-024, «En segundo plano» además de «En terminal»; panel de ejecuciones
   con estado y salida resumida.
6. **Docs**: ADR nueva (extiende la 024), `AGENTS_COMPAT.md` (qué agentes lo soportan).

## Fuera de alcance
Paralelizar varias ejecuciones. Modelos locales o de pago desde la app (ADR-001).

## Criterios de aceptación
- Tests con un agente falso (script que imita `stream-json`), sin red ni LLM.
- Las herramientas permitidas se comprueban en el comando generado (test).
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde.
