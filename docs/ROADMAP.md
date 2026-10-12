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
| 08c | Carta de presentación | ✅ | `generar-carta` redacta y verifica la carta según tus indicaciones (generales y de cada oferta); TXT para pegar y PDF a juego con el CV |
| 08c.1 | ↳ Indicaciones, contenido, verificación y render básico | ✅ | `generar-carta` guarda y verifica una carta que sigue tus indicaciones; PDF con `carta-simple` y TXT |
| 08c.2 | ↳ Diseño a juego con el CV | ✅ | Carta con la cabecera y el estilo de tu plantilla (integradas, html e importadas con `build-letter`) |
| 08c.3 | ↳ API, UI y paquete de candidatura | ✅ | Sección «Carta de presentación» en la ficha y la carta en el paquete de candidatura |
| 08b | Plantillas html | ✅ | Importar diseños desde PDF o imagen (Canva…), también como «Mi CV», y plantilla integrada de dos columnas |
| 09 | Conectores de ATS y scheduler | ✅ | Ingesta diaria de empresas objetivo sin intervención |
| 09b | Alertas, captura y búsqueda con navegador | ✅ | Las alertas de LinkedIn y otros portales llegan solas por correo, cualquier oferta entra con un clic desde el navegador y, opcionalmente, el agente recorre portales |
| 09b.1 | ↳ Ofertas resumen y alertas por correo | ✅ | Las alertas de correo (IMAP en solo lectura o `data/inbox/`) crean ofertas resumen en «Alertas», ordenadas por prefiltro y que caducan solas |
| 09b.2 | ↳ Botón «Enviar a Job Hunter» | ✅ | Extensión de Chromium que manda la oferta que estás viendo y completa los resúmenes |
| 09b.3 | ↳ Plataformas y búsqueda con navegador | ✅ | `list_sources`, `save_source`, `record_source_run` y pantalla «Plataformas»; LinkedIn solo lo activa el usuario |
| 10 | Seguimiento y analítica | ✅ | Kanban, seguimientos pendientes, dashboard del embudo y paquete de candidatura |
| 10.1 | ↳ Seguimiento: kanban, ficha de proceso y calendario | ✅ | Kanban que solo mueve con eventos, hitos con hora de Madrid y contactos, aviso de seguimientos, `list_followups_due`, `list_upcoming` y `.ics` por hito y en feed |
| 10.2 | ↳ Analítica: dashboard del embudo | ✅ | Página «Embudo»: conversión por paso, fuente, puesto y semana; tiempo hasta la primera respuesta; motivos de descarte; `get_funnel_stats` |
| 10.3 | ↳ Paquete de candidatura | ✅ | `save_application_answers` y sección «Paquete de candidatura»: CV elegido, respuestas editables con botón de copiar y hueco de la carta (08c) |
| 11 | Candidatura asistida | ✅ | Rellenado con Playwright y envío tras tu confirmación |
| 11.1 | ↳ Motor de rellenado y envío protegido | ✅ | El worker rellena Greenhouse, Lever, Ashby y formularios genéricos, se para con captcha o login y solo envía con una confirmación de un solo uso |
| 11.2 | ↳ Revisión, envío y UI | ✅ | Pantalla de revisión en la ficha, «Enviar» con el nombre de la empresa, «Lo termino yo» y prueba manual con una oferta real |
| 12 | Demo, compatibilidad y portfolio | ✅ | Modo demo, matriz de agentes probada, evals publicados |
| 12.1 | ↳ Modo demo | ✅ | `jh demo seed` llena `data-demo/` con 60 ofertas, 8 semanas de historial y 2 CVs; banner en la UI |
| 12.2 | ↳ Evals de matching y de CV | ✅ | 80 casos de matching con `evals/REPORT.md` y `jh eval cv` sobre 10 casos |
| 12.3 | ↳ Compatibilidad, README y seguridad | ✅ | Matriz de agentes probada, README de portfolio y repositorio revisado |
| 13 | Contexto y documentos | ✅ | `data/contexto/*.md` (estilo, perfil conductual, criterios, narrativa) que orientan sin respaldar hechos; `data/documentos/` y archivo de cada candidatura enviada |
| 14 | Huecos de skills y vocabulario | ✅ | Página «Skills»: ausentes agregadas; «es lo mismo que…» añade el alias y recalcula; huecos reales → skill `plan-formacion` |
| 15 | Respuestas por correo y seguimientos | ✅ | Los correos de las empresas proponen el evento (entrevista, rechazo…) en la ficha y tú lo aceptas; borradores de seguimiento y agradecimiento |
| 15.1 | ↳ Ingesta y clasificador | ✅ | IMAP en solo lectura (solo cabeceras salvo lo que casa con una candidatura), `<untrusted_email>`, rol `clasificador` y skill `revisar-respuestas` |
| 15.2 | ↳ Bandeja «Respuestas» | ✅ | Aceptar (tal cual o cambiada) o ignorar, solo desde la UI; aviso en la ficha y «Revisar respuestas» en Inicio |
| 15.3 | ↳ Borradores de seguimiento | ✅ | `save_message_draft`, tope de 2 seguimientos, `thanks_due`, skill `redactar-seguimiento` y sección «Borradores» |
| 16 | Ofertas vivas, republicadas y búsqueda ampliada | ✅ | Aviso de oferta cerrada o republicada; títulos parecidos; descubrir tableros de Greenhouse/Lever/Ashby de tus empresas |
| 16.1 | ↳ ¿Sigue abierta? y republicadas | ✅ | `jobs.signals` (ADR-028), `check_job_open`, tarea diaria `check_open`, aviso en la ficha que propone descartar, «Republicada ×N» en bandeja y triaje |
| 16.2 | ↳ Búsqueda ampliada | ✅ | `get_search_titles` y skill `ampliar-busqueda`; `jh sources discover` sobre Greenhouse, Lever y Ashby |
| 17 | Entrevistas: simulacro y repaso | ✅ | Plan de preparación, simulacro con feedback, repaso posterior con notas y historias STAR nuevas |
| 18 | Contactos, mensajes e investigación de empresas | ⏳ | Tus contactos de LinkedIn (CSV) cruzados con tus ofertas, borradores de mensaje y dosier de empresa con fuentes |
| 19 | Lote en segundo plano | ⏳ | «En segundo plano» además de «En terminal» para los skills que no preguntan (fase 2 de la ADR-024) |
| 20 | Calibración y patrones | ⏳ | «¿Acierta el score?»: respuesta por tramo de score, veredicto, fuente, plantilla y carta; retrospectiva semanal |
| 21 | Ofertas recibidas y salario | ⏳ | Comparar ofertas recibidas y la distancia a tu mínimo sin exponerlo al agente; preparar la negociación |
| 22 | LinkedIn por sus endpoints públicos (opcional) | ⏳ | Búsqueda pública sin sesión, apagada por defecto y con límites estrictos; ADR que matiza la 016 |

**MVP usable:** al terminar la 08 ya puedes pegar ofertas, triarlas y sacar CVs a medida; con la
08c, también cartas de presentación. La 08c va antes que la 08b, aunque el orden entre ambas da
igual (la que llegue después añade la carta a las plantillas html).

**Plan 13-22 (2026-10-11):** funciones de [AI Job Search](https://github.com/MadsLorentzen/ai-job-search)
y [career-ops](https://github.com/santifer/career-ops) que encajan con lo que ya hay y con las
reglas duras. Orden recomendado: 13 (base de las demás) → 14 → 15 → 16 → 17 → 18 → 19; la 20
cuando haya unas 20-30 candidaturas enviadas; la 21 cuando llegue la primera oferta; la 22 solo si
la quieres. Descartado: candidaturas automáticas (reglas 5 y 6), sincronización con Notion,
plantillas LaTeX (ya hay docx y html), portales daneses, descubrimiento de empresas financiadas
desde feeds externos y modelos llamados desde la app (ADR-001).

**Skills que se desbloquean por fase:** `actualizar-perfil` tras la 05; `procesar-ofertas` tras la
04 (y con perfil, tras la 05); `evaluar-encaje` tras la 07; `generar-cv` tras la 08; `importar-plantilla-cv` tras la 08 para
Word y tras la 08b para PDF, imagen o HTML; `generar-carta` tras la 08c;
`revisar-linkedin` funciona tras la 05, pero rinde mucho más desde la 07, cuando ya hay ofertas
aprobadas de las que sacar las keywords; `buscar-ofertas` tras la 09b; `preparar-candidatura`,
`preparar-entrevista` y `resumen-diario` tras la 10; la candidatura asistida (sin skill: se
usa desde la ficha) tras la 11; `plan-formacion` tras la 14; `ampliar-busqueda` tras la 16;
`simular-entrevista` y `repasar-entrevista` tras la 17.

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

### 09b.3 · Plataformas y búsqueda con navegador — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 09b. Añade:
  - esquemas `AgentBrowseSource`, `SourceRunSummary` y `AgentBrowseLimits`, y la política
    `agent_browse` en `core/policies.py`;
  - `services/ingestion/browse.py`: `save_source`, `record_run`, `update_settings` y
    `source_for_job`;
  - herramientas `list_sources`, `save_source` y `record_source_run`, y `add_job_from_text` con
    `source_id`, `platform` y `external_id`. `jh sources list` pasa al registro: misma salida, con
    `browse` y los límites;
  - error nuevo `not_allowed` (403 en la API) y `POST /sources/{id}/browse`;
  - pantalla «Plataformas» con el aviso de riesgo de LinkedIn;
  - skill `buscar-ofertas` al día y guía de prueba manual `docs/pruebas/fase-09b.3-prueba-manual.txt`.

  Sin migraciones: la configuración va en `sources.config`. Tests: 22 casos de paridad nuevos,
  tests del servicio y de la API, y 4 de frontend.
- **Decisiones:**
  - Una plataforma se identifica por su nombre normalizado. `priority` va de 1 a 10 (1, primero).
    `allow_agent_browsing` está activada por defecto (el usuario ya la aprobó en `configurar`),
    salvo en LinkedIn.
  - LinkedIn se reconoce por `platform` o por cualquier búsqueda de linkedin.com o lnkd.in (que
    pasa a ser LinkedIn en `platforms.py`). Un `true` del agente da `not_allowed`. Si lo activó el
    usuario, se conserva, y una plataforma LinkedIn no puede pasar a ser otra.
  - Defensas en el código, más allá del encargo (ADR-012):
    - `add_job_from_text` con `source_id` y `record_source_run` exigen la navegación activada;
    - una oferta de LinkedIn, por URL o por `platform`, solo entra por la plataforma LinkedIn;
    - las `search_urls` son del dominio de la plataforma conocida o, si no, todas del mismo sitio.

    Lo encontró la revisión.
  - `record_source_run`: `after_filters = created + existing`, actor `agent`, y `last_run_at` no
    retrocede. Las fechas del futuro (más de 5 minutos) se rechazan.
  - El alta de plataformas sigue siendo cosa del agente: la UI lista y edita prioridad, acceso y
    el interruptor.
- **Deuda:**
  - **Prueba manual pendiente** (`docs/pruebas/fase-09b.3-prueba-manual.txt`):
    `buscar-ofertas configurar` y un recorrido real con Claude in Chrome sobre una plataforma de
    acceso libre. Tienes que reiniciar Claude Code para que su servidor MCP cargue las herramientas
    nuevas.
  - Riesgo residual: la API local no tiene autenticación. Un agente con terminal podría activar
    LinkedIn con `confirm_risk: true` sin pasar por la UI. Está documentado en `FUENTES_OFERTAS.md` y
    en `POLICIES.md` §8.
  - `sources.active` no se usa en las plataformas: se apagan con `allow_agent_browsing`.
  - Siguen pendientes las pruebas manuales de la 09b.1 y la 09b.2, las variables de `.env.example`
    y `uv sync` con Claude Code cerrado.

### 10.1 · Seguimiento: kanban, ficha de proceso y calendario — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:** la fase 10 se parte en tres encargos (`prompts/10.1-*`, `10.2-*` y `10.3-*`) en la
  rama `fase/10-seguimiento-analitica`. Esta subfase añade:
  - migración `0008` (tablas `milestones` y `contacts`) y políticas `followups` y `calendar`;
  - `services/process.py` (hitos con su evento, contactos y ficha de proceso), `tracking.py`
    (seguimientos vencidos, próximos y kanban) y `calendar_ics.py` (iCalendar escrito a mano);
  - herramientas `list_followups_due` y `list_upcoming` con paridad, y `jh calendar export`;
  - API `/board`, `/followups`, `/upcoming`, `/jobs/{id}/process`, hitos, contactos,
    `/milestones/{id}/ics` y `/calendar.ics`; `POST /jobs/{id}/events` acepta `channel`;
  - UI: página «Procesos» (kanban con `@dnd-kit/core`, diálogo que registra el evento, próximos 7
    días y ayuda del calendario), sección «Proceso» en la ficha y aviso de seguimientos en la
    cabecera.

  Guía de prueba manual en `docs/pruebas/fase-10.1-prueba-manual.txt`.
- **Decisiones:**
  - Hitos en tabla propia, enlazados a su evento: crear una entrevista registra
    `interview_scheduled` y una prueba, `test_assigned` (con `payload.milestone_id`), en un
    savepoint. Si el evento no vale en la etapa, no queda el hito. Una entrevista hecha registra
    `interview_done`; reprogramar o cancelar deja una `note`. Plazos y otros no registran eventos.
    Un hito hecho o cancelado no vuelve atrás.
  - El kanban no cambia nada en local: soltar abre un diálogo con los eventos válidos
    (`TRANSITIONS` ∩ `USER_EVENTS`, que da la API). «CV listo» no se alcanza a mano. Hay también un
    botón «Mover» (teclado, lector de pantalla y tests: el arrastre no se simula en jsdom).
  - Cerradas en el tablero: solo las que llegaron a aprobarse, las 50 más recientes, con
    `reopen_to` calculado de sus eventos en una sola consulta.
  - Seguimiento vencido: etapa `applied` y N días (10) desde el último envío o `followup_sent`.
  - Próximos: desde las 00:00 de hoy hasta el final del último día (Madrid), más el
    `application_deadline` de las ofertas sin enviar.
  - `applied`/`applied_manually` desde la UI guardan `channel` y el `render_id` seleccionado.
  - Calendario: UTC, `VALUE=DATE` con fin exclusivo (un rango de varios días incluye el último),
    UID estable y `SEQUENCE`. Google Calendar no puede suscribirse a `127.0.0.1`: se importa el
    fichero (al reimportar, actualiza sin duplicar). El feed es para clientes de escritorio. El nombre
    del `.ics` es ASCII: la empresa es contenido no confiable y la cabecera va en latin-1 (lo vio la
    revisión).
  - Contactos solo en la UI: ninguna herramienta para agentes los devuelve.
  - Dependencias: `@dnd-kit/core` (frontend) y `tzdata` explícita (backend; `ZoneInfo` en Windows).
- **Deuda:**
  - **Prueba manual pendiente:** arrastre en el navegador e importación del `.ics` en Google
    Calendar (criterio de aceptación de la fase 10).
  - El feed solo lleva lo programado: un hito cancelado desaparece del calendario suscrito, pero en
    Google (importado) queda hasta que importes su `.ics` individual con `STATUS:CANCELLED` o lo
    borres a mano.
  - `uv add tzdata` se hizo con `--no-sync`: ejecuta `uv sync --directory backend` con Claude Code
    cerrado.
  - La BD real necesita `jh db upgrade` (hasta 0008).

### 10.2 · Analítica: dashboard del embudo — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:**
  - `services/analytics.py`: una CTE con una fila por oferta (pasos 0/1, fecha de envío y de
    primera respuesta) calculada en SQL sobre `events`. De ella salen, con `GROUP BY` en la BD, el
    embudo de 8 pasos, el resumen por fuente, por puesto (top 8 + «Otros» + «Sin extraer») y por
    semana ISO (con las vacías a cero), el tiempo hasta la primera respuesta y los motivos de
    descarte y de filtro duro. `since` filtra por `first_seen_at` desde las 00:00 de Madrid.
  - Interfaz para agentes: `get_funnel_stats` ↔ `jh stats funnel [--since] --json`, con 4 casos de
    paridad. API: `GET /stats/funnel?since=`.
  - UI: página «Embudo» con Recharts (dependencia nueva, cargada en diferido): cifras clave, embudo,
    primera respuesta, por semana, tablas por fuente y por puesto, motivos; selector de periodo
    (todo, 30 y 90 días, 12 meses o desde una fecha) y estados vacíos. Cada gráfica lleva una tabla
    oculta para lectores de pantalla. Colores `--chart-1`/`--chart-2` (azul y naranja) validados
    contra los fondos claro y oscuro (daltonismo y contraste).
  - `scripts/seed_funnel_demo.py`: 1 000 ofertas ficticias con su histórico (con `events.record()`)
    en `data/funnel-demo/`. El test de rendimiento siembra lo mismo y exige `GET /stats/funnel`
    < 1 s (mejor de 3, tras calentar): ~0,25 s. Sin índices nuevos ni migración (un índice
    `events(job_id, type, occurred_at)` no mejoraba nada).
  - 10 tests del servicio con un histórico hecho a mano (cifras exactas), 3 de API/rendimiento y 4
    de la página. 1 432 tests de backend y 94 de frontend.

  Guía de prueba manual en `docs/pruebas/fase-10.2-prueba-manual.txt`.
- **Decisiones** (definiciones en `DATA_MODEL.md` §Embudo):
  - Embudo **acumulado**: una oferta que llega a un paso cuenta en los anteriores (un
    `applied_manually` sin aprobar cuenta como aprobada), y una sola vez aunque se reabra.
  - Triada: `extracted` sin `hard_filter_failed`, o reabierta después del último. Con respuesta:
    respuesta, entrevista, prueba, oferta o rechazo con fecha ≥ primer envío.
  - Duplicadas (`duplicate_detected` no reabierta) fuera del embudo, contadas en
    `duplicates_excluded`. «Después» se decide como la proyección: por (`occurred_at`, `id`).
  - Mediana en Python sobre los días que calcula SQL (SQLite no tiene mediana).
  - Motivos y filtros cuentan ofertas (`COUNT DISTINCT`), no eventos.
  - Semana ISO en Europe/Madrid con la función SQLite `jh_iso_week` (registrada en
    `app/core/db.py` en cada conexión).
- **Deuda:**
  - **Prueba manual pendiente:** la guía de la 10.2 (carga < 1 s en el navegador, modo oscuro,
    móvil). En la revisión automática, la API respondió en ~0,5 s en frío con 1 000 ofertas.
  - `jh_iso_week` y `json_each` son de SQLite: pasar a Postgres (ADR-002) exige reescribirlas.
  - La barra de navegación se sale de la pantalla en móvil (en todas las páginas; ya pasaba antes).
  - El bundle principal sigue por encima de 500 kB (~800 kB, ya antes de la 10.2): habría que
    trocear más rutas.
  - `pnpm install` en el frontend para Recharts.

### 10.3 · Paquete de candidatura — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 10.
  - `ApplicationAnswers` en `schemas/llm_io.py` (las cuatro claves obligatorias; 1-50 respuestas).
  - Migración `0009`: `documents.edited_by_user`.
  - `services/answers.py`: `save_application_answers` (agente), `save_user_answers` (UI) y
    `get_package`. Validación con un detalle por problema y sin guardar nada.
  - Herramienta `save_application_answers` ↔ `jh applications save-answers ID --file F --json`,
    con 4 casos de paridad. API `GET /jobs/{id}/package` y `POST /jobs/{id}/answers`.
  - `ProcessDocuments.answers_document_id` ya se rellena.
  - UI: sección «Paquete de candidatura» en la ficha, entre «Proceso» y «CV». Muestra:
    - el CV elegido (abrir PDF, enlace a la sección CV);
    - las respuestas con «Copiar» y «Editar», aviso ámbar en las de `needs_user_input` y
      «Añadir pregunta»;
    - el hueco de la carta.
  - `CopyButton` compartido con «Procesos».
  - El skill `preparar-candidatura` aclara las evidencias válidas y que no hay campo de nota.
  - 13 tests de servicio y API y 5 de la sección. 1 448 tests de backend y 99 de frontend.

  Guía de prueba manual en `docs/pruebas/fase-10.3-prueba-manual.txt`.
- **Decisiones:**
  - Evidencias de una respuesta: las del CV (`evidence_refs`), los ids de las historias STAR,
    `extraction` y `user`. Una respuesta con texto necesita al menos una. Vacía, solo con
    `needs_user_input`.
  - Solo en `approved` y `cv_ready`: después del envío el paquete se ve y se copia, pero no se
    edita.
  - Edición del usuario: documento nuevo con `edited_by_user` y actor `user`. Manda el último y el
    anterior se conserva.
    - No exige evidencias, pero las que haya deben existir en la versión del perfil de las
      respuestas que edita.
    - Si cambia el texto, la UI añade `user` al respaldo. Vacía = pendiente de un dato tuyo.
  - `application_prepared` pasa a actor `agent`/`user` (antes ponía `system` en `DATA_MODEL.md`),
    con `payload.document_id` y `edited_by_user`.
  - El idioma del documento sale de la extracción (`es`/`en`; si no, `es`).
  - La clave de consulta del paquete cuelga de la del CV: renderizar o elegir otro render lo
    refresca.
- **Nota para la 08c:**
  - `JobPackage.cover_letter` es hoy `None`. La 08c lo cambia por la carta seleccionada (texto
    plano para copiar y `pdf_url` del render), y `ProcessDocuments.cover_letter_document_id` se
    rellena igual que `answers_document_id`.
  - En `PackageSection.tsx`, `CoverLetterSlot` pasa del aviso a la carta, con `CopyButton`.
  - La carta editada reutiliza `documents.edited_by_user`.
- **Deuda:**
  - **Prueba manual pendiente:** la guía de la 10.3. También siguen pendientes la de la 10.1
    (arrastre e importación del `.ics` en Google Calendar) y la de la 10.2.
  - La BD real necesita `jh db upgrade` (hasta 0009).
  - Que el salario vaya siempre con `needs_user_input` lo impone el skill. El código comprueba que
    las evidencias existen, no lo que dice la respuesta.
  - La suite del frontend es sensible a la carga: con otros procesos pesados en paralelo, algunos
    tests de páginas no tocadas superan los 5 s o el `findBy` de 1 s. Por separado, o con
    `--testTimeout=30000` y la máquina libre, pasan.

### 08c.1 · Carta: indicaciones, contenido, verificación y render básico — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:** la fase 08c se parte en tres encargos (`prompts/08c.1-*`, `08c.2-*` y `08c.3-*`)
  en la rama `fase/08c-carta-presentacion`. Esta subfase añade:
  - `preferences.cover_letter` en el perfil (opcional; también en `demo/profile.example.yaml`) y
    la política `cover_letter` validada;
  - migración `0010` (`cover_letter_briefs`);
  - `schemas/cover_letter.py`;
  - `services/documents/cover_letter.py`: brief, guardar con copia de las indicaciones usadas,
    validación, resolución de opciones a juego con el CV, render, selección, verificación, texto
    plano y edición del usuario (lista para la UI de la 08c.3);
  - eventos `cover_letter_generated` y `cover_letter_verified` (reservados, sin cambio de etapa);
  - plantilla integrada `carta-simple` (`kind: letter`, solo carta, acento libre);
  - las cinco herramientas con paridad (`jh letter brief|show|save|render|save-verification`);
  - el rol `verificador` también para cartas, y `generar-carta` y `actualizar-perfil` al día.

  17 tests del servicio y 13 casos de paridad. 1 495 tests de backend y 99 de frontend.
- **Decisiones:**
  - `TemplateMeta` gana `kind` (`cv` | `letter`) y `letter: {file}`.
    - Una plantilla `kind: letter` no necesita `template.*` ni secciones, y no aparece como
      plantilla de CV: `templates.get` y `list_templates` filtran por `kind`.
    - El contrato de la carta se valida aparte (`LETTER_CONTRACT_VARIABLES`).
  - `AccentColorOption.free`: admite cualquier `#RRGGBB` (lo usa `carta-simple` para heredar el
    color del CV).
  - El render del CV se parte en `write_files`, `store_files` y `prepared_photo`, que reutiliza
    la carta. Los motores aceptan `file` para renderizar `letter.*`.
  - Palabras: solo los párrafos, `\w+` Unicode.
  - Skills en texto libre:
    - se comprueban las de `keywords_targeted` y las de la oferta y las básicas nombradas en los
      párrafos, con los alias del matching;
    - una skill de la oferta que no está en el perfil solo puede nombrarse en un párrafo que cite
      `extraction` y nada del perfil: si cita también un logro, se la estaría atribuyendo (lo vio
      la revisión);
    - las claves se normalizan con `checks.skill_key`, como en el CV (quita «nociones de…»).
  - Evidencias citables: las del CV y las historias STAR (`checks.citable_refs`, compartido con
    las respuestas de la 10.3). `extraction` exige que haya extracción.
  - Contenido del documento: `{letter, instructions: {brief, preferences, max_words}}`. Las
    preferencias se copian como dict: si su esquema cambia, las cartas antiguas se siguen abriendo.
  - Opciones de la carta:
    - foto, color y página salen del render seleccionado del CV, también si se elige otra
      plantilla de carta a mano;
    - una plantilla elegida a mano sin carta da `not_found` (sin respaldo);
    - sin CV, se aplican las reglas del perfil.
  - El subtítulo de la carta es el del CV de la oferta o el `headline`. La fecha es la del día del
    render, en Europe/Madrid. El texto plano no lleva destinatario, fecha ni contacto.
  - `jh templates validate` acepta las plantillas solo de carta. `jh doctor` avisa si falta la
    carta de reserva (`cover_letter.fallback_template`).
  - La edición del usuario (`save_user_letter`) reutiliza las opciones del render seleccionado de
    la carta anterior.
- **Deuda y notas para la 08c.2 y la 08c.3:**
  - Toda carta salía con `carta-simple` y aviso `letter_fallback`; resuelto en la 08c.2.
  - `generar-carta` ya no mencionaba la UI de la ficha; resuelto en la 08c.3.
  - `service.select_render` y la API `/renders/{id}/select` solo aceptan CVs; la selección de la
    carta está en `cover_letter.select_render`. Unificarlo en la 08c.3. `/renders/{id}/pdf` ya
    sirve las cartas, porque no mira el tipo de documento.
  - El texto plano solo existe en el servicio: la API lo sirve en la 08c.3.
  - La BD real necesita `jh db upgrade` (hasta 0010).

### 08c.2 · Carta: diseño a juego con el CV — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:**
  - `ats-simple` y `clasica-foto` traen `letter.docx`: su misma cabecera (la de `clasica-foto`,
    con foto en tabla) y un cuerpo de carta común. Los genera `build_builtin_templates.py`, y
    los `template.docx` del CV no cambian ni un byte.
  - `moderna-2col` trae `letter.html` y `letter.css`, con la barra lateral (foto y contacto) y la
    cabecera del CV. Probada con Chromium: una página.
  - `jh templates build-letter <id> [--force]` (`importer/letter.py`): crea `letter.docx` de una
    plantilla docx del usuario desde su `template.docx`. Probado con una copia de una plantilla
    importada real: conserva su cabecera centrada y la fuente del cuerpo.
  - `jh templates preview <id> --letter` (carta de muestra, en la caché). `validate` comprueba
    y renderiza también la carta.
  - El skill `importar-plantilla-cv` tiene un paso «Carta de presentación a juego»: en docx,
    `build-letter`; en html, `letter.html` a mano.
  - 19 tests nuevos: integradas, foto y color del CV en la carta de `clasica-foto`,
    `moderna-2col` en PDF, hash y bloque `letter:` (CRLF, líneas vacías, en medio), `build-letter`
    con un Word ficticio con la cabecera en tabla, errores, corte de cabecera (con controles
    anidados), orden OOXML, preview y saneado de `letter.css` y `letter.html`. 1 515 tests de
    backend.
- **Decisiones:**
  - Hash por documento: el del CV ignora `letter.*` y el bloque `letter:` de `template.yaml`, y
    el de la carta ignora `template.docx|html`. Así, añadir la carta a las integradas no marca
    como «Plantilla cambiada» los CVs ya renderizados (comprobado contra el `template.yaml`
    anterior, con CRLF).
  - En html, los estilos de la carta van en `letter.css`, que también se sanea, para no tocar
    `style.css` ni el hash del CV.
  - `build-letter`:
    - la cabecera son los bloques del principio que solo usan `name`, `subtitle`, `contact` o
      `photo`, más los párrafos de control que los cierran;
    - el primer bloque con variables del cuerpo (o con `show`) corta. Una cabecera mezclada con
      el cuerpo (tabla a dos columnas) da error y la carta sigue con `carta-simple`;
    - `layout.header_paragraphs` solo dice si hay cabecera: los índices son del original, no de
      `template.docx`;
    - el cuerpo copia `pPr`/`rPr` del primer párrafo de contenido (no de títulos `labels.*`),
      sin viñetas, bordes ni sangría;
    - `letter:` se añade como texto al final de `template.yaml`, sin reescribir el resto;
    - se prepara en `data/tmp/` y solo se copia si valida. La carta y el YAML se copian con
      `os.replace`, primero la carta;
    - `pPr` y `rPr` se escriben en el orden de OOXML (`get_or_add_*` de python-docx): Word
      rechaza los hijos desordenados aunque LibreOffice los tolere (lo vio la revisión);
    - del párrafo del CV se toma la letra, no su énfasis (negrita, cursiva, color, mayúsculas);
    - avisa si la cabecera conservada no lleva contacto o subtítulo, y deja la carta a una
      columna si el CV acababa en varias.
  - La carta de muestra de la preview sale del perfil (resumen y primer logro de las dos
    primeras experiencias). Nunca se guarda.
- **Deuda:**
  - Las previews de la carta no están en la galería (UI de la 08c.3).
  - Los renders de carta hechos en la 08c.1 guardaron el hash completo de la plantilla; ahora es
    el de la carta. Nadie lo compara hoy: si la 08c.3 enseña «Plantilla cambiada» en las
    cartas, esos saldrán como cambiados una vez.
  - `build-letter` no sirve para cabeceras en el encabezado de página de Word: se conservan tal
    cual, porque las secciones no se tocan, pero el corte no las detecta como cabecera. Si el
    cuerpo empieza directamente, da error.

### 08c.3 · Carta: API, UI y paquete de candidatura — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 08c.
  - **API** (`routes/letters.py`):
    - `GET /jobs/{id}/cover-letter`: indicaciones, carta vigente con su TXT, plantilla del CV
      seleccionado y plantillas con carta;
    - `POST /jobs/{id}/cover-letter/brief`;
    - `POST /jobs/{id}/cover-letter`: edición del usuario;
    - `POST /cover-letters/{doc}/renders`;
    - `GET /cover-letters/{doc}/text`: TXT en UTF-8, `\r\n`, `Carta-<Nombre>.txt`;
    - `/renders/{id}/select` sirve para CV y carta (`service.render_kind`).
  - **UI**: sección «Carta de presentación» en la ficha, después de «CV»:
    - indicaciones de la oferta, editables, y resumen de las del perfil, con el límite resuelto;
    - con carta: texto, palabras/límite y verificación, «Copiar texto», «Descargar TXT»,
      «Editar» (por párrafos, más saludo y despedida, con recuento en vivo);
    - formulario «Diseño» («A juego con el CV (…)» u otra plantilla con carta), foto y color;
    - renders con avisos, «Descargar PDF», DOCX y «Usar esta para enviar»;
    - sin carta, qué pedir al agente. En `closed` sin carta no aparece. Tras enviar, solo se
      ve y se copia.
  - **Paquete de candidatura**: `JobPackage.cover_letter` (texto, palabras, estado, `pdf_url` del
    render seleccionado), con «Copiar carta» y «Abrir PDF».
    `ProcessDocuments.cover_letter_document_id` ya se rellena.
  - `generar-carta` vuelve a recordar lo que se hace en la ficha. README, `ARCHITECTURE.md` y
    guía de prueba manual de toda la fase (`docs/pruebas/fase-08c-prueba-manual.txt`).
  - 7 tests de API y 9 de frontend (8 de la sección y 1 del paquete con carta). 1 522 tests de
    backend y 108 de frontend.
- **Decisiones:**
  - La carta y el paquete cuelgan de la clave de consulta `cv`: cambiar el render seleccionado
    del CV refresca «A juego con el CV» y el paquete.
  - Edición:
    - cuando escribe el usuario, `user` vale siempre (su texto es su respaldo);
    - los párrafos que cambian añaden `user` en el servidor (`mark_user_paragraphs`), no en
      React. Antes lo hacía el frontend y fallaba sin indicaciones guardadas: lo vio la revisión;
    - «Guardar» se desactiva sin cambios (así no se pierde la verificación por nada) o sin
      ningún párrafo;
    - se reutilizan las opciones del render seleccionado de la carta anterior.
  - El TXT para copiar llega en la propia respuesta (`plain_text`); el de descarga, por su ruta.
  - «A juego con el CV» manda `template_id: null`; la foto «Como el CV» es `auto`.
- **Deuda:**
  - **Prueba manual pendiente:** `docs/pruebas/fase-08c-prueba-manual.txt` (criterio de aceptación
    de la fase: `/generar-carta` con indicaciones, PDF a juego y TXT sin errores; abrir los DOCX
    en Word).
  - La BD real necesita `jh db upgrade` (hasta 0010).
  - El recuento de palabras de la UI (`\p{L}\p{N}_`) puede diferir del `\w` de Python en casos
    raros de Unicode; manda el del servidor.
  - La suite del frontend sigue siendo sensible a la carga de la máquina (ver 10.3).

### 11.1 · Candidatura asistida: motor de rellenado y envío protegido — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:** la fase 11 se parte en dos encargos (`prompts/11.1-motor-rellenado.md` y
  `11.2-revision-envio-ui.md`) en la rama `fase/11-candidatura-asistida`. Esta subfase añade:
  - `services/applier/`:
    - `browser.py`: contexto persistente en `data/browser-profile/`, visible, en un hilo propio;
      el worker es su único dueño;
    - `platforms.py`: Greenhouse, Lever, Ashby y LinkedIn por la URL, y si no, mirando la página
      (iframe de un ATS conocido, `generic` o `unknown`); también valida la URL;
    - `guard.py`: captcha visible, anti-bot y login (`needs_user`), y el bloqueo del envío mientras
      se rellena;
    - `fields.py`: campos por etiqueta accesible, clasificación, plan y rellenado;
    - `tokens.py`, `submit.py` y `service.py`;
  - migración `0011` (`application_attempts`) y evento `application_filled` (system, reservado);
  - tareas del worker `browser_open`, `apply_open`, `apply_fill`, `apply_rescan`, `apply_submit` y
    `apply_focus`, sin reintentos (`tasks.NO_RETRY_KINDS`, `fail_interrupted`);
  - política `applier` (timeouts, TTL del token, similitud de preguntas) y `JH_BROWSER_HEADLESS`,
    `JH_BROWSER_CHANNEL`;
  - `ARCHITECTURE`, `DATA_MODEL`, `POLICIES` §5.1, `AGENT_INTERFACE` y README al día.

  Tests:
  - 9 con Chromium contra formularios locales (Greenhouse, Lever, Ashby, genérico en español,
    captcha, login, sin formulario, una web que intenta enviarse sola y `safe_click`);
  - 14 del servicio: el flujo completo con 0 envíos al rellenar y exactamente 1 con el token;
    token inventado, usado o caducado; confirmación pendiente; sin reintentos; URL local;
  - 25 de clasificación y plan, y 6 estáticos: fuera de `submit.py` nada pulsa el envío; la CLI y
    el MCP no importan el servicio.

  En total, 1 584 tests de backend y 108 de frontend.
- **Decisiones:**
  - Un **motor común** con particularidades por plataforma, en vez de un rellenador por ATS:
    - la URL del formulario (Lever `/apply`, Ashby `/application`);
    - los marcadores de obligatorio (`*`, `✱`) y los sí/no con botones de Ashby.

    Los tres ATS comparten etiquetas accesibles y el motor sirve también para los genéricos.
  - **Token:**
    - lo emite `confirm_submission` tras comprobar el nombre de la empresa y que `reviewed_at`
      coincide con la versión revisada;
    - la BD guarda solo su hash;
    - viaja una vez en el `payload` de `apply_submit` y se borra al consumirlo o rechazarlo;
    - una segunda confirmación con otra pendiente da `busy`.
  - **Tras un clic no se vuelve a `ready`** (`token_used_at`):
    - un fallo posterior al clic queda `submit_unconfirmed`;
    - «Volver a revisar» se rechaza;
    - un intento nuevo lleva el aviso `possible_duplicate`. Lo vio la revisión.
  - **Sin confirmación reconocida, no hay `applied`.** Con ella, el worker lo registra en su propia
    transacción con actor `user`, `channel: ats_form`, `attempt_id` y la captura en `evidence`.
  - **Campos:**
    - nunca se rellenan datos sensibles: género, origen, discapacidad, nacionalidad, estado civil,
      salud, antecedentes…;
    - los consentimientos obligatorios (aviso legal) se marcan justo antes de pulsar, tras tu
      confirmación;
    - una casilla obligatoria que no es legal la decides tú;
    - nombre de pila = primer término; apellidos = el resto.
  - **Captcha:** el reCAPTCHA invisible solo deja un aviso; para un desafío visible.
  - **Navegador:** sin trucos anti-detección. Nunca reutiliza una pestaña tuya. Si cierras la
    ventana, se vuelve a abrir. Si su hilo muere, la orden falla en vez de colgar el worker.
  - **URL:** solo `http`/`https` y nunca la propia máquina (`JH_APPLIER_ALLOW_LOOPBACK`, solo
    para los tests).
  - **Bloqueo del envío:** se rearma antes de cada campo. Protege de accidentes, no de una web
    hostil, y así consta en `guard.py`.
- **Deuda y notas para la 11.2:**
  - La API debe exigir `reviewed_at` y mostrar el dominio de destino, el botón que se pulsará
    (aviso `submit_button`) y los consentimientos que se aceptan (`AttemptView.consents`).
  - Avisar si el worker no está en marcha: las tareas se quedan en cola. `jh worker --once`
    cierra el navegador al acabar, así que la pestaña preparada se pierde.
  - Los comboboxes de Greenhouse (React-select) solo se han probado con su marcado accesible
    estándar. La prueba manual con una oferta real lo dirá.
  - La BD real necesita `jh db upgrade` (hasta 0011).

### 11.2 · Candidatura asistida: revisión, envío y UI — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 11.
  - **API** (`routes/apply.py`, capa fina):
    - `GET /jobs/{id}/apply`: último intento y qué haría «Preparar» (`get_state`);
    - `POST /jobs/{id}/apply/prepare`, `/apply/{id}/rescan`, `/apply/{id}/focus` y
      `/jobs/{id}/apply/manual-done`;
    - `POST /apply/{id}/submit` con `{company_confirmation, reviewed_at}` (obligatorio): la única
      puerta al envío;
    - `GET /apply/{id}/screenshot/{review|confirmation}` (solo desde `data/applications/`) y
      `POST /browser/open`.

    `ApplierError` va al formato común con el código del servicio en `details`.
  - `AttemptView` gana `domain`, `can_rescan`, `submit_button` (aviso con `detail`) y
    `pending_task` (para avisar si el worker no está en marcha). `can_submit` exige «CV listo».
  - **UI**: sección «Candidatura asistida» en la ficha, después del paquete:
    - preparar, o «Abrir y preparar» en LinkedIn;
    - pantalla de revisión: captura, tabla de campos con estado, valor y origen, obligatorios
      sin respuesta en ámbar, avisos;
    - diálogo «Enviar»: dominio, botón que se pulsará, consentimientos y el nombre de la empresa;
    - «Volver a revisar», «Lo termino yo», «Marcar como enviada», «Preparar de nuevo» y
      «Preparar navegador»;
    - se refresca cada 2 s mientras trabaja el worker y refresca la ficha al quedar enviada.
  - El skill `preparar-candidatura` pide las preguntas literales del formulario (el rellenado las
    busca por parecido) y remite a la sección.
  - `ARCHITECTURE`, `RESUMEN_FASES` y guía de prueba manual (`docs/pruebas/fase-11-prueba-manual.txt`).
  - 13 tests de API y 15 de la sección. 1 597 tests de backend y 123 de frontend.
- **Decisiones:**
  - «Preparar navegador» va en la propia sección: no hay página «Estado» en la UI.
  - El diálogo de envío confirma una **foto del intento** tomada al pulsar «Enviar»: aunque
    llegue una versión nueva, se manda la `reviewed_at` que viste y el servidor da `stale`. Se monta
    solo mientras está abierto (siempre empieza vacío) y no es un formulario: Intro no envía. Lo
    vio la revisión.
  - Enviada pero sin registrar `applied` (fallo del evento): la sección lo dice y ofrece «Marcar
    como enviada».
  - «Marcar como enviada» se rechaza (`busy`) mientras el worker trabaja en el intento.
  - Tras cualquier error de una acción, se vuelve a pedir el estado (`onSettled`).
- **Deuda:**
  - **Prueba manual pendiente:** `docs/pruebas/fase-11-prueba-manual.txt`, que es el criterio de
    aceptación de la fase: una oferta real de Greenhouse o Lever hasta la pantalla de revisión,
    sin enviar. Sobre todo, los desplegables con buscador de Greenhouse.
  - La UI repite la lista de estados del servicio (`REVIEW`, `RETRY`, `MANUAL`). Si cambian,
    habría que exponer acciones permitidas desde el backend, como `can_rescan`.
  - El aviso del worker sale tras 15 s en cola, aunque la causa sea otra tarea larga delante.
  - La BD real necesita `jh db upgrade` (hasta 0011).

### 12.1 · Demo y portfolio: modo demo — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:**
  - Encargos de las tres subfases (`prompts/12.1-*`, `12.2-*`, `12.3-*`) y su tabla en el de la 12.
  - `services/demo.py` y `jh demo seed [--dir] [--force] [--json]` crean `data-demo/`
    (gitignored) con:
    - el perfil y la foto de `demo/`;
    - 60 ofertas ficticias con extracción y score, en 6 fuentes (dos de ATS en pausa);
    - 276 eventos en las 8 semanas anteriores: descartes con motivo, filtros duros, envíos,
      seguimientos, respuestas, pruebas y entrevistas (algunas futuras, en horario de Madrid y
      entre semana), rechazos, una caducada y una oferta;
    - 2 CVs verificados en `cv_ready`;
    - la oferta con la instrucción oculta de `demo/jobs/02`, con `risk_flags`.
  - Catálogo en `demo/seed/catalog.yaml` y `cvs.yaml`.
  - `Settings.demo_mode` (marca `.demo`), `demo_mode` en `get_status` y `GET /status`, y banner
    «Modo demo: datos ficticios» en todas las páginas.
  - README («Probar con datos de demo»), `ARCHITECTURE`, `AGENT_INTERFACE` y ADR-020.
  - 11 tests de backend y 2 de frontend nuevos (1 608 y 125 en total).
  - Prueba real: `jh demo seed` en unos 30 s con LibreOffice; con `jh serve` y `pnpm dev`, la
    Bandeja, el Embudo y los Procesos salen llenos y con el banner (capturas con Playwright).
- **Decisiones:**
  - Todo pasa por los servicios. La única excepción (ADR-020): las fechas de los eventos
    automáticos de cada oferta recién creada se llevan al día de su alta y se recalcula la
    proyección.
  - PDF de los CVs: `ats-simple` con LibreOffice o Word; si no hay, `moderna-2col` con Chromium
    de Playwright; sin ninguno, la demo se crea sin CVs y lo avisa.
  - El seed se niega a escribir en `data/`, dentro de ella, en sus carpetas padre o en una carpeta
    con contenido sin `.demo`. Para recrear una demo hace falta `--force`.
  - Sin embeddings durante el seed, para que sea reproducible y no descargue modelos.
  - Extracciones y CVs con `agent_name: demo-seed`. Las fuentes de Greenhouse y Lever, en pausa
    (sus tableros no existen).
- **Deuda:**
  - Si el seed falla a medias, la carpeta queda con la marca y hay que repetir con `--force`.
  - Algunos nombres de empresa del catálogo son inventados, pero podrían coincidir con empresas
    reales. Cada oferta dice «(empresa ficticia)» y la UI lleva el banner.
  - `_sources` usa funciones privadas de `ingest` y `capture` para crear sus fuentes.
  - Con embeddings instalados, la app recalcula los scores de la demo al consultarlos (otra
    `scoring_key`).

### 12.2 · Demo y portfolio: evals de matching y de CV — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:**
  - **Matching:** `evals/matching/seed.jsonl` pasa de 20 a 80 casos inventados (40 y 40), con
    trampas de título, oficio, ubicación, nivel, años e idioma. `evals/REPORT.md` recoge las
    métricas, la curva, el umbral elegido y los errores típicos. Sin embeddings: precision 0,88,
    recall 0,95 y F1 0,92 (38/5/2/35).
  - **CV:** `evals/cv/cases.jsonl` (10 ofertas inventadas con keywords esperadas y skills
    prohibidas). `jh demo seed --eval-cv` las da de alta aprobadas y sin CV (en una demo
    existente, solo las que falten).
  - **`jh eval cv [--agent] [--min-coverage]`** (`services/evals/cv.py`) comprueba, en la demo:
    evidencias, skills inventadas o prohibidas, skills básicas no pedidas (en skills, titular y
    resumen), una página, cobertura, idioma y verificación. Informe JSON y Markdown;
    `evals/README.md`.
  - **Prueba:** redactor y verificador de Claude Code en dos ejecuciones distintas, solo con
    `jh … --json` contra `data-demo`, sobre `cv04` y `cv07`: los dos pasan las 7 comprobaciones.
  - 16 tests nuevos del eval de CV; los del matching se adaptan a los 80 casos y
    `scripts/seed_triage_demo.py` sigue usando los 20 primeros. 1 624 tests de backend.
- **Decisiones:**
  - Umbral 55 sin cambios: empata con 60 en F1 y prima el recall (el umbral solo atenúa en el
    triaje).
  - La configuración por defecto no cambia: los falsos positivos de oficio (preventa, docencia,
    ventas) se arreglan con `discard_title_keywords`, que es por usuario.
  - La cobertura del eval de CV cuenta solo las skills pedidas que la candidata tiene, más las
    keywords del caso: un CV honesto no puede cubrir lo que no está en el perfil.
  - Identidad estable de cada caso: la URL `https://empleo.example.com/eval-cv/<id>`.
  - Ayuda de `--file`: «tmp/ de la carpeta de datos», no `data/tmp/` fijo.
- **Deuda:**
  - Comparar con embeddings (`uv sync --extra matching`) y elegir modelo (ADR-006).
  - Hallazgos de la prueba sin MCP, para la 12.3:
    - los roles solo nombran herramientas MCP, no su comando `jh`;
    - las skills no se traducen en un CV en inglés («Modelado dimensional»);
    - las secciones extra solo existen en español;
    - la ayuda sale mal codificada en Git Bash sin `PYTHONIOENCODING=utf-8`;
    - el encargo del agente decía `jh match get` (es `jh match show`).
  - El filtro de ubicación no sabe de cercanía (Ourense, Pontevedra).

### 12.3 · Demo y portfolio: compatibilidad, README y seguridad — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 12.
  - **Matriz de compatibilidad.** `jh demo seed --compat` da de alta las 5 ofertas de
    `evals/compat/jobs.txt` solo con su texto, completo y en su idioma (`services/demo_text.py`).
    Claude Code sin MCP, con una ejecución por rol:
    - 54/55 campos extraídos como se esperaba;
    - 5/5 valoraciones;
    - 5/5 CVs al primer intento, verificados y que pasan `jh eval cv`
      (`docs/pruebas/fase-12.3-matriz-sin-mcp.md`, `docs/AGENTS_COMPAT.md`).
  - **Roles** `extractor`, `redactor` y `verificador`: sección «Sin MCP» con sus comandos `jh`.
    El redactor ya no traduce skills ni incluye secciones extra en otro idioma.
    `AGENT_INTERFACE` explica las skills básicas, las evidencias citables e
    `include_regional_language`.
  - **README de portfolio:**
    - problema y qué hace;
    - demo en 5 minutos;
    - 3 diagramas Mermaid;
    - decisiones con su ADR;
    - tests y evals;
    - agentes;
    - límites éticos;
    - 6 capturas de la demo en `docs/img/`.

    El kit y la guía por fases pasan a `docs/DESARROLLO_POR_FASES.md`.
  - **CI:** paso «Demo de humo» (`jh demo seed --compat --eval-cv` en una carpeta temporal).
  - **Seguridad:**
    - `data/`, `.env`, bases de datos, perfiles y fotos reales nunca han entrado en el historial
      (solo la foto ficticia de `demo/`);
    - ningún dato del perfil real (correo, teléfono, enlaces, empresas, centros, proyectos) aparece
      en parches, mensajes ni ficheros;
    - lo único que aparece es el nombre del usuario: en rutas de su carpeta de Windows dentro de
      versiones antiguas de `docs/pruebas/` y en un mensaje de merge (su usuario de GitHub). Ya
      figura como autor de los commits; no se reescribe el historial.
  - **Clon limpio** (con cachés de uv y pnpm y Chromium instalados): sembrado y frontend instalado
    en 81 s; API y UI respondiendo en 92 s.
  - 1 627 tests de backend y 125 de frontend.
- **Decisiones:**
  - Codex queda fuera de la matriz por decisión del usuario; en la tabla figura como «sin probar».
  - La pasada con MCP la hace el usuario en una demo aparte (`data-demo-mcp/`, guía en
    `docs/pruebas/fase-12-compatibilidad.txt`); `.gitignore` cubre `data-demo*/`.
  - La matriz reutiliza casos del eval de CV, así que la misma URL sirve para medir la extracción
    y el CV.
- **Deuda:**
  - **Prueba manual pendiente:** Claude Code con MCP sobre la matriz
    (`docs/pruebas/fase-12-compatibilidad.txt`).
  - **CI pendiente de comprobar en GitHub:** el paso nuevo solo se ha probado en local, y con
    LibreOffice; en CI irá con Chromium.
  - Sin MCP:
    - el esquema de las entradas no llega con la herramienta (`jh schema …` lo resolvería);
    - `procesar-ofertas` no admite elegir ofertas;
    - `generar-cv` no pregunta por las skills básicas que la valoración planteó.
  - El verificador no ve el título crudo de la oferta (no tiene `get_job`).
  - Una oferta remota sin país lleva foto por la política por defecto.
  - El README mezcla portfolio y manual de uso (355 líneas); se podría mover «Usarlo con tus
    datos» a `docs/`.

### Mejora · Arranque del servidor MCP — 2026-10-09 · Claude Code (Opus 5.5)
- **Problema:** `jh-mcp` tardaba ~5 s en caliente y ~17 s en frío (Windows Defender revisa cada
  fichero de `.venv`), y Claude Code lo daba por caído a los 30 s.
- **Cambios:**
  - `trafilatura`, `alembic` y `pypdf` se importan solo dentro de las funciones que los usan;
  - `dump_json` pasa a `app/agent_interface/output.py`, así el servidor ya no importa la CLI
    (Typer);
  - `migrations.head_revision()` se cachea: antes releía las migraciones en cada llamada;
  - test `test_server_startup_skips_heavy_imports`;
  - `.claude/settings.json`: `MCP_TIMEOUT=60000`.
- **Resultado:** ~3,5 s en caliente. Lo que queda es sobre todo el SDK de MCP (~1,5 s) y
  SQLAlchemy (~0,5 s).
- **Recomendado en local:** excluir `backend/.venv` de Windows Defender.

### Mejora · Candidaturas desde portales de empleo — 2026-10-10 · Claude Code (Opus 5.5)
- **Problema:** las ofertas de InfoJobs, Tecnoempleo, Indeed y Glassdoor apuntan a la ficha de la
  oferta, no al formulario. «Preparar candidatura» intentaba rellenarla: en Indeed rellenó el
  buscador («Qué / Dónde»). «Preparar navegador» abría una pestaña en blanco sin explicación y
  fallaba si habías cerrado la ventana.
- **Cambios** (ADR-021):
  - los portales se reconocen por la URL y solo se abren; nunca se rellena una página suya ni de
    LinkedIn;
  - «Rellenar esta página» (`POST /apply/{id}/fill-page`, tarea `apply_fill_page`) rellena el
    formulario de la empresa al que te llevó el portal;
  - la oferta de un portal se abre en tu navegador (Glassdoor bloquea el navegador automatizado
    con Cloudflare y eso no se esquiva); `prepare` admite `form_url` para rellenar el formulario
    de la empresa al que te llevó «Solicitar»;
  - detector genérico más estricto: adjunto, o correo y nombre, fuera de buscadores y logins;
  - en una web de empresa sin formulario visible, se pulsa «Enviar solicitud» (o equivalente) para
    cargarlo, como en Teamtailor (`careers.idealista.com`, comprobado sin rellenar ni enviar);
  - «Abrir navegador» con página de inicio y enlaces a los portales; si la ventana se cerró, se
    vuelve a abrir;
  - la UI explica los pasos en un portal y ofrece «Marcar como enviada» desde el principio.
- **Tests:** detección de portales, ficha de portal ficticia (`portal.html`) que no se rellena,
  «Rellenar esta página» con el formulario en una pestaña nueva y negativa en una página del
  portal, `form_url`, página de inicio del navegador y la UI.
- **Pendiente:** probarlo con ofertas reales de cada portal (`docs/pruebas/fase-11-prueba-manual.txt`).

### Mejora · Seguimiento, avisos y plataformas — 2026-10-10 · Claude Code (Opus 5.5)
- **«¿Qué ha pasado con esta candidatura?»** en la ficha de las ofertas enviadas o en proceso:
  botones directos (Me han respondido, Tengo entrevista, Entrevista hecha, Prueba técnica, Oferta
  recibida, Acepto, Me han rechazado, Me retiro, Sin respuesta). Reutiliza el diálogo del tablero:
  registra el evento con fecha y nota (y el hito, en entrevistas y pruebas). En Procesos, el
  enlace «Mover» pasa a ser un botón «Actualizar estado».
- **Ficha de una oferta ya enviada:** «¿Qué ha pasado?» va lo primero, a todo el ancho; después el
  proceso (hitos y contactos), la extracción y el encaje. Lo de antes de enviar (candidatura
  asistida, paquete, CV, carta y texto) queda plegado en «Antes de enviar» y solo se carga al
  abrirlo.
- **Historial compacto:** con 7 eventos o más se ven los 4 últimos y el alta; el resto, con «Ver N
  eventos más» (los avisos de posible inyección, siempre).
- **«Triaje» → «Por revisar»** en la UI (`/por-revisar`; `/triaje` redirige).
- **Avisos al usuario** (ADR-022): `request_user_action` / `wait_user_action`, tabla
  `user_prompts` (migración 0012), pop-up global con cuenta atrás y notificación del sistema;
  espera de 5 minutos y, si no, el agente sigue. El skill `buscar-ofertas` los usa ante un
  captcha, un anti-bot o un login; la candidatura asistida también.
- **«Añadir plataforma»** en Plataformas (`POST /sources/platforms`): portales conocidos o uno
  propio; LinkedIn se crea siempre desactivada, con el aviso de por qué conviene dejarla así.
- **Tests:** servicio y API de avisos (incl. espera que vuelve al contestar), paridad MCP ↔ CLI de
  las dos herramientas nuevas, alta de plataformas, y UI (pop-up, plataformas, «¿Qué ha pasado?»).

### Mejora · CV a medida de cada oferta — 2026-10-11 · Claude Code (Opus 5.5)
- **Rol `redactor`:** nueva sección «Adaptar a la oferta». Antes de redactar, el redactor identifica
  las 2-3 necesidades centrales de la oferta, los logros que mejor las prueban y su vocabulario
  literal. Subtítulo, resumen, orden y enfoque de los logros, proyectos y skills cambian con cada
  oferta. Puede cambiar el énfasis de un logro, nunca su alcance.
- **Rol `verificador`:** avisa (`warning`) si el CV es genérico (un resumen que valdría para otra
  oferta del mismo rol) o si contradice las indicaciones del usuario. Un hecho respaldado solo por
  las indicaciones es `blocker`.
- **Indicaciones generales para los CVs:** `preferences.cv.instructions` y `preferences.cv.avoid`
  en el perfil, opcionales. Orientan la redacción y nunca respaldan hechos; las indicaciones de
  cada oferta mandan sobre ellas. Llegan al agente con `get_profile`. POLICIES §3 y el skill
  `actualizar-perfil` lo recogen.
- **Enlaces en el CV** (ADR-023): `url` opcional en los proyectos del perfil (`projects[].url` en
  el contrato). LinkedIn, GitHub y el enlace de cada proyecto se pueden pulsar en el PDF de los
  dos motores: el código los enlaza al renderizar y la plantilla sigue sin poder poner `href`
  externos. Las integradas y el HTML base del importador muestran el enlace del proyecto.
- **Inicio** (`/`): resumen de lo que te toca hoy (frase con enlaces a cada lista), recorrido de
  las ofertas por etapa con quién actúa en cada una (tú, el agente o la empresa), mejor encaje por
  revisar, listas para enviar, próximos 7 días y candidaturas sin respuesta. La bandeja pasa a
  `/bandeja`. La cabecera ya no se parte en escritorio ni ensancha la página en móvil.
- **Plataformas:** las búsquedas salen como etiquetas legibles («data engineer · Madrid»,
  «analytics engineer · Remoto») que abren la búsqueda en el portal; las URLs completas, al
  desplegar. `lib/searches.ts` lee los parámetros habituales (Indeed, InfoJobs, Tecnoempleo,
  Glassdoor, LinkedIn); lo que no entiende sale como «Todas las ofertas».
- **Puestos en español:** `config/title_aliases.yaml` (genérico) traduce «Ingeniero/a de datos»,
  «Analista de datos», «Ingeniero de Big Data»… a su nombre en inglés para compararlos con
  `preferences.roles`, en el prefiltro de alertas y conectores y en el score. Antes una alerta
  «Ingeniero de Datos Snowflake» salía como que no encajaba con tus puestos.
- **Tests:** ejemplo del perfil demo, valores por defecto, items vacíos en `avoid`,
  `public_view`, `url` del proyecto, enlaces en docx (integradas) y en html (incluido el PDF de
  `moderna-2col`) y que una plantilla no puede añadir los suyos.

### Mejora · Botones que abren tu agente (ADR-024) — 2026-10-11 · Claude Code (Opus 5.5)
- **«Buscar ofertas»** (y «Procesar ofertas» / «Evaluar encaje» si hay pendientes) en Inicio,
  **«Procesar ahora»** en el aviso de ofertas por extraer y **«Generar CV»** / «Volver a redactar»
  en la ficha de una oferta aprobada. Abren tu agente en una terminal con la orden del skill escrita.
- `services/agent_launch.py` (órdenes cerradas, programa desde `launch` del manifiesto, `JH_AGENT`,
  `unset_env`), `GET /agent` y `POST /agent/launch` (solo desde la UI: `Origin` y JSON). Sin agente
  disponible, la UI copia la orden.
- La orden va a PowerShell codificada (`-EncodedCommand`): `wt` parte su línea por cada `;`.
- **Plataformas:** icono de cada portal (lo carga tu navegador del propio portal, sin referer; si no
  carga, la inicial) y enlace a su página base, sacada de sus búsquedas.
- **Tests:** órdenes, comando de PowerShell (comillas y variables quitadas), elección de agente,
  API (lanza, oferta no aprobada o inexistente, otra web o cuerpo no JSON rechazados, orden para
  copiar si no hay agente) y UI (lanzar y copiar).

### 13 · Contexto y documentos — 2026-10-11 · Claude Code (Opus 5.5)
- **Resumen:**
  - `services/context.py`: los cuatro ficheros de `data/contexto/`, `get_context` con hash y
    límite de 20 KB, `init` desde las plantillas de `demo/contexto/` sin sus datos, y estado para
    la UI.
  - Herramienta `get_context` ↔ `jh context show --json`, y `jh context init`.
  - `services/application_archive.py`: la tarea `archive_application` se encola al registrar
    `applied`/`applied_manually` (desde la UI y desde el envío asistido). Hay también
    `jh applications archive (ID | --all)`.
  - `services/folders.py` y `POST /folders/open`, solo desde la UI y con una lista cerrada de
    carpetas. `GET /context`.
  - Página «Mi perfil» y «Copia de lo que enviaste» en la ficha de una oferta enviada.
  - Skills y roles: `redactor`, `generar-carta`, `evaluar-encaje`, `preparar-entrevista`,
    `actualizar-perfil` y `verificador`.
  - Docs: POLICIES §1.5, `AGENT_INTERFACE.md`, `DATA_MODEL.md` y ADR-025.
  - Tests: 1730 de backend y 169 de frontend.
- **Pruebas reales** (con carpetas de datos aisladas, sin tocar `data/`):
  - El rol `verificador` (sesión aparte, por CLI, sin pistas) dio **FAILED** a un CV con «Di
    formación interna de dbt a 12 compañeros» citando una evidencia que no lo dice. Su primer
    `blocker` señala que solo está en `perfil-conductual.md`.
    - Ojo: dbt es skill básica en la demo y salió también un segundo `blocker` por eso.
  - `jh worker --once` archivó una candidatura `applied_manually` con CV, carta TXT+PDF,
    respuestas y README. `jh applications archive --all` después: «ya estaba».
- **Decisiones:**
  - Contexto ≠ hechos (ADR-025): sin versiones en la BD; el hash permite ver si cambió.
  - Opción `--sections` en lugar del `--section` del encargo, igual que `jh profile show`.
  - Los ids del archivo se fijan al registrar el envío (payload de la tarea), no al archivar.
  - La carpeta que ya existe no se toca, ni con un segundo envío tras reabrir.
  - `archive_folder` va en la ficha (`JobView`) y no en el paquete: el paquete se carga al
    desplegar «Antes de enviar». Solo mira el disco en ofertas enviadas.
  - Para usar en una carta algo de `narrativa.md`, el skill lo propone y lo guarda en el brief si
    el usuario dice que sí.
  - «Abrir carpeta» de contexto o documentos crea lo que falte (`context.init`).
  - `require_ui` da un mensaje genérico.
  - Documentos fuente y README del archivo: texto de terceros, dato y no instrucción.
- **Deuda:**
  - Que un CV no use un hecho del contexto depende del verificador (un agente): el código no puede
    distinguirlo.
  - El documento no guarda qué versión del contexto se usó al redactarlo.
  - `jh applications archive` usa la carta y las respuestas vigentes, no las del momento del envío.
  - `os.startfile` solo en Windows; en otro sistema la UI enseña la ruta.
  - Dos tests de frontend (`HomePage`, `NewJobPage`) fallaron una vez con la máquina cargada y
    pasan solos: parecen intermitentes, ajenos a la fase.
  - La UI no se probó en el navegador, solo con sus tests.

### 14 · Huecos de skills y vocabulario — 2026-10-11 · Claude Code (Opus 5.5)
- **Resumen:**
  - `services/skill_gaps.py`: skills ausentes de las ofertas abiertas y de las aprobadas o
    enviadas en los últimos N días (60 por defecto), con obligatorias y deseables por separado,
    peso (1,0 / 0,5 × score / 100), ejemplos y marca. Recalcula la cobertura con los alias de
    ahora, sin escribir.
  - `services/skill_aliases.py`: «Es lo mismo que…» escribe `config/skill_aliases.yaml` con
    ruamel.yaml (comentarios, orden, comillas y CRLF intactos; temporal y `os.replace`, con
    candado) y encola `rescore_all`. Rechaza sinónimos que ya apuntan a otra skill o que el perfil
    ya cubre.
  - Caché de alias de skills y de puestos por contenido o fecha del fichero: el worker ve los
    cambios sin reiniciarse.
  - Tabla `skill_gap_marks` (migración 0013): «La tengo» / «No la tengo».
  - Herramienta `get_skill_gaps` ↔ `jh skills gaps --json`. API `GET /skills/gaps`,
    `POST /skills/aliases` y `POST /skills/marks` (estas dos, solo desde la UI).
  - Página «Skills»: filtros de periodo, tipo y marca, orden por ofertas o peso, diálogo «Es lo
    mismo que…» y botones del agente «Añadir al perfil las que tengo» y «Plan de formación»
    (acciones `anadir-skills` y `plan-formacion` en `agent_launch.ACTIONS`).
  - Skill nuevo `plan-formacion` y sección nueva en `actualizar-perfil`.
  - Docs: POLICIES §2, `AGENT_INTERFACE.md`, `DATA_MODEL.md`, `ARCHITECTURE.md`,
    `AGENTS_COMPAT.md`, README, `config/README.md` y ADR-026.
  - Tests: 1759 de backend y 175 de frontend.
- **Pruebas reales** (carpeta de datos aislada, sin tocar `data/`): `jh demo seed` y
  `jh skills gaps` sobre la demo listan 11 skills ausentes en 35 ofertas (Estadística, Looker,
  Excel…).
- **Decisiones:**
  - «La tengo» solo guarda la marca; el botón lanza `actualizar-perfil` con una orden fija y el
    agente lee las marcas con `get_skill_gaps`. Ningún nombre de skill de una oferta llega a la
    orden (ADR-024).
  - Los alias van a `config/` y no a `data/`: son genéricos (ADR-026). Aparecen como cambio en
    git.
  - Marcas y alias solo desde la UI: no hay herramienta ni comando para escribirlos.
  - Las marcas se guardan por la forma canónica y siguen visibles aunque sus ofertas salgan del
    periodo.
  - `POST /skills/marks` en vez de `PUT`: CORS solo admite GET y POST.
  - Los huecos se calculan al pedirlos, no se guardan. Una oferta sin match cuenta como score 50.
  - Revisión del rol `revisor` aplicada: marcas `have` fuera del periodo, avisos de dato no
    confiable, caché de puestos coherente con `normalize`, candado y temporal único al escribir el
    YAML, nombres de más de 80 caracteres ignorados.
- **Deuda:**
  - La UI no borra alias: un error se corrige editando el fichero.
  - Marcas huérfanas si alguien cambia a mano el canónico de una skill.
  - El candado es por proceso: dos procesos escribiendo a la vez el fichero (API y algo más) no se
    excluyen. Hoy solo escribe la API.
  - Pendiente de prueba manual: la página «Skills» con datos reales (alias, marcas y recálculo del
    worker), «Añadir al perfil las que tengo» y `plan-formacion` con Claude Code (web y escritura
    de `data/documentos/plan-formacion.md`).

### 15 · Respuestas por correo y seguimientos — 2026-10-11 · Claude Code (Opus 5.5)
- **Resumen** (tres subfases en la misma rama, un commit por subfase):
  - **15.1** · Migración 0014 (`replies`, `message_drafts`). `services/replies.py`:
    - lee por IMAP en solo lectura `JH_IMAP_REPLIES_FOLDER` (por defecto `INBOX`) o
      `data/inbox/respuestas/`, solo si hay candidaturas en `applied`/`in_process`;
    - pide primero las cabeceras y el cuerpo solo de lo que casa con una candidatura (contacto,
      dominio de la empresa, ATS que la nombra o nombre de la empresa en el dominio);
    - guarda el texto visible, con detección de inyección también en lo oculto, y lo entrega
      envuelto en `<untrusted_email>`.
    - Herramientas `list_replies`, `get_reply` y `save_reply_proposal` (`jh replies
      list|show|propose`), `jh replies poll`, tarea `poll_replies`, comprobación en `jh doctor`.
    - Rol `clasificador` y skill `revisar-respuestas`. Correos ficticios en
      `demo/emails/respuestas/`.
  - **15.2** · API `/replies` (bandeja, correo, leer ahora, aceptar e ignorar con `require_ui`,
    que pasa a `api/deps.py`). Aceptar registra el evento como `user` con `payload.reply_id` y,
    con fecha, crea el hito; `none` archiva sin evento. Página «Respuestas», aviso en la ficha,
    recuento en el menú, Inicio con «Revisar respuestas» (acción `revisar-respuestas`).
  - **15.3** · `services/drafts.py`: `save_message_draft` ↔ `jh drafts save` (seguimiento o
    agradecimiento; sustituye el vigente), «Ya lo he enviado» (registra `followup_sent`) y
    «Descartar», solo desde la UI. Tope `followups.max_followups` (2) también en el aviso del
    tablero y de la ficha. `list_followups_due` con `followups_sent`, nombres de contactos,
    `draft_id` y `thanks_due` (`followups.thank_you_days`). Skill `redactar-seguimiento`, sección
    «Borradores» en la ficha y «Redactar borradores» en Procesos (acciones
    `redactar-seguimiento` y `redactar-seguimientos`). La comprobación de etapa de `agent_launch` es
    por acción.
  - Docs: `CONFIGURAR_CORREO.md`, `AGENT_INTERFACE.md`, POLICIES §5, `DATA_MODEL.md`,
    `AGENTS_COMPAT.md`, README, ADR-027 y `docs/pruebas/fase-15-prueba-manual.txt`.
  - Tests: 1831 de backend y 188 de frontend.
- **Pruebas reales** (carpeta de datos aislada, sin tocar `data/`): el rol `clasificador` (Claude
  Code, modelo rápido, modo sin MCP) clasificó los 5 correos de la demo. Salieron entrevista con
  su hito (jueves 8, 10:00 +02:00), rechazo vía Greenhouse, prueba con plazo de todo el día y
  oferta, todos con confianza `high`. El correo con inyección oculta salió `none` con confianza
  `low` y marcado. Ninguna oferta cambió de etapa.
- **Decisiones:**
  - Bandeja de entrada por defecto, con privacidad por diseño: cabeceras primero, nada guardado
    de lo que no casa, sin conexión sin candidaturas abiertas (ADR-027).
  - Avisos de portales fuera por defecto (`replies.portal_sender_domains` vacío). `none` permitido
    para acuses de recibo.
  - La propuesta no registra nada; aceptar solo desde la UI, sin herramienta ni comando. El
    orquestador `revisar-respuestas` no lee correos.
  - Con una sola candidata, un puesto que no coincide del todo baja la confianza a `medium`, no a
    `low`, para no perder el hito.
  - Un correo anterior a la hora anotada del envío se registra desde el envío.
  - Revisión del rol `revisor` aplicada:
    - tope de seguimientos en tablero, ficha y «Ya lo he enviado»;
    - coincidencia por nombre más estricta (igualdad, primera palabra de 5+ letras o sufijo
      corporativo; `metaphor.com` ya no es «Meta»);
    - correos sin fecha descartados;
    - `POST /replies/poll` solo desde la UI;
    - no se repite el agradecimiento de una entrevista ya agradecida;
    - límite de `require_ui` frente a un agente con terminal, documentado en ADR-027.
- **Deuda:**
  - `.env.example` no lleva `JH_IMAP_REPLIES_FOLDER`: el agente no tiene permiso sobre ese
    fichero. Añádela a mano (opcional, por defecto `INBOX`).
  - No hay hito de «plazo» para responder a una oferta: va en el resumen. Encaja en la fase 21.
  - Un agradecimiento descartado vuelve a salir en `thanks_due` mientras dure `thank_you_days`.
    Un agradecimiento enviado solo queda en `message_drafts` (no hay evento).
  - Un borrador de seguimiento sigue vigente aunque la empresa conteste; se descarta a mano.
  - El botón «Seguimiento enviado» del proceso registra `followup_sent` sin cerrar el borrador
    abierto (marcar ese borrador después lo rechaza el tope si ya son 2).
  - Pendiente de prueba manual: IMAP real sobre `INBOX`, la UI de «Respuestas» y «Borradores» en
    el navegador y `redactar-seguimiento` con datos reales
    (`docs/pruebas/fase-15-prueba-manual.txt`).

### 16 · Ofertas vivas, republicadas y búsqueda ampliada — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen** (dos subfases en la misma rama):
  - **16.1** · Migración 0015:
    - `jobs.signals`: `possibly_closed`, `liveness`, `open_confirmed` y `reposted`;
    - `job_sightings`, con relleno de la primera publicación de cada oferta.
  - **16.1** · `services/liveness.py`, ¿sigue abierta?:
    - ATS por su API pública (Greenhouse y Lever 404; Ashby, ausencia en el tablero);
    - el resto con un GET acotado: 404/410, redirección que pierde la oferta, frases de
      `liveness.closed_phrases`, `validThrough` pasado;
    - `unknown` ante bloqueos, anti-bot (`liveness.blocked_phrases`) o páginas que no muestran la
      oferta. LinkedIn, `skipped`.
  - **16.1** · Cuándo y cómo avisa:
    - evento `closure_suspected` sin cambio de etapa; motivo de descarte nuevo `closed`;
    - tarea `check_open` cada día (aprobadas y con CV) y al arrancar el worker;
    - `check_job_open` ↔ `jh jobs check-open`, que llama `generar-cv` antes de redactar;
    - API `check-open` y `still-open` con `require_ui`.
  - **16.1** · `services/reposts.py`: publicación anotada en el alta, por huella y en los
    conectores. Republicada = mismo canal, empresa, título comparable y ubicación, en días
    distintos dentro de 90.
  - **16.1** · UI: insignias «¿Cerrada?» y «Republicada ×N» en Bandeja y Triaje; aviso en la ficha
    con «Descartar» (ya marcado con «Ya no está publicada»), «Sigue abierta» y «Comprobar otra
    vez»; comprobación al abrir una aprobada; aviso junto a «Generar CV».
  - **16.2** · `services/search_titles.py`: `get_search_titles` ↔ `jh jobs titles`, con
    `matches_roles` (puestos que apruebas y el filtro previo deja fuera). Skill `ampliar-busqueda`
    y botón en Plataformas (acción `ampliar-busqueda`).
  - **16.2** · `services/ingestion/discover.py`: `jh sources discover --file F [--add] [--json]`
    (hasta 3 slugs por empresa en Greenhouse, Lever global/UE y Ashby; `confirmed`, `probable` o
    `doubtful`; `--add` nunca da de alta las dudosas). Sin MCP, a propósito.
  - Docs: FUENTES_OFERTAS, DATA_MODEL, AGENT_INTERFACE, POLICIES §2, ARCHITECTURE, AGENTS_COMPAT,
    README, RESUMEN_FASES, ADR-028 y `docs/pruebas/fase-16-prueba-manual.txt`.
  - Tests: última pasada completa con 1937 de backend y 195 de frontend en verde, antes de
    aplicar la revisión. Los tests añadidos después (revisión y botón de Plataformas) pasan por
    separado. La pasada completa final la paró Claude Code por falta de memoria: pendiente.
- **Pruebas reales** (carpeta de datos aislada, sin tocar `data/`):
  - las APIs de Greenhouse, Lever y Ashby responden 404 a una oferta o tablero inexistente y 200 a
    uno vivo; `check_ats` lo interpreta bien con ofertas reales de Stripe, Palantir y Ramp;
  - `jh sources discover` encontró los tableros de las tres y nada para una empresa inventada;
  - en las páginas, Tecnoempleo responde 410 a una oferta inexistente (detectada), Indeed responde 401
    y InfoJobs sirve un control anti-bot con HTTP 200. Por eso se añadió la detección de anti-bot y
    la exigencia de ver la oferta en la página antes de decir «abierta».
- **Decisiones:**
  - Señales en una columna propia y no en `risk_flags`, que sigue siendo solo riesgo de inyección
    (ADR-028, aprobado antes de empezar). Desviación respecto al encargo.
  - Republicadas por canal y ubicación, en días distintos: ni varias ubicaciones el mismo día ni la
    misma oferta en varios portales cuentan.
  - «Sigue abierta» silencia ese motivo hasta que una comprobación vea la oferta abierta.
  - El aviso solo en etapas anteriores al envío; la comprobación diaria, solo de aprobadas y con CV.
  - Las URLs que comprueba el worker vienen de contenido no confiable: se resuelve el DNS y se
    rechaza la red local; del destino de una redirección solo se guarda el dominio.
  - `discover` sin herramienta MCP; «confirmada» exige el nombre completo (no `token_set_ratio`).
  - Revisión del rol `revisor` aplicada: ids en la query (`gh_jid`) y el id de la fuente en el ref,
    `confirmed` estricto, DNS, URL de redirección fuera de los textos, «Sigue abierta» que caduca,
    `InvalidURL`, ubicación en el grupo, textos de API limpios, slugs, Ashby sin mayúsculas, lógica
    de la migración congelada y aviso del servidor MCP matizado.
- **Deuda:**
  - `reposted` no caduca sola: se recalcula al ver otra publicación.
  - Las frases de «oferta cerrada» y anti-bot son heurísticas sin páginas reales cerradas de
    InfoJobs e Indeed (que en la práctica dan `unknown`).
  - El plazo de lectura es por petición, no total (como en el alta por URL).
  - `discover` no enseña progreso y Lever devuelve el tablero entero.
  - Descubrir empresas desde la UI («Empresas»), pendiente.
  - Pendiente de prueba manual: una oferta cerrada real en la ficha, `/generar-cv` con aviso,
    `/ampliar-busqueda` con datos reales y `discover` con tus empresas
    (`docs/pruebas/fase-16-prueba-manual.txt`).

### 17 · Entrevistas: simulacro, repaso y banco de historias — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen:**
  - Migración 0016: `milestones.prep_plan` (JSON), `debrief_notes`, `next_steps` y
    `debriefed_at`. `notes` sigue siendo del usuario.
  - `services/interviews.py` y `schemas/interviews.py`, con tres herramientas y paridad:
    - `get_interviews` ↔ `jh interviews list`: entrevistas de una oferta con plan y repaso,
      contactos (nombre y cargo), `offer_received` y `today`;
    - `save_interview_plan` ↔ `jh interviews plan`: bloques de 15-120 min de hoy al día de la
      entrevista, solo en una programada por empezar y con el proceso abierto;
    - `save_interview_notes` ↔ `jh interviews notes`: solo en una entrevista ya empezada y no
      cancelada.
  - Ninguna registra eventos, cambia el estado del hito ni toca el perfil.
  - Skills: `preparar-entrevista` (dosier por entrevista y plan por días que se guarda con tu OK),
    `simular-entrevista` (nuevo) y `repasar-entrevista` (nuevo, con el modo «dudas antes de
    aceptar»).
  - Botones ADR-024 en el hito: «Preparar», «Simulacro» y «Repasar». En la ficha, «Dudas antes de
    aceptar» con un `offer_received`. `POST /agent/launch` acepta `milestone_id`; la oferta sale
    del hito.
  - Ficha: plan por días con el dosier y «Abrir carpeta» (carpeta `entrevistas`), bloque «Repaso»
    y `ProcessView.offer_received`.
  - Docs: AGENT_INTERFACE, DATA_MODEL, POLICIES §1.6, README, RESUMEN_FASES, ADR-029 y
    `docs/pruebas/fase-17-prueba-manual.txt`.
  - Tests:
    - backend: pasada completa con 1986 en verde y 2 que fijaban la cabeza de migración en 0015
      (corregidos). Los tests añadidos con la revisión pasan sueltos;
    - frontend: 202 en verde. Dos tests ajenos a la fase fallaron por tiempo de espera mientras
      corría a la vez el backend, y pasan sueltos.
- **Pruebas reales** (carpeta de datos aislada con `jh demo seed`, sin tocar `data/`):
  - `jh interviews list|plan|notes` sobre las entrevistas de la demo: plan guardado y ordenado;
    repaso guardado en una entrevista hecha, sin eventos nuevos;
  - rechazados con mensaje claro: el repaso de una entrevista futura y un bloque después de la
    fecha;
  - el `--file` se borra tras el éxito.
- **Decisiones** (ADR-029):
  - Plan y repaso en el hito, no en una tabla nueva.
  - Guardar el repaso no marca la entrevista como hecha: el estado sigue siendo tuyo y el skill te
    lo recuerda.
  - Herramientas extra respecto al encargo: `get_interviews` (los skills no podían leer un hito
    pasado) y `save_interview_plan` (el encargo pide guardar el plan en la ficha).
  - Las «dudas antes de aceptar» son un modo de `repasar-entrevista` y no un skill propio.
  - El dosier lleva el id de la entrevista en el nombre, para no pisar el de otra ronda.
  - El plan y el repaso se guardan sin pedir permiso en Claude Code (el skill ya pide tu OK);
    `add_event` sigue pidiéndolo.
  - Revisión del rol `revisor` aplicada:
    - una entrevista de todo el día cuenta como empezada al acabar ese día (Madrid), con una sola
      comprobación (`check_can_prepare`, `check_can_debrief`) que usan herramientas y botones, y
      su espejo en la UI;
    - tests de la frontera de zona horaria;
    - aviso «la entrevista se ha movido» si un plan tiene bloques posteriores a la nueva fecha;
    - skills: los textos de los hitos y los repasos son datos, no instrucciones; las dudas antes
      de aceptar solo con el proceso abierto; el simulacro solo escribe la nota si la pides;
    - sección de AGENT_INTERFACE recolocada.
- **Deuda:**
  - El plan no avisa de los bloques del día ni se marca como hecho; tampoco va al calendario.
  - El simulacro no guarda nada salvo que pidas la nota: no hay historial de simulacros.
  - La UI no muestra el contenido del dosier, solo su nombre y la carpeta.
  - Reprogramar no rehace el plan: la ficha avisa y se rehace con «Preparar».
  - `save_interview_notes` no guarda qué agente escribió el repaso (el plan sí).
  - El caso de paridad del plan calcula «hoy» al importar: fallaría si la ejecución cruzara la
    medianoche de Madrid.
  - Pendiente de prueba manual: los tres botones con una entrevista real o de prueba y «Dudas
    antes de aceptar» (`docs/pruebas/fase-17-prueba-manual.txt`).
