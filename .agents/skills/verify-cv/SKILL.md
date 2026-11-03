---
name: verify-cv
description: Verifica de forma independiente la versión vigente del CV de una oferta de CandidatAI sin cambiar nada de su texto. Úsalo cuando se pida verificar un CV, sobre todo después de editarlo a mano en la ficha.
---

1. `get_cv_content(job_id)` con la oferta de los argumentos: toma su `document_id`. Si no hay CV,
   dilo y termina.
2. Después, delega en el rol `verifier` con ese `document_id`. Tiene que ser una ejecución independiente, y
   guarda el veredicto con `save_cv_verification`.
3. Resume en 1-3 frases el resultado y, si falla, cada problema con su sugerencia. **No cambies el
   texto**: si el usuario quiere arreglarlo, lo edita en la ficha o pide una corrección allí.
