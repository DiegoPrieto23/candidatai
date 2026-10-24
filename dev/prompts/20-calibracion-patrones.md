# Fase 20 · Calibración y patrones

Plan 13-22 (`dev/ROADMAP.md`). Rama `fase/20-calibracion-patrones`. Inspirada en `calibrate`,
`patterns` y `stats` de career-ops. Tiene sentido a partir de unas 20-30 candidaturas enviadas.

## Contexto
Lee `services/analytics.py` (fase 10.2), `docs/DATA_MODEL.md` §Embudo y la valoración del encaje
(`matches.assessment`).

## Objetivo
Saber si el score y el veredicto predicen respuestas de verdad, y dónde rinde más tu tiempo.

## Alcance
1. **Consultas** (SQL, en `services/analytics.py`): tasa de respuesta y de entrevista de las
   enviadas por tramo de score (p. ej. <60, 60-74, 75-84, ≥85), por veredicto del agente, por
   fuente y portal, por plantilla de CV, con o sin carta, con o sin referencia (fase 18) y por
   días entre alta y envío. Con número de casos e intervalo, y «pocos datos» por debajo de un
   mínimo.
2. **UI**: sección «¿Acierta el score?» en Embudo, con el aviso de que es orientativa.
3. **Herramienta** `get_calibration` → `jh stats calibration --json` y skill `revisar-busqueda`
   (retrospectiva semanal: qué funciona, qué cambiar), que **nunca** cambia pesos ni filtros:
   solo propone, y los cambios en `config/policies.yaml` los decide el usuario con
   `jh eval matching` como red de seguridad.
4. **Docs**: `AGENT_INTERFACE.md`, `evals/matching/README.md`.

## Fuera de alcance
Ajustar pesos automáticamente.

## Criterios de aceptación
- Tests con histórico sintético y cifras exactas; paridad MCP ↔ CLI.
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde.
