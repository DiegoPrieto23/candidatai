# Interfaz para agentes: MCP y CLI

La app expone la misma interfaz de dos formas equivalentes, para que funcione con cualquier agente:

- **Servidor MCP `jobhunter`** (local, stdio, SDK oficial de Python `mcp`, con su `Server` de bajo
  nivel: ADR-013). Es la vía preferida: la mayoría de agentes lo soportan y la configuración se genera desde
  `.agents/manifest.yaml`. Cada agente pone su propio prefijo a los nombres (en Claude Code,
  `mcp__jobhunter__get_status`); los skills usan el nombre corto.
- **CLI `jh` con `--json`** para agentes sin MCP o para depurar. Se ejecuta desde la raíz con
  `uv run --directory backend jh …`. Misma entrada, misma salida y mismos errores que la MCP
  (un test de paridad lo garantiza).

## Reglas comunes

- **Una sola definición por herramienta** en `app/agent_interface/tools.py` (nombre, modelo de
  entrada, modelo de salida, servicio y forma del comando). De ella se derivan la herramienta MCP
  y el comando CLI, y ambos pasan por el mismo `runner`: la paridad sale por construcción.
- Cada herramienta y cada comando llaman a un servicio de `app/services/`; no contienen lógica propia.
- Las entradas se validan con Pydantic y rechazan campos desconocidos. Por CLI todos los valores
  llegan como texto y los valida el mismo modelo, así que los errores coinciden.
- Las entradas largas por CLI se pasan con `--file <ruta>`, que debe estar dentro de `data/tmp/`
  (gitignored): texto de la oferta en `add-text`, JSON en `save-extraction`. El comando borra el
  fichero tras procesarlo correctamente; si falla, lo deja para corregir y reintentar.
- Las salidas son JSON compacto, idéntico por los dos canales (por MCP, además, en
  `structuredContent`). Nada de volcar tablas enteras: siempre `limit`.
- Todos los comandos de la tabla aceptan `--json`. Sin él muestran una salida legible para personas.
- El texto crudo de una oferta solo sale en `get_job`, envuelto así, junto con las señales de
  riesgo que haya detectado el código:
  `<untrusted_job_posting id="42" risk_flags="hidden_text,injection_phrase">…</untrusted_job_posting>`.
- Cada llamada, sea MCP o CLI con `--json`, se registra en `mcp_calls` (con el canal). El nombre
  del cliente sale de la inicialización MCP (`clientInfo.name`) o, por CLI, de la variable
  opcional `JH_CLIENT_NAME`; también se guarda como `agent_name` en los eventos que registra.
  `args_summary` guarda ids, URLs, etapas y tipos; del resto de textos, solo su longitud.
- **Ninguna herramienta ni comando de esta interfaz envía nada al exterior** (ni formularios, ni
  emails, ni mensajes).

## Herramientas y comandos

`jh` = `uv run --directory backend jh`

| MCP | CLI | Fase | Entrada | Salida | Evento |
|---|---|---|---|---|---|
| `get_status` | `jh status --json` | 04 | — | `total`, `by_stage`, `pending_tasks` | — |
| `add_job_from_url` | `jh jobs add-url URL --json` | 04 | `url` | `job_id`, `created`, `duplicate_of?`, `risk_flags` | `found` |
| `add_job_from_text` | `jh jobs add-text --title T --company C --file F [--url U] [--location L] --json` | 04 | `title, company, text, url?, location?` | `job_id`, `created`, `duplicate_of?`, `risk_flags` | `found` |
| | `… [--source S] [--platform P] [--external-id X]` | 09b | Además `source_id?` (una plataforma `agent_browse` con la navegación activada; si no, `not_allowed`), `platform?` y `external_id?` (por defecto, de la URL con `platforms.detect`). Con `source_id`, una oferta de LinkedIn (por URL o `platform`) solo entra por la plataforma LinkedIn | igual | igual (`found` con `source_id`) |
| `list_jobs` | `jh jobs list [--stage S] [--limit N] [--order O] --json` | 04 | `stage?, limit=20, order="score_desc"` | `{jobs: [...]}` resumida (sin texto crudo), con `score` del último match | — |
| `get_job` | `jh jobs show ID --json` | 04 | `job_id` | Metadatos + `text` envuelto como no confiable | — |
| `save_extraction` | `jh jobs save-extraction ID --file F --json` | 04 | `job_id, extraction: JobExtraction` | `ok`, `extraction_id`, `stage`, `injection_suspected`, `hard_filters` (`null` sin perfil) | `extracted` / `injection_suspected` / `hard_filter_failed` |
| `get_extraction` | `jh jobs extraction ID --json` | 04 | `job_id` | `JobExtraction` vigente con `extraction_id`, `schema_version`, `created_at` | — |
| `add_event` | `jh events add ID TYPE [--note N] [--at FECHA] --json` | 04 | `job_id, type, note?, occurred_at?` | `ok`, `event_id`, `stage` resultante | el indicado |
| `get_timeline` | `jh events list ID --json` | 04 | `job_id` | Etapa actual y eventos (sin texto crudo) | — |
| `get_profile` | `jh profile show [--sections S1,S2] --json` | 05 | `sections?` | `profile_version_id`, `created_at`, `profile`: `CandidateProfile` sin email, teléfono ni `private` | — |
| `get_match` | `jh match show ID --json` | 07 | `job_id` | `MatchView`: `score`, `triage_threshold`, `below_threshold`, `hard_filters`, `breakdown` (componentes, skills cubiertas con su nivel y ausentes, similitud, preferencias, notas), `assessment`, `assessment_stale` | `scored` si lo recalcula |
| `save_fit_assessment` | `jh match save-assessment ID --file F --json` | 07 | `job_id, assessment: FitAssessment` | `ok`, `job_id`, `match_id` | `fit_assessed` |
| `list_cv_templates` | `jh templates list --json` | 08 | — | `templates` (`id`, nombre, motor, origen, `ats_friendly`, foto, columnas, página, `capacity`, `sections`, `accent_colors`, fuentes, idiomas, `has_preview`), `invalid` (con el motivo) y `fallback_template` | — |
| `save_cv_content` | `jh cv save ID --file F --json` | 08 | `job_id, content: CvContent, render_options?: CvRenderOptions`; por CLI, `F` = `{"content": …, "render_options": …}` | `document_id` + primer render (`RenderResult`) | `cv_generated`, `cv_rendered` |
| `render_cv` | `jh cv render DOC [--file F] --json` | 08 | `document_id, options?: CvRenderOptions` (por defecto, todo `auto`); por CLI, `F` = las opciones | `RenderResult` | `cv_rendered` |
| `get_cv_content` | `jh cv show (ID \| --document DOC) --json` | 08 | `job_id` (su último CV) o `document_id` | `CvContent`, `evidence` (texto de cada evidencia citada), `verification` y `renders` | — |
| `save_cv_verification` | `jh cv save-verification DOC --file F --json` | 08 | `document_id, verification: CvVerification` | `ok`, `passed`, `stage` y `note` (por qué no pasa a `cv_ready`, si no pasa) | `cv_verified` / `cv_rejected` |
| `save_cover_letter_brief` | `jh letter brief ID --file F --json` | 08c | `job_id, instructions?, max_words?` (50-600); por CLI, `F` = `{"instructions": …, "max_words": …}`. Sustituye al anterior | `ok`, `job_id`, `brief` y `max_words` resuelto | — |
| `get_cover_letter` | `jh letter show (ID \| --document DOC) --json` | 08c | `job_id` (su última carta) o `document_id` | `job_id`, `stage`, `brief` (de la oferta), `preferences` (`preferences.cover_letter`), `max_words` resuelto y `letter` (`null` si no hay): `content` (`CoverLetterContent`), `evidence` resueltas, `word_count`, `instructions_used`, `verification`, `edited_by_user` y `renders` | — |
| `save_cover_letter` | `jh letter save ID --file F --json` | 08c | `job_id, content: CoverLetterContent, render_options?: CoverLetterRenderOptions`; por CLI, `F` = `{"content": …, "render_options": …}` | `document_id`, `word_count` + primer render (`LetterRenderResult`) | `cover_letter_generated` |
| `render_cover_letter` | `jh letter render DOC [--file F] --json` | 08c | `document_id, options?: CoverLetterRenderOptions` | `LetterRenderResult`: como `RenderResult` sin cobertura de keywords, con `options` de la carta (`base_template_id`, `cv_render_id`, `letter_fallback`…) | — |
| `save_cover_letter_verification` | `jh letter save-verification DOC --file F --json` | 08c | `document_id, verification: CvVerification` | `ok`, `passed` | `cover_letter_verified` |
| `save_application_answers` | `jh applications save-answers ID --file F --json` | 10 | `job_id, answers: ApplicationAnswers`; por CLI, `F` = `{"answers": [...]}`. Solo en `approved` o `cv_ready` (si no, `invalid_transition`) | `ok`, `job_id`, `document_id`, `needs_user_input` (cuántas esperan un dato del usuario) | `application_prepared` |
| `list_followups_due` | `jh followups [--days N] --json` | 10 | `days_without_reply?` (por defecto, `followups.days_without_reply` = 10) | `days_without_reply` usado y `followups`: `job_id`, `title`, `company`, `url`, `channel`, `applied_at`, `last_followup_at`, `days_waiting`; la que más espera, primero | — |
| `list_upcoming` | `jh upcoming [--days N] --json` | 10 | `days=7` (1-365) | `days` e `items`: `kind` (`interview`, `test`, `deadline`, `other`, `application_deadline`), `job_id`, `job_title`, `company`, `stage`, `milestone_id` (`null` en el plazo de la oferta), `title`, `starts_at`, `ends_at`, `all_day`, `location`; por fecha | — |
| `get_funnel_stats` | `jh stats funnel [--since AAAA-MM-DD] --json` | 10 | `since?` (fecha; ofertas vistas desde las 00:00 de ese día en Europe/Madrid) | `FunnelStats` (ver §Analítica) | — |
| `list_sources` | `jh sources list [--kind K] --json` | 09b | `kind?` | `sources`: `SourceView` con su config (sin secretos), `browse` (en las `agent_browse`) y última ejecución; `agent_browse`: límites (`max_result_pages`, `delay_seconds`, `default_max_offers`) | — |
| `save_source` | `jh sources save --file F --json` | 09b | `AgentBrowseSource`: `name, platform, search_urls[], priority=5 (1 = primera), access=free\|login\|blocked, allow_agent_browsing? (por defecto true; en LinkedIn false), max_offers?, notes?`; por CLI, `F` = ese objeto | `source_id`, `created`, `allow_agent_browsing` guardado y `message`. Crea o actualiza por `name`. LinkedIn (por `platform` o por cualquier URL de linkedin.com o lnkd.in) con `true`: `not_allowed`; si el usuario ya lo activó, se conserva. Búsquedas de otro dominio: `invalid_request` | — |
| `record_source_run` | `jh sources record-run ID --file F --json` | 09b | `source_id` + `SourceRunSummary`: `found, created, existing=0, incidents[{code, message}], started_at?, finished_at?`; por CLI, `F` = el resumen | `ok`, `run_id`. Actor `agent`; avanza `last_run_at`. Plataforma desactivada: `not_allowed` | — |

La captura del botón «Enviar a Job Hunter» es un endpoint REST de la app (`POST /capture`,
fase 09b), no parte de esta interfaz: la usa la extensión, no el agente.

Las utilidades de autoría de plantillas (`jh templates inspect | build-docx | validate | preview`,
fase 08.3; `scaffold-html` y `compare`, 08b; `build-letter` y `preview --letter`, 08c) son solo CLI:
trabajan con ficheros dentro de `data/` (el original en `data/uploads/` o `data/tmp/`, el mapeo en
`data/tmp/`) y las usa el skill `importar-plantilla-cv`. Aceptan `--json` y dan los errores con el
formato común: un mapeo que no vale es `validation_error` con un detalle por párrafo
(`paragraphs[index=N]`), una ruta fuera de `data/` es `invalid_file` y un `--id` que ya existe sin
`--force`, `exists`. `inspect` da para Word el informe de párrafos y para PDF, imagen o HTML el de
diseño (bloques de texto, paleta, columnas y páginas en PNG). Detalle en `docs/CV_TEMPLATES.md`
§Importar desde Word e §Importar desde PDF, imagen o HTML.

Aprobar o descartar **no tiene herramienta propia a propósito**: esa decisión se toma en la UI. Si
el usuario la dicta a su agente, este puede usar `add_event` con `approved` o `discarded` y el
motivo que él dé en `note`, nunca por iniciativa propia. El evento queda con actor `agent`.

`get_profile` devuelve la última versión importada (no lee `data/profile.yaml`). `sections` admite
`personal`, `headline`, `summary`, `experience`, `projects`, `education`, `certifications`,
`extra_sections` (desde la 08.3), `languages`, `skills`, `basic_skills`, `stories` y `preferences`; por MCP es una lista y por CLI va
separada por comas. `schema_version` sale siempre. De `personal` solo salen los campos de una lista
blanca (`PUBLIC_PERSONAL_FIELDS`): un campo nuevo no se expone hasta añadirlo ahí. Los niveles
F/C+/C/B y las marcas `nda` sí salen: el agente los necesita para aplicar `POLICIES.md` §1.

### Comandos del perfil (solo CLI)

Mantenimiento de `data/profile.yaml`; los usa el skill `actualizar-perfil`. Todos aceptan `--json`
(errores con el formato común; en `validation_error`, `field` es la ruta del campo, p. ej.
`experience[1].achievements[0].id`). Una ruta relativa vale desde el directorio actual o desde la
raíz del repo.

| Comando | Qué hace |
|---|---|
| `jh profile init` | Copia `demo/profile.example.yaml` a `data/profile.yaml` si no existe (si existe: error `exists`) |
| `jh profile validate [RUTA]` | Valida sin importar. Por defecto, `data/profile.yaml` |
| `jh profile import [RUTA]` | Valida y crea una versión nueva si el contenido cambia respecto a la vigente (`created: false` si no) |
| `jh profile diff` | Diff unificado entre las dos últimas versiones; `private` sale como `<oculto>` |

`add_event` no acepta los eventos que registra su propia herramienta o el sistema: `found`,
`duplicate_detected`, `extracted`, `hard_filter_failed`, `scored`, `fit_assessed`,
`cv_generated`, `cv_rendered`, `cv_verified`, `cv_rejected`, `cover_letter_generated`,
`cover_letter_verified` y `application_prepared`. `list_jobs` con
`order="score_desc"` ordena por el score del último match; las ofertas sin score van al final,
las más recientes primero.

### Matching (fase 07)

- `get_match` calcula el match con la extracción vigente y la versión vigente del perfil. Si
  cualquiera de las dos cambió desde el último cálculo, lo recalcula (y registra `scored` si la
  oferta está abierta). Sin extracción o sin perfil importado: `not_found`.
- `save_fit_assessment` guarda la valoración en el match vigente. En una oferta cerrada da
  `invalid_transition`. Si después cambia el perfil o la extracción, `get_match` sigue
  devolviendo esa valoración con `assessment_stale: true` hasta que se guarde otra.
- El score lo calcula el código (`POLICIES.md` §2); el agente no lo corrige, lo explica.

### CV (fase 08)

- `save_cv_content` solo admite ofertas en `approved` o `cv_ready` (si no, `invalid_transition`).
  Antes de guardar comprueba lo que el código puede comprobar de `POLICIES.md` §1: ids de
  experiencia, proyecto, formación y certificación, evidencias que existen en el perfil, skills que
  están en el perfil (con los sinónimos de `config/skill_aliases.yaml`) y skills básicas (nivel B o
  `basic_skills`) solo si la oferta las pide («conocimientos de dbt» cuenta como dbt). Si algo
  falla, `validation_error` con un `details` por problema y no se guarda nada.
- El contacto (email, teléfono, ciudad, LinkedIn, GitHub) lo pone el código desde el perfil; el
  agente no lo ve ni lo escribe. Un idioma regional del perfil solo sale con
  `include_regional_language: true`.
- `RenderResult`: `render_id`, `job_id`, `document_id`, `template_id`, `template_hash`, `options`
  (resueltas: plantilla y de dónde sale —`option`, `rule`, `default_template` o `fallback`—, foto,
  color, páginas, secciones ocultas, tamaño y lo que se sabe de la oferta: ATS, países, sector e
  idioma), `docx_path` y `pdf_path` (relativos a `data/`), `pages`, `max_pages`,
  `keyword_coverage` (`present` y `missing`: skills de la oferta que aparecen o no en el PDF),
  `warnings` (`[{code, message}]`, ver `CV_TEMPLATES.md` §Avisos), `selected` y
  `template_changed` (la plantilla cambió o desapareció desde el render; solo se calcula al
  consultar con `get_cv_content`).
- El primer render sin `too_long` de un CV queda `selected` (el que se enviará). La oferta pasa a
  `cv_ready` cuando un mismo CV está verificado con `passed` y tiene un render sin `too_long`, en
  el orden en que ocurra.

### Carta de presentación (fase 08c)

- Las indicaciones son de dos niveles: `preferences.cover_letter` del perfil y el *brief* de la
  oferta (`save_cover_letter_brief`, que también se edita en la UI). Manda el de la oferta. El
  límite de palabras se resuelve así: brief > perfil > `config/policies.yaml` (180).
- `save_cover_letter` solo admite ofertas en `approved` o `cv_ready`. Rechaza con
  `validation_error`, con un detalle por problema y sin guardar nada:
  - una evidencia del perfil que no existe (valen los ids citables en el CV y los de las
    historias STAR);
  - `user` sin indicaciones (ni `instructions` en el brief ni en el perfil);
  - `extraction` en una oferta sin extracción;
  - más palabras que el límite. Solo cuentan los párrafos, palabras `\w+`;
  - una skill de `keywords_targeted` fuera del perfil;
  - una skill de la oferta que no está en el perfil, nombrada en un párrafo que no cita solo
    `extraction` (o `extraction` y `user`): si cita el perfil, se la estaría atribuyendo;
  - una skill básica (nivel B o `basic_skills`), declarada o nombrada, que la oferta no pide.

  Copia en el documento las indicaciones usadas: son el respaldo de lo que cuenta `user`.
- El render usa por defecto la plantilla, la foto y el color del render seleccionado del CV de la
  oferta (o las reglas del perfil si no hay CV). Si esa plantilla no tiene diseño de carta, usa
  `carta-simple` y avisa `letter_fallback`. Más de una página da `too_long`. Los renders no
  registran eventos. El texto plano lo sirve la API, no esta interfaz.
- Ninguna de estas herramientas cambia la etapa de la oferta ni envía nada.

### Seguimiento (fase 10)

- `list_followups_due`: ofertas en `applied` (sin respuesta) con N días o más desde el envío o el
  último `followup_sent`. Lo que pasa a `in_process` deja de contar. Sirve al skill `resumen-diario`
  para ofrecer el mensaje de seguimiento; registrar que se envió (`followup_sent`) es cosa del
  usuario.
- `list_upcoming`: hitos programados de ofertas abiertas desde las 00:00 de hoy (Europe/Madrid)
  hasta el final del día de dentro de `days` días, más el `application_deadline` de las ofertas
  aún sin enviar. Las horas van en UTC: muéstralas en Europe/Madrid.
- Los hitos, los contactos y el kanban son de la UI (`/board`, `/jobs/{id}/process`,
  `/jobs/{id}/milestones`…): no tienen herramienta. Si el usuario te cuenta una entrevista, pídele
  que la anote en la ficha de la oferta (crea el hito con fecha y registra `interview_scheduled`).
  Un `add_event` con `interview_scheduled` cambia la etapa pero no crea el hito: no saldría en
  `list_upcoming` ni en el calendario.
- `list_upcoming(days=7)` cubre desde las 00:00 de hoy hasta el final del séptimo día (fin
  exclusivo a las 00:00 del día siguiente).
- `jh calendar export [--out RUTA] [--json]` (solo CLI) escribe el `.ics` con los hitos futuros y
  los plazos (por defecto, `data/calendar/jobhunter.ics`). La API sirve el mismo feed en
  `GET /calendar.ics` y cada hito en `GET /milestones/{id}/ics`.

### Analítica (fase 10.2)

`get_funnel_stats(since?)` devuelve (la API, lo mismo en `GET /stats/funnel?since=`); las
definiciones de cada paso están en `DATA_MODEL.md` §Embudo. Tasas entre 0 y 1 con 4 decimales,
`null` si el denominador es 0:

```jsonc
{
  "since": "2026-09-01",            // o null
  "duplicates_excluded": 1,         // cerradas por duplicate_detected: fuera del embudo
  "steps": [                        // siempre los 8, en este orden
    {"step": "found", "label": "Encontradas", "count": 10,
     "rate_from_previous": null, "rate_from_start": 1.0}
    // triaged, approved, applied, replied, interview, offer, accepted
  ],
  "by_source": [                    // por encontradas, de más a menos
    {"source_id": 1, "kind": "greenhouse", "name": "…", "found": 5, "approved": 3,
     "applied": 3, "replied": 2, "interview": 1, "reply_rate": 0.6667}
  ],
  "by_title": [                     // los 8 más frecuentes, «Otros» y «Sin extraer»
    {"title": "data engineer", "group": "title", "found": 3, "…": "…"},
    {"title": "Otros", "group": "others", "…": "…"},
    {"title": "Sin extraer", "group": "not_extracted", "…": "…"}
  ],
  "by_week": [                      // semanas ISO seguidas (las vacías, a cero)
    {"week": "2026-W39", "week_start": "2026-09-21", "found": 5, "…": "…"}
  ],
  "response_time": {"applied": 5, "replied": 3, "median_days": 2.0, "mean_days": 2.2,
                    "awaiting_reply": 1, "closed_without_reply": 1},
  "discard_reasons": [{"reason": "skills", "count": 1}],      // `unspecified` sin motivo
  "hard_filter_failures": [{"filter": "location", "count": 2}]
}
```

`reply_rate` = con respuesta / enviadas. Los motivos y los filtros cuentan ofertas, no eventos:
cuenta toda oferta del periodo con algún `discarded` (o `hard_filter_failed`), aunque luego se
reabriera; descartada dos veces por lo mismo cuenta una vez, y por motivos distintos (o con dos
filtros fallidos) cuenta en cada uno, así que la suma puede pasar del número de ofertas.
Solo lectura: no registra eventos.

### Comandos de matching y worker (solo CLI)

| Comando | Qué hace |
|---|---|
| `jh worker [--once] [--interval S] [--json]` | Ejecuta la cola de tareas (`score_job`, `rescore_all`, `run_source`, `poll_email`, `expire_summaries`) y, en primer plano, la ingesta diaria de las fuentes a la hora de `connectors.daily_at` (al arrancar, también las que no corrieron desde la última hora programada), la caducidad diaria de los resúmenes y la lectura de alertas cada `email_alerts.poll_minutes` (si hay IMAP o correos en `data/inbox/`). Log legible en consola y en `data/logs/worker.log`. `--once` vacía la cola y termina (código 1 si alguna falla) |
| `jh match rescore [--json]` | Recalcula ya los matches desfasados de las ofertas abiertas (tras instalar el extra `matching` o editar `config/policies.yaml`) y cierra las de triaje que no pasan los filtros. Devuelve `scored` y `closed` |
| `jh eval matching [--profile RUTA] [--no-seed] [--no-embeddings] [--json]` | Precision, recall y F1 con el umbral actual y por umbral sobre `evals/matching/*.jsonl` (perfil de demo) y `data/evals/*.jsonl` (tu perfil). Guarda el informe en `data/evals/reports/` |

### Fuentes: empresas objetivo y portales (fase 09, solo CLI)

Las usa la persona (CLI o pantalla «Empresas» de la UI). `jh sources list` es desde la 09b la
herramienta `list_sources` (tabla de arriba); las plataformas `agent_browse` se ven y se activan en
la pantalla «Plataformas».

| Comando | Qué hace |
|---|---|
| `jh sources add --kind K --name N [--slug S] [--region global\|eu] [--query Q] [--where W] [--province P] [--country C] [--keywords a,b] [--json]` | Añade una fuente. ATS (`greenhouse`, `lever`, `ashby`): `--slug` del tablero; la empresa queda como objetivo (`companies.watchlist`). Portales (`infojobs`, `adzuna`): `--query`. Error `exists` si ya está |
| `jh sources list [--kind K] [--json]` | `{sources: [SourceView], agent_browse}`: tipo, nombre, `config` (sin secretos), `active`, `keys_missing`, `browse`, `last_run_at` y `last_run` (encontradas, tras filtros, nuevas, errores), y los límites de la búsqueda con navegador |
| `jh sources test ID \| --kind K --name N … [--json]` | Descarga y aplica el filtro previo sin guardar nada: `found`, `after_filters`, `message` («12 ofertas encontradas, 3 tras filtros»), ofertas con `passed` y `reason`, y `errors`. Código 1 si la fuente falla |
| `jh capture token [--json]` | Genera (o rota) el token del botón «Enviar a Job Hunter» y lo muestra una vez; en `data/capture_token` solo queda su sha256. Con `--json`: `{token, extension_id}` |
| `jh alerts poll [--json]` | Lee ya las alertas nuevas (IMAP en solo lectura y `data/inbox/`, fase 09b) y da de alta sus ofertas: completas si el portal se deja descargar, si no como resumen en `pending_detail`. `EmailPollResult` con `messages`, `found`, `created`, `summaries`, `existing`, `job_ids` y `errors` |
| `jh alerts list [--json]` | Ofertas resumen (`AlertList`): título, empresa, ubicación, plataforma, URL, `expires_at` y prefiltro (`prefilter_passed`, `prefilter_reason`), primero las que pasan |
| `jh alerts expire [--json]` | Cierra con `expired` los resúmenes sin completar más antiguos que `email_alerts.summary_expire_days` |
| `jh sources run [ID] [--json]` | Ejecuta ya una fuente (o todas las activas) y guarda lo nuevo en `pending_extraction`. `{runs: [SourceRunResult]}` con `created`, `existing`, `duplicates`, `job_ids` y `errors` |
| `jh sources enable ID` / `disable ID` | Activa o pausa una fuente en la ingesta diaria |

### Candidatura asistida (fase 11): sin herramientas, a propósito

Rellenar y enviar formularios de candidatura no está en la interfaz para agentes: no hay
herramienta MCP ni comando `jh … --json`. Se desencadena solo desde la UI (POLICIES §5) y un test
comprueba que la CLI, el servidor MCP y `agent_interface` no importan el servicio, el token ni el
envío. El agente prepara el paquete (`save_application_answers`, la carta) y el usuario hace el
resto en la ficha.

## Errores

Mismo JSON por los dos canales (por MCP, con `isError: true`; por CLI, con código de salida 1):

```json
{"ok": false, "error": {"type": "validation_error",
  "message": "Entrada no válida (1 error): extraction.seniority.",
  "details": [{"field": "extraction.seniority", "received": "sr",
               "reason": "Debe ser uno de: intern, junior, mid, senior, lead, unknown."}]}}
```

| `type` | Cuándo |
|---|---|
| `validation_error` | La entrada no cumple el esquema. `details` lista cada campo, el valor recibido (como texto, recortado) y el motivo |
| `not_found` | No existe la oferta, aún no tiene extracción, no hay perfil importado, no existe el CV o la plantilla |
| `invalid_transition` | El evento no es válido en la etapa actual de la oferta |
| `invalid_request` | El servicio rechaza la petición (URL de LinkedIn, evento reservado…) |
| `not_allowed` | La búsqueda con navegador no está permitida ahí: activar LinkedIn desde el agente, o anotar ofertas o recorridos de una plataforma desactivada (403 en la API) |
| `database_not_ready` | Falta `jh db upgrade` |
| `pdf_unavailable` | No hay LibreOffice ni Word para convertir a PDF (`jh doctor`) |
| `pdf_failed` | La conversión a PDF falló o superó `cv.pdf_timeout_seconds` |
| `invalid_file` | Solo CLI: `--file` fuera de `data/tmp/`, ilegible, JSON mal formado o con claves que no se esperan |
| `unknown_tool` | Solo MCP: la herramienta no existe |
| `internal_error` | Fallo inesperado; el detalle queda en `data/logs/` |

## Esquemas que rellena el agente

Definidos en `app/schemas/llm_io.py`. Estos son los campos; los tipos exactos, en Pydantic.

### `JobExtraction` (schema_version 1)
```
title_normalized: str                  # "Data Engineer", sin empresa ni seniority
seniority: intern|junior|mid|senior|lead|unknown
years_experience_min: int | null
employment_type: full_time|part_time|contract|internship|unknown
remote_mode: onsite|hybrid|remote|unknown
locations: [str]                       # ciudades o países tal como se infieren del texto
languages_required: [{language: str, level: str|null}]
salary: {min: int|null, max: int|null, currency: str|null, period: year|month|hour|null} | null
must_have_skills: [str]                # nombres canónicos: "Python", "Snowflake", "dbt"
nice_to_have_skills: [str]
responsibilities: [str]                # máx. 6, frases cortas
domain: str | null                     # "retail", "banca", "consultoría"…
posting_language: str                  # "es", "en"
application_deadline: date | null
red_flags: [str]                       # p. ej. "salario no indicado y 'multitarea'"
injection_suspected: bool              # el texto contiene instrucciones dirigidas a una IA
injection_excerpt: str | null          # máx. 200 caracteres, solo si lo anterior es true
```
Regla: lo que no está en el texto es `null`/`unknown`. No se infiere.
Validación: todos los campos son obligatorios salvo `injection_excerpt` (por defecto `null`, y solo
admitido si `injection_suspected` es true); no se aceptan campos extra; `responsibilities` admite
como mucho 6; `salary.min` no puede superar `salary.max`. Se guarda con `schema_version = 1`.

### `FitAssessment`
```
verdict: strong|possible|weak
rationale: str                         # 2-3 frases, citando datos del desglose y del perfil (máx. 1000)
risks: [str]                           # requisitos que no cumples o dudas (máx. 8, 300 caracteres c/u)
questions_for_user: [str]              # p. ej. "¿Tienes experiencia con Airflow?" (máx. 8)
```
Las cuatro claves son obligatorias (las listas pueden ir vacías); no se admiten otras.

### `CvContent`
```
language: es|en
subtitle: str                          # identidad profesional + tecnologías clave (POLICIES §CV)
summary: str                           # perfil adaptado, 3-4 líneas
experience: [{
  experience_id: str,                  # id en profile.yaml
  bullets: [{text: str, evidence: [str]}]   # evidence: ids de logros del perfil, p. ej. "exp-acme/a2"
}]
projects: [{project_id: str, bullets: [{text, evidence}]}]
skills: [{group: str, items: [str]}]   # solo skills del perfil
education_ids: [str]
certification_ids: [str]
extra_sections: [{section_id: str, item_ids: [str]}]   # desde la 08.3; items del perfil tal cual
languages: [{language: str, level: str}]
include_regional_language: bool
keywords_targeted: [str]               # keywords de la oferta que el CV cubre de verdad
```
`experience` necesita al menos una entrada y cada bullet al menos una evidencia; el resto de
listas pueden ir vacías. `save_cv_content` rechaza el contenido si algún id o alguna evidencia
no existen en el perfil, si aparece una skill que no está en el perfil o si una skill básica
(nivel B o `basic_skills`) no la pide la oferta.

### `CvRenderOptions`
Opciones de presentación, independientes del contenido. `null`/`auto` = lo decide la app con las
reglas de `docs/CV_TEMPLATES.md` §Opciones.
```
template_id: str | null
photo: auto|include|exclude
accent_color: str | null               # uno de los que admite la plantilla
max_pages: int | null
hidden_sections: [str]                 # summary|experience|projects|education|certifications|extra_sections|skills|languages
page_size: A4|Letter|null
```

### `CvVerification`
```
passed: bool
issues: [{severity: blocker|warning, location: str, problem: str, suggestion: str}]
```
`passed: true` con algún `blocker` es un `validation_error`. `suggestion` es opcional.

### `CoverLetterContent` (fase 08c)
```
language: es|en
recipient: str | null                  # "Equipo de selección de Acme"; null = genérico
greeting: str                          # "Estimado equipo de Acme:"
paragraphs: [{text: str, evidence: [str]}]   # ids del perfil, "extraction" o "user"
sign_off: str                          # "Un saludo,"; el nombre lo pone el código
keywords_targeted: [str]
```
Al menos un párrafo, y cada uno con al menos una evidencia. El contacto, la fecha y el lugar los
pone el código. Las indicaciones usadas se guardan con el documento (no las escribe el agente).

### `CoverLetterRenderOptions` (fase 08c)
```
template_id: str | null                # null = la del CV seleccionado; si no tiene carta, carta-simple
photo: auto|include|exclude            # auto = como el CV seleccionado
accent_color: str | null               # null = el del CV seleccionado
page_size: A4|Letter|null
```

### `ApplicationAnswers`
```
answers: [{question: str, answer: str, evidence: [str], needs_user_input: bool}]
```
Las cuatro claves son obligatorias; entre 1 y 50 respuestas (pregunta de hasta 1000 caracteres,
respuesta de hasta 5000, hasta 10 evidencias). `save_application_answers` comprueba, y da un
`validation_error` con un detalle por problema sin guardar nada:
- cada evidencia es un id del perfil citable en el CV (`exp-x`, `exp-x/a1`, `prj-x`, `edu-x`,
  `cert-x`, `seccion/item`), el id de una historia STAR (`stories`), `extraction` (lo dice la
  oferta) o `user` (lo contó el usuario);
- una respuesta con texto lleva al menos una evidencia;
- una respuesta vacía solo vale con `needs_user_input: true` (salario, disponibilidad, permiso de
  trabajo…: lo decide el usuario en la UI).

Se guarda como `document` de `kind = answers` con la versión vigente del perfil. La edición desde
la UI (`POST /jobs/{id}/answers`) crea otro documento con `edited_by_user` y actor `user`; ahí no
se exigen evidencias, pero las que haya deben existir. El paquete de candidatura
(`GET /jobs/{id}/package`) muestra siempre el último.

La carta no va aquí: es un documento propio (fase 08c). El paquete de candidatura usa la última
carta de la oferta con su render seleccionado (`JobPackage.cover_letter`, con su texto plano).
