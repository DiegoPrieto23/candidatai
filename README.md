# Job Hunter · kit de arranque

Especificación, encargos por fase, skills y roles para construir y operar una app local de
búsqueda de empleo (FastAPI + React + SQLite) **con el agente de IA que prefieras**: Claude Code,
Codex (ChatGPT), Gemini CLI, Cursor, Copilot… La app no llama a ninguna API de LLM: el
razonamiento lo pone la suscripción que ya tengas.

Inspirado en [ackyer/job-search-agent-template](https://github.com/ackyer/job-search-agent-template)
(MIT), reconvertido de plantilla de prompts a aplicación con estado en base de datos.

## Qué necesita tu agente

Poder **leer y escribir ficheros** en la carpeta y, además, **hablar MCP o ejecutar comandos**.
Con MCP es más cómodo; sin MCP, usa la CLI `jh … --json`, que es equivalente.
Detalle por agente y garantías de seguridad: `docs/AGENTS_COMPAT.md`.

## Qué hay en el kit

```
AGENTS.md                  instrucciones del proyecto para CUALQUIER agente
CLAUDE.md, GEMINI.md       solo importan AGENTS.md
docs/
  ARCHITECTURE.md          capas, etapas, quién hace qué, seguridad en profundidad
  DATA_MODEL.md            tablas, catálogo de eventos, proyección de etapas
  AGENT_INTERFACE.md       herramientas MCP ↔ comandos CLI, y esquemas que rellena el agente
  POLICIES.md              reglas de negocio: veracidad, CV, privacidad, candidaturas
  AGENTS_COMPAT.md         matriz de agentes soportados y cómo añadir uno
  ROADMAP.md               12 fases con su estado
  DECISIONS.md             ADRs (sin API, SQLite, docxtpl, neutralidad de agente…)
prompts/01…12-*.md         el encargo de cada fase
.agents/                   FUENTE ÚNICA para agentes
  skills/                  8 skills en el estándar Agent Skills (Codex los lee directamente)
  roles/                   subagentes neutrales: extractor, redactor, verificador, revisor
  manifest.yaml            lo específico de cada agente (rutas, modelos, MCP, extras)
scripts/sync_agents.py     genera la configuración nativa desde .agents/
.claude/  .codex/  .mcp.json   GENERADOS (no editar a mano; se commitean)
.claude/settings.json      permisos de Claude Code (este sí, a mano)
config/                    políticas genéricas, sinónimos de skills, patrones de inyección
demo/profile.example.yaml  esquema del perfil con una candidata ficticia
```

## Puesta en marcha (Windows 11)

1. Instala Git, [uv](https://docs.astral.sh/uv/), Node LTS + pnpm (`corepack enable`),
   LibreOffice y tu agente.
2. Copia el kit en una carpeta nueva y haz el primer commit:
   ```
   git init
   git add .
   git commit -m "Kit inicial"
   ```
3. Abre tu agente en esa carpeta y pide la primera fase:
   - Claude Code: `/implementar-fase 01`
   - Codex: `$implementar-fase 01`
   - Otros: "Lee AGENTS.md y usa el skill implementar-fase para la fase 01"

## Cómo construir cada fase

```
implementar-fase NN   →  el agente lee el encargo y propone un plan
revisas y apruebas    →  implementa con tests
pruebas manuales      →  las que te indique
commit                →  cuando estés conforme
sesión nueva          →  contexto limpio para la siguiente fase
```

Con la fase 08 terminada ya tienes un MVP usable: alta de ofertas, triaje y CVs verificados.

**Para no quemar cuota, con cualquier plan:** una fase por sesión, plan antes de código, modelo
"capaz" para construir y "rápido" para los roles mecánicos (se configura en el manifiesto), y
commits pequeños para deshacer con git en vez de con el agente.

## Si cambias skills, roles o el manifiesto

Edita solo `.agents/` y regenera desde la raíz:

```
uv run scripts/sync_agents.py           # escribe .claude/, .codex/ y .mcp.json
uv run scripts/sync_agents.py --check   # lo mismo que comprueba la CI
```

## Cómo usar la app una vez construida

Arranca `jh serve`, `jh worker` y `pnpm dev`. Después, en tu agente:

| Skill | Qué hace |
|---|---|
| `actualizar-perfil` | Crea o actualiza `data/profile.yaml` desde tu CV y lo versiona |
| `procesar-ofertas` | Extrae las ofertas nuevas (rol `extractor`, aislado cuando el agente lo permite) |
| `evaluar-encaje` | Valora y explica el encaje de las ofertas de triaje |
| `generar-cv 42` | Redacta, renderiza y verifica el CV para la oferta 42 |
| `preparar-candidatura 42` | Respuestas de screening y carta, si hace falta |
| `preparar-entrevista 42 tecnica` | Dosier de entrevista y simulacro |
| `resumen-diario` | Qué tienes hoy, seguimientos vencidos, qué procesar |

Si tu agente ofrece tareas programadas, `procesar-ofertas` y `resumen-diario` pueden ejecutarse
solos cada mañana (se documenta al terminar la fase 09).

## Límites deliberados

- Nada se envía sin tu confirmación en la UI, candidatura a candidatura.
- LinkedIn nunca se automatiza y los captchas no se esquivan: la app prepara y tú terminas.
- El CV solo contiene lo que está en tu perfil; lo comprueban el código y un rol verificador independiente.
- Las defensas contra ofertas manipuladas están en el código, así que protegen con cualquier agente.
- Tus datos viven en `data/`, fuera del repositorio. El repo público usa el modo demo.

## Desarrollo

### Requisitos en Windows 11

- **uv** (gestiona Python 3.12 por su cuenta; no hace falta instalar Python aparte):
  ```
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Node LTS** y **pnpm**. Desde Node 25, `corepack` ya no viene incluido; instala pnpm con
  `npm install -g pnpm` (o `corepack enable` si tu Node lo trae). La versión exacta está en
  `frontend/package.json` (`packageManager`).
- **LibreOffice** (para convertir CVs a PDF, a partir de la fase 08). Si no está en
  `C:\Program Files\LibreOffice` ni en el `PATH`, define `SOFFICE_PATH` en `.env`.

Abre una terminal nueva tras instalar para que el `PATH` se actualice.

### Configuración

Copia `.env.example` como `.env` en la raíz si necesitas cambiar algo; por defecto no hace falta.
Los datos personales van en `data/` (se crea sola y está en `.gitignore`).

### Backend

```
cd backend
uv sync                            # instala dependencias (crea .venv)
uv run jh doctor                   # comprueba el entorno
uv run pytest                      # tests
uv run ruff check --fix && uv run ruff format
```

### Frontend

```
cd frontend
pnpm install
pnpm dev                           # http://127.0.0.1:5173
pnpm typecheck && pnpm test && pnpm build
```

### CI

`.github/workflows/ci.yml` ejecuta ruff y pytest (en Windows), typecheck, test y build del
frontend, y `uv run scripts/sync_agents.py --check`. No necesita secretos.
