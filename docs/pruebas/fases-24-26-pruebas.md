# Barrido final: funciones principales y fases 24, 25 y 26

Todas las comprobaciones pendientes en un solo sitio, ordenadas para hacerlas de corrido sobre
`main`. Primero, un barrido rápido de las funciones principales con la demo. Después, lo nuevo de
las fases 24-26 y lo que solo se ve con tus datos. Al final, lo que pide instalar algo (Docker,
WSL2) y GitHub. Cada bloque remite a su fichero por si quieres más detalle, pero no hace falta
abrirlo.

- Marca cada casilla al hacerla. Si algo no cuadra, escríbelo debajo con «→» y pásamelo.
- Todo se hace sobre demos (datos ficticios), salvo el bloque 3 y los pasos marcados **Con tus
  datos**.
- **Hecho el 2026-10-22, no hace falta repetirlo:** la matriz de compatibilidad con Claude Code,
  Codex (una oferta) y Antigravity (`evals/compat/REPORT.md`). OpenCode con un modelo local no es
  viable en este portátil.

| Bloque | Qué | Tiempo aprox. |
|---|---|---|
| 0 | Preparación | 15 min |
| 1 | Barrido de las funciones principales (demo) | 1,5-2 h |
| 2 | Lo nuevo de las fases 24-26 (demo) | 2 h |
| 3 | Con tus datos | 1 h |
| 4 | Otros agentes (opcional) | 30 min |
| 5 | Docker en Windows | 30 min |
| 6 | Linux en WSL2 | 1,5 h |
| 7 | De vuelta en Windows y GitHub | 15 min |

**Si solo tienes una tarde:** 0, 1, 2.0 (lo que trae la demo), 2.1 («Mi perfil»), 3.1 y 3.2 (tu
perfil y tus fuentes) y 6.1 (la guía de cero en WSL2).

---

## 0. Preparación (una vez)

En PowerShell, desde la raíz del repositorio y **con todos los agentes cerrados** (sus servidores
MCP bloquean el entorno de Python y las bases de datos). Codex deja un proceso de fondo al cerrar
la ventana: `taskkill /IM codex.exe /F`.

- [ ] `git checkout main; git pull` → `git log --oneline -1` empieza por `db41a71` o algo posterior.
- [ ] Copia de seguridad de tu base de datos: `copy data\jobhunter.db data\jobhunter.db.bak-final`
      (o `candidatai.db` si ya la renombraste).
- [ ] `uv sync --directory backend`
- [ ] `uv run --directory backend cai db upgrade` → llega a la migración **0024** (`profile_edits`).
      Sin ella, guardar desde «Mi perfil» falla.
- [ ] `cd frontend; pnpm install; pnpm build; cd ..` (la UI compilada que sirve `cai start`).
      **Repítelo después de cada `git checkout` o `git pull`**: `cai start` no sirve el código de
      `frontend/src` sino `frontend/dist`, y con una compilación vieja no ves lo nuevo.
      → `frontend\dist\index.html` tiene la fecha de hoy.
- [ ] `uv run --directory backend cai doctor` → «Todo listo» (o solo avisos que entiendes:
      LibreOffice, IMAP…).
- [ ] Abre Claude Code y comprueba con `/mcp` que `candidatai` está conectado y tiene `get_schema`.
      Ciérralo otra vez antes de crear la demo.
- [ ] Si no vas a usar Docker con tus datos: `docker compose down` y
      `docker volume rm candidatai-data` (en las pruebas anteriores el contenedor trajo tus alertas
      por IMAP a ese volumen).
- [ ] Demo nueva: `uv run --directory backend cai demo seed --force` → «60 ofertas» y
      «CVs verificados: 2», sin avisos.

Arranca la demo en su propia ventana y déjala abierta durante los bloques 1 y 2:

```powershell
$env:CAI_DATA_DIR = "data-demo"; uv run --directory backend cai start
```

- La variable vale solo para esa ventana. **En cada PowerShell que abras para estos bloques**, y
  antes de abrir tu agente a mano, escribe primero `$env:CAI_DATA_DIR = "data-demo"`. Sin ella,
  `cai stats story`, `cai match show`, `cai doctor`… y tu agente usan tus datos reales.
- Los botones «en tu agente» ya abren el agente sobre la demo; no hace falta nada más.
- Recarga la página con Ctrl+F5 la primera vez, por si el navegador guardaba la UI vieja.
- Si algo falla al arrancar, mira `data-demo\logs\start-*.log`.

---

## 1. Barrido de las funciones principales (demo) · `guia-prueba-demo.md`

Una pasada rápida por cada pantalla para ver que nada se ha roto con las fases 24-26. Lo que se
espera en detalle está en la sección de la guía que va entre paréntesis.

### 1.1 Navegación y Inicio
- [ ] Franja amarilla «Modo demo: datos ficticios» en todas las páginas (§0).
- [ ] Barra lateral con sus cuatro grupos, plegarla, idioma (🇪🇸/🇬🇧) y tema oscuro; en una ventana
      estrecha, el menú ☰ (§1).
- [ ] `http://127.0.0.1:8000/no-existe` → «Esta página no existe» (§1).
- [ ] **Inicio**: resumen del día con enlaces, «Para tu agente», recorrido de 7 casillas, paneles y
      avisos de arriba (§2).

### 1.2 Ofertas: bandeja, alta y triaje
- [ ] **Bandeja**: recuentos por etapa, buscar «Data», ordenar por Salario, Encaje y Alta,
      paginación, insignias «Conoces a N» y ⚠️ (§3).
- [ ] **Nueva oferta**: pegar `demo/jobs/01-data-engineer.txt` → aviso de duplicado; una inventada →
      «Por extraer» (§4).
- [ ] **Por revisar**: score y desglose, teclas `J`/`K`/`O`/`A`/`D`, descartar con motivo y
      «Deshacer» (§5).
- [ ] La ficha #3 (Lonxa Retail Tech): ⚠️ y bloque «Posible contenido dirigido a una IA» (§5 y §6).

### 1.3 Ficha de una oferta (#1, Brétema Analytics)
- [ ] Encaje, red («Añadir al proceso»), historial y «Añadir nota» (§6).
- [ ] Extracción, Proceso (añadir un hito y descargar su `.ics`), valoración del agente (§6).
- [ ] Paquete de candidatura con las respuestas de screening y la de salario en ámbar (§6).
- [ ] **CV**: otra plantilla, foto, color, ocultar una sección y «Renderizar»; «Comparar» dos renders
      lado a lado; «Usar este para enviar» (§6).
- [ ] **Carta**: verificada, con su PDF; cambiar las indicaciones y guardar (§6).
- [ ] Una cerrada → «Reabrir»; una enviada → «Tengo entrevista» la pasa a «En proceso»; la #60 →
      «Oferta recibida» y «Preparar negociación» (§6).

### 1.4 Procesos, respuestas y seguimiento
- [ ] **Procesos**: tablero de 5 columnas, «Actualizar estado», arrastrar (y que se niegue a «CV
      listo»), seguimientos, ofertas recibidas, próximos 7 días y calendario `.ics` (§7).
- [ ] **Respuestas**: aceptar la de entrevista, cambiar la del descarte, el acuse «Sin clasificar»
      con el aviso de texto oculto, y los filtros (§8).
- [ ] **Alertas**: vacía en la demo, sin errores (§9).

### 1.5 Análisis y configuración
- [ ] **Embudo**: cifras, embudo por pasos, por semana, fuente, tipo de puesto y motivos; cambiar el
      periodo; «¿Acierta el score?» (§10).
- [ ] **Skills**: filtros, «Es lo mismo que…» (deshazlo después en `config/skill_aliases.yaml`) y
      «La tengo / No la tengo» (§11).
- [ ] **Fuentes**: empresas objetivo pausadas, «Probar» con una real, plataformas y el aviso de
      LinkedIn (§12).
- [ ] **Plantillas**: «Subir mi CV» queda pendiente de importar; miniaturas de todas (§13).
- [ ] **Mi perfil**: contexto, muestras de estilo y documentos con `salarios.csv` (§14).

### 1.6 Con tu agente (Claude Code)
- [ ] «Procesar ofertas» en terminal → las 3 por extraer pasan a «Por revisar» o «Cerrada» (§15).
- [ ] «Evaluar encaje» en segundo plano → la página **Agente** enseña la ejecución, su progreso y su
      resultado; la #3 no sale como encaje perfecto (§15).
- [ ] «Generar CV» de una aprobada → redactado, verificado y renderizado; pasa a «CV listo» (§15).
- [ ] «Dejar para mi próxima sesión» → el encargo sale en **Agente → Para tu próxima sesión**;
      `handle-requests` lo atiende y lo cierra (§15).
- [ ] Uno a elegir de los demás skills (`research-company`, `draft-message`, `prepare-interview`,
      `mock-interview`, `review-search`) (§15).

---

## 2. Lo nuevo de las fases 24-26 (demo)

### 2.0 Lo que trae la demo (26.5)

Comprueba que ninguna pantalla sale vacía. Las empresas con CV son **Brétema Analytics** (Data
Engineer) y **Lumieira Retail** (Analytics Engineer); el resto cambia con la demo.

- [ ] **Ficha de Brétema Analytics** → valoración «Encaje fuerte» con su pregunta; carta
      verificada con sus indicaciones; respuestas de screening (una «Necesita tu dato»: la
      expectativa salarial); dosier de la empresa con fuentes.
- [ ] **Ficha de Lumieira Retail** → borrador de mensaje de LinkedIn para el recruiter; dosier con
      «Banderas rojas» (un ERE con fecha y fuente).
- [ ] **Respuestas** → tres correos: entrevista y descarte con propuesta, y un acuse «Sin
      clasificar» con el aviso de texto oculto. Con tu agente, `review-replies` clasifica el acuse
      como `none` con `injection_suspected`.
- [ ] **Procesos** → la entrevista programada más próxima tiene «Plan de preparación» (bloques de hoy
      al día de la entrevista); dos entrevistas pasadas tienen «Repaso»; la oferta recibida tiene
      sus datos (importes ocultos) y sale en la comparación.
- [ ] **Seguimientos** → un borrador de seguimiento de una candidatura enviada, listo para copiar.
- [ ] **Skills** → Looker y Databricks marcadas «No la tengo»; «Plan de formación» las usa.
- [ ] **Agente → Encargos** → uno pendiente («Generar CV» de una oferta aprobada).
- [ ] **Mi perfil → Contexto y estilo** → los cuatro ficheros con texto y la muestra
      `carta-antigua.txt`; en `data-demo\documentos\` está `salarios.csv`.
- [ ] Cualquier botón «en tu agente» → en la terminal que abre, `echo $env:CAI_DATA_DIR` dice la
      ruta de `data-demo`.
- [ ] (Opcional) La demo en inglés: `uv run --directory backend cai demo seed --lang en --dir
      data-demo-en --force` y arranca con `$env:CAI_DATA_DIR = "data-demo-en"` → lo mismo, en inglés
      (Fogline Analytics y Moher Street Retail).

### 2.1 «Mi perfil» editable (25.7) · `fase-25.7-prueba-manual.txt`

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

### 2.2 Agentes y niveles de gasto desde la UI (24.4 y 24.6) · `fase-24.4-prueba-manual.txt`

- [ ] **Agente → «Agentes»**: una tarjeta por agente (versión o «No instalado» con «Copiar»,
      insignias; las «sin comprobar», con borde discontinuo). Codex y Antigravity salen instalados.
- [ ] «Agente por defecto» en «Automático» → «Por acción», columna «Efectivo»: «Claude Code · el
      primero instalado».
- [ ] Modelo `sonnet` en la tarjeta de Claude Code → «Buscar ofertas» abre
      `claude --model sonnet "…"`; en esa terminal, `echo $env:CAI_CLIENT_NAME` → `claude`. Borra
      el modelo después. Con `son net` → error en rojo, no se guarda.
- [ ] El desplegable ▾ de un botón dice «con Claude Code»; los agentes no instalados salen
      deshabilitados. «Solo esta vez, con Codex» en «Procesar ofertas» → abre Codex con
      `$process-jobs` sobre la demo, sin cambiar la tabla.
- [ ] Con Codex en «Generar CV» (por acción) → «En segundo plano» deshabilitado con su motivo.
      Vuelve a «Automático» después.
- [ ] **En segundo plano** con un modelo en la tarjeta (p. ej. `haiku`): «Procesar ofertas» ▾ →
      «En segundo plano» → en «Agente», «Con claude (haiku)».
- [ ] **Niveles de gasto**: aplica «Económico» → cambia «Por acción» → «Deshacer el último».
- [ ] UI en inglés: la sección y la tabla en inglés.

### 2.3 Coste, umbral y paralelo (25.4) · `fase-25.4-prueba-manual.txt`

- [ ] **Agente → «Coste»**: ejecuciones sumadas, «Tokens del skill» por acción, pestañas de 7 y 30
      días. Con la ejecución de 1.6 ya no está vacío (la demo no inventa costes).
- [ ] «Procesar ofertas» en segundo plano → turnos, tokens y coste; «Por acción» +1; en la ficha de
      una oferta procesada, «Coste del agente» «repartida entre N ofertas».
- [ ] **Umbral**: pon el score mínimo por encima de una oferta por revisar → «Sin valorar en segundo
      plano: su score (X) está por debajo del umbral (Y)»; «Evaluar encaje» en segundo plano solo
      lleva las que llegan. «Volver a…» deja el de por defecto.
- [ ] **Paralelo**: `background_runs.max_parallel: 2` en `config/policies.yaml`, reinicia, y «Generar
      CV» en segundo plano de dos ofertas distintas → las dos «En curso» a la vez; la misma oferta
      otra vez espera. Con `per_agent: {claude: 1}`, de una en una. **Vuelve a `1` al acabar.**
- [ ] **Embudo**: panel «Coste del agente» y columna «Coste por enviada».

### 2.4 Maquetación del PDF (25.5) · `fase-25.5-prueba-manual.txt`

- [ ] Renderiza un CV con `ats-simple`, `clasica-foto` y `moderna-2col` → ningún aviso con un CV de
      una página. Si sale alguno, mira la página que dice: ¿es real?
- [ ] «Máximo de páginas» 2 y contenido que pase de una página → «Última página casi vacía» con la
      página; «Generar CV» recorta y el aviso desaparece.
- [ ] La carta con `carta-simple` y con la plantilla del CV → sin avisos.

### 2.5 Tu búsqueda en números (25.6) · `fase-25.6-prueba-manual.txt`

- [ ] **Embudo → «Tu búsqueda en números»**: fechas y cinco cifras, que no cambian con el periodo.
- [ ] «Copiar en español» y «Copiar en inglés» → ningún nombre de empresa, puesto, fuente ni importe.
- [ ] `uv run --directory backend cai stats story` → las mismas cifras.
- [ ] `uv run --directory backend python ../scripts/release_notes.py v0.1.0` → notas de la 0.1.0;
      con `v0.2.0`, error.

### 2.6 Ofertas dudosas y banderas rojas (25.3) · `fase-25.3-prueba-manual.txt`

- [ ] Nueva oferta pegada de una agencia, temporal («para importante cliente», «contrato de 6
      meses»), y `process-jobs` → en la ficha, «Temporal» y «Empresa oculta»; el score no cambia
      por ellas (`cai match show ID`: «Señales de oferta dudosa (no cuentan en el score)»).
- [ ] `assess-fit` sobre ella → cita `fixed_term` y `employer_hidden` en los riesgos.
- [ ] (Opcional) `exclude_signals: [fixed_term]` en `preferences` e importar → la oferta se cierra
      por esa señal. Quítalo después.
- [ ] `research-company` de una empresa con despidos en prensa → «Banderas rojas» con tipo, fecha y
      cita; `prepare-interview` las convierte en preguntas neutrales.
- [ ] **Embudo → «¿Acierta el score?» → «Señal»**: una fila por señal («pocos datos» es normal).

### 2.7 Skill `expand` (25.2) · `fase-25.2-prueba-manual.txt`

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

### 2.8 Diagnóstico y esquemas (24.1 y 24.2)

- [ ] `uv run --directory backend cai agents doctor` → se usaría Claude Code; detecta Codex y
      Antigravity (con `--refresh` tras instalar uno nuevo); sección «Modelos locales (Ollama)».
- [ ] `uv run --directory backend cai doctor` → sección «Agentes» al final.
- [ ] `cai schema list --json` y `cai schema cv-content --example true --json` → el ejemplo tiene
      sentido.
- [ ] `cai agents doctor --tokens` → cuánto pesa cada skill.

---

## 3. Con tus datos

Cierra la demo (Ctrl+C en su ventana), abre una PowerShell nueva **sin** `CAI_DATA_DIR` y arranca
`uv run --directory backend cai start`. Antes de empezar, `uv run --directory backend cai paths`
dice que usas `data\`.

### 3.1 Tu perfil y tu búsqueda
- [ ] La app arranca sin franja de demo y con tus ofertas; «Inicio» cuadra con lo que esperas.
- [ ] **Mi perfil**: guarda un bloque sin cambiar nada importante → `data/profile.yaml` conserva tus
      comentarios (`git diff` no aplica: compáralo con tu copia).
- [ ] `uv run --directory backend cai profile validate` → válido.
- [ ] **Embudo → «Tu búsqueda en números»**: ¿te cuadran las cifras? Decide si publicas la línea en
      el README (bloque comentado en `README.md` y `README.es.md`).
- [ ] `uv run --directory backend cai jobs signals --recompute` → apunta cuántas de cada señal y los
      falsos positivos (sobre todo «Empresa oculta»: `config/doubtful_patterns.yaml`).
- [ ] Renderiza uno de tus CVs con cada plantilla (y tus importadas): con dos columnas, «Texto del
      PDF incompleto» es real si un ATS leería primero la barra.

### 3.2 Fuentes reales (25.1) · `fase-25.1-prueba-manual.txt`
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

### 3.3 Entrada de ofertas y correo
- [ ] **Alertas por correo**: «Alertas» → «Revisar correo ahora» con tu IMAP → llegan las de hoy, sin
      duplicados (`fase-09b-prueba-manual.txt`).
- [ ] **Respuestas**: «Revisar correo ahora» y «Revisar respuestas» con tu agente → propuestas con
      sentido para tus procesos (`fase-15-prueba-manual.txt`).
- [ ] **Extensión «Enviar a CandidatAI»**: en una oferta real en el navegador, el botón la da de alta
      en «Por extraer» con su texto (`fase-09b.3-prueba-manual.txt`).
- [ ] **Nueva oferta por URL** de Greenhouse o Lever → ficha con el texto completo.
- [ ] «Procesar ofertas» y «Evaluar encaje» en segundo plano sobre las nuevas → «Por revisar» con
      valoración.

### 3.4 De la oferta al envío
- [ ] Aprueba una oferta real y «Generar CV» → verificado, una página, con evidencias de tu perfil.
- [ ] «Preparar candidatura» → respuestas de screening y, si procede, carta.
- [ ] **Candidatura asistida** en una oferta real de acceso libre: el navegador de CandidatAI
      rellena, **no envía nada** y espera tu confirmación (`fase-11-prueba-manual.txt`). Si no
      quieres enviarla, cierra sin enviar.
- [ ] «Marcar como enviada» → pasa a «Enviada» con su evento; sale en Procesos y en el embudo.

### 3.5 Al acabar con tus datos
- [ ] `uv run --directory backend cai status` → recuentos coherentes.
- [ ] Si algo se torció, para la app y restaura la copia del paso 0
      (`copy data\jobhunter.db.bak-final data\jobhunter.db`).

---

## 4. Otros agentes (opcional) · `fase-24.3-prueba-manual.txt`

La matriz ya está hecha con Codex y Antigravity. Esto comprueba el aislamiento del `extractor`,
que la matriz no mide. Con una demo propia (`cai demo seed --dir data-demo-agentes --compat` y
`$env:CAI_DATA_DIR = "data-demo-agentes"` antes de abrir el agente):

- [ ] **Codex**: `codex mcp list` → `candidatai` con `CAI_DATA_DIR`; `get_status` dice modo demo.
- [ ] `$process-jobs` → delega en el `extractor`; la oferta pasa a «Por triar». Las herramientas
      de lectura no piden permiso; «Allow for this session» en las demás.
- [ ] **Aislamiento**: pide al `extractor` que llame a `list_jobs`, ejecute `echo hola` y lea
      `AGENTS.md` → apunta qué consigue (Codex está en nivel B: hereda la política de la sesión).
- [ ] **Antigravity** (si te queda cupo semanal): `/process-jobs` con una oferta → la extrae.
- [ ] Al acabar, cierra los agentes (`taskkill /IM codex.exe /F`) y borra `data-demo-agentes`.

---

## 5. Docker en Windows (26.3) · `fase-26-prueba-manual.txt` §26.3

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

## 6. Linux en WSL2 (26.1, 26.2 y 26.4) · `fase-26-prueba-manual.txt`

El orden importa: **6.1 necesita un Ubuntu sin nada de CandidatAI**. Después se instala lo demás.

### 6.1 La guía de cero a la app (26.4)

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

### 6.2 `install.sh` (26.2)

- [ ] Reinstala con `bash install.sh` (o `--source "$PWD"` desde un clon con la UI compilada) tras
      crear un fichero en `…/data` y añadir una línea tuya a `…/app/.env` → los dos siguen ahí.
- [ ] `bash install.sh --dry-run` → explica los pasos y termina con «no se ha cambiado nada».
- [ ] `bash install.sh --uninstall` → se van la app y el acceso directo; `…/data` sigue.
- [ ] `bash install.sh --uninstall --remove-data` → pide escribir «borrar»; con otra cosa no borra.

### 6.3 Botones y procesos en Linux (26.1)

En un clon de `main` **dentro de Linux** (no en `/mnt/c`), con `uv sync` y `cai db upgrade`:

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

### 6.4 Docker en WSL2 (opcional)

- [ ] Activa en Docker Desktop la integración con tu Ubuntu y repite `docker compose up -d` desde el
      clon de Linux.

---

## 7. De vuelta en Windows y en GitHub

- [ ] Los botones «en tu agente» siguen abriendo Windows Terminal como antes, y `CAI_TERMINAL` no
      cambia nada.
- [ ] **Actions → CI** de la fusión en `main` (`db41a71`): en verde, con macOS (backend e
      instalador).
- [ ] **Actions → Release → «Run workflow»** con `v0.1.0` en `main` → notas en el resumen y el
      artefacto `candidatai-zip`, sin publicar nada (el job «release» sale saltado).
- [ ] Mira los dos README en github.com: el badge «Windows · macOS · Linux», la tabla «Agentes
      compatibles» con Codex y Antigravity probados, capturas y GIF.

---

## Al terminar

- Borra las demos que ya no quieras (`data-demo-agentes`, `data-demo-en`) y quita
  `$env:CAI_DATA_DIR` (o cierra esas ventanas).
- Comprueba que `config/policies.yaml` y `config/skill_aliases.yaml` no se quedaron con cambios de
  prueba: `git status` sin nada en `config/`.
- Pásame lo apuntado con «→»: con eso corrijo lo que haga falta y marco las pruebas en
  `docs/pruebas/PENDIENTES.md`.
