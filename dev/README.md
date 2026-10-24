# Desarrollo · Development

Lo interno de CandidatAI: cómo se construye fase a fase con un agente de IA. Para usar la app o
contribuir no hace falta nada de esto; empieza por [`docs/README.md`](../docs/README.md). `dev/` solo
está en el repositorio: no va en el zip de la release (`.gitattributes`).

CandidatAI's internals: how it is built phase by phase with an AI agent. You don't need any of this
to use the app or to contribute; start with [`docs/README.md`](../docs/README.md). Everything here
is in Spanish, and only in the repository: `dev/` isn't part of the release zip.

| Documento | Qué cuenta |
|---|---|
| [`DESARROLLO_POR_FASES.md`](DESARROLLO_POR_FASES.md) | El método: encargo, plan, rama, tests, revisión y registro |
| [`ROADMAP.md`](ROADMAP.md) | Estado de cada fase y su registro (decisiones y deuda) |
| [`RESUMEN_FASES.md`](RESUMEN_FASES.md) | Qué aporta cada fase, en corto |
| [`DECISIONS.md`](DECISIONS.md) | Las decisiones de arquitectura (ADR), con contexto y consecuencias |
| [`prompts/`](prompts/) | El encargo de cada fase (`NN-<slug>.md`); el skill `implement-phase` los lee de aquí |
| [`pruebas/`](pruebas/) | Guías de prueba manual por fase y pendientes del usuario ([`PENDIENTES.md`](pruebas/PENDIENTES.md)) |

## Qué hay en la raíz del repositorio

| Carpeta | Para qué |
|---|---|
| `backend/`, `frontend/` | La app: API, CLI `cai`, servidor MCP, worker y UI |
| `docs/` | Documentación para quien usa la app o contribuye |
| `dev/` | Esto |
| `.agents/` | Fuente única de skills, roles y manifiesto para agentes (ver [`.agents/README.md`](../.agents/README.md)) |
| `.claude/`, `.codex/`, `.opencode/`, `.qwen/`, `.mcp.json`, `opencode.json` | Generados desde `.agents/` por `scripts/sync_agents.py`; los agentes los buscan en la raíz |
| `config/`, `templates/`, `demo/` | Políticas y listas genéricas, plantillas de CV integradas y datos ficticios |
| `evals/` | Eval de matching (`cai eval matching`) |
| `extension/` | Extensión «Enviar a CandidatAI» |
| `scripts/` | Generar la configuración de agentes, las plantillas, los iconos y los medios del README, y comprobar enlaces |
| `install.ps1`, `install.sh`, `Dockerfile` | Instaladores y Docker |
