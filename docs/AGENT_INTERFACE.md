# Interfaz para agentes: MCP y CLI

La app expone la misma interfaz de dos formas equivalentes, para que funcione con cualquier agente:

- **Servidor MCP `candidatai`** (local, stdio, SDK oficial de Python `mcp`, con su `Server` de bajo
  nivel: ADR-013). Es la vía preferida: la mayoría de agentes lo soportan y la configuración se genera desde
  `.agents/manifest.yaml`. Cada agente pone su propio prefijo a los nombres (en Claude Code,
  `mcp__candidatai__get_status`); los skills usan el nombre corto.
- **CLI `cai` con `--json`** para agentes sin MCP o para depurar. Se ejecuta desde la raíz con
  `uv run --directory backend cai …`. Misma entrada, misma salida y mismos errores que la MCP
  (un test de paridad lo garantiza).
- **Con Docker** (fase 26.3, ADR-042), el agente sigue fuera del contenedor: el servidor MCP es
  `docker exec -i candidatai cai-mcp` y la CLI, `docker exec -i candidatai cai … --json`. Mismas
  herramientas y mismas salidas.

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
- **`--file` tolerante (fase 24.2):** si un `--file` JSON no es JSON tal cual, se acepta el
  primer bloque de código Markdown que lo sea (```` ```json … ``` ````) o, si no, un objeto o
  lista que empiece en el primer `{` o `[` del texto y tras el que no haya otro (texto antes o
  después, sí; un JSON truncado no se convierte en uno de sus fragmentos y conserva su error con
  línea y columna). Los modelos pequeños lo envuelven a menudo. Nada más se relaja: el esquema
  sigue siendo estricto.
- **Esquemas (fase 24.2):** `get_schema` (`cai schema [NOMBRE] [--example true] --json`) da el
  JSON Schema de exactamente lo que va en el `--file` de cada herramienta de escritura, cómo se
  envía y, con `example`, un ejemplo mínimo válido (`demo/schemas/`, con los ids del perfil demo).
  Sin nombre, o con `list`, el catálogo. Un test comprueba que toda herramienta con `--file` JSON
  tiene esquema y que cada ejemplo valida. `get_schema` no está en el techo de ninguna acción en segundo
  plano (ADR-032), a propósito: con MCP el esquema ya llega con la herramienta. Sin `--json`, la
  CLI enseña también `esperado:` y `pista:` de cada error.
- Las salidas son JSON compacto, idéntico por los dos canales (por MCP, además, en
  `structuredContent`). Nada de volcar tablas enteras: siempre `limit`.
- Todos los comandos de la tabla aceptan `--json`. Sin él muestran una salida legible para personas.
- El texto crudo de una oferta solo sale en `get_job`, envuelto así, junto con las señales de
  riesgo que haya detectado el código:
  `<untrusted_job_posting id="42" risk_flags="hidden_text,injection_phrase">…</untrusted_job_posting>`.
- Cada llamada, sea MCP o CLI con `--json`, se registra en `mcp_calls` (con el canal). El nombre
  del cliente sale de la inicialización MCP (`clientInfo.name`) o, por CLI, de la variable
  opcional `CAI_CLIENT_NAME`; también se guarda como `agent_name` en los eventos que registra.
  `args_summary` guarda ids, URLs, etapas y tipos; del resto de textos, solo su longitud.
- **Ninguna herramienta ni comando de esta interfaz envía nada al exterior** (ni formularios, ni
  emails, ni mensajes).

## Herramientas y comandos

`cai` = `uv run --directory backend cai`

| MCP | CLI | Fase | Entrada | Salida | Evento |
|---|---|---|---|---|---|
| `get_schema` | `cai schema [NOMBRE] [--example true] --json` | 24.2 | `name?` (sin él, o `list`: el catálogo), `example=false` | Catálogo: `schemas` (`name`, `tool`, `description`). Uno: `name`, `tool`, `description`, `send` (cómo va por `--file` y por MCP), `json_schema` y `example` (o `null`). Nombres: `extraction`, `fit-assessment`, `cv-content`, `cv-render-options`, `cv-verification`, `application-answers`, `cover-letter-brief`, `cover-letter`, `cover-letter-render-options`, `cover-letter-verification`, `reply-proposal`, `message-draft`, `company-research`, `interview-plan`, `interview-notes`, `source`, `source-run`. Uno que no existe: `not_found` con los más parecidos | — |
| `get_status` | `cai status --json` | 04 | — | `total`, `by_stage`, `pending_tasks`, `agent_requests` (encargos pendientes, 19), `demo_mode` (12.1) | — |
| `add_job_from_url` | `cai jobs add-url URL --json` | 04 | `url` | `job_id`, `created`, `duplicate_of?`, `risk_flags` | `found` |
| `add_job_from_text` | `cai jobs add-text --title T --company C --file F [--url U] [--location L] --json` | 04 | `title, company, text, url?, location?` | `job_id`, `created`, `duplicate_of?`, `risk_flags` | `found` |
| | `… [--source S] [--platform P] [--external-id X]` | 09b | Además `source_id?` (una plataforma `agent_browse` con la navegación activada; si no, `not_allowed`), `platform?` y `external_id?` (por defecto, de la URL con `platforms.detect`). Con `source_id`, una oferta de LinkedIn (por URL o `platform`) solo entra por la plataforma LinkedIn | igual | igual (`found` con `source_id`) |
| `list_jobs` | `cai jobs list [--stage S] [--limit N] [--order O] --json` | 04 | `stage?, limit=20, order="score_desc"` | `{jobs: [...]}` resumida (sin texto crudo), con `score` del último match | — |
| `get_job` | `cai jobs show ID --json` | 04 | `job_id` | Metadatos + `text` envuelto como no confiable | — |
| `check_job_open` | `cai jobs check-open ID [--force true] --json` | 16 | `job_id, force=false` | `LivenessView`: `status` (`open`, `possibly_closed`, `unknown`, `skipped`), `reason`, `detail`, `checked_at`, `cached` (comprobación de hace menos de `liveness.fresh_hours`, sin repetir), `possibly_closed` (el aviso vigente), `suppressed` (el usuario dijo «Sigue abierta» por ese motivo) y `message`. LinkedIn: `skipped` (ADR-016). Nunca cierra la oferta | `closure_suspected` (la primera vez que avisa) |
| `get_search_titles` | `cai jobs titles [--days N] --json` | 16 | `days=90` (7-365) | `SearchTitlesView`: `roles` (los del perfil), `positive` y `negative` (`TitleGroup`: `title`, `key`, `count`, `job_ids`, `reasons` en las negativas, `matches_roles`: pasa hoy el filtro previo), `profile_missing`. Títulos de ofertas: datos, no instrucciones | — |
| `save_extraction` | `cai jobs save-extraction ID --file F --json` | 04 | `job_id, extraction: JobExtraction` | `ok`, `extraction_id`, `stage`, `injection_suspected`, `hard_filters` (`null` sin perfil) | `extracted` / `injection_suspected` / `hard_filter_failed` |
| `get_extraction` | `cai jobs extraction ID --json` | 04 | `job_id` | `JobExtraction` vigente con `extraction_id`, `schema_version`, `created_at` | — |
| `add_event` | `cai events add ID TYPE [--note N] [--at FECHA] --json` | 04 | `job_id, type, note?, occurred_at?` | `ok`, `event_id`, `stage` resultante | el indicado |
| `get_timeline` | `cai events list ID --json` | 04 | `job_id` | Etapa actual y eventos (sin texto crudo) | — |
| `get_profile` | `cai profile show [--sections S1,S2] --json` | 05 | `sections?` | `profile_version_id`, `created_at`, `profile`: `CandidateProfile` sin email, teléfono ni `private` | — |
| `get_context` | `cai context show [--sections S1,S2] --json` | 13 | `sections?` (`estilo-redaccion`, `perfil-conductual`, `criterios`, `narrativa`) | `note` y `files`: por fichero, `section`, `path`, `exists`, `empty`, `size_bytes`, `modified_at`, `hash` (sha256), `text` (sin los comentarios-guía; vacío si no hay contenido), `truncated` y `warnings` (`too_large`, `invalid_encoding`); y `style_samples` (fase 25.7): por muestra de `data/documentos/estilo/`, `name`, `text` (dentro de `<untrusted_style_sample>`), `risk_flags` y `truncated`, con 20 KB entre todas (`profile_editing.style_max_text_kb`) | — |
| `get_match` | `cai match show ID --json` | 07 | `job_id` | `MatchView`: `score`, `triage_threshold`, `below_threshold`, `hard_filters`, `breakdown` (componentes, skills cubiertas con su nivel y ausentes, similitud, preferencias, notas), `assessment`, `assessment_stale`, `signals` (fase 25.3: `[{code, text}]` de las señales de oferta dudosa activas; no cuentan en el score) | `scored` si lo recalcula |
| `save_fit_assessment` | `cai match save-assessment ID --file F --json` | 07 | `job_id, assessment: FitAssessment` | `ok`, `job_id`, `match_id` | `fit_assessed` |
| `list_cv_templates` | `cai templates list --json` | 08 | — | `templates` (`id`, nombre, motor, origen, `ats_friendly`, foto, columnas, página, `capacity`, `sections`, `accent_colors`, fuentes, idiomas, `has_preview`), `invalid` (con el motivo) y `fallback_template` | — |
| `save_cv_content` | `cai cv save ID --file F --json` | 08 | `job_id, content: CvContent, render_options?: CvRenderOptions`; por CLI, `F` = `{"content": …, "render_options": …}` | `document_id` + primer render (`RenderResult`) | `cv_generated`, `cv_rendered` |
| `render_cv` | `cai cv render DOC [--file F] --json` | 08 | `document_id, options?: CvRenderOptions` (por defecto, todo `auto`); por CLI, `F` = las opciones | `RenderResult` (sus `warnings`, desde la 25.5, con los de maquetación: `page` y `fix`; con `fix: content` se recorta como con `too_long`) | `cv_rendered` |
| `get_cv_content` | `cai cv show (ID \| --document DOC) --json` | 08 | `job_id` (su último CV) o `document_id` | `CvContent`, `evidence` (texto de cada evidencia citada), `verification` y `renders` | — |
| `save_cv_verification` | `cai cv save-verification DOC --file F --json` | 08 | `document_id, verification: CvVerification` | `ok`, `passed`, `stage` y `note` (por qué no pasa a `cv_ready`, si no pasa) | `cv_verified` / `cv_rejected` |
| `save_cover_letter_brief` | `cai letter brief ID --file F --json` | 08c | `job_id, instructions?, max_words?` (50-600); por CLI, `F` = `{"instructions": …, "max_words": …}`. Sustituye al anterior | `ok`, `job_id`, `brief` y `max_words` resuelto | — |
| `get_cover_letter` | `cai letter show (ID \| --document DOC) --json` | 08c | `job_id` (su última carta) o `document_id` | `job_id`, `stage`, `brief` (de la oferta), `preferences` (`preferences.cover_letter`), `max_words` resuelto y `letter` (`null` si no hay): `content` (`CoverLetterContent`), `evidence` resueltas, `word_count`, `instructions_used`, `verification`, `edited_by_user` y `renders` | — |
| `save_cover_letter` | `cai letter save ID --file F --json` | 08c | `job_id, content: CoverLetterContent, render_options?: CoverLetterRenderOptions`; por CLI, `F` = `{"content": …, "render_options": …}` | `document_id`, `word_count` + primer render (`LetterRenderResult`) | `cover_letter_generated` |
| `render_cover_letter` | `cai letter render DOC [--file F] --json` | 08c | `document_id, options?: CoverLetterRenderOptions` | `LetterRenderResult`: como `RenderResult` sin cobertura de keywords, con `options` de la carta (`base_template_id`, `cv_render_id`, `letter_fallback`…) | — |
| `save_cover_letter_verification` | `cai letter save-verification DOC --file F --json` | 08c | `document_id, verification: CvVerification` | `ok`, `passed` | `cover_letter_verified` |
| `save_application_answers` | `cai applications save-answers ID --file F --json` | 10 | `job_id, answers: ApplicationAnswers`; por CLI, `F` = `{"answers": [...]}`. Solo en `approved` o `cv_ready` (si no, `invalid_transition`) | `ok`, `job_id`, `document_id`, `needs_user_input` (cuántas esperan un dato del usuario) | `application_prepared` |
| `list_followups_due` | `cai followups [--days N] --json` | 10 (15) | `days_without_reply?` (por defecto, `followups.days_without_reply` = 10) | `days_without_reply` usado, `max_followups` y `followups`: `job_id`, `title`, `company`, `url`, `channel`, `applied_at`, `last_followup_at`, `days_waiting`, `followups_sent`, `contacts` (nombres, sin datos de contacto) y `draft_id`; la que más espera, primero, sin las que ya tienen `max_followups`. `thank_you_days` y `thanks_due`: entrevistas hechas en esos días sin agradecimiento (`milestone_id`, `interview_title`, `interview_at`, `contacts`, `draft_id`) | — |
| `list_upcoming` | `cai upcoming [--days N] --json` | 10 | `days=7` (1-365) | `days` e `items`: `kind` (`interview`, `test`, `deadline`, `other`, `application_deadline`), `job_id`, `job_title`, `company`, `stage`, `milestone_id` (`null` en el plazo de la oferta), `title`, `starts_at`, `ends_at`, `all_day`, `location`; por fecha | — |
| `get_funnel_stats` | `cai stats funnel [--since AAAA-MM-DD] --json` | 10 | `since?` (fecha; ofertas vistas desde las 00:00 de ese día en Europe/Madrid) | `FunnelStats` (ver §Analítica) | — |
| `get_calibration` | `cai stats calibration [--since AAAA-MM-DD] [--min-cases N] --json` | 20 | `since?` (fecha; candidaturas **enviadas** desde las 00:00 de ese día en Europe/Madrid), `min_cases=10` (1-1000) | `Calibration` (ver §Calibración) | — |
| `get_skill_gaps` | `cai skills gaps [--days N] [--status gap\|have\|unmarked] --json` | 14 | `days=60` (1-365), `status?` | `days`, `jobs_considered`, `gaps` y `profile_skills` (ver §Huecos de skills) | — |
| `list_replies` | `cai replies list [--status S] [--limit N] --json` | 15 | `status?` (`new`, `proposed`, `accepted`, `ignored`), `limit=50` | `replies` (sin texto: remitente, candidatas, propuesta) y `counts` por estado | — |
| `get_reply` | `cai replies show ID --json` | 15 | `reply_id` | El correo en `<untrusted_email>`, `candidates` (oferta, etapa, envío, próximos hitos), `timezone` y `proposal` | — |
| `save_reply_proposal` | `cai replies propose ID --file F --json` | 15 | `reply_id`, `proposal` (ver §Respuestas) | `status: proposed`, `stage`, `valid_now`, `message` | — (la acepta el usuario en la UI) |
| `save_message_draft` | `cai drafts save ID --file F --json` | 15 (18) | `job_id`, `draft`: `{kind: followup \| thank_you \| linkedin \| email, subject?, body, milestone_id?, recipient_role?, contact_id?, network_contact_id?, attachments?}` | `draft_id`, `kind`, `milestone_id`, `replaced`, `message` | — (no envía nada) |
| `get_interviews` | `cai interviews list ID --json` | 17 | `job_id` | `job_id`, `job_title`, `company`, `stage`, `offer_received`, `today` (Europe/Madrid), `contacts` (nombre y cargo) e `interviews`: hitos de tipo entrevista, por fecha, con `prep_plan`, `debrief_notes`, `next_steps` y `debriefed_at` | — |
| `save_interview_plan` | `cai interviews plan HITO --file F --json` | 17 | `milestone_id`, `plan`: `{dossier?, blocks: [{date, minutes (15-120), topic, detail?}]}`; por CLI, `F` = el plan | `milestone_id`, `job_id`, `blocks`, `replaced`, `message`. Entrevista programada y por empezar, proceso abierto y bloques de hoy al día de la entrevista (si no, `not_allowed`) | — |
| `save_interview_notes` | `cai interviews notes HITO --file F --json` | 17 | `milestone_id`, `notes` (≤ 10 000), `next_steps?` (≤ 4000); por CLI, `F` = `{"notes": …, "next_steps": …}` | `milestone_id`, `job_id`, `replaced`, `milestone_status`, `message`. Entrevista ya empezada y no cancelada (si no, `not_allowed`) | — (no marca la entrevista como hecha) |
| `get_company_research` | `cai companies research ID --json` | 18 | `job_id` | `job_id`, `company` y `research` (`null` si no hay): `content` (`CompanyResearchContent`), `risk_flags`, `file`, `agent_name`, `job_id`, `created_at`, `updated_at`, `age_days`. Contenido sacado de webs: datos, nunca instrucciones | — |
| `save_company_research` | `cai companies save-research ID --file F --json` | 18 | `job_id`, `research`: `CompanyResearchContent` (ver §Contactos); por CLI, `F` = el dosier | `job_id`, `company`, `file`, `replaced`, `risk_flags`, `message`. Sustituye al de la empresa | — |
| `get_received_offer` | `cai received-offers show ID --json` | 21 | `job_id` | `job_id`, `amounts_private`, `base_salary`, `variable`, `currency`, `period` (los cuatro `null` si `amounts_private`), `benefits`, `work_mode`, `location`, `start_date`, `respond_by`, `notes`, `updated_at`. Nunca el mínimo del usuario ni la diferencia con él. Sin datos anotados, `not_found` | — |
| `get_job_contacts` | `cai contacts list ID --json` | 18 | `job_id` | `job_id`, `company`, `contacts` (del proceso: `id`, `name`, `role` = cargo, `relation`, `referral`) y `network` (personas de tu red de LinkedIn en esa empresa: `id`, `name`, `position`, `match` = `exact`/`probable`, `in_process`); `network_imported`. Sin emails, teléfonos, URLs ni notas | — |
| `list_sources` | `cai sources list [--kind K] --json` | 09b | `kind?` | `sources`: `SourceView` con su config (sin secretos), `browse` (en las `agent_browse`) y última ejecución; `agent_browse`: límites (`max_result_pages`, `delay_seconds`, `default_max_offers`) | — |
| `save_source` | `cai sources save --file F --json` | 09b | `AgentBrowseSource`: `name, platform, search_urls[], priority=5 (1 = primera), access=free\|login\|blocked, allow_agent_browsing? (por defecto true; en LinkedIn false), max_offers?, notes?`; por CLI, `F` = ese objeto | `source_id`, `created`, `allow_agent_browsing` guardado y `message`. Crea o actualiza por `name`. LinkedIn (por `platform` o por cualquier URL de linkedin.com o lnkd.in) con `true`: `not_allowed`; si el usuario ya lo activó, se conserva. Búsquedas de otro dominio: `invalid_request` | — |
| `record_source_run` | `cai sources record-run ID --file F --json` | 09b | `source_id` + `SourceRunSummary`: `found, created, existing=0, incidents[{code, message}], started_at?, finished_at?`; por CLI, `F` = el resumen | `ok`, `run_id`. Actor `agent`; avanza `last_run_at`. Plataforma desactivada: `not_allowed` | — |
| `list_agent_requests` | `cai requests list [--status S] [--limit N] --json` | 19 | `status="pending"` (`pending`, `done`, `cancelled` o `null` para todos), `limit=50` | `requests` (`id`, `action`, `label`, `job_id`, `milestone_id`, `prompt`, `status`, `summary`, `agent_name`, fechas; los pendientes, el más antiguo primero) y `pending` | — |
| `complete_agent_request` | `cai requests complete ID --summary S --json` | 19 | `request_id`, `summary` (1-2000) | `ok`, `request_id`, `message`. Ya cerrado: `not_allowed` | — |
| `request_user_action` | `cai prompts request --kind K --message M [--url U] [--source-id ID] [--timeout-seconds S] --json` | mejora | `kind` (`captcha`, `anti_bot`, `login_required`), `message` (≤ 500), `url?`, `source_id?`, `timeout_seconds` (60-900, por defecto 300) | `PromptView`: `id`, `kind`, `title`, `message`, `status` (`pending`), `expires_at`, `seconds_left`… La UI enseña un pop-up y una notificación del sistema. Un aviso anterior de la misma plataforma caduca. Plataforma inexistente: `not_found` | — |
| `wait_user_action` | `cai prompts wait ID [--max-wait-seconds S] --json` | mejora | `prompt_id`, `max_wait_seconds` (0-55, por defecto 50) | `PromptView` con `status`: `pending` (vuelve a llamar), `done` (lo resolvió el usuario), `skipped` o `expired`. Aviso inexistente: `not_found` | — |

La captura del botón «Enviar a CandidatAI» es un endpoint REST de la app (`POST /capture`,
fase 09b), no parte de esta interfaz: la usa la extensión, no el agente.

Las utilidades de autoría de plantillas (`cai templates inspect | build-docx | validate | preview`,
fase 08.3; `scaffold-html` y `compare`, 08b; `build-letter` y `preview --letter`, 08c) son solo CLI:
trabajan con ficheros dentro de `data/` (el original en `data/uploads/` o `data/tmp/`, el mapeo en
`data/tmp/`) y las usa el skill `import-cv-template`. Aceptan `--json` y dan los errores con el
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

`get_context` lee `data/contexto/*.md` en cada llamada (no hay versiones: el `hash` dice si cambió).
Son indicaciones del usuario, no contenido no confiable, pero **nunca respaldan un hecho**
(`POLICIES.md` §1.5): el tono de un CV o una carta, los riesgos de una oferta y la preparación de
entrevistas. Un fichero que no existe sale con `exists: false`, no es un error. Si pasa de 20 KB,
se recorta y avisa con `too_large`.

### Comandos del perfil (solo CLI)

Mantenimiento de `data/profile.yaml`; los usan los skills `update-profile` y `expand`
(fase 25.2). Todos aceptan `--json` (errores con el formato común; en `validation_error`, `field`
es la ruta del campo, p. ej. `experience[1].achievements[0].id`). Una ruta relativa vale desde el
directorio actual o desde la raíz del repo.

| Comando | Qué hace |
|---|---|
| `cai profile init` | Copia `demo/profile.example.yaml` a `data/profile.yaml` si no existe (si existe: error `exists`) |
| `cai profile validate [RUTA]` | Valida sin importar. Por defecto, `data/profile.yaml` |
| `cai profile import [RUTA]` | Valida y crea una versión nueva si el contenido cambia respecto a la vigente (`created: false` si no) |
| `cai profile diff` | Diff unificado entre las dos últimas versiones; `private` sale como `<oculto>` |
| `cai context init` | Crea los ficheros de `data/contexto/` que falten (solo encabezados y comentarios-guía de las plantillas de `demo/contexto/`, sin sus datos) y las carpetas de `data/documentos/`. Nunca sobrescribe (fase 13) |
| `cai applications archive (ID \| --all)` | Archiva ya, sin worker, las candidaturas enviadas que aún no tienen carpeta en `data/documentos/candidaturas/` (para las de antes de la fase 13). Usa la carta y las respuestas vigentes. Las que ya la tienen no se tocan |

**Ni herramienta ni comando escriben el perfil desde el agente** (fase 25.7, ADR-039). El usuario
edita el perfil, el contexto y sus muestras de estilo en «Mi perfil», por rutas de la API que solo
acepta la UI (`require_ui`): `PUT /profile/sections/{section}`, `POST /profile/undo`,
`PUT /context/{section}` y `POST`/`DELETE /context/style-samples`. Un test del registro comprueba
que no hay ninguna herramienta MCP de escritura del perfil. Para el agente, el perfil se escribe
con `update-profile` o `expand`, que preguntan antes, y `get_profile` sigue sin email ni teléfono.

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
  último `followup_sent`. Lo que pasa a `in_process` deja de contar, y también las que ya llevan
  `followups.max_followups` (2) seguimientos. Desde la fase 15 trae `thanks_due` (entrevistas
  hechas en los últimos `followups.thank_you_days` días sin agradecimiento enviado). Lo usan
  `daily-summary` y `draft-follow-up`; registrar que se envió (`followup_sent`) es cosa del
  usuario.
- `save_message_draft` (fase 15): guarda un borrador de seguimiento (`followup`) o de
  agradecimiento (`thank_you`). Estos dos, solo en candidaturas `applied` o `in_process`; un
  seguimiento con
  menos de `max_followups` enviados (si no, `not_allowed`) y sin `milestone_id`; un
  agradecimiento con una entrevista hecha (`milestone_id`, por defecto la última; si no hay,
  `not_allowed`). Sustituye el borrador vigente del mismo tipo (y entrevista). **No envía
  nada ni registra eventos**: en la ficha, el usuario lo copia y pulsa «Ya lo he enviado»
  (`POST /drafts/{id}/sent`, solo desde la UI), que en un seguimiento registra `followup_sent`
  con `payload.draft_id`; o «Descartar». Los mensajes de LinkedIn y los correos a personas
  (`linkedin`, `email`, fase 18) tienen sus reglas en §Contactos.
- `list_upcoming`: hitos programados de ofertas abiertas desde las 00:00 de hoy (Europe/Madrid)
  hasta el final del día de dentro de `days` días, más el `application_deadline` de las ofertas
  aún sin enviar. Las horas van en UTC: muéstralas en Europe/Madrid.
- Crear, editar y cerrar hitos y contactos, y el kanban, son de la UI (`/board`,
  `/jobs/{id}/process`, `/jobs/{id}/milestones`…): no tienen herramienta. Si el usuario te cuenta
  una entrevista, pídele que la anote en la ficha de la oferta (crea el hito con fecha y registra
  `interview_scheduled`). Las entrevistas se leen con `get_interviews` (fase 17).
  Un `add_event` con `interview_scheduled` cambia la etapa pero no crea el hito: no saldría en
  `list_upcoming` ni en el calendario.
- `list_upcoming(days=7)` cubre desde las 00:00 de hoy hasta el final del séptimo día (fin
  exclusivo a las 00:00 del día siguiente).
- `cai calendar export [--out RUTA] [--json]` (solo CLI) escribe el `.ics` con los hitos futuros y
  los plazos (por defecto, `data/calendar/candidatai.ics`). La API sirve el mismo feed en
  `GET /calendar.ics` y cada hito en `GET /milestones/{id}/ics`.

### Entrevistas (fase 17)

- `get_interviews`: las entrevistas de una oferta con su plan y su repaso, los contactos (solo
  nombre y cargo) y si hay `offer_received`. Lo usan `prepare-interview`, `mock-interview`
  y `debrief-interview`.
- `save_interview_plan`: el plan de preparación por días de `prepare-interview`, en
  `milestones.prep_plan`. `dossier` es solo el nombre del fichero en `data/entrevistas/` (sin
  carpetas). Sustituye al anterior.
- `save_interview_notes`: el repaso de `debrief-interview` (`debrief_notes`, `next_steps`).
  Sustituye al anterior.
- Ninguna registra eventos ni cambia el estado del hito: marcar la entrevista como hecha
  (`interview_done`) lo hace el usuario en la ficha. Tampoco tocan el perfil: una historia STAR
  nueva entra solo con `update-profile` y la confirmación del usuario (ADR-029).
- Botones de la ficha (ADR-024): «Preparar» y «Simulacro» en una entrevista programada por
  empezar, «Repasar» en una que ya ha empezado y «Dudas antes de aceptar» con un `offer_received`.
  `POST /agent/launch` acepta `milestone_id` (entero) para las tres primeras.

### Contactos, mensajes y dosier de empresa (fase 18)

- `get_job_contacts`: a quién conoce el usuario en la empresa de una oferta y quién está ya en el
  proceso, para elegir a quién escribir. Solo nombre, cargo, papel (`referral`, `recruiter`,
  `hiring_manager`) y la marca de referencia (`requested`, `given`). Nunca la red entera ni datos
  de contacto. `match: probable` quiere decir que la empresa de LinkedIn se parece pero no es
  igual («Brétema» frente a «Brétema Analytics»): dilo antes de darlo por hecho.
- `cai contacts import-linkedin [RUTA] [--json]` (solo CLI, sin herramienta MCP: lo lanza el
  usuario): importa la exportación oficial `Connections.csv` (por defecto,
  `data/documentos/linkedin/Connections.csv`) y sincroniza la red (avisa si quita más de la mitad). Sin emails. Salida: `path`,
  `total`, `added`, `updated`, `removed`, `skipped`, `without_company`, `message`. La UI lo hace
  con «Importar Connections.csv» (`POST /network/import`, solo desde la UI y solo esa ruta).
- Añadir a alguien de la red como contacto del proceso, o marcar la referencia, es de la UI
  (`POST /jobs/{id}/contacts/from-network`, `POST /contacts/{id}/referral`): no tiene herramienta.
- Nada de navegar LinkedIn ni buscar perfiles desde el código o el agente.
- `save_message_draft` con `kind: linkedin` (cuerpo ≤ 300 caracteres, sin `subject` ni
  `attachments`) o `kind: email` (con `subject`; `attachments` = nombres de lo que el usuario
  adjuntará): `recipient_role` obligatorio (`recruiter`, `hiring_manager`, `peer`) y, opcional,
  `contact_id` (de esa oferta) o `network_contact_id` (una persona de `network` de esa oferta),
  no los dos; el borrador guarda su nombre. Desde `approved` hasta
  `in_process` (si no, `not_allowed`). Sustituye el vigente del mismo tipo y destinatario. Lo usa
  `draft-message`. «Ya lo he enviado» no registra evento.
- `save_company_research(job_id, research)`: el dosier de `research-company`. Uno por empresa
  (lo comparten sus ofertas). `research`:

  ```jsonc
  {
    "summary": "Qué hace, en 3-5 líneas [1].",      // obligatorio, con cita
    "product": "… [1][2]", "news": "… (junio de 2026) [2]", "engineering_culture": "… [3]",
    "stack": ["Python", "dbt"],                      // nombres cortos, sin repetidos
    "notes": "Qué preguntar o comprobar.",           // la única sección que puede ir sin cita
    "red_flags": [                                   // fase 25.3; 0-10, cada una con cita y fecha
      {"kind": "layoffs", "text": "ERE de 40 personas [2].", "date": "2026-05-12"}
    ],  // kind: layoffs | turnover | reviews | payments | legal | other
    "sources": [{"title": "…", "url": "https://…", "accessed_on": "2026-10-12"}]  // 1-30
  }
  ```

  Una sección con texto o una bandera roja sin cita, con un `[n]` mayor que el número de fuentes,
  una bandera roja sin fecha o una fuente de LinkedIn da `validation_error`. Si `risk_flags` no está vacío, los skills no usan el dosier. El código escribe `data/documentos/empresas/<Empresa>_<id>.md` y busca
  frases de inyección (`risk_flags`). `get_company_research` lo devuelve con `age_days`; lo usan
  `prepare-interview` y `draft-message`, nunca `generate-cover-letter` (POLICIES §7).

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
  "by_referral": [                  // fase 18: siempre given, requested y none, en ese orden
    {"group": "given", "found": 2, "applied": 2, "replied": 2, "…": "…"}
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

### Calibración (fase 20)

`get_calibration(since?, min_cases=10)` responde a «¿acierta el score?» (la API, lo mismo en
`GET /stats/calibration?since=&min_cases=`). Cuenta solo las ofertas **enviadas** (`applied` o
`applied_manually`, sin las duplicadas) y las agrupa por lo que se sabía **al enviarlas**; las
definiciones de cada grupo están en `DATA_MODEL.md` §Calibración. «Con respuesta» y «entrevista»
son los pasos del embudo.

```jsonc
{
  "since": null,                    // fecha del primer envío, o null
  "min_cases": 10,
  "confidence": 0.95,
  "total": {
    "key": "total", "label": "Total",
    "applied": 24, "replied": 9, "interview": 4,
    "awaiting": 3,                  // sin respuesta y aún en `applied`: bajan la tasa sin ser un «no»
    "reply_rate": {"rate": 0.375, "low": 0.2116, "high": 0.5729},   // Wilson al 95 %
    "interview_rate": {"rate": 0.1667, "low": 0.0668, "high": 0.3585},
    "low_data": false               // applied < min_cases
  },
  "by_score": [ /* siempre: lt60, 60_74, 75_84, gte85, none (sin score) */ ],
  "by_verdict": [ /* siempre: strong, possible, weak, none (sin valorar) */ ],
  "by_source": [ /* key = id de la fuente, label = su nombre; solo las que tienen envíos */ ],
  "by_platform": [ /* key = jobs.platform; none = sin portal */ ],
  "by_template": [ /* key = id de la plantilla del CV enviado; none = sin CV de la app */ ],
  "by_cover_letter": [ /* siempre: with, without */ ],
  "by_referral": [ /* siempre: given, requested, none */ ],
  "by_days_to_apply": [ /* siempre: 0_1, 2_3, 4_7, 8_plus (días entre el alta y el envío) */ ],
  "by_signal": [ /* fase 25.3, siempre: salary_range_wide, employer_hidden, fixed_term,
                    stale_repost, ai_screening (una oferta cuenta en cada una que tenga; las de
                    ahora, no las del envío) y none (sin ninguna) */ ]
}
```

Cada grupo tiene la misma forma que `total`. Los fijos salen siempre, en ese orden (a cero si no
tienen envíos, con tasas `null`); los abiertos (fuente, portal, plantilla), de más a menos envíos.
Es **orientativa**: dos grupos con intervalos solapados no son distintos y uno con `low_data` no
permite conclusiones. Solo lectura. El skill `review-search` la usa para proponer cambios;
**nunca** cambia pesos ni filtros (`evals/matching/README.md` §Calibración).

### La historia con números (fase 25.6, solo CLI y API)

`cai stats story [--json]` (y `GET /stats/story`, que usa la tarjeta «Tu búsqueda en números» del
Embudo) cuenta **toda** la búsqueda, desde la primera oferta y sin periodo, en números agregados:

```jsonc
{
  "started_on": "2026-08-13",       // día (Europe/Madrid) de la primera oferta vista
  "first_applied_on": "2026-08-20",
  "last_activity_on": "2026-10-05", // día del último evento
  "weeks": 8,
  "found": 65, "evaluated": 62,     // evaluadas: con extracción, pasaran o no los filtros duros
  "approved": 32, "applied": 21, "replied": 14, "interviews": 6, "offers": 1, "accepted": 0,
  "reply_rate": 0.6667, "interview_rate": 0.2857, "median_days_to_reply": 4.0,
  "markdown": {"es": "**Mi búsqueda con CandidatAI** (13 ago 2026 → 5 oct 2026, 8 semanas): …",
               "en": "**My search with CandidatAI** (13 Aug 2026 → 5 Oct 2026, 8 weeks): …"}
}
```

Los pasos son los del embudo (acumulados, sin duplicadas). **Solo cifras y fechas**: ni empresas,
ni puestos, ni fuentes, ni importes (un test lo comprueba con la demo). Es para que el usuario lo
pegue en su README si quiere; la app no lo publica. Sin herramienta MCP: el agente no lo necesita.

### Ofertas recibidas (fase 21)

`get_received_offer(job_id)` da al agente las condiciones de la oferta que anotó el usuario en la
ficha, para el skill `prepare-negotiation`. Los importes solo si el usuario desmarcó «importes
privados»; **nunca** `private` del perfil ni la comparación con su mínimo, que calcula la API
(`GET /received-offers`) y solo ve la UI (POLICIES §4). Anotar, cambiar y borrar la oferta es solo
de la UI: no hay herramienta para escribirla. Un test recorre todas las herramientas con un mínimo
y unos importes privados centinela y comprueba que no aparecen en ninguna respuesta
(`tests/test_privacy_mcp.py`).

### Huecos de skills (fase 14)

`get_skill_gaps(days=60, status?)` mira las ofertas abiertas con extracción y las aprobadas o
enviadas (`approved`, `applied`, `applied_manually`) en los últimos `days` días aunque ya estén
cerradas, y recalcula la cobertura con el perfil y los alias vigentes (sin embeddings: un alias
nuevo se nota al momento). La API sirve lo mismo en `GET /skills/gaps?days=`.

```jsonc
{
  "days": 60,
  "jobs_considered": 14,
  "gaps": [                          // de más a menos ofertas; a igualdad, por peso
    {"skill": "Kafka",               // la forma más frecuente en las ofertas
     "key": "kafka",                 // forma canónica plegada: identifica la marca
     "must_have_count": 3, "nice_to_have_count": 1, "jobs_count": 4,
     "weight": 2.1,                  // Σ por oferta: 1,0 obligatoria / 0,5 deseable × score / 100
     "mark": "gap",                  // "gap" (no la tiene), "have" (la tiene) o null
     "examples": [{"job_id": 7, "title": "…", "company": "…", "score": 74, "kind": "must_have"}]}
  ],
  "profile_skills": [{"name": "Snowflake", "level": "F"}, {"name": "dbt", "level": "basic"}]
}
```

- Una skill que sale como obligatoria y deseable en la misma oferta cuenta como obligatoria. Una
  oferta sin match todavía cuenta como score 50.
- `status`: `gap`, `have` o `unmarked` filtran por la marca. Las marcadas salen aunque ninguna
  oferta del periodo las pida (con `jobs_count: 0`), mientras el perfil no las cubra.
- Los nombres de skill y los títulos de los ejemplos salen de ofertas: datos no confiables. Un
  nombre de más de 80 caracteres no se cuenta.
- Sin perfil importado: `not_found`. Solo lectura: no registra eventos.
- Marcar y añadir alias es solo de la UI (`POST /skills/marks`, `POST /skills/aliases`): el
  agente no decide qué skills tiene el usuario ni qué nombres son lo mismo (ADR-026).

### Respuestas de las empresas (fase 15)

La app lee los correos de las empresas de tus candidaturas enviadas (`applied`, `in_process`) y
los guarda en `replies` (ver `CONFIGURAR_CORREO.md` §Respuestas). El agente los clasifica con el
skill `review-replies` (rol `classifier`, una sesión aislada por correo) y deja una
propuesta. **Nada cambia de etapa hasta que el usuario la acepta en la UI.**

`get_reply` entrega el correo así (lo de dentro es contenido no confiable):

```
<untrusted_email id="7" risk_flags="">
De: Laura Pazos <laura.pazos@bretema.example>
Asunto: Entrevista para el puesto de Data Engineer
Fecha: 2026-10-05T09:12:00+02:00

Hola: …
</untrusted_email>
```

`proposal` de `save_reply_proposal`:

```jsonc
{
  "job_id": 12,                       // una de las `candidates` del correo
  "event_type": "interview_scheduled",// reply_received | interview_scheduled | test_assigned |
                                      // offer_received | rejected | none (nada que registrar)
  "occurred_at": null,                // por defecto, la fecha del correo
  "milestone": {                      // solo con interview_scheduled o test_assigned
    "title": "Entrevista con Talento", "starts_at": "2026-10-08T10:00:00+02:00",
    "ends_at": null, "all_day": false, "location": "Google Meet"
  },
  "summary": "Primera entrevista por videollamada el jueves 8 a las 10:00.",
  "confidence": "high",               // high | medium | low (con low, sin `milestone`)
  "injection_suspected": false
}
```

- El `job_id` debe estar entre las candidatas (`invalid_request` si no). Una respuesta ya aceptada
  o ignorada por el usuario no admite propuesta (`not_allowed`). Guardar otra propuesta sustituye
  la anterior.
- `valid_now: false` avisa de que el evento no es válido en la etapa actual (p. ej. la oferta ya
  está cerrada): se guarda igual y decide el usuario.
- Sin herramienta para leer el buzón: `cai replies poll` (CLI), la tarea `poll_replies` del worker
  y «Revisar correo ahora» en la UI.
- **Aceptar o ignorar no tiene herramienta ni comando, a propósito**: solo la UI (pantalla
  «Respuestas» y aviso en la ficha de la oferta) llama a `POST /replies/{id}/accept` o `…/ignore`,
  que exigen el origen de la UI y cuerpo JSON (`require_ui`). Aceptar registra el evento como
  `user` con `payload.reply_id` y, si hay hito, lo crea; con `none` archiva sin evento. El usuario
  puede aceptar la propuesta tal cual o cambiar la oferta, el tipo, la fecha o añadir una nota.

### Ofertas vivas y republicadas (fase 16)

- `list_jobs`, `get_job` y las vistas de la UI llevan `signals` (`DATA_MODEL.md` §Fase 16):
  `possibly_closed` y `reposted` son observaciones del código, no veredictos.
- El skill `generate-cv` llama a `check_job_open` antes de redactar: si sale `possibly_closed`,
  avisa y pregunta. **Ningún agente descarta por esto**: descartar (motivo `closed`) o decir «Sigue
  abierta» lo hace el usuario en la UI (`POST /jobs/{id}/still-open`, con `require_ui`).
- El worker comprueba cada día las ofertas en `approved` y `cv_ready` (tarea `check_open`).
- `get_search_titles` alimenta el skill `broaden-search`: el agente propone títulos y solo con el
  OK del usuario los añade a `preferences.roles` (editando el perfil y con `cai profile import`) o a
  las `search_urls` de una plataforma (`save_source`).

### Segundo plano y cola de encargos (fase 19)

Los botones de la UI (ADR-024) tienen un desplegable con **«En segundo plano»** y **«Dejar para mi
próxima sesión»** (ADR-032). Ninguno de los dos tiene herramienta para lanzarlo: un agente no se
lanza a sí mismo.

- **En segundo plano** (`POST /agent/runs`, solo la UI): `process-jobs`, `assess-fit` y
  `generate-cv`. El worker lanza `launch.headless` del manifiesto con la orden y **solo las
  herramientas MCP de la acción** (`agent_launch.ACTIONS[...].background`), su skill, los
  subagentes y la lectura de `docs/`; el resto de herramientas de esta tabla se le **deniegan**
  explícitamente. La orden añade: «no preguntes; si necesitas al usuario, termina con líneas
  `PREGUNTA:`»; esas líneas dejan la ejecución en `needs_user` y la UI ofrece «Contestar en
  terminal» (en las demás, «Abrir en terminal»), que retoma la misma sesión. `generate-cv` solo va en segundo
  plano si a la oferta no le faltan obligatorias o si todas están marcadas «No la tengo».
  Fase 24.5: con Claude Code, el techo va en la orden; con OpenCode, en una configuración propia
  de la ejecución (`services/agent_run_config.py`) que solo enciende esas herramientas, el skill y
  los roles de la acción. `generate-cv` no va en segundo plano con OpenCode (sus roles leen
  ficheros). Si el agente de la acción no puede, `GET /agent` propone otro en
  `background_agent.suggested` y `suggested_name`. Cada ejecución guarda su agente, su formato de
  salida, `run_config` y el uso que informe el agente (`usage`: desde la fase 25.4, `input_tokens`, `output_tokens`, `cached_tokens`, `turns`, `duration_ms` y `cost_usd`, todas opcionales).
- **Cola de encargos** (`POST /agent/requests`, solo la UI): guarda la orden de cualquier acción.
  Tu próxima sesión la ve en `get_status` (`agent_requests`) y con el skill `handle-requests`
  (`list_agent_requests` → sigue el `prompt` → `complete_agent_request`). Un encargo que no se hizo
  no se cierra.

### Agentes (fase 24.1, solo CLI y API)

Sin herramienta MCP, a propósito: son para la persona y la UI, no para el agente (ADR-037).

| Comando | Qué hace |
|---|---|
| `cai agents list [--json] [--refresh]` | Los agentes de `.agents/manifest.yaml` con `info`, `capabilities`, `models` (por nombre, presets, ejemplo y el modelo de los subagentes), `enabled`, `config`, `installed`, `version` y `detect_error`. Con `--json`, también `launchable`, `preferences` y `effective` (fase 24.4: el agente, el modelo, el motivo y si se puede lanzar, por acción, en terminal y en segundo plano). `GET /agent/agents` devuelve lo mismo. La detección se guarda en caché (5 min; 30 s si no está instalado); `--refresh` la repite |
| `cai agents doctor [--refresh]` | Texto: qué agentes tienes, cuál se usaría hoy y por qué, si hay segundo plano y qué falta para los demás. Fase 24.6: sección «Modelos locales (Ollama)» (lo mismo que `GET /agent/local-models`): si responde, sus modelos con parámetros, contexto y si admiten herramientas, y avisos de contexto bajo (< 32 768) o de un modelo pequeño elegido para `generate-cv`. Solo `/api/version`, `/api/tags` y `/api/show` |
| `cai agents doctor --tokens` | Fase 24.2: tokens estimados (4 caracteres por token) de `AGENTS.md` y de cada skill y rol, y lo que cuestan una valoración y un CV. Marca los skills de más de 6 000 |
| `cai agents sync` / `cai agents check` | Regeneran o comprueban la configuración generada (`scripts/sync_agents.py`) |

**Elegir agente y modelo (fase 24.4, solo la UI).** `PUT /agent/preferences` guarda (sustituye
todas) las preferencias: `default_agent`, `agents` (`{agente: {model | preset}}`) y `actions`
(`{acción: {agent, model | preset}}`). Se validan sin red: el agente tiene que tener `launch`, el
preset existir y el modelo tener caracteres seguros, no empezar por `-` y, si el agente tiene
`models.pattern`, cumplirlo (OpenCode: `proveedor/modelo`); si no, 422 con el `field` que falla.
`POST /agent/launch` y `POST /agent/runs` aceptan `agent`, `model` y `preset` para una sola
ejecución. La precedencia (botón > acción > por defecto > `CAI_AGENT` > el primero instalado) y las
comprobaciones por capacidad y por nivel viven en `services/agent_prefs.py`. El modelo va con
`models.flag` (o el preset) justo detrás del programa (o donde diga `{model}` en la orden de
segundo plano, fase 24.5), en terminal y en segundo plano. El agente
lanzado recibe `CAI_CLIENT_NAME=<agente>`.

**Niveles de gasto (fase 24.6, solo la UI).** `GET /agent/tiers` devuelve los tres niveles
(`economy`, `balanced`, `max`) con el agente y el modelo de `process-jobs`, `assess-fit`,
`review-replies` y `generate-cv`, si están editados (`custom`), si coinciden con tus preferencias
(`active`), avisos (`notes`) y `can_undo`. `PUT /agent/tiers/{nivel}` guarda un nivel (se valida
como las preferencias); `POST /agent/tiers/{nivel}/reset` vuelve a la propuesta;
`POST /agent/tiers/{nivel}/apply` pone sus acciones en tus preferencias por acción y guarda las de
antes; `POST /agent/tiers/undo` las devuelve.

### Comandos de matching y worker (solo CLI)

| Comando | Qué hace |
|---|---|
| `cai worker [--once] [--interval S] [--json]` | Ejecuta la cola de tareas (`score_job`, `rescore_all`, `run_source`, `poll_email`, `expire_summaries`, `check_open`…) y, en primer plano, la ingesta diaria de las fuentes a la hora de `connectors.daily_at` (al arrancar, también las que no corrieron desde la última hora programada), la caducidad diaria de los resúmenes y la lectura de alertas cada `email_alerts.poll_minutes` (si hay IMAP o correos en `data/inbox/`). Desde la fase 19, en un hilo aparte, las ejecuciones en segundo plano de `agent_runs`: de una en una o, desde la 25.4, hasta `background_runs.max_parallel` a la vez (ADR-038). Log legible en consola y en `data/logs/worker.log`. `--once` vacía la cola (también las de `agent_runs`, en `agent_runs` del JSON) y termina (código 1 si alguna falla) |
| `GET /agent/costs`, `GET`/`PUT /agent/assess-threshold`, `GET /jobs/{id}/costs` (API de la UI) | Fase 25.4: coste por acción, agente y modelo (7 y 30 días), umbral de «Evaluar encaje» en segundo plano y coste de una oferta. Sin herramienta MCP ni comando: son para la UI, como `POST /agent/runs` |
| `cai jobs signals --recompute [--json]` | Fase 25.3: recalcula las señales de oferta dudosa de todas las ofertas (tras editar `config/doubtful_patterns.yaml` o `doubtful` de `config/policies.yaml`). Devuelve `jobs`, `with_signals` y `counts` por señal. No cambia el score. Sin herramienta MCP: se calculan solas al extraer |
| `cai match rescore [--json]` | Recalcula ya los matches desfasados de las ofertas abiertas (tras instalar el extra `matching` o editar `config/policies.yaml`) y cierra las de triaje que no pasan los filtros. Devuelve `scored` y `closed` |
| `cai eval matching [--profile RUTA] [--no-seed] [--no-embeddings] [--json]` | Precision, recall y F1 con el umbral actual y por umbral sobre `evals/matching/*.jsonl` (perfil de demo) y `data/evals/*.jsonl` (tu perfil). Guarda el informe en `data/evals/reports/` |
| `cai demo seed [--dir data-demo] [--force] [--eval-cv] [--json]` | Crea una carpeta de datos ficticia (fase 12.1, ADR-020): perfil demo, 60 ofertas, 8 semanas de historial y 2 CVs. Nunca escribe en `data/`. `--eval-cv` añade los 10 casos de `evals/cv/` aprobados y sin CV (en una demo existente, solo los que falten). `--json` devuelve `data_dir`, `jobs`, `events`, `by_stage`, `by_source`, `cvs`, `pdf_engine` y `warnings`. Sin herramienta MCP: no es para el agente |
| `cai eval cv [--agent NOMBRE] [--min-coverage 0.8] [--json]` | Comprueba los CVs guardados de los casos de `evals/cv/` (solo en la demo): evidencias, skills, skills básicas, una página, maquetación (fase 25.5: sin avisos de maquetación en el render seleccionado o, si no hay, el último; uno anterior a la 25.5 no los tiene), cobertura, idioma y verificación. Un caso sin CV es «pendiente». Guarda el informe en `evals/reports/` de la carpeta de datos (`evals/README.md`) |
| `cai eval compat --agent NOMBRE [--model M \| --preset P] [--timeout MIN] [--import] [--approve] [--json]` | Fase 24.6: la matriz de compatibilidad sobre su propia demo (`data-demo-compat-<agente>-<modelo>/`). Lanza el agente en segundo plano para `process-jobs`, `assess-fit` y `generate-cv`, y aprueba las 5 ofertas y marca las skills ausentes solo en esa demo. Mide la extracción (11 campos), las valoraciones, `eval cv`, el tiempo, los turnos y los tokens. Guarda `evals/compat/results/<fecha>-<agente>-<modelo>.json` y regenera `evals/compat/REPORT.md`. Si un paso no tiene segundo plano, imprime los pasos manuales; `--approve` aprueba y `--import` mide lo hecho a mano. Lanza tu agente: sin herramienta MCP |

### Fuentes: empresas objetivo y portales (fase 09, solo CLI)

Las usa la persona (CLI o página «Fuentes → Empresas objetivo» de la UI). `cai sources list` es desde la 09b la
herramienta `list_sources` (tabla de arriba); las plataformas `agent_browse` se ven y se activan en
la página «Fuentes → Plataformas».

| Comando | Qué hace |
|---|---|
| `cai sources add --kind K --name N [--slug S] [--region global\|eu] [--language L] [--query Q] [--where W] [--province P] [--country C] [--lang ES\|EN] [--remote-only] [--keywords a,b] [--json]` | Añade una fuente. ATS (`greenhouse`, `lever`, `ashby`, `personio`, `teamtailor`, `workable`, `smartrecruiters`, `recruitee`): `--slug` del tablero; la empresa queda como objetivo (`companies.watchlist`); `--region eu` solo en Lever y `--language` solo en Personio. Portales (`infojobs`, `adzuna`, `manfred`, `freehire`): `--query`; `--lang` en Manfred; `--country` y `--remote-only` en freehire. Error `exists` si ya está |
| `cai sources list [--kind K] [--json]` | `{sources: [SourceView], agent_browse}`: tipo, nombre, `config` (sin secretos), `active`, `keys_missing`, `browse`, `last_run_at` y `last_run` (encontradas, tras filtros, nuevas, errores), y los límites de la búsqueda con navegador |
| `cai sources test ID \| --kind K --name N … [--json]` | Descarga y aplica el filtro previo sin guardar nada: `found`, `after_filters`, `message` («12 ofertas encontradas, 3 tras filtros»), ofertas con `passed` y `reason`, y `errors`. Código 1 si la fuente falla |
| `cai capture token [--json]` | Genera (o rota) el token del botón «Enviar a CandidatAI» y lo muestra una vez; en `data/capture_token` solo queda su sha256. Con `--json`: `{token, extension_id}` |
| `cai alerts poll [--json]` | Lee ya las alertas nuevas (IMAP en solo lectura y `data/inbox/`, fase 09b) y da de alta sus ofertas: completas si el portal se deja descargar, si no como resumen en `pending_detail`. `EmailPollResult` con `messages`, `found`, `created`, `summaries`, `existing`, `job_ids` y `errors` |
| `cai alerts list [--json]` | Ofertas resumen (`AlertList`): título, empresa, ubicación, plataforma, URL, `expires_at` y prefiltro (`prefilter_passed`, `prefilter_reason`), primero las que pasan |
| `cai alerts expire [--json]` | Cierra con `expired` los resúmenes sin completar más antiguos que `email_alerts.summary_expire_days` |
| `cai sources run [ID] [--json]` | Ejecuta ya una fuente (o todas las activas) y guarda lo nuevo en `pending_extraction`. `{runs: [SourceRunResult]}` con `created`, `existing`, `duplicates`, `job_ids` y `errors` |
| `cai sources enable ID` / `disable ID` | Activa o pausa una fuente en la ingesta diaria |
| `cai sources discover --file F [--add] [--json]` | Fase 16 (y 25.1): busca el tablero de Greenhouse, Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters o Recruitee de cada empresa del fichero (una por línea; `Nombre \| slug` fuerza un slug) por sus APIs públicas. `DiscoverResult`: por empresa, `tried`, `hits` (`kind`, `slug`, `region`, `board_name`, `jobs_count`, `sample_titles`, `confidence`: `confirmed`/`probable`/`doubtful`, `existing_source_id`, `add_command`), `errors` y `added_source_ids`. Con `--add`, da de alta las `confirmed` y `probable` que faltan. Sin herramienta MCP |
| `cai sources linkedin-public status [--json]` | Fase 22 (ADR-033): estado de la búsqueda pública de LinkedIn sin sesión. `LinkedInPublicView`: `enabled`, `fetch_detail`, búsquedas que lanzará (`searches`) e ignoradas (`ignored`), `blocked_at`, `next_run_at`, `last_run` y `limits` |
| `cai sources linkedin-public run [--json]` | La ejecuta ya si está activada y le toca (una vez al día; días sin ejecutar tras un bloqueo). `LinkedInPublicRunResult` con `skipped`, `blocked`, `requests`, `found`, `after_filters`, `created`, `summaries`, `existing`, `job_ids` y `errors`. Apagada: `not_allowed`. Código 1 si LinkedIn la bloquea |

La búsqueda pública de LinkedIn **no se activa por la interfaz para agentes**: no hay herramienta
MCP ni comando para encenderla; solo la UI (`POST /sources/linkedin-public/settings` con
`confirm_risk`). Un agente no debe llamar a esa API.

### Candidatura asistida (fase 11): sin herramientas, a propósito

Rellenar y enviar formularios de candidatura no está en la interfaz para agentes: no hay
herramienta MCP ni comando `cai … --json`. Se desencadena solo desde la UI (POLICIES §5) y un test
comprueba que la CLI, el servidor MCP y `agent_interface` no importan el servicio, el token ni el
envío. El agente prepara el paquete (`save_application_answers`, la carta) y el usuario hace el
resto en la ficha.

## Errores

Mismo JSON por los dos canales (por MCP, con `isError: true`; por CLI, con código de salida 1):

```json
{"ok": false, "error": {"type": "validation_error",
  "message": "Entrada no válida (1 error): extraction.seniority.",
  "details": [{"field": "extraction.seniority", "received": "sr",
               "reason": "Debe ser uno de: intern, junior, mid, senior, lead, unknown.",
               "expected": "uno de: intern, junior, mid, senior, lead, unknown",
               "hint": null}]}}
```

Cada detalle (fase 24.2, para que un modelo pequeño acierte al segundo intento):

- `field`: dónde, como path con puntos desde la raíz de la entrada
  (`content.experience.2.bullets.0.evidence.1`). Las comprobaciones del contenido del CV, la carta
  y las respuestas usan el mismo formato (en la API de la UI, sin el prefijo `content.`);
- `received`: el valor recibido como texto, recortado a 80 caracteres;
- `reason`: el problema;
- `expected`: lo que se esperaba, corto (tipo, valores permitidos, longitud), o `null`;
- `hint`: cómo arreglarlo, o `null`. Hoy: campo obligatorio (y `cai schema <nombre>`), campo que
  no existe (el más parecido y los válidos de ese objeto), valor de una enumeración casi bien
  escrito, `language` con el nombre del idioma en vez de `es`/`en`, texto vacío, skill que no está
  en el perfil (el nombre tal cual del perfil, sin traducir) y evidencia o id inexistente (los 5
  más parecidos del perfil).

**Ningún error devuelve más de 80 caracteres seguidos de la entrada** (ni en el valor, ni en el
motivo, ni en el path de una clave larga): puede ser texto no confiable que el agente volvería a
leer. Las pistas solo citan el esquema y el perfil, nunca la oferta. Corregir y reintentar lo hace
el agente (los roles: solo los campos de `field`, como mucho dos veces); la app no reintenta.

| `type` | Cuándo |
|---|---|
| `validation_error` | La entrada no cumple el esquema. `details` lista cada campo, el valor recibido (como texto, recortado), el motivo, lo esperado y una pista |
| `not_found` | No existe la oferta, aún no tiene extracción, no hay perfil importado, no existe el CV o la plantilla |
| `invalid_transition` | El evento no es válido en la etapa actual de la oferta |
| `invalid_request` | El servicio rechaza la petición (URL de LinkedIn, evento reservado…) |
| `not_allowed` | La búsqueda con navegador no está permitida ahí: activar LinkedIn desde el agente, o anotar ofertas o recorridos de una plataforma desactivada (403 en la API) |
| `database_not_ready` | Falta `cai db upgrade` |
| `pdf_unavailable` | No hay LibreOffice ni Word para convertir a PDF (`cai doctor`) |
| `pdf_failed` | La conversión a PDF falló o superó `cv.pdf_timeout_seconds` |
| `invalid_file` | Solo CLI: `--file` fuera de `data/tmp/`, ilegible, sin ningún JSON reconocible (ni en un bloque de código) o con claves que no se esperan |
| `unknown_tool` | Solo MCP: la herramienta no existe |
| `internal_error` | Fallo inesperado; el detalle queda en `data/logs/` |

## Esquemas que rellena el agente

Definidos en `app/schemas/llm_io.py`. Estos son los campos; los tipos exactos, en Pydantic.
El JSON Schema exacto de cada uno, con un ejemplo, lo da `get_schema` (`cai schema <nombre>
--json`): es la fuente para el agente; esta sección explica el porqué de los campos.

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
# Fase 25.3 (opcionales; null si el texto no lo dice; vacíos no se guardan):
contract_type: permanent|fixed_term|freelance|unknown | null   # temporal, por obra, sustitución…
hiring_entity: str | null              # quien contrata si el texto lo nombra (con agencia, el cliente)
is_agency: bool | null                 # la publica una agencia, consultora de selección, ETT o headhunter
mentions_ai_screening: bool | null     # IA o test automático antes de hablar con una persona
```
Regla: lo que no está en el texto es `null`/`unknown`. No se infiere.
Validación: todos los campos son obligatorios salvo `injection_excerpt` (por defecto `null`, y solo
admitido si `injection_suspected` es true) y los cuatro de la fase 25.3 (por defecto `null`); no se aceptan campos extra; `responsibilities` admite
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
  bullets: [{text: str, evidence: [str]}]   # evidence: ids citables del perfil: "exp-acme/a2", "exp-acme", "prj-x", "edu-x", "cert-x"
}]
projects: [{project_id: str, bullets: [{text, evidence}]}]
skills: [{group: str, items: [str]}]   # solo skills del perfil, con su nombre (o un alias de config/skill_aliases.yaml); básicas como "conocimientos de X" / "basic knowledge of X"
education_ids: [str]
certification_ids: [str]
extra_sections: [{section_id: str, item_ids: [str]}]   # desde la 08.3; items del perfil tal cual
languages: [{language: str, level: str}]
include_regional_language: bool       # true: el idioma regional del perfil va en `languages`; false: el código lo quita
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
