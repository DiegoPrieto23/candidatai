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
| Estado | Referencia (se desarrolla con él). Con MCP: probado en la fase 04; matriz de la 12.3 pendiente de la prueba manual. Sin MCP: matriz de la 12.3 probada (5/5) | Configuración generada; sin probar (fuera de la matriz de la fase 12 por decisión del usuario) | Sin probar |
| Cuenta | Plan de Claude con Claude Code | Cuenta de ChatGPT con acceso a Codex (CLI, extensión IDE o app) | La de cada herramienta |
| Instrucciones | `CLAUDE.md` → importa `AGENTS.md` | `AGENTS.md` | `AGENTS.md` (Gemini: `GEMINI.md` → `AGENTS.md`) |
| Skills | `.claude/skills/` (generado) | `.agents/skills/` (lo lee directamente) | `.agents/skills/` si la herramienta sigue el estándar Agent Skills |
| Invocar un skill | `/generar-cv 42` | `$generar-cv 42` | Lenguaje natural: "usa el skill generar-cv con la oferta 42" |
| Subagentes (roles) | `.claude/agents/*.md` (generado) | `.codex/agents/*.toml` (generado) | Sesión aparte siguiendo `.agents/roles/<rol>.md` |
| Servidor MCP | `.mcp.json` (generado) | `.codex/config.toml` (generado) | Registra `jobhunter` con el `command`/`args` del manifiesto, o usa la CLI |
| Modelo por rol | `fast` → Haiku, `capable` → Sonnet | Hereda el de la sesión salvo que lo fijes en el manifiesto | El de la sesión |
| Permisos | `.claude/settings.json` (a mano) | Sandbox y aprobaciones de Codex | Los de cada herramienta |

## Matriz probada (fase 12.3)

Mismas 5 ofertas ficticias para todos (`evals/compat/jobs.txt`, casos de `evals/cv/cases.jsonl`),
dadas de alta solo con su texto con `jh demo seed --compat`. Cada agente recorre
`procesar-ofertas` → `evaluar-encaje` → (el usuario aprueba) → `generar-cv`, y se mide con
`jh eval cv --agent …` y comparando la extracción con la esperada.

| | Claude Code sin MCP (solo `jh … --json`) | Claude Code con MCP | Codex | Otros |
|---|---|---|---|---|
| Fecha | 2026-10-05 | Pendiente (`docs/pruebas/fase-12-compatibilidad.txt`) | Sin probar | Sin probar |
| Cómo | Opus 5.5; cada rol en una ejecución distinta siguiendo `.agents/roles/*.md` (nivel C: sin subagentes con herramientas propias) | Skills y subagentes generados | — | — |
| `procesar-ofertas` | 5/5 al primer intento; **54 de 55 campos** iguales a la extracción esperada (difiere un `title_normalized`, en español) | | | |
| `evaluar-encaje` | 5/5 valoraciones guardadas (4 `strong`, 1 `possible`) | | | |
| `generar-cv` | 5/5 CVs al primer intento, 1 página, sin avisos; verificador: 5 `passed`, 0 bloqueantes, 4 avisos | | | |
| `jh eval cv` | **5/5 pasan las 7 comprobaciones** | | | |
| Tiempo | ~2 min extraer, ~4,5 min redactar y ~2 min verificar (más lectura); ~3,5 s por comando `jh` | | | |
| Ajustes | Ver abajo | | | |

Prueba previa (fase 12.2): dos casos con trampa (`cv04`, `cv07`), también 2/2. Informe de esta
pasada: `docs/pruebas/fase-12.3-matriz-sin-mcp.md`. Sin subagentes, el aislamiento del rol
`extractor` es el del nivel C (ejecución dedicada), no el del A.

**Lo que hubo que ajustar para trabajar sin MCP** (ya corregido en `.agents/roles/` y los docs):
- los roles solo nombraban herramientas MCP: ahora tienen una sección «Sin MCP» con su comando
  `jh`, el formato de `--file` y la excepción a «no ejecutes comandos» y a `sandbox: read-only`;
- el redactor traducía nombres de skills en CVs en inglés (la app los rechaza) e incluía secciones
  extra en otro idioma: el rol ya lo indica;
- `docs/AGENT_INTERFACE.md` no explicaba los prefijos de las skills básicas
  («conocimientos de X»), qué evidencias se pueden citar ni `include_regional_language`;
- la demo no traía `tmp/` y la ayuda de `--file` decía `data/tmp/` aunque `JH_DATA_DIR` apunte a
  otra carpeta;
- en Git Bash, `PYTHONIOENCODING=utf-8` para que la salida de texto no salga mal codificada.

**Pendiente** (no impide usarlo):
- sin MCP, el esquema de cada entrada está en `docs/AGENT_INTERFACE.md` y no llega con la
  herramienta: el agente tiene que buscarlo. Una salida `jh schema <modelo> --json` lo resolvería;
- `procesar-ofertas` no admite elegir ofertas concretas (procesa todas las pendientes);
- sin subagentes, quien extrae lee el texto de las ofertas en la misma sesión: hazlo en una
  sesión dedicada (nivel C);
- `generar-cv` solo pregunta por skills obligatorias ausentes; las básicas cubiertas como
  «conocimientos de» no generan pregunta aunque la valoración la planteara;
- con una oferta remota sin país («Europa»), la foto sale según la política por defecto.

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

### Extracción automática cada mañana (fase 09)

`jh worker` trae las ofertas nuevas a la hora de `connectors.daily_at` y las deja en
`pending_extraction`. La extracción necesita al agente (ADR-001), así que la app no la hace sola.
Opciones, de más a menos cómoda:

| Agente | Cómo | Notas |
|---|---|---|
| Claude Code Desktop | Una **tarea programada local**, diaria y después de la ingesta (p. ej. 08:00), en la carpeta del proyecto, con el prompt `/procesar-ofertas` | Corre en tu equipo, con el MCP `jobhunter` y tus datos. Las herramientas que usa (`get_status`, `list_jobs`, `get_job`, `save_extraction`) ya están permitidas en `.claude/settings.json`, así que no se queda esperando un permiso. El equipo y la app de escritorio tienen que estar encendidos |
| Claude Code (CLI) | El Programador de tareas de Windows lanzando `claude -p "/procesar-ofertas"` en la raíz del repo | Mismo requisito de permisos que arriba. Las rutinas en la nube (`/schedule`) **no sirven**: corren fuera de tu equipo y no ven `data/` ni el MCP local |
| Codex | Si tu versión ofrece tareas programadas locales, el prompt `$procesar-ofertas`; si no, el Programador de tareas con `codex exec "$procesar-ofertas"` en una sesión de solo lectura | Sin probar. Revisa el nivel B de la tabla de garantías: ejecútalo con sandbox de solo lectura |
| Cualquier otro | `resumen-diario` (manual o programado) te recuerda cuántas hay por extraer | Sin programación, basta con lanzar `procesar-ofertas` al empezar el día |

Seguridad: una ejecución desatendida procesa texto no confiable sin que mires. El aislamiento del
rol `extractor` (solo `get_job` y `save_extraction`) es lo que la hace razonable; no amplíes sus
herramientas ni lo programes con un agente de nivel C. Las ofertas con `risk_flags` siguen
apareciendo con aviso en la UI.

### Skills que necesitan ver imágenes
`importar-plantilla-cv` con un PDF o una imagen recrea el diseño mirando la página renderizada:
hace falta un agente que pueda ver imágenes. Con un `.docx` no hace falta. Desde la fase 08b,
`inspect`, `scaffold-html` y `compare` dan al agente la página en PNG, una base de HTML y CSS
que ya se parece y una comparación lado a lado. Recreación desde PDF probada con Claude Code:
pendiente de la prueba manual de la 08b; desde imagen y con Codex, sin probar. `actualizar-perfil`
también funciona mejor si el agente puede leer PDFs; si no, basta con pegar el texto del CV.

### Skills que necesitan el navegador del usuario
`buscar-ofertas` recorre portales con tu navegador y tus sesiones: hace falta un agente con acceso
a él (en Claude Code, Claude in Chrome). Estado a la 09b.3: la interfaz (`list_sources`,
`save_source`, `record_source_run` y `add_job_from_text` con `source_id`) está probada por MCP y
CLI en los tests. Falta la prueba manual de un recorrido real con Claude Code y Claude in Chrome
sobre una plataforma de acceso libre (`docs/pruebas/fase-09b.3-prueba-manual.txt`). En Codex y
otros, sin probar. Si tu agente no puede, las alertas por correo y el botón «Enviar a Job Hunter»
cubren lo mismo sin agente.

Las reglas que más importan no dependen del agente (ADR-012): ningún agente puede activar la
navegación en LinkedIn, y la app rechaza las ofertas y los recorridos de una plataforma
desactivada.

### Botones «en tu agente» de la UI (ADR-024)
«Buscar ofertas», «Procesar ofertas», «Evaluar encaje» y «Generar CV» abren tu agente en una
terminal (Windows Terminal o PowerShell) con la orden del skill ya escrita; tú ves, contestas y
apruebas lo que haga. Qué programa se abre lo dice `launch` de cada agente en el manifiesto:
`command` (con `{prompt}` donde va la orden) y `unset_env` (variables que se quitan antes, como la
clave de la API, para que use tu suscripción). Con varios agentes, elige `JH_AGENT` (`claude`,
`codex`…). Solo Windows de momento; en otro sistema, o sin el agente en el `PATH`, el botón copia
la orden para que la pegues tú. Probado con Claude Code; Codex, sin probar.

### Añadir otro agente
1. Añade su bloque a `targets` en `.agents/manifest.yaml` (rutas, modelos, formato MCP y, si
   quieres los botones de la UI, `launch`).
2. Si su formato no es JSON ni TOML de los ya soportados, añade un emisor en `scripts/sync_agents.py`.
3. Regenera y pasa la matriz: `jh demo seed --dir data-demo-<agente> --compat`, arranca el
   agente con `JH_DATA_DIR` apuntando ahí, recorre `procesar-ofertas`, `evaluar-encaje` y
   `generar-cv` sobre las 5 ofertas (guía: `docs/pruebas/fase-12-compatibilidad.txt`), mide con
   `jh eval cv --agent <nombre>` y añade su columna a «Matriz probada».
