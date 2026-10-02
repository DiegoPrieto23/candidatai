# Modelo de datos

SQLite en `data/jobhunter.db`, modo WAL. SQLAlchemy 2.0 + Alembic. Todas las fechas en UTC
(`datetime` con zona); la UI convierte a Europe/Madrid.

## Tablas

### `sources`
Origen de ofertas.
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| kind | str | `manual_url`, `manual_text`, `greenhouse`, `lever`, `ashby`, `infojobs`, `adzuna`; desde la fase 09b, también `email_alerts`, `browser_capture` y `agent_browse` |
| name | str | Etiqueta legible |
| config | JSON | Parámetros del conector, validados por tipo (`app/schemas/sources.py`): ATS `{slug, region, title_keywords}` (`region: eu` solo en Lever); InfoJobs `{query, province, since, title_keywords}`; Adzuna `{query, where, country, max_days_old, title_keywords}`. Nunca claves: van en `.env` |
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
| risk_flags | JSON | Señales detectadas por el código: `hidden_text`, `injection_phrase`… |
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
| content | JSON | `CvContent`, `CoverLetterContent` (con las indicaciones usadas) u otro esquema, con referencias a evidencias |
| verification | JSON? | `{passed, issues[]}` del verificador |
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
| warnings | JSON | `[{code, message}]`: `too_long`, `not_ats_friendly`, `font_substituted`… |
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
| `run_source` `{source_id}` | `jh worker` a la hora de `connectors.daily_at`, y al arrancar para las fuentes que no corrieron desde la última hora programada | Ejecuta el conector (`ingestion/service.run_source`). Un fallo de red, 5xx, 429 o interno queda en `source_runs` y la tarea se reintenta; un 404 o un formato inesperado no. Los portales sin claves no se encolan. Al arrancar, las tareas que quedaron `running` vuelven a la cola |
| `rescore_all` `{}` | `jh profile import` con versión nueva | Recalcula los matches desfasados de las ofertas abiertas con extracción y cierra las de triaje que ya no pasan los filtros (lo mismo que `jh match rescore`, sin cola) |

No se encola dos veces la misma tarea (mismo `kind` y `payload`) mientras siga en cola. Si falla,
vuelve a la cola con espera creciente; tras 3 intentos queda `failed` con `last_error`.

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
| `scored` / `fit_assessed` | system / agent | sin cambio; `payload`: `match_id` y `score`/`passed` o `verdict` |
| `approved` | user | `approved` |
| `discarded` | user | `closed`; desde la UI, `payload.reason` (`skills`, `seniority`, `location`, `salary`, `company`, `other`) y `note` opcional (obligatoria con `other`) |
| `cv_generated` | agent | sin cambio; `payload.document_id` |
| `cv_rendered` | system / user / agent | `cv_ready` si el render no es `too_long` y su documento ya está verificado con `passed`; si no, sin cambio. `payload`: `document_id`, `render_id`, `template_id`, `too_long`. Solo lo registra el servicio de render |
| `cv_verified` | agent | `cv_ready` si `passed` y ese documento tiene un render sin `too_long`; `payload`: `document_id`, `passed` |
| `cv_rejected` | agent | sin cambio; `payload`: `document_id`, `blockers` |
| `cover_letter_generated` | agent / user | sin cambio; `payload`: `document_id`, `edited_by_user` (fase 08c) |
| `cover_letter_verified` | agent | sin cambio; `payload`: `document_id`, `passed`, `blockers` (fase 08c) |
| `application_prepared` | system | sin cambio |
| `applied` / `applied_manually` | user | `applied`; `payload.render_id` (el CV enviado) y `channel` |
| `reply_received`, `interview_scheduled`, `interview_done`, `test_assigned` | user | `in_process` |
| `followup_sent` | user | sin cambio |
| `offer_received` | user | `in_process` |
| `rejected`, `withdrawn`, `expired`, `accepted` | user/system | `closed` |
| `reopened` | user | la etapa previa al cierre |
| `note` | cualquiera | sin cambio |

La proyección vive en `services/pipeline.py`: `stage_for(events) -> Stage`, con tests que cubren
cada transición. Una transición no válida (p. ej. `applied` sin `cv_ready` ni `applied_manually`)
se rechaza con error claro.

## Ampliaciones de la fase 08c

- `document_renders` guarda también los renders de cartas (`options` = `CoverLetterRenderOptions`
  resueltas, `keyword_coverage` vacío, ficheros `Carta-<Nombre>.pdf|docx`). `selected` funciona
  igual: como mucho una carta seleccionada por documento.
- Tabla `cover_letter_briefs`: `job_id` (PK/FK), `instructions` (texto), `max_words` (int?),
  `updated_at`. Las indicaciones de la carta para esa oferta; no guarda historial (el documento
  copia las que usó).

## Ampliaciones de la fase 09b

Detalle y motivos en `docs/FUENTES_OFERTAS.md` §Modelo de datos.

- `jobs`: `platform` (str?, p. ej. `linkedin`), `detail_level` (`summary` | `full`) e índice
  único parcial sobre (`platform`, `external_id`) cuando ambos existen.
- Etapa nueva `pending_detail`, antes de `pending_extraction`. Desde ella se admiten
  `detail_captured`, `discarded` y `expired`.
- Tabla `source_runs`: ya la crea la fase 09 (migración `0006`); la 09b la reutiliza.
- Tabla `email_messages`: `message_id` (único), `source_id`, `received_at`, `jobs_found`,
  `processed_at`. Nunca guarda el cuerpo del correo.
