# CandidatAI frente a AI Job Search y career-ops

Comparativa de octubre de 2026 entre CandidatAI (este repositorio, tras la fase 22) y los dos
proyectos abiertos de los que más ideas ha tomado:

- **[AI Job Search](https://github.com/MadsLorentzen/ai-job-search)** (Mads Lorentzen, MIT): un
  marco de instrucciones, skills y comandos para Claude Code, con CVs en LaTeX y portales daneses.
- **[career-ops](https://github.com/career-ops-hq/career-ops)** (Santiago Fernández, MIT): un agente
  de búsqueda de empleo para muchos CLIs de IA, con scripts Node, un dashboard de terminal y
  decenas de modos.

Los datos de los otros dos proyectos salen de sus README públicos en esta fecha. Pueden haber
cambiado desde entonces.

## En una frase

| Proyecto | Qué es |
|---|---|
| **CandidatAI** | Una **aplicación** local (API + base de datos + UI web + worker) con una interfaz para agentes (MCP y CLI con paridad). El estado, las reglas y las comprobaciones viven en código; el agente solo razona |
| **AI Job Search** | Un **conjunto de instrucciones y comandos** para Claude Code sobre ficheros (Markdown, CSV, LaTeX). El agente hace casi todo, guiado por los ficheros del perfil |
| **career-ops** | Un **agente con muchos modos** y scripts Node sobre ficheros de texto (Markdown, YAML, TSV), con un dashboard de terminal y soporte para una docena de CLIs |

La diferencia de fondo: en los otros dos el agente lee y escribe ficheros, y las reglas son
instrucciones que el agente debería seguir. En CandidatAI el agente solo puede rellenar esquemas
que el código valida, y las reglas importantes (no inventar, no enviar nada, no seguir
instrucciones de una oferta) se comprueban en código, sea cual sea el agente (ADR-012).

## Arquitectura y filosofía

| | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Forma | App: FastAPI + SQLite + React + worker | Instrucciones + comandos + utilidades | Modos de agente + scripts Node |
| Dónde viven los datos | SQLite con eventos (`data/`, fuera de git) | CSV, Markdown y JSON en el repo | Markdown, YAML y TSV (`data/`, fuera de git) |
| Interfaz para el usuario | **UI web completa** (bandeja, triaje, ficha, kanban, embudo…) | Chat con el agente + informe HTML | Chat + dashboard de terminal (Go) + web en alfa |
| Interfaz para el agente | **MCP + CLI `cai --json` con paridad comprobada** | Comandos `/…` y ficheros | Modos `/career-ops …` y scripts |
| ¿La app llama a un LLM? | **Nunca** (ADR-001) | No (lo hace Claude Code) | Opcional (script con la API de Gemini, OpenRouter, Ollama) |
| Agentes | Claude Code (referencia), Codex; cualquiera con MCP o terminal | Claude Code; parcial en Codex, Gemini CLI | ~12 CLIs (Claude Code, Codex, OpenCode, Gemini, Copilot, Cursor…) |
| Estado de cada oferta | Eventos validados contra una tabla de transiciones | Fila de un CSV | Fila de una tabla Markdown con estados canónicos |
| Defensas | En código: validación de esquemas, verificación determinista del CV, detección de inyección | Instrucciones + guardas de CI | Instrucciones + comprobación de hechos del PDF |
| Sistema principal | Windows 11 (nativo) | Cualquiera con LaTeX y Bun | Cualquiera con Node (Docker, NixOS, guía de Windows) |
| Licencia | **Sin licencia todavía** | MIT | MIT (+ política de marca) |

## Funciones, una a una

Leyenda: ✅ lo tiene · 🟡 en parte · ❌ no lo tiene · 🚫 no lo tendrá a propósito

### Entrada de ofertas

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Alta por URL o texto pegado | ✅ | ✅ | ✅ |
| APIs públicas de ATS (Greenhouse, Lever, Ashby) | ✅ diaria | ❌ | ✅ |
| Otros ATS y tableros (Workable, Wellfound, RSS…) | ❌ | ❌ | ✅ 55+ módulos |
| Portales con API (InfoJobs, Adzuna) | ✅ con claves | ❌ | 🟡 otros feeds y tableros |
| Scrapers HTML de portales locales | 🚫 (ADR-016) | ✅ daneses | ✅ |
| Alertas de empleo por correo (IMAP de solo lectura) | ✅ | ❌ | ❌ |
| Botón de extensión del navegador para la página que ves | ✅ | ❌ | ❌ |
| El agente recorre portales con tu navegador | ✅ opcional | ❌ | ❌ |
| LinkedIn por la búsqueda pública sin sesión | ✅ opcional y apagado (ADR-033) | ✅ | ❌ |
| Descubrir el tablero de ATS de tus empresas | ✅ `cai sources discover` | ❌ | ✅ |
| Empresas recién financiadas desde feeds públicos | 🚫 descartado | ❌ | ✅ |
| Lista de empresas objetivo preconfigurada | ❌ | ❌ | ✅ 100+ |
| Deduplicación y republicadas | ✅ huella, plataforma e id, «Republicada ×N» | 🟡 vistas | ✅ |
| ¿Sigue abierta? | ✅ diaria, con evidencia | ✅ caducadas | ✅ con Playwright |
| Detección de texto oculto o dirigido a una IA | ✅ en código, con aviso en la UI | 🟡 por instrucciones | 🟡 por instrucciones |
| Proxy de salida para escanear | 🚫 | ❌ | ✅ |

### Valorar el encaje

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Filtros duros (nivel, años, modalidad, zona, idiomas) | ✅ en código | ✅ deal-breakers + Language Gate | ✅ |
| Score explicado | ✅ 0-100 por componentes | ✅ 5 dimensiones | ✅ 1-5 con pesos y su origen |
| Similitud semántica local (embeddings) | ✅ opcional | ❌ | ❌ |
| Valoración razonada del agente | ✅ `assess-fit` | ✅ | ✅ informe A-H |
| Triaje rápido con teclado | ✅ J/K, A, D, deshacer | ❌ | 🟡 en la TUI |
| Autorización de trabajo / patrocinio de visado | ❌ | ❌ | ✅ |
| Estrategia de nivel y arquetipo del puesto | 🟡 | ❌ | ✅ |
| Eval publicado del matching | ✅ 80 casos, precision 0,88 / recall 0,95 | ❌ | 🟡 `evals/` |
| ¿Acierta el score? (calibración con resultados) | ✅ | ❌ | ✅ |
| Huecos de skills agregados y plan de formación | ✅ | ✅ `/upskill` | ✅ |
| Valorar un curso o un proyecto | ✅ `training-plan` | ❌ | ✅ |
| Títulos cercanos para ampliar la búsqueda | ✅ `broaden-search` | ❌ | ✅ |
| Evaluación en lote en paralelo | 🟡 en segundo plano, de una en una | ✅ `/rank` | ✅ `batch` con varios workers |

### CV y carta

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| CV a medida sin inventar | ✅ cada línea cita su evidencia; el código la comprueba | ✅ por instrucciones + revisor | ✅ comprobación de hechos |
| Verificación independiente | ✅ rol `verifier` en otra ejecución | ✅ revisor con contexto limpio | 🟡 |
| Formatos | Word + PDF (docx) o PDF (html) | PDF con LaTeX | PDF con HTML, Markdown, LaTeX para Overleaf |
| **Tu propio diseño como plantilla** (Word, PDF, imagen, Canva) | ✅ `import-cv-template` | 🟡 LaTeX/Typst con `/add-template` | 🟡 tu `resume.tex` |
| Foto, color y secciones por oferta sin gastar agente | ✅ | ❌ | ❌ |
| Foto según el país | ✅ | ❌ | ❌ |
| Control de páginas y recorte | ✅ aviso `too_long` | ✅ recorte puntuado | 🟡 |
| Comprobación ATS del texto del PDF | ✅ cobertura de keywords | ✅ | 🟡 PDF legible por ATS |
| Carta a medida, a juego con el CV | ✅ | ✅ | ✅ con 4 ángulos |
| Respuestas de formularios | ✅ `prepare-application` | ❌ | ✅ |

### Candidatura y seguimiento

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Rellenar el formulario de la candidatura | ✅ Greenhouse, Lever, Ashby y genéricos | ❌ | 🟡 lee campos y genera respuestas |
| Enviar | ✅ **solo tras tu confirmación** (token de un uso) | 🚫 | 🚫 |
| Paquete de candidatura y archivo de lo enviado | ✅ | ✅ | ✅ |
| Kanban de procesos | ✅ solo se mueve con eventos | ❌ | 🟡 TUI |
| Hitos y calendario `.ics` | ✅ | ❌ | ❌ |
| Seguimientos (máx. 2) y agradecimientos | ✅ borradores | ✅ borradores | ✅ con cadencia |
| Clasificar las respuestas de las empresas | ✅ IMAP, propuesta que aceptas | ✅ Gmail | ✅ `reply-watch` |
| Tu red de LinkedIn cruzada con las ofertas | ✅ CSV, «Conoces a N» | ❌ | ❌ |
| Mensaje a un recruiter o compañero (≤ 300 caracteres) | ✅ | ❌ | ✅ |
| Dosier de empresa con fuentes | ✅ | ✅ dentro de `/apply` | ✅ `deep` |
| Embudo y analítica | ✅ por fuente, puesto, semana, plantilla, carta, referencia | ✅ informe HTML | ✅ patrones y estadísticas |
| Exportar a Notion | 🚫 descartado | ✅ solo lectura | ✅ plugin |

### Entrevistas y ofertas

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Plan de preparación por días | ✅ | ✅ | ✅ |
| Simulacro con feedback | ✅ | ✅ | ✅ |
| Repaso posterior y banco de historias STAR | ✅ (al perfil, con tu OK) | 🟡 | ✅ STAR+R |
| Detector de banderas rojas de la empresa | ❌ | ❌ | ✅ |
| Comparar ofertas recibidas con tu mínimo | ✅ **sin que el agente vea tu mínimo** | ❌ | ✅ `salary-gap` |
| Preparar la negociación y revisar el contrato | ✅ sin proponer cifras | ❌ | ✅ |
| Datos salariales propios | ✅ CSV opcional | ✅ | ✅ |

### Perfil, agentes y uso

| Función | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Perfil validado y versionado | ✅ YAML con esquema | 🟡 Markdown | 🟡 YAML + Markdown |
| Contexto que orienta sin respaldar hechos (estilo, narrativa…) | ✅ `data/contexto/` | ✅ perfil conductual y estilo | ✅ |
| Enriquecer el perfil desde GitHub, portfolio, Scholar… | ❌ | ✅ `/expand` | ✅ `expand` |
| Revisar tu perfil de LinkedIn | ✅ | ❌ | ❌ |
| Lanzar el agente desde la UI (terminal o segundo plano) | ✅ | ❌ | ❌ |
| Cola de encargos para la próxima sesión | ✅ | ❌ | ✅ `agent-inbox` |
| Modo demo con datos inventados | ✅ `cai demo seed` | ❌ | ✅ `examples/` |
| Instalación de un comando | ❌ | ❌ | ✅ `npx … init` |
| Docker / macOS / Linux documentados | ❌ (solo Windows probado) | ✅ | ✅ |
| Modelos gratuitos o locales | 🟡 si tu CLI los usa | ❌ | ✅ guía de presupuesto |
| Actualizar sin pisar tus datos | ✅ datos fuera del código | ✅ herramientas de triaje upstream | ✅ `update` |
| README en varios idiomas | 🟡 español e inglés | ❌ | ✅ 17 idiomas |
| UI en varios idiomas | ✅ español e inglés, con selector | n/a | n/a |

## Lo que solo tiene CandidatAI

- Una **UI web completa**: bandeja, triaje con teclado, ficha con el CV y sus renders, kanban,
  calendario, embudo, respuestas, skills, plataformas, alertas y la página del agente.
- **MCP + CLI con paridad comprobada por test**: un agente sin MCP hace exactamente lo mismo.
- **Eventos como fuente de verdad**: historial completo y estados que no se corrompen.
- **El código comprueba el CV**: cada línea apunta a una evidencia del perfil que tiene que
  existir, y un rol independiente lo verifica.
- **Importar tu CV con cualquier diseño** (Word, PDF, imagen, Canva) como plantilla, y cambiar
  plantilla, foto o color en segundos sin gastar agente.
- **Candidatura asistida de verdad**: rellena el formulario y solo envía tras tu confirmación.
- **Fuentes que no dependen de scraping**: alertas por correo y botón de extensión.
- **Privacidad del salario**: el agente nunca ve tu mínimo.
- **Red de LinkedIn y referencias** cruzadas con tus ofertas.

## Lo que nos falta (y se podría hacer)

Ordenado por lo que más aportaría, de mayor a menor.

| # | Qué | Lo tiene | Por qué merece la pena | Esfuerzo |
|---|---|---|---|---|
| 1 | **Licencia, `CONTRIBUTING`, `SECURITY`, `CHANGELOG` y releases** | ambos | Sin licencia, nadie puede usar el código legalmente; sin versiones no se sabe qué cambió | Bajo |
| 2 | **README y guía en inglés** (y español) | career-ops (17 idiomas) | El público de GitHub lee inglés | Medio |
| 3 | **Instalación sencilla** (un script `setup.ps1` / `setup.sh` o Docker) y prueba en macOS/Linux | career-ops | Hoy hacen falta uv, Node, pnpm y LibreOffice o Chromium a mano | Medio |
| 4 | **Más conectores de ATS con API pública**: Workable, SmartRecruiters, Recruitee, Personio, Teamtailor | career-ops | Mucha empresa europea usa estos ATS; son APIs públicas, sin scraping | Medio |
| 5 | **Enriquecer el perfil desde enlaces públicos** (GitHub, portfolio, Scholar) | ambos | Proyectos y logros que no están en el CV; con tu confirmación antes de escribir | Bajo (un skill) |
| 6 | **Autorización de trabajo y visado** como filtro duro | career-ops | Ofertas que excluyen patrocinio, si buscas fuera de la UE | Bajo |
| 7 | **Evaluación en lote en paralelo** | ambos | Hoy el segundo plano va de una en una | Medio |
| 8 | **Detector de banderas rojas** de una empresa antes de la entrevista | career-ops | Rotación, despidos, reseñas; encaja en `research-company` | Bajo |
| 9 | ~~**UI en inglés**~~ ✅ hecho (fase 23.6) | — | Para que la use alguien que no lea español | Alto |
| 10 | **Estrategia de nivel / arquetipo del puesto** en la valoración | career-ops | Ayuda a decidir a qué nivel presentarse | Bajo |
| 11 | **Herramienta para traer cambios del repositorio original** sin pisar lo tuyo | AI Job Search | Útil si otros lo usan con sus datos | Bajo |
| 12 | **Guía de agentes con modelos gratuitos o locales** (OpenCode + Ollama…) | career-ops | Sin suscripción de pago; la app no cambia, solo el agente | Bajo (documentación) |

## Lo que no vamos a hacer (y qué regla lo impide)

| Qué | Lo tiene | Por qué no | Regla |
|---|---|---|---|
| Que la app llame a un LLM (Gemini, OpenRouter, Ollama desde el código) | career-ops | El razonamiento lo pone tu agente; la app no tiene claves ni SDKs | Regla dura 1, ADR-001 |
| Enviar candidaturas sin tu confirmación, o en lote | — (ninguno lo hace) | Nada sale sin tu clic, oferta a oferta | Regla dura 5, POLICIES §5 |
| Enviar correos o mensajes | — | Solo borradores que copias tú | Regla dura 5 |
| Candidaturas automáticas en LinkedIn, o usar tu sesión o cookies para leerlo | — | Riesgo para tu cuenta y contra sus condiciones | Regla dura 6, ADR-009 |
| Resolver o esquivar captchas, proxies para evitar bloqueos | career-ops (proxy) | Un bloqueo se respeta: se para y se avisa | Regla dura 6, ADR-033 |
| Scrapers HTML de portales sin API | ambos | Se cubren con alertas, captura y el navegador del agente | ADR-016 |
| Sincronizar con Notion o subir tu pipeline a terceros | ambos | Tus datos no salen de tu equipo | Reglas 3 y 5, decisión del plan 13-22 |
| Plugins de scraping de pago (Apify…) | career-ops | Scraping de terceros y datos fuera | Reglas 1, 5 y 6 |
| Descubrir empresas financiadas desde feeds externos | career-ops | Descartado en el plan 13-22: fuera del foco | Decisión del plan 13-22 |
| CVs en LaTeX | ambos | Ya hay dos motores (Word y HTML) e importación de cualquier diseño | Decisión del plan 13-22 |
| Lógica específica de un agente en el producto | — | Todo lo específico va en `.agents/manifest.yaml` | Regla dura 2 |
| Inventar o «mejorar» datos del candidato | — | Todo sale de `data/profile.yaml` y se verifica | Regla dura 7 |
| Datos personales en el repositorio (fork público con tus datos) | riesgo en ambos | Tus datos solo en `data/` y `.env`, fuera de git | Regla dura 3 |
| Proponer o deducir una cifra salarial | — | La cifra la pones tú; el agente no ve tu mínimo | POLICIES §4, fase 21 |

## Conclusión

CandidatAI ya cubre casi todo lo que hacen bien los otros dos: el ciclo entero (ofertas, triaje,
CV, carta, candidatura, seguimiento, entrevistas, ofertas recibidas) y la mayoría de sus extras
(calibración, republicadas, huecos de skills, títulos cercanos, red de contactos, negociación).
Donde va por delante es en lo que necesita una app: UI, estado fiable, comprobaciones en código y
la candidatura asistida.

Donde se queda atrás no es en funciones, sino en **lo que hace que otros lo usen**: licencia,
inglés, instalación sencilla, más sistemas operativos y una página de GitHub que lo enseñe. Eso es
lo siguiente.
