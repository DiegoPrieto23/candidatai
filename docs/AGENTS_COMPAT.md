# Compatibilidad con agentes

CandidatAI funciona con cualquier agente de IA que pueda **leer y escribir ficheros** y, además,
**hablar MCP o ejecutar comandos**. La configuración nativa de cada agente se genera desde
`.agents/` con `uv run scripts/sync_agents.py` (ADR-011).

Las rutas y formatos de cada herramienta cambian con frecuencia. Si algo de esta tabla deja de
funcionar, corrige el bloque del agente en `.agents/manifest.yaml` (o su emisor en el script),
regenera y actualiza esta página.

## Registro de agentes (fase 24.1)

Qué agentes conoce la app, qué sabe hacer cada uno y si los tienes instalados sale de
`.agents/manifest.yaml`, que el backend lee solo con `app/services/agent_registry.py` (ADR-037):

```
uv run --directory backend cai agents list           # todos, con capacidades y detección
uv run --directory backend cai agents list --json    # lo mismo en JSON (y GET /agent/agents)
uv run --directory backend cai agents doctor         # cuál se usaría hoy, por qué y qué falta
```

| Agente | Licencia | En el manifiesto | Nivel | MCP | Segundo plano |
|---|---|---|---|---|---|
| Claude Code | propietaria | habilitado, configuración generada | A | sí | sí |
| Codex | Apache-2.0 | habilitado, configuración generada | B | sí | no |
| Cursor CLI | propietaria | solo compatible vía `AGENTS.md` | C | sí | no |
| GitHub Copilot CLI | propietaria | solo compatible vía `AGENTS.md` | C | sí | no |
| Pi | MIT | solo compatible vía `AGENTS.md` | C | sí | no |
| goose | Apache-2.0 | solo compatible vía `AGENTS.md` | C | sí | no |

Los datos de Cursor CLI, Copilot CLI, Pi y goose (binario, instalación, licencia, MCP) se
comprobaron en sus webs el 2026-10-16. Copilot CLI 1.0.75 respondió a `copilot --version` en
Windows. Ninguno de los cuatro se ha probado con la app: «compatible vía `AGENTS.md`» quiere decir
que lee las instrucciones del repo y puede usar el servidor MCP o la CLI, con el nivel C de
aislamiento.

La detección busca en el `PATH` el programa de `info.detect` y lo ejecuta (máximo 5 s, sin las
variables de `launch.unset_env`). El resultado se guarda en caché 5 minutos. `--refresh` vuelve a
detectar. `cai doctor` resume lo mismo en su sección «Agentes».

## Matriz

| | Claude Code | Codex (ChatGPT) | Otros (Gemini CLI, Cursor, Copilot, OpenCode…) |
|---|---|---|---|
| Estado | Referencia (se desarrolla con él). Con MCP: probado en la fase 04; matriz de la 12.3 pendiente de la prueba manual. Sin MCP: matriz de la 12.3 probada (5/5) | Configuración generada; sin probar (fuera de la matriz de la fase 12 por decisión del usuario) | Sin probar |
| Cuenta | Plan de Claude con Claude Code | Cuenta de ChatGPT con acceso a Codex (CLI, extensión IDE o app) | La de cada herramienta |
| Instrucciones | `CLAUDE.md` → importa `AGENTS.md` | `AGENTS.md` | `AGENTS.md` (Gemini: `GEMINI.md` → `AGENTS.md`) |
| Skills | `.claude/skills/` (generado) | `.agents/skills/` (lo lee directamente) | `.agents/skills/` si la herramienta sigue el estándar Agent Skills |
| Invocar un skill | `/generate-cv 42` | `$generate-cv 42` | Lenguaje natural: "usa el skill generate-cv con la oferta 42" |
| Subagentes (roles) | `.claude/agents/*.md` (generado) | `.codex/agents/*.toml` (generado) | Sesión aparte siguiendo `.agents/roles/<rol>.md` |
| Servidor MCP | `.mcp.json` (generado) | `.codex/config.toml` (generado) | Registra `candidatai` con el `command`/`args` del manifiesto, o usa la CLI |
| Modelo por rol | `fast` → Haiku, `capable` → Sonnet | Hereda el de la sesión salvo que lo fijes en el manifiesto | El de la sesión |
| Permisos | `.claude/settings.json` (a mano) | Sandbox y aprobaciones de Codex | Los de cada herramienta |

## Matriz probada (fase 12.3)

Mismas 5 ofertas ficticias para todos (`evals/compat/jobs.txt`, casos de `evals/cv/cases.jsonl`),
dadas de alta solo con su texto con `cai demo seed --compat`. Cada agente recorre
`process-jobs` → `assess-fit` → (el usuario aprueba) → `generate-cv`, y se mide con
`cai eval cv --agent …` y comparando la extracción con la esperada.

| | Claude Code sin MCP (solo `cai … --json`) | Claude Code con MCP | Codex | Otros |
|---|---|---|---|---|
| Fecha | 2026-10-05 | Pendiente (`docs/pruebas/fase-12-compatibilidad.txt`) | Sin probar | Sin probar |
| Cómo | Opus 5.5; cada rol en una ejecución distinta siguiendo `.agents/roles/*.md` (nivel C: sin subagentes con herramientas propias) | Skills y subagentes generados | — | — |
| `process-jobs` | 5/5 al primer intento; **54 de 55 campos** iguales a la extracción esperada (difiere un `title_normalized`, en español) | | | |
| `assess-fit` | 5/5 valoraciones guardadas (4 `strong`, 1 `possible`) | | | |
| `generate-cv` | 5/5 CVs al primer intento, 1 página, sin avisos; verificador: 5 `passed`, 0 bloqueantes, 4 avisos | | | |
| `cai eval cv` | **5/5 pasan las 7 comprobaciones** | | | |
| Tiempo | ~2 min extraer, ~4,5 min redactar y ~2 min verificar (más lectura); ~3,5 s por comando `cai` | | | |
| Ajustes | Ver abajo | | | |

Prueba previa (fase 12.2): dos casos con trampa (`cv04`, `cv07`), también 2/2. Informe de esta
pasada: `docs/pruebas/fase-12.3-matriz-sin-mcp.md`. Sin subagentes, el aislamiento del rol
`extractor` es el del nivel C (ejecución dedicada), no el del A.

**Lo que hubo que ajustar para trabajar sin MCP** (ya corregido en `.agents/roles/` y los docs):
- los roles solo nombraban herramientas MCP: ahora tienen una sección «Sin MCP» con su comando
  `cai`, el formato de `--file` y la excepción a «no ejecutes comandos» y a `sandbox: read-only`;
- el redactor traducía nombres de skills en CVs en inglés (la app los rechaza) e incluía secciones
  extra en otro idioma: el rol ya lo indica;
- `docs/AGENT_INTERFACE.md` no explicaba los prefijos de las skills básicas
  («conocimientos de X»), qué evidencias se pueden citar ni `include_regional_language`;
- la demo no traía `tmp/` y la ayuda de `--file` decía `data/tmp/` aunque `CAI_DATA_DIR` apunte a
  otra carpeta;
- en Git Bash, `PYTHONIOENCODING=utf-8` para que la salida de texto no salga mal codificada.

**Pendiente** (no impide usarlo):
- sin MCP, el esquema de cada entrada está en `docs/AGENT_INTERFACE.md` y no llega con la
  herramienta: el agente tiene que buscarlo. Una salida `cai schema <modelo> --json` lo resolvería;
- `process-jobs` no admite elegir ofertas concretas (procesa todas las pendientes);
- sin subagentes, quien extrae lee el texto de las ofertas en la misma sesión: hazlo en una
  sesión dedicada (nivel C);
- `generate-cv` solo pregunta por skills obligatorias ausentes; las básicas cubiertas como
  «conocimientos de» no generan pregunta aunque la valoración la planteara;
- con una oferta remota sin país («Europa»), la foto sale según la política por defecto.

## Garantías de seguridad por nivel

Todas las opciones tienen las defensas del código (ADR-012): detección de texto oculto e
inyección al guardar, `risk_flags` visibles, validación estricta y una interfaz que no puede
enviar nada. Encima, cada agente añade lo que permite:

| Nivel | Agente | Aislamiento del rol `extractor` |
|---|---|---|
| **A** | Claude Code | El subagente solo tiene `get_job` y `save_extraction`: sin shell, ficheros ni web |
| **B** | Codex | El subagente se declara con `sandbox_mode = "read-only"`, pero **hereda la política de la sesión padre** y los cambios en vivo del padre prevalecen. Ejecuta `process-jobs` en una sesión de solo lectura o con aprobación de comandos |
| **C** | Sin subagentes | Sesión nueva dedicada solo a extraer, con los permisos más restrictivos que ofrezca la herramienta. No mezcles extracción con desarrollo en la misma sesión |

Recomendación para todos: ejecuta `process-jobs` en su propia sesión y revisa en la UI las
ofertas marcadas con riesgo antes de aprobarlas.

El rol `classifier` (fase 15, skill `review-replies`) lee correos de empresas, igual de no
confiables, y tiene el mismo aislamiento por nivel: en Claude Code solo `get_reply` y
`save_reply_proposal`. Además, lo que guarda es una propuesta: no cambia nada hasta que la
aceptas en la UI, y aceptar no tiene herramienta ni comando.

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
  `[mcp_servers.candidatai]` a tu `~/.codex/config.toml`.
- Para delegar en un rol, pídelo explícitamente: "lanza el subagente `extractor` con el job_id 42".
- Los modelos por rol están vacíos en el manifiesto a propósito (heredan el de la sesión). Si
  quieres un modelo rápido para `extractor`, pon su nombre en `targets.codex.models.fast` y regenera.

### Sin MCP (cualquier agente que ejecute comandos)
- Usa los comandos `cai … --json` de `docs/AGENT_INTERFACE.md`: misma salida y mismos errores.
- Las entradas largas van en `data/tmp/` con `--file`. Exporta `CAI_CLIENT_NAME=<tu-agente>` para
  que la auditoría sepa quién llama.
- Un test de extremo a extremo (`tests/test_e2e_cli.py`) recorre el flujo de `process-jobs`
  solo con comandos.

### Observado en la prueba manual con Claude Code (fase 04, 2026-09-24)
- Tras reiniciar, `/mcp` muestra `candidatai` conectado con sus 9 herramientas.
- `/process-jobs` con `demo/jobs/01-data-engineer.txt`: la sesión principal solo usó
  `get_status` y `list_jobs` y delegó en el subagente `extractor` (Haiku), que llamó a `get_job` y
  `save_extraction` sin pedir permiso. La oferta acabó en `pending_triage`, con el evento
  `extracted` como `agent/claude-code`.
- Calidad de la extracción: correcta en salario, años, modalidad, idioma, plazo y skills. Dos
  detalles menores: redactó `responsibilities` en inglés aunque la oferta está en español, y puso
  `domain: "data"` en vez del sector de la empresa (distribución/retail). Candidatos a precisar en
  `.agents/roles/extractor.md` cuando se evalúe el matching (fase 07).

### Comprobado en código (fase 04)
- `cai-mcp` arranca por stdio, lista las 9 herramientas y responde (test con el proceso real).
  stdout queda reservado al protocolo; los logs van a stderr y a `data/logs/mcp.log`.

### Extracción automática cada mañana (fase 09)

`cai worker` trae las ofertas nuevas a la hora de `connectors.daily_at` y las deja en
`pending_extraction`. La extracción necesita al agente (ADR-001), así que la app no la hace sola.
Opciones, de más a menos cómoda:

| Agente | Cómo | Notas |
|---|---|---|
| Claude Code Desktop | Una **tarea programada local**, diaria y después de la ingesta (p. ej. 08:00), en la carpeta del proyecto, con el prompt `/process-jobs` | Corre en tu equipo, con el MCP `candidatai` y tus datos. Las herramientas que usa (`get_status`, `list_jobs`, `get_job`, `save_extraction`) ya están permitidas en `.claude/settings.json`, así que no se queda esperando un permiso. El equipo y la app de escritorio tienen que estar encendidos |
| Claude Code (CLI) | El Programador de tareas de Windows lanzando `claude -p "/process-jobs"` en la raíz del repo | Mismo requisito de permisos que arriba. Las rutinas en la nube (`/schedule`) **no sirven**: corren fuera de tu equipo y no ven `data/` ni el MCP local |
| Codex | Si tu versión ofrece tareas programadas locales, el prompt `$process-jobs`; si no, el Programador de tareas con `codex exec "$process-jobs"` en una sesión de solo lectura | Sin probar. Revisa el nivel B de la tabla de garantías: ejecútalo con sandbox de solo lectura |
| Cualquier otro | `daily-summary` (manual o programado) te recuerda cuántas hay por extraer | Sin programación, basta con lanzar `process-jobs` al empezar el día |

Seguridad: una ejecución desatendida procesa texto no confiable sin que mires. El aislamiento del
rol `extractor` (solo `get_job` y `save_extraction`) es lo que la hace razonable; no amplíes sus
herramientas ni lo programes con un agente de nivel C. Las ofertas con `risk_flags` siguen
apareciendo con aviso en la UI.

### Skills que necesitan ver imágenes
`import-cv-template` con un PDF o una imagen recrea el diseño mirando la página renderizada:
hace falta un agente que pueda ver imágenes. Con un `.docx` no hace falta. Desde la fase 08b,
`inspect`, `scaffold-html` y `compare` dan al agente la página en PNG, una base de HTML y CSS
que ya se parece y una comparación lado a lado. Recreación desde PDF probada con Claude Code:
pendiente de la prueba manual de la 08b; desde imagen y con Codex, sin probar. `update-profile`
también funciona mejor si el agente puede leer PDFs; si no, basta con pegar el texto del CV.

### Skills que necesitan el navegador del usuario
`search-jobs` recorre portales con tu navegador y tus sesiones: hace falta un agente con acceso
a él (en Claude Code, Claude in Chrome). Estado a la 09b.3: la interfaz (`list_sources`,
`save_source`, `record_source_run` y `add_job_from_text` con `source_id`) está probada por MCP y
CLI en los tests. Falta la prueba manual de un recorrido real con Claude Code y Claude in Chrome
sobre una plataforma de acceso libre (`docs/pruebas/fase-09b.3-prueba-manual.txt`). En Codex y
otros, sin probar. Si tu agente no puede, las alertas por correo y el botón «Enviar a CandidatAI»
cubren lo mismo sin agente.

Las reglas que más importan no dependen del agente (ADR-012): ningún agente puede activar la
navegación en LinkedIn, y la app rechaza las ofertas y los recorridos de una plataforma
desactivada.

### Skills que necesitan buscar en la web
`training-plan` (fase 14) busca cursos, certificaciones y documentación oficial, y abre cada
página para comprobarla: hace falta un agente con búsqueda y lectura web (en Claude Code,
`WebSearch` y `WebFetch`). Sin web, el skill no puede verificar recursos y no debe proponerlos de
memoria: puede priorizar los huecos, pero cada recurso necesita una URL abierta. Probado con
Claude Code: pendiente de la prueba manual de la fase 14; Codex y otros, sin probar.
`research-company` (fase 18) también: busca y abre las páginas de la empresa y guarda el dosier
con sus URLs (`save_company_research` rechaza un apartado sin fuente). Sin web, dice que no puede y
para; `prepare-interview` trabaja entonces con el dosier que haya. Probado solo con los tests de
sus herramientas; pendiente de la prueba manual con Claude Code.

### Skills que editan el perfil
`broaden-search` (fase 16) añade los títulos que aceptas a `preferences.roles` editando
`data/profile.yaml` y ejecutando `cai profile validate` e `import`, como `update-profile`: hace
falta un agente que pueda editar ficheros y ejecutar esos comandos. Si no puede, el skill te da el
texto y los comandos para que lo hagas tú. Las búsquedas de plataformas van por `save_source`
(MCP o CLI). Probado solo con los tests de su herramienta (`get_search_titles`); pendiente de la
prueba manual con Claude Code.

### Botones «en tu agente» de la UI (ADR-024)
«Buscar ofertas», «Procesar ofertas», «Evaluar encaje», «Generar CV», en la página Skills
(fase 14) «Añadir al perfil las que tengo» (`update-profile`) y «Plan de formación», y desde
la fase 15 «Revisar respuestas» (Inicio y «Respuestas»), «Redactar borradores» (Procesos) y
«Redactar seguimiento» (ficha de una candidatura enviada), desde la fase 16 «Ampliar búsqueda»
(Plataformas), desde la 17 los de las entrevistas y desde la 18 «Redactar mensaje» e «Investigar
empresa» (ficha), abren tu
agente en una terminal (Windows Terminal o PowerShell) con la orden del skill ya escrita; tú
ves, contestas y apruebas lo que haga. Qué programa se abre lo dice `launch` de cada agente en el
manifiesto: `command` (con `{prompt}` donde va la orden) y `unset_env` (variables que se quitan
antes, como la clave de la API, para que use tu suscripción). Con varios agentes, elige `CAI_AGENT` (`claude`,
`codex`…). Solo Windows de momento; en otro sistema, o sin el agente en el `PATH`, el botón copia
la orden para que la pegues tú. Probado con Claude Code; Codex, sin probar.

### En segundo plano y cola de encargos (fase 19, ADR-032)
El desplegable de cada botón ofrece **«En segundo plano»** en `process-jobs`, `assess-fit`
y `generate-cv`: el worker lanza tu agente sin ventana y la página «Agente» enseña el progreso, el
resultado y, si el skill necesita algo, sus preguntas, con «Contestar en terminal» para seguir en
la misma sesión. Sale de `launch.headless` del manifiesto: `command` (con `{prompt}` y
`{allowed_tools}`), `allow` (las herramientas no MCP) y `output` (formato de la salida), con el
mismo `unset_env`.

| | Claude Code | Codex | Otros |
|---|---|---|---|
| En segundo plano | Sí: `claude -p` con `stream-json`, `--tools Skill,Agent,Read`, `dontAsk`, `--allowedTools` con las herramientas MCP de la acción, `Skill(<su skill>)` y `Read(./docs/**)`, y `--disallowedTools` con todas las demás MCP de la app. Los tests usan un agente falso; las reglas se comprobaron con `claude` 2.1.296 (ver abajo). El recorrido completo, pendiente de la prueba manual (`docs/pruebas/fase-19-prueba-manual.txt`) | No: no permite limitar las herramientas MCP de una ejecución con garantías (nivel B). El botón lo dice | No |
| Cola de encargos | Sí (`list_agent_requests`, `complete_agent_request`, skill `handle-requests`) | Sí (mismas herramientas o `cai requests … --json`) | Sí, con MCP o CLI |

Comprobado con `claude` 2.1.296 (2026-10-12, modelo haiku, sin datos):
- una herramienta MCP permitida en `.claude/settings.json` pero no en `--allowedTools` **se usa**,
  también desde un subagente: por eso las demás se deniegan con `--disallowedTools`, que las quita
  de la sesión entera («No such tool available»);
- `Skill(process-jobs)` permite ese skill y deniega los demás («denied … don't ask mode»);
- `Agent(extractor)` no acota: `general-purpose` se lanzó igual. Da igual para el techo: un
  subagente no tiene más herramientas que la sesión;
- con `--strict-mcp-config` solo carga `candidatai` (ni Claude in Chrome ni los conectores de
  claude.ai).

Para dar segundo plano a otro agente: un bloque `headless` cuyo comando limite las herramientas a
las de `{allowed_tools}`, deniegue las de `{denied_tools}` y no tenga terminal ni web, y un lector
de su salida en `backend/app/services/agent_output.py` (`PARSERS`). Si el agente no puede
limitarlas, no lo añadas: la garantía de este modo es justo esa.

**«Dejar para mi próxima sesión»** funciona con cualquier agente: guarda la orden y tu próxima
sesión la ve en `get_status` (`agent_requests`) o con el skill `handle-requests`.

### Añadir otro agente
1. Añade su bloque a `targets` en `.agents/manifest.yaml`: `config`, `info` y `capabilities`
   (ver el comentario del principio del manifiesto) y, si tiene configuración generada, rutas,
   modelos, formato MCP y, si quieres los botones de la UI, `launch`; para el segundo plano,
   `launch.headless`. `cai agents list` falla con el agente y la clave si algo está mal escrito.
2. Si su formato no es JSON ni TOML de los ya soportados, añade un emisor en `scripts/sync_agents.py`.
3. Regenera y pasa la matriz: `cai demo seed --dir data-demo-<agente> --compat`, arranca el
   agente con `CAI_DATA_DIR` apuntando ahí, recorre `process-jobs`, `assess-fit` y
   `generate-cv` sobre las 5 ofertas (guía: `docs/pruebas/fase-12-compatibilidad.txt`), mide con
   `cai eval cv --agent <nombre>` y añade su columna a «Matriz probada».
