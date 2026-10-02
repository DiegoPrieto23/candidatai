# Registro de decisiones (ADR)

Formato corto: contexto → decisión → consecuencias. Añade una entrada nueva en lugar de editar
una antigua; si una decisión cambia, la nueva la marca como sustituida.

## ADR-001 · El razonamiento lo pone el agente del usuario, sin API de LLM
- **Contexto:** el coste debe asumirlo la suscripción que cada persona ya tenga; la API se factura aparte.
- **Decisión:** la app no llama a ningún modelo. Expone una interfaz para agentes (ADR-010) y el
  agente del usuario hace el razonamiento mediante skills y roles.
- **Consecuencias:** sin coste extra por uso. Lo que necesita LLM queda en cola hasta que se
  ejecuta un skill (o una tarea programada del agente, si la soporta). Los botones de la UI no
  pueden generar texto por sí solos. Toda la frontera con el LLM está en la interfaz para agentes,
  así que añadir una vía por API en el futuro no obliga a rehacer los servicios.

## ADR-002 · SQLite + SQLAlchemy 2 + Alembic
- **Contexto:** un solo usuario en local; despliegue más adelante.
- **Decisión:** SQLite en modo WAL con migraciones de Alembic desde el primer día.
- **Consecuencias:** cero administración. Pasar a Postgres es cambiar la URL de conexión.

## ADR-003 · FastAPI + React (Vite, TypeScript)
- **Contexto:** hace falta kanban, flujos de confirmación y tareas largas; además, es portfolio.
- **Decisión:** API REST en FastAPI y SPA en React con shadcn/ui y TanStack Query; cliente
  tipado generado desde OpenAPI.
- **Descartado:** Streamlit (modelo de re-ejecución incompatible con kanban y confirmaciones),
  Next.js (segundo backend en JS), Reflex (ecosistema pequeño).

## ADR-004 · CV con `docxtpl` a partir de datos estructurados (ampliado por ADR-014)
- **Contexto:** reemplazar texto en `document.xml` falla porque Word parte el texto en varios `<w:r>`.
- **Decisión:** plantilla `.docx` con marcadores Jinja; el agente produce `CvContent` y el código renderiza.
  PDF con LibreOffice headless; páginas con `pypdf`.
- **Consecuencias:** hay que preparar la plantilla una vez. A cambio, el render es determinista y
  el contenido verificable.

## ADR-005 · Eventos como fuente de verdad
- **Decisión:** cada cambio de estado es un evento; la etapa es una proyección.
- **Consecuencias:** histórico completo, analítica del embudo con SQL y nada se pierde al
  descartar o cerrar.

## ADR-006 · Embeddings locales
- **Contexto:** Anthropic no ofrece API de embeddings y no queremos otro proveedor de pago.
- **Decisión:** sentence-transformers con un modelo multilingüe pequeño en CPU (candidatos:
  `paraphrase-multilingual-MiniLM-L12-v2`, `intfloat/multilingual-e5-small`), elegido con el set de evaluación.
- **Consecuencias:** descarga inicial del modelo; sin coste ni red después.

## ADR-007 · Ejecución nativa en Windows, sin Docker de momento
- **Decisión:** `uv` + `pnpm` en nativo. Playwright con navegador visible y LibreOffice del sistema.
- **Consecuencias:** configuración por variables de entorno para rutas de herramientas.

## ADR-008 · Aislamiento del texto crudo (sustituido parcialmente por ADR-012)
- **Decisión original:** el texto crudo de las ofertas solo lo ve el rol `extractor`, con
  herramientas mínimas; el resto trabaja con `JobExtraction`.
- **Estado:** se mantiene donde el agente lo permite, pero ya no es la única defensa (ADR-012).

## ADR-009 · Sin automatización en LinkedIn ni captchas
- **Decisión:** LinkedIn y cualquier web con anti-bot se tratan en modo "preparar y abrir".
- **Consecuencias:** algo menos de automatización a cambio de no arriesgar cuentas.
- **Matizada por la ADR-016:** la búsqueda con el navegador del agente en LinkedIn es posible solo
  si la activa el usuario. Las candidaturas en LinkedIn siguen sin automatizarse.

## ADR-010 · Interfaz para agentes neutral: MCP + CLI con paridad
- **Contexto:** el proyecto debe poder usarse con distintos agentes (Claude Code, Codex, Gemini
  CLI, Cursor, Copilot…), no solo con uno de pago concreto.
- **Decisión:** toda la interacción del agente con la app pasa por una interfaz con dos canales
  equivalentes: servidor MCP y CLI `jh … --json`. Un test garantiza la paridad.
- **Consecuencias:** cualquier agente que hable MCP o ejecute comandos sirve. El listón queda algo
  por encima del proyecto original (que solo pedía leer y escribir ficheros), a cambio de estado
  fiable y validación.

## ADR-011 · `.agents/` como fuente única y configuración nativa generada
- **Contexto:** cada agente espera instrucciones, skills, subagentes y servidores MCP en rutas y
  formatos distintos. Mantener copias a mano diverge enseguida.
- **Decisión:** `AGENTS.md` para instrucciones (`CLAUDE.md` y `GEMINI.md` solo lo importan);
  `.agents/skills/` con skills en el estándar Agent Skills y frontmatter mínimo (`name`,
  `description`); `.agents/roles/` con subagentes en un formato propio y neutral;
  `.agents/manifest.yaml` con lo específico de cada agente. `scripts/sync_agents.py` genera
  `.claude/`, `.codex/` y `.mcp.json`, y `--check` falla en CI si no están al día. Se copian
  ficheros en vez de usar enlaces simbólicos, porque en Windows requieren permisos especiales.
- **Consecuencias:** añadir un agente nuevo es añadir un bloque al manifiesto y, si hace falta, un
  emisor al script. Los ficheros generados se commitean para que el repo funcione tras clonarlo.

## ADR-012 · Seguridad que no depende del agente
- **Contexto:** no todos los agentes permiten restringir las herramientas de un subagente. En Codex,
  por ejemplo, los subagentes heredan la política de sandbox de la sesión padre.
- **Decisión:** las defensas críticas viven en el código: detección de texto oculto y frases de
  inyección al guardar, envoltorio con `risk_flags`, validación estricta de todo lo que devuelve el
  agente, comprobación determinista del CV e interfaz sin capacidad de enviar nada. El
  aislamiento por rol es una capa adicional donde exista.
- **Consecuencias:** las garantías mínimas son iguales para todos los agentes; `AGENTS_COMPAT.md`
  documenta las capas extra de cada uno.

## ADR-013 · Servidor MCP con el `Server` de bajo nivel y registro único de herramientas
- **Contexto:** el encargo de la fase 04 pedía FastMCP (en el SDK 2.x, `MCPServer`). FastMCP
  construye el esquema desde la firma de cada función y valida los argumentos por su cuenta:
  sus errores no coincidirían con los de la CLI y no admite pasarle un esquema propio sin tocar
  su API interna.
- **Decisión:** `app/agent_interface/` define cada herramienta una sola vez (`ToolSpec`: nombre,
  modelo de entrada y de salida, servicio y forma del comando). El servidor MCP usa el `Server` de
  bajo nivel del SDK oficial, publica los esquemas de esos modelos y delega en el mismo `runner`
  que la CLI, que valida, ejecuta, audita y traduce los errores a un formato común. La CLI
  recibe todo como texto y deja la validación al modelo.
- **Consecuencias:** paridad por construcción (misma validación, salida y errores) y un test que
  la comprueba herramienta a herramienta. Añadir una herramienta es añadir un `ToolSpec`. A
  cambio, se depende de la API de bajo nivel del SDK, que es más verbosa. El campo `received` de
  los errores va siempre como texto para que coincida en los dos canales.

## ADR-014 · Contenido y presentación separados; plantillas múltiples con dos motores
- **Contexto:** el usuario quiere subir CVs con cualquier diseño y elegir en cada oferta el estilo,
  la foto y otros detalles. Una sola plantilla Word no basta, y muchos diseños solo existen en PDF
  o imagen (Canva y similares).
- **Decisión:**
  - el agente redacta `CvContent` sin saber nada del estilo; el código lo combina con una
    plantilla y unas `CvRenderOptions`, y cada combinación es un `document_render`;
  - plantillas integradas en `templates/` y del usuario en `data/templates/`, descritas con
    `template.yaml` y un contrato de variables común;
  - dos motores: **docx** (docxtpl; conserva exacto un diseño que ya está en Word y genera DOCX y
    PDF) y **html** (Jinja2 + Chromium; recrea diseños que vienen en PDF o imagen; solo PDF);
  - la importación la hace el agente con utilidades deterministas (`jh templates …`): en docx
    decide el mapeo y el código inserta los marcadores sin partirlos; en html escribe HTML/CSS
    local y saneado.
- **Consecuencias:** cambiar de estilo o de foto no gasta cuota del agente. Recrear un diseño desde
  PDF o imagen es aproximado y requiere un agente que vea imágenes. Las plantillas html no dan Word.

## ADR-015 · Matching: embeddings opcionales, filtros al extraer y cálculo perezoso
- **Contexto:** el score debe estar cuando el usuario abre el triaje, aunque `jh worker` no esté en
  marcha. sentence-transformers trae torch (~1 GB), que no hace falta para los tests ni la CI.
- **Decisión:**
  - sentence-transformers es el extra opcional `matching` (`uv sync --extra matching`). Sin él, o
    con `JH_EMBEDDINGS=off`, la similitud semántica no cuenta y su peso se reparte entre los demás
    componentes; el desglose y `jh doctor` lo dicen. Los tests usan un embedder falso.
  - Los filtros duros se aplican en `save_extraction`, en la misma transacción: son baratos y así
    la etapa que devuelve ya es la definitiva. El score se encola (`score_job`).
  - Un match se guarda con su `extraction_id` y su `profile_version_id`. `get_match`, la ficha y el
    triaje lo recalculan si está desfasado; el worker solo lo adelanta. `jh profile import` con
    versión nueva encola `rescore_all`.
  - También guarda `scoring_key`, una huella de cómo se puntuó (versión del scorer, políticas de
    puntuación y filtros salvo `triage_threshold`, alias de skills y modelo de embeddings). Si
    cambia (p. ej. al instalar el extra `matching`), el match está desfasado. `jh match rescore`
    lo recalcula todo ya, sin esperar a que se consulte.
  - Recalcular puede cerrar ofertas en triaje que ya no pasan los filtros, salvo que el usuario
    las reabriera después de un `hard_filter_failed`.
  - Descartar desde la UI exige un motivo de una lista cerrada (para la analítica de la fase 10).
    El agente sigue usando `add_event` con `note`.
- **Consecuencias:** el triaje funciona sin worker, a costa de que una consulta (`get_match`,
  `GET /triage`) pueda escribir un match y un evento `scored`. La primera consulta con embeddings
  carga el modelo (y lo descarga la primera vez).

## ADR-016 · Portales sin API: alertas por correo, captura manual y navegación opcional del agente
- **Contexto:** LinkedIn no ofrece API para buscar ni leer ofertas: su única API de empleo sirve
  para publicar, es solo para socios aprobados y no admite nuevos. Los servicios de terceros que se
  anuncian como «LinkedIn Jobs API» son scrapers de pago contrarios a sus condiciones, y LinkedIn
  los demanda (Proxycurl cerró en 2025 tras su demanda). El usuario quiere LinkedIn como fuente
  principal, y otros portales grandes tampoco tienen API abierta.
- **Decisión** (detalle en `docs/FUENTES_OFERTAS.md`):
  - ofertas «resumen» (`detail_level: summary`) en una etapa nueva, `pending_detail`, que se
    completan más tarde (`detail_captured`) y se identifican por `platform` + `external_id`;
  - lectura de las alertas de empleo por correo, por IMAP en solo lectura sobre una carpeta o desde
    una carpeta local de correos exportados;
  - extensión mínima «Enviar a Job Hunter» que solo actúa cuando el usuario la pulsa, oferta a
    oferta, y envía a la API local con un token;
  - skill `buscar-ofertas` con el navegador del usuario, con reglas estrictas (dominios, solo
    lectura, límites, sin captchas). LinkedIn queda desactivado por defecto y solo el usuario puede
    activarlo, desde la UI.
- **Consecuencias:** LinkedIn y otros portales alimentan la app sin scraping por defecto. Los
  parsers de correo pueden romperse si cambian los formatos (se nota porque un correo deja de
  producir ofertas, y queda en `source_runs`). La navegación del agente es la superficie más
  expuesta: se limita por reglas y por ejecutarse en una sesión dedicada.

## ADR-017 · CV: cuándo está listo, país de la oferta y contacto
- **Contexto:** la fase 08 separa contenido y renders (ADR-014), así que «CV verificado» y «PDF que
  cabe» pueden llegar en cualquier orden, con varios documentos por oferta. Las reglas de plantilla
  y la política de foto necesitan el país, y la extracción solo trae ubicaciones en texto libre.
- **Decisión:**
  - la oferta pasa a `cv_ready` cuando un **mismo** documento tiene `cv_verified` con `passed` y un
    `cv_rendered` sin `too_long`, en el orden que sea. Los eventos llevan `document_id` y la
    proyección lo sigue. `cv_rendered` es un evento reservado: solo lo registra el servicio de
    render, porque uno suelto podría llevar a `cv_ready` sin ficheros;
  - el país se deduce con `config/countries.yaml` (lista corta y editable, sin nombres ambiguos).
    Si no se sabe, ninguna regla de país encaja y la foto sigue `photo_policy.default`;
  - el contacto lo añade el código desde el perfil: `get_profile` no lo devuelve (POLICIES §4);
  - el primer render sin `too_long` de un documento queda seleccionado para enviar; cambiarlo es
    decisión del usuario en la UI;
  - un render que falla borra sus ficheros y no deja nada en la BD.
- **Consecuencias:** el agente no puede marcar un CV como listo sin un PDF que quepa. Un país que no
  esté en la lista no aplica sus reglas: hay que ampliar `countries.yaml`. Cada conversión arranca
  LibreOffice (unos 10-20 s en Windows).

## ADR-018 · Tu CV como base y carta de presentación como documento propio
- **Contexto:** el usuario quiere subir su CV y que la IA mantenga su estilo cambiando solo el
  texto, y generar cartas de presentación según sus indicaciones, en PDF o texto. Hasta ahora la
  carta era un campo de texto de las respuestas de screening (fase 10), con extensión fija.
- **Decisión:**
  - **CV propio**: no se añade un modo en que la IA reescriba el Word en cada oferta. El CV se
    importa una vez como plantilla (ADR-014) y se marca por defecto desde la UI; la importación
    mide en el original la extensión (`capacity`) y el orden de secciones, y las secciones que no
    están en el contrato pasan al perfil como `extra_sections`, que el redactor elige sin
    reescribir;
  - **carta**: documento propio (`documents.kind = cover_letter`) con su esquema, sus
    herramientas, su verificación por el rol `verificador` y sus renders, en una fase nueva (08c)
    que reutiliza la infraestructura del CV;
  - las indicaciones tienen dos niveles: generales en `preferences.cover_letter` del perfil y por
    oferta en `cover_letter_briefs` (UI o agente); mandan las de la oferta y ambas pueden cambiar
    la extensión y el estilo por defecto de `POLICIES.md` §7, nunca §1 ni §4;
  - lo que el usuario cuenta en sus indicaciones es respaldo válido para la carta (evidencia
    `user`), igual que la extracción de la oferta (`extraction`); el documento guarda las
    indicaciones usadas para que la verificación sea reproducible;
  - el PDF va a juego con el CV seleccionado (`letter.*` de la plantilla, `carta-simple` si no
    hay); el texto plano se genera al vuelo. La edición manual en la UI crea un documento nuevo
    sin verificación, marcado «Editada por ti».
- **Consecuencias:** el estilo de un CV propio se conserva exacto en docx y aproximado en html,
  pero un diseño con elementos que no encajan en el contrato (p. ej. un gráfico de habilidades)
  se queda fijo o se pierde. La carta ya está disponible antes de la fase 10, que solo la muestra
  en el paquete de candidatura; `ApplicationAnswers` deja de llevar `cover_letter`.
