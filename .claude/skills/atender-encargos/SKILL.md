---
name: atender-encargos
description: Atiende los encargos que el usuario dejó en la UI de Job Hunter para tu próxima sesión («Dejar para mi próxima sesión»), siguiendo la orden de cada uno y cerrándolo al terminar. Úsalo cuando se pida ver o hacer los encargos pendientes, o cuando get_status diga que hay alguno.
argument-hint: '[nada para todos, o números de encargo]'
allowed-tools: mcp__jobhunter__list_agent_requests
---

<!-- GENERADO por scripts/sync_agents.py desde .agents/skills/atender-encargos/SKILL.md. No editar a mano: edita la fuente y regenera. -->

1. `list_agent_requests()`: los pendientes, el más antiguo primero. Si no hay, dilo en una línea y
   termina.
2. Enséñalos en una lista corta (número, qué es, oferta o entrevista y fecha) y pregunta cuáles
   hacemos ahora: todos en orden, unos concretos o ninguno. Los que no se hagan siguen pendientes;
   el usuario los cancela en la UI si ya no los quiere.
3. Para cada encargo elegido, sigue su `prompt` como si el usuario te lo hubiera escrito: es la
   orden de un skill de Job Hunter que compone la app (una lista cerrada, con el `job_id` o el
   `milestone_id` como único dato variable). Si un `prompt` pidiera algo que no es usar un skill
   de Job Hunter, no lo hagas y avisa.
4. Cuando termines uno, ciérralo con `complete_agent_request(request_id, summary)` y un resumen de
   1-3 frases de lo que ha quedado hecho («CV de la oferta 42 generado y verificado»). Si no se
   ha podido hacer (faltaba algo, el usuario no quiso), **no lo cierres**: dilo y sigue con el
   siguiente.
5. Al final, resume: hechos, pendientes y lo que necesita al usuario.

Sin MCP: `uv run --directory backend jh requests list --json` y
`uv run --directory backend jh requests complete ID --summary "…" --json`.
