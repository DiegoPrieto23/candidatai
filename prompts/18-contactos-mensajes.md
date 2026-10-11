# Fase 18 · Red de contactos, mensajes e investigación de empresas

Plan 13-22 (`docs/ROADMAP.md`). Rama `fase/18-contactos-mensajes`. Inspirada en `contacto`,
`email`, `deep` y el cruce con la exportación de LinkedIn de career-ops.

## Contexto
Lee `docs/DATA_MODEL.md` (`contacts`, fase 10.1), `docs/POLICIES.md` §4 (privacidad) y §5 (nada
sale sin confirmación), §7 (la carta solo usa la extracción y las indicaciones del usuario) y
`data/documentos/linkedin/` (fase 13).

## Objetivo
Aprovechar a la gente que ya conoces y escribir a la adecuada, sin automatizar nada en LinkedIn.

## Alcance
1. **Importar tus contactos de LinkedIn**: `jh contacts import-linkedin data/documentos/linkedin/Connections.csv`
   (la exportación oficial que descarga el usuario). Tabla `network_contacts` (migración) separada
   de los contactos de cada proceso. Nada de navegar LinkedIn.
2. **Cruce con tus ofertas**: en la ficha y en el triaje, «Conoces a 2 personas en Acme» con sus
   cargos; acción «Añadir como contacto del proceso» (con rol: referencia, recruiter, responsable).
3. **Mensajes**: skill `redactar-mensaje`: borrador para recruiter, responsable del puesto o
   compañero (≤ 300 caracteres para LinkedIn, o correo de candidatura con asunto, cuerpo y lista
   de adjuntos), usando solo el perfil, la extracción y el contexto. Se guarda en la ficha con
   botón de copiar. Nunca se envía.
4. **Investigación de empresa**: skill `investigar-empresa`: dosier con fuentes (web pública) sobre
   la empresa (producto, noticias recientes, cultura de ingeniería, stack) guardado en la ficha y
   en `data/documentos/candidaturas/…`. Lo usan `preparar-entrevista` y `redactar-mensaje`. La
   carta sigue sin poder usar datos de empresa que no estén en la extracción o en tus indicaciones
   (§7), salvo que tú los copies a las indicaciones de esa oferta.
5. **Referencias**: evento o marca «referencia pedida / dada» en el contacto del proceso y columna en
   el embudo para medir si las referencias convierten más.
6. **Docs**: `POLICIES.md`, `DATA_MODEL.md`, `AGENT_INTERFACE.md`.

## Fuera de alcance
Enviar mensajes o invitaciones. Buscar perfiles en LinkedIn desde el código o el agente.

## Criterios de aceptación
- Importación con un CSV ficticio en `demo/` (formato real de LinkedIn) y tests de cruce por
  empresa normalizada.
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde.
