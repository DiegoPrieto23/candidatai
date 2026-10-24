# Fase 02 · Núcleo de datos

## Contexto
Lee `docs/DATA_MODEL.md` entero y `docs/ARCHITECTURE.md` §Capas.

## Objetivo
Esquema completo, migraciones, registro de eventos y proyección de etapas, todo con tests.

## Alcance
1. `app/core/db.py`: engine SQLite con WAL y `foreign_keys=ON`, sesión por contexto.
2. `app/models/`: todas las tablas de `DATA_MODEL.md`.
3. Alembic configurado para leer la URL de `Settings`; migración inicial.
4. `app/services/events.py`: `record(session, job_id, type, actor, payload=None, occurred_at=None)`.
   Valida que el tipo existe en el catálogo y que la transición es válida; tras registrar,
   actualiza la proyección en `applications`.
5. `app/services/pipeline.py`: enum `Stage`, `stage_for(events) -> Stage` y función para
   recalcular la proyección de una oferta o de todas.
6. `app/services/normalize.py`: normalización de empresa, título y ubicación, y huella.
   Tests con casos reales: "Acme S.L.", "ACME, S.A.", "Data Engineer (m/f/d)",
   "Sr. Data Engineer – Remote".
7. CLI: `jh db upgrade`, `jh status` (recuento por etapa) y `jh events list <job_id>`. Todos con
   opción `--json` (la fase 04 los convierte en parte de la interfaz para agentes).

## Fuera de alcance
Ingesta, API REST, MCP.

## Criterios de aceptación
- Tests de cada transición del catálogo, incluidas las inválidas (error explícito).
- Test de que recalcular la proyección desde cero da lo mismo que la proyección incremental.
- `uv run alembic upgrade head` crea `data/jobhunter.db`; `alembic downgrade base` la deja vacía.
- Cobertura de `services/` ≥ 85 %.

## Al terminar
Actualiza `dev/ROADMAP.md` y propón mensaje de commit.
