---
name: preparar-candidatura
description: Prepara respuestas de screening y, si procede, carta de presentación (con el skill generar-carta) para una oferta de Job Hunter con CV listo. Úsalo cuando se pida preparar una candidatura o responder preguntas de un formulario.
---

Sigue `docs/POLICIES.md` §1, §4, §5 y §7. Argumentos: `job_id` y, opcionalmente, las preguntas
pegadas del formulario o la palabra `carta`.

1. Carga `get_extraction`, `get_profile` y `get_cv_content` del `job_id`.
2. Si hay preguntas del formulario, respóndelas una a una: en el idioma de la pregunta, directas
   y con `evidence`: ids del perfil (logros, proyectos, historias STAR…), `extraction` o `user`.
   - Salario, disponibilidad exacta, permiso de trabajo o cualquier dato que no esté en el perfil
     público: `needs_user_input: true` y la respuesta vacía (no hay campo de nota: di qué hace
     falta al enseñar el resultado; la UI la marca como pendiente).
   - Preguntas tipo "¿Por qué quieres trabajar aquí?": usa solo la extracción de la oferta y lo
     que cuente el usuario; no inventes datos de la empresa.
3. Carta de presentación solo si la oferta la pide o si los argumentos incluyen `carta`: sigue el
   skill `generar-carta` con este `job_id` (es un documento propio, con sus indicaciones y su
   verificación). Si ya hay una carta verificada, no la rehagas: dilo y sigue.
4. Guarda con `save_application_answers`.
5. Enseña el resultado para revisarlo: el usuario lo ve, lo edita y lo copia en la sección
   «Paquete de candidatura» de la ficha. **No envíes nada ni abras formularios**: el envío es de la
   fase 11 y siempre desde la UI.
