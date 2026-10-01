# Compatibilidad con agentes

Job Hunter funciona con cualquier agente de IA que pueda **leer y escribir ficheros** y, además,
**hablar MCP o ejecutar comandos**. La configuración nativa de cada agente se genera desde
`.agents/` con `uv run scripts/sync_agents.py` (ADR-011).

Las rutas y formatos de cada herramienta cambian con frecuencia. Si algo de esta tabla deja de
funcionar, corrige el bloque del agente en `.agents/manifest.yaml` (o su emisor en el script),
regenera y actualiza esta página.

## Matriz

| | Claude Code | Codex (ChatGPT) | Otros (Gemini CLI, Cursor, Copilot, OpenCode…) |
|---|---|---|---|
| Estado | Referencia (se desarrolla con él); probado en la fase 04 | Segundo agente; prueba manual pendiente | Sin probar |
| Cuenta | Plan de Claude con Claude Code | Cuenta de ChatGPT con acceso a Codex (CLI, extensión IDE o app) | La de cada herramienta |
| Instrucciones | `CLAUDE.md` → importa `AGENTS.md` | `AGENTS.md` | `AGENTS.md` (Gemini: `GEMINI.md` → `AGENTS.md`) |
| Skills | `.claude/skills/` (generado) | `.agents/skills/` (lo lee directamente) | `.agents/skills/` si la herramienta sigue el estándar Agent Skills |
| Invocar un skill | `/generar-cv 42` | `$generar-cv 42` | Lenguaje natural: "usa el skill generar-cv con la oferta 42" |
| Subagentes (roles) | `.claude/agents/*.md` (generado) | `.codex/agents/*.toml` (generado) | Sesión aparte siguiendo `.agents/roles/<rol>.md` |
| Servidor MCP | `.mcp.json` (generado) | `.codex/config.toml` (generado) | Registra `jobhunter` con el `command`/`args` del manifiesto, o usa la CLI |
| Modelo por rol | `fast` → Haiku, `capable` → Sonnet | Hereda el de la sesión salvo que lo fijes en el manifiesto | El de la sesión |
| Permisos | `.claude/settings.json` (a mano) | Sandbox y aprobaciones de Codex | Los de cada herramienta |

## Garantías de seguridad por nivel

Todas las opciones tienen las defensas del código (ADR-012): detección de texto oculto e
inyección al guardar, `risk_flags` visibles, validación estricta y una interfaz que no puede
enviar nada. Encima, cada agente añade lo que permite:

| Nivel | Agente | Aislamiento del rol `extractor` |
|---|---|---|
| **A** | Claude Code | El subagente solo tiene `get_job` y `save_extraction`: sin shell, ficheros ni web |
| **B** | Codex | El subagente se declara con `sandbox_mode = "read-only"`, pero **hereda la política de la sesión padre** y los cambios en vivo del padre prevalecen. Ejecuta `procesar-ofertas` en una sesión de solo lectura o con aprobación de comandos |
| **C** | Sin subagentes | Sesión nueva dedicada solo a extraer, con los permisos más restrictivos que ofrezca la herramienta. No mezcles extracción con desarrollo en la misma sesión |

Recomendación para todos: ejecuta `procesar-ofertas` en su propia sesión y revisa en la UI las
ofertas marcadas con riesgo antes de aprobarlas.

## Notas por agente

### Claude Code
- La primera vez te pedirá aprobar el servidor MCP del proyecto. Tras cambiar el código del
  servidor, reinicia Claude Code (o reconecta en `/mcp`) para que arranque la versión nueva.
- `get_job` y `save_extraction` están permitidas en `.claude/settings.json` para que el subagente
  `extractor` procese ofertas sin pedir permiso en cada una. Las herramientas que escriben
  (`add_job_*`, `add_event`) siguen pidiéndolo.
- Informa `clientInfo.name = "claude-code"`, que queda en `mcp_calls` y en `events.agent_name`.
- `disable-model-invocation`, `argument-hint` y `allowed-tools` de los skills se añaden al generar
  (`.agents/manifest.yaml` → `targets.claude.skill_extras`); los skills canónicos no los llevan.

### Codex (ChatGPT)
- Inicia sesión en Codex con tu cuenta de ChatGPT y abre la raíz del repo.
- Si Codex no carga la configuración del proyecto (`.codex/config.toml`), revisa en su
  documentación cómo marcar el proyecto como de confianza, o copia el bloque
  `[mcp_servers.jobhunter]` a tu `~/.codex/config.toml`.
- Para delegar en un rol, pídelo explícitamente: "lanza el subagente `extractor` con el job_id 42".
- Los modelos por rol están vacíos en el manifiesto a propósito (heredan el de la sesión). Si
  quieres un modelo rápido para `extractor`, pon su nombre en `targets.codex.models.fast` y regenera.

### Sin MCP (cualquier agente que ejecute comandos)
- Usa los comandos `jh … --json` de `docs/AGENT_INTERFACE.md`: misma salida y mismos errores.
- Las entradas largas van en `data/tmp/` con `--file`. Exporta `JH_CLIENT_NAME=<tu-agente>` para
  que la auditoría sepa quién llama.
- Un test de extremo a extremo (`tests/test_e2e_cli.py`) recorre el flujo de `procesar-ofertas`
  solo con comandos.

### Observado en la prueba manual con Claude Code (fase 04, 2026-09-24)
- Tras reiniciar, `/mcp` muestra `jobhunter` conectado con sus 9 herramientas.
- `/procesar-ofertas` con `demo/jobs/01-data-engineer.txt`: la sesión principal solo usó
  `get_status` y `list_jobs` y delegó en el subagente `extractor` (Haiku), que llamó a `get_job` y
  `save_extraction` sin pedir permiso. La oferta acabó en `pending_triage`, con el evento
  `extracted` como `agent/claude-code`.
- Calidad de la extracción: correcta en salario, años, modalidad, idioma, plazo y skills. Dos
  detalles menores: redactó `responsibilities` en inglés aunque la oferta está en español, y puso
  `domain: "data"` en vez del sector de la empresa (distribución/retail). Candidatos a precisar en
  `.agents/roles/extractor.md` cuando se evalúe el matching (fase 07).

### Comprobado en código (fase 04)
- `jh-mcp` arranca por stdio, lista las 9 herramientas y responde (test con el proceso real).
  stdout queda reservado al protocolo; los logs van a stderr y a `data/logs/mcp.log`.

### Skills que necesitan ver imágenes
`importar-plantilla-cv` con un PDF o una imagen recrea el diseño mirando la página renderizada:
hace falta un agente que pueda ver imágenes. Con un `.docx` no hace falta. `actualizar-perfil`
también funciona mejor si el agente puede leer PDFs; si no, basta con pegar el texto del CV.

### Skills que necesitan el navegador del usuario
`buscar-ofertas` recorre portales con tu navegador y tus sesiones: hace falta un agente con acceso
a él (en Claude Code, Claude in Chrome). En Codex y otros, sin probar. Si tu agente no puede, las
alertas por correo y el botón «Enviar a Job Hunter» cubren lo mismo sin agente.

### Añadir otro agente
1. Añade su bloque a `targets` en `.agents/manifest.yaml` (rutas, modelos, formato MCP).
2. Si su formato no es JSON ni TOML de los ya soportados, añade un emisor en `scripts/sync_agents.py`.
3. Regenera, prueba los skills `procesar-ofertas` y `generar-cv` con los datos de `demo/` y añade
   una columna a esta matriz.
