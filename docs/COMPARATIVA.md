# CandidatAI frente a AI Job Search y career-ops

Comparativa revisada el **25 de octubre de 2026**, con la primera release de CandidatAI (`v0.1.0`)
publicada, entre este repositorio y los dos proyectos abiertos de los que más ideas ha tomado:

- **[AI Job Search](https://github.com/MadsLorentzen/ai-job-search)** (Mads Lorentzen, MIT): un
  marco de instrucciones, skills y comandos para Claude Code, con CVs en LaTeX y portales daneses.
  Versión `v1.7.3` (19 de octubre).
- **[career-ops](https://github.com/career-ops-hq/career-ops)** (Santiago Fernández, MIT): un agente
  de búsqueda de empleo para una docena de CLIs de IA, con más de 140 scripts Node, un dashboard de
  terminal y una web en alfa. Versión `1.38.0` y web `0.16.0` (23 de octubre).

Los datos de los otros dos salen de sus repositorios, sus guías y sus `CHANGELOG` a esta fecha (los
dos tenían commits de esa semana; career-ops, del mismo día). Cambian deprisa: revisa sus README
antes de citar una cifra.

## En una frase

| Proyecto | Qué es |
|---|---|
| **CandidatAI** | Una **aplicación** local (API + base de datos + UI web + worker) con una interfaz para agentes (MCP y CLI con paridad). El estado, las reglas y las comprobaciones viven en código; el agente solo razona |
| **AI Job Search** | Un **conjunto de instrucciones y comandos** para Claude Code sobre ficheros (Markdown, CSV, LaTeX). El agente hace casi todo, guiado por los ficheros del perfil |
| **career-ops** | Un **agente con muchos modos** y scripts Node sobre ficheros de texto (Markdown, YAML, TSV), que funciona en **12 CLIs de IA**, con rutas gratuitas y modelos locales, un dashboard de terminal y una web en alfa |

La diferencia de fondo: en los otros dos el agente lee y escribe ficheros, y las reglas son sobre
todo instrucciones que el agente debería seguir (cada vez con más comprobaciones en código: el
filtro de inyección de AI Job Search, la comprobación de hechos del PDF de career-ops). En
CandidatAI el agente solo puede rellenar esquemas que el código valida, y las reglas importantes (no
inventar, no enviar nada, no seguir instrucciones de una oferta) se comprueban en código, sea cual
sea el agente (ADR-012).

Donde los otros dos van claramente por delante es en **comunidad y alcance**: decenas de miles de
estrellas, cientos de contribuidores e historias reales de gente contratada. Y career-ops, además, en
**cuántos agentes, fuentes de ofertas y países cubre**.

## Madurez y comunidad

| | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Estrellas / forks en GitHub | 0 / 0 (recién publicado) | ~65 000 / ~20 000 | ~77 000 / ~14 000 |
| Contribuidores | 1 (con agentes de IA) | ~90 | ~460 (y una flota de agentes que mantiene el repo) |
| Primera release | `v0.1.0`, 24 de octubre de 2026 | 2026 (va por la `v1.7.3`) | 2026 (va por la `1.38.0`, una cada ~semana) |
| Releases | Zip con suma SHA-256 desde el `CHANGELOG` | Etiquetas con `CHANGELOG` | release-please, npm y web por separado |
| Historia del autor | 🟡 `cai stats story` da la línea; publicarla es decisión tuya | ✅ 69 candidaturas, 20 entrevistas, 1 contrato | ✅ 740 ofertas, 68 candidaturas, 12 entrevistas, 1 oferta |
| Comunidad | ❌ | 🟡 Discussions e índice de forks por país | ✅ Discord, muro de contratados, manifiesto con firmas, prensa (WIRED, Business Insider), patrocinador |
| README en varios idiomas | 🟡 español e inglés | ❌ inglés | ✅ 19 idiomas |
| Tests y CI | ✅ ~3 000 tests de backend y ~340 de frontend; CI en Windows, Linux y macOS | ✅ CI con LaTeX, lint de skills y tests de Python (también en Windows desde octubre) | ✅ tests de Node, web y navegador |

## Instalación, una a una

Lo que hay que hacer para tener cada uno funcionando desde un equipo sin nada.

| | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Qué necesitas antes | **Nada** (ni Python, ni Node, ni administrador) | Claude Code, Python 3.10+, Bun y una distribución de LaTeX (`lualatex` y `xelatex`); opcional `pypdf` o Poppler | Node.js; Chromium de Playwright para los PDF; Git Bash en Windows para el lote |
| Cómo se instala | Windows: dos líneas de PowerShell. macOS y Linux: `curl … \| bash`. Opcional: `docker compose up -d --build` | `gh repo fork … --clone` (o un repositorio privado con este como `upstream`, porque un fork es público) y `python3 tools/install_portal_clis.py` | `npx @santifer/career-ops init` (o `git clone` + `npm install` + `npx playwright install chromium`) |
| Qué hace el instalador | Instala uv (que trae Python 3.12), descarga la release, **comprueba su SHA-256**, instala dependencias, Chromium y la base de datos, y crea el acceso directo | Ejecuta `bun install` en cada CLI de portal | Clona la última release en `./career-ops` e instala las dependencias |
| Cómo se arranca | **Icono «CandidatAI»** en el escritorio y el menú Inicio (Aplicaciones en macOS, menú en Linux): abre la app en el navegador. También `cai start` | `claude` en la carpeta, y `/setup` | `claude` (o `codex`, `opencode`, `agy`, `grok`…) en la carpeta; la TUI con `npm run serve:dashboard`; la web con `npm run ui` o `cd web && npm ci && npm run build && npm start` |
| Primera configuración | Página «Mi perfil» o skill `update-profile`; demo con `cai demo seed` | `/setup`: lee tu carpeta `documents/`, un CV pegado o una entrevista | En el chat la primera vez: CV, perfil y puestos |
| Sin agente, ¿qué puedes hacer? | Mucho: ver y triar ofertas, fuentes, alertas, kanban, calendario, embudo, cambiar plantilla o foto del CV, editar el perfil | Nada (todo pasa por Claude Code) | Escanear (sin tokens), la TUI y la web |
| Dónde quedan tus datos | `%LOCALAPPDATA%\CandidatAI\data` (o `~/.local/share/…`), fuera del código | En ficheros del repositorio, algunos versionados | `data/`, `reports/` y `output/` fuera de git, o una carpeta aparte con `CAREER_OPS_DATA_DIR` |
| Actualizar | Volver a ejecutar el instalador; tus datos no se tocan | Fusionar una etiqueta de `upstream`, con `check_upstream_updates.py` y `upstream_triage.py` para ver qué toca | Modo `update` con diff y comprobación de compatibilidad |
| Desinstalar | `install.ps1 -Uninstall` / `install.sh --uninstall` (deja tus datos) | Borrar la carpeta | Borrar la carpeta |
| Probado en un equipo limpio | ✅ Windows 11 recién instalado con la release real (25 de octubre); macOS y Linux en la CI, sin probar a mano desde la release | Sin datos | Sin datos; tiene guías para Windows (Git Bash, finales de línea) y NixOS |

En resumen: **CandidatAI es el único que se instala como un programa** (un comando, un icono y sin
nada previo) y el único que sirve para algo sin abrir un agente. Los otros dos se instalan como
proyectos de desarrollo: hay que tener Node o Bun y, en AI Job Search, LaTeX, y todo empieza en el
chat del agente. career-ops lo compensa con `npx … init`, que es un solo comando si ya tienes Node.

## Arquitectura y filosofía

| | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Forma | App: FastAPI + SQLite + React + worker | Instrucciones + comandos + utilidades en Python y Bun | Modos de agente + scripts Node + TUI en Go + web en Next.js |
| Dónde viven los datos | SQLite con eventos (`data/`, fuera de git) | CSV, Markdown y JSON en el repo (aviso: un fork es público) | Markdown, YAML y TSV (`data/`, fuera de git, o una carpeta externa) |
| Interfaz para el usuario | **UI web completa** en español e inglés | Chat con el agente + informe HTML + vista en Notion opcional | Chat + dashboard de terminal + web en alfa (pipeline, exploración, escaneos programados, rellenado de formularios, hoy, analítica, CV) |
| Interfaz para el agente | **MCP (casi 60 herramientas) + CLI `cai --json` con paridad comprobada** | Comandos `/…` y ficheros | Un router `/career-ops <modo>` y scripts |
| ¿La app llama a un LLM? | **Nunca** (ADR-001) | No (lo hace Claude Code) | Opcional: scripts que llaman a Gemini, a cualquier API compatible con OpenAI, a OpenRouter o a Ollama |
| Estado de cada oferta | Eventos validados contra una tabla de transiciones | Fila de un CSV | Fila de una tabla Markdown con estados canónicos |
| Defensas | En código: validación de esquemas, verificación determinista del CV, detección de inyección, techo de herramientas en segundo plano | Instrucciones + filtro determinista de la oferta (`posting_guard.py`: texto oculto, caracteres invisibles, líneas con forma de instrucción) + guardas de CI | Instrucciones + comprobación de hechos del PDF y de títulos del CV en código + el agente del CV en la web sin herramientas de escritura (en Claude Code) |
| Sistema principal | Windows 11 nativo; macOS, Linux y Docker también | Cualquiera con LaTeX y Bun | Cualquiera con Node (Windows con Git Bash) |
| Licencia | MIT | MIT | MIT (+ política de marca) |

## Agentes y modelos

Leyenda: ✅ lo tiene · 🟡 en parte · ❌ no lo tiene · 🚫 no lo tendrá a propósito.

| | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Fuente única de instrucciones | ✅ `AGENTS.md` (+ `CLAUDE.md`, que lo importa, y `GEMINI.md`, vacío a propósito) | 🟡 `CLAUDE.md` es la fuente; `AGENTS.md` apunta a él | ✅ `AGENTS.md` + un envoltorio por CLI |
| Skills en el estándar Agent Skills | ✅ 24 skills y 5 roles en `.agents/` (+ copias generadas) | 🟡 solo los portales | ✅ un skill router en `.agents/skills/career-ops/` |
| Configuración nativa generada desde una fuente | ✅ `sync_agents.py` (Claude Code, Codex, OpenCode, Qwen Code y Antigravity), comprobado en la CI | ❌ | 🟡 envoltorios y enlaces por CLI, mantenidos a mano |
| Claude Code | ✅ referencia; matriz completa (53/55 campos, 5/5 valoraciones, 5/5 CVs que pasan `eval cv`) | ✅ referencia, el único oficial | ✅ |
| Codex | ✅ matriz con una oferta (11/11 campos, 1/1 valoración, 1/1 CV) | 🟡 los portales; el resto, en forks de la comunidad | ✅ con guía propia |
| Antigravity CLI (sustituye a Gemini CLI) | 🟡 matriz: 54/55 campos y 5/5 valoraciones; el CV, cortado por el cupo gratuito | 🟡 los portales | ✅ con guía de su plan gratuito |
| **OpenCode** y **Qwen Code** (open-source) | 🟡 configuración generada; OpenCode medido solo con un modelo local de 20B, que no da la talla (0/55) en un equipo de 16 GB sin gráfica | ❌ | ✅ también para el lote en paralelo |
| Pi, Grok Build, Kimi, Copilot CLI, Cursor, Hermes | 🟡 sin configurar ni probar; valdrían si leen `AGENTS.md` y hablan MCP, o con la CLI `cai` | ❌ | ✅ (Hermes, solo lectura en la web y sin lote) |
| Gemini CLI | ❌ ya no sirve con cuentas gratuitas ni Pro (ver nota) | 🟡 mencionado | 🟡 envoltorio heredado |
| Subagentes con herramientas limitadas | ✅ Claude Code (nivel A); Codex, OpenCode y Qwen Code en nivel B | ✅ revisor con contexto limpio | 🟡 |
| Segundo plano / lote | ✅ Claude Code y OpenCode, hasta 4 a la vez, con techo de herramientas comprobado | ✅ `/rank` en paralelo | ✅ `batch-runner.sh` con Claude, OpenCode, Gemini, Qwen y Grok, filtro por empresa, límite de tiempo y regla de descarte |
| **Elegir y cambiar de agente desde la UI**, por acción | ✅ por defecto, por acción y en cada botón, con las capacidades comprobadas | n/a | 🟡 la web recuerda el CLI elegido |
| Elegir modelo o nivel de gasto | ✅ modelo por agente y por acción y niveles «Económico/Equilibrado/Máximo» | ❌ | ✅ `spend_tier` + filtro previo |
| Modelos gratuitos o locales | ✅ guía `MODELOS_GRATIS.md` con medidas reales y diagnóstico de Ollama | ❌ | ✅ guías (OpenCode + Ollama, Kimi, OpenRouter, Antigravity gratis) |
| Matriz de agentes probada | ✅ automatizada con `cai eval compat` y publicada en `evals/compat/REPORT.md` (22 de octubre) | ❌ | 🟡 verificaciones por CLI en sus docs |

**Nota sobre Gemini.** Google cortó Gemini CLI para cuentas gratuitas, Google AI Pro/Ultra y Gemini
Code Assist gratuito el 18 de junio de 2026 (responde 410) y lo sustituyó por **Antigravity CLI
(`agy`)**, que es de código cerrado, tiene un plan gratuito y lee `AGENTS.md`, `GEMINI.md` (este
manda si están los dos), los skills de `.agents/skills/` y el MCP de `.agents/mcp_config.json`.
Gemini CLI solo sigue con una clave de pago de la API de Gemini o con una licencia de empresa. Los
tres proyectos han llegado a lo mismo: `GEMINI.md` vacío o de paso, y Antigravity en su lugar.

## Funciones, una a una

### Entrada de ofertas

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Alta por URL o texto pegado | ✅ | ✅ | ✅ |
| APIs públicas de ATS (Greenhouse, Lever, Ashby) | ✅ diaria | ❌ | ✅ |
| Otros ATS con API (Personio, Teamtailor, Workable, SmartRecruiters, Recruitee…) | ✅ diaria y en `cai sources discover` | ❌ | ✅ |
| ATS que solo dan HTML (Workday, SuccessFactors, Zoho, Dover…) | 🚫 (ADR-016); se cubren con alertas, la extensión o el navegador del agente | ❌ | ✅ dentro de sus 55+ proveedores |
| Portales con API (InfoJobs, Adzuna, Manfred) | ✅ InfoJobs y Adzuna con claves; Manfred sin claves | ❌ | 🟡 otros feeds (Manfred, Remotive, WWR, HN «Who's hiring», Platsbanken en Suecia, Kalibrr, Computrabajo…) |
| Scrapers HTML de portales locales | 🚫 (ADR-016) | ✅ daneses + generador `/add-portal` | ✅ |
| Agregador con API pública (freehire.me) | ✅ | ✅ | ❌ |
| Alertas de empleo por correo (IMAP de solo lectura) | ✅ **varios buzones** | ❌ | ❌ |
| Botón de extensión del navegador para la página que ves | ✅ | ❌ | ❌ |
| El agente recorre portales con tu navegador | ✅ opcional | ❌ | 🟡 descubrimiento asistido en la web |
| LinkedIn por la búsqueda pública sin sesión | ✅ opcional y apagado (ADR-033) | ✅ | ❌ |
| Descubrir el tablero de ATS de tus empresas | ✅ `cai sources discover` | ❌ | ✅ `discover` |
| Lista de empresas objetivo preconfigurada | ❌ | ❌ | ✅ 100+ (laboratorios de IA, voz, plataformas, Europa, LatAm…) |
| Escaneos programados | ✅ el worker revisa cada fuente a diario | ❌ | ✅ en la web, con una tarea del sistema cada 15 min |
| Empresas recién financiadas desde feeds públicos | 🚫 descartado | ❌ | ✅ |
| Deduplicación y republicadas | ✅ huella, plataforma e id, «Republicada ×N» | ✅ claves de oferta y vistas | ✅ también por idioma |
| ¿Sigue abierta? | ✅ diaria, con evidencia | ✅ caducadas | ✅ con Playwright (`--verify`), también de las filas abiertas del tracker |
| Detección de texto oculto o dirigido a una IA | ✅ en código, con aviso en la UI | ✅ en código (`posting_guard.py`) | 🟡 instrucciones + validador de cobertura |
| Proxy de salida para escanear | 🚫 | ❌ | ✅ |

### Valorar el encaje

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Filtros duros (nivel, años, modalidad, zona, idiomas, sueldo mínimo) | ✅ en código, editables en «Mi perfil → Búsqueda» | ✅ deal-breakers + Language Gate | ✅ y para en seco si rompe una regla dura |
| Score explicado | ✅ 0-100 por componentes | ✅ 5 dimensiones | ✅ 1-5 con pesos y su origen |
| Similitud semántica local (embeddings) | ✅ opcional | ❌ | ❌ |
| Valoración razonada del agente | ✅ `assess-fit` | ✅ | ✅ informe A-H con veredicto |
| Triaje rápido con teclado | ✅ J/K, A, D, deshacer; descartar también desde la Bandeja | ❌ | 🟡 en la TUI |
| Señales de oferta dudosa | 🟡 rango ancho, empresa oculta o agencia, temporal, antigua y cribado con IA, sin puntuar | ❌ | ✅ 18 señales (también tasas que paga el candidato, prácticas sin pagar o identidad del recruiter) |
| Autorización de trabajo / patrocinio de visado | ❌ | ❌ | ✅ |
| Estrategia de nivel y arquetipo del puesto | 🟡 | ❌ | ✅ |
| Calibración por región (p. ej. ingeniería en Europa) | ❌ | ❌ | ✅ `eu-swe` |
| Eval publicado del matching | ✅ 80 casos, precision 0,88 / recall 0,95 | ❌ | 🟡 `eval-golden` |
| ¿Acierta el score? (calibración con resultados) | ✅ | ✅ `/setup` recalibra con lo que llegó a entrevista | ✅ `calibrate` |
| Aprender reglas de las sesiones | 🟡 `review-search` propone cambios, sin tocar nada | ❌ | ✅ `retro` propone reglas que `learn.mjs` aplica con tu OK |
| Huecos de skills agregados y plan de formación | ✅ | ✅ `/upskill` | ✅ |
| Valorar un curso o un proyecto | ✅ `training-plan` | ❌ | ✅ |
| Títulos cercanos para ampliar la búsqueda | ✅ `broaden-search` | ✅ `/setup --section search` | ✅ |
| Evaluación en lote en paralelo | 🟡 hasta 4 ejecuciones a la vez; cada lote es una ejecución | ✅ `/rank` | ✅ `batch` con varios workers |

### CV y carta

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| CV a medida sin inventar | ✅ cada línea cita su evidencia; el código la comprueba | ✅ por instrucciones + revisor | ✅ comprobación de hechos y de títulos en código |
| Verificación independiente | ✅ rol `verifier` en otra ejecución | ✅ revisor con contexto limpio | 🟡 |
| Formatos | Word + PDF (docx) o PDF (html) | PDF con LaTeX | PDF con HTML, Markdown, LaTeX para Overleaf |
| **Tu propio diseño como plantilla** (Word, PDF, imagen, Canva) | ✅ `import-cv-template` | 🟡 LaTeX o Typst con `/add-template` | 🟡 tu `resume.tex` |
| Foto, color y secciones por oferta sin gastar agente | ✅ | ❌ | ❌ |
| Foto según el país | ✅ | ❌ | 🟡 tamaño de papel según el país |
| Fijar secciones para que el agente no las toque | ❌ | ❌ | ✅ |
| Control de páginas | ✅ aviso `too_long` | ✅ páginas exactas y recorte por relevancia | 🟡 |
| Verificar la maquetación del PDF | ✅ cinco avisos con página y arreglo, en CV y carta | ✅ `verify_layout.py` | 🟡 `verify-cv-structure` |
| Comprobación ATS del texto del PDF | ✅ cobertura de keywords | ✅ | ✅ `verify-ats` (y en la web) |
| Carta a medida, a juego con el CV | ✅ | ✅ | ✅ con 4 ángulos |
| Respuestas de formularios | ✅ `prepare-application` | ❌ | ✅ |

### Candidatura y seguimiento

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Rellenar el formulario de la candidatura | ✅ Greenhouse, Lever, Ashby y genéricos | ❌ | ✅ en la web y en el modo `apply` |
| Enviar | ✅ **solo tras tu confirmación** (token de un uso) | 🚫 | 🚫 |
| Paquete de candidatura y archivo de lo enviado | ✅ | ✅ | ✅ |
| Kanban de procesos | ✅ solo se mueve con eventos | ❌ | 🟡 TUI y web |
| Pruebas técnicas y plazos | ✅ hitos con fecha en la ficha y el calendario | ❌ | ✅ `assessment-log` |
| Calendario `.ics` | ✅ un `.ics` por hito y feed para Google Calendar | ❌ | 🟡 lee el `.ics` de una invitación |
| Seguimientos (máx. 2) y agradecimientos | ✅ borradores | ✅ borradores | ✅ con cadencia, desactivables |
| Clasificar las respuestas de las empresas | ✅ IMAP, propuesta que aceptas | ✅ Gmail, propuesta que aceptas | ✅ `reply-watch` |
| Tu red de LinkedIn cruzada con las ofertas | ✅ «Conoces a N» en bandeja, triaje y ficha | ❌ | ✅ `linkedin-join` (script) |
| Mensaje a un recruiter o compañero (≤ 300 caracteres) | ✅ | ❌ | ✅ |
| Correo de candidatura | ✅ | ❌ | ✅ |
| Dosier de empresa con fuentes | ✅ | ✅ dentro de `/apply` | ✅ `deep` |
| Embudo y analítica | ✅ por fuente, puesto, semana, plantilla, carta, referencia | ✅ informe HTML | ✅ patrones, velocidad, latencia de rechazo, Sankey en la web |
| Exportar el tracker a una hoja de cálculo | ❌ | ✅ es un CSV | ✅ `query --csv` |
| Exportar a Notion | 🚫 descartado | ✅ solo lectura | ✅ plugin |

### Entrevistas y ofertas

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Guía y plan de preparación por días | ✅ guía en PDF y plan | ✅ | ✅ |
| Simulacro con feedback | ✅ | ✅ | ✅ |
| Repaso posterior y banco de historias STAR | ✅ (al perfil, con tu OK) | 🟡 | ✅ STAR+R, y actualiza score y contactos |
| Detector de banderas rojas de la empresa | ✅ en el dosier, con fuente y fecha | ❌ | ✅ `interview-redflag` |
| Comparar ofertas recibidas con tu mínimo | ✅ **sin que el agente vea tu mínimo** | ❌ | ✅ `salary-gap` |
| Preparar la negociación y revisar el contrato | ✅ sin proponer cifras | ❌ | ✅ |
| Datos salariales propios | ✅ CSV opcional | ✅ | ✅ |

### Perfil y uso diario

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Perfil validado y versionado | ✅ YAML con esquema | 🟡 Markdown | 🟡 YAML + Markdown + perfil maestro |
| Contexto que orienta sin respaldar hechos (estilo, narrativa…) | ✅ `data/contexto/` | ✅ perfil conductual y estilo | ✅ |
| Editar el perfil desde una UI, sin YAML | ✅ «Mi perfil» por bloques, con diff y deshacer | n/a | ✅ editor de perfil en la web |
| Crear el perfil desde tus documentos | ✅ `update-profile` con tu CV | ✅ `/setup` lee una carpeta (CV, LinkedIn, títulos, cartas de referencia) | ✅ en el chat |
| Enriquecer el perfil desde GitHub, portfolio, Scholar… | ✅ `expand`, con fuente y tu OK | ✅ `/expand` | ✅ `expand`, también con tus PRs y commits |
| Revisar tu perfil de LinkedIn | ✅ | ❌ | ❌ |
| Lanzar el agente desde la UI (terminal o segundo plano) | ✅ | ❌ | 🟡 workers en la web |
| Cola de encargos para la próxima sesión | ✅ | ❌ | ✅ `agent-inbox` |
| Resumen diario | ✅ `daily-summary` y la página Inicio | ❌ | ✅ «Hoy» en la web |
| Modo demo con datos inventados | ✅ `cai demo seed` (es y en), que sobrevive a las actualizaciones | ❌ | ✅ `examples/` |
| UI en varios idiomas | ✅ español e inglés, con selector | n/a | 🟡 modos e informes traducidos |
| Licencia, `CONTRIBUTING`, `SECURITY` | ✅ | ✅ | ✅ (+ aviso legal y política de marca) |

## Lo que solo tiene CandidatAI

- **Se instala como un programa**: un comando sin nada previo, la suma SHA-256 comprobada, un icono
  en el escritorio y la app abierta en el navegador. Probado en un Windows 11 recién instalado.
- **Sirve sin agente** para lo de cada día: bandeja, triaje, fuentes, alertas, kanban, calendario,
  embudo, perfil y cambios de plantilla. El agente solo entra para razonar.
- Una **UI web completa** y bilingüe, que no es una vista sobre ficheros sino la app misma.
- **MCP + CLI con paridad comprobada por test**: un agente sin MCP hace exactamente lo mismo.
- **Eventos como fuente de verdad**: historial completo y estados que no se corrompen.
- **El código comprueba el CV**: cada línea apunta a una evidencia del perfil que tiene que
  existir, y un rol independiente lo verifica.
- **Importar tu CV con cualquier diseño** (Word, PDF, imagen, Canva) como plantilla, y cambiar
  plantilla, foto o color en segundos sin gastar agente.
- **Candidatura asistida con envío**: rellena el formulario y envía, pero solo tras tu clic.
- **Fuentes que no dependen de scraping**: alertas por correo con varios buzones, botón de
  extensión, InfoJobs y Adzuna.
- **Privacidad del salario**: el agente nunca ve tu mínimo.
- **Segundo plano con techo de herramientas comprobado**: la ejecución sin ventana solo tiene las
  herramientas MCP de su acción (ADR-032).
- **Matriz de agentes medida y publicada** (`cai eval compat`), en vez de compatibilidad declarada.
- **Revisión del perfil de LinkedIn** frente a las ofertas que apruebas.

## Lo que nos falta (y se podría hacer)

Reordenado el 2026-10-25, con todo lo de la revisión anterior (fases 24 a 26) ya hecho. Lo primero
ya no son funciones sino **que la gente lo conozca y lo pruebe**: es justo lo que preparan las fases
28.4 y 28.5.

| # | Qué | Lo tiene | Por qué merece la pena | Esfuerzo | Dónde |
|---|---|---|---|---|---|
| 1 | **Portada, historia y lanzamiento** (README con gancho, la historia con números reales, publicarlo en listas y canales) | ambos | Lo que hace famosos a los otros dos no son las funciones, sino la historia y la comunidad | Medio | 28.4 y 28.5 |
| 2 | **Comunidad** (Discussions o Discord, muro de contratados, plantillas de issues) | career-ops | Sin ella, todo el mantenimiento depende de una persona | Bajo para empezar | 28.4 (plantillas) |
| 3 | **Instalador más robusto con red mala** (avisar de que es la red y reintentar Chromium) y sin las herramientas de desarrollo (`uv sync --no-dev`) | — | Lo encontró la prueba en el Windows limpio (ver `dev/pruebas/fase-28.1-prueba-manual.md`) | Bajo | Sin fecha |
| 4 | **Probar más agentes de verdad**: OpenCode y Qwen Code con un modelo en la nube, y Pi, Grok Build, Copilot CLI y Cursor | career-ops | Hoy solo Claude Code, Codex y Antigravity están medidos | Medio | Sin fecha |
| 5 | **Exportar ofertas y candidaturas a CSV** | ambos | Para quien quiere su hoja de cálculo o irse con sus datos | Bajo | Sin fecha |
| 6 | **Lista de empresas objetivo de ejemplo**, con su ATS ya resuelto | career-ops | Arrancar con fuentes sin buscar a mano | Bajo | Sin fecha |
| 7 | **Más señales de oferta dudosa** (tasas al candidato, prácticas sin pagar, identidad del recruiter) y que cuenten en el score | career-ops | Hoy se avisan pero no pesan | Bajo | Sin fecha |
| 8 | **Fijar secciones del CV** que el agente no puede tocar | career-ops | Útil para un resumen o una sección que quieres siempre igual | Bajo | Sin fecha |
| 9 | **Leer el `.ics` de una invitación** de entrevista y crear el hito | career-ops | Menos tecleo; hoy el hito se crea a mano o por la respuesta clasificada | Bajo | Sin fecha |
| 10 | Autorización de trabajo y visado como filtro duro, y calibración por región | career-ops | Solo si se busca fuera de la UE | Bajo | Sin fecha |
| 11 | README en más idiomas | career-ops | Llegar a más gente; la UI ya está preparada para más idiomas | Bajo por idioma | Sin fecha |
| 12 | Probar macOS y Linux desde la release real | — | Hoy solo la CI y los tests del instalador | Bajo (con un equipo) | 28.1 |

## Lo que no vamos a hacer (y qué regla lo impide)

| Qué | Lo tiene | Por qué no | Regla |
|---|---|---|---|
| Que la app llame a un LLM (Gemini, OpenRouter, Ollama desde el código) | career-ops | El razonamiento lo pone tu agente; la app no tiene claves ni SDKs. Los modelos gratuitos o locales se usan **a través de agentes open-source** | Regla dura 1, ADR-001 |
| Enviar candidaturas sin tu confirmación, o en lote | — (ninguno lo hace) | Nada sale sin tu clic, oferta a oferta | Regla dura 5, POLICIES §5 |
| Enviar correos o mensajes | — | Solo borradores que copias tú | Regla dura 5 |
| Candidaturas automáticas en LinkedIn, o usar tu sesión o cookies para leerlo | — | Riesgo para tu cuenta y contra sus condiciones | Regla dura 6, ADR-009 |
| Resolver o esquivar captchas, proxies para evitar bloqueos | career-ops (proxy) | Un bloqueo se respeta: se para y se avisa | Regla dura 6, ADR-033 |
| Scrapers HTML de portales y ATS sin API | ambos | Se cubren con alertas, captura y el navegador del agente | ADR-016 |
| Sincronizar con Notion o subir tu pipeline a terceros | ambos | Tus datos no salen de tu equipo | Reglas 3 y 5, decisión del plan 13-22 |
| Plugins de scraping de pago (Apify…) | career-ops | Scraping de terceros y datos fuera | Reglas 1, 5 y 6 |
| Descubrir empresas financiadas desde feeds externos | career-ops | Fuera del foco | Decisión del plan 13-22 |
| CVs en LaTeX | ambos | Ya hay dos motores (Word y HTML) e importación de cualquier diseño, sin instalar LaTeX | Decisión del plan 13-22 |
| Lógica específica de un agente en el producto | — | Todo lo específico va en `.agents/manifest.yaml` y en lo que genera `sync_agents.py` | Regla dura 2 |
| Segundo plano con un agente que no pueda limitar sus herramientas | — | La garantía del segundo plano es justo ese techo | ADR-032 |
| Inventar o «mejorar» datos del candidato | — | Todo sale de `data/profile.yaml` y se verifica | Regla dura 7 |
| Datos personales en el repositorio (fork público con tus datos) | riesgo en AI Job Search | Tus datos solo en `data/` y `.env`, fuera de git | Regla dura 3 |
| Proponer o deducir una cifra salarial | — | La cifra la pones tú; el agente no ve tu mínimo | POLICIES §4, fase 21 |

## Conclusión

En funciones, CandidatAI ya cubre el ciclo entero (ofertas, triaje, CV, carta, candidatura,
seguimiento, entrevistas, ofertas recibidas) y casi todos los extras de los otros dos. Va por
delante en lo que necesita una app: instalación de un clic, UI, estado fiable, comprobaciones en
código y candidatura asistida. La distancia con career-ops en agentes, que era la gran carencia de
la revisión anterior, se ha cerrado en lo importante (cinco agentes configurados, elegir desde la UI,
modelos y niveles de gasto, matriz medida).

Donde se queda atrás ahora es en **alcance**: career-ops cubre más fuentes, más países y más señales,
y los dos tienen una comunidad, historias reales y decenas de miles de estrellas, mientras que
CandidatAI acaba de publicar su primera versión. Lo que más rinde a partir de aquí no es otra
función, sino la portada, la historia y el lanzamiento (28.4 y 28.5).
