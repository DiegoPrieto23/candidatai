# Fase 07 · Matching y triaje

## Contexto
Lee `docs/POLICIES.md` §2, `config/policies.yaml`, `docs/AGENT_INTERFACE.md` (`get_match`,
`save_fit_assessment`) y `.agents/skills/evaluar-encaje/SKILL.md`.

## Objetivo
Ordenar las ofertas por encaje real, con explicación, y decidir rápido cuáles seguir.

## Alcance
1. `app/services/matching/hard_filters.py`: seniority, años exigidos, modalidad, ubicaciones
   (preferidas, permitidas, descartadas), idiomas requeridos y palabras de descarte. Parámetros
   del perfil y de `config/policies.yaml`. Devuelve `{passed, failures[]}`.
   Si no pasa: evento `hard_filter_failed` con motivo (reabrible desde la UI).
2. `app/services/matching/skills.py`: normalización con un diccionario de sinónimos editable
   (`config/skill_aliases.yaml`: "PySpark" → "Spark", "MS SQL" → "SQL Server"…) y cobertura
   ponderada por nivel (F=1.0, C+=0.8, C=0.5, B=0.2).
3. `app/services/matching/embeddings.py`: sentence-transformers en CPU con carga perezosa y
   caché en `data/models/`. Similitud entre el resumen del perfil + logros y
   responsabilidades + skills de la oferta.
4. `app/services/matching/scorer.py`: score 0-100 = combinación ponderada según
   `config/policies.yaml`, con desglose completo. Se calcula al guardar una extracción (encola
   una tarea) y al importar una versión nueva del perfil (recalcula todo).
5. Interfaz para agentes: `get_match` y `save_fit_assessment`, en MCP y CLI con paridad.
6. UI de **triaje**: lista de `pending_triage` ordenada por score, tarjeta con score, desglose,
   skills cubiertas y ausentes, valoración del agente si existe y sus preguntas. Botones
   Aprobar / Descartar (motivo obligatorio con opciones rápidas) con atajos de teclado `A` y `D`.
7. **Set de evaluación** `evals/matching/`: formato JSONL (`job_fixture`, `label` ∈
   {encaja, no_encaja}) y `uv run jh eval matching`, que calcule precision, recall y F1 con el
   umbral actual y la curva por umbral. Incluye 20 ejemplos inventados como semilla; el usuario
   añadirá casos reales en `data/evals/`, que también se leen.

## Fuera de alcance
CVs.

## Criterios de aceptación
- Tests de cada filtro duro y del score con perfiles y ofertas de `demo/`.
- `jh eval matching` imprime métricas y guarda el informe en `data/evals/reports/`.
- El triaje de 10 ofertas con teclado es fluido.

## Al terminar
Actualiza `dev/ROADMAP.md` y propón mensaje de commit.
