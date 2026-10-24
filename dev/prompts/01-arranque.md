# Fase 01 · Arranque del repo

## Contexto
Lee `AGENTS.md` (probablemente ya en contexto), `docs/ARCHITECTURE.md` y `dev/DECISIONS.md`.

## Objetivo
Dejar el esqueleto del monorepo funcionando en Windows 11, sin lógica de negocio todavía.

## Alcance
1. `backend/` como proyecto `uv` (Python 3.12) con `pyproject.toml`:
   - dependencias: fastapi, uvicorn[standard], sqlalchemy>=2, alembic, pydantic>=2,
     pydantic-settings, typer, httpx, pyyaml;
   - dev: pytest, pytest-cov, ruff, respx;
   - ruff configurado (líneas de 100, reglas E, F, I, UP, B, SIM);
   - entry points: `jh = "app.cli:app"` y `jh-mcp = "app.mcp.server:main"` (este último,
     de momento, un stub que imprime un aviso y sale).
2. Paquete `app/` con `core/config.py`: `Settings` (pydantic-settings) con `JH_DATA_DIR`
   (por defecto `<raíz del repo>/data`, resuelto con pathlib desde la ubicación del paquete),
   `JH_DB_URL` derivada, `SOFFICE_PATH` opcional. Crea `data/` si no existe.
3. `app/cli.py` con Typer y un comando `jh doctor` que compruebe: versión de Python, que existe
   `data/` y si es escribible, si LibreOffice está accesible (aviso, no error) y si hay una
   plantilla de CV (aviso).
4. `frontend/` con Vite + React + TypeScript (pnpm), una página vacía "Job Hunter" y Vitest
   configurado con un test trivial.
5. `.env.example` con las variables anteriores comentadas.
6. `.github/workflows/ci.yml`: ruff y pytest en backend, typecheck, test y build en frontend, y
   `uv run scripts/sync_agents.py --check` (la configuración de agentes generada debe estar al
   día). Que no necesite secretos.
7. `README.md` de desarrollo con el arranque en Windows (uv, pnpm, LibreOffice). No reescribas
   el README del kit: añade una sección «Desarrollo».

## Fuera de alcance
Modelos, base de datos, API real, MCP real.

## Criterios de aceptación
- `cd backend && uv run pytest` pasa (al menos un test de `Settings` y otro de `jh doctor`).
- `uv run ruff check` limpio.
- `uv run jh doctor` muestra un informe legible en Windows.
- `cd frontend && pnpm test && pnpm build` pasan.
- `uv run scripts/sync_agents.py --check` pasa.
- `git status` no muestra nada bajo `data/`.

## Al terminar
Actualiza `dev/ROADMAP.md` y propón mensaje de commit.
