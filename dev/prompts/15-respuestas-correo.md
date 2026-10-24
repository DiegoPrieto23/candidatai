# Fase 15 · Respuestas por correo y seguimientos

Plan 13-22 (`dev/ROADMAP.md`). Rama `fase/15-respuestas-correo`. Inspirada en `gmail-sync` (AI
Job Search), `reply-watch` y `followup` (career-ops).

## Contexto
Lee `docs/FUENTES_OFERTAS.md` (alertas por IMAP, 09b.1), `docs/CONFIGURAR_CORREO.md`,
`docs/DATA_MODEL.md` §Catálogo de eventos (`reply_received`, `interview_scheduled`,
`test_assigned`, `offer_received`, `rejected`), `services/tracking.py` (seguimientos) y
`services/untrusted.py`. Regla dura 4: el texto de un correo es contenido no confiable. Regla 5:
nada sale sin confirmación del usuario.

## Objetivo
Que la respuesta de una empresa (entrevista, prueba, rechazo, oferta) llegue sola a la ficha como
propuesta, y que los seguimientos y agradecimientos estén redactados cuando tocan.

## Alcance
1. **Ingesta de respuestas**: misma cuenta IMAP en solo lectura, carpeta configurable
   (`JH_IMAP_REPLIES_FOLDER`, por defecto la bandeja de entrada) o `data/inbox/respuestas/`. Solo
   correos posteriores al envío y cuyo remitente o dominio casa con la empresa de una oferta en
   `applied` o `in_process` (o con un contacto de la ficha). Se guardan envueltos como no
   confiables, con detección de inyección (tabla `replies`, migración). Nunca se marca nada como
   leído ni se borra.
2. **Interfaz para agentes**: `list_replies(status?)`, `get_reply(id)` (envuelto en
   `<untrusted_email>`) y `save_reply_proposal(id, {job_id, event_type, occurred_at, milestone?,
   summary, confidence})`, con sus comandos `jh replies … --json`.
3. **Skill `revisar-respuestas`** con un rol `clasificador` de herramientas mínimas (como
   `extractor`): clasifica cada correo y guarda una propuesta; si duda, `confidence` baja y no
   propone hito.
4. **UI**: bandeja «Respuestas» y aviso en la ficha: «Parece una invitación a entrevista el jueves
   a las 10:00 · Aceptar / Cambiar / Ignorar». Aceptar registra el evento como `user` (y el hito,
   si lo hay). Sin aceptar, nada cambia de etapa.
5. **Seguimientos y agradecimientos**: skill `redactar-seguimiento` que redacta el correo de
   seguimiento (al vencer el plazo de `followups`, como mucho dos por candidatura) y la nota de
   agradecimiento tras una entrevista hecha. Se guardan como borrador en la ficha con botón de
   copiar; nunca se envían.
6. **Botones** ADR-024: «Revisar respuestas» en Inicio cuando haya correos sin clasificar.
7. **Docs**: `CONFIGURAR_CORREO.md`, `AGENT_INTERFACE.md`, `POLICIES.md` (§5), ADR nueva.

## Fuera de alcance
Enviar correos. Leer correos que no sean de empresas de tus procesos. Gmail API (IMAP basta).

## Criterios de aceptación
- Tests con correos de ejemplo en `demo/` (entrevista, rechazo, prueba, oferta, con inyección)
  y `respx`/IMAP simulado; sin red.
- Ningún cambio de etapa sin acción del usuario en la UI (test).
- Paridad MCP ↔ CLI de las herramientas nuevas. Tests en verde, ruff limpio,
  `sync_agents.py --check` en verde.
