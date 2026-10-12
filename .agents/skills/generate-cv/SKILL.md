---
name: generate-cv
description: Genera y verifica el CV a medida para una oferta aprobada de CandidatAI. Úsalo cuando se pida un CV para una oferta concreta o para las aprobadas sin CV. Antes se llamaba generar-cv.
---

Sigue `docs/POLICIES.md` §1, §3 y §4.

1. Si los argumentos dicen `pendientes` o no hay argumentos, usa `list_jobs(stage="approved")`; si
   no, trabaja con los `job_id` indicados. Si hay más de 5, pregunta si seguimos con todos.
   **¿Sigue abierta?** Para cada oferta, llama a `check_job_open`. Si responde `possibly_closed`,
   dile al usuario el motivo y pregunta si redactas igualmente; no la descartes tú (eso lo decide
   él en la UI). Con `open`, `unknown` o `skipped`, sigue.
2. **Preguntas antes de redactar.** Para cada oferta, mira en `get_match` las skills obligatorias
   ausentes del perfil y haz todas esas preguntas juntas en un solo mensaje ("¿Has trabajado con
   Airflow?"). Si alguna respuesta es sí, para: primero hay que añadirla al perfil con el skill
   `update-profile`. Nunca la metas en el CV sin que esté en el perfil.
3. **Plantilla y opciones.** Si el usuario las ha indicado en los argumentos o en el chat («con
   foto», «sin foto», «plantilla moderna», «en verde», «sin proyectos»), tradúcelas a
   `CvRenderOptions` (`docs/CV_TEMPLATES.md`); lo que no indique se queda en `null`/`auto` y lo
   resuelve la app con sus reglas. Consulta `list_cv_templates` para usar un `template_id` que exista.
4. Para cada oferta, delega en el rol `writer` con el `job_id`, las `render_options` y las
   indicaciones del usuario (idioma forzado, qué proyecto destacar…). El contenido no depende
   de la plantilla: el redactor solo usa su `capacity` para ajustar la extensión.
5. Cuando devuelva el `document_id`, delega en el rol `verifier` con ese id. Tiene que ser una
   ejecución distinta de la del redactor: la independencia es el sentido del paso.
6. Si la verificación falla o hay aviso `too_long`, devuelve los problemas al `writer` para una
   nueva versión. Máximo 2 vueltas; después, para y enseña los problemas.
7. Resume por oferta: plantilla y foto usadas, ruta del PDF, páginas, keywords cubiertas y
   ausentes, avisos del render (p. ej. `not_ats_friendly`) y resultado de la verificación.
8. Recuerda que cambiar de plantilla, quitar o poner la foto o cambiar el color se hace desde la
   UI (o con `render_cv`) sin volver a redactar: no gasta cuota del agente. Solo hace falta
   volver al `writer` si el nuevo render da `too_long`.
