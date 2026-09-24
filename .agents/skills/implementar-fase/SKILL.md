---
name: implementar-fase
description: Implementa una fase del roadmap de Job Hunter a partir de su encargo en prompts/. Úsalo solo cuando el usuario pida explícitamente implementar una fase.
---

Vas a implementar la fase de Job Hunter indicada en los argumentos (p. ej. `03`).

1. Localiza `prompts/<NN>-*.md`. Si no existe, lista los encargos disponibles y para.
2. Lee el encargo y los documentos que cita en «Contexto». Consulta `docs/ROADMAP.md`: si alguna
   fase anterior no está ✅, avisa y pregunta si seguimos.
3. **Antes de editar nada**, presenta un plan breve: ficheros que crearás o cambiarás, migraciones,
   dependencias nuevas, tests y cualquier duda o ambigüedad del encargo. Espera el OK.
4. Implementa en pasos pequeños. Después de cada paso, ejecuta los tests afectados y ruff. Si algo
   del encargo choca con `AGENTS.md` o con `docs/`, para y pregunta: los docs mandan salvo que
   decidamos cambiarlos (y entonces se añade un ADR en `docs/DECISIONS.md`).
5. Comprueba los criterios de aceptación uno a uno, ejecutando de verdad los comandos. Di cuáles
   requieren una prueba manual del usuario y cómo hacerla.
6. Delega en el rol `revisor` la revisión de los cambios de la fase y aplica lo razonable.
7. Cierra: ejecuta `uv run scripts/sync_agents.py --check`, marca la fase en `docs/ROADMAP.md`,
   añade una entrada al registro (fecha, agente usado, resumen, decisiones y deuda pendiente) y
   propón un mensaje de commit. No hagas commit sin que te lo pidan.

Si la fase es demasiado grande para una sesión, propón partirla en subfases y hazlas de una en una.
