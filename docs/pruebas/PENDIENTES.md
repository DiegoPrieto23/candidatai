# Pendientes del usuario

Cosas que tiene que hacer el usuario a mano: el agente no puede hacerlas (permisos, cuentas,
navegador, Claude Code cerrado) o necesitan datos reales. El agente añade aquí lo que salga en
cada fase y lo quita cuando el usuario confirma que está hecho.

Marca `[x]` lo que hagas y, si algo falla, apúntalo debajo de la línea con `→`.

Última actualización: 2026-10-12 (fase 23.2).

## 1. Poner la app al día (antes de probar nada)

Desde la raíz del repo, en PowerShell, en `main` y **con Claude Code cerrado** (su servidor MCP
bloquea el entorno de Python):

- [ ] Copia de seguridad de la BD: `copy data\jobhunter.db data\jobhunter.db.bak-0012` (tu BD
      sigue llamándose así: la app la usa tal cual, ver «Nombre nuevo» abajo)
- [ ] `uv sync --directory backend` (dependencias añadidas con `--no-sync`, p. ej. `tzdata`; desde
      la fase 23 instala también los comandos nuevos `cai` y `cai-mcp` en lugar de `jh` y `jh-mcp`)
- [ ] `uv run --directory backend cai db upgrade`: tu BD está en **0012** y el código espera la
      **0021** (`skill_gap_marks` de la fase 14; `replies` y `message_drafts` de la 15;
      `jobs.signals` y `job_sightings` de la 16; plan y repaso de entrevistas en `milestones`
      de la 17; `network_contacts`, referencias, mensajes y `company_research` de la 18;
      `agent_runs` y `agent_requests` de la 19; `received_offers` de la 21; nombres de skill
      en inglés en tus encargos y ejecuciones de la 23.2)
- [ ] `cd frontend; pnpm install`
- [ ] Abrir Claude Code de nuevo para que el servidor MCP cargue las herramientas nuevas
      (`list_replies`, `get_reply`, `save_reply_proposal`, `save_message_draft`, `get_skill_gaps`,
      `check_job_open`, `get_search_titles`, `get_interviews`, `save_interview_plan`,
      `save_interview_notes`, `get_job_contacts`, `get_company_research`,
      `save_company_research`, `list_agent_requests`, `complete_agent_request`,
      `get_calibration`…).
      Comprobar con `/mcp`.

### Nombre nuevo: CandidatAI (fase 23.1)

La herramienta se llama ahora **CandidatAI**: la CLI es `cai` (ya no existe `jh`), el servidor MCP
es `candidatai` y las variables son `CAI_*`. Lo que tienes sigue funcionando: las `JH_*` de tu
`.env` se leen como respaldo y tu `data/jobhunter.db` se usa tal cual. `cai doctor` te recuerda
ambas cosas.

- [ ] Tras `uv sync`, abre Claude Code de nuevo y comprueba con `/mcp` que aparece `candidatai`
      (y no `jobhunter`).
- [ ] En `.env`, renombra cuando quieras cada `JH_…` a `CAI_…` (p. ej. `JH_IMAP_HOST` →
      `CAI_IMAP_HOST`). `uv run --directory backend cai doctor` te dice cuáles quedan.
- [ ] Opcional, con la app parada: renombra `data\jobhunter.db` a `data\candidatai.db` (y sus
      ficheros `-wal`/`-shm` si los hay).
- [ ] Revisa si tienes algo propio que llame a `jh` (accesos directos, scripts, tareas programadas
      o rutinas de tu agente) y cámbialo a `cai`.
- [ ] La extensión del navegador se llama ahora «Enviar a CandidatAI»: en `chrome://extensions`,
      pulsa «Recargar» en ella (el id y el token no cambian).

### Skills en inglés (fase 23.2)

Los skills se llaman ahora en inglés: `/process-jobs`, `/assess-fit`, `/generate-cv 42`,
`/prepare-interview 42`… (tabla en el README). Pedirlo en lenguaje natural, en español, sigue
funcionando. Los roles son `writer`, `verifier`, `classifier`, `reviewer` y `extractor`.

- [ ] Tras `cai db upgrade`, tus encargos pendientes («Dejar para mi próxima sesión») y las
      ejecuciones en cola ya usan los nombres nuevos.
- [ ] Si tienes tareas programadas o rutinas de tu agente que llamen a un skill por su nombre
      antiguo (p. ej. `resumen-diario` cada mañana), cámbialas (`daily-summary`).

## 2. `.env.example` (el agente no puede leerlo ni editarlo)

- [ ] Crear o completar `.env.example`, **sin valores reales**, con todas las variables de
      `backend/app/core/config.py`:
  - generales: `CAI_DATA_DIR`, `CAI_DB_URL`, `SOFFICE_PATH`, `CAI_CLIENT_NAME`, `CAI_AGENT`,
    `CAI_EMBEDDINGS`;
  - portales: `CAI_INFOJOBS_CLIENT_ID`, `CAI_INFOJOBS_CLIENT_SECRET`, `CAI_ADZUNA_APP_ID`,
    `CAI_ADZUNA_APP_KEY`;
  - correo: `CAI_IMAP_HOST`, `CAI_IMAP_PORT`, `CAI_IMAP_USER`, `CAI_IMAP_PASSWORD`,
    `CAI_IMAP_FOLDER` y, de la fase 15, `CAI_IMAP_REPLIES_FOLDER` (por defecto `INBOX`);
  - navegador: `CAI_CAPTURE_EXTENSION_ID`, `CAI_BROWSER_HEADLESS`, `CAI_BROWSER_CHANNEL`,
    `CAI_APPLIER_ALLOW_LOOPBACK`.

## 3. Pruebas manuales pendientes

Cada guía está en `docs/pruebas/`. No consta en el ROADMAP que estén hechas; si alguna ya la
hiciste, márcala.

- [ ] **Fase 22 · LinkedIn por sus endpoints públicos** (`fase-22-prueba-manual.txt`), **solo si
      quieres usarla** (va contra las condiciones de LinkedIn y puede bloquear tu IP un tiempo):
  - comprobar que la tarjeta de LinkedIn de «Fuentes → Plataformas» muestra «Búsqueda pública sin sesión»
    apagada y con las búsquedas que usaría;
  - activarla aceptando el aviso, «Buscar ahora» y ver en «Alertas» los resúmenes nuevos (o el
    aviso de bloqueo, si LinkedIn responde 999 a un user-agent honesto: apúntalo);
  - apagarla al terminar si no la quieres diaria.
- [ ] **Fase 21 · Ofertas recibidas y salario** (`fase-21-prueba-manual.txt`), con la demo o
      cuando llegue la primera oferta:
  - poner `private.salary_floor_eur` en tu perfil (si no, la comparación sale sin mínimo);
  - anotar una oferta en la ficha y verla en «Procesos → Ofertas recibidas»;
  - `/prepare-negotiation`: que no proponga cifras y que no sepa tu mínimo aunque se lo pidas;
  - opcional: crear `data/documentos/salarios.csv` con tus fuentes (formato en
    `demo/salarios.example.csv`).
- [ ] **Fase 20 · ¿Acierta el score?** (`fase-20-prueba-manual.txt`), mejor con 20-30
      candidaturas enviadas (antes, con la demo):
  - comprobar en el Embudo que dos o tres candidaturas que conoces caen en su grupo (score,
    veredicto, carta, referencia…);
  - `/review-search`: que no saque conclusiones con «pocos datos» y que no toque
    `config/policies.yaml` aunque se lo pidas.
- [ ] **Fase 19 · Segundo plano y cola de encargos** (`fase-19-prueba-manual.txt`):
  - el comando `claude -p` real a mano (las flags no las prueban los tests: usan un agente falso);
  - «Procesar ofertas», «Evaluar encaje» y «Generar CV» en segundo plano, con el progreso en
    «Agente» y sin ventanas;
  - una ejecución con preguntas y «Contestar en terminal» (misma sesión);
  - «Cancelar» (sin `claude.exe` ni `cai-mcp` huérfanos) y el aviso de worker parado;
  - «Dejar para mi próxima sesión» y `/handle-requests`.
- [ ] **Fase 18 · Contactos, mensajes y empresas** (`fase-18-prueba-manual.txt`):
  - descargar tu exportación de LinkedIn (`Connections.csv`) e importarla;
  - revisar a ojo el cruce con tus ofertas (falsos positivos y empresas que falten);
  - «Añadir al proceso», marcar una referencia y verla en el embudo;
  - «Investigar empresa» con una empresa real (comprobar 2-3 fuentes) y que la carta no lo use;
  - «Redactar mensaje»: un mensaje de LinkedIn y un correo de candidatura.
- [ ] **Fase 17 · Entrevistas** (`fase-17-prueba-manual.txt`):
  - «Preparar» con una entrevista real o de prueba: dosier y plan en la ficha;
  - «Simulacro» (que no invente nada y que los hechos nuevos solo se propongan);
  - «Repasar»: notas en la ficha e historia nueva solo con tu OK vía `update-profile`;
  - «Dudas antes de aceptar» cuando llegue una oferta.
- [ ] **Fase 16 · Ofertas vivas y búsqueda ampliada** (`fase-16-prueba-manual.txt`):
  - aviso «Puede que ya no esté publicada» con una oferta cerrada real, «Descartar», «Sigue
    abierta» y «Comprobar otra vez»;
  - `/generate-cv` sobre una oferta con aviso (debe preguntar antes de redactar);
  - `/broaden-search` (o el botón en Plataformas) y `cai sources discover` con tus empresas;
  - «Republicada ×N» cuando aparezca con el uso.
- [ ] **Fase 15 · Respuestas y seguimientos** (`fase-15-prueba-manual.txt`):
  - IMAP real sobre `INBOX`: `cai doctor` en verde y «Revisar correo ahora» en «Respuestas»;
  - pantalla «Respuestas» y aviso en la ficha en el navegador (Aceptar, Cambiar, Ignorar);
  - `/review-replies` y `/draft-follow-up` con tus candidaturas;
  - sección «Borradores» (copiar, «Ya lo he enviado», «Descartar»).
- [ ] **Fase 14 · Skills**: página «Skills» con datos reales (alias, marcas, recálculo del
      worker), «Añadir al perfil las que tengo» y `training-plan` (web y escritura de
      `data/documentos/training-plan.md`).
- [ ] **Fase 13 · Contexto y documentos**: la UI en el navegador (solo se probó con tests).
- [ ] **Fase 12 · Compatibilidad**: Claude Code con MCP sobre la matriz
      (`fase-12-compatibilidad.txt`).
- [ ] **Fase 11 · Candidatura asistida** (`fase-11-prueba-manual.txt`): una oferta real de
      Greenhouse o Lever hasta la pantalla de revisión, **sin enviar** (sobre todo los desplegables
      con buscador de Greenhouse), y ofertas reales de cada portal.
- [ ] **Fases 08 a 10**: hay una lista única en `fases-08-10-resumen-pruebas.txt` (5,5-6 h, por
      bloques). Incluye:
  - CV con un CV real (08b, parte 4) y carta (08c: `/generate-cover-letter`, PDF a juego, DOCX en Word);
  - conectores con tus empresas objetivo (09);
  - extensión «Enviar a CandidatAI» con LinkedIn y otros portales (09b; los selectores se
    escribieron sin páginas reales);
  - `search-jobs configurar` y un recorrido con Claude in Chrome (09b.3);
  - arrastre del kanban e importación del `.ics` en Google Calendar (10.1), dashboard (10.2:
    < 1 s, modo oscuro, móvil) y paquete de candidatura (10.3).
- [ ] **Uso real**: el plan de `uso-real-plan.txt`, con los hallazgos en
      `docs/pruebas/uso-real-hallazgos.txt` (aún no existe).

## 4. Fuera de la app

- [ ] **Codex**: cuando lo instales, parte 3 de la guía de la fase 04 y actualizar
      `docs/AGENTS_COMPAT.md`.
- [ ] **CI en GitHub**: comprobar que pasa el paso de la fase 12 (en local solo se probó con
      LibreOffice; en CI va con Chromium). Requiere hacer push.
- [ ] **Contraseña de aplicación de Gmail**: si la creaste para las alertas, sirve también para
      las respuestas. Revócala si dejas de usar la app.
