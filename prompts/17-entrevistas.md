# Fase 17 · Entrevistas: simulacro, repaso y banco de historias

Plan 13-22 (`docs/ROADMAP.md`). Rama `fase/17-entrevistas`. Inspirada en `/interview` (AI Job
Search) e `interview/plan`, `practice`, `debrief` e `interview-redflag` (career-ops).

## Contexto
Lee el skill `preparar-entrevista`, `stories` del perfil (historias STAR), la ficha de proceso
(hitos `interview`, contactos; fase 10.1) y `data/contexto/` (fase 13).

## Objetivo
Llegar a cada entrevista con un plan y práctica, y aprender de cada una.

## Alcance
1. **Plan de preparación**: `preparar-entrevista` genera, además del dosier, un plan por días
   hasta la fecha del hito (bloques de 30-60 min) y lo guarda en la ficha.
2. **Simulacro**: skill `simular-entrevista`: una pregunta cada vez (RR. HH., técnica o caso, según
   el tipo de entrevista), espera la respuesta, da feedback concreto y propone una versión mejor
   basada solo en el perfil. Al final, resumen de puntos fuertes y flojos.
3. **Repaso posterior**: skill `repasar-entrevista`: el usuario cuenta cómo fue; se guardan notas
   en el hito (herramienta `save_interview_notes(milestone_id, notes, next_steps)` con su
   comando `jh`), se predice la siguiente ronda y se proponen historias nuevas para `stories`
   (siempre vía `actualizar-perfil`, con confirmación).
4. **Señales de alarma antes de aceptar**: en `offer_received`, el skill revisa lo que hay en la
   ficha, la extracción y las notas de entrevistas y lista dudas que conviene aclarar.
5. **Botones** ADR-024 en el hito: «Preparar», «Simulacro», «Repasar».
6. **Docs**: `AGENT_INTERFACE.md`, skills.

## Fuera de alcance
Grabar audio o vídeo. Buscar a los entrevistadores en LinkedIn desde el código.

## Criterios de aceptación
- `save_interview_notes` con paridad y tests; las notas aparecen en la ficha.
- Ningún hecho nuevo entra en el perfil sin pasar por `actualizar-perfil`.
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde.
