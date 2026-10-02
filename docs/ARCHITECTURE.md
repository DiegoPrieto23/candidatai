# Arquitectura

## Idea central

La app hace todo lo determinista: guardar, deduplicar, filtrar, puntuar, detectar contenido
sospechoso, renderizar documentos y llevar el seguimiento. **El agente de IA del usuario** hace lo
que necesita criterio o redacción, llamando a la interfaz para agentes de la app (MCP o CLI).
La app nunca llama a un modelo y no depende de ningún proveedor.

```
                  ┌──────────────────────────────────────────────┐
  Tú ──── UI ─────┤  FastAPI  ─┐                                 │
  (React)         │            ├──► services/ ──► SQLite (data/) │
  Tú ─ tu agente ─┤  MCP     ──┤        │                        │
  (Claude Code,   │  CLI jh  ──┘        ├──► docxtpl + LibreOffice│
   Codex, …)      │                     ├──► embeddings locales  │
                  │  worker ────────────┘   (scheduler, ingesta) │
                  └──────────────────────────────────────────────┘
```

## Capas

| Capa | Responsabilidad | Regla |
|---|---|---|
| `app/models` | Tablas SQLAlchemy | Sin lógica |
| `app/schemas` | Modelos Pydantic de entrada/salida, incluidos los que rellena el agente | Única definición de cada esquema |
| `app/services` | Toda la lógica de negocio | Se prueba aquí; no conoce HTTP, MCP ni CLI |
| `app/api` | Endpoints REST para la UI | Solo traduce HTTP ↔ servicios |
| `app/mcp` | Herramientas MCP para agentes | Solo traduce MCP ↔ servicios; valida con Pydantic |
| `app/cli.py` | CLI `jh`, con modo `--json` equivalente a la MCP | Solo traduce CLI ↔ servicios |
| `app/services/tasks.py`, `worker.py` | Cola de tareas en BD y worker (`jh worker`, APScheduler): scores, recálculos, ingesta diaria, alertas por correo y caducidad de resúmenes | Ejecuta servicios; nunca un LLM |
| `app/services/ingestion/` | Conectores de ATS y portales, filtro previo y ejecución de fuentes (fase 09); `email/`: alertas por correo (09b) | Solo endpoints públicos documentados; IMAP en solo lectura; guardan con el mismo servicio que el alta manual |
| `app/services/capture.py` | Captura desde la extensión: token (solo su hash en `data/`) y alta o compleción de la oferta (09b) | Todo lo capturado es no confiable: pasa por la detección de riesgo |
| `app/services/platforms.py`, `summaries.py` | Identidad de oferta por plataforma (`platform` + `external_id`) y ofertas resumen en `pending_detail`: bandeja «Alertas» y caducidad (09b) | Sin red ni agente |
| `frontend/` | UI | Solo habla con la API |
| `.agents/` | Skills, roles y manifiesto, sin nada específico de un proveedor | Fuente única; lo nativo se genera |

## API REST para la UI

`app/api/` expone lo que necesita la UI; la lógica sigue en `app/services/`:

| Método y ruta | Para qué |
|---|---|
| `GET /status` | Recuentos por etapa (cabecera) |
| `GET /jobs?stage=&q=&limit=&offset=` | Bandeja: filtro por etapa, búsqueda en título y empresa, paginación con `total` |
| `GET /jobs/{id}` | Ficha: metadatos, texto original, extracción vigente, eventos y aviso de inyección |
| `GET /jobs/{id}/match` | Match vigente (lo recalcula si está desfasado), igual que `get_match` |
| `GET /triage` | Ofertas en `pending_triage` con extracción y match, mayor score primero; calcula los que falten |
| `POST /jobs/url`, `POST /jobs/text` | Alta (mismos servicios que `add_job_from_url` y `add_job_from_text`) |
| `POST /jobs/{id}/events` | Eventos del usuario (actor `user`): nota, aprobar, descartar con `reason` obligatorio, reabrir… |
| `GET /templates`, `GET /templates/{id}/preview.png` | Plantillas de CV (como `list_cv_templates`) y la miniatura de cada una |
| `GET /jobs/{id}/cv` | CV vigente de la oferta (`cv: null` si no tiene): contenido, verificación y renders con avisos, páginas, cobertura, `selected` y `template_changed` |
| `POST /documents/{id}/renders` | Otro render del mismo contenido con otras `CvRenderOptions` (actor `user`, sin IA) |
| `POST /renders/{id}/select` | Marca el render que se enviará (uno por CV; sin evento ni cambio de etapa) |
| `GET /renders/{id}/pdf`, `GET /renders/{id}/docx` | Ficheros del render |
| `GET /uploads`, `POST /uploads`, `DELETE /uploads/{name}` | «Mi CV»: CVs subidos a `data/uploads/` (máximo 10 MB, nombre saneado, nunca se sobrescribe) y la plantilla creada desde cada uno, si la hay (por sha256 del `source.*`) |
| `GET /templates/{id}/source.png`, `GET /templates/{id}/preview-real.png` | Primera página del original importado y la plantilla con el perfil real (en caché por plantilla y versión del perfil) |
| `GET /sources`, `POST /sources` | Pantalla «Empresas»: fuentes con conector (empresas objetivo y portales) con su última ejecución; alta (`exists` 409 si ya está) |
| `POST /sources/test`, `POST /sources/{id}/test` | Prueba una fuente nueva o guardada sin guardar nada: «12 ofertas encontradas, 3 tras filtros». Un fallo de la fuente es 200 con `errors` |
| `POST /sources/{id}/run`, `POST /sources/{id}/active` | Ejecuta ya la fuente (lo nuevo, a `pending_extraction`) o la activa/pausa en la ingesta diaria |
| `GET /alerts`, `POST /alerts/poll` | Pantalla «Alertas»: ofertas resumen (`pending_detail`) con su prefiltro, primero las que pasan; leer ya el correo (como `jh alerts poll`). Descartar va por `POST /jobs/{id}/events` |
| `POST /capture` | Botón «Enviar a Job Hunter» (la extensión, no la UI): exige el origen de la extensión (403) y su token (401; 503 si no hay); completa un resumen, reconoce una oferta ya guardada o da de alta una nueva (`services/capture.py`) |
| `GET /templates/default`, `POST /templates/{id}/default` | Plantilla por defecto del perfil vigente; fijarla edita solo esa clave de `data/profile.yaml` (con ruamel.yaml, conserva comentarios) e importa la versión nueva |

- `jh serve` escucha solo en `127.0.0.1`; CORS solo para `http://127.0.0.1:5173`. La extensión de
  captura no lo necesita: sus `host_permissions` la eximen, y `POST /capture` exige su origen y token.
- Errores con el mismo formato que la interfaz para agentes (`{ok: false, error: {type, message,
  details}}`): 404 `not_found`, 409 `invalid_transition` o `exists`, 413 `too_large`, 422
  validación, 503 BD sin migrar o sin conversor a PDF (`pdf_unavailable`).
- Los ficheros solo se sirven desde `data/cvs/` (renders; no todo `data/`, que también guarda
  secretos como el token de captura de la 09b) y desde las carpetas de plantillas (previews): la ruta guardada se resuelve y se comprueba que queda dentro antes de abrirla; si no,
  404.
- La ficha devuelve el texto original **sin** el envoltorio `<untrusted_job_posting>`: lo lee una
  persona y React lo pinta como texto. El envoltorio es para los agentes (`get_job`).
- Las llamadas de la UI no se auditan en `mcp_calls`: esa tabla registra a los agentes.
- El cliente del frontend se genera desde el OpenAPI (`pnpm gen:api`) y se versiona
  (`frontend/src/api/`); un test del backend falla si se queda desfasado.

## Etapas de una oferta

```
found ─► pending_extraction ─► pending_triage ─► approved ─► cv_ready ─► applied ─► in_process ─► closed
  └─► pending_detail ─┘   (fase 09b: ofertas «resumen» de alertas, hasta completarlas)
                  │                   │              │           │
              [agente]            [Tú en UI,     [agente:     [Tú confirmas
             rol extractor        con ayuda de   redactor +   en la UI]
                                  evaluar-encaje] verificador]
```

- Las etapas marcadas [agente] se quedan en cola hasta que ejecutas el skill correspondiente en tu
  agente, o hasta que una tarea programada de tu agente lo hace por ti, si tu herramienta lo permite.
- La etapa actual de cada oferta se calcula a partir de sus eventos (`docs/DATA_MODEL.md`).

## Qué hace el agente y qué hace el código

| Tarea | Quién | Por qué |
|---|---|---|
| Descargar ofertas (APIs de ATS, URL, texto pegado) | Código | Determinista y repetible |
| Leer alertas de correo y capturas del botón del navegador | Código | Determinista; nunca entra en los portales |
| Recorrer portales con el navegador (opcional) | Agente, skill `buscar-ofertas` | Solo donde no hay otra vía; con reglas estrictas (POLICIES §8) |
| Deduplicar (huella + similitud difusa) | Código | Determinista |
| Detectar texto oculto y frases de inyección | Código | No depende del agente que se use |
| Extraer la oferta a JSON | Agente, rol `extractor` (modelo rápido) | Necesita comprensión de texto |
| Filtros duros (seniority, ubicación, idioma) | Código | Reglas explícitas en `config/policies.yaml` |
| Score de encaje (embeddings + cobertura de skills) | Código | Medible y evaluable |
| Explicar el encaje y sus riesgos | Agente | Criterio |
| Aprobar o descartar | Tú | Decisión tuya |
| Redactar el contenido del CV | Agente, rol `redactor` | Redacción |
| Verificar que no hay nada inventado | Agente, rol `verificador` (distinto del redactor) | Segunda opinión independiente |
| Comprobar evidencias, skills y páginas | Código | Determinista; no se fía del agente |
| Elegir plantilla y foto para una oferta | Código, por reglas; tú puedes cambiarlo en la UI | Configurable y sin coste |
| Renderizar DOCX/PDF, también en otra plantilla o sin foto | Código | Determinista; no hace falta volver al agente |
| Convertir tu CV en plantilla | Agente (mapeo o recreación) + código (construye, sanea, valida y previsualiza) | El agente interpreta el diseño; el código garantiza que funciona |
| Rellenar formularios de candidatura | Código (Playwright) | Determinista, con pausa antes de enviar |
| Enviar | Tú (confirmación en la UI) | Irreversible |

## Fronteras de seguridad (defensa en profundidad)

Las garantías se reparten en capas para que **no dependan de qué agente use cada persona**
(detalle por agente en `docs/AGENTS_COMPAT.md`):

1. **En el código, siempre activas:**
   - Al guardar una oferta se detecta texto oculto en el HTML y frases típicas de inyección
     (`config/injection_patterns.yaml`); se guardan como `risk_flags` y se registra el evento antes
     de que ningún agente la vea.
   - `get_job` entrega el texto envuelto como no confiable y con sus `risk_flags`.
   - Todo lo que devuelve un agente se valida con Pydantic. El CV se rechaza si cita evidencias
     inexistentes, skills fuera del perfil o skills básicas no pedidas.
   - La interfaz para agentes no tiene nada que envíe datos al exterior. Enviar solo ocurre desde
     la UI, con tu clic.
2. **En el agente, cuando lo permite:** el texto crudo solo lo ve el rol `extractor`, configurado
   con las herramientas mínimas (en Claude Code, solo las dos herramientas MCP que necesita; en
   Codex, sandbox de solo lectura). El resto de roles trabaja con datos ya estructurados.
3. **Auditoría:** cada llamada a la interfaz queda en la tabla `mcp_calls`.
4. **Datos personales** en `data/`, fuera del repositorio.

## Ejecución en local (Windows 11)

- Todo nativo con `uv` y `pnpm`, sin Docker: Playwright necesita un navegador visible para que
  inicies sesión y revises formularios, y LibreOffice se usa instalado en el sistema.
- `jh serve` levanta la API, `jh worker` el scheduler y `pnpm dev` la UI. El worker debe estar en
  marcha para la ingesta diaria; si el equipo estaba apagado a esa hora, al arrancarlo ejecuta
  las fuentes pendientes.
- Cada agente arranca el servidor MCP solo, según su configuración generada (`.mcp.json` para
  Claude Code, `.codex/config.toml` para Codex…).

## Despliegue futuro (fuera del alcance actual)

SQLite → Postgres cambiando la URL de conexión (las migraciones ya existen), API + worker en
contenedores, y el aplicador Playwright y la interfaz para agentes como componentes locales.
