# Fase 13 · Contexto y documentos del candidato

Primera del plan 13-22 (ideas de AI Job Search y career-ops adaptadas a Job Hunter; ver
`docs/ROADMAP.md` §Plan 13-22). Rama `fase/13-contexto-documentos`.

## Contexto
Lee `docs/POLICIES.md` §1 (veracidad), `docs/DATA_MODEL.md` (perfil, `profile_versions`),
`backend/app/services/profile.py` (`public_view`) y los skills `actualizar-perfil`, `generar-cv`,
`generar-carta`, `evaluar-encaje` y `preparar-entrevista`. Decisión ya tomada con el usuario:
`data/profile.yaml` sigue siendo la única fuente de **hechos** (lo único que puede citar un CV o
una carta); lo nuevo es **contexto** que orienta y nunca respalda un hecho, igual que
`preferences.cv.instructions`.

## Objetivo
Tener, como AI Job Search, varios ficheros con información distinta del candidato (cómo escribe,
cómo es, qué busca y por qué, qué no acepta) y una carpeta con sus documentos fuente, sin perder la
validación ni la trazabilidad del perfil.

## Alcance
1. **`data/contexto/`** (gitignored, como todo `data/`), ficheros Markdown con nombre fijo, todos
   opcionales:
   - `estilo-redaccion.md`: tono, estructura, palabras que usa y que evita, ejemplos propios;
   - `perfil-conductual.md`: cómo trabaja, fortalezas, test de personalidad si lo tiene (DISC, PI…);
   - `criterios.md`: deal-breakers y preferencias en texto libre (guardias, viajes, tamaño de
     empresa, sectores que no quiere…), que complementan los filtros duros sin sustituirlos;
   - `narrativa.md`: historia profesional, motivación, hacia dónde quiere ir, cómo explicar cambios.
   Plantillas ficticias en `demo/contexto/` (la candidata demo). `jh context init` crea los que
   falten desde las plantillas, vacíos de datos.
2. **Interfaz para agentes**: `get_context(sections?)` → `jh context show [--section] --json`
   (paridad), que devuelve el texto de cada fichero con su hash. Límite de tamaño por fichero
   (p. ej. 20 KB) con aviso. El texto lo escribe el usuario: no es contenido no confiable, pero los
   skills lo tratan como indicaciones, no como hechos.
3. **Skills** que lo usan:
   - `generar-cv` y `generar-carta` (rol `redactor`): `estilo-redaccion.md` para el tono;
   - `evaluar-encaje`: `criterios.md` como riesgos o motivo de `weak` cuando un deal-breaker choca
     con la extracción (citándolo);
   - `preparar-entrevista`: `perfil-conductual.md` y `narrativa.md`;
   - `actualizar-perfil`: propone rellenar los ficheros de contexto en la primera sesión.
   El rol `verificador` marca `blocker` cualquier hecho del CV o la carta que solo esté en el
   contexto.
4. **`data/documentos/`**: `cv/`, `linkedin/` (exportaciones de LinkedIn), `titulos/`,
   `referencias/` y `candidaturas/`. `actualizar-perfil` puede leer de aquí (PDF o texto) para
   crear o ampliar el perfil, siempre confirmando antes de escribir.
5. **Archivo de candidaturas**: al registrar `applied` o `applied_manually`, el worker copia a
   `data/documentos/candidaturas/<empresa>_<puesto>_<job_id>/` el PDF del CV seleccionado, la carta
   (TXT y PDF) y las respuestas de screening (JSON), con un `README.md` con fecha, URL y versión del
   perfil. Idempotente. Si el CV o la carta se rehacen después, no se tocan los archivados.
6. **UI**: en una página «Mi perfil» (o dentro de Plantillas → «Mi CV»), lista de ficheros de
   contexto con estado (vacío, con contenido, tamaño, última modificación) y botón para abrir la
   carpeta; en la ficha de una oferta enviada, enlace a su carpeta archivada.
7. **Docs**: `POLICIES.md` §1 (contexto ≠ hechos), `DATA_MODEL.md` (carpetas), `AGENT_INTERFACE.md`
   (`get_context`), ADR nueva.

## Fuera de alcance
Editar los ficheros desde la UI (se editan en el editor del usuario). Partir `profile.yaml` en
varios ficheros. Subir documentos desde la UI (ya existe `data/uploads/` para plantillas).

## Criterios de aceptación
- `get_context` con paridad MCP ↔ CLI y tests con los ficheros demo.
- El verificador rechaza un CV de prueba con un hecho que solo está en el contexto.
- El archivo de una candidatura se crea al enviar, con el CV y la carta seleccionados, y es
  idempotente.
- Ningún dato personal en tests ni fixtures (solo `demo/`). Tests en verde, ruff limpio,
  `sync_agents.py --check` en verde.
