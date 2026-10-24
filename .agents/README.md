# `.agents/` · fuente única para agentes

Aquí se escriben, una sola vez y sin nada específico de un agente, los **skills** (`skills/`), los
**roles** o subagentes (`roles/`) y lo propio de cada agente (`manifest.yaml`).
`scripts/sync_agents.py` genera desde aquí `.claude/`, `.codex/`, `.opencode/`, `.qwen/`, `.mcp.json`,
`opencode.json` y `.agents/mcp_config.json`: no son cuatro copias a mano, y no se editan.

This is the single source for agents: skills, roles (subagents) and per-agent settings are written
here once. `scripts/sync_agents.py` generates `.claude/`, `.codex/`, `.opencode/`, `.qwen/`,
`.mcp.json`, `opencode.json` and `.agents/mcp_config.json` from it; don't edit those by hand.

```
uv run scripts/sync_agents.py           # regenerar
uv run scripts/sync_agents.py --check   # CI: falla si lo generado no está al día
```

Cómo encaja cada agente: [`docs/AGENTS_COMPAT.md`](../docs/AGENTS_COMPAT.md).
