---
name: assess-fit
description: Valora el encaje de las ofertas por revisar en CandidatAI y guarda una valoración explicada para cada una. Úsalo cuando se pida evaluar, priorizar o revisar ofertas nuevas. Antes se llamaba evaluar-encaje.
---

<!-- GENERADO por scripts/sync_agents.py desde .agents/skills/assess-fit/SKILL.md. No editar a mano: edita la fuente y regenera. -->

Sigue `docs/POLICIES.md` §1 y §2.

1. `get_profile()` y `get_context(sections=["criterios"])` una sola vez al principio. Los
   criterios son lo que el candidato busca y no acepta, en texto libre (guardias, viajes, sector…);
   complementan los filtros duros, que ya aplicó el código.
2. `list_jobs(stage="pending_triage", limit=15)`, o los `job_id` indicados en los argumentos.
3. Para cada oferta, `get_match` y `get_extraction`. Trabajas solo con datos estructurados; no
   llames a `get_job`. Si `get_match` ya trae `assessment` y `assessment_stale` es `false`, está
   valorada: sáltala salvo que te pidan revalorarla.
4. Redacta un `FitAssessment` (esquema: `cai schema fit-assessment --json`):
   - `verdict`: `strong` solo si cubre la mayoría de `must_have_skills` con nivel F o C+
     (`breakdown.must_have.covered[].level`) y pasa los filtros duros (`hard_filters.passed`);
     `weak` si faltan requisitos centrales (`breakdown.must_have.missing`); si no, `possible`;
   - `rationale`: 2-3 frases que citen datos concretos del desglose y del perfil, sin adjetivos
     vacíos. El score lo calcula el código: explícalo, no lo corrijas, y no escribas su número
     (la UI ya lo muestra y cambia si se recalcula);
   - `risks`: requisitos no cubiertos o dudosos, y los filtros duros que no pasa si el usuario
     reabrió la oferta. Si la extracción choca con algo de `criterios.md`, añádelo citándolo
     («criterios.md: «Guardias de fin de semana fijas» — la oferta pide guardias rotativas»). Solo
     con lo que diga la extracción: no lo supongas;
   - un **deal-breaker** de `criterios.md` que la extracción confirma claramente es motivo de
     `weak` aunque el encaje técnico sea bueno; dilo en el `rationale`. Una preferencia (no un
     deal-breaker) solo va en `risks`. Lo dudoso va en `questions_for_user`;
   - **señales de oferta dudosa** (`get_match` → `signals`: `salary_range_wide`,
     `employer_hidden`, `fixed_term`, `stale_repost`, `ai_screening`): cada una va en `risks`
     citándola por su código y su texto («fixed_term: contrato temporal…»). No cambian el score
     ni son motivo de `weak` por sí solas, **salvo** que choquen con un deal-breaker de
     `criterios.md` («criterios.md: «Nada de agencias» — employer_hidden: la publica una
     agencia…»): entonces cuentan como tal deal-breaker;
   - `questions_for_user`: solo si una respuesta cambiaría el veredicto (p. ej. una skill ausente
     que quizá tenga y no está en el perfil).
5. Guarda con `save_fit_assessment`. Sin MCP: escribe el JSON en `data/tmp/` y usa
   `cai match save-assessment ID --file data/tmp/<fichero>.json --json`.
6. **No apruebes ni descartes**: eso lo decide el usuario en la UI.
7. Termina con un resumen ordenado por veredicto y score y, juntas al final, las preguntas para el usuario.

## Esquema y errores
Con MCP, el esquema de lo que guardas viene en la propia herramienta. Sin MCP:
`cai schema fit-assessment --json` (con `--example true`, un ejemplo mínimo válido). Si la app rechaza la entrada,
corrige solo los campos de `details[].field` siguiendo su `hint` y vuelve a enviar, como mucho dos
veces; si sigue fallando, para y explica qué falta.
