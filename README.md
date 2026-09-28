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
  CV_TEMPLATES.md          plantillas de CV, motores docx/html, foto y opciones por oferta
  AGENTS_COMPAT.md         matriz de agentes soportados y cómo añadir uno
  ROADMAP.md               12 fases con su estado
  DECISIONS.md             ADRs (sin API, SQLite, docxtpl, neutralidad de agente…)
prompts/01…12-*.md         el encargo de cada fase
.agents/                   FUENTE ÚNICA para agentes
  skills/                  10 skills en el estándar Agent Skills (Codex los lee directamente)
  roles/                   subagentes neutrales: extractor, redactor, verificador, revisor
  manifest.yaml            lo específico de cada agente (rutas, modelos, MCP, extras)
scripts/sync_agents.py     genera la configuración nativa desde .agents/
.claude/  .codex/  .mcp.json   GENERADOS (no editar a mano; se commitean)
.claude/settings.json      permisos de Claude Code (este sí, a mano)
templates/                 plantillas de CV integradas (se crean en las fases 08 y 08b)
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

## Cuándo entra tu CV real

Mientras se construye la app, el código se prueba siempre con datos ficticios de `demo/`: tus
datos nunca van al repositorio. Tu CV real entra dos veces, para cosas distintas, y siempre en
`data/` (fuera de git):

| Momento | Qué se usa de tu CV | Resultado |
|---|---|---|
| Al terminar la fase 05 | Su **contenido**: el agente lo lee con el skill `actualizar-perfil` y te pregunta lo que falte | `data/profile.yaml`, la fuente de verdad de todo lo que se escriba sobre ti |
| Desde la fase 08 | Su **diseño**: el skill `importar-plantilla-cv` convierte en plantilla cualquier CV tuyo o modelo que te guste (Word desde la 08; PDF, imagen o HTML desde la 08b). Puedes tener varias | `data/templates/<id>/`, junto a las integradas (`ats-simple`, `clasica-foto`, `moderna-2col`) |
| Cuando quieras | Tu **foto** | `data/photo.jpg` (o png); cada plantilla la recorta a su forma |

### Elegir estilo y foto en cada oferta

El agente redacta el contenido del CV una sola vez; la presentación la pone la app. En la ficha de
cada oferta eliges plantilla, foto (automática, con o sin), color de acento y secciones visibles, y
pulsas «Renderizar»: tarda segundos y **no gasta cuota del agente**. Puedes comparar renders lado
a lado y marcar cuál envías. Si no eliges nada, se aplican tus reglas (por ejemplo, `ats-simple`
sin foto para ofertas en Workday o en el Reino Unido). Detalle: `docs/CV_TEMPLATES.md`.

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
| `importar-plantilla-cv data/uploads/mi-cv.pdf` | Convierte un CV con cualquier diseño en plantilla reutilizable |
| `revisar-linkedin` | Informe de mejoras para tu perfil de LinkedIn, listo para copiar (tú lo aplicas) |

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
uv sync --extra matching           # opcional: similitud semántica (trae torch, ~1 GB)
uv run jh doctor                   # comprueba el entorno
uv run jh worker                   # tareas en segundo plano (scores); --once para vaciar la cola
uv run jh eval matching            # calidad del matching (evals/matching/README.md)
uv run pytest                      # tests
uv run ruff check --fix && uv run ruff format
```

### Frontend

```
cd frontend
pnpm install
pnpm dev                           # http://127.0.0.1:5173
pnpm typecheck && pnpm test && pnpm build
pnpm gen:api                       # regenera el cliente tras cambiar la API
```

### Usar la UI

Dos terminales: `cd backend && uv run jh db upgrade && uv run jh serve` (API en
http://127.0.0.1:8000, solo en local) y `cd frontend && pnpm dev`. Abre http://127.0.0.1:5173.
La UI da de alta ofertas y las muestra; la extracción la hace tu agente con el skill
`procesar-ofertas`, y la ficha la enseña en cuanto termina.

### CI

`.github/workflows/ci.yml` ejecuta ruff y pytest (en Windows), typecheck, test y build del
frontend, y `uv run scripts/sync_agents.py --check`. No necesita secretos.
