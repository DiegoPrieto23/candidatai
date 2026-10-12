# Fuentes de ofertas

De dónde llegan las ofertas a CandidatAI, qué hace cada vía y con qué límites. Todas acaban en el
mismo sitio: la tabla `jobs`, con deduplicación, detección de riesgo e historial de eventos.

| Vía | Fase | Automática | Cubre |
|---|---|---|---|
| Alta manual por URL o texto | 03 | No | Cualquier oferta |
| APIs públicas de ATS (Greenhouse, Lever, Ashby) | 09 | Sí, diaria | Tus empresas objetivo |
| APIs de portales (InfoJobs, Adzuna), si hay claves | 09 | Sí, diaria | Búsquedas por palabras clave |
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
del agente (ADR-016) o la búsqueda pública sin sesión que hace la propia app (ADR-033, abajo).

## APIs de ATS y portales (fase 09)

- **Empresas objetivo:** nombre + ATS + slug del tablero, en la página «Fuentes → Empresas objetivo» o con
  `cai sources add`. Endpoints públicos documentados, sin autenticación ni scraping:
  Greenhouse `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`, Lever
  `api.lever.co/v0/postings/{slug}?mode=json` (o `api.eu.lever.co`) y Ashby
  `api.ashbyhq.com/posting-api/job-board/{slug}`.
- **Portales con API (opcionales):** InfoJobs (`api.infojobs.net/api/9/offer` y el detalle de
  cada oferta, con `CAI_INFOJOBS_CLIENT_ID` y `CAI_INFOJOBS_CLIENT_SECRET`) y Adzuna
  (`api.adzuna.com/v1/api/jobs/{país}/search/{página}`, con `CAI_ADZUNA_APP_ID` y
  `CAI_ADZUNA_APP_KEY`). Sin claves, esas fuentes se omiten con un aviso. Adzuna solo da un
  extracto de la descripción: la extracción sale más pobre.
- **Filtro previo** antes de guardar (`ingestion/prefilter.py`): el título debe contener todas las
  palabras de alguno de tus `preferences.roles` (también en español, con
  `config/title_aliases.yaml`; o una `title_keywords` de la fuente) y ninguna
  `discard_title_keywords`; la ubicación, encajar con tus zonas o ser remota si aceptas remoto.
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
- **Conexión IMAP de solo lectura** a una única carpeta o etiqueta (p. ej. una etiqueta de Gmail
  «Alertas empleo» rellenada por un filtro). Abre la carpeta en modo solo lectura: no marca como
  leído, no mueve, no borra. Credenciales en `.env` (`CAI_IMAP_HOST`, `CAI_IMAP_PORT` (993),
  `CAI_IMAP_USER`, `CAI_IMAP_PASSWORD`, `CAI_IMAP_FOLDER`).
  - Solo usa `LOGIN`, `EXAMINE`, `UID SEARCH`, `UID FETCH` con `BODY.PEEK[]` y `LOGOUT`. Busca los
    correos de los últimos `summary_expire_days` días, pide primero solo sus `Message-ID` y
    descarga el cuerpo solo de los nuevos. Un test con un servidor IMAP falso que falla ante
    cualquier escritura lo comprueba.
  - Gmail: IMAP con contraseña de aplicación (requiere verificación en dos pasos). Guía para el
    usuario: `CONFIGURAR_CORREO.md`.
  - Otros proveedores pueden exigir OAuth para IMAP (p. ej. Outlook.com). La fase lo verifica; si
    no es viable, se usa la alternativa de abajo.
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
- Envía los datos desde su *service worker* a `http://127.0.0.1:8000/capture` con un token
  (`cai capture token` lo genera y lo muestra una vez; en `data/capture_token` solo queda su
  sha256; se pega una vez en las opciones de la extensión). La API rechaza peticiones sin token
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
  `search-jobs configurar` (como la etapa 1 del original); en la página «Fuentes → Plataformas» ves
  cada una con sus búsquedas y su último recorrido, y cambias su prioridad, su acceso y si el
  agente puede recorrerla.
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
**apagada por defecto**, es para uso personal y solo la activas tú (ADR-033).

- **Dónde:** tarjeta de LinkedIn en «Fuentes → Plataformas» → «Búsqueda pública sin sesión». Es un interruptor
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
Las dos cosas van a `jobs.signals` (no a `risk_flags`, que es solo riesgo de inyección; ADR-028) y
son **observaciones, no veredictos**: la app nunca cierra una oferta por ellas.

### ¿Sigue abierta?

`services/liveness.py`, una petición ligera por oferta:

- **ATS por su API pública**, si la URL (`boards.greenhouse.io/{slug}/jobs/{id}`,
  `jobs.lever.co/{slug}/{id}`, `jobs.ashbyhq.com/{slug}/{id}`) o la fuente con conector dan el
  tablero y el id: Greenhouse `boards-api.greenhouse.io/v1/boards/{slug}/jobs/{id}` y Lever
  `api.lever.co/v0/postings/{slug}/{id}` (o `api.eu.lever.co`) responden 404 a una oferta retirada;
  en Ashby, la oferta deja de aparecer en `posting-api/job-board/{slug}`.
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
- **LinkedIn nunca** (ADR-016; la búsqueda pública de la fase 22 no cambia esto): `skipped`.

Cuándo se comprueba:

- cada día, con la ingesta, y al arrancar `cai worker`: las ofertas en `approved` y `cv_ready` sin
  comprobación en las últimas `liveness.fresh_hours` (tarea `check_open`, una por oferta);
- al abrir la ficha de una oferta aprobada o con CV listo (si la última es reciente, no repite);
- antes de redactar un CV: el skill `generate-cv` llama a `check_job_open` y, si puede estar
  cerrada, pregunta antes de gastar cuota; el botón «Generar CV» también lo avisa;
- a mano: «Comprobar otra vez» en la ficha o `cai jobs check-open ID --force true`.

Si puede estar cerrada, la ficha lo dice con el motivo y la fecha y ofrece **«Descartar»** (con el
motivo nuevo «Ya no está publicada», `closed`), **«Sigue abierta»** (quita el aviso y ese mismo
motivo ya no vuelve a avisar, hasta que una comprobación la vea abierta) y «Comprobar otra vez». La bandeja y el triaje la marcan «¿Cerrada?».
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

La bandeja y el triaje muestran «Republicada ×N» (las fechas, al pasar el ratón) y la ficha una
nota. Puede ser una oferta difícil de cubrir o una que el portal renueva sola: decides tú.

## Búsqueda ampliada (fase 16)

### Títulos parecidos: skill `broaden-search`

`get_search_titles` (`cai jobs titles`) agrupa los títulos de las ofertas que apruebas o envías y de
las que descartas (con sus motivos; no las descartadas por estar cerradas) en los últimos 90 días.
Marca con `matches_roles: false` los puestos que te interesan y que el filtro previo de conectores y
alertas deja fuera. El skill `broaden-search` propone, con esa base, hasta 8 títulos cercanos
(«Data Platform Engineer», «Analytics Engineer», «BI Engineer»…) con su porqué y su riesgo y, solo
con tu OK a cada uno, los añade a `preferences.roles` (editando `data/profile.yaml` y reimportándolo)
o a las `search_urls` de tus plataformas (`save_source`). Botón «Ampliar búsqueda» en Plataformas.

### Descubrir empresas: `cai sources discover`

```
cai sources discover --file empresas.txt [--add] [--json]
```

- `empresas.txt`: una empresa por línea; `#` comenta. `Nombre | slug` prueba solo ese slug.
- Para cada empresa prueba hasta 3 slugs (`acmedatos`, `acme-datos` y, si tiene 4 letras o más, la
  primera palabra) en las APIs públicas de los conectores: Greenhouse
  (`boards-api.greenhouse.io/v1/boards/{slug}`), Lever (`api.lever.co` y `api.eu.lever.co`) y Ashby
  (`api.ashbyhq.com/posting-api/job-board/{slug}`). Las tres responden 404 a un tablero que no
  existe. Sin agente ni tokens; una pausa corta entre peticiones.
- Confianza: Greenhouse da el nombre del tablero (`confirmed` si casa entero con la empresa y el
  slug sale del nombre completo; `doubtful` si no: un tablero «Capital» no confirma «Capital
  Energy»). Lever y Ashby no lo dan: `probable` si el slug sale del nombre completo, `doubtful` si de
  la primera palabra. Se enseñan el número de ofertas y hasta 3 títulos para comprobarlo.
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
