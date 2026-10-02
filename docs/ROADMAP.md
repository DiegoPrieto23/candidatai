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
| 06 | Frontend base | ✅ | UI con bandeja de ofertas, ficha y alta por URL o texto; `jh serve` |
| 07 | Matching y triaje | ✅ | Filtros duros, score, skill `evaluar-encaje`, aprobar o descartar en la UI |
| 08 | CV a medida con plantillas | ✅ | `generar-cv` produce CVs verificados; plantilla, foto y color se cambian en la UI sin agente; tu CV de Word como base |
| 08.1 | ↳ Contenido, verificación y motor docx | ✅ | `generar-cv` produce un PDF verificado con `ats-simple` y la oferta pasa a `cv_ready` |
| 08.2 | ↳ Foto, renders múltiples y UI | ✅ | Plantilla, foto y color se cambian en la UI sin agente; `clasica-foto` |
| 08.3 | ↳ Importar plantillas desde Word y «Mi CV» | ✅ | Subes tu CV de Word, se convierte en plantilla por defecto y los CVs a medida salen con tu diseño, tu orden de secciones y tus secciones extra |
| 08c | Carta de presentación | ⏳ | `generar-carta` redacta y verifica la carta según tus indicaciones (generales y de cada oferta); TXT para pegar y PDF a juego con el CV |
| 08b | Plantillas html | 🚧 | Importar diseños desde PDF o imagen (Canva…), también como «Mi CV», y plantilla integrada de dos columnas |
| 09 | Conectores de ATS y scheduler | ✅ | Ingesta diaria de empresas objetivo sin intervención |
| 09b | Alertas, captura y búsqueda con navegador | 🚧 | Las alertas de LinkedIn y otros portales llegan solas por correo, cualquier oferta entra con un clic desde el navegador y, opcionalmente, el agente recorre portales |
| 09b.1 | ↳ Ofertas resumen y alertas por correo | ✅ | Las alertas de correo (IMAP en solo lectura o `data/inbox/`) crean ofertas resumen en «Alertas», ordenadas por prefiltro y que caducan solas |
| 09b.2 | ↳ Botón «Enviar a Job Hunter» | ✅ | Extensión de Chromium que manda la oferta que estás viendo y completa los resúmenes |
| 09b.3 | ↳ Plataformas y búsqueda con navegador | ⏳ | `list_sources`, `save_source`, `record_source_run` y pantalla «Plataformas» |
| 10 | Seguimiento y analítica | ⏳ | Kanban, seguimientos pendientes, dashboard del embudo |
| 11 | Candidatura asistida | ⏳ | Rellenado con Playwright y envío tras tu confirmación |
| 12 | Demo, compatibilidad y portfolio | ⏳ | Modo demo, matriz de agentes probada, evals publicados |

**MVP usable:** al terminar la 08 ya puedes pegar ofertas, triarlas y sacar CVs a medida; con la
08c, también cartas de presentación. La 08c va antes que la 08b, aunque el orden entre ambas da
igual (la que llegue después añade la carta a las plantillas html).

**Skills que se desbloquean por fase:** `actualizar-perfil` tras la 05; `procesar-ofertas` tras la
04 (y con perfil, tras la 05); `evaluar-encaje` tras la 07; `generar-cv` tras la 08; `importar-plantilla-cv` tras la 08 para
Word y tras la 08b para PDF, imagen o HTML; `generar-carta` tras la 08c;
`revisar-linkedin` funciona tras la 05, pero rinde mucho más desde la 07, cuando ya hay ofertas
aprobadas de las que sacar las keywords; `buscar-ofertas` tras la 09b; `preparar-candidatura`,
`preparar-entrevista` y `resumen-diario` tras la 10.

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

### 06 · Frontend base — 2026-09-28 · Claude Code (Opus 5.5)
- **Resumen:** API REST en `app/api/` (`GET /status`, `GET /jobs`, `GET /jobs/{id}`, `POST
  /jobs/url|text`, `POST /jobs/{id}/events`), `jh serve` (solo 127.0.0.1) y `jh openapi`; servicios
  `search_jobs`, `get_job_view` y `add_user_event`. UI con Tailwind v4, shadcn/ui, React Router,
  TanStack Query y cliente `openapi-fetch` generado (`pnpm gen:api`): bandeja, ficha, alta y
  cabecera con recuentos y recordatorio de `procesar-ofertas`; tema claro/oscuro/sistema; móvil.
  Backend 624 tests (`services/` al 98 %), frontend 17 tests. Probado a mano por el usuario con
  Claude Code (`docs/pruebas/fase-06-prueba-manual.txt`): alta en la UI → `procesar-ofertas` →
  extracción visible en la ficha.
- **Decisiones:**
  - La ficha devuelve el texto original sin el envoltorio `<untrusted_job_posting>`: lo lee una
    persona y React lo pinta como texto (nunca `dangerouslySetInnerHTML`).
  - Errores de la API con el formato común de la interfaz para agentes; 404/409/422/503/500.
  - `POST /jobs/{id}/events` acepta solo `USER_EVENTS` (actor `user` del catálogo, sin
    `cv_rendered`, que llega en la 08). La UI solo usa la nota; aprobar/descartar, en la 07.
  - La bandeja usa su propio servicio (con `remote_mode`, `q`, `offset` y `total`); `list_jobs`
    de los agentes no cambia, así que la paridad MCP ↔ CLI sigue igual.
  - Las llamadas de la UI no se auditan en `mcp_calls`.
  - `frontend/src/api/openapi.json` y `schema.d.ts` se versionan; un test del backend falla si
    se desfasan.
  - Diseño: neutros zinc, un único acento verde azulado, ámbar solo para el aviso de inyección,
    Geist, iconos Phosphor. Las etapas se distinguen por intensidad del acento.
  - `strictPort` en Vite: CORS solo admite `http://127.0.0.1:5173` exacto.
- **Deuda:**
  - El CLI de shadcn resolvió mal el alias `@/lib/utils` (instaló un paquete `cn` ajeno y usó
    lucide): se corrigió a mano. Al añadir componentes, revisar sus imports.
  - Bundle de 540 kB (164 kB gzip): partir por rutas si crece.
  - `openapi-typescript` 7 declara TypeScript 5 como peer; funciona con el 6.
  - Al parar `pnpm dev` desde un agente en Windows puede quedar Vite huérfano ocupando el 5173;
    la guía explica cómo cerrarlo.

### 07 · Matching y triaje — 2026-09-28 · Claude Code (Opus 5.5)
- **Resumen:** `services/matching/` con filtros duros (seniority, años, modalidad, ubicaciones,
  idiomas MCER y palabras de descarte), cobertura de skills ponderada por nivel con
  `config/skill_aliases.yaml`, similitud semántica con sentence-transformers (extra opcional
  `matching`), score 0-100 con desglose y evaluación (`jh eval matching`, 20 casos semilla en
  `evals/matching/`). Cola de tareas y `jh worker`; migraciones `0003` (`matches.extraction_id`)
  y `0004` (`matches.scoring_key`); `jh match rescore`.
  Herramientas `get_match` y `save_fit_assessment` con paridad; `list_jobs` ordena por score. API
  `GET /triage` y `GET /jobs/{id}/match`; UI de triaje con atajos (J/K, A, D + 1-6, O), descarte
  con motivo obligatorio, deshacer, panel de encaje y «Reabrir» en la ficha, score en la bandeja.
  Backend 827 tests (`services/` al 98 %), frontend 35. Guía de prueba manual en
  `docs/pruebas/fase-07-prueba-manual.txt` y ofertas de prueba con `scripts/seed_triage_demo.py`.
- **Decisiones** (ADR-015):
  - sentence-transformers es un extra opcional: sin él (o con `JH_EMBEDDINGS=off`) la similitud
    no cuenta y su peso se reparte; `jh doctor` avisa. Los tests usan un embedder falso.
  - Los filtros duros se aplican al guardar la extracción (`save_extraction` devuelve
    `hard_filters`); el score se encola. Un match guarda `extraction_id` y `profile_version_id`, y
    `get_match` y el triaje lo recalculan si está desfasado: el triaje funciona sin worker.
  - El match también guarda `scoring_key` (versión del scorer, políticas, alias y modelo de
    embeddings): instalar el extra `matching` o editar `policies.yaml` lo deja desfasado.
    `jh match rescore` recalcula las ofertas abiertas sin esperar a que se consulten.
  - Importar un perfil nuevo encola `rescore_all`, que puede cerrar ofertas en triaje que ya no
    pasan; nunca las que el usuario reabrió tras un `hard_filter_failed`.
  - Descartar desde la UI exige `reason` (`skills`, `seniority`, `location`, `salary`, `company`,
    `other`; `other` con nota) para la analítica de la fase 10. El agente sigue con `note`.
  - Preferencias del score: puesto según el orden de `roles`, comparando por partes del título
    (fuera y dentro de paréntesis, separadas por « - », « | » o « / »), sin «(m/f/d)» ni
    seniority; todas las palabras del rol deben aparecer y el parecido es `token_sort_ratio`;
    modalidad según el orden de `remote_modes`; zona preferida 1, permitida 0,6, desconocida 0,5.
  - Seniority: pasan solo los niveles de `seniority_target`, que es la lista de todos los que
    acepta el candidato, por arriba y por abajo (quien busca mid puede no querer junior; quien
    empieza, no querer senior). Sin tolerancia global en `policies.yaml`: lo decide cada perfil,
    y `actualizar-perfil` lo pregunta. «Nativo» cuenta como C2; un nivel de idioma que no se
    entiende no descarta.
  - Rol `extractor`: `responsibilities` en el idioma de la oferta y `domain` como sector (deuda
    de la fase 04).
  - `jh doctor`: el aviso de `data/cv_template.docx` (diseño de la fase 01, anterior al ADR-014) se
    sustituye por «Plantillas de CV», que lista las de `templates/` y `data/templates/` con
    `template.yaml`. `Settings.cv_template_path` pasa a `user_templates_dir`.
- **Deuda:**
  - «Sales Engineer (Data Platform)» ya no cuenta como «Data Engineer», pero el puesto solo pesa
    un tercio del 15 % de preferencias: con todas las skills cubiertas sigue por encima del umbral
    (caso trampa del set de evaluación). Para descartarlo, `discard_title_keywords`.
  - El modelo de embeddings no se ha elegido aún con el set de evaluación (ADR-006): hay que
    instalar el extra y comparar informes. Los umbrales `similarity_floor/ceiling` son iniciales.
  - `GET /triage` y `get_match` pueden escribir (match y `scored`) al consultar; con embeddings, la
    primera consulta carga el modelo y tarda.
  - `save_fit_assessment` sigue pidiendo permiso en Claude Code (no está en
    `.claude/settings.json`): en `evaluar-encaje` con muchas ofertas, un permiso por oferta.
  - La BD real del usuario necesita `jh db upgrade` (hasta 0004).

### 08.1 · CV: contenido, verificación y motor docx — 2026-09-28 · Claude Code (Opus 5.5)
- **Resumen:** migración `0005` (`document_renders`; `documents` sin rutas; `applications.render_id`),
  evento `cv_rendered`, esquemas `CvContent`, `CvRenderOptions`, `CvVerification` y `TemplateMeta`
  (`app/schemas/cv.py`) y `services/documents/`: registro de plantillas, resolución de opciones
  (ATS por URL, país con `config/countries.yaml`, sector, idioma), contexto del contrato (fechas y
  `labels` es/en, contacto desde el perfil), motor docx, PDF con LibreOffice o Word, comprobaciones
  (contenido, páginas, cobertura, avisos), previews y servicio. Plantilla `ats-simple` generada por
  `scripts/build_builtin_templates.py` (reproducible, con test que compara con la versionada). Cinco
  herramientas MCP/CLI con paridad y `jh doctor` con una conversión real. 966 tests de backend.
  Flujo probado por CLI con LibreOffice: rechazo con detalle → PDF de 1 página → `cv_ready`.
- **Decisiones** (ADR-017; se numeró 016 y se renumeró al coincidir con la 016 de la 09b):
  - `cv_ready` cuando un mismo documento está verificado con `passed` y tiene un render sin
    `too_long`, en cualquier orden; `cv_rendered` es reservado (solo el servicio de render).
  - País por `countries.yaml` (sin nombres ambiguos); varios países: la regla encaja con alguno y la
    foto `auto` exige que todos la permitan. Si la regla o `default_template` piden una plantilla
    que no existe, aviso `template_not_found` y se sigue (el perfil demo pide `clasica-foto`, que
    llega en la 08.2).
  - Contacto e idioma regional los decide el código; «conocimientos de X» cuenta como X; las skills
    de nivel B cuentan como básicas.
  - `jh cv save --file F` recibe `{content, render_options}` (`CliSpec.file_keys`).
  - Primer render sin `too_long` seleccionado; un render fallido borra sus ficheros.
  - `alembic/env.py` desactiva las claves foráneas durante las migraciones en SQLite y comprueba
    al final que no queda ninguna rota (la recreación de `documents` en modo batch lo necesitaba).
  - Los grupos de skills del contexto son objetos: en Jinja, `s.items` de un dict es el método.
  - `find_soffice` pasa de `doctor.py` a `documents/pdf.py`; errores nuevos `pdf_unavailable` y
    `pdf_failed`.
- **Deuda:**
  - Cada conversión arranca LibreOffice: unos 15 s por render en Windows. Un LibreOffice en
    segundo plano lo bajaría a 1-2 s si la UI de la 08.2 lo necesita.
  - `preferences.cv.max_pages` del perfil no se usa: manda `max_pages` de la opción o de la
    plantilla (como dicen `CV_TEMPLATES.md` y `POLICIES.md` §3). Decidir en la 08.2.
  - Mientras el servidor MCP de Claude Code está abierto, `uv run`/`uv sync` fallan al reinstalar
    `jh-mcp.exe` (fichero en uso): usar `uv run --no-sync` o cerrar la sesión. Afecta también a
    `pnpm gen:api`.
  - `validate` de plantillas solo comprueba variables de primer nivel (`labels.foo` inexistente no
    se detecta hasta renderizar).
  - La BD real necesita `jh db upgrade` (hasta 0005).

### 08.2 · CV: foto, renders múltiples y UI — 2026-10-01 · Claude Code (Opus 5.5)
- **Resumen:** `documents/photo.py` (búsqueda, recorte centrado por forma con EXIF y caché en
  `data/cache/photo/`), foto real en el render (`auto`/`include`), plantilla integrada
  `clasica-foto` (cabecera con foto circular en tabla sin bordes, 4 colores de acento) y foto
  ficticia `demo/photo.png` generadas por `scripts/build_builtin_templates.py`, previews
  `preview.png` con `pypdfium2`, `select_render` y `template_changed`, rutas de API
  (`/templates`, `/jobs/{id}/cv`, `/documents/{id}/renders`, `/renders/{id}/select|pdf|docx`) que
  solo sirven ficheros desde `data/` y las carpetas de plantillas, sección «CV» en la ficha
  (selector con miniaturas, foto, color, secciones ocultas, renders con avisos, comparación lado
  a lado y «Usar este para enviar»), página **Plantillas** y aviso de foto en `jh doctor`.
  1000 tests de backend y 46 de frontend.
  Prueba manual con datos demo aislados y LibreOffice: oferta en `cv_ready` con `clasica-foto` →
  render por la API de la UI con `clasica-foto` sin foto, en verde y sin proyectos → PDF correcto
  en ~12 s → seleccionado para enviar. La UI no se probó en navegador (extensión de Chrome sin
  conectar): solo con sus tests.
- **Decisiones:**
  - Foto: `preferences.cv.photo_file` y, si no existe, el primer `data/photo.*` (jpg, jpeg, png,
    webp; heic solo si Pillow lo abre). Las que no se pueden abrir se ignoran.
  - `preferences.cv.max_pages` pasa a opcional (`null` por defecto) y cuenta: opción > perfil >
    plantilla. Los perfiles guardados con `max_pages: 1` siguen igual.
  - `select_render` admite también un render `too_long` (decides tú); no registra evento.
  - `GET /jobs/{id}/cv` devuelve `cv: null` (no 404) si aún no hay CV, con `can_render`.
  - La API sirve renders solo desde `data/cvs/` (no todo `data/`, donde la 09b guardará
    `data/capture_token`); ruta fuera o fichero inexistente: 404 `not_found` (sin decir por qué).
  - La sección «CV» de la ficha sale en una lista explícita de etapas (de `approved` en adelante;
    en `closed`, solo si hubo CV), para que la etapa `pending_detail` de la 09b no la muestre.
  - Compatibilidad con la 09b (ya en `main`): la ADR de la 08.1 pasa a ser la ADR-017. Al
    implementar la 09b: `cv_rendered` entra en los tests evento × etapa con `pending_detail`, el
    check de IMAP de `jh doctor` se añade a la lista de `test_cli_doctor_json` junto a «Foto del
    CV», y su migración va después de la `0005`.
  - `TemplateInfo.has_preview` y `sections` tipado; `pdf_unavailable` → 503 y `pdf_failed` → 500.
  - El conversor falso de los tests declara Cambria para que las integradas no den
    `font_substituted`.
- **Deuda:**
  - Cada render desde la UI tarda ~10-15 s (LibreOffice arranca en cada conversión). La UI lo
    indica; un LibreOffice en segundo plano lo bajaría.
  - La comparación lado a lado usa el visor de PDF del navegador en un `iframe`.
  - `template_changed` recalcula el hash de cada plantilla en cada consulta del CV.
  - La BD real sigue necesitando `jh db upgrade` (hasta 0005); la 08.2 no añade migraciones.

### 08.3 · CV: importar plantillas desde Word y «Mi CV» — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** `services/documents/importer/` (`docx_xml`: párrafos numerados con fragmentos
  fusionados; `inspect`: página, fuentes que se ven, colores, tablas, cuadros de texto, imágenes,
  cabecera y pie, secciones en su orden, `capacity` medida y estimación de ATS; `mapping`: esquema
  y comprobación previa; `build`: aplica el mapeo y escribe `data/templates/<id>/`; `paths`: solo
  `data/`), `authoring.py`, CLI `jh templates inspect | build-docx | validate | preview`.
  `extra_sections` en perfil, `CvContent`, contrato, `ats-simple` y `clasica-foto`. «Mi CV» en la
  página Plantillas: subidas (`uploads.py`), original y preview con tu perfil lado a lado, «Usar
  por defecto» (`default_template.py`, ruamel.yaml) y etiqueta «Tu CV». 1046 tests de backend y 51
  de frontend. Prueba de humo con LibreOffice: Word ficticio → plantilla con el mismo diseño,
  orden de secciones y extensión. Prueba manual completa del usuario
  (`docs/pruebas/fase-08.3-prueba-manual.txt`, también la parte 4 con su CV de Word): todo bien.
  Cierra la fase 08.
- **Decisiones:**
  - Mapeo por párrafo: `static` (por defecto), `delete`, `variable` (`text` o `runs` con el
    formato del fragmento `like`, para «**Rol** | Empresa») y `photo`; bloques con `start`/`end`
    y `scope: row` para filas de tabla; `header` → `layout.header_paragraphs` (carta de la 08c).
  - Antes de tocar el Word, el mapeo se monta como plantilla Jinja de borrador y se renderiza con
    todo el perfil demo: bloques sin cerrar, variables fuera del contrato y atributos inexistentes
    salen con el índice del párrafo. Si la plantilla final no renderiza, no queda nada (staging en
    `data/tmp/`).
  - Secciones de `template.yaml` en el orden en que las usa el mapeo; `capacity` y páginas
    medidas en el original; fuentes efectivas por caracteres (fragmento → estilo y `basedOn` →
    por defecto → tema), no las de estilos sin usar.
  - Secciones extra con un único bucle genérico `extra_sections` (título + items); sus ids
    cuentan como de primer nivel, así `<sección>/<item>` no choca con `exp-x/a1`.
  - Render con `SandboxedEnvironment` (docxtpl y comprobación del mapeo) y mapeos sin `__` ni
    `{#`: una plantilla importada de un CV ajeno no puede llegar a atributos internos de Python
    (lo detectó la revisión).
  - Una subida está «importada» si una plantilla tuya tiene un `source.*` con el mismo sha256: no
    se apunta el origen en ningún sitio. Subidas: 10 MB, nombre saneado (también nombres
    reservados de Windows), firma del contenido y nunca se sobrescribe.
  - «Usar por defecto» es la única escritura de `profile.yaml` desde la app: solo esa clave, con
    ruamel.yaml (`null` explícito, LF conservado), validando antes de sustituir; sin copia, la
    versión anterior queda en `profile_versions`.
  - Errores nuevos: `exists` (409), `too_large` (413), `invalid_file` también en la API (422).
  - Dependencias: `python-multipart` y `ruamel.yaml`.
- **Deuda:**
  - Una foto flotante pasa a ir en línea; el color de acento no se parametriza en las importadas.
  - `GET /uploads` calcula el sha256 de subidas y originales en cada consulta (la UI sondea cada
    15 s); cachear por ruta, fecha y tamaño si hay muchos ficheros.
  - Un `--id` igual al de una integrada la sustituye en la galería (solo se avisa).
  - Con el servidor MCP de Claude Code abierto, `uv add`/`uv sync` y `pnpm gen:api` siguen
    fallando por `jh-mcp.exe` en uso: se instaló con `uv pip install` y se regeneró el cliente con
    `uv run --no-sync`. Ejecuta `uv sync --directory backend` con Claude Code cerrado.


### 08b · Motor html e importación de CVs en cualquier formato — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** motor html (`engines/html.py`: Jinja2 en sandbox → HTML saneado → PDF con
  Chromium de Playwright sin JavaScript ni red; solo sirve la carpeta de la plantilla, `fonts/` o
  `data/fonts/` y la foto), saneado en dos capas (`sanitize.py`: `validate` falla con fichero y
  línea; al renderizar se limpia el HTML y los CSS servidos), aviso `pdf_only` y renders sin DOCX.
  Plantilla integrada `moderna-2col` (barra lateral a sangre, foto circular, 4 colores, secciones
  extra, Lato OFL incluida). Importación desde PDF, imagen o HTML: `inspect` (páginas en PNG,
  bloques de texto con posición, tamaño y fuente, imágenes, paleta, columnas, barra, banda,
  márgenes, secciones con su columna, `capacity` y ATS), `scaffold-html` (una base de HTML y CSS
  que ya se parece al original) y `compare` (lado a lado con SSIM orientativa). `jh doctor`
  comprueba Chromium e imprime `moderna-2col` sin red. UI: «Solo PDF», «Original | Recreación» en
  la galería y en «Mi CV», y la subida ya no avisa de la 08b. 1084 tests de backend y 52 de
  frontend; los de Chromium se saltan si no está instalado (la CI lo instala). Prueba de los
  comandos y de la API con el CV ficticio de los fixtures: correcta. **Pendiente:** la prueba
  manual con un CV real (`docs/pruebas/fase-08b-prueba-manual.txt`, parte 4) y, con ella,
  `docs/AGENTS_COMPAT.md`.
- **Decisiones:**
  - Errores del motor html como los del PDF (`ChromiumUnavailableError` → `pdf_unavailable`,
    `HtmlRenderError` → `pdf_failed`): API, MCP y CLI no cambian. `EngineNotAvailableError` fuera.
  - La página se carga desde un origen virtual (`http://jh.local/`) con `route` sobre todo; además
    Chromium arranca sin resolución de nombres. Variables estrictas en Jinja (`StrictUndefined`):
    `validate` detecta `labels.foo` o `e.rol` en html (en docx sigue la deuda de la 08.1).
  - `inspect` de PDF con pypdfium2 carácter a carácter: tamaño efectivo con la matriz del carácter
    (Chromium dibuja a 0,75), negrita y cursiva por nombre y flags (el peso de pdfium no es
    fiable), espacios por el hueco típico de cada línea (con `letter-spacing` los de pdfium
    partían palabras). Logros por viñeta de texto o por sangría (las viñetas de lista se dibujan).
  - Columnas, barra lateral, banda y márgenes se estiman sobre la imagen (numpy), igual para PDF e
    imagen. Una imagen no se lee (sin OCR): secciones y `capacity` las pasa el agente.
  - Un HTML importado se imprime sin servir ningún fichero (su carpeta es `data/uploads/`). Los
    nombres de fuente del PDF se filtran antes de escribirlos en el CSS base.
  - La SSIM se calcula desenfocada y a 300 px: cuenta la maqueta, no el texto. Diseños distintos
    dan 0,4-0,65; es para ver si una vuelta acerca o aleja, no una nota.
  - Fuente de `moderna-2col`: Lato en woff2 (subconjuntos latin y latin-ext, 108 KB, OFL) en vez
    de los TTF completos (2 MB). Las integradas html se escriben a mano; el script solo hace su
    preview.
  - Una subida `.png` se guarda como `source.png` sin sustituirla por la miniatura (su sha256 la
    marca como importada).
  - Dependencias: `playwright` y `numpy`. Chromium se instala aparte (`playwright install
    chromium`; README, `jh doctor` y CI).
- **Deuda:**
  - Carta en html (punto 7 del encargo): la hará la 08c (`letter.html` en el motor html y en
    `moderna-2col`, y `importar-plantilla-cv` creándola desde la cabecera recreada).
  - `scan` y `clean_css` trabajan con expresiones regulares: escapes CSS (`u\72l(`) pasarían el
    escaneo. No salen a la red (route y sin DNS), pero `validate` no los avisa.
  - El orden de las secciones de un PDF es el del contenido: en diseños de Canva, con el texto en
    orden arbitrario, puede salir desordenado y el agente lo corrige con `--sections`.
  - `jh doctor` imprime `moderna-2col` en cada ejecución (unos 2 s).
  - Al probar la API se cerraron todos los `jh.exe` con `taskkill /IM`: no repetirlo, matar solo
    el PID del servidor de prueba.

### 09 · Conectores de ATS y scheduler — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** `services/ingestion/` con conectores de Greenhouse, Lever (global y UE) y Ashby, y
  opcionales InfoJobs y Adzuna con claves en `.env`. Cada endpoint se verificó contra su
  documentación y, de forma manual, contra tableros públicos reales: lectura sin ningún error por
  oferta. Además: filtro previo de título y ubicación (`prefilter.py`), `run_source` idempotente
  con `source_runs` (migración `0006`, adelantada desde la 09b) y `jh worker` con APScheduler
  (ingesta diaria a `connectors.daily_at`, recuperación al arrancar, reintentos y log legible en
  consola y `data/logs/worker.log`). También `jh sources add | list | test | run | enable |
  disable`, API `/sources`, pantalla **Empresas** («12 ofertas encontradas, 3 tras filtros») y
  aviso en `jh doctor`. 1183 tests de backend y 57 de frontend. Guía de prueba manual en
  `docs/pruebas/fase-09-prueba-manual.txt`. **Pendiente:** la prueba manual con tus empresas
  objetivo.
- **Decisiones** (ADR-019):
  - Filtro previo indulgente: el título debe contener todas las palabras de algún rol (la regla
    del score) o una `title_keywords` de la fuente. La ubicación debe encajar con tus zonas o ser
    remota si aceptas remoto. Sin ubicación o sin perfil, pasa.
  - Ya visto = mismo `source_id` + `external_id`, misma URL o misma huella: no se crea ni se pide
    el detalle. Dentro de una fuente con conector, ids distintos no son duplicado difuso entre sí
    (sin esto, «Senior Data Engineer» en remoto se cerraba como duplicado de «Data Engineer» en
    Vigo). Frente a otras fuentes, el difuso no cambia.
  - Una tarea `run_source` por fuente, en un solo hilo. Red, 5xx, 429 o fallo interno: se
    reintenta. 404 o formato inesperado: no. Si la fuente falla entera, `last_run_at` no avanza y
    al arrancar se vuelve a encolar. Los portales sin claves no se encolan. Las tareas que quedaron
    `running` vuelven a la cola al arrancar.
  - Primero la red y después la escritura, en un savepoint. Un fallo inesperado queda como
    `internal_error` sin dejar ofertas a medias.
  - Las respuestas de las APIs son contenido no confiable. URLs solo http(s), ids de ruta con
    `[A-Za-z0-9_-]`, sin redirecciones (Adzuna lleva las claves en la URL) y log de httpx en
    WARNING. Lo encontró la revisión.
  - Hora en `config/policies.yaml` (`connectors.daily_at: "07:30"`, `timezone: Europe/Madrid`).
  - La API usa `POST /sources/{id}/active` en vez de `PATCH`: CORS sigue con GET y POST.
  - Dependencia: `apscheduler` 3.x (la 4 sigue en alfa).
- **Deuda:**
  - Adzuna solo da un extracto de la descripción: tratar sus ofertas como resumen en la 09b.
  - El filtro previo deja fuera los títulos en otro idioma que tus roles (p. ej. «Ingeniero de
    datos» si solo tienes «Data Engineer»): añade el rol en los dos idiomas o usa `title_keywords`.
  - Sin herramientas MCP de fuentes: `list_sources`, `save_source` y `record_source_run` llegan con
    la 09b, y `jh sources list --json` ya devuelve la salida prevista.
  - InfoJobs y Adzuna solo se han probado con respuestas grabadas: no había claves.
  - `parse_datetime` toma como UTC las fechas sin zona (posible desfase de horas en `posted_at`).
  - Con el servidor MCP de Claude Code abierto, `uv add` sigue fallando: APScheduler se instaló con
    `uv add --no-sync` + `uv pip install`. Ejecuta `uv sync --directory backend` con Claude Code
    cerrado.
  - La BD real necesita `jh db upgrade` (hasta 0006).

### 09b.1 · Ofertas resumen y alertas por correo — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** la fase 09b se parte en tres encargos (`prompts/09b.1-*`, `09b.2-*` y `09b.3-*`) en
  la rama `fase/09b-alertas-captura-busqueda`. Esta subfase añade:
  - migración `0007` (`jobs.platform`, `jobs.detail_level`, índice único parcial
    (`platform`, `external_id`) y tabla `email_messages`);
  - etapa `pending_detail` y evento `detail_captured`;
  - `services/platforms.py` (LinkedIn, InfoJobs, Indeed y Tecnoempleo, con patrones verificados
    con URLs públicas reales);
  - prefiltro de resúmenes con la seniority del título;
  - conector de correo `services/ingestion/email/`: IMAP en solo lectura y `data/inbox/`, un parser
    de LinkedIn y otro genérico;
  - tareas `poll_email` y `expire_summaries` en el worker;
  - `jh alerts poll | list | expire`, `GET /alerts`, `POST /alerts/poll` y pantalla «Alertas»
    (`J`/`K`, `O` abre en el portal, `D` descarta, con deshacer);
  - comprobación IMAP en `jh doctor`.

  1304 tests de backend (uno de ellos con un servidor IMAP falso que falla ante cualquier
  escritura) y 60 de frontend.
- **Decisiones:**
  - Desde `pending_detail` solo se admiten `detail_captured`, `discarded`, `expired`,
    `duplicate_detected`, `injection_suspected` y `note`. `WORKING_STAGES` separa las demás
    transiciones (y el matching) de `OPEN_STAGES`. `detail_captured` es reservado: lo registrará la
    captura de la 09b.2.
  - El prefiltro se calcula al listar y no se guarda. Los resúmenes no se filtran al entrar: el
    usuario ya eligió sus alertas, y la bandeja los ordena.
  - `store_job` deduce `platform` de la URL cuando su id coincide con `external_id` (o no hay), y
    reconoce primero por (`platform`, `external_id`). LinkedIn y Indeed se guardan con su URL
    canónica; las demás, sin parámetros de seguimiento. Los redirectores de seguimiento se leen sin
    seguirlos.
  - La detección de riesgo de un resumen mira el texto de la oferta, no el HTML del correo: los
    «preheader» ocultos de las alertas marcarían `hidden_text` en todas.
  - IMAP: `EXAMINE`, `UID SEARCH SINCE` (`summary_expire_days`), primero solo los `Message-ID` y
    luego `BODY.PEEK[]` de los nuevos. TLS con `ssl.create_default_context()`: en Python 3.12,
    `IMAP4_SSL` sin contexto no verifica el certificado (lo detectó la revisión). Nombre de
    carpeta en UTF-7 modificado.
  - Un correo cuya oferta no se pudo guardar por un error de BD no se anota en `email_messages`,
    así que se reintenta. Un correo de plataforma conocida sin ofertas sí se anota, con el aviso
    `no_jobs_found`.
  - Parser: tarjeta = el bloque más grande que solo enlaza esa oferta, sin llegar a `body`; como
    mucho 8 líneas, 1000 enlaces y 200 ofertas por correo; sin caracteres de control.
  - `POST /capture` sin prefijo `/api`, como el resto de la API (docs corregidos).
  - `jh alerts` es solo CLI (no hay herramienta para agentes): lo usan la persona y el worker.
- **Deuda:**
  - **Faltan alertas reales.** El parser de LinkedIn y el genérico (InfoJobs, Indeed, Tecnoempleo)
    se construyeron con fixtures inventados que imitan la estructura conocida. Hay que afinarlos
    con correos reales en `data/inbox/samples/` (punto 7 del encargo).
  - Un correo sin `Message-ID` se descarga entero en cada pasada IMAP (se descarta luego por su
    hash).
  - `POST /alerts/poll` hace la red dentro de la petición (hasta 30 s de IMAP más las descargas).
  - Dar de alta por URL una oferta que ya está como resumen devuelve «ya existe» sin completarla:
    eso lo hará la captura de la 09b.2.
  - Una oferta de un correo sin empresa se descarta con el aviso `invalid_item`.
  - `.env.example` sin las variables `JH_IMAP_*`: el agente no puede leerlo ni editarlo
    (permisos). Hay que añadirlas a mano.
  - La BD real necesita `jh db upgrade` (hasta 0007).

### 09b.2 · Botón «Enviar a Job Hunter» — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:**
  - `services/capture.py`: token con `jh capture token` (solo su sha256 en `data/capture_token`,
    comparación en tiempo constante) y captura. Completa un resumen (`detail_captured`, actor
    `user`), reconoce lo ya guardado o da de alta con la fuente `browser_capture`, con detección de
    riesgo sobre el texto y el HTML del bloque de la descripción.
  - `POST /capture`: origen y token en una dependencia que va antes que el cuerpo (403/401; 503 si
    no hay token).
  - `jh doctor` dice si la captura está lista.
  - Extensión Manifest V3 en `extension/`: JavaScript plano, popup, opciones, extractores
    (LinkedIn, Indeed, InfoJobs, Tecnoempleo, JSON-LD y `main`), iconos y README para Chrome y Edge.
  - Tests: 1330 de backend y 72 de frontend, de los que 12 son de la extensión, con HTML inventado.
- **Decisiones:**
  - **Id fijo:** `key` pública en el manifiesto, así que el id es
    `hnaofhehllbkghfehnehamjbkcmdjmle` en cualquier equipo, en Chrome y en Edge. Es el valor por
    defecto de `JH_CAPTURE_EXTENSION_ID`. La clave privada no hace falta para cargarla sin
    empaquetar y no se guardó.
  - **Popup** con el resultado y «Abrir ficha» (un badge no admite enlaces). El badge queda como
    señal en la pestaña: ✓, = o !.
  - **Pestaña:** el popup manda el `tabId`, y el service worker solo atiende mensajes de su propio
    `popup.html`.
  - **Sin empresa** en una oferta nueva: 422, que pide seleccionar el texto con la empresa.
  - **Sin CORS para la extensión**, a diferencia del encargo: sus `host_permissions` la eximen, y
    añadirla le dejaría leer toda la API sin token. Lo señaló la revisión. CORS sigue solo para
    la UI.
  - **Sin `main` en portales conocidos:** si su HTML cambia, la extensión no manda la página
    entera. Además, un resumen no se completa con texto de `main` sin selección, porque podría ser
    la lista de resultados de LinkedIn. Lo encontró la revisión.
  - **Orden de la captura:** primero se busca la oferta y luego se exige la descripción (200
    caracteres), así una ya guardada se reconoce aunque falle el extractor.
  - **URLs:** la extensión quita el fragmento y, si la URL es enorme, se queda solo con
    `currentJobId`. La app guarda la URL canónica en LinkedIn e Indeed, y en el resto la recorta a
    2000 caracteres quitando la query si hace falta.
  - **Texto:** se usa `innerText`, que respeta el CSS; en los tests, un recorrido que salta lo
    oculto en línea, scripts y botones, con un salto de línea por bloque. El HTML del bloque sí
    viaja, para detectar `hidden_text`.
  - **Tests de la extensión:** los ejecuta el Vitest del frontend (`server.fs.allow` incluye
    `../extension`), sin dependencias en `extension/`.
  - El test de una oferta sola de la 09b.1 ya no depende del fin de línea: `core.autocrlf` deja
    los `.eml` con CRLF en Windows.
- **Deuda:**
  - **Prueba manual pendiente** (`docs/pruebas/fase-09b-prueba-manual.txt`, que cubre también la
    09b.1): cargar la extensión, enviar una oferta real de LinkedIn (y de otros portales) y
    generar su CV. Los selectores de los portales se escribieron sin páginas
    reales delante: hay que ajustarlos con esa prueba.
  - El token vive sin cifrar en `chrome.storage.local`, como en cualquier extensión.
  - El puerto de la API (8000) está fijo en el manifiesto y en `core.js`.
  - `.env.example` sigue sin `JH_IMAP_*` ni `JH_CAPTURE_EXTENSION_ID` (el agente no puede
    editarlo).

