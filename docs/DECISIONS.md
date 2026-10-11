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

## ADR-019 · Ingesta diaria: conectores, filtro previo y deduplicación
- **Contexto:** la fase 09 trae solas las ofertas de las empresas objetivo (Greenhouse, Lever,
  Ashby) y de búsquedas en portales con API (InfoJobs, Adzuna). Hay que decidir qué se guarda,
  cuándo se ejecuta y cómo se evita duplicar o perder ofertas.
- **Decisión:**
  - **solo endpoints públicos documentados**, verificados contra su documentación al implementar;
    las claves de los portales en `.env`, nunca en `sources.config`;
  - **filtro previo barato** antes de guardar (título contra `preferences.roles` con la misma regla
    de palabras que el score, y ubicación contra las zonas). Ante la duda deja pasar: lo fino lo
    hacen después los filtros duros y el score con la extracción;
  - **idempotencia**: una oferta ya vista (por `source_id` + `external_id`, URL o huella) no se
    vuelve a crear ni a descargar. Dentro de una misma fuente con conector, dos ids distintos nunca
    son duplicado difuso entre sí (el ATS ya dice que son publicaciones distintas, p. ej. «Senior
    Data Engineer» en remoto y «Data Engineer» en Vigo); frente a otras fuentes, el difuso de la
    fase 03 sigue igual;
  - **programación con APScheduler 3** dentro de `jh worker` (la 4 sigue en alfa), con un solo hilo
    para no escribir a la vez en SQLite. Cada fuente es una tarea `run_source` de la cola: un fallo
    no para a las demás, queda en `source_runs` y se reintenta con espera creciente si es de red,
    5xx o 429. Al arrancar, el worker encola las fuentes que no han corrido desde la última hora
    programada: en un portátil que estaba apagado no se pierde el día;
  - la hora está en `config/policies.yaml` (`connectors.daily_at` y `timezone`);
  - la respuesta de una API es contenido no confiable: las URLs de oferta deben ser http(s), los
    ids que van en una ruta solo llevan `[A-Za-z0-9_-]`, no se siguen redirecciones (se llevarían
    las claves que Adzuna pide en la URL) y el log de httpx no baja de WARNING;
  - primero toda la red (descarga, filtro y detalles) y después la escritura, en un savepoint: un
    fallo inesperado no deja ofertas a medias y queda en `source_runs` como `internal_error`.
- **Consecuencias:** la ingesta solo ocurre con el worker en marcha. Un título que no contenga las
  palabras de ningún rol no entra (se puede ampliar por fuente con `title_keywords`). Adzuna solo
  da un extracto: sus ofertas llegan con poca descripción hasta que la 09b las trate como resumen.

## ADR-020 · Modo demo: datos ficticios por los servicios y fechas repartidas después
- **Contexto:** la fase 12.1 necesita una demo con 8 semanas de historial para que el embudo y los
  procesos tengan forma. Los pasos del usuario aceptan `occurred_at`, pero la alta, la extracción,
  los filtros y el score fechan sus eventos «ahora».
- **Decisión:**
  - `jh demo seed` (`services/demo.py`) crea la demo **por los mismos servicios** que los datos
    reales, para que cumpla las mismas reglas (transiciones, filtros, validación del CV);
  - **única excepción a «nada cambia sin evento»:** justo después de crear cada oferta, el
    generador lleva las fechas de sus eventos automáticos (y de la oferta, su extracción y su
    match) al día del alta y recalcula la proyección desde los eventos. No cambia tipos, orden
    ni contenido, y solo ocurre en una carpeta con la marca `.demo`. No se añade un reloj a los
    servicios de producción solo para la demo;
  - la carpeta lleva la marca `.demo`; el seed se niega a escribir en `data/`, dentro de ella, en
    una carpeta que la contenga o en una carpeta con contenido sin la marca;
  - determinista (semilla fija, sin embeddings durante el seed); solo cambian las fechas, relativas
    al día en que se ejecuta.
- **Consecuencias:** los eventos de los CVs de la demo llevan la hora real del seed (son de la
  última semana, así que la cronología sigue en orden). `get_status` devuelve `demo_mode` y la UI
  muestra un banner.

## ADR-021 · Candidaturas desde portales de empleo: abrir la oferta y rellenar la página del formulario
- **Contexto:** la candidatura asistida (fase 11) solo sabía rellenar formularios de ATS (Greenhouse,
  Lever, Ashby) o webs con formulario. Casi todas las ofertas reales llegan de portales (InfoJobs,
  Tecnoempleo, Indeed, Glassdoor, Manfred), cuya URL es la ficha de la oferta: candidatar es iniciar
  sesión y pulsar «Solicitar», que a menudo lleva a la web de la empresa. El detector genérico
  tomaba cualquier campo de correo por un formulario y llegó a rellenar el buscador de Indeed.
- **Decisión:**
  - los portales se reconocen por la URL (`applier/platforms.job_board`). **Nunca se rellena una
    página de un portal ni de LinkedIn** (`fill_problem`), aunque tengas la sesión iniciada: tienen
    anti-bot y es tu cuenta;
  - la UI abre la oferta de un portal **en tu navegador**, con tu sesión, como un enlace normal.
    Glassdoor (Cloudflare) bloquea el navegador automatizado de Job Hunter («Solo personas
    reales») y eso no se esquiva (ADR-009): nada de perfiles «stealth» ni de quitar las marcas de
    automatización. `prepare` sin `form_url` sigue abriéndola en el navegador de Job Hunter
    (`mode: open`, `platform: board`) para los portales que lo admitan, pero la UI no lo ofrece;
  - «Rellenar esta página» (`fill_page`, tarea `apply_fill_page`): cuando el portal te ha llevado al
    formulario de la empresa, se rellena la pestaña que tienes delante en el navegador de Job
    Hunter (la última visible) y el intento pasa a `fill` con esa URL. De ahí en adelante, todo
    igual que en la fase 11: revisión, confirmación con el nombre de la empresa y token de un solo
    uso;
  - el paso principal desde un portal: pegas el enlace al formulario de la empresa (al que te llevó
    «Solicitar») y `prepare` con `form_url` lo rellena en el navegador de Job Hunter;
  - un formulario genérico tiene que tener adjunto, o correo y un campo de nombre (sin contraseña y
    fuera de un buscador). Un buscador, un login o una alerta por correo no lo son;
  - si la página de la empresa no tiene formulario, se pulsa su botón de abrirlo («Enviar
    solicitud», «Solicitar», «Apply now»…: `platforms.APPLY_BUTTON`), solo si está fuera de
    cualquier formulario, y se espera a que cargue (webs como Teamtailor). Sin campos rellenos ese
    clic no envía nada; queda el aviso `form_opened` con el texto del botón;
  - «Preparar navegador» pasa a «Abrir navegador» y abre una página de inicio local con enlaces a
    los portales para iniciar sesión.
- **Consecuencias:** en un portal hay dos pasos manuales (pulsar «Solicitar» y copiar el enlace del
  formulario) a cambio de no automatizar cuentas de terceros ni esquivar sus defensas. Las candidaturas que se completan dentro del portal (p. ej. la inscripción de
  InfoJobs) las terminas tú con el paquete de candidatura y «Marcar como enviada».

## ADR-022 · Avisos al usuario con espera limitada (captcha, login)
- **Contexto:** al buscar ofertas, un captcha paraba la plataforma entera aunque el usuario
  estuviera delante y pudiera resolverlo en segundos. En la candidatura asistida, el intento se
  quedaba en «Necesita tu intervención» sin que nadie se enterase.
- **Decisión:**
  - tabla `user_prompts` y servicio `prompts`. El agente crea el aviso con `request_user_action`
    y espera con `wait_user_action` (≤ 55 s por llamada, para no pasarse del timeout de una
    herramienta MCP) hasta que deje de estar `pending`. El worker crea uno cuando una
    candidatura se para por captcha, anti-bot o login;
  - la UI pregunta cada 4 s por los pendientes y enseña un pop-up global con cuenta atrás, «Ya
    está» y «Saltar», y una notificación del sistema (Notification API del navegador; en Windows,
    la del centro de actividades) si el usuario la activa;
  - por defecto caduca a los 5 minutos: el agente anota el incidente y sigue con la siguiente
    plataforma. En una candidatura asistida, «Ya está» vuelve a rellenar la página;
  - nada resuelve ni esquiva el captcha: solo se avisa (POLICIES §5.3, regla dura 6).
- **Consecuencias:** una consulta ligera cada 4 s desde la UI. Si la pestaña de Job Hunter no
  está abierta ni las notificaciones activadas, el aviso pasa desapercibido y caduca, como antes.

## ADR-023 · Los enlaces del CV los pone el código, no la plantilla
- **Contexto:** se pidieron enlaces que se puedan pulsar en el PDF (LinkedIn, GitHub y el
  repositorio de cada proyecto). Las plantillas html no admiten `href` externos (fase 08b): una
  plantilla puede venir de un CV ajeno y colar un enlace de phishing en un CV que se envía.
- **Decisión:**
  - los proyectos del perfil tienen un `url` opcional; la plantilla lo muestra como texto
    (`projects[].url`), igual que `contact.linkedin` y `contact.github`;
  - al renderizar, el código convierte en enlace solo los textos que coinciden exactamente con
    esas URLs del perfil (`context.links`; sin esquema se les añade `https://`). En docx, parte la
    run y envuelve el trozo en un `w:hyperlink` con el formato de la run; en html, añade
    `<a href>` después del último saneado;
  - el saneado no cambia: una plantilla sigue sin poder poner `href` externos.
- **Consecuencias:** los enlaces se ven como el texto que diseñó la plantilla (sin azul ni
  subrayado; en html, si su CSS no dice otra cosa). En docx solo se enlaza un texto que esté
  entero en una run de texto simple, que es como salen las variables del contrato.

## ADR-024 · Botones que abren tu agente en una terminal, sin API
- **Contexto:** se quería lanzar skills desde la UI («Buscar ofertas», «Generar CV») como si fuera
  una API, pero sin coste de API (ADR-001) y sin atar la app a un agente (regla dura 2). Se
  valoraron: abrir el agente en una terminal visible; lanzarlo sin ventana (`claude -p`) desde el
  worker; una cola de encargos que recoge una sesión abierta; copiar la orden; y el SDK o la API
  (descartado: de pago y prohibido).
- **Decisión:**
  - `POST /agent/launch` abre una terminal (Windows Terminal o, si no está, PowerShell) con tu
    agente en modo interactivo y la orden del skill ya escrita. Lo que haga lo ves, lo contestas y
    lo apruebas tú: sirve también para los skills que preguntan (`generar-cv`) o usan tu navegador
    (`buscar-ofertas`);
  - las órdenes son una lista cerrada en `services/agent_launch.py`; lo único variable es el
    `job_id` (entero). Ningún texto de una oferta ni de una web llega al comando;
  - el programa sale de `launch` en `.agents/manifest.yaml` (`command` con `{prompt}` y
    `unset_env`); `JH_AGENT` elige entre varios. Antes de abrirlo se quitan las variables de
    `unset_env` (p. ej. `ANTHROPIC_API_KEY`), para que use tu suscripción y no la API;
  - solo la UI puede lanzar: el endpoint exige el `Origin` de la UI (si viene) y cuerpo JSON, que
    desde otra web obliga a una comprobación CORS que la API no concede. No hay herramienta MCP ni
    comando `--json`: un agente no se lanza a sí mismo;
  - si no se puede abrir (otro sistema, agente no instalado), la API devuelve la orden y la UI la
    copia al portapapeles.
- **Consecuencias:** sin coste extra, pero gasta los límites de uso de tu plan. Hace falta que la
  API corra en tu sesión de Windows (como `jh serve` en tu ventana). Queda abierto, como fase 2
  opcional, un modo «en segundo plano» (`claude -p` con solo las herramientas del MCP) para skills
  que no preguntan.


## ADR-025 · Contexto del candidato separado de los hechos, y archivo de candidaturas
- **Contexto:** como en AI Job Search, se quería dar al agente más información del candidato que
  la de un CV: cómo escribe, cómo trabaja, qué busca y por qué, qué no acepta. Meterla en
  `data/profile.yaml` mezclaría hechos verificables con opiniones y estilo, y rompería la regla
  de que todo lo que dice un CV tiene respaldo en el perfil. También faltaba guardar qué se envió
  exactamente en cada candidatura, porque el CV y la carta se pueden rehacer después.
- **Decisión:**
  - `data/profile.yaml` sigue siendo la única fuente de **hechos**. Lo nuevo es **contexto**:
    cuatro ficheros Markdown con nombre fijo en `data/contexto/` (`estilo-redaccion`,
    `perfil-conductual`, `criterios`, `narrativa`), todos opcionales. Se editan en el editor del
    usuario, no en la UI, y no se versionan en la BD: `get_context` los lee con su sha256.
  - El contexto orienta y nunca respalda (POLICIES §1.5): el estilo, en `redactor` y
    `generar-carta`; los criterios, en `evaluar-encaje` (como riesgo o motivo de `weak`, siempre
    citados); el perfil conductual y la narrativa, en `preparar-entrevista`. El `verificador` lo
    lee y marca `blocker` un hecho que solo esté ahí. Para usar en una carta algo de la narrativa,
    el skill lo propone y, si el usuario dice que sí, lo guarda en las indicaciones de la carta,
    que sí respaldan `user`.
  - Lo escribe el usuario, así que no se envuelve como contenido no confiable; aun así tiene un
    límite de 20 KB por fichero (`too_large`) para no inflar el contexto del agente.
  - Plantillas: las de la candidata demo (`demo/contexto/`). `jh context init` copia solo sus
    encabezados y comentarios-guía, así que una sola plantilla sirve de ejemplo y de esqueleto
    vacío.
  - `data/documentos/` guarda los documentos fuente (`cv/`, `linkedin/`, `titulos/`,
    `referencias/`), que `actualizar-perfil` puede leer, siempre confirmando antes de escribir.
    Su texto es de terceros (exportaciones, referencias, el título y la URL de la oferta en el
    README de una candidatura): se trata como dato, nunca como instrucción (regla dura 4).
  - Archivo de candidaturas: al registrar `applied` o `applied_manually` se encola
    `archive_application` con los ids de lo que está seleccionado en ese momento. El worker copia
    el PDF del CV, la carta (TXT y PDF) y las respuestas (JSON) a
    `documentos/candidaturas/<empresa>_<puesto>_<job_id>/`, con un `README.md`. Escribe en una
    carpeta temporal y la renombra al final. Es idempotente y no toca una carpeta que ya existe,
    así que si se reabre y se vuelve a enviar, se queda lo del primer envío.
    `jh applications archive` archiva las anteriores a esta fase.
  - «Abrir carpeta» en la UI (`POST /folders/open`): lista cerrada (contexto, documentos y la
    carpeta de una candidatura) y solo desde la UI, como `POST /agent/launch` (ADR-024). Abre el
    explorador con `os.startfile`; en otro sistema devuelve la ruta para copiarla.
- **Consecuencias:** el agente escribe con la voz del usuario y valora con sus criterios sin que
  eso pueda colarse como un hecho en un CV. Esa garantía depende del verificador (un agente), no
  del código: el código solo comprueba que las evidencias existen en el perfil. El documento no
  guarda qué versión del contexto se usó al redactarlo. El archivo de una candidatura enviada
  antes de que corra el worker usa lo seleccionado al registrar el envío, no al archivar.


## ADR-026 · Alias de skills desde la UI y huecos marcados por el usuario
- **Contexto:** con datos reales, la mayoría de las skills «ausentes» del desglose de matching
  eran otra forma de llamar a algo que el perfil ya tenía («data warehousing», «cloud»,
  «modelado semántico»), y bajaban el score sin que faltara experiencia. Los sinónimos ya vivían
  en `config/skill_aliases.yaml`, pero solo se podían añadir a mano. También faltaba separar el
  vocabulario de los huecos de verdad para poder formarse en ellos (fase 14).
- **Decisión:**
  - la página «Skills» agrega las ausentes (`services/skill_gaps.py`, sin guardar nada) y el
    usuario decide cada una: «Es lo mismo que…», «La tengo» o «No la tengo»;
  - «Es lo mismo que…» escribe en `config/skill_aliases.yaml` (no en `data/`): los sinónimos son
    genéricos, no datos personales, y así sirven a cualquiera que use el repositorio. Se edita con
    ruamel.yaml (conserva comentarios, orden, comillas y fin de línea) y se sustituye de una vez.
    Rechaza un sinónimo que ya apunta a otra skill o que el perfil ya cubre. Lo que se añada
    aparece como cambio en git: se puede confirmar o descartar como cualquier otro;
  - la caché de los alias depende de la fecha de modificación del fichero, no del proceso: la API
    y el worker ven el cambio sin reiniciarse. Cambiar los alias cambia el `scoring_key` y se
    encola `rescore_all`;
  - «La tengo» y «No la tengo» se guardan en `skill_gap_marks` por la forma canónica de la skill.
    Los botones del agente de esa página («Añadir al perfil las que tengo», «Plan de formación»)
    llevan una orden fija sin nombres de skills, porque salen de las ofertas (ADR-024): el agente
    los lee con `get_skill_gaps`;
  - solo el usuario decide un alias o una marca, y solo desde la UI (`require_ui`). No hay
    herramienta MCP ni comando para escribirlos, y nada propone alias automáticamente.
- **Consecuencias:** el score deja de castigar el vocabulario sin tocar sus pesos. Un alias mal
  elegido sube el score de las ofertas que lo piden; se corrige editando el fichero a mano (la UI
  no borra alias). Si el usuario no confirma los cambios en git, un `git checkout` del fichero los
  pierde. Las marcas `have` no se borran al añadir la skill al perfil: simplemente dejan de verse.
