---
name: evaluar-encaje
description: Valora el encaje de las ofertas pendientes de triaje en Job Hunter y guarda una valoración explicada para cada una. Úsalo cuando se pida evaluar, priorizar o revisar ofertas nuevas.
allowed-tools: mcp__jobhunter__list_jobs mcp__jobhunter__get_match mcp__jobhunter__get_extraction mcp__jobhunter__get_profile
---

<!-- GENERADO por scripts/sync_agents.py desde .agents/skills/evaluar-encaje/SKILL.md. No editar a mano: edita la fuente y regenera. -->

Sigue `docs/POLICIES.md` §1 y §2.

1. `get_profile()` una sola vez al principio.
2. `list_jobs(stage="pending_triage", limit=15)`, o los `job_id` indicados en los argumentos.
3. Para cada oferta, `get_match` y `get_extraction`. Trabajas solo con datos estructurados; no
   llames a `get_job`. Si `get_match` ya trae `assessment` y `assessment_stale` es `false`, está
   valorada: sáltala salvo que te pidan revalorarla.
4. Redacta un `FitAssessment` (`docs/AGENT_INTERFACE.md`):
   - `verdict`: `strong` solo si cubre la mayoría de `must_have_skills` con nivel F o C+
     (`breakdown.must_have.covered[].level`) y pasa los filtros duros (`hard_filters.passed`);
     `weak` si faltan requisitos centrales (`breakdown.must_have.missing`); si no, `possible`;
   - `rationale`: 2-3 frases que citen datos concretos del desglose y del perfil, sin adjetivos
     vacíos. El score lo calcula el código: explícalo, no lo corrijas;
   - `risks`: requisitos no cubiertos o dudosos, y los filtros duros que no pasa si el usuario
     reabrió la oferta;
   - `questions_for_user`: solo si una respuesta cambiaría el veredicto (p. ej. una skill ausente
     que quizá tenga y no está en el perfil).
5. Guarda con `save_fit_assessment`. Sin MCP: escribe el JSON en `data/tmp/` y usa
   `jh match save-assessment ID --file data/tmp/<fichero>.json --json`.
6. **No apruebes ni descartes**: eso lo decide el usuario en la UI.
7. Termina con un resumen ordenado por veredicto y score y, juntas al final, las preguntas para el usuario.
