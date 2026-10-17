# Pendientes del usuario

Cosas que tiene que hacer el usuario a mano: el agente no puede hacerlas (permisos, cuentas,
navegador, Claude Code cerrado) o necesitan datos reales. El agente añade aquí lo que salga en
cada fase y lo quita cuando el usuario confirma que está hecho.

Marca `[x]` lo que hagas y, si algo falla, apúntalo debajo de la línea con `→`.

Última actualización: 2026-10-17 (fase 26.1).

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

### Arranque con un comando e instalador (fase 23.4)

- [ ] Compila la UI una vez: `cd frontend; pnpm build`. Desde entonces basta con
      `cd backend; uv run cai start` (API con la UI y worker, en http://127.0.0.1:8000): ya no
      hacen falta tres ventanas. `--dev` añade Vite si vas a tocar la UI.
- [ ] Prueba el instalador desde tu repositorio (aún no hay release pública):
      `powershell -ExecutionPolicy Bypass -File .\install.ps1 -WhatIf -Source .` y, si te
      convence, lo mismo sin `-WhatIf`. Instala en
      `%LOCALAPPDATA%\CandidatAI` (sus datos van aparte de los tuyos de `data/`) y crea el acceso
      directo. Ábrelo, comprueba que se abre el navegador y que al cerrar la ventana se para todo.
      Desinstala con `.\install.ps1 -Uninstall` (tus datos se quedan).
- [ ] Cuando quieras publicar una versión: `git tag v0.1.0; git push origin v0.1.0` crea la release
      con `candidatai.zip`. Para que el instalador de una línea funcione para otros, el
      repositorio tiene que ser público.

### Idioma de la UI (fase 23.6)

- [ ] Abre la app y pulsa el globo de abajo en la barra lateral: cambia a «English», recorre unas
      cuantas páginas y vuelve a «Español». Recarga y comprueba que recuerda el idioma. Si ves
      algún texto de la interfaz (no de tus datos) que se haya quedado en español, apúntalo.

### README y demo en inglés (fase 23.5b)

- [ ] Cuando hagas push, abre el repositorio en github.com y mira los dos README: capturas, GIF y
      el modo oscuro (cambia el tema de GitHub). Guía: `fase-23-prueba-manual.txt`, parte 1.
- [ ] Opcional: para que el vídeo se vea dentro del README, edítalo en github.com y arrastra
      `docs/video/tour-en.mp4` (y `tour-es.mp4` en `README.es.md`); ver
      `scripts/readme_media/README.md`.
- [ ] Si tenías una demo creada antes de hoy y la arrancaste con `cai start`, puede tener tus
      correos reales dentro (ya no pasa): bórrala y vuelve a sembrarla con `cai demo seed --force`.

### Registro de agentes (fase 24.1)

- [ ] `uv run --directory backend cai agents doctor`: comprueba que dice que se usaría Claude
      Code y que ve Copilot CLI como instalado y «solo compatible». Si instalas otro agente
      (p. ej. Codex), vuelve a ejecutarlo con `--refresh` y mira que lo detecta.
- [ ] `uv run --directory backend cai doctor`: la sección «Agentes» al final.

### Esquemas y errores (fase 24.2)

- [ ] Abre Claude Code de nuevo (o reconecta en `/mcp`) para que cargue la herramienta
      `get_schema`.
- [ ] `uv run --directory backend cai schema list --json` y
      `uv run --directory backend cai schema cv-content --example true --json`: mira que el
      ejemplo tenga sentido con tu forma de trabajar.
- [ ] `uv run --directory backend cai agents doctor --tokens`: cuánto pesa cada skill.

### Agentes nuevos (fase 24.3)

- [ ] `uv run --directory backend cai agents list`: OpenCode, Qwen Code y Antigravity CLI
      habilitados; Gemini CLI deshabilitado, con el motivo.
- [ ] Si instalas OpenCode, Qwen Code o Antigravity: `fase-24.3-prueba-manual.txt` (servidor,
      skills, `process-jobs` y aislamiento del extractor). OpenCode necesita un modelo local o tu
      clave: los gratuitos de OpenCode Zen no admiten agentes propios.

### Elegir agente desde la UI (fase 24.4)

- [ ] `uv run --directory backend alembic upgrade head` (migración 0022) o arranca `cai start`.
- [ ] `fase-24.4-prueba-manual.txt`: sección «Agentes», agente por defecto y por acción,
      «con Claude Code ▾» y el modelo en terminal y en segundo plano.

### Segundo plano con OpenCode (fase 24.5)

- [ ] `uv run --directory backend alembic upgrade head` (migración 0023) o arranca `cai start`.
- [ ] Con OpenCode instalado y **un modelo local o tu clave** (los gratuitos de OpenCode Zen
      rechazan el agente de la ejecución): `fase-24.5-prueba-manual.txt`. `process-jobs` y
      `assess-fit` en segundo plano sobre una demo, el techo de herramientas con un modelo y
      `generate-cv`, que propone Claude Code.

### Modelos gratuitos, niveles de gasto y matriz (fase 24.6)

- [ ] Página «Agente»: «Niveles de gasto» con los tres niveles. Aplica uno, mira que cambia la tabla
      «Por acción» y pulsa «Deshacer el último».
- [ ] `uv run --directory backend cai agents doctor`: sección «Modelos locales (Ollama)» («no
      responde» si no lo tienes).
- [ ] **La matriz** (`fase-24.6-matriz.md`): como mínimo Claude Code con MCP
      (`cai eval compat --agent claude`, cierra el pendiente de la 12.3). Si instalas Ollama y
      OpenCode, también OpenCode con un modelo local: es el criterio de cierre de la fase 24.
      Después, pásame `evals/compat/REPORT.md` para completar `AGENTS_COMPAT.md`, el README y la
      ADR-037.

### «Mi perfil» editable (fase 25.7)

- [ ] `uv run --directory backend cai db upgrade` (migración **0024**, `profile_edits`) o arranca
      `cai start`. Sin ella, guardar desde «Mi perfil» o «Usar por defecto» en Plantillas falla.
- [ ] La prueba manual sobre la demo: `fase-25.7-prueba-manual.txt` (empresa con dos logros e
      historia STAR desde la UI, CV y carta que los usan, muestra de estilo que da el tono sin
      colar hechos, deshacer y conflicto).
- [ ] Con tu perfil real: abre «Mi perfil», guarda un bloque sin cambiar nada importante y mira con
      `git diff --no-index` (o tu editor) que `data/profile.yaml` conserva tus comentarios.

### CHANGELOG y tu búsqueda en números (fase 25.6)

- [ ] Embudo → «Tu búsqueda en números»: ¿te cuadran las cifras? Copia la línea en los dos idiomas
      y comprueba que no lleva ningún nombre. Guía: `fase-25.6-prueba-manual.txt`.
- [ ] **Decidir si publicas tus cifras** en el README: el bloque está preparado y comentado en
      `README.md` y `README.es.md` (pega la línea de `cai stats story`, escribe qué funcionó y
      quita el comentario).
- [ ] Tras el push de la rama: Actions → Release → «Run workflow» con `v0.1.0` (prueba en seco:
      solo escribe las notas en el resumen).
- [ ] Cuando quieras la primera release pública (0.2.0): `CONTRIBUTING.md` §Changelog, versiones
      y releases.

### Conectores de ATS y portales con API (fase 25.1)

- [ ] «Fuentes → Empresas objetivo»: añade con «Probar» una empresa tuya en Personio, Teamtailor,
      Workable, SmartRecruiters o Recruitee (el enlace «Cómo encontrarlo» explica el slug), y una
      búsqueda en Manfred y otra en freehire. Guía: `fase-25.1-prueba-manual.txt`.
- [ ] `uv run --directory backend cai sources discover --file empresas.txt` con tu lista: ahora
      prueba también esos cinco ATS (tarda más: hasta 8 ATS × 3 slugs por empresa).

### Maquetación del PDF (fase 25.5)

- [ ] Renderiza tus CVs con cada plantilla (y tus plantillas importadas) y mira los avisos de
      maquetación en la ficha: ¿alguno es un falso positivo? Guía: `fase-25.5-prueba-manual.txt`.
- [ ] Con un CV de dos páginas, el aviso de última página casi vacía y «Generar CV» recortando.

### Coste, umbral y lote en paralelo (fase 25.4)

- [ ] Página «Agente» → «Coste» con tus ejecuciones reales: por acción, agente y modelo, y lo que
      pesa cada skill. Guía: `fase-25.4-prueba-manual.txt`.
- [ ] Umbral de «Evaluar encaje»: con una oferta por debajo, el triaje dice por qué y la ejecución
      en segundo plano no la incluye.
- [ ] `background_runs.max_parallel: 2` en `config/policies.yaml`: dos «Generar CV» de ofertas
      distintas a la vez y la misma oferta nunca dos veces. Con un modelo local de Ollama,
      `per_agent: {opencode: 1}`.

### Ofertas dudosas y banderas rojas (fase 25.3)

- [ ] `uv run --directory backend cai jobs signals --recompute` con tus datos: apunta cuántas salen
      de cada señal y si alguna es un falso positivo (sobre todo `employer_hidden` por el nombre:
      edita `config/doubtful_patterns.yaml`). Guía: `fase-25.3-prueba-manual.txt`.
- [ ] Procesa unas ofertas nuevas (`process-jobs`) y mira en la ficha si `fixed_term`,
      `employer_hidden` (agencia) y `ai_screening` salen donde deben.
- [ ] `research-company` de una empresa con noticias de despidos: banderas rojas con fuente y
      fecha, y `prepare-interview` las convierte en preguntas.

### Skill `expand` (fase 25.2)

- [ ] `/expand` sobre la demo con un GitHub público real (el tuyo si quieres): propone con la
      fuente, no escribe nada si dices que no, y con tu OK añade lo aceptado con `source`. Guía:
      `fase-25.2-prueba-manual.txt`.
- [ ] «Mi perfil» → «Ampliar perfil desde mis enlaces» abre tu agente con la orden del skill.
- [ ] Cuando lo uses con tu perfil real: el primer `cai profile import` tras la fase **no** crea
      versión si no has añadido ningún `source` (si la crea, avísame).

## 2. `.env.example` (el agente no puede leerlo ni editarlo)

- [ ] Crear o completar `.env.example`, **sin valores reales**, con todas las variables de
      `backend/app/core/config.py`:
  - generales: `CAI_DATA_DIR`, `CAI_DB_URL`, `SOFFICE_PATH`, `CAI_CLIENT_NAME`, `CAI_AGENT`,
    `CAI_EMBEDDINGS` y, de la fase 26.1, `CAI_TERMINAL` (comentada: solo macOS y Linux; p. ej.
    `iterm`, `kitty` o la ruta de tu terminal);
  - portales: `CAI_INFOJOBS_CLIENT_ID`, `CAI_INFOJOBS_CLIENT_SECRET`, `CAI_ADZUNA_APP_ID`,
    `CAI_ADZUNA_APP_KEY` y, de la fase 25.1, `CAI_FREEHIRE_BASE_URL` (opcional, comentada: por
    defecto `https://freehire.me/api/v1`);
  - correo: `CAI_IMAP_HOST`, `CAI_IMAP_PORT`, `CAI_IMAP_USER`, `CAI_IMAP_PASSWORD`,
    `CAI_IMAP_FOLDER` y, de la fase 15, `CAI_IMAP_REPLIES_FOLDER` (por defecto `INBOX`);
  - navegador: `CAI_CAPTURE_EXTENSION_ID`, `CAI_BROWSER_HEADLESS`, `CAI_BROWSER_CHANNEL`,
    `CAI_APPLIER_ALLOW_LOOPBACK`.

## 3. Pruebas manuales pendientes

- [ ] **Recorrido completo con la demo** (`guia-prueba-demo.md`): todas las funciones, página a
      página, con lo que debes ver. Sirve también para la demo en inglés (`--lang en`).

Cada guía está en `docs/pruebas/`. No consta en el ROADMAP que estén hechas; si alguna ya la
hiciste, márcala.

- [ ] **Fase 26.1 · macOS y Linux** (`fase-26-prueba-manual.txt`, sección 26.1), en WSL2:
  - los tests de `test_terminals.py` y `test_agent_runs.py` que en Windows se saltan («necesita
    macOS o Linux») tienen que pasar en Ubuntu;
  - un botón «en tu agente» abre gnome-terminal con la orden y el agente arrancado, sin la clave
    de API y con `CAI_CLIENT_NAME`;
  - cancelar una ejecución en segundo plano y cerrar `cai start` no dejan procesos huérfanos;
  - en Windows, los botones siguen abriendo Windows Terminal como antes.

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
