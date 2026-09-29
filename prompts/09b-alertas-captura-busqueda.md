# Fase 09b · Alertas por correo, botón de captura y búsqueda con navegador

## Contexto
Lee `docs/FUENTES_OFERTAS.md` entero (es la especificación de esta fase), `docs/POLICIES.md` §5 y
§6, `docs/DATA_MODEL.md` y `.agents/skills/buscar-ofertas/SKILL.md`. Requiere la fase 09
(worker, `sources` y conectores).

Si no cabe en una sesión, pártela: **09b.1** modelo de datos, ofertas resumen y alertas por correo;
**09b.2** botón de captura (API + extensión); **09b.3** plataformas y búsqueda con navegador.

## Objetivo
Que LinkedIn y el resto de portales sin API alimenten la app: sus alertas llegan solas, cualquier
oferta que estés viendo entra con un clic y, si quieres, el agente recorre portales por ti.

## Alcance

### 09b.1 · Ofertas resumen y alertas por correo
1. **Migración** según `FUENTES_OFERTAS.md` §Modelo de datos: `jobs.platform`,
   `jobs.detail_level`, índice único parcial (`platform`, `external_id`), tablas `source_runs` y
   `email_messages`, tipos nuevos de `sources`.
2. **Pipeline**: etapa `pending_detail`, evento `detail_captured`, y `discarded`/`expired` desde
   `pending_detail` en `pipeline.TRANSITIONS`. Actualiza los tests de combinaciones evento × etapa.
3. **Identidad por plataforma** (`services/platforms.py`): detectar `platform` y `external_id` a
   partir de una URL (LinkedIn `/jobs/view/<id>` y `currentJobId=`; InfoJobs, Indeed y Tecnoempleo
   según sus patrones de URL, verificándolos con ejemplos reales antes de fijarlos).
4. **Prefiltro de resúmenes** en código: título y ubicación contra `preferences` y los filtros
   duros evaluables sin descripción. Orden de la bandeja por ese prefiltro.
5. **Conector de correo** (`services/ingestion/email/`): IMAP en solo lectura sobre una carpeta, o
   carpeta `data/inbox/` con `.eml`/`.mbox`. Parsers por plataforma elegidos por remitente y un
   parser genérico por patrones de URL. Para cada oferta: si la plataforma permite descargar la
   página, alta completa con el servicio de la fase 03; si no (LinkedIn), alta `summary` en
   `pending_detail`. Registrar `Message-ID` y `source_runs`.
6. **Parsers reales**: pide al usuario que deje una alerta real de cada plataforma que use en
   `data/inbox/samples/`. Construye el parser con ella y crea un fixture **inventado** con la misma
   estructura para los tests. Nunca copies nombres, enlaces ni datos reales a los fixtures.
7. **Expiración**: tarea diaria que cierra con `expired` los resúmenes más antiguos que
   `summary_expire_days`.
8. **UI**: vista «Alertas» con las ofertas `pending_detail` (título, empresa, ubicación, plataforma,
   prefiltro), botones «Abrir» (abre la URL en una pestaña nueva) y «Descartar» con atajo de teclado.
9. `jh doctor`: comprueba la conexión IMAP si está configurada (solo login y selección de carpeta
   en modo lectura).

### 09b.2 · Botón «Enviar a Job Hunter»
1. **API**: `POST /api/capture` con token (`jh capture token` genera y rota el token en
   `data/capture_token`), CORS solo para el origen de la extensión configurado en `.env`
   (`JH_CAPTURE_EXTENSION_ID`). Servicio `services/capture.py`: identifica plataforma, completa
   una oferta resumen existente (`detail_captured`), detecta duplicados o crea una oferta nueva.
   Detección de riesgo sobre el texto capturado.
2. **Extensión** en `extension/` (Manifest V3): `action` + `activeTab` + `scripting` + `storage`;
   `host_permissions` solo `http://127.0.0.1:8000/*`. Extractores por sitio con respaldo a JSON-LD
   y a `main`; si hay texto seleccionado, manda ese. Página de opciones para el token. Mensaje de
   resultado en el botón. Sin dependencias ni paso de build (JavaScript plano).
3. **README de la extensión** con los pasos para cargarla en Chrome y Edge.
4. **Tests**: servicio de captura (nueva, completa un resumen, duplicada, token inválido) y
   extractores de la extensión contra HTML de ejemplo **inventado** (Vitest o Node).

### 09b.3 · Plataformas y búsqueda con navegador
1. **Interfaz para agentes** (MCP y CLI con paridad): `list_sources`, `save_source` y
   `record_source_run`, y los campos nuevos de `add_job_from_text`, según
   `FUENTES_OFERTAS.md` §Interfaz. `save_source` rechaza `allow_agent_browsing: true` en LinkedIn.
2. **UI «Plataformas»**: lista, prioridad, acceso, última ejecución y resultados. El interruptor
   `allow_agent_browsing` de LinkedIn muestra el aviso de riesgo y pide confirmación.
3. Configuración por defecto en `config/policies.yaml` → `agent_browse`.

## Fuera de alcance
Candidaturas automáticas, resolver captchas, publicar la extensión en tiendas, Firefox.

## Criterios de aceptación
- Una alerta de LinkedIn (fixture inventado) crea ofertas `pending_detail`; capturar después una
  de ellas con el endpoint la completa y la lleva a `pending_extraction` sin duplicarla.
- Procesar dos veces el mismo correo no crea nada nuevo.
- El conector IMAP nunca modifica el buzón (test con un servidor IMAP falso que falle ante
  cualquier escritura).
- `save_source` no puede activar la navegación en LinkedIn.
- Prueba manual: cargar la extensión, enviar una oferta real de LinkedIn y generar su CV.
- Prueba manual de `buscar-ofertas` con una plataforma de acceso libre.

## Al terminar
Actualiza `docs/ROADMAP.md` y `docs/AGENTS_COMPAT.md` (qué agentes han podido usar
`buscar-ofertas` con el navegador del usuario). Explica al usuario cómo crear en cada portal las
búsquedas con alerta y el filtro de correo que las lleve a la carpeta configurada.
