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
| | `… [--source S] [--platform P] [--external-id X]` | 09b | `add_job_from_text` admite además `source_id?, platform?, external_id?` | igual | igual |
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
| `save_application_answers` | `jh applications save-answers ID --file F` | 10 | `job_id, answers: ApplicationAnswers` | `document_id` | `application_prepared` |
| `list_followups_due` | `jh followups --days N --json` | 10 | `days_without_reply=10` | Candidaturas sin respuesta | — |
| `list_upcoming` | `jh upcoming --days N --json` | 10 | `days=7` | Entrevistas, pruebas y plazos próximos | — |
| `get_funnel_stats` | `jh stats funnel [--since] --json` | 10 | `since?` | Conversión por etapa, fuente y tipo de puesto | — |
| `list_sources` | `jh sources list [--kind K] --json` | 09b | `kind?` | Fuentes con su config (sin secretos) y última ejecución | — |
| `save_source` | `jh sources save --file F --json` | 09b | `AgentBrowseSource` | `source_id`. Solo tipo `agent_browse`; nunca activa `allow_agent_browsing` en LinkedIn | — |
| `record_source_run` | `jh sources record-run ID --file F` | 09b | `SourceRunSummary` | `ok` | — |

La captura del botón «Enviar a Job Hunter» es un endpoint REST de la app (`POST /api/capture`,
fase 09b), no parte de esta interfaz: la usa la extensión, no el agente.

Las utilidades de autoría de plantillas (`jh templates inspect | build-docx | scaffold-html |
validate | preview | compare`) son solo CLI: trabajan con ficheros dentro de `data/` y las usa el
skill `importar-plantilla-cv`. Detalle en `docs/CV_TEMPLATES.md`.

Aprobar o descartar **no tiene herramienta propia a propósito**: esa decisión se toma en la UI. Si
el usuario la dicta a su agente, este puede usar `add_event` con `approved` o `discarded` y el
motivo que él dé en `note`, nunca por iniciativa propia. El evento queda con actor `agent`.

`get_profile` devuelve la última versión importada (no lee `data/profile.yaml`). `sections` admite
`personal`, `headline`, `summary`, `experience`, `projects`, `education`, `certifications`,
`languages`, `skills`, `basic_skills`, `stories` y `preferences`; por MCP es una lista y por CLI va
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
`cv_generated`, `cv_rendered`, `cv_verified`, `cv_rejected` y `application_prepared`. `list_jobs` con
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

### Comandos de matching y worker (solo CLI)

| Comando | Qué hace |
|---|---|
| `jh worker [--once] [--interval S] [--json]` | Ejecuta la cola de tareas (`score_job`, `rescore_all`). `--once` la vacía y termina (código 1 si alguna falla) |
| `jh match rescore [--json]` | Recalcula ya los matches desfasados de las ofertas abiertas (tras instalar el extra `matching` o editar `config/policies.yaml`) y cierra las de triaje que no pasan los filtros. Devuelve `scored` y `closed` |
| `jh eval matching [--profile RUTA] [--no-seed] [--no-embeddings] [--json]` | Precision, recall y F1 con el umbral actual y por umbral sobre `evals/matching/*.jsonl` (perfil de demo) y `data/evals/*.jsonl` (tu perfil). Guarda el informe en `data/evals/reports/` |

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
hidden_sections: [str]                 # summary|experience|projects|education|certifications|skills|languages
page_size: A4|Letter|null
```

### `CvVerification`
```
passed: bool
issues: [{severity: blocker|warning, location: str, problem: str, suggestion: str}]
```
`passed: true` con algún `blocker` es un `validation_error`. `suggestion` es opcional.

### `ApplicationAnswers`
```
answers: [{question: str, answer: str, evidence: [str], needs_user_input: bool}]
cover_letter: str | null
```
