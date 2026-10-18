# Desarrollo por fases con un agente

CandidatAI empezó como un kit de arranque: especificación, encargos por fase, skills y roles para
construir la app **con el agente de IA que prefieras**. Esta guía cuenta cómo se construye (o se
amplía) fase a fase. El estado de cada fase está en `ROADMAP.md`; lo que aporta cada una, en
`RESUMEN_FASES.md`.

## Qué necesita tu agente

Poder **leer y escribir ficheros** en la carpeta y, además, **hablar MCP o ejecutar comandos**.
Con MCP es más cómodo; sin MCP, usa la CLI `cai … --json`, que es equivalente.
Detalle por agente y garantías de seguridad: `docs/AGENTS_COMPAT.md`.

## Qué hay en el kit

```
AGENTS.md                  instrucciones del proyecto para CUALQUIER agente
CLAUDE.md                  solo importa AGENTS.md
GEMINI.md                  vacío a propósito (ADR-037)
docs/
  ARCHITECTURE.md          capas, etapas, quién hace qué, seguridad en profundidad
  DATA_MODEL.md            tablas, catálogo de eventos, proyección de etapas
  AGENT_INTERFACE.md       herramientas MCP ↔ comandos CLI, y esquemas que rellena el agente
  POLICIES.md              reglas de negocio: veracidad, CV, privacidad, candidaturas
  CV_TEMPLATES.md          plantillas de CV, motores docx/html, foto y opciones por oferta
  AGENTS_COMPAT.md         matriz de agentes soportados y cómo añadir uno
  ROADMAP.md               fases con su estado y registro
  DECISIONS.md             ADRs (sin API, SQLite, docxtpl, neutralidad de agente…)
prompts/01…12-*.md         el encargo de cada fase
.agents/                   FUENTE ÚNICA para agentes
  skills/                  skills en el estándar Agent Skills (Codex los lee directamente)
  roles/                   subagentes neutrales: extractor, redactor, verificador, revisor
  manifest.yaml            lo específico de cada agente (rutas, modelos, MCP, extras)
scripts/sync_agents.py     genera la configuración nativa desde .agents/
.claude/  .codex/  .mcp.json   GENERADOS (no editar a mano; se commitean)
.claude/settings.json      permisos de Claude Code (este sí, a mano)
templates/                 plantillas de CV integradas
config/                    políticas genéricas, sinónimos de skills, patrones de inyección
demo/profile.example.yaml  esquema del perfil con una candidata ficticia
```

## Empezar un proyecto desde el kit (Windows 11)

1. Instala Git, [uv](https://docs.astral.sh/uv/), Node LTS + pnpm (`corepack enable`),
   LibreOffice y tu agente.
2. Copia el kit en una carpeta nueva y haz el primer commit:
   ```
   git init
   git add .
   git commit -m "Kit inicial"
   ```
3. Abre tu agente en esa carpeta y pide la primera fase:
   - Claude Code: `/implement-phase 01`
   - Codex: `$implement-phase 01`
   - Otros: "Lee AGENTS.md y usa el skill implement-phase para la fase 01"

### En macOS y Linux (fase 26)

Lo mismo: Git, [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`),
Node LTS + pnpm (`npm install -g pnpm`) y tu agente. LibreOffice es opcional (los PDF salen con el
Chromium de Playwright); en Linux, `uv run playwright install --with-deps chromium` instala también
sus librerías (pide `sudo`). Los comandos de `AGENTS.md` son los mismos, con `/` en las rutas. La
CI prueba el backend en Windows y Linux en cada push, y en macOS en `main`, en las etiquetas y a
mano (`.github/workflows/ci.yml`).

## Cómo construir cada fase

```
implement-phase NN   →  el agente lee el encargo y propone un plan
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
