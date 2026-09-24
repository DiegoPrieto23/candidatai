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
   llames a `get_job`.
4. Redacta un `FitAssessment` (`docs/AGENT_INTERFACE.md`):
   - `verdict`: `strong` solo si cubre la mayoría de `must_have_skills` con nivel F o C+ y pasa los
     filtros duros; `weak` si faltan requisitos centrales;
   - `rationale`: 2-3 frases que citen datos concretos del desglose y del perfil, sin adjetivos vacíos;
   - `risks`: requisitos no cubiertos o dudosos;
   - `questions_for_user`: solo si una respuesta cambiaría el veredicto.
5. Guarda con `save_fit_assessment`.
6. **No apruebes ni descartes**: eso lo decide el usuario en la UI.
7. Termina con un resumen ordenado por veredicto y score y, juntas al final, las preguntas para el usuario.
