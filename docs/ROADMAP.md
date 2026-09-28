# Roadmap

Cada fase tiene su encargo en `prompts/NN-*.md`. Con cualquier agente: pídele "implementa la fase
NN" o usa el skill `implementar-fase` (`/implementar-fase 03` en Claude Code, `$implementar-fase 03`
en Codex). Al cerrar una fase, el agente actualiza su estado aquí.
Estados: ⏳ pendiente · 🚧 en curso · ✅ hecha.

| # | Fase | Estado | Resultado visible |
|---|---|---|---|
| 01 | Arranque del repo | ✅ | `uv run pytest` y `pnpm build` funcionan; CI mínimo con `sync_agents.py --check` |
| 02 | Núcleo de datos | ✅ | Esquema, migraciones, eventos, proyección de etapas, CLI `jh` |
| 03 | Alta de ofertas | ✅ | `jh jobs add-url` y `add-text` crean ofertas deduplicadas y con `risk_flags` |
| 04 | Interfaz para agentes | ✅ | Servidor MCP + CLI con paridad; funciona desde Claude Code y Codex |
| 05 | Perfil del candidato | ✅ | `data/profile.yaml` validado y versionado; `get_profile` |
| 05b | Preferencias de CV en el perfil | ✅ | El perfil admite plantilla por defecto, foto y reglas de plantilla; `demo/profile.example.yaml` vuelve a validar |
| 06 | Frontend base | ⏳ | UI con bandeja de ofertas, ficha y alta por URL |
| 07 | Matching y triaje | ⏳ | Filtros duros, score, skill `evaluar-encaje`, aprobar o descartar en la UI |
| 08 | CV a medida con plantillas | ⏳ | `generar-cv` produce CVs verificados; plantilla, foto y color se cambian en la UI sin agente; importar plantillas desde Word |
| 08b | Plantillas html | ⏳ | Importar diseños desde PDF o imagen (Canva…) y plantilla integrada de dos columnas |
| 09 | Conectores de ATS y scheduler | ⏳ | Ingesta diaria de empresas objetivo sin intervención |
| 10 | Seguimiento y analítica | ⏳ | Kanban, seguimientos pendientes, dashboard del embudo |
| 11 | Candidatura asistida | ⏳ | Rellenado con Playwright y envío tras tu confirmación |
| 12 | Demo, compatibilidad y portfolio | ⏳ | Modo demo, matriz de agentes probada, evals publicados |

**MVP usable:** al terminar la 08 ya puedes pegar ofertas, triarlas y sacar CVs a medida.

**Skills que se desbloquean por fase:** `actualizar-perfil` tras la 05; `procesar-ofertas` tras la
04 (y con perfil, tras la 05); `evaluar-encaje` tras la 07; `generar-cv` tras la 08; `importar-plantilla-cv` tras la 08 para
Word y tras la 08b para PDF, imagen o HTML;
`revisar-linkedin` funciona tras la 05, pero rinde mucho más desde la 07, cuando ya hay ofertas
aprobadas de las que sacar las keywords; `preparar-candidatura`, `preparar-entrevista` y
`resumen-diario` tras la 10.

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

### 03 · Alta de ofertas — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** `services/ingest.py` (`add_from_url` con httpx + trafilatura + JSON-LD/`og:`,
  `add_from_text`, duplicados exactos por huella y difusos con rapidfuzz), `services/untrusted.py`
  (texto oculto en el HTML original y frases de `injection_patterns.yaml`), `services/jobs.py`
  (`list_jobs`), `core/policies.py` (carga de `config/`) y CLI `jh jobs add-url | add-text | list`
  con `--json`. Cinco fixtures inventados; 398 tests, `services/` al 98 %.
- **Decisiones:**
  - Duplicado difuso: `duplicate_of` + evento `duplicate_detected` (cierra la oferta, reabrible),
    en el orden `found` → `injection_suspected` → `duplicate_detected`. Siempre apunta a la
    original, no a otro duplicado.
  - Duplicado exacto (misma huella, o misma URL en `add-url`, sin descargar): devuelve la oferta
    existente con `created: false` y no registra eventos.
  - Salida de alta `{job_id, created, duplicate_of, risk_flags}`; `add-text` admite `--location`
    (entra en la huella) y guarda `url = ""` si no hay. `AGENT_INTERFACE.md` actualizado.
  - Texto oculto en zonas benignas (nav, header, footer, diálogos, listas de enlaces) no activa
    `hidden_text`, pero sí se busca en él una frase de inyección. Documentado en `POLICIES.md` §6.
  - trafilatura descarta el texto con `display:none`: la detección se hace sobre el HTML original.
    Si la página se pinta con JavaScript pero trae la oferta en el JSON-LD, se usa su
    `description`.
  - La descarga comprueba cada salto (hook de httpx): no sigue a LinkedIn ni a IPs locales o
    privadas tras una redirección. Máximo 5 MB, sin cookies previas.
- **Deuda:**
  - La protección SSRF solo mira IPs literales y `localhost`; un dominio que resuelva a una IP
    privada pasaría (resolver DNS en el código rompería los tests sin red).
  - Si una oferta se dio de alta por texto (sin URL) y luego llega por URL con la misma huella, no
    se completa su `url`.
  - El patrón `system prompt` puede dar falsos positivos en ofertas reales de ingeniería de LLM.
  - `jh jobs list` ordena por `first_seen_at`; el orden `score_desc` de la interfaz llega con la
    fase 07. Las llamadas aún no se registran en `mcp_calls` (fase 04).

### 04 · Interfaz para agentes — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** registro único de herramientas en `app/agent_interface/` (`ToolSpec` → herramienta
  MCP y comando `jh`), servidor `jh-mcp` por stdio con el SDK `mcp` 2.2, las 9 herramientas de la
  fase, `JobExtraction` (schema_version 1), `get_job` con envoltorio blindado, `save_extraction`
  con `injection_suspected` del agente, auditoría en `mcp_calls`, formato de error común y
  `jh agents sync | check`. Dos ofertas ficticias en `demo/jobs/`. 492 tests. Probado a mano con
  Claude Code (`/mcp` + `/procesar-ofertas` → `pending_triage`); guía en
  `docs/pruebas/fase-04-prueba-manual.txt`.
- **Decisiones:**
  - `Server` de bajo nivel en vez de FastMCP para que MCP y CLI validen con el mismo modelo y den
    errores idénticos (ADR-013). Por CLI todo llega como texto; `received` va siempre como texto.
  - Error común `{ok: false, error: {type, message, details: [{field, received, reason}]}}`,
    mensajes en español. Sustituye al provisional de la fase 02.
  - `jh jobs show` sin `--raw`; `list_jobs order=score_desc` igual que `recent` hasta la fase 07.
  - `add_event`: actor `agent`, `note` en el payload; rechaza los eventos con herramienta propia o
    del sistema (`extracted`, `cv_verified`…).
  - Auditoría: MCP siempre, CLI solo con `--json`; cliente por `clientInfo.name` o
    `JH_CLIENT_NAME`. `args_summary` guarda ids/URLs/etapas y, del resto, solo longitudes.
  - `--file` solo dentro de `data/tmp/` (también `add-text`, que antes aceptaba cualquier ruta);
    se borra tras el éxito. Una ruta relativa vale desde el directorio actual o desde la raíz
    (con `uv run --directory backend` el proceso corre en `backend/`).
  - `get_job` y `save_extraction` permitidas en `.claude/settings.json` (el extractor no pide
    permiso por oferta); las herramientas `add_*` siguen pidiéndolo.
  - Envoltorio: se neutraliza cualquier variante de la etiqueta (mayúsculas, espacios, guiones,
    `<` Unicode parecidos, caracteres invisibles) escapando su `<`.
- **Deuda:**
  - Extractor: `responsibilities` salió en inglés con una oferta en español y `domain` como
    "data" en vez del sector. Precisar el rol al evaluar el matching (fase 07).
  - **Prueba con Codex pendiente:** el usuario aún no tiene Codex instalado. Cuando lo tenga,
    seguir la parte 3 de la guía y actualizar `docs/AGENTS_COMPAT.md`.
  - El test de paridad tarda ~0,5 s por caso (migra dos BD por caso).

### 05 · Perfil del candidato — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** `CandidateProfile` (`app/schemas/profile.py`) valida la estructura de
  `demo/profile.example.yaml`; `services/profile.py` con `load_from_yaml` (errores con la ruta del
  campo, p. ej. `experience[1].achievements[0].id`), `import_profile`, `current`, `public_view`,
  `diff_last_two`, `init_profile` y `resolve_evidence`; herramienta `get_profile(sections?)`; CLI
  `jh profile validate | import | diff | init | show`. Migración `0002`. 574 tests;
  `services/profile.py` al 100 %.
- **Decisiones:**
  - Ids de primer nivel (experiencias, proyectos, formación, certificaciones, historias) únicos en
    todo el perfil; los de logro, dentro de su experiencia. Las evidencias son `exp-x/a1` o el id
    de una experiencia, un proyecto, una formación o una certificación.
  - Es un error que un logro o un proyecto cite una skill que no esté en `skills` ni en
    `basic_skills`. Una skill solo puede estar en una de las dos listas.
  - Las comprobaciones entre secciones se lanzan juntas (`ProfileConsistencyError`), pero solo
    cuando los campos ya validan: un perfil muy roto se corrige en dos pasadas.
  - Hash = sha256 del JSON canónico: los comentarios y el formato del YAML no crean versión.
    Migración `0002`: `content_hash` pasa de único a índice. Importar lo mismo que la versión
    vigente no crea versión; volver a un contenido anterior sí.
  - `get_profile` sale de una lista blanca de secciones y de campos de `personal`: nunca email,
    teléfono ni `private`. Sí devuelve los niveles F/C+/C/B y las marcas `nda`. La CLI es
    `jh profile show [--sections a,b]`, siempre con la vista pública (se quita `--public`).
  - `jh profile diff` muestra `private` como `<oculto>`.
  - `resolve_evidence(profile, ref)` es una función pura sobre una versión concreta: los CVs se
    verifican contra la versión con la que se redactaron.
  - Traducción de errores de Pydantic movida a `app/core/validation.py`, compartida por la
    interfaz para agentes y el perfil.
  - La auditoría guarda tal cual las listas de texto de los campos seguros (las `sections`).
- **Deuda:**
  - `preferences.locations.allowed` («solo si es híbrido o remoto») no se valida en el esquema:
    lo aplicarán los filtros duros de la fase 07.
  - Importar un perfil nuevo aún no recalcula los scores; llega con la fase 07.
  - Una clave YAML `NO` (Noruega) en `photo_policy.by_country` se lee como booleano: hay que
    escribirla entre comillas.

### 05b · Preferencias de CV en el perfil — 2026-09-28 · Claude Code (Opus 5.5)
- **Resumen:** `CvPreferences` admite `default_template`, `photo_file` y `template_rules`
  (`TemplateRule` con `when: TemplateRuleWhen` y `use`); `max_pages` y `photo_policy` no cambian.
  `demo/profile.example.yaml` vuelve a validar y un bloque `cv` antiguo sigue siendo válido.
  `public_view` ya incluía `preferences` entero; ahora un test cubre `preferences.cv`. 592 tests.
- **Decisiones:**
  - `default_template` y `use` se validan con el formato de id (minúsculas, dígitos, `-`, `_`);
    si la plantilla existe se comprueba en la fase 08.
  - Una regla necesita al menos una lista no vacía en `when` (`ats`, `country`, `domain`,
    `language`); `country` en ISO 3166-1 alfa-2 mayúsculas, `language` en minúsculas.
  - `photo_file` se valida con `PureWindowsPath`: se rechaza cualquier ancla (`/x`, `\x`, `C:x`,
    `C:\x`, UNC) y cualquier `..`. `\x` sin unidad es relativa para `is_absolute()`, pero en
    Windows `data / "\x"` acaba en la raíz de la unidad (lo detectó la revisión).
  - Los errores de código de idioma y país explican el formato esperado, no solo «formato no
    válido».
- **Deuda:**
  - No había `data/profile.yaml` para probar el criterio «sin tocarlo»; se probó con una copia del
    demo con el bloque `cv` antiguo, por test y con `jh profile validate`.
  - `docs/CV_TEMPLATES.md` habla de `data/photo.*`, pero el perfil ya dice qué fichero usar
    (`photo_file`): alinearlo en la fase 08.
  - `country: [NO]` (Noruega) en `template_rules` se lee como booleano, igual que en
    `photo_policy.by_country`: hay que escribirlo entre comillas.
