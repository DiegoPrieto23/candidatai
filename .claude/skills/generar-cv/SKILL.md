---
name: generar-cv
description: Genera y verifica el CV a medida para una oferta aprobada de Job Hunter. Úsalo cuando se pida un CV para una oferta concreta o para las aprobadas sin CV.
argument-hint: '[job_id o ''pendientes'']'
allowed-tools: mcp__jobhunter__list_jobs mcp__jobhunter__get_match mcp__jobhunter__get_extraction
---

<!-- GENERADO por scripts/sync_agents.py desde .agents/skills/generar-cv/SKILL.md. No editar a mano: edita la fuente y regenera. -->

Sigue `docs/POLICIES.md` §1, §3 y §4.

1. Si los argumentos dicen `pendientes` o no hay argumentos, usa `list_jobs(stage="approved")`; si
   no, trabaja con los `job_id` indicados. Si hay más de 5, pregunta si seguimos con todos.
2. **Preguntas antes de redactar.** Para cada oferta, mira en `get_match` las skills obligatorias
   ausentes del perfil y haz todas esas preguntas juntas en un solo mensaje ("¿Has trabajado con
   Airflow?"). Si alguna respuesta es sí, para: primero hay que añadirla al perfil con el skill
   `actualizar-perfil`. Nunca la metas en el CV sin que esté en el perfil.
3. Para cada oferta, delega en el rol `redactor` con el `job_id` y las indicaciones del usuario
   (idioma forzado, qué proyecto destacar…).
4. Cuando devuelva el `document_id`, delega en el rol `verificador` con ese id. Tiene que ser una
   ejecución distinta de la del redactor: la independencia es el sentido del paso.
5. Si la verificación falla o hay aviso `too_long`, devuelve los problemas al `redactor` para una
   nueva versión. Máximo 2 vueltas; después, para y enseña los problemas.
6. Resume por oferta: ruta del PDF, páginas, keywords cubiertas y ausentes, y resultado de la verificación.
