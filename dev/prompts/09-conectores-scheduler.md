# Fase 09 · Conectores de ATS y scheduler

## Contexto
Lee `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md` (§sources, §companies, §tasks) y `docs/POLICIES.md` §6.

## Objetivo
Que las ofertas de tus empresas objetivo y de tus búsquedas guardadas lleguen solas cada día.

## Alcance
1. Interfaz `Connector` en `app/services/ingestion/`: `fetch(source) -> list[RawJob]`.
   Cada conector es idempotente y respeta la deduplicación de la fase 03.
2. Conectores a los endpoints públicos de ofertas de cada ATS. **Verifica la URL y el formato
   actuales de cada endpoint contra su documentación oficial antes de implementarlo**:
   - Greenhouse (Job Board API, por `board_token`, con contenido);
   - Lever (Postings API, por nombre de empresa);
   - Ashby (Posting API del job board, por nombre).
   Sin autenticación ni scraping. Si un endpoint cambia o falla, el conector registra el error y
   continúa con el resto.
3. Opcionales, desactivados por defecto y detrás de claves en `.env`: InfoJobs API y Adzuna API.
   Si no hay claves, se omiten con un aviso.
4. Filtro previo barato antes de guardar: palabras clave de título y ubicación desde
   `preferences`, para no llenar la BD de ofertas irrelevantes.
5. **Worker**: `jh worker` con APScheduler, que ejecuta los conectores activos a la hora
   configurada y procesa la tabla `tasks` (reintentos con backoff, `last_error`).
6. **Lista de empresas objetivo**: pantalla en la UI para añadir una empresa (nombre + ATS + slug)
   y probar el conector al momento ("12 ofertas encontradas, 3 tras filtros").
   CLI equivalente: `jh sources add|list|test|run`.
7. Tras cada ejecución, las ofertas nuevas quedan en `pending_extraction`.

## Fuera de alcance
Scraping de portales con anti-bot. LinkedIn.

## Criterios de aceptación
- Tests de cada conector con respuestas grabadas (respx), incluidos errores HTTP y JSON inesperado.
- Ejecutar dos veces seguidas no duplica nada.
- `jh worker` en primer plano muestra un log legible de cada ejecución.

## Al terminar
Actualiza `dev/ROADMAP.md`. Explica al usuario cómo hacer que la extracción también ocurra sola cada
mañana: con una tarea programada de su agente, si la ofrece (p. ej. las tareas programadas locales
de Claude Code Desktop), ejecutando el skill `procesar-ofertas`. Si su agente no la ofrece,
`resumen-diario` le recordará lo pendiente. Documenta las opciones en `docs/AGENTS_COMPAT.md`.
