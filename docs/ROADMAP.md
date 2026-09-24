# Roadmap

Cada fase tiene su encargo en `prompts/NN-*.md`. Con cualquier agente: pídele "implementa la fase
NN" o usa el skill `implementar-fase` (`/implementar-fase 03` en Claude Code, `$implementar-fase 03`
en Codex). Al cerrar una fase, el agente actualiza su estado aquí.
Estados: ⏳ pendiente · 🚧 en curso · ✅ hecha.

| # | Fase | Estado | Resultado visible |
|---|---|---|---|
| 01 | Arranque del repo | ✅ | `uv run pytest` y `pnpm build` funcionan; CI mínimo con `sync_agents.py --check` |
| 02 | Núcleo de datos | ✅ | Esquema, migraciones, eventos, proyección de etapas, CLI `jh` |
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

### 01 · Arranque del repo — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** backend `uv` (Python 3.12) con `Settings`, `jh doctor` (texto y `--json`) y stub
  `jh-mcp`; frontend Vite + React + TS con Vitest; CI (backend en Windows, frontend, sync de
  agentes); sección «Desarrollo» en el README. 17 tests de backend y 1 de frontend.
- **Decisiones:** las comprobaciones de `doctor` viven en `app/services/doctor.py`; `JH_DATA_DIR`
  relativo se resuelve desde la raíz del repo, no desde el cwd; la CLI fuerza UTF-8 en
  stdout/stderr (en Windows, con salida por tubería, Python usa cp1252 y rompía tildes en
  `--json`); pnpm fijado con `packageManager` (Node 25 ya no trae corepack).
- **Deuda:** `.env.example` pendiente de crear a mano (la regla `Read(./.env.*)` de
  `.claude/settings.json` también lo bloquea para el agente); LibreOffice sin instalar en la
  máquina de desarrollo (necesario en la fase 08); cobertura sin umbral mínimo.

### 02 · Núcleo de datos — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** las 11 tablas de `DATA_MODEL.md` en `app/models/`, migración inicial `0001`,
  engine SQLite con WAL y claves foráneas, `services/events.record()`, `services/pipeline.py`
  (etapas, tabla de transiciones, proyección y recálculo), `services/normalize.py` (empresa,
  título, ubicación, huella) y CLI `jh db upgrade`, `jh status` y `jh events list` con `--json`.
  291 tests; cobertura de `services/` del 99 %, con un umbral del 85 % en CI.
- **Decisiones:**
  - `found` es el evento inicial, no una etapa.
  - Las etapas de origen válidas de cada evento están en `pipeline.TRANSITIONS` y se prueban
    las 210 combinaciones de evento y etapa. `applied` exige `cv_ready`; `applied_manually`
    es la vía alternativa.
  - `reopened` vuelve a la etapa previa al último cierre. `cv_verified` solo lleva a
    `cv_ready` con `payload.passed = true`.
  - `record()` reproduce todos los eventos de la oferta (por `occurred_at` y luego por `id`)
    antes de escribir. Así admite eventos con fecha pasada y un error no deja nada a medias.
  - Las fechas son `UTCDateTime`: se guardan en UTC y se rechazan las fechas sin zona.
  - Título normalizado: se quitan las etiquetas entre paréntesis de género, seniority y
    modalidad, y los sufijos de modalidad («– Remote»). Sr./Jr. se expanden y se conservan.
  - Los comandos que leen la BD fallan con «ejecuta `jh db upgrade`» si no está al día.
- **Deuda:**
  - `jh --help` muestra mal las tildes en consolas Windows con cp1252: Typer pinta la ayuda
    antes del callback que fuerza UTF-8. Ya pasaba en la fase 01.
  - El JSON de error de la CLI (`{ok: false, error}`) es provisional hasta fijar el formato de
    errores común con la MCP en la fase 04.
