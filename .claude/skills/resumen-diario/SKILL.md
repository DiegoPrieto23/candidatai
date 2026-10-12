---
name: resumen-diario
description: Resumen breve del estado de la búsqueda en Job Hunter (pendientes, seguimientos vencidos, próximos hitos). Úsalo cuando se pida un resumen, "qué tengo hoy" o como tarea programada matinal.
allowed-tools: mcp__jobhunter__get_status mcp__jobhunter__list_followups_due mcp__jobhunter__list_upcoming mcp__jobhunter__list_jobs
---

<!-- GENERADO por scripts/sync_agents.py desde .agents/skills/resumen-diario/SKILL.md. No editar a mano: edita la fuente y regenera. -->

1. `get_status`, `list_upcoming(days=7)`, `list_followups_due()` y
   `list_jobs(stage="pending_triage", limit=5)`.
2. Escribe un resumen de 10 líneas como máximo, en este orden:
   - **Hoy y mañana**: entrevistas, pruebas y plazos, con hora (Europe/Madrid);
   - **Seguimientos vencidos**: empresa, puesto y días sin respuesta; ofrece redactar el mensaje de seguimiento;
   - **Por procesar**: cuántas en `pending_extraction` (sugiere el skill `procesar-ofertas`) y las
     5 mejores de triaje por score;
   - **Encargos**: si `get_status` trae `agent_requests` > 0, cuántos te dejó el usuario en la UI
     (sugiere el skill `atender-encargos`);
   - **Semana**: nada si no hay novedades.
3. Si nada requiere acción, dilo en una línea.
