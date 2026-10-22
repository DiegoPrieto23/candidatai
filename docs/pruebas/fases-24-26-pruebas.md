# Pruebas manuales de las fases 24, 25 y 26, en orden

Todas las pruebas pendientes de las tres fases en un solo sitio, ordenadas para hacerlas de corrido:
primero lo que solo necesita Windows y la demo, luego lo que pide instalar algo (agentes, Docker,
WSL2) y al final GitHub. Cada prueba remite a su fichero por si quieres más detalle, pero no hace
falta abrirlo.

- Marca cada casilla al hacerla. Si algo no cuadra, escríbelo debajo con «→» y pásamelo.
- Todo se hace sobre demos (datos ficticios), salvo los pasos marcados **Con tus datos**.
- **Si solo tienes una tarde:** 0, 1.0 (lo que trae la demo), 1.1 («Mi perfil»), 2 (la matriz con
  Claude Code) y 5.1 (la guía de cero en WSL2).

---

## 0. Preparación (una vez)

En PowerShell, desde la raíz del repositorio y **con Claude Code cerrado** (su servidor MCP bloquea
el entorno de Python):

- [ ] Fusiona antes en `main` las ramas que quieras probar, o haz `git checkout` de la rama.
- [ ] Copia de seguridad de tu base de datos: `copy data\jobhunter.db data\jobhunter.db.bak-2426`
      (o `candidatai.db` si ya la renombraste).
- [ ] `uv sync --directory backend`
- [ ] `uv run --directory backend cai db upgrade` → llega a la migración **0024** (0022 y 0023 de
      la fase 24, 0024 de «Mi perfil»). Sin ella, guardar desde «Mi perfil» falla.
- [ ] `cd frontend; pnpm install; pnpm build; cd ..` (la UI compilada que sirve `cai start`).
      **Repítelo después de cada `git checkout` o `git pull`**: `cai start` no sirve el código de
      `frontend/src`, sino `frontend/dist`, y con una compilación vieja no ves lo nuevo (en «Mi
      perfil» no salen «Añadir empresa», «Añadir historia» ni «Mejorar con mi agente»).
      → `frontend\dist\index.html` tiene la fecha de hoy.
- [ ] Abre Claude Code y comprueba con `/mcp` que `candidatai` está conectado y tiene `get_schema`.
- [ ] Si no vas a usar Docker con tus datos: `docker compose down` y
      `docker volume rm candidatai-data` (en mis pruebas el contenedor trajo tus alertas por IMAP a
      ese volumen).
- [ ] Demo nueva para el bloque 1: `uv run --directory backend cai demo seed --force`
      → «60 ofertas» y «2 CVs», sin avisos. Hazla de nuevo si la creaste antes de la fase 26.5:
      las de antes no traen cartas, correos, dosieres ni entrevistas preparadas.

---

## 1. Windows con la demo (sin instalar nada)

Arranca la demo en su propia ventana y déjala abierta durante todo el bloque:

```powershell
$env:CAI_DATA_DIR = "data-demo"; uv run --directory backend cai start
```

- La variable vale solo para esa ventana. **En cada PowerShell que abras para este bloque**, y
  antes de abrir Claude Code a mano, escribe primero `$env:CAI_DATA_DIR = "data-demo"`: sin ella,
  `cai stats story`, `cai match show`, `cai doctor`… y tu agente usan tus datos reales.
- Los botones «en tu agente» ya abren el agente sobre la demo; no hace falta nada más.
- Recarga la página con Ctrl+F5 la primera vez, por si el navegador guardaba la UI vieja.

### 1.0 Lo que trae la demo (26.5)

Comprueba que ninguna pantalla sale vacía. Las empresas con CV son **Brétema Analytics** (Data
Engineer) y **Lumieira Retail** (Analytics Engineer); el resto cambia con la demo.

- [ ] **Ficha de Brétema Analytics** → valoración «Encaje fuerte» con su pregunta; carta
      verificada con sus indicaciones; respuestas de screening (una «Necesita tu dato»: la
      expectativa salarial); dosier de la empresa con fuentes.
- [ ] **Ficha de Lumieira Retail** → borrador de mensaje de LinkedIn para el recruiter; dosier con
      «Banderas rojas» (un ERE con fecha y fuente).
- [ ] **Respuestas** → tres correos: entrevista y descarte con propuesta, y un acuse «Sin
      clasificar» con el aviso de texto oculto. Acepta la de entrevista → la oferta pasa a «En
      proceso» con el hito.
      Con tu agente, `review-replies` clasifica el acuse como `none` con `injection_suspected`.
- [ ] **Procesos** → la entrevista programada más próxima tiene «Plan de preparación» (bloques de hoy
      al día de la entrevista); dos entrevistas pasadas tienen «Repaso»; la oferta recibida tiene
      sus datos (importes ocultos) y sale en la comparación.
- [ ] **Seguimientos** → un borrador de seguimiento de una candidatura enviada, listo para copiar.
- [ ] **Skills** → Looker y Databricks marcadas «No la tengo»; «Plan de formación» las usa.
- [ ] **Agente → Encargos** → uno pendiente («Generar CV» de una oferta aprobada). Con tu agente,
      `handle-requests` lo hace y lo cierra.
- [ ] **Mi perfil → Contexto y estilo** → los cuatro ficheros con texto y la muestra
      `carta-antigua.txt`; en `data-demo\documentos\` está `salarios.csv` (lo usa
      `prepare-negotiation`).
- [ ] Cualquier botón «en tu agente» → en la terminal que abre, `echo $env:CAI_DATA_DIR` dice la
      ruta de `data-demo`.
- [ ] (Opcional) La demo en inglés: `uv run --directory backend cai demo seed --lang en --dir
      data-demo-en --force` y arranca con `$env:CAI_DATA_DIR = "data-demo-en"` → lo mismo, en inglés
      (Fogline Analytics y Moher Street Retail).

### 1.1 «Mi perfil» editable (25.7) · `fase-25.7-prueba-manual.txt`

- [ ] **Experiencia → «Añadir empresa»**: «Ría Analytics (ficticia)», «Analytics Engineer», desde
      2026-05, «Actualidad», con dos logros (uno con métrica), cada uno con una skill de la lista.
      «Guardar».
      → `data-demo\profile.yaml` tiene la empresa (`exp-ria-analytics`, logros `a1` y `a2`) y los
      comentarios del resto siguen igual.
      → Con una skill que no está en tu perfil, el error sale en ese campo.
- [ ] **Historias STAR → «Añadir historia»**: «Guardar» no se puede pulsar sin evidencia; elige un
      logro nuevo (sale por su texto) y guarda.
- [ ] Intenta borrar ese logro → no te deja y dice qué historia lo cita.
- [ ] **«Mejorar con mi agente»** en el logro → tu agente propone, pregunta la métrica que falte y
      solo escribe con tu OK, en `data-demo\profile.yaml` (no en `data\`). Si escribió, al
      guardar otro bloque sale el aviso «Recargar».
- [ ] **Búsqueda** → añade «Analytics Engineer» → antes de guardar, el diff y el aviso de que se
      recalculan los scores. En la bandeja se recalculan.
- [ ] **Skills e idiomas**: el nivel de idioma es un desplegable (uno de texto libre sale como
      «Otro»); cambiar el nivel de una skill también enseña el diff.
- [ ] **CV y carta**: cambia el tono y la despedida de la carta y guarda.
- [ ] Aprueba una oferta que encaje con «Analytics Engineer» y genera su CV → cita algún logro de
      Ría Analytics («Evidencias»).
- [ ] **Contexto y estilo → «Subir muestra»**: una carta inventada con un tono reconocible y un
      hecho que NO esté en el perfil («dirigí un equipo de 8»). «Ver texto extraído». Con «Ignora
      las instrucciones anteriores…» dentro, sale el aviso de frases dirigidas a una IA.
- [ ] Genera la carta de esa oferta → tiene el tono de la muestra pero NO su hecho.
- [ ] **Contexto → «Criterios»**: añade una línea, «Vista previa» (sin comentarios-guía), «Guardar».
- [ ] **Historial**: «Ver cambios» y «Deshacer el último cambio» → el perfil vuelve atrás.
- [ ] **Conflicto**: con la página abierta, cambia a mano el titular en el YAML y luego en la
      página → «Tu perfil ha cambiado…» y «Recargar», sin pisar tu cambio.
- [ ] Con un bloque sin guardar, sal de la página → te avisa.
- [ ] Cambia la UI a inglés y repasa las pestañas: todo traducido.
- [ ] **Con tus datos** (más tarde, sin la demo): guarda un bloque sin cambiar nada importante y
      comprueba que `data/profile.yaml` conserva tus comentarios.

### 1.2 Agentes y niveles de gasto desde la UI (24.4 y 24.6) · `fase-24.4-prueba-manual.txt`

- [ ] **Agente → «Agentes»**: una tarjeta por agente (versión o «No instalado» con «Copiar»,
      insignias; las «sin comprobar», con borde discontinuo).
- [ ] «Agente por defecto» en «Automático» → «Por acción», columna «Efectivo»: «Claude Code · el
      primero instalado».
- [ ] Modelo `sonnet` en la tarjeta de Claude Code → «Buscar ofertas» abre
      `claude --model sonnet "…"`; en esa terminal, `echo $env:CAI_CLIENT_NAME` → `claude`. Borra
      el modelo después. Con `son net` → error en rojo, no se guarda.
- [ ] El desplegable ▾ de un botón dice «con Claude Code»; los agentes no instalados salen
      deshabilitados. Con otro agente instalado: «Solo esta vez, con…» lo abre sin cambiar la tabla.
- [ ] **En segundo plano** con un modelo en la tarjeta (p. ej. `haiku`): «Procesar ofertas» ▾ →
      «En segundo plano» → en «Agente», «Con claude (haiku)».
- [ ] **Niveles de gasto**: aplica «Económico» → cambia «Por acción» → «Deshacer el último».
- [ ] UI en inglés: la sección y la tabla en inglés.

### 1.3 Coste, umbral y paralelo (25.4) · `fase-25.4-prueba-manual.txt`

- [ ] **Agente → «Coste»**: ejecuciones sumadas, «Tokens del skill» por acción, pestañas de 7 y 30
      días. En una demo nueva está vacío hasta que lanzas algo en segundo plano (el paso siguiente):
      la demo no inventa costes.
- [ ] «Procesar ofertas» en segundo plano → turnos, tokens y coste; «Por acción» +1; en la ficha de
      una oferta procesada, «Coste del agente» «repartida entre N ofertas».
- [ ] **Umbral**: pon el score mínimo por encima de una oferta por revisar → «Sin valorar en segundo
      plano: su score (X) está por debajo del umbral (Y)»; «Evaluar encaje» en segundo plano solo
      lleva las que llegan. «Volver a…» deja el de por defecto.
- [ ] **Paralelo**: `background_runs.max_parallel: 2` en `config/policies.yaml`, reinicia, y «Generar
      CV» en segundo plano de dos ofertas distintas → las dos «En curso» a la vez; la misma oferta
      otra vez espera. Con `per_agent: {claude: 1}`, de una en una. Vuelve a `1` al acabar.
- [ ] **Embudo**: panel «Coste del agente» y columna «Coste por enviada».

### 1.4 Maquetación del PDF (25.5) · `fase-25.5-prueba-manual.txt`

- [ ] Renderiza un CV con `ats-simple`, `clasica-foto` y `moderna-2col` → ningún aviso con un CV de
      una página. Si sale alguno, mira la página que dice: ¿es real?
- [ ] Con tus plantillas importadas (si tienes): con dos columnas, «Texto del PDF incompleto» es
      real si un ATS leería primero la barra.
- [ ] «Máximo de páginas» 2 y contenido que pase de una página → «Última página casi vacía» con la
      página; «Generar CV» recorta y el aviso desaparece.
- [ ] La carta con `carta-simple` y con la plantilla del CV → sin avisos.

### 1.5 Tu búsqueda en números (25.6) · `fase-25.6-prueba-manual.txt`

- [ ] **Embudo → «Tu búsqueda en números»**: fechas y cinco cifras, que no cambian con el periodo.
- [ ] «Copiar en español» y «Copiar en inglés» → ningún nombre de empresa, puesto, fuente ni importe.
- [ ] `uv run --directory backend cai stats story` → las mismas cifras.
- [ ] `python scripts/release_notes.py v0.1.0` → notas de la 0.1.0; con `v0.2.0`, error.
- [ ] **Con tus datos**: ¿te cuadran las cifras? Decide si publicas la línea en el README (bloque
      comentado en `README.md` y `README.es.md`).

### 1.6 Ofertas dudosas y banderas rojas (25.3) · `fase-25.3-prueba-manual.txt`

- [ ] Nueva oferta pegada de una agencia, temporal («para importante cliente», «contrato de 6
      meses»), y `process-jobs` → en la ficha, «Temporal» y «Empresa oculta»; el score no cambia
      por ellas (`cai match show ID`: «Señales de oferta dudosa (no cuentan en el score)»).
- [ ] `assess-fit` sobre ella → cita `fixed_term` y `employer_hidden` en los riesgos.
- [ ] (Opcional) `exclude_signals: [fixed_term]` en `preferences` e importar → la oferta se cierra
      por esa señal. Quítalo después.
- [ ] `research-company` de una empresa con despidos en prensa → «Banderas rojas» con tipo, fecha y
      cita; `prepare-interview` las convierte en preguntas neutrales.
- [ ] **Embudo → «¿Acierta el score?» → «Señal»**: una fila por señal («pocos datos» es normal).
- [ ] **Con tus datos**: `uv run --directory backend cai jobs signals --recompute` → apunta
      cuántas de cada señal y los falsos positivos (sobre todo «Empresa oculta» por el nombre:
      `config/doubtful_patterns.yaml`).

### 1.7 Skill `expand` (25.2) · `fase-25.2-prueba-manual.txt`

- [ ] En `data-demo/profile.yaml`, `personal.github: https://github.com/<usuario>` (el tuyo u otro
      público). Copia: `Copy-Item data-demo/profile.yaml $env:TEMP/perfil-antes.yaml`.
- [ ] Con `$env:CAI_DATA_DIR = "data-demo"`, abre Claude Code y escribe `/expand` → enseña los
      enlaces; del TFG de la demo dice que no lo encuentra (no se lo inventa).
- [ ] Elige tu GitHub → propuestas agrupadas con URL y fecha; sin forks ajenos ni repos vacíos;
      skills **sin nivel**; números tal como los da GitHub.
- [ ] `git diff --no-index $env:TEMP/perfil-antes.yaml data-demo/profile.yaml` → **sin
      diferencias**. Contesta «no» → sigue igual.
- [ ] Repite y acepta solo «el 1 y el 3», con nivel para una skill → escribe con permiso, cada
      proyecto con `source:`, la skill con nivel en `skills` y la otra en `basic_skills`;
      `cai profile validate` dice válido.
- [ ] **«Mi perfil» → «Ampliar perfil desde mis enlaces»** → abre tu agente con la orden; sin «En
      segundo plano».

### 1.8 Conectores nuevos (25.1) · `fase-25.1-prueba-manual.txt`

Esta va **con tus datos** (las APIs reales): cierra la demo y arranca `cai start` sin
`CAI_DATA_DIR`.

- [ ] **Fuentes → Empresas objetivo → «Añadir»**: aparecen Personio, Teamtailor, Workable,
      SmartRecruiters, Recruitee, «Manfred (búsqueda)» y «freehire (búsqueda)», con la pista del
      slug y «Cómo encontrarlo».
- [ ] Una empresa tuya en uno de esos ATS → «Probar» → «N ofertas, M tras filtros»; los enlaces
      llevan a la oferta real. Un slug inventado da el 404 con la pista (SmartRecruiters: «0
      ofertas» y su aviso).
- [ ] «Añadir» y «Ejecutar ahora» → nuevas en «Por extraer» con el texto completo; otra vez → 0
      nuevas.
- [ ] **Manfred** con tus palabras → solo títulos con todas las palabras; la oferta trae secciones y
      salario, **sin el nombre ni el correo del «scout»**.
- [ ] **freehire** con «data engineer», `es`, solo remoto → ofertas remotas en España.
- [ ] `cai sources discover --file empresas.txt` con tu lista → apunta empresas con tablero en los
      cinco ATS nuevos que no detecte.

### 1.9 Diagnóstico y esquemas (24.1 y 24.2)

- [ ] `uv run --directory backend cai agents doctor` → se usaría Claude Code; detecta lo que tengas
      instalado (con `--refresh` tras instalar uno nuevo); sección «Modelos locales (Ollama)».
- [ ] `uv run --directory backend cai doctor` → sección «Agentes» al final.
- [ ] `cai schema list --json` y `cai schema cv-content --example true --json` → el ejemplo tiene
      sentido.
- [ ] `cai agents doctor --tokens` → cuánto pesa cada skill.

---

## 2. La matriz de compatibilidad con Claude Code (24.6) · `fase-24.6-matriz.md`

La más importante de la fase 24. Va sola, unos 30-40 minutos, y gasta tu suscripción. No hace falta
`cai worker` ni la app abierta.

- [ ] Cierra cualquier sesión de tu agente en este repositorio.
- [ ] `uv run --directory backend cai eval compat --agent claude` (si una ejecución agota el tiempo,
      repite con `--timeout 30`).
- [ ] Apunta los permisos que te pidió y el error de lo que falle.
- [ ] Pásame `evals/compat/REPORT.md`: con él completo AGENTS_COMPAT, el README y la ADR-037.

---

## 3. Agentes opcionales (24.3, 24.5 y 24.6)

Solo si instalas alguno. **Lo que cierra la fase 24 es OpenCode con un modelo local (3.1).**

### 3.1 OpenCode con Ollama · `fase-24.6-matriz.md` §2 y `fase-24.5-prueba-manual.txt`

- [ ] Ollama según `docs/MODELOS_GRATIS.md`: `OLLAMA_CONTEXT_LENGTH=32768` y
      `ollama pull gpt-oss:20b` (o `qwen3:14b` si no cabe). `cai agents doctor`: Ollama responde,
      sin aviso de contexto.
- [ ] `npm install -g opencode-ai` y el proveedor `ollama` en `~/.config/opencode/opencode.json`.
      `opencode run -m ollama/gpt-oss:20b "di hola"` responde.
- [ ] **Matriz**: `cai eval compat --agent opencode --model ollama/gpt-oss:20b --timeout 30`;
      `generate-cv` va a mano (imprime los pasos) y después `--import`.
- [ ] **Segundo plano** (demo propia: `cai demo seed --dir data-demo-245 --compat`,
      `$env:CAI_DATA_DIR = "data-demo-245"`, `cai start`; OpenCode en «Procesar ofertas» y «Evaluar
      encaje»): «Procesar ofertas» en segundo plano → «Con opencode (<modelo>)», solo con
      `get_status`, `list_jobs`, `get_job` y `save_extraction`; las 5 ofertas pasan a «Por triar».
      «Evaluar encaje» igual.
- [ ] **El techo con un modelo**: los pasos C.1-C.5 del fichero → ninguna herramienta fuera de la
      acción funciona (ni bash, ni leer, ni web; el `writer` se deniega).
- [ ] «Generar CV» con OpenCode → «En segundo plano» deshabilitado y «En segundo plano con Claude
      Code» debajo.
- [ ] «Abrir en terminal» en una ejecución terminada → OpenCode retoma la misma sesión.

### 3.2 Qwen Code, Antigravity o Codex · `fase-24.3-prueba-manual.txt`

Con una demo propia (`cai demo seed --dir data-demo-agentes --compat` y
`$env:CAI_DATA_DIR = "data-demo-agentes"`):

- [ ] `/mcp` con `candidatai` conectado y los skills visibles.
- [ ] `process-jobs` con una oferta → delega en el `extractor`; la oferta pasa a «Por triar».
- [ ] **Aislamiento**: pide al `extractor` que llame a `list_jobs`, ejecute `echo hola` y lea
      `AGENTS.md` → no puede. En Qwen, el `writer` no puede leer `.env`.
- [ ] Codex local: `codex --oss -m gpt-oss:20b` → `$process-jobs` con una oferta.
- [ ] Matriz a mano: `cai eval compat --agent codex` (o `--preset local`) y sus pasos `--approve` e
      `--import`.

---

## 4. Docker en Windows (26.3) · `fase-26-prueba-manual.txt` §26.3

Con Docker Desktop abierto y la CandidatAI nativa cerrada (mismo puerto).

- [ ] `docker compose up -d --build` → `docker compose ps` dice «healthy» y
      http://127.0.0.1:8000 abre la app. Desde otro equipo de tu red, `http://<tu IP>:8000` **no**
      responde.
- [ ] `docker compose exec candidatai cai demo seed` → «Demo creada en /data-demo» con 2 CVs.
- [ ] `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d` → la demo (60 ofertas);
      abre un CV en PDF desde una ficha.
- [ ] `docker compose exec candidatai cai doctor` → sección «Docker» en verde y «Todo listo».
- [ ] Un botón «en tu agente» → copia la orden con «Estás en Docker…». En «Agente», «En segundo
      plano» desactivado con el motivo. Una oferta en «CV listo» → «Abrir la oferta en tu navegador»
      y «Marcar como enviada», sin «Abrir navegador» ni «Preparar candidatura».
- [ ] **Tu agente por MCP**: `claude mcp add --scope local candidatai -- docker exec -i candidatai cai-mcp`;
      en Claude Code, `/mcp` lo ve; `/process-jobs` extrae las 3 ofertas pendientes de la demo.
      Después, `claude mcp remove --scope local candidatai`.
- [ ] Sin MCP: `docker exec -i candidatai cai status --json`.
- [ ] `docker compose stop` termina en unos segundos; la copia de seguridad de la guía («Con
      Docker») deja `candidatai-data.tgz`.
- [ ] Al acabar: `docker compose down` y, si no lo usas, `docker volume rm candidatai-data candidatai-demo`.

---

## 5. Linux en WSL2 (26.1, 26.2 y 26.4) · `fase-26-prueba-manual.txt`

El orden importa: **5.1 necesita un Ubuntu sin nada de CandidatAI**. Después se instala lo demás.

### 5.1 La guía de cero a la app (26.4)

Con `docs/GUIA.md` abierta y sin mirar nada más (ni este documento):

- [ ] Sigue «Requisitos» y «En macOS y Linux: `install.sh`» tal cual. Apunta cada paso que falte,
      sobre o no se entienda.
- [ ] Abre «CandidatAI» desde el menú de Windows («CandidatAI (Ubuntu)») → se abre la app en el
      navegador; al cerrar la terminal, se para (`ps -ef | grep cai` sin nada).
- [ ] `cai paths` (desde `…/app/backend`, con `uv run`) → la carpeta de la tabla «Dónde están tus
      datos».
- [ ] Sigue «Conectar tu agente» → tu agente ve las herramientas de `candidatai`.
- [ ] **Copia de seguridad** como dice la guía: con la app cerrada, copia la carpeta de datos,
      bórrala, restáurala y abre la app → todo sigue ahí.

### 5.2 `install.sh` (26.2)

- [ ] Reinstala con `bash install.sh` (o `--source "$PWD"` desde un clon con la UI compilada) tras
      crear un fichero en `…/data` y añadir una línea tuya a `…/app/.env` → los dos siguen ahí.
- [ ] `bash install.sh --dry-run` → explica los pasos y termina con «no se ha cambiado nada».
- [ ] `bash install.sh --uninstall` → se van la app y el acceso directo; `…/data` sigue.
- [ ] `bash install.sh --uninstall --remove-data` → pide escribir «borrar»; con otra cosa no borra.

### 5.3 Botones y procesos en Linux (26.1)

En un clon de la rama **dentro de Linux** (no en `/mnt/c`), con `uv sync` y `cai db upgrade`:

- [ ] `uv run pytest tests/test_terminals.py tests/test_agent_runs.py -q` → los «necesita macOS o
      Linux» pasan, no se saltan.
- [ ] `uv run cai agents doctor` → «Terminal para los botones: gnome-terminal…»; con
      `CAI_TERMINAL=kitty` y sin kitty, dice que no la encuentra.
- [ ] «Procesar ofertas» → «En terminal» → gnome-terminal con tu agente y la orden; al salir,
      `echo $CAI_CLIENT_NAME` dice el agente y `echo ${ANTHROPIC_API_KEY-sin}` dice «sin».
- [ ] Con `CAI_TERMINAL=no-existe` → el botón dice que no la encuentra y copia la orden.
- [ ] «En segundo plano» y cancelar en «Agente» → `ps -ef | grep -E "claude|opencode|cai-mcp"` sin
      nada de esa ejecución. Repite cerrando `cai start` con Ctrl+C → tampoco, y la ejecución sale
      como «Se paró el worker…».
- [ ] Con `libreoffice-writer`, `cai doctor` lo encuentra y la demo genera PDF y DOCX; «Abrir
      carpeta» abre el explorador.

### 5.4 Docker en WSL2 (opcional)

- [ ] Activa en Docker Desktop la integración con tu Ubuntu y repite `docker compose up -d` desde el
      clon de Linux.

---

## 6. De vuelta en Windows y en GitHub

- [ ] Los botones «en tu agente» siguen abriendo Windows Terminal como antes, y `CAI_TERMINAL` no
      cambia nada.
- [ ] **Actions → Release → «Run workflow»** con `v0.1.0` en la rama → notas en el resumen y el
      artefacto `candidatai-zip`, sin publicar nada (el job «release» sale saltado).
- [ ] Tras fusionar en `main`: la primera CI ahí incluye macOS (backend e instalador) y sale en
      verde.
- [ ] Mira los dos README en github.com: el badge «Windows · macOS · Linux».

---

## Al terminar

- Borra las demos que ya no quieras (`data-demo-245`, `data-demo-agentes`,
  `data-demo-compat-*`) y quita `$env:CAI_DATA_DIR`.
- Pásame lo apuntado con «→» y `evals/compat/REPORT.md`: con eso cierro la 24.6 y la fase 24, y
  marco las pruebas en `docs/pruebas/PENDIENTES.md`.
