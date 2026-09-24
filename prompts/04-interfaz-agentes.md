# Fase 04 · Interfaz para agentes: MCP + CLI

## Contexto
Lee `docs/AGENT_INTERFACE.md` entero, `docs/ARCHITECTURE.md` §Fronteras de seguridad,
`docs/AGENTS_COMPAT.md`, `docs/DECISIONS.md` (ADR-010 a ADR-012) y `.agents/roles/extractor.md`.

## Objetivo
Que cualquier agente opere la app: ver el estado, dar de alta ofertas y extraerlas, por MCP o por
CLI, con el mismo resultado.

## Alcance
1. Dependencia `mcp` (SDK oficial de Python). `app/mcp/server.py` con FastMCP, transporte stdio y
   `main()` como entry point `jh-mcp`. Nunca escribir a stdout fuera del protocolo (los logs van a
   stderr o a `data/logs/`).
2. Herramientas de la fase 04: `get_status`, `add_job_from_url`, `add_job_from_text`, `list_jobs`,
   `get_job`, `save_extraction`, `get_extraction`, `add_event` y `get_timeline`.
3. **Comandos CLI equivalentes** según la tabla de `AGENT_INTERFACE.md`, con `--json` y `--file`
   para entradas largas (solo rutas dentro de `data/tmp/`; se borran tras procesarse bien).
4. **Una sola definición por herramienta**: un registro en `app/agent_interface/` con nombre,
   modelo de entrada, modelo de salida y servicio, del que se derivan la herramienta MCP y el
   comando CLI. Así la paridad sale por construcción.
5. `app/schemas/llm_io.py` con `JobExtraction` (schema_version 1), exactamente como en el doc.
6. `get_job` envuelve el texto en `<untrusted_job_posting id="…" risk_flags="…">`, escapando
   cualquier aparición de esa etiqueta dentro del propio texto.
7. `save_extraction`: valida y guarda. Si el agente marca `injection_suspected`, registra además el
   evento con el extracto y actor `agent`. Tras guardar, el evento `extracted` (los filtros duros
   llegan en la fase 07).
8. Auditoría en `mcp_calls` con `channel` (`mcp` o `cli`) y `client_name` si el cliente MCP lo
   informa en la inicialización (`claude-code`, `codex`…); también en `events.agent_name`.
9. Errores de validación legibles e idénticos en ambos canales: campo, valor recibido y motivo.
10. Integra el generador: `jh agents sync` y `jh agents check` llaman a `scripts/sync_agents.py`
    (sin duplicar su lógica).

## Fuera de alcance
Perfil, matching y CV.

## Criterios de aceptación
- Test de paridad: para cada herramienta, misma entrada por MCP (en proceso) y por CLI (`--json`)
  → misma salida y mismos errores.
- Test de que `get_job` no permite romper el envoltorio.
- **Claude Code**: tras reiniciarlo, `/mcp` muestra `jobhunter` conectado; `jh jobs add-text` con
  una oferta de `demo/` y luego `/procesar-ofertas` deja la oferta en `pending_triage`.
- **Codex**: con `.codex/config.toml` cargado, el servidor aparece disponible, y `$procesar-ofertas`
  hace lo mismo con otra oferta demo. Si el usuario aún no tiene Codex configurado, deja la prueba
  como pendiente en `docs/ROADMAP.md`.
- **Sin MCP**: el mismo flujo con solo comandos `jh … --json` funciona (simúlalo en un test de extremo a extremo).

## Al terminar
Actualiza `docs/ROADMAP.md` y `docs/AGENTS_COMPAT.md` con lo observado. Recuerda al usuario que
cada agente puede pedir aprobar el servidor MCP del proyecto la primera vez.
