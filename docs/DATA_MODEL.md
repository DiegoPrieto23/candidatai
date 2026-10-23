# Modelo de datos

SQLite en `data/candidatai.db`, modo WAL. SQLAlchemy 2.0 + Alembic. Todas las fechas en UTC
(`datetime` con zona); la UI convierte a Europe/Madrid.

## Tablas

### `sources`
Origen de ofertas.
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| kind | str | `manual_url`, `manual_text`, `greenhouse`, `lever`, `ashby`, `infojobs`, `adzuna`; desde la fase 25.1, también `personio`, `teamtailor`, `workable`, `smartrecruiters`, `recruitee`, `manfred` y `freehire`; desde la fase 09b, también `email_alerts`, `browser_capture` y `agent_browse`; desde la fase 22, `linkedin_public` (una sola fila, se crea al activarla) |
| name | str | Etiqueta legible |
| config | JSON | Parámetros del conector, validados por tipo (`app/schemas/sources.py`): ATS `{slug, region, title_keywords, website?}` (`website`: origen de la web de la empresa, solo para su logo) (`region: eu` solo en Lever; Personio, además, `language` si se fija); InfoJobs `{query, province, since, title_keywords}`; Adzuna `{query, where, country, max_days_old, title_keywords}`; Manfred `{query, lang, title_keywords}`; freehire `{query, country, remote_only, title_keywords}`; plataforma `agent_browse` `{platform, search_urls, priority, access, allow_agent_browsing, max_offers, notes}` (el nombre va en `name`; `priority` es un puesto único 1…N, sin empates, desde la fase 27.3); `linkedin_public` `{enabled, fetch_detail, enabled_at, blocked_at}` (fase 22: las búsquedas salen de la plataforma LinkedIn). Nunca claves: van en `.env` |
| active | bool | Las activas con conector entran en la ingesta diaria del worker |
| last_run_at | datetime? | Última ejecución del conector que no falló entera. Si falla, no avanza: el worker la vuelve a encolar al arrancar (el fallo queda en `source_runs`) |

### `source_runs` (fase 09)
Una fila por ejecución de una fuente; la usan los conectores y, desde la 09b, alertas y navegación.
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| source_id | FK sources | |
| actor | str | `system` (worker), `user` (CLI o UI), `agent` (09b) |
| started_at / finished_at | datetime | |
| found | int | Ofertas que devolvió la fuente |
| after_filters | int | Las que pasaron el filtro previo de título y ubicación |
| created | int | Ofertas nuevas guardadas (en `pending_extraction`) |
| completed | int | Resúmenes completados (09b) |
| errors | JSON | `[{code, message, item?}]`: fallo de la fuente o de una oferta suelta |

### `companies`
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| name | str | Como aparece |
| normalized_name | str UNIQUE | Minúsculas, sin forma jurídica (S.L., S.A., GmbH, Inc…) ni signos |
| ats_kind / ats_slug | str? | Si la empresa está en la lista de seguimiento |
| watchlist | bool | Empresa objetivo |

### `jobs`
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| source_id | FK sources | |
| company_id | FK companies | |
| external_id | str? | ID en la fuente, si existe. Índice (`source_id`, `external_id`): un conector reconoce así lo ya visto |
| url | str | |
| title | str | Tal cual |
| location_raw | str? | Tal cual |
| raw_text | text | Texto limpio de la oferta. **No confiable** |
| risk_flags | JSON | Riesgo de inyección detectado por el código: `hidden_text`, `injection_phrase`… |
| signals | JSON | Observaciones que no son riesgo (fase 16, ADR-028): `possibly_closed`, `liveness`, `open_confirmed`, `reposted`; y de oferta dudosa (fase 25.3): `salary_range_wide`, `employer_hidden`, `fixed_term`, `stale_repost`, `ai_screening`. Ver §Fase 16 |
| fingerprint | str UNIQUE | Ver abajo |
| duplicate_of | FK jobs? | Si se detecta como duplicado difuso |
| posted_at | datetime? | |
| first_seen_at | datetime | |

**Huella:** `sha256(normalized_company | normalized_title | normalized_location)`, donde
`normalized_title` quita seniority genérica entre paréntesis, emojis, dobles espacios y pasa a
minúsculas. Además, un chequeo difuso (rapidfuzz, umbral en `config/policies.yaml`) entre ofertas
de la misma empresa en los últimos 60 días marca `duplicate_of`. Excepción (fase 09): dos ofertas
de la misma fuente con conector y `external_id` distintos nunca son duplicado difuso entre sí (el
ATS ya dice que son publicaciones distintas).

### `job_extractions`
Una fila por extracción; la vigente es la más reciente.
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id | FK jobs | |
| schema_version | int | Versión del esquema `JobExtraction` |
| data | JSON | Validado con `JobExtraction` (ver `AGENT_INTERFACE.md`) |
| created_at | datetime | |

### `profile_versions`
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| data | JSON | Validado con `CandidateProfile`, importado desde `data/profile.yaml` |
| content_hash | str | sha256 del JSON canónico. Importar un contenido igual al de la versión vigente no crea versión; volver a uno anterior sí (índice, no único) |
| created_at | datetime | |

### `matches`
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id / profile_version_id | FK | |
| extraction_id | FK job_extractions? | Extracción con la que se calculó. Si hay una más reciente o una versión de perfil más reciente, el match está desfasado |
| scoring_key | str? | Huella de la configuración de puntuación: versión del scorer, `scoring` (sin `triage_threshold`) y `hard_filters` de `policies.yaml`, alias de skills y modelo de embeddings (o ninguno). Si cambia, el match está desfasado |
| hard_filters | JSON | `{passed: bool, failures: [{filter, reason}]}` |
| score | int 0-100 | Calculado por código |
| breakdown | JSON | `ScoreBreakdown`: componentes (valor, peso, peso efectivo, puntos), skills cubiertas (con nivel) y ausentes, similitud, preferencias y notas |
| assessment | JSON? | `FitAssessment` del agente: veredicto, motivo, riesgos y preguntas |
| created_at | datetime | |

Una fila por cálculo: el vigente es el último de la oferta. Los anteriores se conservan (la
valoración del agente puede venir de uno anterior: `assessment_stale`).

### `documents`
Contenido de un documento (lo que escribe el agente). La presentación va en `document_renders`.
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id / profile_version_id | FK | |
| kind | str | `cv`, `cover_letter` (fase 08c), `answers` |
| language | str | `es`, `en` |
| content | JSON | `CvContent`; en las cartas, `{letter: CoverLetterContent, instructions: {brief, preferences, max_words}}` (las indicaciones vigentes al guardar, respaldo de `user`); o `ApplicationAnswers` (`kind = answers`, fase 10.3). Con referencias a evidencias |
| verification | JSON? | `{passed, issues[]}` del verificador |
| edited_by_user | bool | Editado por el usuario en la UI (respuestas; cartas desde la 08c). Cada edición es un documento nuevo: el anterior se conserva y manda el último |
| created_at | datetime | |

### `document_renders`
Cada combinación de contenido + plantilla + opciones que se ha generado. Crear uno nuevo no
cambia `documents` ni necesita al agente.
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| document_id | FK documents | |
| template_id | str | Id de la plantilla (integrada o del usuario) |
| template_hash | str | Hash de los ficheros de la plantilla al renderizar, para saber si cambió después |
| options | JSON | `CvRenderOptions` ya resueltas (plantilla y de dónde sale, foto sí/no, color, páginas, secciones, tamaño) y lo que se supo de la oferta (ATS, países, sector, idioma) |
| docx_path / pdf_path | str? | Relativos a `data/` (`cvs/<job_id>/<document_id>/<render_id>/CV-<Nombre>.pdf`); `docx_path` vacío en el motor html |
| pages | int | |
| keyword_coverage | JSON | Keywords de la oferta presentes y ausentes en el PDF |
| warnings | JSON | `[{code, message, page?, fix?}]`: `too_long`, `not_ats_friendly`, `font_substituted`…; desde la fase 25.5, los de maquetación del PDF (`orphan_heading`, `large_gap`, `footer_overlap`, `nearly_empty_last_page`, `text_layer`) con la página y cómo arreglarlo (`fix`: `template` o `content`). Los demás no llevan `page` ni `fix`. Sin migración |
| selected | bool | El que se usará al enviar; como mucho uno por documento. El primer render sin `too_long` queda seleccionado; después lo cambias en la UI (`select_render`, sin evento: no cambia la etapa) |
| created_at | datetime | |

### `applications`
Proyección del estado de candidatura para consultas rápidas; se recalcula desde `events`.
| Columna | Tipo | Notas |
|---|---|---|
| job_id | PK/FK | |
| stage | str | Ver etapas |
| channel | str? | `ats_form`, `email`, `linkedin_manual`, `portal_manual` |
| render_id | FK document_renders? | Render del CV enviado |
| applied_at | datetime? | |
| last_event_at | datetime | |

### `events` (fuente de verdad)
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id | FK jobs | |
| type | str | Ver catálogo |
| actor | str | `system`, `user`, `agent` |
| agent_name | str? | Qué agente lo registró, si el cliente MCP lo informa (`claude-code`, `codex`…) |
| payload | JSON | Datos del evento |
| occurred_at | datetime | Cuándo pasó (puede ser pasado) |
| recorded_at | datetime | Cuándo se registró |

### `tasks`
Cola de trabajo del worker (sin Redis).
`id, kind, payload JSON, status (queued|running|done|failed), attempts, run_after, last_error`.

| `kind` | Lo encola | Hace |
|---|---|---|
| `score_job` `{job_id}` | `save_extraction` (con perfil) | Calcula el match vigente |
| `run_source` `{source_id}` | `cai worker` a la hora de `connectors.daily_at`, y al arrancar para las fuentes que no corrieron desde la última hora programada | Ejecuta el conector (`ingestion/service.run_source`). Un fallo de red, 5xx, 429 o interno queda en `source_runs` y la tarea se reintenta; un 404 o un formato inesperado no. Los portales sin claves no se encolan. Al arrancar, las tareas que quedaron `running` vuelven a la cola |
| `poll_email` `{}` | `cai worker` cada `email_alerts.poll_minutes`, y al arrancar, si hay IMAP configurado o correos en `data/inbox/` | Lee las alertas nuevas (`ingestion/email/service.poll_email`). Si el buzón falla por la red, queda en `source_runs` y se reintenta |
| `expire_summaries` `{}` | `cai worker` cada día con la ingesta y al arrancar | Cierra con `expired` los resúmenes más antiguos que `summary_expire_days` |
| `rescore_all` `{}` | `cai profile import` con versión nueva | Recalcula los matches desfasados de las ofertas abiertas con extracción y cierra las de triaje que ya no pasan los filtros (lo mismo que `cai match rescore`, sin cola) |
| `browser_open` `{}` | «Abrir navegador» (fase 11) | Abre el navegador persistente (`data/browser-profile/`), con una página de inicio para que inicies sesión en tus portales |
| `apply_fill` `{attempt_id}` | `prepare` (fase 11) | Rellena el formulario y para antes de enviar (`services/applier/service.run_fill`) |
| `apply_open` `{attempt_id}` | `prepare` en LinkedIn o en un portal de empleo | Solo abre la URL |
| `apply_fill_page` `{attempt_id, previous}` | «Rellenar esta página» (ADR-021) | Rellena la pestaña que tienes delante (el formulario de la empresa al que te llevó el portal) y para antes de enviar. Si es una página del portal o de LinkedIn, no toca nada y el intento vuelve a `previous` con el motivo |
| `apply_rescan` `{attempt_id}` | «Volver a revisar» | Vuelve a leer los campos y a capturar, sin rellenar nada |
| `apply_submit` `{attempt_id, token, consents}` | `confirm_submission` (solo la UI) | Consume el token, pulsa el envío, captura la confirmación y registra `applied` |
| `apply_focus` `{attempt_id}` | «Lo termino yo» | Trae la pestaña al frente y retira el bloqueo del envío |
| `check_open` `{job_id}` | `cai worker` cada día con la ingesta y al arrancar, para las ofertas en `approved` o `cv_ready` sin comprobación en `liveness.fresh_hours` (fase 16) | ¿Sigue abierta? (`services/liveness.check_job`). Un fallo de red da `unknown`, no se reintenta |
| `run_linkedin_public` `{}` | `cai worker` cada día con la ingesta y al arrancar, solo si la búsqueda pública de LinkedIn está activada y le toca (fase 22) | `ingestion/linkedin_public.run`. Nunca se reintenta: un bloqueo de LinkedIn deja `blocked_at` y no se vuelve a intentar en `block_cooldown_days` |
| `archive_application` `{job_id, event_id, cv_render_id, letter_document_id, letter_render_id, answers_document_id}` | `applied` o `applied_manually` (fase 13) | Copia lo enviado a `data/documentos/candidaturas/` (ver §Fase 13). Los ids se fijan al registrar el envío. Idempotente |

No se encola dos veces la misma tarea (mismo `kind` y `payload`) mientras siga en cola. Si falla,
vuelve a la cola con espera creciente; tras 3 intentos queda `failed` con `last_error`.
Las tareas del navegador (`browser_open` y `apply_*`) **no se reintentan** (POLICIES §5.4): si
fallan, quedan `failed`; si el worker se cierra mientras corren, al arrancar quedan `failed` y nunca
vuelven a la cola.

### `mcp_calls`
Auditoría de cada llamada a la interfaz para agentes:
`id, channel (mcp|cli), client_name?, tool, args_summary, job_id?, ok, error?, called_at`.
Nunca guarda texto crudo de ofertas ni datos del perfil en `args_summary`.

## Catálogo de eventos

| Tipo | Actor típico | Lleva a la etapa |
|---|---|---|
| `found` | system | `pending_extraction`, o `pending_detail` si `payload.detail_level = summary` (fase 09b) |
| `detail_captured` | user / system | `pending_extraction` (fase 09b) |
| `duplicate_detected` | system | `closed` |
| `extracted` | agent | `pending_triage` (si pasa filtros duros) |
| `hard_filter_failed` | system | `closed` (reabrible); `payload.failures` |
| `extraction_failed` | agent | se queda en `pending_extraction` |
| `injection_suspected` | system / agent | sin cambio; aviso visible en la UI |
| `closure_suspected` | system | sin cambio; la primera vez que una comprobación dice que la oferta puede estar cerrada (fase 16). `payload`: `reason`, `detail`. Nunca cierra la oferta |
| `scored` / `fit_assessed` | system / agent | sin cambio; `payload`: `match_id` y `score`/`passed` o `verdict` |
| `approved` | user | `approved` |
| `discarded` | user | `closed`; desde la UI, `payload.reason` (`skills`, `seniority`, `location`, `salary`, `company`, `closed` (ya no está publicada, fase 16), `other`) y `note` opcional (obligatoria con `other`) |
| `cv_generated` | agent | sin cambio; `payload.document_id` |
| `cv_rendered` | system / user / agent | `cv_ready` si el render no es `too_long` y su documento ya está verificado con `passed`; si no, sin cambio. `payload`: `document_id`, `render_id`, `template_id`, `too_long`. Solo lo registra el servicio de render |
| `cv_verified` | agent | `cv_ready` si `passed` y ese documento tiene un render sin `too_long`; `payload`: `document_id`, `passed` |
| `cv_rejected` | agent | sin cambio; `payload`: `document_id`, `blockers` |
| `cover_letter_generated` | agent / user | sin cambio; `payload`: `document_id`, `edited_by_user` (fase 08c) |
| `cover_letter_verified` | agent | sin cambio; `payload`: `document_id`, `passed`, `blockers` (fase 08c) |
| `application_prepared` | agent / user | sin cambio; `payload`: `document_id` (las respuestas, `kind = answers`) y `edited_by_user`. Solo en `approved` o `cv_ready` (fase 10.3) |
| `application_filled` | system | sin cambio; solo en `cv_ready`. Lo registra el worker al rellenar un formulario (fase 11); `payload`: `attempt_id`, `platform`, `status` (`ready` o `needs_user`), `filled` y `missing_required` |
| `applied` / `applied_manually` | user | `applied`; `payload.render_id` (el CV enviado: el render seleccionado del último CV, lo pone el código) y `channel` (`ats_form`, `email`, `linkedin_manual`, `portal_manual`; opcional). Desde la fase 11, el envío asistido lo registra el worker tras tu confirmación, con `channel: ats_form`, `attempt_id` y `evidence` (la captura de la página de confirmación, relativa a `data/`) |
| `reply_received`, `interview_scheduled`, `interview_done`, `test_assigned` | user | `in_process`. Desde la fase 10, los registra la ficha de proceso al crear una entrevista o una prueba (`payload.milestone_id`, `title`, `starts_at`) o al marcar una entrevista como hecha |
| `followup_sent` | user | sin cambio |
| `offer_received` | user | `in_process` |
| `rejected`, `withdrawn`, `expired`, `accepted` | user/system | `closed` |
| `reopened` | user | la etapa previa al cierre |
| `note` | cualquiera | sin cambio. Reprogramar o cancelar una entrevista o una prueba deja una `note` con `payload.milestone_id` (fase 10) |

La proyección vive en `services/pipeline.py`: `stage_for(events) -> Stage`, con tests que cubren
cada transición. Una transición no válida (p. ej. `applied` sin `cv_ready` ni `applied_manually`)
se rechaza con error claro.

## Ampliaciones de la fase 08c

- `document_renders` guarda también los renders de cartas (`options` = `CoverLetterRenderOptions`
  resueltas, `keyword_coverage` vacío, ficheros `Carta-<Nombre>.pdf|docx`). `selected` funciona
  igual: como mucho una carta seleccionada por documento.
- Tabla `cover_letter_briefs` (migración 0010): `job_id` (PK/FK), `instructions` (texto), `max_words` (int?),
  `updated_at`. Las indicaciones de la carta para esa oferta; no guarda historial (el documento
  copia las que usó).

## Ampliaciones de la fase 09b

Detalle y motivos en `docs/FUENTES_OFERTAS.md` §Modelo de datos.

- `jobs`: `platform` (str?, p. ej. `linkedin`), `detail_level` (`summary` | `full`) e índice
  único parcial sobre (`platform`, `external_id`) cuando ambos existen.
- Etapa nueva `pending_detail`, antes de `pending_extraction`. Desde ella se admiten
  `detail_captured`, `discarded`, `expired`, `duplicate_detected` (un resumen puede ser duplicado
  difuso de otra oferta), `injection_suspected` y `note`; no `scored`, `fit_assessed`,
  `application_prepared`, `rejected` ni `withdrawn`. Reabrir un resumen caducado lo devuelve a
  `pending_detail`. `detail_captured` es un evento reservado: `add_event` no lo acepta.
- Migración `0007`: `jobs.platform`, `jobs.detail_level` (por defecto `full`) y el índice único
  parcial; las ofertas anteriores quedan con `platform = null`.
- Tabla `source_runs`: ya la crea la fase 09 (migración `0006`); la 09b la reutiliza.
- Tabla `email_messages`: `message_id` (único), `source_id`, `received_at`, `jobs_found`,
  `processed_at`. Nunca guarda el cuerpo del correo.

## Ampliaciones de la fase 10

Migración `0008`. Detalle del seguimiento en `prompts/10.1-seguimiento.md`.

### `milestones`
Hitos con fecha de un proceso. Las entrevistas y las pruebas registran su evento; el resto no
cambia la etapa.
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id | FK jobs | |
| kind | str | `interview` (registra `interview_scheduled`), `test` (`test_assigned`), `deadline`, `other` (sin evento) |
| title | str | Por defecto, el tipo («Entrevista», «Prueba técnica»…) |
| starts_at / ends_at | datetime / datetime? | Sin fin: `calendar.default_duration_minutes` (60) en el calendario |
| all_day | bool | `starts_at` a las 00:00 de ese día en Europe/Madrid (`calendar.timezone`); con varios días, `ends_at` se guarda como las 00:00 del día siguiente al último (fin exclusivo, como en iCalendar) |
| location | str? | Lugar o enlace de la videollamada |
| notes | text? | |
| status | str | `scheduled`, `done` (entrevista: `interview_done`), `cancelled` (entrevista o prueba: `note`). No vuelve atrás |
| event_id | FK events? | El evento que registró al crearse |
| sequence | int | `SEQUENCE` del iCalendar: sube con cada cambio |
| created_at / updated_at | datetime | |
| prep_plan | json? | Fase 17. Plan de preparación de una entrevista (`save_interview_plan`): `dossier?` (nombre del fichero en `data/entrevistas/`), `blocks` (`date`, `minutes`, `topic`, `detail?`), `saved_at`, `agent_name` |
| prep_guide | json? | ADR-044. Guía de preparación en PDF (`save_interview_guide`): `file` (el PDF en `entrevistas/` de la carpeta de datos), `saved_at`, `agent_name` y `guide` (el contenido estructurado que maqueta la app) |
| debrief_notes / next_steps | text? / text? | Fase 17. Repaso de la entrevista (`save_interview_notes`). Aparte de `notes`, que es lo que anota el usuario |
| debriefed_at | datetime? | Cuándo se guardó el repaso |

Ni el plan ni el repaso registran eventos ni cambian `status` (ADR-029).

Si el evento no es válido en la etapa (p. ej. una entrevista antes de enviar), no se guarda el hito.
Editar la fecha de una entrevista o una prueba deja una `note` («reprogramada para el…»).

### `contacts`
`id, job_id, name, role?, email?, phone?, linkedin?, notes?, created_at`. Personas del proceso
(recruiter, hiring manager…). `role` es el cargo. Las herramientas para agentes solo devuelven el
nombre (`list_followups_due`), el cargo (`get_interviews`) y, desde la fase 18, el papel y la
referencia (`get_job_contacts`); el email, el teléfono, el LinkedIn y las notas, solo la UI.

Fase 18 (migración 0017):

| Columna | Tipo | Notas |
|---|---|---|
| relation | str? | Papel en el proceso: `referral` (referencia), `recruiter` o `hiring_manager` (responsable) |
| referral | str? | `requested` (referencia pedida) o `given` (dada). Marca, no evento: no cambia la etapa |
| referral_at | datetime? | Cuándo se puso la marca (se borra al quitarla) |
| network_contact_id | FK network_contacts? | La persona de tu red de la que sale («Añadir como contacto del proceso»). Si desaparece al reimportar, queda en `null` y el contacto sigue |

### Seguimientos y calendario
- **Seguimiento vencido**: oferta en `applied` con `followups.days_without_reply` días o más (10 por
  defecto, `config/policies.yaml`) desde el último `applied`/`applied_manually` o `followup_sent`.
- **Próximos**: hitos `scheduled` de ofertas abiertas desde las 00:00 de hoy (Madrid) hasta el
  final del último día de la ventana, más el
  `application_deadline` de la extracción vigente de las ofertas en `pending_triage`, `approved` o
  `cv_ready`.
- **Calendario**: `.ics` por hito y feed con los próximos sin límite de días (solo hitos
  programados de ofertas abiertas: lo cancelado o cerrado sale del feed) (RFC 5545, UTC, `UID`
  `milestone-<id>@candidatai.local` y `deadline-<job_id>-<fecha>@candidatai.local`).

### Embudo (fase 10.2)

Lo calcula `services/analytics.py` con consultas agregadas sobre `events` (sin tablas nuevas ni
índices: con 1 000 ofertas responde en unos 0,2 s). Cada oferta cuenta **una vez** por paso,
aunque se reabra, y el embudo es **acumulado**: una oferta que llega a un paso cuenta también en
los anteriores (un `applied_manually` sin aprobar antes cuenta como aprobada y triada), así que la
conversión nunca pasa del 100 %.

| Paso | La oferta tiene… |
|---|---|
| Encontradas (`found`) | cualquier oferta del periodo, salvo las cerradas por `duplicate_detected` sin `reopened` posterior (se cuentan aparte en `duplicates_excluded`) |
| Triadas (`triaged`) | `extracted` y ningún `hard_filter_failed`, o un `reopened` después del último (después en el orden de la proyección: `occurred_at` y, a igual fecha, `id`; lo mismo con `duplicate_detected`) |
| Aprobadas (`approved`) | `approved` |
| Enviadas (`applied`) | `applied` o `applied_manually` |
| Con respuesta (`replied`) | `reply_received`, `interview_scheduled`, `test_assigned`, `offer_received` o `rejected` con `occurred_at` igual o posterior al primer envío |
| Entrevista (`interview`) | `interview_scheduled` |
| Oferta (`offer`) | `offer_received` |
| Aceptadas (`accepted`) | `accepted` |

- **Periodo** (`since`): `jobs.first_seen_at` desde las 00:00 de ese día en Europe/Madrid.
- **Por fuente**: `jobs.source_id` (con `sources.kind` y `name`). **Por puesto**: `title_normalized`
  de la extracción vigente (la de mayor `id`); los 8 más frecuentes, «Otros» y «Sin extraer».
  **Por semana**: semana ISO de `first_seen_at` en Europe/Madrid (función SQLite `cai_iso_week`,
  registrada en `app/core/db.py`).
- **Tiempo hasta la primera respuesta**: días entre el primer envío y la primera respuesta (mediana
  y media, 1 decimal), sobre las ofertas con `applied`/`applied_manually` (las transiciones impiden
  responder sin enviar, así que coincide con el paso «Enviadas»). Sin respuesta: `awaiting_reply` (aún en `applied`) y `closed_without_reply`.
- **Por referencia** (fase 18): `given` si algún contacto del proceso tiene `referral = given`; si
  no, `requested` si alguno la tiene pedida; si no, `none`. Siempre los tres grupos. La marca no
  tiene fecha de corte: cuenta aunque se pusiera después del envío.
- **Motivos**: ofertas con `discarded` por `payload.reason` (`unspecified` si falta) y con
  `hard_filter_failed` por cada `payload.failures[].filter` (`json_each`).
- `cai_iso_week` y `json_each` son de SQLite: pasar a Postgres (ADR-002) exigiría reescribir esas dos
  expresiones.

### Calibración (fase 20)

«¿Acierta el score?»: `services/analytics.py` (`get_calibration`), sin tablas nuevas. Cuenta las
ofertas con `applied` o `applied_manually` (sin las cerradas por `duplicate_detected`) y, para
cada grupo, cuántas tuvieron respuesta y entrevista (los pasos del embudo), cuántas esperan
(`awaiting`: sin el paso «Con respuesta» y aún en `applied`), las dos tasas con su **intervalo de Wilson al 95 %**
y `low_data` si hay menos de `min_cases` enviadas (10 por defecto). Todo se mide en el **primer
envío** (`applied_at`, el primer `applied`/`applied_manually`):

| Desglose | Grupo de cada oferta |
|---|---|
| Score (`by_score`) | `matches.score` del último match con `created_at` ≤ envío; si no hay, del primero después (el score es código: no sabe del resultado). Tramos `< 60`, `60-74`, `75-84`, `≥ 85` y «Sin score» |
| Veredicto (`by_verdict`) | `payload.verdict` del último `fit_assessed` con `occurred_at` ≤ envío; uno posterior no cuenta (pudo escribirse sabiendo cómo fue). «Sin valorar» si no hay |
| Fuente (`by_source`) | `jobs.source_id` |
| Portal (`by_platform`) | `jobs.platform`; «Sin portal» si es `null` |
| Plantilla (`by_template`) | `document_renders.template_id` del render de `payload.render_id` del primer envío (el CV enviado); «Sin CV de la app» si no lo lleva |
| Carta (`by_cover_letter`) | Con carta si hay algún documento `cover_letter` con `created_at` ≤ envío |
| Referencia (`by_referral`) | Como en el embudo: `given`, `requested` o `none`, sin fecha de corte |
| Días hasta el envío (`by_days_to_apply`) | `applied_at - first_seen_at` en días: `0-1` (< 2, también negativos: un envío con fecha anterior al alta), `2-3` (< 4), `4-7` (< 8) y `8 o más` |

- **Periodo** (`since`): primer envío desde las 00:00 de ese día en Europe/Madrid (no
  `first_seen_at`, como el resto del embudo: en una retrospectiva importa cuándo enviaste).
- Score, veredicto, carta, días y referencia no son independientes (las de más score suelen
  llevar carta o referencia): la calibración muestra correlaciones, no causas. Por eso es
  orientativa y nunca cambia pesos ni filtros (`evals/matching/README.md` §Calibración).
- Con 1 000 ofertas, cada una con matches, veredicto, carta y CV, responde en unos 0,15 s (el
  test, `tests/test_funnel_performance.py`, exige menos de 1 s).

## Ampliaciones de la fase 11

### `application_attempts`
Un intento de candidatura asistida (migración 0011). El estado de la oferta sigue saliendo de los
eventos; esta tabla guarda lo que necesita la pantalla de revisión.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id | FK jobs | |
| platform | str | `greenhouse`, `lever`, `ashby`, `generic`, `linkedin`, `board` (portal de empleo), `unknown` (por la URL y, si no, mirando la página) |
| mode | str | `fill` (rellenar y revisar) u `open` (LinkedIn o un portal: solo abrir; con «Rellenar esta página» pasa a `fill`) |
| url | str | La del formulario (Lever `…/apply`, Ashby `…/application`) |
| status | str | `queued` → `filling` → `ready` / `needs_user` / `failed`; `submitting` → `submitted` / `submit_unconfirmed` / `submit_failed` / `needs_user`; `manual` («Lo termino yo» o `open`), `manual_done` y `cancelled` (otro intento lo sustituye) |
| fields | JSON | `[FieldReport]`: `marker`, `label`, `control`, `kind`, `required`, `status` (`filled`, `empty`, `needs_user_input`, `sensitive`, `consent`, `skipped`, `error`), `source`, `value` (recortado) y `note` |
| warnings | JSON | `[{code, message}]`: `invisible_captcha`, `submit_blocked`, `no_resume_field`, `unused_answers`, `no_answers`, `missing_required`, `submit_button` (qué botón se pulsará), `no_submit_button`, `form_opened` (se pulsó el botón que abre el formulario), `possible_duplicate` (un intento anterior ya pulsó «Enviar»), `captcha`, `antibot`, `login`, `no_form`, `form_error`, `no_evidence` |
| screenshot_path / confirmation_path | str? | Relativos a `data/` (`applications/<job_id>/<intento>/review.png`, `confirmation.png` o `after-submit.png`) |
| token_hash | str? | SHA-256 del token de envío; el valor nunca se guarda aquí |
| token_expires_at / token_used_at | datetime? | Un solo uso; caduca a los `applier.token_ttl_seconds` |
| error | str? | Por qué se paró o falló |
| created_at / updated_at | datetime | `updated_at` es la versión revisada: si cambia, la confirmación pide revisar otra vez |

Un campo obligatorio cuenta como **pendiente** si no tiene valor y no es un consentimiento: los
consentimientos obligatorios los aceptas tú al confirmar el envío y se marcan justo antes de pulsar.

Tras usar la confirmación (`token_used_at`), el clic pudo darse: el intento ya no vuelve a `ready`
(«Volver a revisar» se rechaza) y cualquier fallo posterior al clic queda `submit_unconfirmed`. Para
enviar otra vez hay que preparar un intento nuevo, que lleva el aviso `possible_duplicate`. El token
viaja una vez en el `payload` de `apply_submit` y se borra de ahí al consumirlo o rechazarlo.

Registro por paso en `data/logs/applier/<intento>.jsonl` (sin valores personales).

## Ampliaciones de la mejora «seguimiento y plataformas»

### `user_prompts`
Avisos para que el usuario haga algo en el navegador (migración 0012): un captcha, una
comprobación anti-bot o un login. Los crea el agente (`request_user_action`) al buscar ofertas o
el worker cuando una candidatura asistida se para. La UI los enseña en un pop-up.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| kind | str | `captcha`, `anti_bot`, `login_required` |
| message | text | Qué hacer y dónde |
| url | str? | La página afectada |
| source_id | FK sources? | La plataforma (búsqueda con navegador) |
| attempt_id | FK application_attempts? | El intento (candidatura asistida): con «Ya está» se encola `apply_fill_page` |
| status | str | `pending` → `done` («Ya está») / `skipped` («Saltar») / `expired` (pasó `expires_at` o lo sustituyó otro aviso de lo mismo) |
| created_at / expires_at / answered_at | datetime | Por defecto caduca a los 5 minutos |

## Ampliaciones de la fase 13 (sin tablas nuevas)

Ficheros en `data/` (gitignored), fuera de la BD:

| Ruta | Qué es |
|---|---|
| `contexto/estilo-redaccion.md` | Cómo escribe el candidato (tono, palabras que usa y evita, ejemplos) |
| `contexto/perfil-conductual.md` | Cómo trabaja, fortalezas, puntos a mejorar, tests de personalidad |
| `contexto/criterios.md` | Deal-breakers y preferencias en texto libre; complementan los filtros duros |
| `contexto/narrativa.md` | Historia profesional, motivación, hacia dónde va, cómo explica los cambios |
| `documentos/cv/`, `linkedin/`, `titulos/`, `referencias/` | Documentos fuente que `update-profile` puede leer (confirmando antes de escribir) |
| `documentos/candidaturas/<empresa>_<puesto>_<job_id>/` | Lo enviado en cada candidatura: PDF del CV, carta en TXT y PDF, `respuestas.json` y `README.md` (fecha en Europe/Madrid, canal, URL, versión del perfil) |

- Contexto: todos opcionales, sin versiones ni copia en la BD; `get_context` los lee con su hash.
  Plantillas en `demo/contexto/` (la candidata demo). No respaldan hechos (`POLICIES.md` §1.5).
- Archivo: nombre en ASCII y sin signos, de 40 caracteres como mucho por parte; se reconoce por el
  sufijo `_<job_id>`. Se escribe en `.tmp-<job_id>-…` y se renombra al final, así que nunca queda a
  medias. Si la carpeta ya existe no se toca: rehacer el CV o la carta después no cambia lo archivado.
  `JobView.archive_folder` (ficha de la UI) la da relativa a `data/`.

## Ampliaciones de la fase 25.7 («Mi perfil» editable, ADR-039)

Ficheros en `data/`:

| Ruta | Qué es |
|---|---|
| `profile-history/<AAAAMMDDTHHMMSSffffffZ>.yaml` | Copia de `profile.yaml` antes de cada guardado desde la UI (las `profile_editing.history_keep` últimas, 20 por defecto). «Deshacer» escribe la más reciente y la quita |
| `documentos/estilo/<nombre>` | Muestras de estilo (`.txt`, `.md`, `.docx`, `.pdf`), subidas desde «Mi perfil» (límites en `profile_editing`) |
| `documentos/estilo/.texto/<nombre>.txt` | Su texto, extraído al subirlas: es lo que lee el agente (`get_context.style_samples`) |

### `profile_edits` (migración 0024)

Auditoría de lo que el usuario guarda desde «Mi perfil». No va en `events`, que son de una oferta.
Sin el contenido: solo qué, cuándo y el sha256 del fichero.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| target | str | `profile`, `context` o `style_sample` |
| section | str? | La sección del perfil, el fichero de contexto o el nombre de la muestra; `null` al deshacer |
| action | str | `save`, `undo`, `upload` o `delete` |
| hash_before / hash_after | str? | sha256 de los bytes del fichero antes y después (`null` si no existía) |
| created_at | datetime | |

Un guardado del perfil que no cambia los datos (comentarios aparte) no crea versión en
`profile_versions` ni encola `rescore_all`, pero sí deja su copia y su fila.

## Ampliaciones de la fase 14

### `skill_gap_marks`
Lo que el usuario dijo, en la página «Skills», de una skill que piden las ofertas y su perfil no
cubre (migración 0013). No es estado de una oferta: no lleva evento.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| skill_key | str único | Forma canónica plegada (sin tildes ni mayúsculas, tras `config/skill_aliases.yaml`): la misma con que compara el matching. «spark» y «PySpark» son la misma marca |
| skill_name | str | Como la escriben las ofertas (la última vez que se marcó) |
| status | str | `gap` («No la tengo»: hueco real, para `training-plan`) o `have` («La tengo»: pendiente de añadir al perfil con `update-profile`) |
| created_at / updated_at | datetime | |

- Quitar la marca borra la fila. Una skill marcada sigue en la lista aunque ninguna oferta del
  periodo la pida (con `jobs_count: 0`) y deja de verse sola cuando entra en el perfil. Si
  alguien cambia a mano el canónico en `skill_aliases.yaml`, las marcas con la clave antigua se
  quedan huérfanas (se ven como filas sin ofertas; se quitan desde la página).
- Los huecos no se guardan: `services/skill_gaps.py` los calcula al pedirlos con las extracciones
  vigentes, el perfil vigente y los alias de ahora (ver `get_skill_gaps` en
  `AGENT_INTERFACE.md`).
- Ficheros: «Es lo mismo que…» escribe `config/skill_aliases.yaml`, fuera de `data/` (ADR-026).
  El skill `training-plan` escribe `data/documentos/training-plan.md` (y guarda la versión
  anterior como `plan-formacion-<AAAA-MM-DD>.md` al sustituirlo).

## Ampliaciones de la fase 15

### `replies`
Correos de las empresas de tus procesos (migración 0014). Solo se guardan los que casan con una
candidatura enviada; de los demás no queda nada. Contenido no confiable.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| message_id | str único | `Message-ID` o, si falta, `<sha256:…>` del correo |
| origin | str | `imap` o `local` (`data/inbox/respuestas/`) |
| sender, sender_name, subject | str | Remitente en minúsculas; nombre y asunto en una línea |
| received_at | datetime? | Cabecera `Date` |
| body_text | text | Texto visible (sin lo oculto del HTML), hasta `replies.max_body_chars` |
| risk_flags, risk_excerpt | JSON, str? | `injection_phrase` (visible u oculta) y `hidden_text` si la frase estaba oculta |
| candidates | JSON | `[{job_id, reason}]`, de la coincidencia más fiable a la menos: `contact`, `domain`, `ats`, `company_name` |
| status | str | `new` → `proposed` (agente) → `accepted` / `ignored` (usuario) |
| proposal | JSON? | `ReplyProposal` (`AGENT_INTERFACE.md` §Respuestas) |
| proposed_at, proposed_by | datetime?, str? | Cliente del agente |
| job_id | FK? | La oferta de la propuesta (o la que eligió el usuario al aceptar) |
| event_id | FK? | Evento registrado al aceptar |
| resolved_at | datetime? | Al aceptar o ignorar |
| created_at | datetime | |

### `message_drafts`
Borradores de seguimiento y agradecimiento (fase 15.3). La app nunca los envía. Como mucho uno
vigente (`draft`) por oferta y tipo (y entrevista, en un agradecimiento): guardar otro lo
sustituye. Un seguimiento no se guarda si la oferta ya tiene `followups.max_followups` (2)
eventos `followup_sent`.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id | FK | |
| kind | str | `followup` o `thank_you`; desde la fase 18, también `linkedin` y `email` |
| milestone_id | FK? | La entrevista que se agradece |
| subject, body | str?, text | Sin asunto solo en `linkedin` (migración 0018) |
| status | str | `draft`, `sent` (el usuario marcó que lo envió) o `discarded` |
| event_id | FK? | `followup_sent` al marcarlo enviado |
| agent_name | str? | |
| created_at / updated_at | datetime | |

## Ampliaciones de la fase 16

### `jobs.signals`
Observaciones del código sobre la oferta que **no** son riesgo de inyección (migración 0015,
ADR-028). `risk_flags` sigue significando solo eso. Las escribe el código, nunca el agente.

| Clave | Contenido | Quién |
|---|---|---|
| `possibly_closed` | `since`, `checked_at`, `reason` (`http_404`, `http_410`, `redirected`, `closed_text`, `expired_date`, `ats_missing`), `detail`, `http_status?` | La comprobación «¿sigue abierta?» (`services/liveness.py`). Se borra si una comprobación posterior dice `open`; `unknown` la deja como estaba |
| `liveness` | `checked_at`, `status` (`open`, `possibly_closed`, `unknown`, `skipped`), `reason?`, `detail`, `http_status?` | Última comprobación, sea cual sea |
| `open_confirmed` | `at`, `reason?` | «Sigue abierta» en la UI: ese mismo motivo ya no vuelve a avisar, hasta que una comprobación dé `open` (entonces se borra) |
| `reposted` | `count` (días distintos con publicación nueva), `dates[]`, `channel`, `window_days` | `services/reposts.py`, en todas las ofertas del grupo (misma empresa, título normalizado y ubicación). Se recalcula al ver una publicación nueva; no caduca sola |
| `salary_range_wide` (25.3) | `min`, `max`, `currency?`, `pct`, `threshold_pct` | `services/doubtful.py` al guardar la extracción: el máximo supera al mínimo en más de `doubtful.salary_range_max_pct` % |
| `employer_hidden` (25.3) | `reason` (`agency`, `agency_for_client`, `unnamed`), `origin` (`extraction`, `company`), `client?`, `matched?` | Ídem: `is_agency` de la extracción, o el nombre de la empresa coincide con `agencies` o `hidden_employer` de `config/doubtful_patterns.yaml` |
| `fixed_term` (25.3) | `origin` | Ídem: `contract_type: fixed_term` en la extracción |
| `ai_screening` (25.3) | `origin` (`extraction`, `text`), `matched?` | Ídem: `mentions_ai_screening`, o una frase de `ai_screening` en el texto |
| `stale_repost` (25.3) | `count`, `channel`, `first_seen`, `last_seen`, `span_days` | `services/reposts.py`, con todo el historial de `job_sightings` del grupo, sin ventana: `count ≥ doubtful.stale_repost_min_count` o `span_days ≥ doubtful.stale_repost_min_span_days` |

Las cinco de la fase 25.3 son **señales de oferta dudosa**: no cambian el score ni los filtros
duros, salvo `employer_hidden` y `fixed_term` si están en `preferences.exclude_signals` del perfil
(filtro `signal`). `cai jobs signals --recompute` las recalcula todas. Sin migración: es la misma
columna JSON. Las extracciones anteriores a la fase no traen los campos nuevos, así que solo
cuentan las señales del nombre, el texto, el salario y las publicaciones.

### `job_sightings`
Cada publicación vista de una oferta (migración 0015, que rellena una fila por oferta existente).

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id | FK jobs | La oferta en la que se anota (la existente si la huella la reconoce) |
| channel | str | Plataforma (`infojobs`…) o dominio de la URL sin `www.` |
| ref | str | Id en la plataforma (de la URL), el id que da la fuente (conectores) o la URL sin esquema ni fragmento, con solo los parámetros que identifican la oferta (`gh_jid`, `jk`, `id`…) |
| seen_at | datetime | |

Único (`job_id`, `channel`, `ref`). Se anota al dar de alta una oferta y cuando reaparece con otro
id o URL: por huella en `ingest.store_job` y, en los conectores, lo que ya estaba por URL o huella.

**Republicada** = en los últimos `reposts.window_days` (90) días, el mismo canal muestra
publicaciones distintas de la misma empresa con el mismo título normalizado (traducido con
`config/title_aliases.yaml`) y la misma ubicación en al menos `reposts.min_count` (2) días distintos. Varias el mismo día
(varias ubicaciones) o en canales distintos (la misma oferta en InfoJobs e Indeed) no cuentan.

## Ampliaciones de la fase 18

### `network_contacts`
Tu red de LinkedIn, de la exportación oficial `Connections.csv` (migración 0017). Separada de los
contactos de cada proceso. La escribe solo `cai contacts import-linkedin` (o «Importar» en la ficha),
nunca el agente.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| first_name / last_name | str / str | `last_name` puede ir vacío |
| linkedin_url | str? único | Solo si es de `linkedin.com`; sin `/` final |
| company | str? | Como viene en la exportación |
| company_key | str? índice | `normalize_company(company)`: la misma normalización que `companies.normalized_name` |
| position | str? | Cargo |
| connected_on | date? | `Connected On` (`12 Oct 2024`, también ISO o con meses en español) |
| imported_at | datetime | Última importación que la vio |

- **Sin email**: aunque la exportación lo traiga, no se guarda.
- **Importar sincroniza**: se reconoce a cada persona por su URL (sin URL, por nombre y empresa);
  añade, actualiza y borra lo que ya no está. Un fichero sin filas no borra la red; si quita más de
  la mitad, el mensaje lo avisa. Los contactos del proceso y los borradores que apuntaban a una
  persona borrada siguen, sin el enlace.
- **Cruce con una oferta** (`services/network.py`): `exact` si las claves de empresa son iguales (o
  iguales sin espacios); `probable` si una es el principio de la otra palabra a palabra
  («bretema» ↔ «bretema analytics»), salvo que la corta sea una sola palabra de menos de 5 letras
  o genérica («banco», «grupo», «data»…). `JobRow.known_contacts` lleva el recuento a la bandeja y
  al triaje.

### `message_drafts` (fase 18, migración 0018)
Mensajes a personas de la empresa: `linkedin` (≤ 300 caracteres, sin asunto ni adjuntos) y `email`
(con asunto). Se guardan desde `approved` hasta `in_process` (los seguimientos y agradecimientos,
solo en `applied`/`in_process`). «Ya lo he enviado» no registra evento. Como mucho uno vigente por
oferta, tipo y destinatario.

| Columna | Tipo | Notas |
|---|---|---|
| recipient_role | str? | `recruiter`, `hiring_manager` (responsable del puesto) o `peer` (compañero). Obligatorio en `linkedin` y `email` |
| contact_id | FK contacts? | El contacto del proceso al que va (de esa oferta) |
| network_contact_id | FK network_contacts? | O la persona de tu red, de la empresa de la oferta. No los dos. Queda en `null` si sale de la red al reimportar |
| recipient_name | str? | El nombre del destinatario al guardar (sigue aunque la persona salga de la red) |
| attachments | JSON? | Solo en `email`: nombres de los adjuntos que menciona (la app no adjunta nada) |

### `company_research`
Dosier de una empresa (skill `research-company`, migración 0018). Uno por empresa: lo comparten
todas sus ofertas y guardar otro lo sustituye. No lleva evento: no es estado de una oferta.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| company_id | FK companies, único | |
| job_id | FK jobs? | La oferta desde la que se investigó |
| content | JSON | `CompanyResearchContent`: `summary`, `product?`, `news?`, `engineering_culture?`, `stack[]`, `notes?` y `sources[]` (`title`, `url` http(s) y no de LinkedIn, `accessed_on?`). Cada apartado con texto, salvo `notes`, cita `[n]` de `sources` |
| risk_flags | JSON | `injection_phrase` si el texto guardado contiene frases dirigidas a una IA (sale de webs) |
| file_name | str | `<Empresa>_<company_id>.md` en `data/documentos/empresas/`, que escribe el código (se reescribe al sustituirlo) |
| agent_name | str? | |
| created_at / updated_at | datetime | |

Al archivar una candidatura (fase 13) se copia ese `.md` a su carpeta como `empresa.md`: el
dosier vigente al archivar, que no forma parte de lo enviado (el README lo dice).

## Ampliaciones de la fase 19

Migración 0019. Ninguna de las dos tablas lleva eventos: no son estado de una oferta (lo que haga
el agente sí los registra, por sus herramientas, como siempre).

### `agent_runs`
Ejecuciones del agente en segundo plano (ADR-032). Es su propia cola: la llena la UI
(`POST /agent/runs`) y la vacía el worker en un hilo aparte, de una en una o, desde la fase 25.4, hasta `background_runs.max_parallel` a la vez (ADR-038).

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| action | str | Una de `agent_launch.ACTIONS` con `background` (`process-jobs`, `assess-fit`, `generate-cv`) |
| job_id | FK jobs? | En `generate-cv` |
| milestone_id | FK milestones? | Reservado (ninguna acción de entrevista va en segundo plano) |
| agent | str | El agente del manifiesto (`claude`, `opencode`) |
| model / preset | str? | El modelo o el preset con que se lanzó (fase 24.4, migración 0022); vacíos: el del agente |
| status | str | `queued`, `running`, `done`, `needs_user` (terminó con preguntas), `failed`, `cancelled`, `timeout` |
| prompt | text | La orden, con la nota de segundo plano (y, en `generate-cv`, la de las skills marcadas «No la tengo») |
| command | JSON | El comando exacto (con las herramientas permitidas si el techo va en la orden): para auditar qué podía hacer |
| run_config | JSON? | Fase 24.5 (migración 0023): con techo por configuración (OpenCode), cómo se escribe la de la ejecución: `format`, `env`, `value`, `agent` y `mcp_prefix`. El runner la escribe en `data/tmp/agent-runs/<id>/` al lanzar y la borra al terminar. Vacía: el techo va en `command` |
| unset_env | JSON | Variables que se quitan antes de lanzarlo (`ANTHROPIC_API_KEY`) |
| output_format | str | El `output` de `launch.headless`: qué lector de `agent_output.PARSERS` usa |
| session_id | str? | La sesión del agente: «Abrir en terminal» la retoma |
| progress | JSON | Las últimas `background_runs.max_progress_lines` líneas `{at, kind: tool\|text\|info\|error, text}`. De las herramientas, solo el nombre (nunca sus entradas ni el detalle de sus errores); del texto, el del agente principal, recortado |
| result | text? | La respuesta final (hasta 20 000 caracteres) |
| questions | JSON | Las líneas «PREGUNTA:» del resultado |
| error | text? | |
| usage | JSON? | Desde la fase 25.4, las mismas claves para todos los agentes, todas opcionales: `input_tokens`, `output_tokens`, `cached_tokens`, `turns`, `duration_ms` y `cost_usd` (el que informa el agente; con suscripción no se factura), más `denied_tools`. Las filas de antes usaban `num_turns`, `total_cost_usd` y `cache_read_tokens`: `agent_usage.normalize_usage` las traduce al leer. Sin migración |
| cancel_requested | bool | La UI lo pide; el worker para el proceso en ≤ 2 s |
| pid | int? | |
| created_at / started_at / finished_at | datetime | |

Reclamar es un `UPDATE` condicionado a que no haya otra `running`: una sola a la vez, también
entre procesos. Cancelar y terminar también van condicionados al estado. Si el worker se para, la
que esté en curso queda `failed`; si muere de golpe, al arrancar quedan `failed`, no se repiten y
se para su agente si sigue vivo.

### `agent_requests`
Cola de encargos: lo que la UI deja para la próxima sesión interactiva del agente.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| action | str | Cualquiera de `agent_launch.ACTIONS` salvo `handle-requests` |
| job_id / milestone_id | FK? | Los de la acción |
| prompt | text | La orden, compuesta por la app (lista cerrada; ningún texto de una oferta) |
| status | str | `pending`, `done` (lo cerró el agente con `complete_agent_request`) o `cancelled` (desde la UI) |
| summary | text? | El resumen del agente al cerrarlo |
| agent_name | str? | |
| created_at / completed_at | datetime | |

Mismo encargo pendiente (acción, oferta e hito) no se duplica. `get_status` cuenta los pendientes
en `agent_requests`.

### `agent_preferences`
Qué agente y qué modelo usa cada acción (fase 24.4, ADR-037, migración 0022). Son datos de uso de
la persona: viven en la base de datos de `data/`, nunca en el repositorio ni en la configuración
generada. Las escribe la página «Agente» (`PUT /agent/preferences`, que las sustituye todas) y las
lee `services/agent_prefs.py`.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| scope | str | `default` (el agente por defecto), `agent` (el modelo de un agente) o `action` (el agente de una acción) |
| key | str | Vacía en `default`; el agente en `agent`; la acción en `action`. Única con `scope` |
| agent | str? | En `default` y `action` |
| model / preset | str? | Uno de los dos o ninguno. El modelo es texto libre validado con `models.pattern` del agente, sin red |
| updated_at | datetime | |

Precedencia: elección puntual del botón > `action` > `default` > `CAI_AGENT` > el primero
habilitado e instalado. El modelo sale del mismo nivel que eligió el agente; si no lo da, del
`agent` de ese agente.

## Ampliaciones de la fase 21

### `received_offers`
La oferta que ha hecho la empresa de un proceso (migración 0020). La anota solo el usuario desde
la ficha («Oferta recibida»); una por oferta de empleo. Guardarla sin `offer_received` previo lo
registra (actor `user`, así que solo vale en `applied` o `in_process`); cambiarla deja una `note`
con los campos cambiados, **sin valores** (el historial lo leen los agentes). Borrarla no quita el
`offer_received`.

| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| job_id | FK jobs, único | |
| base_salary | int? | Fijo bruto |
| variable | int? | Variable o bonus bruto objetivo, siempre anual |
| currency | str | ISO 4217, `EUR` por defecto |
| period | str | `year` o `month`: el del fijo |
| benefits | text? | |
| work_mode | str? | `remote`, `hybrid` u `onsite` |
| location | str? | |
| start_date | date? | Incorporación |
| respond_by | date? | Fecha límite para responder |
| notes | text? | Las ve el agente: la UI avisa de no poner cifras propias |
| amounts_private | bool | `true` por defecto: fijo y variable no salen por la interfaz para agentes |
| created_at / updated_at | datetime | |

**Comparación** (`received_offers.compare`, `GET /received-offers`, solo la UI): por oferta, el
fijo anualizado (mensual ×12, marcado como aproximado: no cuenta pagas extra) y el total (fijo
anual + variable; sin fijo no hay total), su diferencia con `private.salary_floor_eur` del perfil (solo si la oferta está en
EUR) y la del fijo con el mínimo y el máximo del rango publicado en la extracción vigente (misma
moneda; un rango sin moneda, sin periodo o por hora no se compara, y uno mal formado se ignora). `remarks` explica lo que no se ha podido comparar.
Nunca recomienda una cifra.

