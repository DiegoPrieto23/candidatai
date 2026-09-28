# Modelo de datos

SQLite en `data/jobhunter.db`, modo WAL. SQLAlchemy 2.0 + Alembic. Todas las fechas en UTC
(`datetime` con zona); la UI convierte a Europe/Madrid.

## Tablas

### `sources`
Origen de ofertas.
| Columna | Tipo | Notas |
|---|---|---|
| id | int PK | |
| kind | str | `manual_url`, `manual_text`, `greenhouse`, `lever`, `ashby`, `infojobs`, `adzuna` |
| name | str | Etiqueta legible |
| config | JSON | Parámetros del conector (slug del ATS, consulta, filtros) |
| active | bool | |
| last_run_at | datetime? | |

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
| external_id | str? | ID en la fuente, si existe |
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
de la misma empresa en los últimos 60 días marca `duplicate_of`.

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
| kind | str | `cv`, `cover_letter`, `answers` |
| language | str | `es`, `en` |
| content | JSON | `CvContent` u otro esquema, con referencias a evidencias |
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
| options | JSON | `CvRenderOptions` ya resueltas (plantilla, foto sí/no, color…) |
| docx_path / pdf_path | str? | Relativos a `data/`; `docx_path` vacío en el motor html |
| pages | int | |
| keyword_coverage | JSON | Keywords de la oferta presentes y ausentes en el PDF |
| warnings | JSON | `too_long`, `not_ats_friendly`, `font_substituted`… |
| selected | bool | El que se usará al enviar; como mucho uno por documento |
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
| `found` | system | `pending_extraction` |
| `duplicate_detected` | system | `closed` |
| `extracted` | agent | `pending_triage` (si pasa filtros duros) |
| `hard_filter_failed` | system | `closed` (reabrible); `payload.failures` |
| `extraction_failed` | agent | se queda en `pending_extraction` |
| `injection_suspected` | system / agent | sin cambio; aviso visible en la UI |
| `scored` / `fit_assessed` | system / agent | sin cambio; `payload`: `match_id` y `score`/`passed` o `verdict` |
| `approved` | user | `approved` |
| `discarded` | user | `closed`; desde la UI, `payload.reason` (`skills`, `seniority`, `location`, `salary`, `company`, `other`) y `note` opcional (obligatoria con `other`) |
| `cv_generated` | agent | sin cambio |
| `cv_rendered` | system / user / agent | sin cambio |
| `cv_verified` | agent | `cv_ready` si `passed` y hay un render sin `too_long` |
| `cv_rejected` | agent | sin cambio |
| `application_prepared` | system | sin cambio |
| `applied` / `applied_manually` | user | `applied` |
| `reply_received`, `interview_scheduled`, `interview_done`, `test_assigned` | user | `in_process` |
| `followup_sent` | user | sin cambio |
| `offer_received` | user | `in_process` |
| `rejected`, `withdrawn`, `expired`, `accepted` | user/system | `closed` |
| `reopened` | user | la etapa previa al cierre |
| `note` | cualquiera | sin cambio |

La proyección vive en `services/pipeline.py`: `stage_for(events) -> Stage`, con tests que cubren
cada transición. Una transición no válida (p. ej. `applied` sin `cv_ready` ni `applied_manually`)
se rechaza con error claro.
