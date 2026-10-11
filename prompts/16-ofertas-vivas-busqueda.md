# Fase 16 · Ofertas vivas, republicadas y búsqueda ampliada

Plan 13-22 (`docs/ROADMAP.md`). Rama `fase/16-ofertas-vivas-busqueda`. Inspirada en `--verify`,
`detect-reposts`, `titles` y `discover` de career-ops.

## Contexto
Lee `docs/FUENTES_OFERTAS.md`, `services/ingest.py` (huella y duplicados), `services/platforms.py`
(ADR-016: el código nunca descarga páginas de LinkedIn), los conectores de Greenhouse, Lever y
Ashby (fase 09) y `services/ingestion/prefilter.py`.

## Objetivo
No perder tiempo en ofertas cerradas o fantasma, y encontrar puestos y empresas que hoy se escapan.

## Alcance
1. **¿Sigue abierta?**: tarea del worker que comprueba la URL de una oferta (salvo LinkedIn) con
   petición ligera: 404/410, redirección a una lista, o patrones de «oferta cerrada» por portal
   (InfoJobs, Indeed, Tecnoempleo, ATS). Resultado en `risk_flags` (`possibly_closed`, con fecha)
   y aviso en la ficha. Se ejecuta antes de `generar-cv` (aviso en el botón) y una vez al día para
   las aprobadas y con CV listo. Nunca cierra la oferta sola: propone descartarla.
2. **Republicadas**: misma empresa y título normalizado (con `title_aliases`) visto varias veces
   en N días, aunque cambie la URL → `risk_flags: reposted` con el número de veces y fechas;
   insignia «Republicada ×3» en bandeja y triaje. Es una observación, no un veredicto.
3. **Títulos parecidos**: skill `ampliar-busqueda` que, con las aprobadas y descartadas, propone
   títulos cercanos (p. ej. «Data Platform Engineer», «BI Engineer») y, si el usuario acepta, los
   añade a `preferences.roles` o a las búsquedas de sus plataformas (`save_source`).
4. **Descubrir empresas**: `jh sources discover --file empresas.txt` resuelve cada empresa a su
   tablero de Greenhouse, Lever o Ashby probando los slugs públicos de esas APIs (sin agente ni
   tokens) y propone darlas de alta como fuente.
5. **Docs**: `FUENTES_OFERTAS.md`, `DATA_MODEL.md` (`risk_flags` nuevos).

## Fuera de alcance
Comprobar ofertas de LinkedIn desde el código (ADR-016; ver fase 22). Cerrar ofertas sin el usuario.

## Criterios de aceptación
- Tests con `respx` de cada portal (abierta, cerrada, redirigida) y de republicación.
- `discover` con respuestas simuladas de las tres APIs.
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde.
