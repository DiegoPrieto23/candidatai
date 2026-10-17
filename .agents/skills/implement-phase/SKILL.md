---
name: implement-phase
description: Implementa una fase del roadmap de CandidatAI a partir de su encargo en prompts/. Úsalo solo cuando el usuario pida explícitamente implementar una fase. Antes se llamaba implementar-fase.
---

Vas a implementar la fase de CandidatAI indicada en los argumentos (p. ej. `03`).

1. Localiza el encargo: `prompts/<fase>-*.md`, donde la fase puede llevar letra (`05b`, `08b`). Si
   no existe, lista los encargos disponibles y para.
2. Lee el encargo y los documentos que cita en «Contexto». Consulta `docs/ROADMAP.md`: si alguna
   fase anterior no está ✅, avisa y pregunta si seguimos.
3. **Antes de editar nada**, presenta un plan breve: ficheros que crearás o cambiarás, migraciones,
   dependencias nuevas, tests y cualquier duda o ambigüedad del encargo. Espera el OK.
4. Con el OK, crea la rama de la fase desde `main` al día: `fase/NN-<slug>`, con el nombre del
   fichero del encargo (ver «Git» en `AGENTS.md`). Si hay cambios sin commitear o no estás en
   `main`, avisa y pregunta antes de crearla.
5. Implementa en pasos pequeños. Después de cada paso, ejecuta los tests afectados y ruff. Si algo
   del encargo choca con `AGENTS.md` o con `docs/`, para y pregunta: los docs mandan salvo que
   decidamos cambiarlos (y entonces se añade un ADR en `docs/DECISIONS.md`).
6. Comprueba los criterios de aceptación uno a uno, ejecutando de verdad los comandos. Di cuáles
   requieren una prueba manual del usuario y cómo hacerla.
7. Delega en el rol `reviewer` la revisión de los cambios de la fase y aplica lo razonable.
8. Cierra: ejecuta `uv run scripts/sync_agents.py --check`, marca la fase en `docs/ROADMAP.md`,
   añade una entrada al registro (fecha, agente usado, resumen, decisiones y deuda pendiente),
   actualiza la sección «Sin publicar» de `CHANGELOG.md` con lo que note quien usa la app (en su
   grupo: Añadido, Cambiado, Eliminado, Corregido, Seguridad…) y propón un mensaje de commit.
   No hagas commit sin que te lo pidan; cuando lo pidan, va a la rama de la fase. Fusionar en
   `main` o hacer push, solo si lo piden.

Si la fase es demasiado grande para una sesión, propón partirla en subfases y hazlas de una en una.
