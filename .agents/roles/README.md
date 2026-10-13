# Roles (subagentes neutrales)

Cada fichero define un rol que `scripts/sync_agents.py` convierte en el subagente nativo de cada
agente (`.claude/agents/*.md`, `.codex/agents/*.toml`…). En agentes sin subagentes, el rol se
ejecuta en una sesión aparte siguiendo este fichero.

Frontmatter:
- `name`, `description`: obligatorios.
- `tier`: `fast` o `capable`. Cada agente lo traduce a un modelo según `.agents/manifest.yaml`.
- `tools`: herramientas lógicas mínimas que necesita el rol. `mcp:<herramienta>` para la
  interfaz de CandidatAI; `read`, `search`, `git_read` y `web` para capacidades genéricas. Donde el
  agente permite restringir herramientas, el rol solo tendrá estas.
- `sandbox`: `read-only` si el rol no debe escribir ficheros ni ejecutar comandos que modifiquen nada.
