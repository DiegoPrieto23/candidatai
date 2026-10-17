# CandidatAI frente a AI Job Search y career-ops

Comparativa revisada el **16 de octubre de 2026**, tras la fase 23, entre CandidatAI (este
repositorio) y los dos proyectos abiertos de los que más ideas ha tomado:

- **[AI Job Search](https://github.com/MadsLorentzen/ai-job-search)** (Mads Lorentzen, MIT): un
  marco de instrucciones, skills y comandos para Claude Code, con CVs en LaTeX y portales daneses.
- **[career-ops](https://github.com/career-ops-hq/career-ops)** (Santiago Fernández, MIT): un agente
  de búsqueda de empleo para una docena de CLIs de IA, con más de 140 scripts Node, un dashboard de
  terminal y una web en alfa.

Los datos de los otros dos proyectos salen de sus repositorios a esta fecha (los dos tenían commits
de esa misma semana). Cambian deprisa: revisa sus README antes de citar una cifra.

## En una frase

| Proyecto | Qué es |
|---|---|
| **CandidatAI** | Una **aplicación** local (API + base de datos + UI web + worker) con una interfaz para agentes (MCP y CLI con paridad). El estado, las reglas y las comprobaciones viven en código; el agente solo razona |
| **AI Job Search** | Un **conjunto de instrucciones y comandos** para Claude Code sobre ficheros (Markdown, CSV, LaTeX). El agente hace casi todo, guiado por los ficheros del perfil |
| **career-ops** | Un **agente con muchos modos** y scripts Node sobre ficheros de texto (Markdown, YAML, TSV), que funciona en **12 CLIs de IA**, con rutas gratuitas y modelos locales, un dashboard de terminal y una web en alfa |

La diferencia de fondo: en los otros dos el agente lee y escribe ficheros, y las reglas son
instrucciones que el agente debería seguir. En CandidatAI el agente solo puede rellenar esquemas
que el código valida, y las reglas importantes (no inventar, no enviar nada, no seguir
instrucciones de una oferta) se comprueban en código, sea cual sea el agente (ADR-012).

Donde career-ops va claramente por delante es en **cuántos agentes y modelos admite y lo fácil que
es cambiar entre ellos**. Es la base de la fase 24 (ver «Lo que nos falta»).

## Arquitectura y filosofía

| | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Forma | App: FastAPI + SQLite + React + worker | Instrucciones + comandos + utilidades | Modos de agente + scripts Node |
| Dónde viven los datos | SQLite con eventos (`data/`, fuera de git) | CSV, Markdown y JSON en el repo (aviso: un fork es público) | Markdown, YAML y TSV (`data/`, fuera de git, o una carpeta externa con `CAREER_OPS_DATA_DIR`) |
| Interfaz para el usuario | **UI web completa** en español e inglés | Chat con el agente + informe HTML | Chat + dashboard de terminal (Go) + web en alfa (pipeline, rellenado de formularios, escaneos programados) |
| Interfaz para el agente | **MCP + CLI `cai --json` con paridad comprobada** | Comandos `/…` y ficheros | Un router `/career-ops <modo>` y scripts |
| ¿La app llama a un LLM? | **Nunca** (ADR-001) | No (lo hace Claude Code) | Opcional: scripts que llaman a Gemini, a cualquier API compatible con OpenAI, a OpenRouter o a Ollama |
| Estado de cada oferta | Eventos validados contra una tabla de transiciones | Fila de un CSV | Fila de una tabla Markdown con estados canónicos |
| Defensas | En código: validación de esquemas, verificación determinista del CV, detección de inyección | Instrucciones + guardas de CI | Instrucciones + comprobación de hechos del PDF en código |
| Sistema principal | Windows 11 (nativo, instalador `install.ps1`) | Cualquiera con LaTeX y Bun | Cualquiera con Node (`npx … init`, Docker, NixOS) |
| Licencia | MIT | MIT | MIT (+ política de marca) |

## Agentes y modelos

La parte en la que más nos separa career-ops. Leyenda: ✅ lo tiene · 🟡 en parte · ❌ no lo tiene ·
🚫 no lo tendrá a propósito.

| | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Fuente única de instrucciones | ✅ `AGENTS.md` (+ `CLAUDE.md`, que lo importa, y `GEMINI.md`, vacío a propósito) | 🟡 `CLAUDE.md` es la fuente; `AGENTS.md` apunta a él | ✅ `AGENTS.md` + un envoltorio por CLI |
| Skills en el estándar Agent Skills | ✅ `.agents/skills/` (+ copia generada para Claude Code) | 🟡 solo los portales | ✅ un skill router en `.agents/skills/career-ops/` |
| Configuración nativa generada desde una fuente | ✅ `sync_agents.py` (Claude Code, Codex, OpenCode, Qwen Code y Antigravity) | ❌ | 🟡 envoltorios y enlaces por CLI, mantenidos a mano |
| Claude Code | ✅ referencia, probado | ✅ referencia | ✅ |
| Codex | 🟡 configuración generada, **sin probar** | 🟡 parcial | ✅ con guía propia |
| **OpenCode** (open-source) | 🟡 configuración generada y comprobada con su binario (24.3), sin probar con un modelo | ❌ | ✅ también para el lote en paralelo (`opencode run`) |
| **Qwen Code** (open-source) | 🟡 configuración generada (24.3), sin probar | ❌ | ✅ |
| Antigravity CLI (sustituye a Gemini CLI) | 🟡 MCP del espacio de trabajo generado (24.3), sin probar; nivel C | 🟡 mencionado | ✅ con guía de su plan gratuito |
| Gemini CLI | ❌ **ya no sirve con cuentas gratuitas ni Pro** (ver nota); deshabilitado en el registro y `GEMINI.md` vacío a propósito (24.3) | 🟡 `gemini -p` en un subagente | 🟡 `GEMINI.md` vacío a propósito |
| Pi, Grok, Kimi, Copilot CLI, Cursor, Hermes | 🟡 sin probar, valdrían si leen `AGENTS.md` | ❌ | ✅ |
| Subagentes con herramientas limitadas | ✅ Claude Code (nivel A); Codex, OpenCode y Qwen Code en nivel B (OpenCode y Qwen generan cada rol con solo sus herramientas, pendiente de probar) | ✅ revisor con contexto limpio | 🟡 |
| Segundo plano / lote | ✅ Claude Code y OpenCode (24.5), hasta 4 a la vez con tope por agente (25.4), con herramientas limitadas | ✅ `/rank` en paralelo | ✅ `batch-runner.sh --cli claude\|opencode\|gemini\|qwen --model …` |
| Elegir el agente | ✅ desde la UI (24.4); `CAI_AGENT` como respaldo | ❌ | ✅ el CLI que abras; `--cli` en el lote |
| **Cambiar de agente desde la UI**, por acción | ✅ por defecto, por acción y «con Claude Code ▾» en cada botón, con las capacidades de cada agente comprobadas (24.4) | n/a | 🟡 la web en alfa usa el CLI o la clave que le des |
| Elegir modelo o nivel de gasto | ✅ modelo o preset por agente y por acción (24.4) y niveles «Económico/Equilibrado/Máximo» que se aplican con un clic y se deshacen (24.6) | ❌ | ✅ `spend_tier` economy/standard/premium + filtro previo que ahorra evaluaciones |
| **Modelos gratuitos o locales** (Ollama, OpenRouter `:free`) | ✅ guía `MODELOS_GRATIS.md` (Ollama en Windows, modelos por memoria, privacidad por vía) y diagnóstico de Ollama solo con metadatos (24.6) | ❌ | ✅ guías verificadas (OpenCode + Ollama, Kimi, OpenRouter) y rutas de coste cero |
| Esquemas para el agente | ✅ `cai schema` / `get_schema` con ejemplos y errores con `hint` (24.2) | n/a | 🟡 |
| Matriz de agentes probada | 🟡 automatizada con `cai eval compat` (24.6, resultados en `evals/compat/REPORT.md`); medida: Claude Code sin MCP (5/5). El resto, pendiente de la pasada del usuario | ❌ | 🟡 verificaciones por CLI en sus docs |

**Nota sobre Gemini.** Google cortó Gemini CLI para cuentas gratuitas, Google AI Pro/Ultra y Gemini
Code Assist gratuito el 18 de junio de 2026 (responde 410) y lo ha sustituido por **Antigravity CLI
(`agy`)**, que es de código cerrado, tiene un plan gratuito y lee `AGENTS.md`, `GEMINI.md` (este
manda si están los dos), los skills de `.agents/skills/` y el MCP del espacio de trabajo en
`.agents/mcp_config.json`. Gemini CLI solo sigue funcionando con una clave de pago de la API de
Gemini o con una licencia de empresa. Hasta la fase 24, el README de CandidatAI decía «Gemini CLI»
como agente válido sin que hubiera configuración MCP para él; desde la 24.3 ya no figura como
compatible y Antigravity CLI ocupa su sitio.

## Funciones, una a una

### Entrada de ofertas

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Alta por URL o texto pegado | ✅ | ✅ | ✅ |
| APIs públicas de ATS (Greenhouse, Lever, Ashby) | ✅ diaria | ❌ | ✅ |
| Otros ATS con API (Workable, SmartRecruiters, Personio, Teamtailor, Recruitee, Workday…) | 🟡 Personio, Teamtailor, Workable, SmartRecruiters y Recruitee, diaria y en `cai sources discover` (25.1); Workday y los que solo dan HTML, no | ❌ | ✅ más de 55 proveedores |
| Portales con API (InfoJobs, Adzuna, Manfred) | ✅ InfoJobs y Adzuna con claves; Manfred sin claves (25.1) | ❌ | 🟡 otros feeds (Manfred, Remotive, WWR, HN «Who's hiring», Telegram…) |
| Scrapers HTML de portales locales | 🚫 (ADR-016) | ✅ daneses + generador `/add-portal` | ✅ |
| Agregador con API pública (freehire.me) | ✅ por título, país y remoto (25.1) | ✅ | ❌ |
| Alertas de empleo por correo (IMAP de solo lectura) | ✅ | ❌ | ❌ |
| Botón de extensión del navegador para la página que ves | ✅ | ❌ | ❌ |
| El agente recorre portales con tu navegador | ✅ opcional | ❌ | 🟡 descubrimiento asistido en la web alfa |
| LinkedIn por la búsqueda pública sin sesión | ✅ opcional y apagado (ADR-033) | ✅ | ❌ |
| Descubrir el tablero de ATS de tus empresas | ✅ `cai sources discover` | ❌ | ✅ |
| Lista de empresas objetivo preconfigurada | ❌ | ❌ | ✅ 100+ |
| Empresas recién financiadas desde feeds públicos | 🚫 descartado | ❌ | ✅ |
| Deduplicación y republicadas | ✅ huella, plataforma e id, «Republicada ×N» | 🟡 vistas | ✅ |
| ¿Sigue abierta? | ✅ diaria, con evidencia | ✅ caducadas | ✅ con Playwright (`--verify`) |
| Confirmar en la web de la empresa una oferta de agregador | 🟡 aviso de republicada | ❌ | ✅ regla explícita |
| Detección de texto oculto o dirigido a una IA | ✅ en código, con aviso en la UI | 🟡 por instrucciones | 🟡 por instrucciones + validador de cobertura |
| Proxy de salida para escanear | 🚫 | ❌ | ✅ |

### Valorar el encaje

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Filtros duros (nivel, años, modalidad, zona, idiomas) | ✅ en código | ✅ deal-breakers + Language Gate | ✅ |
| Score explicado | ✅ 0-100 por componentes | ✅ 5 dimensiones | ✅ 1-5 con pesos y su origen (texto, estructura o estimación) |
| Similitud semántica local (embeddings) | ✅ opcional | ❌ | ❌ (solo léxica, para reutilizar un CV) |
| Valoración razonada del agente | ✅ `assess-fit` | ✅ | ✅ informe A-H |
| Triaje rápido con teclado | ✅ J/K, A, D, deshacer | ❌ | 🟡 en la TUI |
| Señales de oferta dudosa (agencia sin licencia, rango salarial demasiado ancho, temporal oculto, cribado con IA…) | 🟡 rango ancho, empresa oculta o agencia, temporal, publicada hace meses y cribado con IA, sin puntuar (25.3); licencias de agencias, no | ❌ | ✅ `oferta-signals` |
| Autorización de trabajo / patrocinio de visado | ❌ | ❌ | ✅ |
| Estrategia de nivel y arquetipo del puesto | 🟡 | ❌ | ✅ |
| Calibración por región (p. ej. ingeniería en Europa) | ❌ | ❌ | ✅ `eu-swe` |
| Eval publicado del matching | ✅ 80 casos, precision 0,88 / recall 0,95 | ❌ | 🟡 `eval-golden` |
| ¿Acierta el score? (calibración con resultados) | ✅ | ❌ | ✅ |
| Huecos de skills agregados y plan de formación | ✅ | ✅ `/upskill` | ✅ |
| Valorar un curso o un proyecto | ✅ `training-plan` | ❌ | ✅ |
| Títulos cercanos para ampliar la búsqueda | ✅ `broaden-search` | ❌ | ✅ |
| Evaluación en lote en paralelo | 🟡 en segundo plano, hasta 4 ejecuciones a la vez (25.4); cada lote es una ejecución | ✅ `/rank` | ✅ `batch` con varios workers |

### CV y carta

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| CV a medida sin inventar | ✅ cada línea cita su evidencia; el código la comprueba | ✅ por instrucciones + revisor | ✅ comprobación de hechos en código |
| Verificación independiente | ✅ rol `verifier` en otra ejecución | ✅ revisor con contexto limpio | 🟡 |
| Formatos | Word + PDF (docx) o PDF (html) | PDF con LaTeX | PDF con HTML, Markdown, LaTeX para Overleaf |
| **Tu propio diseño como plantilla** (Word, PDF, imagen, Canva) | ✅ `import-cv-template` | 🟡 LaTeX/Typst con `/add-template` | 🟡 tu `resume.tex` |
| Foto, color y secciones por oferta sin gastar agente | ✅ | ❌ | ❌ |
| Foto según el país | ✅ | ❌ | ❌ |
| Control de páginas | ✅ aviso `too_long` | ✅ páginas exactas y recorte por relevancia | 🟡 |
| **Verificar la maquetación del PDF** (títulos huérfanos, huecos, pie) | ✅ cinco avisos con página y arreglo, en CV y carta, y en `cai eval cv` (25.5) | ✅ `verify_layout.py` | 🟡 `verify-cv-structure` |
| Comprobación ATS del texto del PDF | ✅ cobertura de keywords | ✅ | ✅ `verify-ats` |
| Carta a medida, a juego con el CV | ✅ | ✅ | ✅ con 4 ángulos |
| Respuestas de formularios | ✅ `prepare-application` | ❌ | ✅ |

### Candidatura y seguimiento

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Rellenar el formulario de la candidatura | ✅ Greenhouse, Lever, Ashby y genéricos | ❌ | 🟡 lee campos y genera respuestas; rellenado en la web alfa |
| Enviar | ✅ **solo tras tu confirmación** (token de un uso) | 🚫 | 🚫 |
| Paquete de candidatura y archivo de lo enviado | ✅ | ✅ | ✅ |
| Kanban de procesos | ✅ solo se mueve con eventos | ❌ | 🟡 TUI y web alfa |
| Hitos y calendario `.ics` | ✅ | ❌ | ❌ |
| Seguimientos (máx. 2) y agradecimientos | ✅ borradores | ✅ borradores | ✅ con cadencia |
| Clasificar las respuestas de las empresas | ✅ IMAP, propuesta que aceptas | ✅ Gmail | ✅ `reply-watch` |
| Tu red de LinkedIn cruzada con las ofertas | ✅ CSV, «Conoces a N» en bandeja, triaje y ficha | ❌ | ✅ `linkedin-join` (script, sin UI) |
| Mensaje a un recruiter o compañero (≤ 300 caracteres) | ✅ | ❌ | ✅ |
| Correo de candidatura | ✅ | ❌ | ✅ |
| Dosier de empresa con fuentes | ✅ | ✅ dentro de `/apply` | ✅ `deep` |
| Embudo y analítica | ✅ por fuente, puesto, semana, plantilla, carta, referencia | ✅ informe HTML | ✅ patrones, velocidad del embudo, latencia de rechazo, resumen semanal |
| Exportar a Notion | 🚫 descartado | ✅ solo lectura | ✅ plugin |

### Entrevistas y ofertas

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Plan de preparación por días | ✅ | ✅ | ✅ |
| Simulacro con feedback | ✅ | ✅ | ✅ |
| Repaso posterior y banco de historias STAR | ✅ (al perfil, con tu OK) | 🟡 | ✅ STAR+R |
| Detector de banderas rojas de la empresa | ✅ `red_flags` del dosier, con fuente y fecha, y preguntas en `prepare-interview` (25.3) | ❌ | ✅ `interview-redflag` |
| Comparar ofertas recibidas con tu mínimo | ✅ **sin que el agente vea tu mínimo** | ❌ | ✅ `salary-gap` |
| Preparar la negociación y revisar el contrato | ✅ sin proponer cifras | ❌ | ✅ |
| Datos salariales propios | ✅ CSV opcional | ✅ | ✅ |

### Perfil, instalación y comunidad

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Perfil validado y versionado | ✅ YAML con esquema | 🟡 Markdown | 🟡 YAML + Markdown + perfil maestro |
| Contexto que orienta sin respaldar hechos (estilo, narrativa…) | ✅ `data/contexto/` | ✅ perfil conductual y estilo | ✅ |
| Enriquecer el perfil desde GitHub, portfolio, Scholar… | ✅ `expand`, con la fuente de cada dato y tu OK (25.2) | ✅ `/expand` | ✅ `expand` |
| Revisar tu perfil de LinkedIn | ✅ | ❌ | ❌ |
| Lanzar el agente desde la UI (terminal o segundo plano) | ✅ | ❌ | 🟡 workers en la web alfa |
| Cola de encargos para la próxima sesión | ✅ | ❌ | ✅ `agent-inbox` |
| Modo demo con datos inventados | ✅ `cai demo seed` (es y en) | ❌ | ✅ `examples/` |
| Instalación de un comando | ✅ `install.ps1` (Windows) | 🟡 `install_portal_clis.py` | ✅ `npx … init` |
| macOS / Linux / Docker documentados | ❌ (solo Windows probado) | ✅ | ✅ |
| Actualizar sin pisar tus datos | ✅ datos fuera del código | ✅ triaje de cambios upstream | ✅ `update` |
| Licencia, `CONTRIBUTING`, `SECURITY` | ✅ | ✅ | ✅ |
| `CHANGELOG` y releases | 🟡 releases por etiqueta, sin `CHANGELOG` | ✅ | ✅ también en npm |
| README en varios idiomas | 🟡 español e inglés | ❌ | ✅ 18 idiomas |
| UI en varios idiomas | ✅ español e inglés, con selector | n/a | n/a |
| Comunidad | ❌ | 🟡 Discussions, índice de forks | ✅ Discord, muro de contratados, manifiesto, prensa |

## Lo que solo tiene CandidatAI

- Una **UI web completa** y bilingüe: bandeja, triaje con teclado, ficha con el CV y sus renders,
  kanban, calendario, embudo, respuestas, skills, plataformas, alertas y la página del agente.
- **MCP + CLI con paridad comprobada por test**: un agente sin MCP hace exactamente lo mismo.
- **Eventos como fuente de verdad**: historial completo y estados que no se corrompen.
- **El código comprueba el CV**: cada línea apunta a una evidencia del perfil que tiene que
  existir, y un rol independiente lo verifica.
- **Importar tu CV con cualquier diseño** (Word, PDF, imagen, Canva) como plantilla, y cambiar
  plantilla, foto o color en segundos sin gastar agente.
- **Candidatura asistida de verdad**: rellena el formulario y solo envía tras tu confirmación.
- **Fuentes que no dependen de scraping**: alertas por correo, botón de extensión, InfoJobs y Adzuna.
- **Privacidad del salario**: el agente nunca ve tu mínimo.
- **Red de LinkedIn integrada en la app**: «Conoces a N» en bandeja, triaje y ficha, y el embudo
  «Por referencia».
- **Segundo plano con techo de herramientas comprobado**: la ejecución sin ventana solo tiene las
  herramientas MCP de su acción, y las demás se deniegan (ADR-032).

## Lo que nos falta (y se podría hacer)

Reordenado el 2026-10-16: lo primero es **poder usar varios agentes, algunos open-source y
gratuitos, y cambiar entre ellos** (fase 24). Después, la fase 25 (fuentes, perfil, ofertas
dudosas, coste y calidad del CV) y la 26 (macOS, Linux y Docker).

| # | Qué | Lo tiene | Por qué merece la pena | Esfuerzo | Dónde |
|---|---|---|---|---|---|
| 1 | **Registro de agentes y diagnóstico**: qué agentes hay, cuáles están instalados, qué saben hacer (MCP, subagentes, segundo plano, ver imágenes, web, navegador) y si son open-source | career-ops | Base para todo lo demás; hoy el manifiesto solo sabe de dos agentes | Medio | 24.1 |
| 2 | **Esquemas y errores para cualquier modelo** (`cai schema`, errores de validación que dicen qué campo arreglar) | — | Los modelos abiertos y pequeños fallan sobre todo en esquemas estrictos; el pendiente de la 12.3 | Bajo | 24.2 |
| 3 | **Agentes nuevos**: OpenCode y Qwen Code (open-source), Antigravity CLI (gratis, cerrado) y Codex con modelos locales (`--oss`); corregir lo de Gemini | career-ops | Usar la app sin suscripción de pago y sin depender de un proveedor | Medio | 24.3 |
| 4 | **Elegir y cambiar de agente desde la UI**, global y por acción, con el modelo de cada uno | career-ops (en parte) | Extraer con un modelo local gratis y redactar el CV con el más capaz, sin tocar variables de entorno | Medio | 24.4 |
| 5 | **Segundo plano con varios agentes** (OpenCode y, si se puede garantizar, Codex) | career-ops (`--cli` en el lote) | Que el lote no dependa de Claude Code, con el mismo techo de herramientas | Medio | 24.5 |
| 6 | **Guía de modelos gratuitos y locales + matriz probada por agente y modelo** | career-ops | Recomendar modelos con datos (`cai eval cv`) y no por opinión | Medio | 24.6 |
| 7 | **Más conectores de ATS con API pública**: Personio, Teamtailor, Workable, SmartRecruiters, Recruitee, y feeds como Manfred o freehire.me | ambos | Mucha empresa española y europea usa estos ATS; son APIs, sin scraping (ADR-016) | Medio | 25.1 ✅ |
| 8 | **Enriquecer el perfil desde enlaces públicos** (GitHub, portfolio, Scholar), con tu OK antes de escribir | ambos | Proyectos y logros que no están en el CV | Bajo (un skill) | 25.2 ✅ |
| 9 | **Señales de oferta dudosa y banderas rojas** en `assess-fit` y `research-company` | career-ops | Evita perder tiempo con ofertas fantasma, agencias o condiciones escondidas | Bajo | 25.3 ✅ |
| 10 | **Lote en paralelo y coste por skill y por agente** (tokens, turnos, tiempo) con un filtro previo por score | ambos | Saber qué cuesta cada oferta y gastar solo en las que pasan el umbral | Medio | 25.4 ✅ |
| 11 | **Verificar la maquetación del PDF** (huérfanos, huecos, pie) | AI Job Search | Hoy solo se avisa de que sobra una página | Bajo | 25.5 ✅ |
| 12 | **macOS, Linux o Docker** | ambos | Solo si se busca que lo use más gente; hoy el instalador es solo para Windows | Medio | 26 |
| 13 | **`CHANGELOG`, historia con números reales y comunidad** | career-ops | Lo que hace famoso a career-ops no son las funciones, sino la historia y la comunidad | Bajo | 25.6 (sin comunidad) |
| 14 | Autorización de trabajo y visado como filtro duro | career-ops | Solo si se busca fuera de la UE | Bajo | Sin fecha |

Hecho desde la revisión anterior: licencia MIT, `CONTRIBUTING` y `SECURITY`, README y guía en
inglés, instalación con un clic (`install.ps1`, `cai start`, releases) y UI en inglés (fase 23).

## Lo que no vamos a hacer (y qué regla lo impide)

| Qué | Lo tiene | Por qué no | Regla |
|---|---|---|---|
| Que la app llame a un LLM (Gemini, OpenRouter, Ollama desde el código) | career-ops | El razonamiento lo pone tu agente; la app no tiene claves ni SDKs. Para usar modelos gratuitos o locales, la fase 24 los usa **a través de agentes open-source** (OpenCode, Qwen Code, Codex `--oss`). Se revisará solo si, tras la matriz de la 24.6, ningún agente con modelo local da la talla en las tareas cerradas (extraer, clasificar) | Regla dura 1, ADR-001 |
| Enviar candidaturas sin tu confirmación, o en lote | — (ninguno lo hace) | Nada sale sin tu clic, oferta a oferta | Regla dura 5, POLICIES §5 |
| Enviar correos o mensajes | — | Solo borradores que copias tú | Regla dura 5 |
| Candidaturas automáticas en LinkedIn, o usar tu sesión o cookies para leerlo | — | Riesgo para tu cuenta y contra sus condiciones | Regla dura 6, ADR-009 |
| Resolver o esquivar captchas, proxies para evitar bloqueos | career-ops (proxy) | Un bloqueo se respeta: se para y se avisa | Regla dura 6, ADR-033 |
| Scrapers HTML de portales sin API | ambos | Se cubren con alertas, captura y el navegador del agente | ADR-016 |
| Sincronizar con Notion o subir tu pipeline a terceros | ambos | Tus datos no salen de tu equipo | Reglas 3 y 5, decisión del plan 13-22 |
| Plugins de scraping de pago (Apify…) | career-ops | Scraping de terceros y datos fuera | Reglas 1, 5 y 6 |
| Descubrir empresas financiadas desde feeds externos | career-ops | Descartado en el plan 13-22: fuera del foco | Decisión del plan 13-22 |
| CVs en LaTeX | ambos | Ya hay dos motores (Word y HTML) e importación de cualquier diseño | Decisión del plan 13-22 |
| Lógica específica de un agente en el producto | — | Todo lo específico va en `.agents/manifest.yaml` y en lo que genera `sync_agents.py` | Regla dura 2 |
| Segundo plano con un agente que no pueda limitar sus herramientas | — | La garantía del segundo plano es justo ese techo | ADR-032 |
| Inventar o «mejorar» datos del candidato | — | Todo sale de `data/profile.yaml` y se verifica | Regla dura 7 |
| Datos personales en el repositorio (fork público con tus datos) | riesgo en AI Job Search | Tus datos solo en `data/` y `.env`, fuera de git | Regla dura 3 |
| Proponer o deducir una cifra salarial | — | La cifra la pones tú; el agente no ve tu mínimo | POLICIES §4, fase 21 |

## Conclusión

CandidatAI cubre el ciclo entero (ofertas, triaje, CV, carta, candidatura, seguimiento,
entrevistas, ofertas recibidas) y casi todos los extras de los otros dos, y va por delante en lo
que necesita una app: UI, estado fiable, comprobaciones en código y candidatura asistida.

Donde se queda atrás es en **con qué IA se puede usar**: career-ops funciona en una docena de CLIs,
con modelos gratuitos y locales y cambiando de uno a otro sin esfuerzo, mientras que CandidatAI
solo está probado con Claude Code. La fase 24 lo corrige sin renunciar a lo que nos diferencia:
cada agente nuevo hereda las mismas comprobaciones en código, y el segundo plano solo se abre a los
agentes que pueden limitar sus herramientas.
