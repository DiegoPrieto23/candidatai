# Fase 06 · Frontend base

## Contexto
Lee `docs/ARCHITECTURE.md` y `docs/DATA_MODEL.md` §Catálogo de eventos.

## Objetivo
Una UI usable para ver y dar de alta ofertas, con la base técnica que usarán las fases siguientes.

## Alcance
1. API FastAPI (`app/api/`): `GET /jobs?stage=&q=&limit=&offset=`, `GET /jobs/{id}` (con
   extracción, eventos y aviso de inyección), `POST /jobs/url`, `POST /jobs/text`,
   `POST /jobs/{id}/events` (solo eventos de actor `user`) y `GET /status`.
   CORS solo para `http://127.0.0.1:5173`. La API escucha únicamente en 127.0.0.1.
2. `jh serve` levanta uvicorn.
3. Frontend: Tailwind + shadcn/ui, React Router, TanStack Query, y cliente generado con
   `openapi-typescript` + `openapi-fetch` (script `pnpm gen:api`).
4. Pantallas:
   - **Bandeja**: tabla filtrable por etapa con búsqueda, empresa, título, modalidad, fecha y
     etiqueta de etapa.
   - **Ficha de oferta**: extracción legible (skills obligatorias y deseables, seniority,
     modalidad, salario si hay), texto original plegado, línea de tiempo de eventos (con el agente
     que registró cada uno, si se conoce), aviso visible si hay `risk_flags` o
     `injection_suspected` y botón para añadir nota.
   - **Alta**: pestañas "Por URL" y "Pegar texto".
   - Cabecera con recuentos por etapa y un recordatorio si hay ofertas en `pending_extraction`:
     "Ejecuta el skill procesar-ofertas en tu agente".
5. Modo claro/oscuro y diseño que funcione a 1280 px y en móvil.

## Fuera de alcance
Triaje, kanban, dashboard.

## Criterios de aceptación
- Tests de API con `TestClient`; tests de componentes clave con Vitest + Testing Library.
- `pnpm build` sin errores de tipos.
- Flujo manual: dar de alta desde la UI → procesar con tu agente → ver la extracción en la ficha.

## Al terminar
Actualiza `docs/ROADMAP.md` y propón mensaje de commit.
