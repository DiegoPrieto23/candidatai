# Roadmap

Cada fase tiene su encargo en `prompts/NN-*.md`. Con cualquier agente: pídele "implementa la fase
NN" o usa el skill `implementar-fase` (`/implementar-fase 03` en Claude Code, `$implementar-fase 03`
en Codex). Al cerrar una fase, el agente actualiza su estado aquí.
Estados: ⏳ pendiente · 🚧 en curso · ✅ hecha.

| # | Fase | Estado | Resultado visible |
|---|---|---|---|
| 01 | Arranque del repo | ⏳ | `uv run pytest` y `pnpm build` funcionan; CI mínimo con `sync_agents.py --check` |
| 02 | Núcleo de datos | ⏳ | Esquema, migraciones, eventos, proyección de etapas, CLI `jh` |
| 03 | Alta de ofertas | ⏳ | `jh jobs add-url` y `add-text` crean ofertas deduplicadas y con `risk_flags` |
| 04 | Interfaz para agentes | ⏳ | Servidor MCP + CLI con paridad; funciona desde Claude Code y Codex |
| 05 | Perfil del candidato | ⏳ | `data/profile.yaml` validado y versionado; `get_profile` |
| 06 | Frontend base | ⏳ | UI con bandeja de ofertas, ficha y alta por URL |
| 07 | Matching y triaje | ⏳ | Filtros duros, score, skill `evaluar-encaje`, aprobar o descartar en la UI |
| 08 | CV a medida | ⏳ | Skill `generar-cv` produce DOCX + PDF verificados |
| 09 | Conectores de ATS y scheduler | ⏳ | Ingesta diaria de empresas objetivo sin intervención |
| 10 | Seguimiento y analítica | ⏳ | Kanban, seguimientos pendientes, dashboard del embudo |
| 11 | Candidatura asistida | ⏳ | Rellenado con Playwright y envío tras tu confirmación |
| 12 | Demo, compatibilidad y portfolio | ⏳ | Modo demo, matriz de agentes probada, evals publicados |

**MVP usable:** al terminar la 08 ya puedes pegar ofertas, triarlas y sacar CVs a medida.

## Registro de fases

<!-- El agente añade aquí, al cerrar cada fase: fecha, agente usado, resumen de 2-3 líneas,
decisiones tomadas y deuda técnica pendiente. -->
