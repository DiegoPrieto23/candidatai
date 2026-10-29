# Fuentes de ofertas

De dónde llegan las ofertas a CandidatAI, qué hace cada vía y con qué límites. Todas acaban en el
mismo sitio: la tabla `jobs`, con deduplicación, detección de riesgo e historial de eventos.

| Vía | Fase | Automática | Cubre |
|---|---|---|---|
| Alta manual por URL o texto | 03 | No | Cualquier oferta |
| APIs y feeds públicos de ATS (Greenhouse, Lever, Ashby; Personio, Teamtailor, Workable, SmartRecruiters y Recruitee desde la 25.1) | 09, 25.1 | Sí, diaria | Tus empresas objetivo |
| APIs de portales: InfoJobs y Adzuna (si hay claves), Manfred y freehire (sin claves) | 09, 25.1 | Sí, diaria | Búsquedas por palabras clave |
| **Alertas de empleo por correo** | 09b | Sí | LinkedIn, InfoJobs, Indeed, Tecnoempleo… (lo que te envíen) |
| **Botón «Enviar a CandidatAI»** | 09b | No (un clic) | Cualquier página que estés viendo, LinkedIn incluido |
| **Búsqueda con el navegador del agente** | 09b | A demanda | Portales que la permitan; LinkedIn solo si lo activas tú |
| **Búsqueda pública de LinkedIn sin sesión** (opcional, apagada) | 22 | Sí, diaria | Tus búsquedas de LinkedIn, solo si la activas tú |

## Por qué LinkedIn va así

LinkedIn no ofrece API para buscar o leer ofertas: su única API de empleo sirve para publicar, es
solo para socios aprobados y no admite nuevos. Las «APIs de LinkedIn Jobs» de terceros son
scrapers de pago que incumplen sus condiciones, y LinkedIn demanda a quien lo hace a escala. Por
eso aquí LinkedIn entra por tres vías que no dependen de eso: sus propias alertas por correo, tu
clic en el botón mientras ves una oferta y, solo si tú lo activas, la búsqueda con el navegador
del agente o la búsqueda pública sin sesión que hace la propia app (abajo).

## APIs de ATS y portales (fases 09 y 25.1)

- **Empresas objetivo:** nombre + ATS + slug del tablero, en la página «Dónde buscar → Empresas objetivo» o con
  `cai sources add`. Solo APIs y feeds públicos, sin autenticación ni scraping de HTML.
  La tabla de abajo dice qué usa cada uno.
- **Portales con API:** búsquedas por palabras clave, no por empresa. InfoJobs y Adzuna necesitan
  claves en `.env` (sin ellas, esas fuentes se omiten con un aviso); Manfred y freehire, no.

| Fuente | `--kind` | Endpoint | Descripción | Qué cubre |
|---|---|---|---|---|
| Greenhouse | `greenhouse` | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | En el listado | Tablero de la empresa |
| Lever | `lever` | `api.lever.co/v0/postings/{slug}?mode=json` (o `api.eu.lever.co`, `--region eu`) | En el listado | Tablero de la empresa |
| Ashby | `ashby` | `api.ashbyhq.com/posting-api/job-board/{slug}` | En el listado | Tablero de la empresa |
| Personio | `personio` | Feed XML `{slug}.jobs.personio.de/xml?language={idioma}` | En el listado, solo en el idioma pedido: sin `--language`, se prueba `es` y luego `en`; si no viene, entran departamento y tipo de contrato | Muchas empresas españolas y alemanas |
| Teamtailor | `teamtailor` | Feed RSS `{slug}.teamtailor.com/jobs.rss` (paginado con `per_page` y `offset`) | En el listado | Empresas europeas, sobre todo nórdicas |
| Workable | `workable` | Widget `apply.workable.com/api/v1/widget/accounts/{slug}` y detalle `apply.workable.com/api/v2/accounts/{slug}/jobs/{código}` | Se pide el detalle solo de las que pasan el filtro previo | Startups y pymes |
| SmartRecruiters | `smartrecruiters` | `api.smartrecruiters.com/v1/companies/{slug}/postings` (paginado) y `…/postings/{id}` | Igual: detalle solo de las que pasan | Empresas grandes |
| Recruitee | `recruitee` | `{slug}.recruitee.com/api/offers/` | En el listado | Pymes europeas |
| InfoJobs | `infojobs` | `api.infojobs.net/api/9/offer` y el detalle; `CAI_INFOJOBS_CLIENT_ID` y `CAI_INFOJOBS_CLIENT_SECRET` | Detalle solo de las que pasan | Portal generalista en España |
| Adzuna | `adzuna` | `api.adzuna.com/v1/api/jobs/{país}/search/{página}`; `CAI_ADZUNA_APP_ID` y `CAI_ADZUNA_APP_KEY` | Solo un extracto: la extracción sale más pobre | Agregador por países |
| Manfred | `manfred` | `www.getmanfred.com/api/v2/public/offers?lang=ES` y `…/offers/{id}` | Detalle solo de las que pasan | Tecnología en España (unas decenas de ofertas activas) |
| freehire | `freehire` | `freehire.me/api/v1/agent/jobs/search` (cambiable con `CAI_FREEHIRE_BASE_URL`) | En la búsqueda | Agregador de tecnología de muchos ATS; país y remoto |

Notas:

- **Documentación.** Greenhouse, Lever, Ashby, Personio (feed XML), Teamtailor (RSS), Recruitee
  (Careers Site API), SmartRecruiters (Posting API), InfoJobs, Adzuna y freehire documentan sus
  endpoints. Dos excepciones aceptadas en la fase 25.1 porque son JSON público, no HTML,
  y no piden sesión: el **detalle de Workable** (el JSON que usa su propia página de empleo; el
  widget documentado no trae la descripción y su variante con detalles redirige a un dominio que
  bloquea las peticiones sin navegador) y la **API de Manfred**, que no está documentada.
- **SmartRecruiters no da 404** a una empresa que no existe: devuelve una lista vacía, igual que una
  que hoy no publica nada. La ejecución lo avisa (`empty`) sin poder distinguirlas.
- **Manfred no busca:** devuelve todas sus ofertas activas y aquí se quedan las que casan con la
  búsqueda por el título (todas sus palabras, sin tildes ni mayúsculas; varias búsquedas, separadas
  por comas). El detalle trae el nombre y el correo de su «scout»: nunca se guardan.
- **freehire** busca solo en el título (`q_fields=title`); con varias palabras, todas tienen que
  estar. `--country` (por defecto `es`) y `--remote-only` acotan. La URL de cada oferta es la de
  origen (el ATS o el portal donde se publicó), así que se reconoce si ya la tenías por otra vía.
- **Encabezados añadidos al texto:** al juntar varias partes de una oferta, algunos conectores
  ponen un encabezado propio en español («Requisitos» y «Beneficios» en Workable y Recruitee;
  «Departamento» y «Contrato» en Personio si no hay descripción). Manfred los pone en el idioma de
  la búsqueda (`--lang`). Solo ordenan el texto para la extracción; no cambian lo que dice la oferta.
- **Fuera:** Workday, iCIMS, Taleo y otros ATS que solo ofrecen HTML o exigen sesión. Siguen
  entrando por el alta manual, el botón del navegador o las alertas por correo.

### Cómo encontrar el slug

Abre la página de empleo de la empresa (el enlace «Careers» o «Trabaja con nosotros») y mira la URL
de una oferta:

| Si la URL es… | ATS | Slug |
|---|---|---|
| `boards.greenhouse.io/acme/jobs/123` o `job-boards.greenhouse.io/acme` | Greenhouse | `acme` |
| `jobs.lever.co/acme/…` (o `jobs.eu.lever.co`, región `eu`) | Lever | `acme` |
| `jobs.ashbyhq.com/acme/…` | Ashby | `acme` |
| `acme.jobs.personio.de/job/123` (o `.com`) | Personio | `acme` |
| `acme.teamtailor.com/jobs/123-…` | Teamtailor | `acme` |
| `apply.workable.com/acme/j/ABC123` | Workable | `acme` |
| `jobs.smartrecruiters.com/Acme/123-…` | SmartRecruiters | `Acme` (da igual en mayúsculas o minúsculas) |
| `acme.recruitee.com/o/…` | Recruitee | `acme` |

Si la página de empleo tiene dominio propio (`careers.acme.com`), busca en su código o en el
enlace de «Aplicar» uno de esos dominios.

**Logo de la empresa.** La UI lo carga de la web de la empresa (`website` en la configuración, solo
el origen: `https://acme.com`). La pones al añadirla (`--website acme.com`) o después en su fila
(`POST /sources/{id}/website`). Sin ella, la app usa la de sus ofertas más recientes si no están en
el dominio del ATS (Teamtailor, p. ej., las publica en el dominio de la empresa); si tampoco, pone
la inicial. `cai sources discover` lo prueba solo para una lista de
empresas (abajo). Antes de guardar, «Probar» enseña cuántas ofertas tiene y cuántas pasan tus
filtros.
- **Filtro previo** antes de guardar (`ingestion/prefilter.py`): el título debe contener todas las
  palabras de alguno de tus `preferences.roles` (también en español, con
  `config/title_aliases.yaml`; o una `title_keywords` de la fuente) y ninguna palabra de descarte
  (las de `preferences.discard_title_keywords` del perfil más las de `policies.yaml`); la ubicación, encajar con tus zonas o ser remota si aceptas remoto.
  Ante la duda deja pasar (sin ubicación, sin perfil). La 09b lo reutiliza para los resúmenes.
- **Idempotente:** lo ya visto (por id en la fuente, URL o huella) no se vuelve a crear ni a
  descargar. Lo nuevo queda en `pending_extraction` con el evento `found`.
- **Cada día** a la hora de `connectors.daily_at` (`config/policies.yaml`), `cai worker` encola una
  tarea por fuente activa. Si una falla, se anota en `source_runs` y las demás siguen.

## Ofertas «resumen» y «completas»

Una alerta por correo trae título, empresa, ubicación y enlace, pero no la descripción. Esas
ofertas entran con `detail_level: summary` y en la etapa nueva `pending_detail`:

```
found ─► pending_detail ─(detail_captured)─► pending_extraction ─► pending_triage ─► …
   └──────────── (si llega completa) ────────┘
```

- En `pending_detail` ya se pueden descartar y se ordenan por un **prefiltro barato** en código
  (título y ubicación contra `preferences`, y los filtros duros que se puedan evaluar sin
  descripción). No se llama al agente.
- **Se completan** con el botón de captura (LinkedIn) o descargando la URL con el alta de la fase
  03 (portales que lo permiten). Evento `detail_captured`.
- Una oferta resumen sin completar en `summary_expire_days` (config) se cierra con `expired`.
- Identidad de oferta por plataforma: `platform` + `external_id` (en LinkedIn, el número de
  `/jobs/view/<id>` o del parámetro `currentJobId`). Así la alerta, la captura y una búsqueda
  posterior reconocen que es la misma oferta.

## Alertas por correo

- **Qué hace:** lee los correos de alertas de empleo y da de alta cada oferta que contienen.
  Configuras las búsquedas con alerta en cada portal; la app recibe lo nuevo de todos ellos sin
  entrar en ninguno.
- **Varios buzones** (fase 27.4), cada uno con su carpeta o etiqueta (p. ej. una
  etiqueta de Gmail «Alertas empleo» rellenada por un filtro). Se añaden en «Alertas → Añadir
  buzón» (tabla `mail_sources`): IMAP o una carpeta `data/inbox/<nombre>/` de `.eml`/`.mbox`. La
  cuenta de siempre de `.env` (`CAI_IMAP_HOST`, `CAI_IMAP_PORT` (993), `CAI_IMAP_USER`,
  `CAI_IMAP_PASSWORD`, `CAI_IMAP_FOLDER`) aparece sola como «Principal» y se sigue cambiando en
  `.env`.
  - **Contraseñas solo en `.env`**, una variable por buzón (`CAI_IMAP_<ALIAS>_PASSWORD`), que
    escribe la app de forma atómica cuando la escribes en la UI. La tabla guarda el nombre de la
    variable, nunca el valor, y la contraseña no vuelve por la API ni por MCP (solo
    `has_password`). En Docker la app no puede guardarla: te dice qué línea añadir a tu `.env`.
  - Se leen uno detrás de otro, con un tope de 5 minutos por pasada: el fallo de uno no frena a
    los demás y queda en su `last_error`. El mismo aviso recibido en dos buzones cuenta una vez
    (por `Message-ID`).
  - El servidor se valida: solo el nombre, y ni IP privadas ni locales salvo que el buzón lo
    permita (`allow_private`, «Servidor en mi equipo o mi red», para un servidor propio).
    Cifrado `ssl` (993) o `starttls` (143); nunca sin cifrar, y el certificado se verifica
    siempre (por eso Proton Bridge, con su certificado propio, no sirve: exporta `.eml`).
  - En una demo no se lee ningún buzón IMAP (las carpetas, sí).
  - El agente solo los ve (`list_mail_sources`); añadirlos, cambiarlos y probarlos se hace en la
    UI. `cai mail-sources test ID` prueba uno y `cai doctor` los prueba todos.
- **Conexión IMAP de solo lectura**: abre la carpeta en modo solo lectura: no marca como leído,
  no mueve, no borra.
  - Solo usa `LOGIN`, `EXAMINE`, `UID SEARCH`, `UID FETCH` con `BODY.PEEK[]` y `LOGOUT`. Busca los
    correos de los últimos `summary_expire_days` días, pide primero solo sus `Message-ID` y
    descarga el cuerpo solo de los nuevos. Un test con un servidor IMAP falso que falla ante
    cualquier escritura lo comprueba.
  - Gmail: IMAP con contraseña de aplicación (requiere verificación en dos pasos). Guía para el
    usuario: `CONFIGURAR_CORREO.md`.
  - Yahoo e iCloud: también con contraseña de aplicación. Outlook: Microsoft ya no admite
    contraseña por IMAP en cuentas de trabajo y ha anunciado que la retirará en las personales;
    la app no implementa OAuth, así que la guía recomienda reenviar las alertas a otra cuenta o
    exportarlas como `.eml` (comprobado el 2026-10-23).
- **Alternativa sin credenciales:** carpeta `data/inbox/` donde dejas correos exportados (`.eml`
  o `.mbox`). El worker la procesa igual. Los ficheros no se mueven ni se borran; los ya
  procesados se reconocen por su `Message-ID`. Las subcarpetas (como `samples/`) no se leen.
- **Parsers por plataforma** en `app/services/ingestion/email/`, elegidos por el dominio del
  remitente (`config/policies.yaml` → `email_alerts.platforms`). Un parser genérico de respaldo
  reconoce enlaces con patrones de URL de ofertas conocidos.
  - Los formatos de estos correos cambian: los parsers se construyen a partir de correos reales
    que el usuario deja en `data/inbox/samples/` (fuera de git) y se prueban con fixtures
    **inventados** que imitan su estructura.
- Para cada oferta del correo: si ya está (por `platform` + `external_id`), se cuenta y no se toca;
  si el portal se deja descargar, alta completa con el servicio de la fase 03; si no (LinkedIn), o
  si la descarga falla, alta como resumen. Los enlaces de seguimiento (`…?url=https%3A…`) se leen
  sin seguirlos, y la URL se guarda sin parámetros de seguimiento.
- Un correo de una plataforma conocida del que no sale ninguna oferta deja el aviso
  `no_jobs_found` en `source_runs`: suele indicar que ha cambiado el formato.
- Se guardan los `Message-ID` procesados (tabla `email_messages`), nunca el cuerpo del correo.
- El contenido del correo es **no confiable**, igual que una oferta: pasa por la detección de
  riesgo y no se sigue ningún enlace de LinkedIn automáticamente. La detección mira el texto de
  cada oferta, no el HTML del correo: casi todas las alertas llevan texto oculto legítimo (el
  «preheader») y marcarían `hidden_text` en todas.
- Frecuencia: la del worker (`email_alerts.poll_minutes`). A mano: `cai alerts poll` o «Revisar
  correo ahora» en la pantalla «Alertas», que lista los resúmenes con su prefiltro y permite
  abrirlos en su portal (`O`) o descartarlos (`D`).

## Botón «Enviar a CandidatAI»

- **Extensión mínima para navegadores Chromium** (Chrome, Edge, Brave) en `extension/`, cargada
  como «extensión sin empaquetar»; no se publica en ninguna tienda.
- **Solo actúa cuando pulsas su botón** en la pestaña actual (permisos `activeTab` y
  `scripting`). Lee de esa página: URL, título, el texto seleccionado si lo hay y, si no, la
  descripción de la oferta con extractores por sitio (LinkedIn, InfoJobs, Indeed, Tecnoempleo;
  JSON-LD `JobPosting` si existe; `main` como último recurso).
- **Se instala y se conecta desde la app**, en «Dónde buscar → Botón del navegador» (`/fuentes/extension`):
  la página detecta la extensión, guía la carga sin empaquetar, avisa si es de una versión antigua
  y la conecta con un clic. Al pulsar «Conectar», la app crea un token (`POST /capture/pair`, solo
  desde la UI) y se lo pasa a la extensión por `externally_connectable` (solo páginas de
  `127.0.0.1` y `localhost`); la extensión lo prueba y solo lo guarda si la app lo acepta. A mano
  sigue valiendo `cai capture token`, que lo muestra una vez para pegarlo en sus opciones.
- Envía los datos desde su *service worker* a `http://127.0.0.1:8000/capture` con ese token (en
  `data/capture_token` solo queda su sha256). La API rechaza peticiones sin token
  (401) y solo acepta el origen `chrome-extension://<CAI_CAPTURE_EXTENSION_ID>` (403). El id es
  fijo (`hnaofhehllbkghfehnehamjbkcmdjmle`): lo da la clave pública de `manifest.json`, igual en
  Chrome, Edge y cualquier equipo, y es el valor por defecto de `CAI_CAPTURE_EXTENSION_ID`.
- Manda `url`, `title`, `company`, `location`, `text`, `selection` (si la hay, la app la
  prefiere), `html` (solo el bloque de la descripción, para detectar texto oculto) y `site` (el
  extractor usado). Con menos de 200 caracteres de descripción, o sin empresa en una oferta
  nueva, responde 422 pidiendo que selecciones el texto y vuelvas a pulsar. En un portal con
  extractor propio cuyo HTML ha cambiado, la extensión no manda la página entera (`main`); y un
  resumen nunca se completa con el texto de `main` sin selección (podría ser la lista de
  resultados). Una oferta que ya estaba se reconoce aunque esta vez no haya descripción.
- La extensión no necesita CORS (sus `host_permissions` la eximen), así que su origen no se añade
  a CORS: no podría leer el resto de la API. La defensa real es el token, porque la clave pública
  del manifiesto está en el repositorio.
- La oferta se reconoce por `platform` + `external_id` (también desde la vista de búsqueda de
  LinkedIn, con `currentJobId`), por URL o por huella. Un resumen en `pending_detail` se completa
  (texto, `detail_level: full`, `risk_flags` y evento `detail_captured`, actor `user`); una
  oferta ya completa no se toca; lo demás entra con la fuente `browser_capture`.
- **Permisos mínimos:** sin acceso a cookies, sin scripts permanentes en ningún sitio, sin
  lecturas en segundo plano. `host_permissions` solo para `http://127.0.0.1:8000/*`.
- **Resultado** en el popup del botón: «Nueva», «Completada» (tenía un resumen de una alerta),
  «Ya estaba» o un error con lo que hay que hacer, y «Abrir ficha». El icono queda marcado en esa
  pestaña (✓, = o !). Instalación y uso: `extension/README.md`.
- Honestidad: las condiciones de LinkedIn prohíben extensiones que copien su contenido. Aquí la
  acción es tuya, oferta a oferta, equivalente a copiar y pegar: no recorre páginas ni busca por
  su cuenta. Es la misma práctica que las herramientas de seguimiento de candidaturas conocidas.

## Búsqueda con el navegador del agente (opcional)

Equivale a la etapa 3 del proyecto original: el agente recorre con tu navegador los portales que
hayas aprobado. Skill `search-jobs`.

- **Plataformas** = fuentes de tipo `agent_browse`:
  `{name, platform, search_urls[], priority (1 = primera), access: free|login|blocked,
  allow_agent_browsing, max_offers, notes}`. Las da de alta el agente con
  `search-jobs configurar` (botón «Configurar con mi agente»; como la etapa 1 del original) o el
  usuario con «Añadir portal»: en InfoJobs, Tecnoempleo, Indeed y LinkedIn la UI genera las
  `search_urls` con los puestos (`preferences.roles`), las dos primeras ubicaciones preferidas y,
  si acepta remoto, una búsqueda en remoto, hasta 10 (Glassdoor y Manfred usan ids que no se
  sacan de un nombre). En la página «Dónde buscar → Portales de empleo» ves cada una con sus
  búsquedas y su último recorrido, editas su nombre y sus búsquedas (de su mismo sitio), y cambias
  su prioridad, su acceso, cuántas ofertas abre en cada recorrido (`max_offers`, de 1 a 100) y si
  el agente puede recorrerla. Si el
  agente vuelve a guardarla sin `max_offers`, se conserva el que tenía.
- **Prioridad = puesto en el orden de recorrido, sin empates** (fase 27.3). Con N plataformas van
  de 1 a N, sin huecos ni repetidos, y sin tope (antes era 1…10 y todas entraban con 5). Una
  plataforma nueva va al final si no se dice otra cosa; en un puesto ocupado se inserta y las
  siguientes bajan uno. Cambiar la de una existente a un puesto ocupado **intercambia** las dos
  (la otra se queda con el puesto anterior); guardarla sin `priority` conserva el suyo. Un puesto
  fuera de 1…N se rechaza diciendo el rango. Desactivar la búsqueda con navegador no mueve la
  plataforma: el agente se la salta y conserva su puesto. En la UI, el selector dice qué
  plataforma ocupa cada puesto y a cuál pasaría la otra; si otra pestaña cambió el orden entre
  tanto, la API responde `conflict` (409) y la lista se recarga. Todos los caminos (UI, CLI, MCP,
  alta) pasan por `browse.place`, y la base de datos rechaza un empate que llegue por otro camino
  (`conflict`, diciendo qué plataforma tiene ya ese puesto). La migración `0026` numeró las
  existentes por `(prioridad, nombre)`.
- **LinkedIn** se crea siempre con `allow_agent_browsing: false`. Solo lo puedes activar tú en la
  UI, que muestra el aviso de riesgo para la cuenta y pide confirmarlo (la API exige
  `confirm_risk: true`). El agente no puede activarlo por la interfaz para agentes: `save_source`
  la guarda desactivada por defecto, responde `not_allowed` a un `true` (también si la llama de
  otra forma pero alguna búsqueda es de linkedin.com o lnkd.in) y, si ya lo activaste, lo conserva.
  Una plataforma LinkedIn no puede pasar a ser otra.
- **Defensas en el código** (no dependen del skill):
  - `add_job_from_text` con `source_id` y `record_source_run` rechazan las plataformas con la
    navegación desactivada (`not_allowed`);
  - con `source_id`, una oferta de LinkedIn (por URL o por `platform`) solo entra por la plataforma
    LinkedIn. Sin `source_id` es el alta manual de siempre, que sí admite el texto de LinkedIn
    pegado por ti;
  - las `search_urls` son del dominio de la plataforma si la app la conoce (`platforms.py`) y, si
    no, todas del mismo sitio.
- **Riesgo residual:** la API local no lleva autenticación (solo escucha en 127.0.0.1). Un agente
  que pueda ejecutar comandos podría llamar a `POST /sources/{id}/browse` con `confirm_risk: true`
  sin pasar por la UI. `confirm_risk` evita activaciones por error, no a un agente que se salta
  las reglas. Si eso te preocupa, no le des acceso a la terminal mientras busca, o deja LinkedIn
  fuera de las plataformas.
- **Reglas de navegación** (las aplica el skill y las recuerda cada run):
  - solo dominios de la plataforma; nunca enlaces sugeridos por el contenido de las páginas;
  - como mucho `agent_browse.max_result_pages` páginas de resultados y `max_offers` ofertas
    (por defecto, `agent_browse.default_max_offers`);
  - pausa entre páginas (`agent_browse.delay_seconds`). `list_sources` devuelve estos límites;
  - solo lectura: nada de «Solicitar», «Guardar», «Seguir», mensajes ni formularios;
  - si aparece un captcha, un aviso anti-bot o un login inesperado, el agente te avisa
    (`request_user_action`: pop-up en la UI y notificación del sistema) y espera hasta 5 minutos
    (`wait_user_action`). Si lo resuelves («Ya está»), sigue con esa plataforma; si no («Saltar» o
    caduca), lo anota y pasa a la siguiente. Los captchas los resuelves tú: nunca el agente.
- Cada oferta encontrada entra por `add_job_from_text` con `source_id`, `platform`,
  `external_id` y `url`. La deduplicación hace que lo ya visto o descartado no vuelva como nuevo.
  El agente que navega no extrae ni valora: eso lo hacen luego `process-jobs` y `assess-fit`.
- Al terminar cada plataforma, `record_source_run` con lo encontrado, lo nuevo y los incidentes.
- **Seguridad:** es la superficie más expuesta (un agente con navegador leyendo webs). Ejecútalo
  en una sesión dedicada, sin mezclar con desarrollo. Todo el texto de las páginas es dato, nunca
  instrucción.
- Requiere un agente con acceso a tu navegador (en Claude Code, Claude in Chrome). Ver
  `docs/AGENTS_COMPAT.md`.

## Búsqueda pública de LinkedIn sin sesión (fase 22, opcional)

LinkedIn sirve su búsqueda de empleo a quien no ha iniciado sesión desde unos endpoints públicos
(`jobs-guest`). La app puede consultarlos una vez al día, **sin tu cuenta ni cookies**, para tener
ofertas de LinkedIn sin depender del correo. Es **contrario a las condiciones de uso de LinkedIn**
(prohíben el acceso automatizado) y puede hacer que bloquee tu IP un tiempo: por eso está
**apagada por defecto**, es para uso personal y solo la activas tú.

- **Dónde:** tarjeta de LinkedIn en «Dónde buscar → Portales de empleo» → «Búsqueda pública sin sesión». Es un interruptor
  distinto de «El agente la recorre». Encenderlo abre un aviso de riesgo que hay que aceptar (la API
  exige `confirm_risk: true` y solo la acepta desde la UI). El agente no puede activarla: no hay
  herramienta MCP ni comando para eso, y `save_source` no la toca.
- **Qué busca:** las `search_urls` de la plataforma LinkedIn que sean búsquedas de
  `linkedin.com/jobs/search?…`. De cada una se usan solo `keywords`, `location`, `geoId`,
  `distance`, `f_TPR`, `f_WT`, `f_E` y `f_JT`; sin `f_TPR`, las publicadas en las últimas 24 h
  (`default_time_posted`). Las demás URLs (una oferta, colecciones…) se ignoran y la tarjeta dice
  por qué.
- **Endpoint:** `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?…&start=N`,
  que devuelve tarjetas HTML (id, título, empresa, ubicación, fecha). Sin cookies, sin seguir
  redirecciones y con un user-agent que dice lo que es.
- **Límites** (`config/policies.yaml` → `linkedin_public`; los mínimos están en el código):
  `max_searches_per_run` (5), `max_pages_per_search` (2, no más), `delay_seconds` (10, no menos)
  entre dos peticiones cualesquiera, `min_hours_between_runs` (20: una al día) y
  `max_details_per_run` (10).
- **Bloqueo:** ante 429, 999, 401/403, una redirección (al inicio de sesión o a un control) o una
  página de captcha o anti-bot servida con 200, **se corta en el acto**: ni una petición más, lo ya
  leído se guarda, `blocked` en `source_runs`, aviso en la tarjeta y `block_cooldown_days` (3) sin
  volver a intentarlo. La tarea del worker no se reintenta nunca. Un 5xx o un fallo de red es un
  aviso de esa búsqueda, no un bloqueo.
- **Entrada:** las ofertas pasan el **filtro previo de resúmenes** (título, ubicación y seniority del
  título) **antes** de guardarse: lo que no pasa no entra. Lo nuevo entra como **resumen**
  (`pending_detail`, `platform: linkedin`, `external_id`) en «Alertas», igual que las del correo, y
  se completa con el botón «Enviar a CandidatAI». Lo ya visto (por `platform` + `external_id`) no
  se duplica.
- **Descripción por el endpoint público** (`jobs-guest/jobs/api/jobPosting/{id}`): otro interruptor,
  también apagado y con su propio aviso. Solo para las nuevas que pasan el filtro y hasta
  `max_details_per_run`; con descripción suficiente entran completas (`pending_extraction`), con la
  detección de riesgo sobre su HTML. Más peticiones, más riesgo.
- **Cuándo:** con la ingesta diaria del worker y al arrancar, si está activada y le toca; o «Buscar
  ahora» en la tarjeta, o `cai sources linkedin-public run` (mismos límites). `cai sources
  linkedin-public status` enseña el estado y las búsquedas.
- **Si no funciona:** con un user-agent honesto es posible que LinkedIn responda siempre 999. Entonces
  la función queda bloqueada y se ve en la tarjeta; no se intenta esquivar. Si su HTML cambia, la
  ejecución deja el aviso `page_changed`.

## ¿Sigue abierta? y republicadas (fase 16)

Para no gastar tiempo ni cuota del agente en ofertas cerradas o que se publican una y otra vez.
Las dos cosas van a `jobs.signals` (no a `risk_flags`, que es solo riesgo de inyección) y
son **observaciones, no veredictos**: la app nunca cierra una oferta por ellas.

### ¿Sigue abierta?

`services/liveness.py`, una petición ligera por oferta:

- **ATS por su API pública**, si la URL (`boards.greenhouse.io/{slug}/jobs/{id}`,
  `jobs.lever.co/{slug}/{id}`, `jobs.ashbyhq.com/{slug}/{id}`) o la fuente con conector dan el
  tablero y el id: Greenhouse `boards-api.greenhouse.io/v1/boards/{slug}/jobs/{id}` y Lever
  `api.lever.co/v0/postings/{slug}/{id}` (o `api.eu.lever.co`) responden 404 a una oferta retirada;
  en Ashby, la oferta deja de aparecer en `posting-api/job-board/{slug}`. Los ATS de la fase 25.1
  (Personio, Teamtailor, Workable, SmartRecruiters, Recruitee) van por la vía siguiente, la de su
  página.
- **El resto con un GET** como el del alta por URL (sin cookies ni JavaScript, nada local ni de red
  privada, también tras redirecciones; además se resuelve el dominio y se rechaza si apunta a la
  red local), leyendo como mucho `liveness.max_bytes`. Posible cierre si:
  - responde **404 o 410**;
  - **redirige y pierde la oferta**: otro id de plataforma (o ninguno), la portada, un tramo superior
    de la ruta (la lista) o una página de error (`?error=true`, como Greenhouse);
  - el texto visible contiene una frase de **`liveness.closed_phrases`** (`config/policies.yaml`):
    genéricas en español e inglés y propias de InfoJobs, Indeed y Tecnoempleo. Son heurísticas: si
    ves una oferta cerrada que no se detecta, añade la frase que muestra;
  - el JSON-LD `JobPosting` tiene un **`validThrough` ya pasado** (con un día de margen).
- 401/403/429/5xx, fallos de red, una página de login o un **control anti-bot** servido con
  HTTP 200 (`liveness.blocked_phrases`): `unknown`, sin aviso.
- **«Abierta» exige ver la oferta**: su título en la página o un JSON-LD `JobPosting`. Una página
  genérica sin ninguno de los dos da `unknown`.
- En la práctica (comprobado en octubre de 2026): los ATS y Tecnoempleo responden bien; InfoJobs
  sirve un control anti-bot e Indeed responde 401 a peticiones sin navegador, así que sus ofertas
  suelen quedar en `unknown`. No se intenta esquivar: el aviso solo sale cuando hay evidencia.
- **LinkedIn nunca** (la búsqueda pública de la fase 22 no cambia esto): `skipped`.

Cuándo se comprueba:

- cada día, con la ingesta, y al arrancar `cai worker`: las ofertas en `approved` y `cv_ready` sin
  comprobación en las últimas `liveness.fresh_hours` (tarea `check_open`, una por oferta);
- al abrir la ficha de una oferta aprobada o con CV listo (si la última es reciente, no repite);
- antes de redactar un CV: el skill `generate-cv` llama a `check_job_open` y, si puede estar
  cerrada, pregunta antes de gastar cuota; el botón «Generar CV» también lo avisa;
- a mano: «Comprobar otra vez» en la ficha o `cai jobs check-open ID --force true`.

Si puede estar cerrada, la ficha lo dice con el motivo y la fecha y ofrece **«Descartar»** (con el
motivo nuevo «Ya no está publicada», `closed`), **«Sigue abierta»** (quita el aviso y ese mismo
motivo ya no vuelve a avisar, hasta que una comprobación la vea abierta) y «Comprobar otra vez». La bandeja y «Por revisar» la marcan «¿Cerrada?».
La primera vez se registra el evento `closure_suspected`, que no cambia la etapa.

### Republicadas

`services/reposts.py`. Cada publicación vista queda en `job_sightings`: la primera al dar de alta
la oferta y las siguientes cuando reaparece con otro id o URL aunque la huella la reconozca como la
misma (alta manual, alertas, captura y conectores). Una oferta está **republicada** cuando, en los
últimos `reposts.window_days` días (90), el mismo canal ha mostrado publicaciones distintas de la
misma empresa con el mismo título normalizado (también traducido con `config/title_aliases.yaml`)
y la misma ubicación en al menos `reposts.min_count` días distintos (2):

- varias publicaciones el mismo día suelen ser varias ubicaciones: no cuentan;
- la misma oferta en varios portales (InfoJobs e Indeed) no es republicar: no cuenta.

La bandeja y «Por revisar» muestran «Republicada ×N» (las fechas, al pasar el ratón) y la ficha una
nota. Puede ser una oferta difícil de cubrir o una que el portal renueva sola: decides tú.

## Búsqueda ampliada (fase 16)

### Títulos parecidos: skill `broaden-search`

`get_search_titles` (`cai jobs titles`) agrupa los títulos de las ofertas que apruebas o envías y de
las que descartas (con sus motivos; no las descartadas por estar cerradas) en los últimos 90 días.
Marca con `matches_roles: false` los puestos que te interesan y que el filtro previo de conectores y
alertas deja fuera. El skill `broaden-search` propone, con esa base, hasta 8 títulos cercanos
(«Data Platform Engineer», «Analytics Engineer», «BI Engineer»…) con su porqué y su riesgo y, solo
con tu OK a cada uno, los añade a `preferences.roles` (editando `data/profile.yaml` y reimportándolo)
o a las `search_urls` de tus plataformas (`save_source`). Botón «Ampliar búsqueda» en «Dónde buscar → Portales de empleo».

### Descubrir empresas: `cai sources discover`

```
cai sources discover --file empresas.txt [--add] [--json]
```

- `empresas.txt`: una empresa por línea; `#` comenta. `Nombre | slug` prueba solo ese slug.
- Para cada empresa prueba hasta 3 slugs (`acmedatos`, `acme-datos` y, si tiene 4 letras o más, la
  primera palabra) en las APIs y feeds públicos de los conectores: Greenhouse
  (`boards-api.greenhouse.io/v1/boards/{slug}`), Lever (`api.lever.co` y `api.eu.lever.co`), Ashby
  (`api.ashbyhq.com/posting-api/job-board/{slug}`) y, desde la fase 25.1, Personio, Teamtailor,
  Workable, SmartRecruiters y Recruitee (los endpoints de la tabla de arriba). Todos responden 404 a
  un tablero que no existe salvo SmartRecruiters, que devuelve una lista vacía: ahí solo cuenta si
  tiene alguna oferta. Sin agente ni tokens; una pausa corta entre peticiones (hasta 8 ATS × 3
  slugs por empresa).
- Confianza: Greenhouse y Workable dan el nombre del tablero (SmartRecruiters, el de la empresa en
  cada oferta) (`confirmed` si casa entero con la
  empresa y el slug sale del nombre completo; `doubtful` si no: un tablero «Capital» no confirma
  «Capital Energy»). El resto no lo da: `probable` si el slug sale del nombre completo, `doubtful` si
  de la primera palabra. Se enseñan el número de ofertas y hasta 3 títulos para comprobarlo.
- Sin `--add` solo propone e imprime el `cai sources add …` de cada una. Con `--add` da de alta las
  `confirmed` y `probable` que aún no son fuente (la empresa queda como objetivo); las `doubtful`,
  nunca. Sin herramienta MCP: es un comando para ti.

## Modelo de datos (fase 09b)

- `jobs`: `platform` (str?, p. ej. `linkedin`), `detail_level` (`summary` | `full`) e índice
  único parcial sobre (`platform`, `external_id`) cuando ambos existen.
- Etapa nueva `pending_detail`; evento nuevo `detail_captured` (actor `user` o `system`),
  que lleva a `pending_extraction`. `discarded` y `expired` admitidos desde `pending_detail`.
- `sources.kind` admite además `email_alerts`, `browser_capture` y `agent_browse`.
- Tabla `source_runs`: `id, source_id, actor, started_at, finished_at, found, created,
  completed, errors (JSON)`. También la usan los conectores de la fase 09.
- Tabla `email_messages`: `message_id` (único), `source_id`, `received_at`, `jobs_found`,
  `processed_at`.

## Interfaz para agentes (fase 09b)

| MCP | CLI | Entrada | Salida |
|---|---|---|---|
| `list_sources` | `cai sources list [--kind K] --json` | `kind?` | Fuentes con su config (sin secretos), `browse` y última ejecución, y los límites `agent_browse` |
| `save_source` | `cai sources save --file F --json` | `AgentBrowseSource` | `source_id`, `created`, `allow_agent_browsing`, `message`. Solo tipo `agent_browse`, por `name`; nunca puede poner `allow_agent_browsing: true` en LinkedIn |
| `record_source_run` | `cai sources record-run ID --file F --json` | `SourceRunSummary` (`found, created, existing, incidents[{code, message}], started_at?, finished_at?`) | `ok`, `run_id` |
| `add_job_from_text` (ampliada) | `cai jobs add-text … [--source S] [--platform P] [--external-id X]` | `+ source_id?, platform?, external_id?` | igual que antes |

La captura del botón es un endpoint REST (`POST /capture`) de la app, no de la interfaz para
agentes: la usa la extensión, no el agente.
