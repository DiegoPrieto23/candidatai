# Roadmap

Cada fase tiene su encargo en `dev/prompts/NN-*.md`. Con cualquier agente: pídele "implementa la fase
NN" o usa el skill `implementar-fase` (`/implementar-fase 03` en Claude Code, `$implementar-fase 03`
en Codex). Al cerrar una fase, el agente actualiza su estado aquí.
Estados: ⏳ pendiente · 🚧 en curso · ✅ hecha.

| # | Fase | Estado | Resultado visible |
|---|---|---|---|
| 01 | Arranque del repo | ✅ | `uv run pytest` y `pnpm build` funcionan; CI mínimo con `sync_agents.py --check` |
| 02 | Núcleo de datos | ✅ | Esquema, migraciones, eventos, proyección de etapas, CLI `jh` |
| 03 | Alta de ofertas | ✅ | `jh jobs add-url` y `add-text` crean ofertas deduplicadas y con `risk_flags` |
| 04 | Interfaz para agentes | ✅ | Servidor MCP + CLI con paridad; funciona desde Claude Code y Codex |
| 05 | Perfil del candidato | ✅ | `data/profile.yaml` validado y versionado; `get_profile` |
| 05b | Preferencias de CV en el perfil | ✅ | El perfil admite plantilla por defecto, foto y reglas de plantilla; `demo/profile.example.yaml` vuelve a validar |
| 06 | Frontend base | ✅ | UI con bandeja de ofertas, ficha y alta por URL o texto; `jh serve` |
| 07 | Matching y triaje | ✅ | Filtros duros, score, skill `evaluar-encaje`, aprobar o descartar en la UI |
| 08 | CV a medida con plantillas | ✅ | `generar-cv` produce CVs verificados; plantilla, foto y color se cambian en la UI sin agente; tu CV de Word como base |
| 08.1 | ↳ Contenido, verificación y motor docx | ✅ | `generar-cv` produce un PDF verificado con `ats-simple` y la oferta pasa a `cv_ready` |
| 08.2 | ↳ Foto, renders múltiples y UI | ✅ | Plantilla, foto y color se cambian en la UI sin agente; `clasica-foto` |
| 08.3 | ↳ Importar plantillas desde Word y «Mi CV» | ✅ | Subes tu CV de Word, se convierte en plantilla por defecto y los CVs a medida salen con tu diseño, tu orden de secciones y tus secciones extra |
| 08c | Carta de presentación | ✅ | `generar-carta` redacta y verifica la carta según tus indicaciones (generales y de cada oferta); TXT para pegar y PDF a juego con el CV |
| 08c.1 | ↳ Indicaciones, contenido, verificación y render básico | ✅ | `generar-carta` guarda y verifica una carta que sigue tus indicaciones; PDF con `carta-simple` y TXT |
| 08c.2 | ↳ Diseño a juego con el CV | ✅ | Carta con la cabecera y el estilo de tu plantilla (integradas, html e importadas con `build-letter`) |
| 08c.3 | ↳ API, UI y paquete de candidatura | ✅ | Sección «Carta de presentación» en la ficha y la carta en el paquete de candidatura |
| 08b | Plantillas html | ✅ | Importar diseños desde PDF o imagen (Canva…), también como «Mi CV», y plantilla integrada de dos columnas |
| 09 | Conectores de ATS y scheduler | ✅ | Ingesta diaria de empresas objetivo sin intervención |
| 09b | Alertas, captura y búsqueda con navegador | ✅ | Las alertas de LinkedIn y otros portales llegan solas por correo, cualquier oferta entra con un clic desde el navegador y, opcionalmente, el agente recorre portales |
| 09b.1 | ↳ Ofertas resumen y alertas por correo | ✅ | Las alertas de correo (IMAP en solo lectura o `data/inbox/`) crean ofertas resumen en «Alertas», ordenadas por prefiltro y que caducan solas |
| 09b.2 | ↳ Botón «Enviar a Job Hunter» | ✅ | Extensión de Chromium que manda la oferta que estás viendo y completa los resúmenes |
| 09b.3 | ↳ Plataformas y búsqueda con navegador | ✅ | `list_sources`, `save_source`, `record_source_run` y pantalla «Plataformas»; LinkedIn solo lo activa el usuario |
| 10 | Seguimiento y analítica | ✅ | Kanban, seguimientos pendientes, dashboard del embudo y paquete de candidatura |
| 10.1 | ↳ Seguimiento: kanban, ficha de proceso y calendario | ✅ | Kanban que solo mueve con eventos, hitos con hora de Madrid y contactos, aviso de seguimientos, `list_followups_due`, `list_upcoming` y `.ics` por hito y en feed |
| 10.2 | ↳ Analítica: dashboard del embudo | ✅ | Página «Embudo»: conversión por paso, fuente, puesto y semana; tiempo hasta la primera respuesta; motivos de descarte; `get_funnel_stats` |
| 10.3 | ↳ Paquete de candidatura | ✅ | `save_application_answers` y sección «Paquete de candidatura»: CV elegido, respuestas editables con botón de copiar y hueco de la carta (08c) |
| 11 | Candidatura asistida | ✅ | Rellenado con Playwright y envío tras tu confirmación |
| 11.1 | ↳ Motor de rellenado y envío protegido | ✅ | El worker rellena Greenhouse, Lever, Ashby y formularios genéricos, se para con captcha o login y solo envía con una confirmación de un solo uso |
| 11.2 | ↳ Revisión, envío y UI | ✅ | Pantalla de revisión en la ficha, «Enviar» con el nombre de la empresa, «Lo termino yo» y prueba manual con una oferta real |
| 12 | Demo, compatibilidad y portfolio | ✅ | Modo demo, matriz de agentes probada, evals publicados |
| 12.1 | ↳ Modo demo | ✅ | `jh demo seed` llena `data-demo/` con 60 ofertas, 8 semanas de historial y 2 CVs; banner en la UI |
| 12.2 | ↳ Evals de matching y de CV | ✅ | 80 casos de matching con `evals/REPORT.md` y `jh eval cv` sobre 10 casos |
| 12.3 | ↳ Compatibilidad, README y seguridad | ✅ | Matriz de agentes probada, README de portfolio y repositorio revisado |
| 13 | Contexto y documentos | ✅ | `data/contexto/*.md` (estilo, perfil conductual, criterios, narrativa) que orientan sin respaldar hechos; `data/documentos/` y archivo de cada candidatura enviada |
| 14 | Huecos de skills y vocabulario | ✅ | Página «Skills»: ausentes agregadas; «es lo mismo que…» añade el alias y recalcula; huecos reales → skill `plan-formacion` |
| 15 | Respuestas por correo y seguimientos | ✅ | Los correos de las empresas proponen el evento (entrevista, rechazo…) en la ficha y tú lo aceptas; borradores de seguimiento y agradecimiento |
| 15.1 | ↳ Ingesta y clasificador | ✅ | IMAP en solo lectura (solo cabeceras salvo lo que casa con una candidatura), `<untrusted_email>`, rol `clasificador` y skill `revisar-respuestas` |
| 15.2 | ↳ Bandeja «Respuestas» | ✅ | Aceptar (tal cual o cambiada) o ignorar, solo desde la UI; aviso en la ficha y «Revisar respuestas» en Inicio |
| 15.3 | ↳ Borradores de seguimiento | ✅ | `save_message_draft`, tope de 2 seguimientos, `thanks_due`, skill `redactar-seguimiento` y sección «Borradores» |
| 16 | Ofertas vivas, republicadas y búsqueda ampliada | ✅ | Aviso de oferta cerrada o republicada; títulos parecidos; descubrir tableros de Greenhouse/Lever/Ashby de tus empresas |
| 16.1 | ↳ ¿Sigue abierta? y republicadas | ✅ | `jobs.signals` (ADR-028), `check_job_open`, tarea diaria `check_open`, aviso en la ficha que propone descartar, «Republicada ×N» en bandeja y triaje |
| 16.2 | ↳ Búsqueda ampliada | ✅ | `get_search_titles` y skill `ampliar-busqueda`; `jh sources discover` sobre Greenhouse, Lever y Ashby |
| 17 | Entrevistas: simulacro y repaso | ✅ | Plan de preparación, simulacro con feedback, repaso posterior con notas y historias STAR nuevas |
| 18 | Contactos, mensajes e investigación de empresas | ✅ | Tus contactos de LinkedIn (CSV) cruzados con tus ofertas, borradores de mensaje y dosier de empresa con fuentes |
| 18.1 | ↳ Red de LinkedIn y referencias | ✅ | `jh contacts import-linkedin` (sin emails), «Conoces a N» en bandeja, triaje y ficha, «Añadir al proceso» con su papel, `get_job_contacts` y embudo «Por referencia» |
| 18.2 | ↳ Mensajes e investigación de empresa | ✅ | Skills `redactar-mensaje` (LinkedIn ≤ 300 caracteres o correo con adjuntos) e `investigar-empresa` (dosier con fuentes en la ficha y en `data/documentos/empresas/`) |
| 19 | Lote en segundo plano | ✅ | «En segundo plano» además de «En terminal» para los skills que no preguntan (fase 2 de la ADR-024) |
| 19.1 | ↳ Ejecución en segundo plano | ✅ | `launch.headless`, `agent_runs` en un hilo del worker con solo las herramientas MCP de la acción (las demás denegadas), progreso, preguntas, tiempo máximo y cancelación |
| 19.2 | ↳ Cola de encargos y UI | ✅ | «Dejar para mi próxima sesión», `list_agent_requests` / `complete_agent_request`, skill `atender-encargos` y página «Agente» |
| 20 | Calibración y patrones | ✅ | «¿Acierta el score?»: respuesta por tramo de score, veredicto, fuente, plantilla y carta; retrospectiva semanal |
| 21 | Ofertas recibidas y salario | ✅ | Comparar ofertas recibidas y la distancia a tu mínimo sin exponerlo al agente; preparar la negociación |
| 22 | LinkedIn por sus endpoints públicos (opcional) | ✅ | Búsqueda pública sin sesión, apagada por defecto y con límites estrictos; ADR que matiza la 016 |
| 23 | CandidatAI | ✅ | Nombre y logo nuevos, identificadores en inglés, barra lateral, UI en inglés y español e instalación con un clic |
| 23.1 | ↳ Renombrado a CandidatAI | ✅ | Todo dice CandidatAI; `cai` en vez de `jh`; MCP `candidatai`; repositorio renombrado |
| 23.2 | ↳ Skills y roles en inglés | ✅ | `/generate-cv 42`, `/prepare-interview 42`…; roles `writer`, `verifier`… |
| 23.3 | ↳ Barra lateral | ✅ | Navegación lateral agrupada, plegable y con cajón en el móvil |
| 23.4 | ↳ Instalación fácil | ✅ | `cai start`, `install.ps1`, acceso directo y releases con la UI compilada |
| 23.5a | ↳ Logo | ✅ | Logo nuevo, elegido entre propuestas, en la UI, el favicon, la extensión, el icono y el banner |
| 23.6 | ↳ UI en inglés y español | ✅ | Toda la UI traducida, con un selector de idioma junto al del tema |
| 23.5b | ↳ Medios y README | ✅ | Capturas en los dos idiomas, GIF y vídeo; README sin la comparativa |
| 24 | Varios agentes: open-source, gratuitos y a elegir | ✅ | Usar la app con OpenCode, Qwen Code, Antigravity o Codex con modelos locales, además de Claude Code, y cambiar de agente y modelo desde la UI, globalmente o por acción |
| 24.1 | ↳ Registro de agentes y diagnóstico | ✅ | `cai agents list` y `cai agents doctor`: qué agentes hay, cuáles están instalados, qué saben hacer y si son open-source |
| 24.2 | ↳ Esquemas y errores para cualquier modelo | ✅ | `cai schema` y `get_schema`; errores de validación con `path` y pista |
| 24.3 | ↳ Agentes nuevos | ✅ | Configuración generada para OpenCode, Qwen Code y Antigravity; Codex con `--oss`; Gemini CLI fuera |
| 24.4 | ↳ Elegir y cambiar de agente | ✅ | Sección «Agentes» con capacidades, agente por defecto y por acción, «con Claude Code ▾» en cada botón |
| 24.5 | ↳ Segundo plano con varios agentes | ✅ | «En segundo plano» también con OpenCode (`process-jobs` y `assess-fit`), con el techo en una configuración propia de cada ejecución; Codex y Qwen Code, aún no |
| 24.6 | ↳ Modelos gratuitos, niveles de gasto y matriz | ✅ (matriz con Claude Code, Codex y Antigravity; la local, no viable en el equipo de pruebas) | Guía de modelos gratis y locales, diagnóstico de Ollama, «Económico/Equilibrado/Máximo» y matriz probada por agente y modelo |
| 25 | Más fuentes, perfil más rico, ofertas dudosas, coste y calidad del CV | ✅ | Más ATS con API, `expand`, señales de oferta dudosa, coste por oferta y agente, maquetación del PDF, `CHANGELOG` y el perfil editable desde la UI |
| 25.1 | ↳ Conectores de ATS y portales con API | ✅ | Personio, Teamtailor, Workable, SmartRecruiters y Recruitee, más Manfred y freehire.me; `cai sources discover` para todos |
| 25.2 | ↳ Skill `expand` | ✅ | Proyectos, skills y logros propuestos desde GitHub, portfolio o Scholar, con su fuente y solo con tu OK |
| 25.3 | ↳ Ofertas dudosas y banderas rojas | ✅ | Señales (rango salarial ancho, empresa oculta, temporal, republicada, cribado con IA) y `red_flags` con fuentes en el dosier |
| 25.4 | ↳ Coste y lote en paralelo | ✅ | Coste por oferta, skill y agente; umbral de score antes de `assess-fit`; hasta N ejecuciones a la vez |
| 25.5 | ↳ Maquetación del PDF | ✅ | Avisos de títulos huérfanos, huecos, pie y última página casi vacía en CV y carta |
| 25.6 | ↳ CHANGELOG y la historia con números | ✅ | `CHANGELOG.md`, notas de release desde él y `cai stats story` para el README |
| 25.7 | ↳ Tu perfil, editable desde la UI | ✅ | Experiencia y logros, historias STAR, preferencias de búsqueda, CV y carta, contexto y muestras de estilo desde «Mi perfil», con validación, diff y «Deshacer»; «Mejorar con mi agente» opcional |
| 25.7a | ↳↳ Escritura del perfil, contexto y muestras (backend) | ✅ | `profile_editor` por secciones (conserva comentarios, `conflict`, validación, copia y «Deshacer»), contexto y muestras de estilo por la API solo para la UI, `style_samples` en `get_context`, ADR-039 |
| 25.7b | ↳↳ La página «Mi perfil» editable (UI) | ✅ | Formularios por bloque en es y en, diff antes de guardar, «Mejorar con mi agente» y «Proponer historias», guía, README y prueba manual |
| 26 | macOS, Linux y Docker | ✅ | Instalar y usar la app en los tres sistemas, botones «en tu agente» incluidos, y Docker opcional |
| 26.1 | ↳ Núcleo multiplataforma | ✅ | Rutas, procesos, LibreOffice y terminales en macOS y Linux (`CAI_TERMINAL`) |
| 26.2 | ↳ Instalador para macOS y Linux | ✅ | `install.sh` con acceso directo, datos en la carpeta de cada sistema y desinstalación |
| 26.3 | ↳ Docker opcional | ✅ | `docker compose up` con los datos en un volumen; el agente desde fuera por MCP; límites documentados |
| 26.4 | ↳ CI en tres sistemas y docs | ✅ | Backend probado en Windows, Linux y macOS, humo del instalador y de Docker, guía y README al día |
| 26.5 | ↳ Demo completa | ✅ | La demo trae hecho lo de cada pantalla (cartas, dosieres, correos, entrevistas, oferta recibida, contexto…) y los botones abren el agente sobre la demo |
| 27 | Ayudas, prioridades, varios buzones, experiencia plegable y preferencias | ✅ | Globos que explican cada botón de skill, prioridades de plataforma sin empates, Alertas con varios buzones, «Experiencia» que se recorre de un vistazo y «Búsqueda» con los filtros que faltan |
| 27.1 | ↳ Ayudas en los botones de los skills | ✅ | Globo al pasar el ratón o enfocar, con qué hace, qué toca y qué necesita, en español e inglés |
| 27.2 | ↳ «Experiencia» plegable | ✅ | Empresas plegadas por defecto, bordes rectos y logros con fondo alterno |
| 27.3 | ↳ Prioridades únicas | ✅ | Orden de plataformas sin empates; elegir un puesto ocupado intercambia |
| 27.4 | ↳ Alertas con varios buzones | ✅ | «Añadir buzón» con guía para Gmail, Outlook, Yahoo, iCloud y carpeta de `.eml` |
| 27.5 | ↳ Preferencias de búsqueda | ✅ | «Mi perfil → Búsqueda» en bloques y alineada, con años mínimos, sueldo mínimo privado, palabras que descartan, contrato y tipo de empresa |
| 27.6 | ↳ Descartar desde la Bandeja | ✅ | Botón «Descartar» con «Deshacer» en «Por completar» y «Por extraer», y «Cerrada» con su fecha de cierre, ordenable |
| 28 | Repo público: raíz limpia, release, medios nuevos y lanzamiento | ⏳ | Primera release que instala de verdad, lo interno en `dev/`, medios y README al día con todas las funcionalidades, portada y ajustes de GitHub, y borradores de difusión |
| 28.1 | ↳ Auditoría y primera release | ⏳ (`v0.1.0` publicada el 2026-10-24 y probada en un Windows 11 limpio; faltan Linux/WSL, Docker y actualizar sin perder datos) | Historial auditado, `v0.1.0` publicada con suma de verificación y los instaladores probados contra ella |
| 28.2 | ↳ Raíz limpia | ✅ (falta comprobar en GitHub la barra de lenguajes tras el push) | Encargos, pruebas, ROADMAP y ADR a `dev/`, enlaces comprobados y la barra de lenguajes de GitHub bien |
| 28.3 | ↳ Medios y funcionalidades | ✅ | Capturas y animaciones nuevas (en/es, sin vídeos), `FEATURES.md` y un script que impide funciones sin contar |
| 28.4 | ↳ Portada y GitHub | ⏳ (hechos README, guía «Empieza aquí», CONTRIBUTING y plantillas; faltan los ajustes en la web de GitHub y la prueba con un lector, `dev/pruebas/fase-28.4-github.md`) | Portada con gancho, «Por qué CandidatAI», guía para quien no es técnico, temas, imagen social y plantillas |
| 28.5 | ↳ Lanzamiento | ⏳ | Borradores por canal, listas «awesome», preguntas esperables y plan de dos semanas |

**MVP usable:** al terminar la 08 ya puedes pegar ofertas, triarlas y sacar CVs a medida; con la
08c, también cartas de presentación. La 08c va antes que la 08b, aunque el orden entre ambas da
igual (la que llegue después añade la carta a las plantillas html).

**Plan 13-22 (2026-10-11):** funciones de [AI Job Search](https://github.com/MadsLorentzen/ai-job-search)
y [career-ops](https://github.com/santifer/career-ops) que encajan con lo que ya hay y con las
reglas duras. Orden recomendado: 13 (base de las demás) → 14 → 15 → 16 → 17 → 18 → 19; la 20
cuando haya unas 20-30 candidaturas enviadas; la 21 cuando llegue la primera oferta; la 22 solo si
la quieres. Descartado: candidaturas automáticas (reglas 5 y 6), sincronización con Notion,
plantillas LaTeX (ya hay docx y html), portales daneses, descubrimiento de empresas financiadas
desde feeds externos y modelos llamados desde la app (ADR-001).

**Plan 24 (2026-10-16):** tras revisar `docs/COMPARATIVA.md`, imitar a career-ops en lo que más
nos saca: varios agentes (algunos open-source y con modelos gratuitos o locales) y cambiar entre
ellos desde la UI. Se mantiene el ADR-001: los modelos gratuitos se usan a través de agentes
open-source, no desde la app. Orden: 24.1 → 24.2 → 24.3 → 24.4 → 24.5 → 24.6, una subfase por
sesión.

**Fases 25 y 26 (2026-10-16):** el resto de «Lo que nos falta» de `docs/COMPARATIVA.md`. La 25
(fuentes, `expand`, ofertas dudosas, coste y lote, maquetación del PDF, `CHANGELOG` y, desde el
2026-10-17, el perfil editable desde la UI en la 25.7) va después de
la 24, porque la 25.4 usa el agente y el modelo que guarda la 24.4. La 26 (macOS, Linux y Docker)
va aparte porque toca el instalador, los botones de terminal y la CI, y gana sentido cuando ya hay
agentes open-source que funcionan en los tres sistemas. Descartado por ahora: autorización de
trabajo y visado (solo importa fuera de la UE).

**Skills que se desbloquean por fase:** `actualizar-perfil` tras la 05; `procesar-ofertas` tras la
04 (y con perfil, tras la 05); `evaluar-encaje` tras la 07; `generar-cv` tras la 08; `importar-plantilla-cv` tras la 08 para
Word y tras la 08b para PDF, imagen o HTML; `generar-carta` tras la 08c;
`revisar-linkedin` funciona tras la 05, pero rinde mucho más desde la 07, cuando ya hay ofertas
aprobadas de las que sacar las keywords; `buscar-ofertas` tras la 09b; `preparar-candidatura`,
`preparar-entrevista` y `resumen-diario` tras la 10; la candidatura asistida (sin skill: se
usa desde la ficha) tras la 11; `plan-formacion` tras la 14; `ampliar-busqueda` tras la 16;
`simular-entrevista` y `repasar-entrevista` tras la 17; `redactar-mensaje` e `investigar-empresa`
tras la 18; `atender-encargos` tras la 19; `revisar-busqueda` tras la 20;
`preparar-negociacion` tras la 21.

## Registro de fases

> **Nombre (fase 23, ADR-034):** hasta la fase 22 la herramienta se llamaba «Job Hunter», la CLI
> `jh`, el servidor MCP `jobhunter` y las variables `JH_*`. Desde la 23 es **CandidatAI**: `cai`,
> `candidatai` y `CAI_*`. El registro de abajo conserva los nombres de cada momento.

<!-- El agente añade aquí, al cerrar cada fase: fecha, agente usado, resumen de 2-3 líneas,
decisiones tomadas y deuda técnica pendiente. -->

### 01 · Arranque del repo — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** backend `uv` (Python 3.12) con `Settings`, `jh doctor` (texto y `--json`) y stub
  `jh-mcp`; frontend Vite + React + TS con Vitest; CI (backend en Windows, frontend, sync de
  agentes); sección «Desarrollo» en el README. 17 tests de backend y 1 de frontend.
- **Decisiones:** las comprobaciones de `doctor` viven en `app/services/doctor.py`; `JH_DATA_DIR`
  relativo se resuelve desde la raíz del repo, no desde el cwd; la CLI fuerza UTF-8 en
  stdout/stderr (en Windows, con salida por tubería, Python usa cp1252 y rompía tildes en
  `--json`); pnpm fijado con `packageManager` (Node 25 ya no trae corepack).
- **Deuda:** `.env.example` pendiente de crear a mano (la regla `Read(./.env.*)` de
  `.claude/settings.json` también lo bloquea para el agente); LibreOffice sin instalar en la
  máquina de desarrollo (necesario en la fase 08); cobertura sin umbral mínimo.

### 02 · Núcleo de datos — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** las 11 tablas de `DATA_MODEL.md` en `app/models/`, migración inicial `0001`,
  engine SQLite con WAL y claves foráneas, `services/events.record()`, `services/pipeline.py`
  (etapas, tabla de transiciones, proyección y recálculo), `services/normalize.py` (empresa,
  título, ubicación, huella) y CLI `jh db upgrade`, `jh status` y `jh events list` con `--json`.
  291 tests; cobertura de `services/` del 99 %, con un umbral del 85 % en CI.
- **Decisiones:**
  - `found` es el evento inicial, no una etapa.
  - Las etapas de origen válidas de cada evento están en `pipeline.TRANSITIONS` y se prueban
    las 210 combinaciones de evento y etapa. `applied` exige `cv_ready`; `applied_manually`
    es la vía alternativa.
  - `reopened` vuelve a la etapa previa al último cierre. `cv_verified` solo lleva a
    `cv_ready` con `payload.passed = true`.
  - `record()` reproduce todos los eventos de la oferta (por `occurred_at` y luego por `id`)
    antes de escribir. Así admite eventos con fecha pasada y un error no deja nada a medias.
  - Las fechas son `UTCDateTime`: se guardan en UTC y se rechazan las fechas sin zona.
  - Título normalizado: se quitan las etiquetas entre paréntesis de género, seniority y
    modalidad, y los sufijos de modalidad («– Remote»). Sr./Jr. se expanden y se conservan.
  - Los comandos que leen la BD fallan con «ejecuta `jh db upgrade`» si no está al día.
- **Deuda:**
  - `jh --help` muestra mal las tildes en consolas Windows con cp1252: Typer pinta la ayuda
    antes del callback que fuerza UTF-8. Ya pasaba en la fase 01.
  - El JSON de error de la CLI (`{ok: false, error}`) es provisional hasta fijar el formato de
    errores común con la MCP en la fase 04.

### 03 · Alta de ofertas — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** `services/ingest.py` (`add_from_url` con httpx + trafilatura + JSON-LD/`og:`,
  `add_from_text`, duplicados exactos por huella y difusos con rapidfuzz), `services/untrusted.py`
  (texto oculto en el HTML original y frases de `injection_patterns.yaml`), `services/jobs.py`
  (`list_jobs`), `core/policies.py` (carga de `config/`) y CLI `jh jobs add-url | add-text | list`
  con `--json`. Cinco fixtures inventados; 398 tests, `services/` al 98 %.
- **Decisiones:**
  - Duplicado difuso: `duplicate_of` + evento `duplicate_detected` (cierra la oferta, reabrible),
    en el orden `found` → `injection_suspected` → `duplicate_detected`. Siempre apunta a la
    original, no a otro duplicado.
  - Duplicado exacto (misma huella, o misma URL en `add-url`, sin descargar): devuelve la oferta
    existente con `created: false` y no registra eventos.
  - Salida de alta `{job_id, created, duplicate_of, risk_flags}`; `add-text` admite `--location`
    (entra en la huella) y guarda `url = ""` si no hay. `AGENT_INTERFACE.md` actualizado.
  - Texto oculto en zonas benignas (nav, header, footer, diálogos, listas de enlaces) no activa
    `hidden_text`, pero sí se busca en él una frase de inyección. Documentado en `POLICIES.md` §6.
  - trafilatura descarta el texto con `display:none`: la detección se hace sobre el HTML original.
    Si la página se pinta con JavaScript pero trae la oferta en el JSON-LD, se usa su
    `description`.
  - La descarga comprueba cada salto (hook de httpx): no sigue a LinkedIn ni a IPs locales o
    privadas tras una redirección. Máximo 5 MB, sin cookies previas.
- **Deuda:**
  - La protección SSRF solo mira IPs literales y `localhost`; un dominio que resuelva a una IP
    privada pasaría (resolver DNS en el código rompería los tests sin red).
  - Si una oferta se dio de alta por texto (sin URL) y luego llega por URL con la misma huella, no
    se completa su `url`.
  - El patrón `system prompt` puede dar falsos positivos en ofertas reales de ingeniería de LLM.
  - `jh jobs list` ordena por `first_seen_at`; el orden `score_desc` de la interfaz llega con la
    fase 07. Las llamadas aún no se registran en `mcp_calls` (fase 04).

### 04 · Interfaz para agentes — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** registro único de herramientas en `app/agent_interface/` (`ToolSpec` → herramienta
  MCP y comando `jh`), servidor `jh-mcp` por stdio con el SDK `mcp` 2.2, las 9 herramientas de la
  fase, `JobExtraction` (schema_version 1), `get_job` con envoltorio blindado, `save_extraction`
  con `injection_suspected` del agente, auditoría en `mcp_calls`, formato de error común y
  `jh agents sync | check`. Dos ofertas ficticias en `demo/jobs/`. 492 tests. Probado a mano con
  Claude Code (`/mcp` + `/procesar-ofertas` → `pending_triage`); guía en
  `dev/pruebas/fase-04-prueba-manual.txt`.
- **Decisiones:**
  - `Server` de bajo nivel en vez de FastMCP para que MCP y CLI validen con el mismo modelo y den
    errores idénticos (ADR-013). Por CLI todo llega como texto; `received` va siempre como texto.
  - Error común `{ok: false, error: {type, message, details: [{field, received, reason}]}}`,
    mensajes en español. Sustituye al provisional de la fase 02.
  - `jh jobs show` sin `--raw`; `list_jobs order=score_desc` igual que `recent` hasta la fase 07.
  - `add_event`: actor `agent`, `note` en el payload; rechaza los eventos con herramienta propia o
    del sistema (`extracted`, `cv_verified`…).
  - Auditoría: MCP siempre, CLI solo con `--json`; cliente por `clientInfo.name` o
    `JH_CLIENT_NAME`. `args_summary` guarda ids/URLs/etapas y, del resto, solo longitudes.
  - `--file` solo dentro de `data/tmp/` (también `add-text`, que antes aceptaba cualquier ruta);
    se borra tras el éxito. Una ruta relativa vale desde el directorio actual o desde la raíz
    (con `uv run --directory backend` el proceso corre en `backend/`).
  - `get_job` y `save_extraction` permitidas en `.claude/settings.json` (el extractor no pide
    permiso por oferta); las herramientas `add_*` siguen pidiéndolo.
  - Envoltorio: se neutraliza cualquier variante de la etiqueta (mayúsculas, espacios, guiones,
    `<` Unicode parecidos, caracteres invisibles) escapando su `<`.
- **Deuda:**
  - Extractor: `responsibilities` salió en inglés con una oferta en español y `domain` como
    "data" en vez del sector. Precisar el rol al evaluar el matching (fase 07).
  - **Prueba con Codex pendiente:** el usuario aún no tiene Codex instalado. Cuando lo tenga,
    seguir la parte 3 de la guía y actualizar `docs/AGENTS_COMPAT.md`.
  - El test de paridad tarda ~0,5 s por caso (migra dos BD por caso).

### 05 · Perfil del candidato — 2026-09-24 · Claude Code (Opus 5.5)
- **Resumen:** `CandidateProfile` (`app/schemas/profile.py`) valida la estructura de
  `demo/profile.example.yaml`; `services/profile.py` con `load_from_yaml` (errores con la ruta del
  campo, p. ej. `experience[1].achievements[0].id`), `import_profile`, `current`, `public_view`,
  `diff_last_two`, `init_profile` y `resolve_evidence`; herramienta `get_profile(sections?)`; CLI
  `jh profile validate | import | diff | init | show`. Migración `0002`. 574 tests;
  `services/profile.py` al 100 %.
- **Decisiones:**
  - Ids de primer nivel (experiencias, proyectos, formación, certificaciones, historias) únicos en
    todo el perfil; los de logro, dentro de su experiencia. Las evidencias son `exp-x/a1` o el id
    de una experiencia, un proyecto, una formación o una certificación.
  - Es un error que un logro o un proyecto cite una skill que no esté en `skills` ni en
    `basic_skills`. Una skill solo puede estar en una de las dos listas.
  - Las comprobaciones entre secciones se lanzan juntas (`ProfileConsistencyError`), pero solo
    cuando los campos ya validan: un perfil muy roto se corrige en dos pasadas.
  - Hash = sha256 del JSON canónico: los comentarios y el formato del YAML no crean versión.
    Migración `0002`: `content_hash` pasa de único a índice. Importar lo mismo que la versión
    vigente no crea versión; volver a un contenido anterior sí.
  - `get_profile` sale de una lista blanca de secciones y de campos de `personal`: nunca email,
    teléfono ni `private`. Sí devuelve los niveles F/C+/C/B y las marcas `nda`. La CLI es
    `jh profile show [--sections a,b]`, siempre con la vista pública (se quita `--public`).
  - `jh profile diff` muestra `private` como `<oculto>`.
  - `resolve_evidence(profile, ref)` es una función pura sobre una versión concreta: los CVs se
    verifican contra la versión con la que se redactaron.
  - Traducción de errores de Pydantic movida a `app/core/validation.py`, compartida por la
    interfaz para agentes y el perfil.
  - La auditoría guarda tal cual las listas de texto de los campos seguros (las `sections`).
- **Deuda:**
  - `preferences.locations.allowed` («solo si es híbrido o remoto») no se valida en el esquema:
    lo aplicarán los filtros duros de la fase 07.
  - Importar un perfil nuevo aún no recalcula los scores; llega con la fase 07.
  - Una clave YAML `NO` (Noruega) en `photo_policy.by_country` se lee como booleano: hay que
    escribirla entre comillas.

### 05b · Preferencias de CV en el perfil — 2026-09-28 · Claude Code (Opus 5.5)
- **Resumen:** `CvPreferences` admite `default_template`, `photo_file` y `template_rules`
  (`TemplateRule` con `when: TemplateRuleWhen` y `use`); `max_pages` y `photo_policy` no cambian.
  `demo/profile.example.yaml` vuelve a validar y un bloque `cv` antiguo sigue siendo válido.
  `public_view` ya incluía `preferences` entero; ahora un test cubre `preferences.cv`. 592 tests.
- **Decisiones:**
  - `default_template` y `use` se validan con el formato de id (minúsculas, dígitos, `-`, `_`);
    si la plantilla existe se comprueba en la fase 08.
  - Una regla necesita al menos una lista no vacía en `when` (`ats`, `country`, `domain`,
    `language`); `country` en ISO 3166-1 alfa-2 mayúsculas, `language` en minúsculas.
  - `photo_file` se valida con `PureWindowsPath`: se rechaza cualquier ancla (`/x`, `\x`, `C:x`,
    `C:\x`, UNC) y cualquier `..`. `\x` sin unidad es relativa para `is_absolute()`, pero en
    Windows `data / "\x"` acaba en la raíz de la unidad (lo detectó la revisión).
  - Los errores de código de idioma y país explican el formato esperado, no solo «formato no
    válido».
- **Deuda:**
  - No había `data/profile.yaml` para probar el criterio «sin tocarlo»; se probó con una copia del
    demo con el bloque `cv` antiguo, por test y con `jh profile validate`.
  - `docs/CV_TEMPLATES.md` habla de `data/photo.*`, pero el perfil ya dice qué fichero usar
    (`photo_file`): alinearlo en la fase 08.
  - `country: [NO]` (Noruega) en `template_rules` se lee como booleano, igual que en
    `photo_policy.by_country`: hay que escribirlo entre comillas.

### 06 · Frontend base — 2026-09-28 · Claude Code (Opus 5.5)
- **Resumen:** API REST en `app/api/` (`GET /status`, `GET /jobs`, `GET /jobs/{id}`, `POST
  /jobs/url|text`, `POST /jobs/{id}/events`), `jh serve` (solo 127.0.0.1) y `jh openapi`; servicios
  `search_jobs`, `get_job_view` y `add_user_event`. UI con Tailwind v4, shadcn/ui, React Router,
  TanStack Query y cliente `openapi-fetch` generado (`pnpm gen:api`): bandeja, ficha, alta y
  cabecera con recuentos y recordatorio de `procesar-ofertas`; tema claro/oscuro/sistema; móvil.
  Backend 624 tests (`services/` al 98 %), frontend 17 tests. Probado a mano por el usuario con
  Claude Code (`dev/pruebas/fase-06-prueba-manual.txt`): alta en la UI → `procesar-ofertas` →
  extracción visible en la ficha.
- **Decisiones:**
  - La ficha devuelve el texto original sin el envoltorio `<untrusted_job_posting>`: lo lee una
    persona y React lo pinta como texto (nunca `dangerouslySetInnerHTML`).
  - Errores de la API con el formato común de la interfaz para agentes; 404/409/422/503/500.
  - `POST /jobs/{id}/events` acepta solo `USER_EVENTS` (actor `user` del catálogo, sin
    `cv_rendered`, que llega en la 08). La UI solo usa la nota; aprobar/descartar, en la 07.
  - La bandeja usa su propio servicio (con `remote_mode`, `q`, `offset` y `total`); `list_jobs`
    de los agentes no cambia, así que la paridad MCP ↔ CLI sigue igual.
  - Las llamadas de la UI no se auditan en `mcp_calls`.
  - `frontend/src/api/openapi.json` y `schema.d.ts` se versionan; un test del backend falla si
    se desfasan.
  - Diseño: neutros zinc, un único acento verde azulado, ámbar solo para el aviso de inyección,
    Geist, iconos Phosphor. Las etapas se distinguen por intensidad del acento.
  - `strictPort` en Vite: CORS solo admite `http://127.0.0.1:5173` exacto.
- **Deuda:**
  - El CLI de shadcn resolvió mal el alias `@/lib/utils` (instaló un paquete `cn` ajeno y usó
    lucide): se corrigió a mano. Al añadir componentes, revisar sus imports.
  - Bundle de 540 kB (164 kB gzip): partir por rutas si crece.
  - `openapi-typescript` 7 declara TypeScript 5 como peer; funciona con el 6.
  - Al parar `pnpm dev` desde un agente en Windows puede quedar Vite huérfano ocupando el 5173;
    la guía explica cómo cerrarlo.

### 07 · Matching y triaje — 2026-09-28 · Claude Code (Opus 5.5)
- **Resumen:** `services/matching/` con filtros duros (seniority, años, modalidad, ubicaciones,
  idiomas MCER y palabras de descarte), cobertura de skills ponderada por nivel con
  `config/skill_aliases.yaml`, similitud semántica con sentence-transformers (extra opcional
  `matching`), score 0-100 con desglose y evaluación (`jh eval matching`, 20 casos semilla en
  `evals/matching/`). Cola de tareas y `jh worker`; migraciones `0003` (`matches.extraction_id`)
  y `0004` (`matches.scoring_key`); `jh match rescore`.
  Herramientas `get_match` y `save_fit_assessment` con paridad; `list_jobs` ordena por score. API
  `GET /triage` y `GET /jobs/{id}/match`; UI de triaje con atajos (J/K, A, D + 1-6, O), descarte
  con motivo obligatorio, deshacer, panel de encaje y «Reabrir» en la ficha, score en la bandeja.
  Backend 827 tests (`services/` al 98 %), frontend 35. Guía de prueba manual en
  `dev/pruebas/fase-07-prueba-manual.txt` y ofertas de prueba con `scripts/seed_triage_demo.py`.
- **Decisiones** (ADR-015):
  - sentence-transformers es un extra opcional: sin él (o con `JH_EMBEDDINGS=off`) la similitud
    no cuenta y su peso se reparte; `jh doctor` avisa. Los tests usan un embedder falso.
  - Los filtros duros se aplican al guardar la extracción (`save_extraction` devuelve
    `hard_filters`); el score se encola. Un match guarda `extraction_id` y `profile_version_id`, y
    `get_match` y el triaje lo recalculan si está desfasado: el triaje funciona sin worker.
  - El match también guarda `scoring_key` (versión del scorer, políticas, alias y modelo de
    embeddings): instalar el extra `matching` o editar `policies.yaml` lo deja desfasado.
    `jh match rescore` recalcula las ofertas abiertas sin esperar a que se consulten.
  - Importar un perfil nuevo encola `rescore_all`, que puede cerrar ofertas en triaje que ya no
    pasan; nunca las que el usuario reabrió tras un `hard_filter_failed`.
  - Descartar desde la UI exige `reason` (`skills`, `seniority`, `location`, `salary`, `company`,
    `other`; `other` con nota) para la analítica de la fase 10. El agente sigue con `note`.
  - Preferencias del score: puesto según el orden de `roles`, comparando por partes del título
    (fuera y dentro de paréntesis, separadas por « - », « | » o « / »), sin «(m/f/d)» ni
    seniority; todas las palabras del rol deben aparecer y el parecido es `token_sort_ratio`;
    modalidad según el orden de `remote_modes`; zona preferida 1, permitida 0,6, desconocida 0,5.
  - Seniority: pasan solo los niveles de `seniority_target`, que es la lista de todos los que
    acepta el candidato, por arriba y por abajo (quien busca mid puede no querer junior; quien
    empieza, no querer senior). Sin tolerancia global en `policies.yaml`: lo decide cada perfil,
    y `actualizar-perfil` lo pregunta. «Nativo» cuenta como C2; un nivel de idioma que no se
    entiende no descarta.
  - Rol `extractor`: `responsibilities` en el idioma de la oferta y `domain` como sector (deuda
    de la fase 04).
  - `jh doctor`: el aviso de `data/cv_template.docx` (diseño de la fase 01, anterior al ADR-014) se
    sustituye por «Plantillas de CV», que lista las de `templates/` y `data/templates/` con
    `template.yaml`. `Settings.cv_template_path` pasa a `user_templates_dir`.
- **Deuda:**
  - «Sales Engineer (Data Platform)» ya no cuenta como «Data Engineer», pero el puesto solo pesa
    un tercio del 15 % de preferencias: con todas las skills cubiertas sigue por encima del umbral
    (caso trampa del set de evaluación). Para descartarlo, `discard_title_keywords`.
  - El modelo de embeddings no se ha elegido aún con el set de evaluación (ADR-006): hay que
    instalar el extra y comparar informes. Los umbrales `similarity_floor/ceiling` son iniciales.
  - `GET /triage` y `get_match` pueden escribir (match y `scored`) al consultar; con embeddings, la
    primera consulta carga el modelo y tarda.
  - `save_fit_assessment` sigue pidiendo permiso en Claude Code (no está en
    `.claude/settings.json`): en `evaluar-encaje` con muchas ofertas, un permiso por oferta.
  - La BD real del usuario necesita `jh db upgrade` (hasta 0004).

### 08.1 · CV: contenido, verificación y motor docx — 2026-09-28 · Claude Code (Opus 5.5)
- **Resumen:** migración `0005` (`document_renders`; `documents` sin rutas; `applications.render_id`),
  evento `cv_rendered`, esquemas `CvContent`, `CvRenderOptions`, `CvVerification` y `TemplateMeta`
  (`app/schemas/cv.py`) y `services/documents/`: registro de plantillas, resolución de opciones
  (ATS por URL, país con `config/countries.yaml`, sector, idioma), contexto del contrato (fechas y
  `labels` es/en, contacto desde el perfil), motor docx, PDF con LibreOffice o Word, comprobaciones
  (contenido, páginas, cobertura, avisos), previews y servicio. Plantilla `ats-simple` generada por
  `scripts/build_builtin_templates.py` (reproducible, con test que compara con la versionada). Cinco
  herramientas MCP/CLI con paridad y `jh doctor` con una conversión real. 966 tests de backend.
  Flujo probado por CLI con LibreOffice: rechazo con detalle → PDF de 1 página → `cv_ready`.
- **Decisiones** (ADR-017; se numeró 016 y se renumeró al coincidir con la 016 de la 09b):
  - `cv_ready` cuando un mismo documento está verificado con `passed` y tiene un render sin
    `too_long`, en cualquier orden; `cv_rendered` es reservado (solo el servicio de render).
  - País por `countries.yaml` (sin nombres ambiguos); varios países: la regla encaja con alguno y la
    foto `auto` exige que todos la permitan. Si la regla o `default_template` piden una plantilla
    que no existe, aviso `template_not_found` y se sigue (el perfil demo pide `clasica-foto`, que
    llega en la 08.2).
  - Contacto e idioma regional los decide el código; «conocimientos de X» cuenta como X; las skills
    de nivel B cuentan como básicas.
  - `jh cv save --file F` recibe `{content, render_options}` (`CliSpec.file_keys`).
  - Primer render sin `too_long` seleccionado; un render fallido borra sus ficheros.
  - `alembic/env.py` desactiva las claves foráneas durante las migraciones en SQLite y comprueba
    al final que no queda ninguna rota (la recreación de `documents` en modo batch lo necesitaba).
  - Los grupos de skills del contexto son objetos: en Jinja, `s.items` de un dict es el método.
  - `find_soffice` pasa de `doctor.py` a `documents/pdf.py`; errores nuevos `pdf_unavailable` y
    `pdf_failed`.
- **Deuda:**
  - Cada conversión arranca LibreOffice: unos 15 s por render en Windows. Un LibreOffice en
    segundo plano lo bajaría a 1-2 s si la UI de la 08.2 lo necesita.
  - `preferences.cv.max_pages` del perfil no se usa: manda `max_pages` de la opción o de la
    plantilla (como dicen `CV_TEMPLATES.md` y `POLICIES.md` §3). Decidir en la 08.2.
  - Mientras el servidor MCP de Claude Code está abierto, `uv run`/`uv sync` fallan al reinstalar
    `jh-mcp.exe` (fichero en uso): usar `uv run --no-sync` o cerrar la sesión. Afecta también a
    `pnpm gen:api`.
  - `validate` de plantillas solo comprueba variables de primer nivel (`labels.foo` inexistente no
    se detecta hasta renderizar).
  - La BD real necesita `jh db upgrade` (hasta 0005).

### 08.2 · CV: foto, renders múltiples y UI — 2026-10-01 · Claude Code (Opus 5.5)
- **Resumen:** `documents/photo.py` (búsqueda, recorte centrado por forma con EXIF y caché en
  `data/cache/photo/`), foto real en el render (`auto`/`include`), plantilla integrada
  `clasica-foto` (cabecera con foto circular en tabla sin bordes, 4 colores de acento) y foto
  ficticia `demo/photo.png` generadas por `scripts/build_builtin_templates.py`, previews
  `preview.png` con `pypdfium2`, `select_render` y `template_changed`, rutas de API
  (`/templates`, `/jobs/{id}/cv`, `/documents/{id}/renders`, `/renders/{id}/select|pdf|docx`) que
  solo sirven ficheros desde `data/` y las carpetas de plantillas, sección «CV» en la ficha
  (selector con miniaturas, foto, color, secciones ocultas, renders con avisos, comparación lado
  a lado y «Usar este para enviar»), página **Plantillas** y aviso de foto en `jh doctor`.
  1000 tests de backend y 46 de frontend.
  Prueba manual con datos demo aislados y LibreOffice: oferta en `cv_ready` con `clasica-foto` →
  render por la API de la UI con `clasica-foto` sin foto, en verde y sin proyectos → PDF correcto
  en ~12 s → seleccionado para enviar. La UI no se probó en navegador (extensión de Chrome sin
  conectar): solo con sus tests.
- **Decisiones:**
  - Foto: `preferences.cv.photo_file` y, si no existe, el primer `data/photo.*` (jpg, jpeg, png,
    webp; heic solo si Pillow lo abre). Las que no se pueden abrir se ignoran.
  - `preferences.cv.max_pages` pasa a opcional (`null` por defecto) y cuenta: opción > perfil >
    plantilla. Los perfiles guardados con `max_pages: 1` siguen igual.
  - `select_render` admite también un render `too_long` (decides tú); no registra evento.
  - `GET /jobs/{id}/cv` devuelve `cv: null` (no 404) si aún no hay CV, con `can_render`.
  - La API sirve renders solo desde `data/cvs/` (no todo `data/`, donde la 09b guardará
    `data/capture_token`); ruta fuera o fichero inexistente: 404 `not_found` (sin decir por qué).
  - La sección «CV» de la ficha sale en una lista explícita de etapas (de `approved` en adelante;
    en `closed`, solo si hubo CV), para que la etapa `pending_detail` de la 09b no la muestre.
  - Compatibilidad con la 09b (ya en `main`): la ADR de la 08.1 pasa a ser la ADR-017. Al
    implementar la 09b: `cv_rendered` entra en los tests evento × etapa con `pending_detail`, el
    check de IMAP de `jh doctor` se añade a la lista de `test_cli_doctor_json` junto a «Foto del
    CV», y su migración va después de la `0005`.
  - `TemplateInfo.has_preview` y `sections` tipado; `pdf_unavailable` → 503 y `pdf_failed` → 500.
  - El conversor falso de los tests declara Cambria para que las integradas no den
    `font_substituted`.
- **Deuda:**
  - Cada render desde la UI tarda ~10-15 s (LibreOffice arranca en cada conversión). La UI lo
    indica; un LibreOffice en segundo plano lo bajaría.
  - La comparación lado a lado usa el visor de PDF del navegador en un `iframe`.
  - `template_changed` recalcula el hash de cada plantilla en cada consulta del CV.
  - La BD real sigue necesitando `jh db upgrade` (hasta 0005); la 08.2 no añade migraciones.

### 08.3 · CV: importar plantillas desde Word y «Mi CV» — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** `services/documents/importer/` (`docx_xml`: párrafos numerados con fragmentos
  fusionados; `inspect`: página, fuentes que se ven, colores, tablas, cuadros de texto, imágenes,
  cabecera y pie, secciones en su orden, `capacity` medida y estimación de ATS; `mapping`: esquema
  y comprobación previa; `build`: aplica el mapeo y escribe `data/templates/<id>/`; `paths`: solo
  `data/`), `authoring.py`, CLI `jh templates inspect | build-docx | validate | preview`.
  `extra_sections` en perfil, `CvContent`, contrato, `ats-simple` y `clasica-foto`. «Mi CV» en la
  página Plantillas: subidas (`uploads.py`), original y preview con tu perfil lado a lado, «Usar
  por defecto» (`default_template.py`, ruamel.yaml) y etiqueta «Tu CV». 1046 tests de backend y 51
  de frontend. Prueba de humo con LibreOffice: Word ficticio → plantilla con el mismo diseño,
  orden de secciones y extensión. Prueba manual completa del usuario
  (`dev/pruebas/fase-08.3-prueba-manual.txt`, también la parte 4 con su CV de Word): todo bien.
  Cierra la fase 08.
- **Decisiones:**
  - Mapeo por párrafo: `static` (por defecto), `delete`, `variable` (`text` o `runs` con el
    formato del fragmento `like`, para «**Rol** | Empresa») y `photo`; bloques con `start`/`end`
    y `scope: row` para filas de tabla; `header` → `layout.header_paragraphs` (carta de la 08c).
  - Antes de tocar el Word, el mapeo se monta como plantilla Jinja de borrador y se renderiza con
    todo el perfil demo: bloques sin cerrar, variables fuera del contrato y atributos inexistentes
    salen con el índice del párrafo. Si la plantilla final no renderiza, no queda nada (staging en
    `data/tmp/`).
  - Secciones de `template.yaml` en el orden en que las usa el mapeo; `capacity` y páginas
    medidas en el original; fuentes efectivas por caracteres (fragmento → estilo y `basedOn` →
    por defecto → tema), no las de estilos sin usar.
  - Secciones extra con un único bucle genérico `extra_sections` (título + items); sus ids
    cuentan como de primer nivel, así `<sección>/<item>` no choca con `exp-x/a1`.
  - Render con `SandboxedEnvironment` (docxtpl y comprobación del mapeo) y mapeos sin `__` ni
    `{#`: una plantilla importada de un CV ajeno no puede llegar a atributos internos de Python
    (lo detectó la revisión).
  - Una subida está «importada» si una plantilla tuya tiene un `source.*` con el mismo sha256: no
    se apunta el origen en ningún sitio. Subidas: 10 MB, nombre saneado (también nombres
    reservados de Windows), firma del contenido y nunca se sobrescribe.
  - «Usar por defecto» es la única escritura de `profile.yaml` desde la app: solo esa clave, con
    ruamel.yaml (`null` explícito, LF conservado), validando antes de sustituir; sin copia, la
    versión anterior queda en `profile_versions`.
  - Errores nuevos: `exists` (409), `too_large` (413), `invalid_file` también en la API (422).
  - Dependencias: `python-multipart` y `ruamel.yaml`.
- **Deuda:**
  - Una foto flotante pasa a ir en línea; el color de acento no se parametriza en las importadas.
  - `GET /uploads` calcula el sha256 de subidas y originales en cada consulta (la UI sondea cada
    15 s); cachear por ruta, fecha y tamaño si hay muchos ficheros.
  - Un `--id` igual al de una integrada la sustituye en la galería (solo se avisa).
  - Con el servidor MCP de Claude Code abierto, `uv add`/`uv sync` y `pnpm gen:api` siguen
    fallando por `jh-mcp.exe` en uso: se instaló con `uv pip install` y se regeneró el cliente con
    `uv run --no-sync`. Ejecuta `uv sync --directory backend` con Claude Code cerrado.


### 08b · Motor html e importación de CVs en cualquier formato — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** motor html (`engines/html.py`: Jinja2 en sandbox → HTML saneado → PDF con
  Chromium de Playwright sin JavaScript ni red; solo sirve la carpeta de la plantilla, `fonts/` o
  `data/fonts/` y la foto), saneado en dos capas (`sanitize.py`: `validate` falla con fichero y
  línea; al renderizar se limpia el HTML y los CSS servidos), aviso `pdf_only` y renders sin DOCX.
  Plantilla integrada `moderna-2col` (barra lateral a sangre, foto circular, 4 colores, secciones
  extra, Lato OFL incluida). Importación desde PDF, imagen o HTML: `inspect` (páginas en PNG,
  bloques de texto con posición, tamaño y fuente, imágenes, paleta, columnas, barra, banda,
  márgenes, secciones con su columna, `capacity` y ATS), `scaffold-html` (una base de HTML y CSS
  que ya se parece al original) y `compare` (lado a lado con SSIM orientativa). `jh doctor`
  comprueba Chromium e imprime `moderna-2col` sin red. UI: «Solo PDF», «Original | Recreación» en
  la galería y en «Mi CV», y la subida ya no avisa de la 08b. 1084 tests de backend y 52 de
  frontend; los de Chromium se saltan si no está instalado (la CI lo instala). Prueba de los
  comandos y de la API con el CV ficticio de los fixtures: correcta. **Pendiente:** la prueba
  manual con un CV real (`dev/pruebas/fase-08b-prueba-manual.txt`, parte 4) y, con ella,
  `docs/AGENTS_COMPAT.md`.
- **Decisiones:**
  - Errores del motor html como los del PDF (`ChromiumUnavailableError` → `pdf_unavailable`,
    `HtmlRenderError` → `pdf_failed`): API, MCP y CLI no cambian. `EngineNotAvailableError` fuera.
  - La página se carga desde un origen virtual (`http://jh.local/`) con `route` sobre todo; además
    Chromium arranca sin resolución de nombres. Variables estrictas en Jinja (`StrictUndefined`):
    `validate` detecta `labels.foo` o `e.rol` en html (en docx sigue la deuda de la 08.1).
  - `inspect` de PDF con pypdfium2 carácter a carácter: tamaño efectivo con la matriz del carácter
    (Chromium dibuja a 0,75), negrita y cursiva por nombre y flags (el peso de pdfium no es
    fiable), espacios por el hueco típico de cada línea (con `letter-spacing` los de pdfium
    partían palabras). Logros por viñeta de texto o por sangría (las viñetas de lista se dibujan).
  - Columnas, barra lateral, banda y márgenes se estiman sobre la imagen (numpy), igual para PDF e
    imagen. Una imagen no se lee (sin OCR): secciones y `capacity` las pasa el agente.
  - Un HTML importado se imprime sin servir ningún fichero (su carpeta es `data/uploads/`). Los
    nombres de fuente del PDF se filtran antes de escribirlos en el CSS base.
  - La SSIM se calcula desenfocada y a 300 px: cuenta la maqueta, no el texto. Diseños distintos
    dan 0,4-0,65; es para ver si una vuelta acerca o aleja, no una nota.
  - Fuente de `moderna-2col`: Lato en woff2 (subconjuntos latin y latin-ext, 108 KB, OFL) en vez
    de los TTF completos (2 MB). Las integradas html se escriben a mano; el script solo hace su
    preview.
  - Una subida `.png` se guarda como `source.png` sin sustituirla por la miniatura (su sha256 la
    marca como importada).
  - Dependencias: `playwright` y `numpy`. Chromium se instala aparte (`playwright install
    chromium`; README, `jh doctor` y CI).
- **Deuda:**
  - Carta en html (punto 7 del encargo): la hará la 08c (`letter.html` en el motor html y en
    `moderna-2col`, y `importar-plantilla-cv` creándola desde la cabecera recreada).
  - `scan` y `clean_css` trabajan con expresiones regulares: escapes CSS (`u\72l(`) pasarían el
    escaneo. No salen a la red (route y sin DNS), pero `validate` no los avisa.
  - El orden de las secciones de un PDF es el del contenido: en diseños de Canva, con el texto en
    orden arbitrario, puede salir desordenado y el agente lo corrige con `--sections`.
  - `jh doctor` imprime `moderna-2col` en cada ejecución (unos 2 s).
  - Al probar la API se cerraron todos los `jh.exe` con `taskkill /IM`: no repetirlo, matar solo
    el PID del servidor de prueba.

### 09 · Conectores de ATS y scheduler — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** `services/ingestion/` con conectores de Greenhouse, Lever (global y UE) y Ashby, y
  opcionales InfoJobs y Adzuna con claves en `.env`. Cada endpoint se verificó contra su
  documentación y, de forma manual, contra tableros públicos reales: lectura sin ningún error por
  oferta. Además: filtro previo de título y ubicación (`prefilter.py`), `run_source` idempotente
  con `source_runs` (migración `0006`, adelantada desde la 09b) y `jh worker` con APScheduler
  (ingesta diaria a `connectors.daily_at`, recuperación al arrancar, reintentos y log legible en
  consola y `data/logs/worker.log`). También `jh sources add | list | test | run | enable |
  disable`, API `/sources`, pantalla **Empresas** («12 ofertas encontradas, 3 tras filtros») y
  aviso en `jh doctor`. 1183 tests de backend y 57 de frontend. Guía de prueba manual en
  `dev/pruebas/fase-09-prueba-manual.txt`. **Pendiente:** la prueba manual con tus empresas
  objetivo.
- **Decisiones** (ADR-019):
  - Filtro previo indulgente: el título debe contener todas las palabras de algún rol (la regla
    del score) o una `title_keywords` de la fuente. La ubicación debe encajar con tus zonas o ser
    remota si aceptas remoto. Sin ubicación o sin perfil, pasa.
  - Ya visto = mismo `source_id` + `external_id`, misma URL o misma huella: no se crea ni se pide
    el detalle. Dentro de una fuente con conector, ids distintos no son duplicado difuso entre sí
    (sin esto, «Senior Data Engineer» en remoto se cerraba como duplicado de «Data Engineer» en
    Vigo). Frente a otras fuentes, el difuso no cambia.
  - Una tarea `run_source` por fuente, en un solo hilo. Red, 5xx, 429 o fallo interno: se
    reintenta. 404 o formato inesperado: no. Si la fuente falla entera, `last_run_at` no avanza y
    al arrancar se vuelve a encolar. Los portales sin claves no se encolan. Las tareas que quedaron
    `running` vuelven a la cola al arrancar.
  - Primero la red y después la escritura, en un savepoint. Un fallo inesperado queda como
    `internal_error` sin dejar ofertas a medias.
  - Las respuestas de las APIs son contenido no confiable. URLs solo http(s), ids de ruta con
    `[A-Za-z0-9_-]`, sin redirecciones (Adzuna lleva las claves en la URL) y log de httpx en
    WARNING. Lo encontró la revisión.
  - Hora en `config/policies.yaml` (`connectors.daily_at: "07:30"`, `timezone: Europe/Madrid`).
  - La API usa `POST /sources/{id}/active` en vez de `PATCH`: CORS sigue con GET y POST.
  - Dependencia: `apscheduler` 3.x (la 4 sigue en alfa).
- **Deuda:**
  - Adzuna solo da un extracto de la descripción: tratar sus ofertas como resumen en la 09b.
  - El filtro previo deja fuera los títulos en otro idioma que tus roles (p. ej. «Ingeniero de
    datos» si solo tienes «Data Engineer»): añade el rol en los dos idiomas o usa `title_keywords`.
  - Sin herramientas MCP de fuentes: `list_sources`, `save_source` y `record_source_run` llegan con
    la 09b, y `jh sources list --json` ya devuelve la salida prevista.
  - InfoJobs y Adzuna solo se han probado con respuestas grabadas: no había claves.
  - `parse_datetime` toma como UTC las fechas sin zona (posible desfase de horas en `posted_at`).
  - Con el servidor MCP de Claude Code abierto, `uv add` sigue fallando: APScheduler se instaló con
    `uv add --no-sync` + `uv pip install`. Ejecuta `uv sync --directory backend` con Claude Code
    cerrado.
  - La BD real necesita `jh db upgrade` (hasta 0006).

### 09b.1 · Ofertas resumen y alertas por correo — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** la fase 09b se parte en tres encargos (`dev/prompts/09b.1-*`, `09b.2-*` y `09b.3-*`) en
  la rama `fase/09b-alertas-captura-busqueda`. Esta subfase añade:
  - migración `0007` (`jobs.platform`, `jobs.detail_level`, índice único parcial
    (`platform`, `external_id`) y tabla `email_messages`);
  - etapa `pending_detail` y evento `detail_captured`;
  - `services/platforms.py` (LinkedIn, InfoJobs, Indeed y Tecnoempleo, con patrones verificados
    con URLs públicas reales);
  - prefiltro de resúmenes con la seniority del título;
  - conector de correo `services/ingestion/email/`: IMAP en solo lectura y `data/inbox/`, un parser
    de LinkedIn y otro genérico;
  - tareas `poll_email` y `expire_summaries` en el worker;
  - `jh alerts poll | list | expire`, `GET /alerts`, `POST /alerts/poll` y pantalla «Alertas»
    (`J`/`K`, `O` abre en el portal, `D` descarta, con deshacer);
  - comprobación IMAP en `jh doctor`.

  1304 tests de backend (uno de ellos con un servidor IMAP falso que falla ante cualquier
  escritura) y 60 de frontend.
- **Decisiones:**
  - Desde `pending_detail` solo se admiten `detail_captured`, `discarded`, `expired`,
    `duplicate_detected`, `injection_suspected` y `note`. `WORKING_STAGES` separa las demás
    transiciones (y el matching) de `OPEN_STAGES`. `detail_captured` es reservado: lo registrará la
    captura de la 09b.2.
  - El prefiltro se calcula al listar y no se guarda. Los resúmenes no se filtran al entrar: el
    usuario ya eligió sus alertas, y la bandeja los ordena.
  - `store_job` deduce `platform` de la URL cuando su id coincide con `external_id` (o no hay), y
    reconoce primero por (`platform`, `external_id`). LinkedIn y Indeed se guardan con su URL
    canónica; las demás, sin parámetros de seguimiento. Los redirectores de seguimiento se leen sin
    seguirlos.
  - La detección de riesgo de un resumen mira el texto de la oferta, no el HTML del correo: los
    «preheader» ocultos de las alertas marcarían `hidden_text` en todas.
  - IMAP: `EXAMINE`, `UID SEARCH SINCE` (`summary_expire_days`), primero solo los `Message-ID` y
    luego `BODY.PEEK[]` de los nuevos. TLS con `ssl.create_default_context()`: en Python 3.12,
    `IMAP4_SSL` sin contexto no verifica el certificado (lo detectó la revisión). Nombre de
    carpeta en UTF-7 modificado.
  - Un correo cuya oferta no se pudo guardar por un error de BD no se anota en `email_messages`,
    así que se reintenta. Un correo de plataforma conocida sin ofertas sí se anota, con el aviso
    `no_jobs_found`.
  - Parser: tarjeta = el bloque más grande que solo enlaza esa oferta, sin llegar a `body`; como
    mucho 8 líneas, 1000 enlaces y 200 ofertas por correo; sin caracteres de control.
  - `POST /capture` sin prefijo `/api`, como el resto de la API (docs corregidos).
  - `jh alerts` es solo CLI (no hay herramienta para agentes): lo usan la persona y el worker.
- **Deuda:**
  - **Faltan alertas reales.** El parser de LinkedIn y el genérico (InfoJobs, Indeed, Tecnoempleo)
    se construyeron con fixtures inventados que imitan la estructura conocida. Hay que afinarlos
    con correos reales en `data/inbox/samples/` (punto 7 del encargo).
  - Un correo sin `Message-ID` se descarga entero en cada pasada IMAP (se descarta luego por su
    hash).
  - `POST /alerts/poll` hace la red dentro de la petición (hasta 30 s de IMAP más las descargas).
  - Dar de alta por URL una oferta que ya está como resumen devuelve «ya existe» sin completarla:
    eso lo hará la captura de la 09b.2.
  - Una oferta de un correo sin empresa se descarta con el aviso `invalid_item`.
  - `.env.example` sin las variables `JH_IMAP_*`: el agente no puede leerlo ni editarlo
    (permisos). Hay que añadirlas a mano.
  - La BD real necesita `jh db upgrade` (hasta 0007).

### 09b.2 · Botón «Enviar a Job Hunter» — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:**
  - `services/capture.py`: token con `jh capture token` (solo su sha256 en `data/capture_token`,
    comparación en tiempo constante) y captura. Completa un resumen (`detail_captured`, actor
    `user`), reconoce lo ya guardado o da de alta con la fuente `browser_capture`, con detección de
    riesgo sobre el texto y el HTML del bloque de la descripción.
  - `POST /capture`: origen y token en una dependencia que va antes que el cuerpo (403/401; 503 si
    no hay token).
  - `jh doctor` dice si la captura está lista.
  - Extensión Manifest V3 en `extension/`: JavaScript plano, popup, opciones, extractores
    (LinkedIn, Indeed, InfoJobs, Tecnoempleo, JSON-LD y `main`), iconos y README para Chrome y Edge.
  - Tests: 1330 de backend y 72 de frontend, de los que 12 son de la extensión, con HTML inventado.
- **Decisiones:**
  - **Id fijo:** `key` pública en el manifiesto, así que el id es
    `hnaofhehllbkghfehnehamjbkcmdjmle` en cualquier equipo, en Chrome y en Edge. Es el valor por
    defecto de `JH_CAPTURE_EXTENSION_ID`. La clave privada no hace falta para cargarla sin
    empaquetar y no se guardó.
  - **Popup** con el resultado y «Abrir ficha» (un badge no admite enlaces). El badge queda como
    señal en la pestaña: ✓, = o !.
  - **Pestaña:** el popup manda el `tabId`, y el service worker solo atiende mensajes de su propio
    `popup.html`.
  - **Sin empresa** en una oferta nueva: 422, que pide seleccionar el texto con la empresa.
  - **Sin CORS para la extensión**, a diferencia del encargo: sus `host_permissions` la eximen, y
    añadirla le dejaría leer toda la API sin token. Lo señaló la revisión. CORS sigue solo para
    la UI.
  - **Sin `main` en portales conocidos:** si su HTML cambia, la extensión no manda la página
    entera. Además, un resumen no se completa con texto de `main` sin selección, porque podría ser
    la lista de resultados de LinkedIn. Lo encontró la revisión.
  - **Orden de la captura:** primero se busca la oferta y luego se exige la descripción (200
    caracteres), así una ya guardada se reconoce aunque falle el extractor.
  - **URLs:** la extensión quita el fragmento y, si la URL es enorme, se queda solo con
    `currentJobId`. La app guarda la URL canónica en LinkedIn e Indeed, y en el resto la recorta a
    2000 caracteres quitando la query si hace falta.
  - **Texto:** se usa `innerText`, que respeta el CSS; en los tests, un recorrido que salta lo
    oculto en línea, scripts y botones, con un salto de línea por bloque. El HTML del bloque sí
    viaja, para detectar `hidden_text`.
  - **Tests de la extensión:** los ejecuta el Vitest del frontend (`server.fs.allow` incluye
    `../extension`), sin dependencias en `extension/`.
  - El test de una oferta sola de la 09b.1 ya no depende del fin de línea: `core.autocrlf` deja
    los `.eml` con CRLF en Windows.
- **Deuda:**
  - **Prueba manual pendiente** (`dev/pruebas/fase-09b-prueba-manual.txt`, que cubre también la
    09b.1): cargar la extensión, enviar una oferta real de LinkedIn (y de otros portales) y
    generar su CV. Los selectores de los portales se escribieron sin páginas
    reales delante: hay que ajustarlos con esa prueba.
  - El token vive sin cifrar en `chrome.storage.local`, como en cualquier extensión.
  - El puerto de la API (8000) está fijo en el manifiesto y en `core.js`.
  - `.env.example` sigue sin `JH_IMAP_*` ni `JH_CAPTURE_EXTENSION_ID` (el agente no puede
    editarlo).

### 09b.3 · Plataformas y búsqueda con navegador — 2026-10-02 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 09b. Añade:
  - esquemas `AgentBrowseSource`, `SourceRunSummary` y `AgentBrowseLimits`, y la política
    `agent_browse` en `core/policies.py`;
  - `services/ingestion/browse.py`: `save_source`, `record_run`, `update_settings` y
    `source_for_job`;
  - herramientas `list_sources`, `save_source` y `record_source_run`, y `add_job_from_text` con
    `source_id`, `platform` y `external_id`. `jh sources list` pasa al registro: misma salida, con
    `browse` y los límites;
  - error nuevo `not_allowed` (403 en la API) y `POST /sources/{id}/browse`;
  - pantalla «Plataformas» con el aviso de riesgo de LinkedIn;
  - skill `buscar-ofertas` al día y guía de prueba manual `dev/pruebas/fase-09b.3-prueba-manual.txt`.

  Sin migraciones: la configuración va en `sources.config`. Tests: 22 casos de paridad nuevos,
  tests del servicio y de la API, y 4 de frontend.
- **Decisiones:**
  - Una plataforma se identifica por su nombre normalizado. `priority` va de 1 a 10 (1, primero).
    `allow_agent_browsing` está activada por defecto (el usuario ya la aprobó en `configurar`),
    salvo en LinkedIn.
  - LinkedIn se reconoce por `platform` o por cualquier búsqueda de linkedin.com o lnkd.in (que
    pasa a ser LinkedIn en `platforms.py`). Un `true` del agente da `not_allowed`. Si lo activó el
    usuario, se conserva, y una plataforma LinkedIn no puede pasar a ser otra.
  - Defensas en el código, más allá del encargo (ADR-012):
    - `add_job_from_text` con `source_id` y `record_source_run` exigen la navegación activada;
    - una oferta de LinkedIn, por URL o por `platform`, solo entra por la plataforma LinkedIn;
    - las `search_urls` son del dominio de la plataforma conocida o, si no, todas del mismo sitio.

    Lo encontró la revisión.
  - `record_source_run`: `after_filters = created + existing`, actor `agent`, y `last_run_at` no
    retrocede. Las fechas del futuro (más de 5 minutos) se rechazan.
  - El alta de plataformas sigue siendo cosa del agente: la UI lista y edita prioridad, acceso y
    el interruptor.
- **Deuda:**
  - **Prueba manual pendiente** (`dev/pruebas/fase-09b.3-prueba-manual.txt`):
    `buscar-ofertas configurar` y un recorrido real con Claude in Chrome sobre una plataforma de
    acceso libre. Tienes que reiniciar Claude Code para que su servidor MCP cargue las herramientas
    nuevas.
  - Riesgo residual: la API local no tiene autenticación. Un agente con terminal podría activar
    LinkedIn con `confirm_risk: true` sin pasar por la UI. Está documentado en `FUENTES_OFERTAS.md` y
    en `POLICIES.md` §8.
  - `sources.active` no se usa en las plataformas: se apagan con `allow_agent_browsing`.
  - Siguen pendientes las pruebas manuales de la 09b.1 y la 09b.2, las variables de `.env.example`
    y `uv sync` con Claude Code cerrado.

### 10.1 · Seguimiento: kanban, ficha de proceso y calendario — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:** la fase 10 se parte en tres encargos (`dev/prompts/10.1-*`, `10.2-*` y `10.3-*`) en la
  rama `fase/10-seguimiento-analitica`. Esta subfase añade:
  - migración `0008` (tablas `milestones` y `contacts`) y políticas `followups` y `calendar`;
  - `services/process.py` (hitos con su evento, contactos y ficha de proceso), `tracking.py`
    (seguimientos vencidos, próximos y kanban) y `calendar_ics.py` (iCalendar escrito a mano);
  - herramientas `list_followups_due` y `list_upcoming` con paridad, y `jh calendar export`;
  - API `/board`, `/followups`, `/upcoming`, `/jobs/{id}/process`, hitos, contactos,
    `/milestones/{id}/ics` y `/calendar.ics`; `POST /jobs/{id}/events` acepta `channel`;
  - UI: página «Procesos» (kanban con `@dnd-kit/core`, diálogo que registra el evento, próximos 7
    días y ayuda del calendario), sección «Proceso» en la ficha y aviso de seguimientos en la
    cabecera.

  Guía de prueba manual en `dev/pruebas/fase-10.1-prueba-manual.txt`.
- **Decisiones:**
  - Hitos en tabla propia, enlazados a su evento: crear una entrevista registra
    `interview_scheduled` y una prueba, `test_assigned` (con `payload.milestone_id`), en un
    savepoint. Si el evento no vale en la etapa, no queda el hito. Una entrevista hecha registra
    `interview_done`; reprogramar o cancelar deja una `note`. Plazos y otros no registran eventos.
    Un hito hecho o cancelado no vuelve atrás.
  - El kanban no cambia nada en local: soltar abre un diálogo con los eventos válidos
    (`TRANSITIONS` ∩ `USER_EVENTS`, que da la API). «CV listo» no se alcanza a mano. Hay también un
    botón «Mover» (teclado, lector de pantalla y tests: el arrastre no se simula en jsdom).
  - Cerradas en el tablero: solo las que llegaron a aprobarse, las 50 más recientes, con
    `reopen_to` calculado de sus eventos en una sola consulta.
  - Seguimiento vencido: etapa `applied` y N días (10) desde el último envío o `followup_sent`.
  - Próximos: desde las 00:00 de hoy hasta el final del último día (Madrid), más el
    `application_deadline` de las ofertas sin enviar.
  - `applied`/`applied_manually` desde la UI guardan `channel` y el `render_id` seleccionado.
  - Calendario: UTC, `VALUE=DATE` con fin exclusivo (un rango de varios días incluye el último),
    UID estable y `SEQUENCE`. Google Calendar no puede suscribirse a `127.0.0.1`: se importa el
    fichero (al reimportar, actualiza sin duplicar). El feed es para clientes de escritorio. El nombre
    del `.ics` es ASCII: la empresa es contenido no confiable y la cabecera va en latin-1 (lo vio la
    revisión).
  - Contactos solo en la UI: ninguna herramienta para agentes los devuelve.
  - Dependencias: `@dnd-kit/core` (frontend) y `tzdata` explícita (backend; `ZoneInfo` en Windows).
- **Deuda:**
  - **Prueba manual pendiente:** arrastre en el navegador e importación del `.ics` en Google
    Calendar (criterio de aceptación de la fase 10).
  - El feed solo lleva lo programado: un hito cancelado desaparece del calendario suscrito, pero en
    Google (importado) queda hasta que importes su `.ics` individual con `STATUS:CANCELLED` o lo
    borres a mano.
  - `uv add tzdata` se hizo con `--no-sync`: ejecuta `uv sync --directory backend` con Claude Code
    cerrado.
  - La BD real necesita `jh db upgrade` (hasta 0008).

### 10.2 · Analítica: dashboard del embudo — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:**
  - `services/analytics.py`: una CTE con una fila por oferta (pasos 0/1, fecha de envío y de
    primera respuesta) calculada en SQL sobre `events`. De ella salen, con `GROUP BY` en la BD, el
    embudo de 8 pasos, el resumen por fuente, por puesto (top 8 + «Otros» + «Sin extraer») y por
    semana ISO (con las vacías a cero), el tiempo hasta la primera respuesta y los motivos de
    descarte y de filtro duro. `since` filtra por `first_seen_at` desde las 00:00 de Madrid.
  - Interfaz para agentes: `get_funnel_stats` ↔ `jh stats funnel [--since] --json`, con 4 casos de
    paridad. API: `GET /stats/funnel?since=`.
  - UI: página «Embudo» con Recharts (dependencia nueva, cargada en diferido): cifras clave, embudo,
    primera respuesta, por semana, tablas por fuente y por puesto, motivos; selector de periodo
    (todo, 30 y 90 días, 12 meses o desde una fecha) y estados vacíos. Cada gráfica lleva una tabla
    oculta para lectores de pantalla. Colores `--chart-1`/`--chart-2` (azul y naranja) validados
    contra los fondos claro y oscuro (daltonismo y contraste).
  - `scripts/seed_funnel_demo.py`: 1 000 ofertas ficticias con su histórico (con `events.record()`)
    en `data/funnel-demo/`. El test de rendimiento siembra lo mismo y exige `GET /stats/funnel`
    < 1 s (mejor de 3, tras calentar): ~0,25 s. Sin índices nuevos ni migración (un índice
    `events(job_id, type, occurred_at)` no mejoraba nada).
  - 10 tests del servicio con un histórico hecho a mano (cifras exactas), 3 de API/rendimiento y 4
    de la página. 1 432 tests de backend y 94 de frontend.

  Guía de prueba manual en `dev/pruebas/fase-10.2-prueba-manual.txt`.
- **Decisiones** (definiciones en `DATA_MODEL.md` §Embudo):
  - Embudo **acumulado**: una oferta que llega a un paso cuenta en los anteriores (un
    `applied_manually` sin aprobar cuenta como aprobada), y una sola vez aunque se reabra.
  - Triada: `extracted` sin `hard_filter_failed`, o reabierta después del último. Con respuesta:
    respuesta, entrevista, prueba, oferta o rechazo con fecha ≥ primer envío.
  - Duplicadas (`duplicate_detected` no reabierta) fuera del embudo, contadas en
    `duplicates_excluded`. «Después» se decide como la proyección: por (`occurred_at`, `id`).
  - Mediana en Python sobre los días que calcula SQL (SQLite no tiene mediana).
  - Motivos y filtros cuentan ofertas (`COUNT DISTINCT`), no eventos.
  - Semana ISO en Europe/Madrid con la función SQLite `jh_iso_week` (registrada en
    `app/core/db.py` en cada conexión).
- **Deuda:**
  - **Prueba manual pendiente:** la guía de la 10.2 (carga < 1 s en el navegador, modo oscuro,
    móvil). En la revisión automática, la API respondió en ~0,5 s en frío con 1 000 ofertas.
  - `jh_iso_week` y `json_each` son de SQLite: pasar a Postgres (ADR-002) exige reescribirlas.
  - La barra de navegación se sale de la pantalla en móvil (en todas las páginas; ya pasaba antes).
  - El bundle principal sigue por encima de 500 kB (~800 kB, ya antes de la 10.2): habría que
    trocear más rutas.
  - `pnpm install` en el frontend para Recharts.

### 10.3 · Paquete de candidatura — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 10.
  - `ApplicationAnswers` en `schemas/llm_io.py` (las cuatro claves obligatorias; 1-50 respuestas).
  - Migración `0009`: `documents.edited_by_user`.
  - `services/answers.py`: `save_application_answers` (agente), `save_user_answers` (UI) y
    `get_package`. Validación con un detalle por problema y sin guardar nada.
  - Herramienta `save_application_answers` ↔ `jh applications save-answers ID --file F --json`,
    con 4 casos de paridad. API `GET /jobs/{id}/package` y `POST /jobs/{id}/answers`.
  - `ProcessDocuments.answers_document_id` ya se rellena.
  - UI: sección «Paquete de candidatura» en la ficha, entre «Proceso» y «CV». Muestra:
    - el CV elegido (abrir PDF, enlace a la sección CV);
    - las respuestas con «Copiar» y «Editar», aviso ámbar en las de `needs_user_input` y
      «Añadir pregunta»;
    - el hueco de la carta.
  - `CopyButton` compartido con «Procesos».
  - El skill `preparar-candidatura` aclara las evidencias válidas y que no hay campo de nota.
  - 13 tests de servicio y API y 5 de la sección. 1 448 tests de backend y 99 de frontend.

  Guía de prueba manual en `dev/pruebas/fase-10.3-prueba-manual.txt`.
- **Decisiones:**
  - Evidencias de una respuesta: las del CV (`evidence_refs`), los ids de las historias STAR,
    `extraction` y `user`. Una respuesta con texto necesita al menos una. Vacía, solo con
    `needs_user_input`.
  - Solo en `approved` y `cv_ready`: después del envío el paquete se ve y se copia, pero no se
    edita.
  - Edición del usuario: documento nuevo con `edited_by_user` y actor `user`. Manda el último y el
    anterior se conserva.
    - No exige evidencias, pero las que haya deben existir en la versión del perfil de las
      respuestas que edita.
    - Si cambia el texto, la UI añade `user` al respaldo. Vacía = pendiente de un dato tuyo.
  - `application_prepared` pasa a actor `agent`/`user` (antes ponía `system` en `DATA_MODEL.md`),
    con `payload.document_id` y `edited_by_user`.
  - El idioma del documento sale de la extracción (`es`/`en`; si no, `es`).
  - La clave de consulta del paquete cuelga de la del CV: renderizar o elegir otro render lo
    refresca.
- **Nota para la 08c:**
  - `JobPackage.cover_letter` es hoy `None`. La 08c lo cambia por la carta seleccionada (texto
    plano para copiar y `pdf_url` del render), y `ProcessDocuments.cover_letter_document_id` se
    rellena igual que `answers_document_id`.
  - En `PackageSection.tsx`, `CoverLetterSlot` pasa del aviso a la carta, con `CopyButton`.
  - La carta editada reutiliza `documents.edited_by_user`.
- **Deuda:**
  - **Prueba manual pendiente:** la guía de la 10.3. También siguen pendientes la de la 10.1
    (arrastre e importación del `.ics` en Google Calendar) y la de la 10.2.
  - La BD real necesita `jh db upgrade` (hasta 0009).
  - Que el salario vaya siempre con `needs_user_input` lo impone el skill. El código comprueba que
    las evidencias existen, no lo que dice la respuesta.
  - La suite del frontend es sensible a la carga: con otros procesos pesados en paralelo, algunos
    tests de páginas no tocadas superan los 5 s o el `findBy` de 1 s. Por separado, o con
    `--testTimeout=30000` y la máquina libre, pasan.

### 08c.1 · Carta: indicaciones, contenido, verificación y render básico — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:** la fase 08c se parte en tres encargos (`dev/prompts/08c.1-*`, `08c.2-*` y `08c.3-*`)
  en la rama `fase/08c-carta-presentacion`. Esta subfase añade:
  - `preferences.cover_letter` en el perfil (opcional; también en `demo/profile.example.yaml`) y
    la política `cover_letter` validada;
  - migración `0010` (`cover_letter_briefs`);
  - `schemas/cover_letter.py`;
  - `services/documents/cover_letter.py`: brief, guardar con copia de las indicaciones usadas,
    validación, resolución de opciones a juego con el CV, render, selección, verificación, texto
    plano y edición del usuario (lista para la UI de la 08c.3);
  - eventos `cover_letter_generated` y `cover_letter_verified` (reservados, sin cambio de etapa);
  - plantilla integrada `carta-simple` (`kind: letter`, solo carta, acento libre);
  - las cinco herramientas con paridad (`jh letter brief|show|save|render|save-verification`);
  - el rol `verificador` también para cartas, y `generar-carta` y `actualizar-perfil` al día.

  17 tests del servicio y 13 casos de paridad. 1 495 tests de backend y 99 de frontend.
- **Decisiones:**
  - `TemplateMeta` gana `kind` (`cv` | `letter`) y `letter: {file}`.
    - Una plantilla `kind: letter` no necesita `template.*` ni secciones, y no aparece como
      plantilla de CV: `templates.get` y `list_templates` filtran por `kind`.
    - El contrato de la carta se valida aparte (`LETTER_CONTRACT_VARIABLES`).
  - `AccentColorOption.free`: admite cualquier `#RRGGBB` (lo usa `carta-simple` para heredar el
    color del CV).
  - El render del CV se parte en `write_files`, `store_files` y `prepared_photo`, que reutiliza
    la carta. Los motores aceptan `file` para renderizar `letter.*`.
  - Palabras: solo los párrafos, `\w+` Unicode.
  - Skills en texto libre:
    - se comprueban las de `keywords_targeted` y las de la oferta y las básicas nombradas en los
      párrafos, con los alias del matching;
    - una skill de la oferta que no está en el perfil solo puede nombrarse en un párrafo que cite
      `extraction` y nada del perfil: si cita también un logro, se la estaría atribuyendo (lo vio
      la revisión);
    - las claves se normalizan con `checks.skill_key`, como en el CV (quita «nociones de…»).
  - Evidencias citables: las del CV y las historias STAR (`checks.citable_refs`, compartido con
    las respuestas de la 10.3). `extraction` exige que haya extracción.
  - Contenido del documento: `{letter, instructions: {brief, preferences, max_words}}`. Las
    preferencias se copian como dict: si su esquema cambia, las cartas antiguas se siguen abriendo.
  - Opciones de la carta:
    - foto, color y página salen del render seleccionado del CV, también si se elige otra
      plantilla de carta a mano;
    - una plantilla elegida a mano sin carta da `not_found` (sin respaldo);
    - sin CV, se aplican las reglas del perfil.
  - El subtítulo de la carta es el del CV de la oferta o el `headline`. La fecha es la del día del
    render, en Europe/Madrid. El texto plano no lleva destinatario, fecha ni contacto.
  - `jh templates validate` acepta las plantillas solo de carta. `jh doctor` avisa si falta la
    carta de reserva (`cover_letter.fallback_template`).
  - La edición del usuario (`save_user_letter`) reutiliza las opciones del render seleccionado de
    la carta anterior.
- **Deuda y notas para la 08c.2 y la 08c.3:**
  - Toda carta salía con `carta-simple` y aviso `letter_fallback`; resuelto en la 08c.2.
  - `generar-carta` ya no mencionaba la UI de la ficha; resuelto en la 08c.3.
  - `service.select_render` y la API `/renders/{id}/select` solo aceptan CVs; la selección de la
    carta está en `cover_letter.select_render`. Unificarlo en la 08c.3. `/renders/{id}/pdf` ya
    sirve las cartas, porque no mira el tipo de documento.
  - El texto plano solo existe en el servicio: la API lo sirve en la 08c.3.
  - La BD real necesita `jh db upgrade` (hasta 0010).

### 08c.2 · Carta: diseño a juego con el CV — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:**
  - `ats-simple` y `clasica-foto` traen `letter.docx`: su misma cabecera (la de `clasica-foto`,
    con foto en tabla) y un cuerpo de carta común. Los genera `build_builtin_templates.py`, y
    los `template.docx` del CV no cambian ni un byte.
  - `moderna-2col` trae `letter.html` y `letter.css`, con la barra lateral (foto y contacto) y la
    cabecera del CV. Probada con Chromium: una página.
  - `jh templates build-letter <id> [--force]` (`importer/letter.py`): crea `letter.docx` de una
    plantilla docx del usuario desde su `template.docx`. Probado con una copia de una plantilla
    importada real: conserva su cabecera centrada y la fuente del cuerpo.
  - `jh templates preview <id> --letter` (carta de muestra, en la caché). `validate` comprueba
    y renderiza también la carta.
  - El skill `importar-plantilla-cv` tiene un paso «Carta de presentación a juego»: en docx,
    `build-letter`; en html, `letter.html` a mano.
  - 19 tests nuevos: integradas, foto y color del CV en la carta de `clasica-foto`,
    `moderna-2col` en PDF, hash y bloque `letter:` (CRLF, líneas vacías, en medio), `build-letter`
    con un Word ficticio con la cabecera en tabla, errores, corte de cabecera (con controles
    anidados), orden OOXML, preview y saneado de `letter.css` y `letter.html`. 1 515 tests de
    backend.
- **Decisiones:**
  - Hash por documento: el del CV ignora `letter.*` y el bloque `letter:` de `template.yaml`, y
    el de la carta ignora `template.docx|html`. Así, añadir la carta a las integradas no marca
    como «Plantilla cambiada» los CVs ya renderizados (comprobado contra el `template.yaml`
    anterior, con CRLF).
  - En html, los estilos de la carta van en `letter.css`, que también se sanea, para no tocar
    `style.css` ni el hash del CV.
  - `build-letter`:
    - la cabecera son los bloques del principio que solo usan `name`, `subtitle`, `contact` o
      `photo`, más los párrafos de control que los cierran;
    - el primer bloque con variables del cuerpo (o con `show`) corta. Una cabecera mezclada con
      el cuerpo (tabla a dos columnas) da error y la carta sigue con `carta-simple`;
    - `layout.header_paragraphs` solo dice si hay cabecera: los índices son del original, no de
      `template.docx`;
    - el cuerpo copia `pPr`/`rPr` del primer párrafo de contenido (no de títulos `labels.*`),
      sin viñetas, bordes ni sangría;
    - `letter:` se añade como texto al final de `template.yaml`, sin reescribir el resto;
    - se prepara en `data/tmp/` y solo se copia si valida. La carta y el YAML se copian con
      `os.replace`, primero la carta;
    - `pPr` y `rPr` se escriben en el orden de OOXML (`get_or_add_*` de python-docx): Word
      rechaza los hijos desordenados aunque LibreOffice los tolere (lo vio la revisión);
    - del párrafo del CV se toma la letra, no su énfasis (negrita, cursiva, color, mayúsculas);
    - avisa si la cabecera conservada no lleva contacto o subtítulo, y deja la carta a una
      columna si el CV acababa en varias.
  - La carta de muestra de la preview sale del perfil (resumen y primer logro de las dos
    primeras experiencias). Nunca se guarda.
- **Deuda:**
  - Las previews de la carta no están en la galería (UI de la 08c.3).
  - Los renders de carta hechos en la 08c.1 guardaron el hash completo de la plantilla; ahora es
    el de la carta. Nadie lo compara hoy: si la 08c.3 enseña «Plantilla cambiada» en las
    cartas, esos saldrán como cambiados una vez.
  - `build-letter` no sirve para cabeceras en el encabezado de página de Word: se conservan tal
    cual, porque las secciones no se tocan, pero el corte no las detecta como cabecera. Si el
    cuerpo empieza directamente, da error.

### 08c.3 · Carta: API, UI y paquete de candidatura — 2026-10-03 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 08c.
  - **API** (`routes/letters.py`):
    - `GET /jobs/{id}/cover-letter`: indicaciones, carta vigente con su TXT, plantilla del CV
      seleccionado y plantillas con carta;
    - `POST /jobs/{id}/cover-letter/brief`;
    - `POST /jobs/{id}/cover-letter`: edición del usuario;
    - `POST /cover-letters/{doc}/renders`;
    - `GET /cover-letters/{doc}/text`: TXT en UTF-8, `\r\n`, `Carta-<Nombre>.txt`;
    - `/renders/{id}/select` sirve para CV y carta (`service.render_kind`).
  - **UI**: sección «Carta de presentación» en la ficha, después de «CV»:
    - indicaciones de la oferta, editables, y resumen de las del perfil, con el límite resuelto;
    - con carta: texto, palabras/límite y verificación, «Copiar texto», «Descargar TXT»,
      «Editar» (por párrafos, más saludo y despedida, con recuento en vivo);
    - formulario «Diseño» («A juego con el CV (…)» u otra plantilla con carta), foto y color;
    - renders con avisos, «Descargar PDF», DOCX y «Usar esta para enviar»;
    - sin carta, qué pedir al agente. En `closed` sin carta no aparece. Tras enviar, solo se
      ve y se copia.
  - **Paquete de candidatura**: `JobPackage.cover_letter` (texto, palabras, estado, `pdf_url` del
    render seleccionado), con «Copiar carta» y «Abrir PDF».
    `ProcessDocuments.cover_letter_document_id` ya se rellena.
  - `generar-carta` vuelve a recordar lo que se hace en la ficha. README, `ARCHITECTURE.md` y
    guía de prueba manual de toda la fase (`dev/pruebas/fase-08c-prueba-manual.txt`).
  - 7 tests de API y 9 de frontend (8 de la sección y 1 del paquete con carta). 1 522 tests de
    backend y 108 de frontend.
- **Decisiones:**
  - La carta y el paquete cuelgan de la clave de consulta `cv`: cambiar el render seleccionado
    del CV refresca «A juego con el CV» y el paquete.
  - Edición:
    - cuando escribe el usuario, `user` vale siempre (su texto es su respaldo);
    - los párrafos que cambian añaden `user` en el servidor (`mark_user_paragraphs`), no en
      React. Antes lo hacía el frontend y fallaba sin indicaciones guardadas: lo vio la revisión;
    - «Guardar» se desactiva sin cambios (así no se pierde la verificación por nada) o sin
      ningún párrafo;
    - se reutilizan las opciones del render seleccionado de la carta anterior.
  - El TXT para copiar llega en la propia respuesta (`plain_text`); el de descarga, por su ruta.
  - «A juego con el CV» manda `template_id: null`; la foto «Como el CV» es `auto`.
- **Deuda:**
  - **Prueba manual pendiente:** `dev/pruebas/fase-08c-prueba-manual.txt` (criterio de aceptación
    de la fase: `/generar-carta` con indicaciones, PDF a juego y TXT sin errores; abrir los DOCX
    en Word).
  - La BD real necesita `jh db upgrade` (hasta 0010).
  - El recuento de palabras de la UI (`\p{L}\p{N}_`) puede diferir del `\w` de Python en casos
    raros de Unicode; manda el del servidor.
  - La suite del frontend sigue siendo sensible a la carga de la máquina (ver 10.3).

### 11.1 · Candidatura asistida: motor de rellenado y envío protegido — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:** la fase 11 se parte en dos encargos (`dev/prompts/11.1-motor-rellenado.md` y
  `11.2-revision-envio-ui.md`) en la rama `fase/11-candidatura-asistida`. Esta subfase añade:
  - `services/applier/`:
    - `browser.py`: contexto persistente en `data/browser-profile/`, visible, en un hilo propio;
      el worker es su único dueño;
    - `platforms.py`: Greenhouse, Lever, Ashby y LinkedIn por la URL, y si no, mirando la página
      (iframe de un ATS conocido, `generic` o `unknown`); también valida la URL;
    - `guard.py`: captcha visible, anti-bot y login (`needs_user`), y el bloqueo del envío mientras
      se rellena;
    - `fields.py`: campos por etiqueta accesible, clasificación, plan y rellenado;
    - `tokens.py`, `submit.py` y `service.py`;
  - migración `0011` (`application_attempts`) y evento `application_filled` (system, reservado);
  - tareas del worker `browser_open`, `apply_open`, `apply_fill`, `apply_rescan`, `apply_submit` y
    `apply_focus`, sin reintentos (`tasks.NO_RETRY_KINDS`, `fail_interrupted`);
  - política `applier` (timeouts, TTL del token, similitud de preguntas) y `JH_BROWSER_HEADLESS`,
    `JH_BROWSER_CHANNEL`;
  - `ARCHITECTURE`, `DATA_MODEL`, `POLICIES` §5.1, `AGENT_INTERFACE` y README al día.

  Tests:
  - 9 con Chromium contra formularios locales (Greenhouse, Lever, Ashby, genérico en español,
    captcha, login, sin formulario, una web que intenta enviarse sola y `safe_click`);
  - 14 del servicio: el flujo completo con 0 envíos al rellenar y exactamente 1 con el token;
    token inventado, usado o caducado; confirmación pendiente; sin reintentos; URL local;
  - 25 de clasificación y plan, y 6 estáticos: fuera de `submit.py` nada pulsa el envío; la CLI y
    el MCP no importan el servicio.

  En total, 1 584 tests de backend y 108 de frontend.
- **Decisiones:**
  - Un **motor común** con particularidades por plataforma, en vez de un rellenador por ATS:
    - la URL del formulario (Lever `/apply`, Ashby `/application`);
    - los marcadores de obligatorio (`*`, `✱`) y los sí/no con botones de Ashby.

    Los tres ATS comparten etiquetas accesibles y el motor sirve también para los genéricos.
  - **Token:**
    - lo emite `confirm_submission` tras comprobar el nombre de la empresa y que `reviewed_at`
      coincide con la versión revisada;
    - la BD guarda solo su hash;
    - viaja una vez en el `payload` de `apply_submit` y se borra al consumirlo o rechazarlo;
    - una segunda confirmación con otra pendiente da `busy`.
  - **Tras un clic no se vuelve a `ready`** (`token_used_at`):
    - un fallo posterior al clic queda `submit_unconfirmed`;
    - «Volver a revisar» se rechaza;
    - un intento nuevo lleva el aviso `possible_duplicate`. Lo vio la revisión.
  - **Sin confirmación reconocida, no hay `applied`.** Con ella, el worker lo registra en su propia
    transacción con actor `user`, `channel: ats_form`, `attempt_id` y la captura en `evidence`.
  - **Campos:**
    - nunca se rellenan datos sensibles: género, origen, discapacidad, nacionalidad, estado civil,
      salud, antecedentes…;
    - los consentimientos obligatorios (aviso legal) se marcan justo antes de pulsar, tras tu
      confirmación;
    - una casilla obligatoria que no es legal la decides tú;
    - nombre de pila = primer término; apellidos = el resto.
  - **Captcha:** el reCAPTCHA invisible solo deja un aviso; para un desafío visible.
  - **Navegador:** sin trucos anti-detección. Nunca reutiliza una pestaña tuya. Si cierras la
    ventana, se vuelve a abrir. Si su hilo muere, la orden falla en vez de colgar el worker.
  - **URL:** solo `http`/`https` y nunca la propia máquina (`JH_APPLIER_ALLOW_LOOPBACK`, solo
    para los tests).
  - **Bloqueo del envío:** se rearma antes de cada campo. Protege de accidentes, no de una web
    hostil, y así consta en `guard.py`.
- **Deuda y notas para la 11.2:**
  - La API debe exigir `reviewed_at` y mostrar el dominio de destino, el botón que se pulsará
    (aviso `submit_button`) y los consentimientos que se aceptan (`AttemptView.consents`).
  - Avisar si el worker no está en marcha: las tareas se quedan en cola. `jh worker --once`
    cierra el navegador al acabar, así que la pestaña preparada se pierde.
  - Los comboboxes de Greenhouse (React-select) solo se han probado con su marcado accesible
    estándar. La prueba manual con una oferta real lo dirá.
  - La BD real necesita `jh db upgrade` (hasta 0011).

### 11.2 · Candidatura asistida: revisión, envío y UI — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 11.
  - **API** (`routes/apply.py`, capa fina):
    - `GET /jobs/{id}/apply`: último intento y qué haría «Preparar» (`get_state`);
    - `POST /jobs/{id}/apply/prepare`, `/apply/{id}/rescan`, `/apply/{id}/focus` y
      `/jobs/{id}/apply/manual-done`;
    - `POST /apply/{id}/submit` con `{company_confirmation, reviewed_at}` (obligatorio): la única
      puerta al envío;
    - `GET /apply/{id}/screenshot/{review|confirmation}` (solo desde `data/applications/`) y
      `POST /browser/open`.

    `ApplierError` va al formato común con el código del servicio en `details`.
  - `AttemptView` gana `domain`, `can_rescan`, `submit_button` (aviso con `detail`) y
    `pending_task` (para avisar si el worker no está en marcha). `can_submit` exige «CV listo».
  - **UI**: sección «Candidatura asistida» en la ficha, después del paquete:
    - preparar, o «Abrir y preparar» en LinkedIn;
    - pantalla de revisión: captura, tabla de campos con estado, valor y origen, obligatorios
      sin respuesta en ámbar, avisos;
    - diálogo «Enviar»: dominio, botón que se pulsará, consentimientos y el nombre de la empresa;
    - «Volver a revisar», «Lo termino yo», «Marcar como enviada», «Preparar de nuevo» y
      «Preparar navegador»;
    - se refresca cada 2 s mientras trabaja el worker y refresca la ficha al quedar enviada.
  - El skill `preparar-candidatura` pide las preguntas literales del formulario (el rellenado las
    busca por parecido) y remite a la sección.
  - `ARCHITECTURE`, `RESUMEN_FASES` y guía de prueba manual (`dev/pruebas/fase-11-prueba-manual.txt`).
  - 13 tests de API y 15 de la sección. 1 597 tests de backend y 123 de frontend.
- **Decisiones:**
  - «Preparar navegador» va en la propia sección: no hay página «Estado» en la UI.
  - El diálogo de envío confirma una **foto del intento** tomada al pulsar «Enviar»: aunque
    llegue una versión nueva, se manda la `reviewed_at` que viste y el servidor da `stale`. Se monta
    solo mientras está abierto (siempre empieza vacío) y no es un formulario: Intro no envía. Lo
    vio la revisión.
  - Enviada pero sin registrar `applied` (fallo del evento): la sección lo dice y ofrece «Marcar
    como enviada».
  - «Marcar como enviada» se rechaza (`busy`) mientras el worker trabaja en el intento.
  - Tras cualquier error de una acción, se vuelve a pedir el estado (`onSettled`).
- **Deuda:**
  - **Prueba manual pendiente:** `dev/pruebas/fase-11-prueba-manual.txt`, que es el criterio de
    aceptación de la fase: una oferta real de Greenhouse o Lever hasta la pantalla de revisión,
    sin enviar. Sobre todo, los desplegables con buscador de Greenhouse.
  - La UI repite la lista de estados del servicio (`REVIEW`, `RETRY`, `MANUAL`). Si cambian,
    habría que exponer acciones permitidas desde el backend, como `can_rescan`.
  - El aviso del worker sale tras 15 s en cola, aunque la causa sea otra tarea larga delante.
  - La BD real necesita `jh db upgrade` (hasta 0011).

### 12.1 · Demo y portfolio: modo demo — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:**
  - Encargos de las tres subfases (`dev/prompts/12.1-*`, `12.2-*`, `12.3-*`) y su tabla en el de la 12.
  - `services/demo.py` y `jh demo seed [--dir] [--force] [--json]` crean `data-demo/`
    (gitignored) con:
    - el perfil y la foto de `demo/`;
    - 60 ofertas ficticias con extracción y score, en 6 fuentes (dos de ATS en pausa);
    - 276 eventos en las 8 semanas anteriores: descartes con motivo, filtros duros, envíos,
      seguimientos, respuestas, pruebas y entrevistas (algunas futuras, en horario de Madrid y
      entre semana), rechazos, una caducada y una oferta;
    - 2 CVs verificados en `cv_ready`;
    - la oferta con la instrucción oculta de `demo/jobs/02`, con `risk_flags`.
  - Catálogo en `demo/seed/catalog.yaml` y `cvs.yaml`.
  - `Settings.demo_mode` (marca `.demo`), `demo_mode` en `get_status` y `GET /status`, y banner
    «Modo demo: datos ficticios» en todas las páginas.
  - README («Probar con datos de demo»), `ARCHITECTURE`, `AGENT_INTERFACE` y ADR-020.
  - 11 tests de backend y 2 de frontend nuevos (1 608 y 125 en total).
  - Prueba real: `jh demo seed` en unos 30 s con LibreOffice; con `jh serve` y `pnpm dev`, la
    Bandeja, el Embudo y los Procesos salen llenos y con el banner (capturas con Playwright).
- **Decisiones:**
  - Todo pasa por los servicios. La única excepción (ADR-020): las fechas de los eventos
    automáticos de cada oferta recién creada se llevan al día de su alta y se recalcula la
    proyección.
  - PDF de los CVs: `ats-simple` con LibreOffice o Word; si no hay, `moderna-2col` con Chromium
    de Playwright; sin ninguno, la demo se crea sin CVs y lo avisa.
  - El seed se niega a escribir en `data/`, dentro de ella, en sus carpetas padre o en una carpeta
    con contenido sin `.demo`. Para recrear una demo hace falta `--force`.
  - Sin embeddings durante el seed, para que sea reproducible y no descargue modelos.
  - Extracciones y CVs con `agent_name: demo-seed`. Las fuentes de Greenhouse y Lever, en pausa
    (sus tableros no existen).
- **Deuda:**
  - Si el seed falla a medias, la carpeta queda con la marca y hay que repetir con `--force`.
  - Algunos nombres de empresa del catálogo son inventados, pero podrían coincidir con empresas
    reales. Cada oferta dice «(empresa ficticia)» y la UI lleva el banner.
  - `_sources` usa funciones privadas de `ingest` y `capture` para crear sus fuentes.
  - Con embeddings instalados, la app recalcula los scores de la demo al consultarlos (otra
    `scoring_key`).

### 12.2 · Demo y portfolio: evals de matching y de CV — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:**
  - **Matching:** `evals/matching/seed.jsonl` pasa de 20 a 80 casos inventados (40 y 40), con
    trampas de título, oficio, ubicación, nivel, años e idioma. `evals/REPORT.md` recoge las
    métricas, la curva, el umbral elegido y los errores típicos. Sin embeddings: precision 0,88,
    recall 0,95 y F1 0,92 (38/5/2/35).
  - **CV:** `evals/cv/cases.jsonl` (10 ofertas inventadas con keywords esperadas y skills
    prohibidas). `jh demo seed --eval-cv` las da de alta aprobadas y sin CV (en una demo
    existente, solo las que falten).
  - **`jh eval cv [--agent] [--min-coverage]`** (`services/evals/cv.py`) comprueba, en la demo:
    evidencias, skills inventadas o prohibidas, skills básicas no pedidas (en skills, titular y
    resumen), una página, cobertura, idioma y verificación. Informe JSON y Markdown;
    `evals/README.md`.
  - **Prueba:** redactor y verificador de Claude Code en dos ejecuciones distintas, solo con
    `jh … --json` contra `data-demo`, sobre `cv04` y `cv07`: los dos pasan las 7 comprobaciones.
  - 16 tests nuevos del eval de CV; los del matching se adaptan a los 80 casos y
    `scripts/seed_triage_demo.py` sigue usando los 20 primeros. 1 624 tests de backend.
- **Decisiones:**
  - Umbral 55 sin cambios: empata con 60 en F1 y prima el recall (el umbral solo atenúa en el
    triaje).
  - La configuración por defecto no cambia: los falsos positivos de oficio (preventa, docencia,
    ventas) se arreglan con `discard_title_keywords`, que es por usuario.
  - La cobertura del eval de CV cuenta solo las skills pedidas que la candidata tiene, más las
    keywords del caso: un CV honesto no puede cubrir lo que no está en el perfil.
  - Identidad estable de cada caso: la URL `https://empleo.example.com/eval-cv/<id>`.
  - Ayuda de `--file`: «tmp/ de la carpeta de datos», no `data/tmp/` fijo.
- **Deuda:**
  - Comparar con embeddings (`uv sync --extra matching`) y elegir modelo (ADR-006).
  - Hallazgos de la prueba sin MCP, para la 12.3:
    - los roles solo nombran herramientas MCP, no su comando `jh`;
    - las skills no se traducen en un CV en inglés («Modelado dimensional»);
    - las secciones extra solo existen en español;
    - la ayuda sale mal codificada en Git Bash sin `PYTHONIOENCODING=utf-8`;
    - el encargo del agente decía `jh match get` (es `jh match show`).
  - El filtro de ubicación no sabe de cercanía (Ourense, Pontevedra).

### 12.3 · Demo y portfolio: compatibilidad, README y seguridad — 2026-10-05 · Claude Code (Opus 5.5)
- **Resumen:** cierra la fase 12.
  - **Matriz de compatibilidad.** `jh demo seed --compat` da de alta las 5 ofertas de
    `evals/compat/jobs.txt` solo con su texto, completo y en su idioma (`services/demo_text.py`).
    Claude Code sin MCP, con una ejecución por rol:
    - 54/55 campos extraídos como se esperaba;
    - 5/5 valoraciones;
    - 5/5 CVs al primer intento, verificados y que pasan `jh eval cv`
      (`dev/pruebas/fase-12.3-matriz-sin-mcp.md`, `docs/AGENTS_COMPAT.md`).
  - **Roles** `extractor`, `redactor` y `verificador`: sección «Sin MCP» con sus comandos `jh`.
    El redactor ya no traduce skills ni incluye secciones extra en otro idioma.
    `AGENT_INTERFACE` explica las skills básicas, las evidencias citables e
    `include_regional_language`.
  - **README de portfolio:**
    - problema y qué hace;
    - demo en 5 minutos;
    - 3 diagramas Mermaid;
    - decisiones con su ADR;
    - tests y evals;
    - agentes;
    - límites éticos;
    - 6 capturas de la demo en `docs/img/`.

    El kit y la guía por fases pasan a `dev/DESARROLLO_POR_FASES.md`.
  - **CI:** paso «Demo de humo» (`jh demo seed --compat --eval-cv` en una carpeta temporal).
  - **Seguridad:**
    - `data/`, `.env`, bases de datos, perfiles y fotos reales nunca han entrado en el historial
      (solo la foto ficticia de `demo/`);
    - ningún dato del perfil real (correo, teléfono, enlaces, empresas, centros, proyectos) aparece
      en parches, mensajes ni ficheros;
    - lo único que aparece es el nombre del usuario: en rutas de su carpeta de Windows dentro de
      versiones antiguas de `dev/pruebas/` y en un mensaje de merge (su usuario de GitHub). Ya
      figura como autor de los commits; no se reescribe el historial.
  - **Clon limpio** (con cachés de uv y pnpm y Chromium instalados): sembrado y frontend instalado
    en 81 s; API y UI respondiendo en 92 s.
  - 1 627 tests de backend y 125 de frontend.
- **Decisiones:**
  - Codex queda fuera de la matriz por decisión del usuario; en la tabla figura como «sin probar».
  - La pasada con MCP la hace el usuario en una demo aparte (`data-demo-mcp/`, guía en
    `dev/pruebas/fase-12-compatibilidad.txt`); `.gitignore` cubre `data-demo*/`.
  - La matriz reutiliza casos del eval de CV, así que la misma URL sirve para medir la extracción
    y el CV.
- **Deuda:**
  - **Prueba manual pendiente:** Claude Code con MCP sobre la matriz
    (`dev/pruebas/fase-12-compatibilidad.txt`).
  - **CI pendiente de comprobar en GitHub:** el paso nuevo solo se ha probado en local, y con
    LibreOffice; en CI irá con Chromium.
  - Sin MCP:
    - el esquema de las entradas no llega con la herramienta (`jh schema …` lo resolvería);
    - `procesar-ofertas` no admite elegir ofertas;
    - `generar-cv` no pregunta por las skills básicas que la valoración planteó.
  - El verificador no ve el título crudo de la oferta (no tiene `get_job`).
  - Una oferta remota sin país lleva foto por la política por defecto.
  - El README mezcla portfolio y manual de uso (355 líneas); se podría mover «Usarlo con tus
    datos» a `docs/`.

### Mejora · Arranque del servidor MCP — 2026-10-09 · Claude Code (Opus 5.5)
- **Problema:** `jh-mcp` tardaba ~5 s en caliente y ~17 s en frío (Windows Defender revisa cada
  fichero de `.venv`), y Claude Code lo daba por caído a los 30 s.
- **Cambios:**
  - `trafilatura`, `alembic` y `pypdf` se importan solo dentro de las funciones que los usan;
  - `dump_json` pasa a `app/agent_interface/output.py`, así el servidor ya no importa la CLI
    (Typer);
  - `migrations.head_revision()` se cachea: antes releía las migraciones en cada llamada;
  - test `test_server_startup_skips_heavy_imports`;
  - `.claude/settings.json`: `MCP_TIMEOUT=60000`.
- **Resultado:** ~3,5 s en caliente. Lo que queda es sobre todo el SDK de MCP (~1,5 s) y
  SQLAlchemy (~0,5 s).
- **Recomendado en local:** excluir `backend/.venv` de Windows Defender.

### Mejora · Candidaturas desde portales de empleo — 2026-10-10 · Claude Code (Opus 5.5)
- **Problema:** las ofertas de InfoJobs, Tecnoempleo, Indeed y Glassdoor apuntan a la ficha de la
  oferta, no al formulario. «Preparar candidatura» intentaba rellenarla: en Indeed rellenó el
  buscador («Qué / Dónde»). «Preparar navegador» abría una pestaña en blanco sin explicación y
  fallaba si habías cerrado la ventana.
- **Cambios** (ADR-021):
  - los portales se reconocen por la URL y solo se abren; nunca se rellena una página suya ni de
    LinkedIn;
  - «Rellenar esta página» (`POST /apply/{id}/fill-page`, tarea `apply_fill_page`) rellena el
    formulario de la empresa al que te llevó el portal;
  - la oferta de un portal se abre en tu navegador (Glassdoor bloquea el navegador automatizado
    con Cloudflare y eso no se esquiva); `prepare` admite `form_url` para rellenar el formulario
    de la empresa al que te llevó «Solicitar»;
  - detector genérico más estricto: adjunto, o correo y nombre, fuera de buscadores y logins;
  - en una web de empresa sin formulario visible, se pulsa «Enviar solicitud» (o equivalente) para
    cargarlo, como en Teamtailor (`careers.idealista.com`, comprobado sin rellenar ni enviar);
  - «Abrir navegador» con página de inicio y enlaces a los portales; si la ventana se cerró, se
    vuelve a abrir;
  - la UI explica los pasos en un portal y ofrece «Marcar como enviada» desde el principio.
- **Tests:** detección de portales, ficha de portal ficticia (`portal.html`) que no se rellena,
  «Rellenar esta página» con el formulario en una pestaña nueva y negativa en una página del
  portal, `form_url`, página de inicio del navegador y la UI.
- **Pendiente:** probarlo con ofertas reales de cada portal (`dev/pruebas/fase-11-prueba-manual.txt`).

### Mejora · Seguimiento, avisos y plataformas — 2026-10-10 · Claude Code (Opus 5.5)
- **«¿Qué ha pasado con esta candidatura?»** en la ficha de las ofertas enviadas o en proceso:
  botones directos (Me han respondido, Tengo entrevista, Entrevista hecha, Prueba técnica, Oferta
  recibida, Acepto, Me han rechazado, Me retiro, Sin respuesta). Reutiliza el diálogo del tablero:
  registra el evento con fecha y nota (y el hito, en entrevistas y pruebas). En Procesos, el
  enlace «Mover» pasa a ser un botón «Actualizar estado».
- **Ficha de una oferta ya enviada:** «¿Qué ha pasado?» va lo primero, a todo el ancho; después el
  proceso (hitos y contactos), la extracción y el encaje. Lo de antes de enviar (candidatura
  asistida, paquete, CV, carta y texto) queda plegado en «Antes de enviar» y solo se carga al
  abrirlo.
- **Historial compacto:** con 7 eventos o más se ven los 4 últimos y el alta; el resto, con «Ver N
  eventos más» (los avisos de posible inyección, siempre).
- **«Triaje» → «Por revisar»** en la UI (`/por-revisar`; `/triaje` redirige).
- **Avisos al usuario** (ADR-022): `request_user_action` / `wait_user_action`, tabla
  `user_prompts` (migración 0012), pop-up global con cuenta atrás y notificación del sistema;
  espera de 5 minutos y, si no, el agente sigue. El skill `buscar-ofertas` los usa ante un
  captcha, un anti-bot o un login; la candidatura asistida también.
- **«Añadir plataforma»** en Plataformas (`POST /sources/platforms`): portales conocidos o uno
  propio; LinkedIn se crea siempre desactivada, con el aviso de por qué conviene dejarla así.
- **Tests:** servicio y API de avisos (incl. espera que vuelve al contestar), paridad MCP ↔ CLI de
  las dos herramientas nuevas, alta de plataformas, y UI (pop-up, plataformas, «¿Qué ha pasado?»).

### Mejora · CV a medida de cada oferta — 2026-10-11 · Claude Code (Opus 5.5)
- **Rol `redactor`:** nueva sección «Adaptar a la oferta». Antes de redactar, el redactor identifica
  las 2-3 necesidades centrales de la oferta, los logros que mejor las prueban y su vocabulario
  literal. Subtítulo, resumen, orden y enfoque de los logros, proyectos y skills cambian con cada
  oferta. Puede cambiar el énfasis de un logro, nunca su alcance.
- **Rol `verificador`:** avisa (`warning`) si el CV es genérico (un resumen que valdría para otra
  oferta del mismo rol) o si contradice las indicaciones del usuario. Un hecho respaldado solo por
  las indicaciones es `blocker`.
- **Indicaciones generales para los CVs:** `preferences.cv.instructions` y `preferences.cv.avoid`
  en el perfil, opcionales. Orientan la redacción y nunca respaldan hechos; las indicaciones de
  cada oferta mandan sobre ellas. Llegan al agente con `get_profile`. POLICIES §3 y el skill
  `actualizar-perfil` lo recogen.
- **Enlaces en el CV** (ADR-023): `url` opcional en los proyectos del perfil (`projects[].url` en
  el contrato). LinkedIn, GitHub y el enlace de cada proyecto se pueden pulsar en el PDF de los
  dos motores: el código los enlaza al renderizar y la plantilla sigue sin poder poner `href`
  externos. Las integradas y el HTML base del importador muestran el enlace del proyecto.
- **Inicio** (`/`): resumen de lo que te toca hoy (frase con enlaces a cada lista), recorrido de
  las ofertas por etapa con quién actúa en cada una (tú, el agente o la empresa), mejor encaje por
  revisar, listas para enviar, próximos 7 días y candidaturas sin respuesta. La bandeja pasa a
  `/bandeja`. La cabecera ya no se parte en escritorio ni ensancha la página en móvil.
- **Plataformas:** las búsquedas salen como etiquetas legibles («data engineer · Madrid»,
  «analytics engineer · Remoto») que abren la búsqueda en el portal; las URLs completas, al
  desplegar. `lib/searches.ts` lee los parámetros habituales (Indeed, InfoJobs, Tecnoempleo,
  Glassdoor, LinkedIn); lo que no entiende sale como «Todas las ofertas».
- **Puestos en español:** `config/title_aliases.yaml` (genérico) traduce «Ingeniero/a de datos»,
  «Analista de datos», «Ingeniero de Big Data»… a su nombre en inglés para compararlos con
  `preferences.roles`, en el prefiltro de alertas y conectores y en el score. Antes una alerta
  «Ingeniero de Datos Snowflake» salía como que no encajaba con tus puestos.
- **Tests:** ejemplo del perfil demo, valores por defecto, items vacíos en `avoid`,
  `public_view`, `url` del proyecto, enlaces en docx (integradas) y en html (incluido el PDF de
  `moderna-2col`) y que una plantilla no puede añadir los suyos.

### Mejora · Botones que abren tu agente (ADR-024) — 2026-10-11 · Claude Code (Opus 5.5)
- **«Buscar ofertas»** (y «Procesar ofertas» / «Evaluar encaje» si hay pendientes) en Inicio,
  **«Procesar ahora»** en el aviso de ofertas por extraer y **«Generar CV»** / «Volver a redactar»
  en la ficha de una oferta aprobada. Abren tu agente en una terminal con la orden del skill escrita.
- `services/agent_launch.py` (órdenes cerradas, programa desde `launch` del manifiesto, `JH_AGENT`,
  `unset_env`), `GET /agent` y `POST /agent/launch` (solo desde la UI: `Origin` y JSON). Sin agente
  disponible, la UI copia la orden.
- La orden va a PowerShell codificada (`-EncodedCommand`): `wt` parte su línea por cada `;`.
- **Plataformas:** icono de cada portal (lo carga tu navegador del propio portal, sin referer; si no
  carga, la inicial) y enlace a su página base, sacada de sus búsquedas.
- **Tests:** órdenes, comando de PowerShell (comillas y variables quitadas), elección de agente,
  API (lanza, oferta no aprobada o inexistente, otra web o cuerpo no JSON rechazados, orden para
  copiar si no hay agente) y UI (lanzar y copiar).

### 13 · Contexto y documentos — 2026-10-11 · Claude Code (Opus 5.5)
- **Resumen:**
  - `services/context.py`: los cuatro ficheros de `data/contexto/`, `get_context` con hash y
    límite de 20 KB, `init` desde las plantillas de `demo/contexto/` sin sus datos, y estado para
    la UI.
  - Herramienta `get_context` ↔ `jh context show --json`, y `jh context init`.
  - `services/application_archive.py`: la tarea `archive_application` se encola al registrar
    `applied`/`applied_manually` (desde la UI y desde el envío asistido). Hay también
    `jh applications archive (ID | --all)`.
  - `services/folders.py` y `POST /folders/open`, solo desde la UI y con una lista cerrada de
    carpetas. `GET /context`.
  - Página «Mi perfil» y «Copia de lo que enviaste» en la ficha de una oferta enviada.
  - Skills y roles: `redactor`, `generar-carta`, `evaluar-encaje`, `preparar-entrevista`,
    `actualizar-perfil` y `verificador`.
  - Docs: POLICIES §1.5, `AGENT_INTERFACE.md`, `DATA_MODEL.md` y ADR-025.
  - Tests: 1730 de backend y 169 de frontend.
- **Pruebas reales** (con carpetas de datos aisladas, sin tocar `data/`):
  - El rol `verificador` (sesión aparte, por CLI, sin pistas) dio **FAILED** a un CV con «Di
    formación interna de dbt a 12 compañeros» citando una evidencia que no lo dice. Su primer
    `blocker` señala que solo está en `perfil-conductual.md`.
    - Ojo: dbt es skill básica en la demo y salió también un segundo `blocker` por eso.
  - `jh worker --once` archivó una candidatura `applied_manually` con CV, carta TXT+PDF,
    respuestas y README. `jh applications archive --all` después: «ya estaba».
- **Decisiones:**
  - Contexto ≠ hechos (ADR-025): sin versiones en la BD; el hash permite ver si cambió.
  - Opción `--sections` en lugar del `--section` del encargo, igual que `jh profile show`.
  - Los ids del archivo se fijan al registrar el envío (payload de la tarea), no al archivar.
  - La carpeta que ya existe no se toca, ni con un segundo envío tras reabrir.
  - `archive_folder` va en la ficha (`JobView`) y no en el paquete: el paquete se carga al
    desplegar «Antes de enviar». Solo mira el disco en ofertas enviadas.
  - Para usar en una carta algo de `narrativa.md`, el skill lo propone y lo guarda en el brief si
    el usuario dice que sí.
  - «Abrir carpeta» de contexto o documentos crea lo que falte (`context.init`).
  - `require_ui` da un mensaje genérico.
  - Documentos fuente y README del archivo: texto de terceros, dato y no instrucción.
- **Deuda:**
  - Que un CV no use un hecho del contexto depende del verificador (un agente): el código no puede
    distinguirlo.
  - El documento no guarda qué versión del contexto se usó al redactarlo.
  - `jh applications archive` usa la carta y las respuestas vigentes, no las del momento del envío.
  - `os.startfile` solo en Windows; en otro sistema la UI enseña la ruta.
  - Dos tests de frontend (`HomePage`, `NewJobPage`) fallaron una vez con la máquina cargada y
    pasan solos: parecen intermitentes, ajenos a la fase.
  - La UI no se probó en el navegador, solo con sus tests.

### 14 · Huecos de skills y vocabulario — 2026-10-11 · Claude Code (Opus 5.5)
- **Resumen:**
  - `services/skill_gaps.py`: skills ausentes de las ofertas abiertas y de las aprobadas o
    enviadas en los últimos N días (60 por defecto), con obligatorias y deseables por separado,
    peso (1,0 / 0,5 × score / 100), ejemplos y marca. Recalcula la cobertura con los alias de
    ahora, sin escribir.
  - `services/skill_aliases.py`: «Es lo mismo que…» escribe `config/skill_aliases.yaml` con
    ruamel.yaml (comentarios, orden, comillas y CRLF intactos; temporal y `os.replace`, con
    candado) y encola `rescore_all`. Rechaza sinónimos que ya apuntan a otra skill o que el perfil
    ya cubre.
  - Caché de alias de skills y de puestos por contenido o fecha del fichero: el worker ve los
    cambios sin reiniciarse.
  - Tabla `skill_gap_marks` (migración 0013): «La tengo» / «No la tengo».
  - Herramienta `get_skill_gaps` ↔ `jh skills gaps --json`. API `GET /skills/gaps`,
    `POST /skills/aliases` y `POST /skills/marks` (estas dos, solo desde la UI).
  - Página «Skills»: filtros de periodo, tipo y marca, orden por ofertas o peso, diálogo «Es lo
    mismo que…» y botones del agente «Añadir al perfil las que tengo» y «Plan de formación»
    (acciones `anadir-skills` y `plan-formacion` en `agent_launch.ACTIONS`).
  - Skill nuevo `plan-formacion` y sección nueva en `actualizar-perfil`.
  - Docs: POLICIES §2, `AGENT_INTERFACE.md`, `DATA_MODEL.md`, `ARCHITECTURE.md`,
    `AGENTS_COMPAT.md`, README, `config/README.md` y ADR-026.
  - Tests: 1759 de backend y 175 de frontend.
- **Pruebas reales** (carpeta de datos aislada, sin tocar `data/`): `jh demo seed` y
  `jh skills gaps` sobre la demo listan 11 skills ausentes en 35 ofertas (Estadística, Looker,
  Excel…).
- **Decisiones:**
  - «La tengo» solo guarda la marca; el botón lanza `actualizar-perfil` con una orden fija y el
    agente lee las marcas con `get_skill_gaps`. Ningún nombre de skill de una oferta llega a la
    orden (ADR-024).
  - Los alias van a `config/` y no a `data/`: son genéricos (ADR-026). Aparecen como cambio en
    git.
  - Marcas y alias solo desde la UI: no hay herramienta ni comando para escribirlos.
  - Las marcas se guardan por la forma canónica y siguen visibles aunque sus ofertas salgan del
    periodo.
  - `POST /skills/marks` en vez de `PUT`: CORS solo admite GET y POST.
  - Los huecos se calculan al pedirlos, no se guardan. Una oferta sin match cuenta como score 50.
  - Revisión del rol `revisor` aplicada: marcas `have` fuera del periodo, avisos de dato no
    confiable, caché de puestos coherente con `normalize`, candado y temporal único al escribir el
    YAML, nombres de más de 80 caracteres ignorados.
- **Deuda:**
  - La UI no borra alias: un error se corrige editando el fichero.
  - Marcas huérfanas si alguien cambia a mano el canónico de una skill.
  - El candado es por proceso: dos procesos escribiendo a la vez el fichero (API y algo más) no se
    excluyen. Hoy solo escribe la API.
  - Pendiente de prueba manual: la página «Skills» con datos reales (alias, marcas y recálculo del
    worker), «Añadir al perfil las que tengo» y `plan-formacion` con Claude Code (web y escritura
    de `data/documentos/plan-formacion.md`).

### 15 · Respuestas por correo y seguimientos — 2026-10-11 · Claude Code (Opus 5.5)
- **Resumen** (tres subfases en la misma rama, un commit por subfase):
  - **15.1** · Migración 0014 (`replies`, `message_drafts`). `services/replies.py`:
    - lee por IMAP en solo lectura `JH_IMAP_REPLIES_FOLDER` (por defecto `INBOX`) o
      `data/inbox/respuestas/`, solo si hay candidaturas en `applied`/`in_process`;
    - pide primero las cabeceras y el cuerpo solo de lo que casa con una candidatura (contacto,
      dominio de la empresa, ATS que la nombra o nombre de la empresa en el dominio);
    - guarda el texto visible, con detección de inyección también en lo oculto, y lo entrega
      envuelto en `<untrusted_email>`.
    - Herramientas `list_replies`, `get_reply` y `save_reply_proposal` (`jh replies
      list|show|propose`), `jh replies poll`, tarea `poll_replies`, comprobación en `jh doctor`.
    - Rol `clasificador` y skill `revisar-respuestas`. Correos ficticios en
      `demo/emails/respuestas/`.
  - **15.2** · API `/replies` (bandeja, correo, leer ahora, aceptar e ignorar con `require_ui`,
    que pasa a `api/deps.py`). Aceptar registra el evento como `user` con `payload.reply_id` y,
    con fecha, crea el hito; `none` archiva sin evento. Página «Respuestas», aviso en la ficha,
    recuento en el menú, Inicio con «Revisar respuestas» (acción `revisar-respuestas`).
  - **15.3** · `services/drafts.py`: `save_message_draft` ↔ `jh drafts save` (seguimiento o
    agradecimiento; sustituye el vigente), «Ya lo he enviado» (registra `followup_sent`) y
    «Descartar», solo desde la UI. Tope `followups.max_followups` (2) también en el aviso del
    tablero y de la ficha. `list_followups_due` con `followups_sent`, nombres de contactos,
    `draft_id` y `thanks_due` (`followups.thank_you_days`). Skill `redactar-seguimiento`, sección
    «Borradores» en la ficha y «Redactar borradores» en Procesos (acciones
    `redactar-seguimiento` y `redactar-seguimientos`). La comprobación de etapa de `agent_launch` es
    por acción.
  - Docs: `CONFIGURAR_CORREO.md`, `AGENT_INTERFACE.md`, POLICIES §5, `DATA_MODEL.md`,
    `AGENTS_COMPAT.md`, README, ADR-027 y `dev/pruebas/fase-15-prueba-manual.txt`.
  - Tests: 1831 de backend y 188 de frontend.
- **Pruebas reales** (carpeta de datos aislada, sin tocar `data/`): el rol `clasificador` (Claude
  Code, modelo rápido, modo sin MCP) clasificó los 5 correos de la demo. Salieron entrevista con
  su hito (jueves 8, 10:00 +02:00), rechazo vía Greenhouse, prueba con plazo de todo el día y
  oferta, todos con confianza `high`. El correo con inyección oculta salió `none` con confianza
  `low` y marcado. Ninguna oferta cambió de etapa.
- **Decisiones:**
  - Bandeja de entrada por defecto, con privacidad por diseño: cabeceras primero, nada guardado
    de lo que no casa, sin conexión sin candidaturas abiertas (ADR-027).
  - Avisos de portales fuera por defecto (`replies.portal_sender_domains` vacío). `none` permitido
    para acuses de recibo.
  - La propuesta no registra nada; aceptar solo desde la UI, sin herramienta ni comando. El
    orquestador `revisar-respuestas` no lee correos.
  - Con una sola candidata, un puesto que no coincide del todo baja la confianza a `medium`, no a
    `low`, para no perder el hito.
  - Un correo anterior a la hora anotada del envío se registra desde el envío.
  - Revisión del rol `revisor` aplicada:
    - tope de seguimientos en tablero, ficha y «Ya lo he enviado»;
    - coincidencia por nombre más estricta (igualdad, primera palabra de 5+ letras o sufijo
      corporativo; `metaphor.com` ya no es «Meta»);
    - correos sin fecha descartados;
    - `POST /replies/poll` solo desde la UI;
    - no se repite el agradecimiento de una entrevista ya agradecida;
    - límite de `require_ui` frente a un agente con terminal, documentado en ADR-027.
- **Deuda:**
  - `.env.example` no lleva `JH_IMAP_REPLIES_FOLDER`: el agente no tiene permiso sobre ese
    fichero. Añádela a mano (opcional, por defecto `INBOX`).
  - No hay hito de «plazo» para responder a una oferta: va en el resumen. Encaja en la fase 21.
  - Un agradecimiento descartado vuelve a salir en `thanks_due` mientras dure `thank_you_days`.
    Un agradecimiento enviado solo queda en `message_drafts` (no hay evento).
  - Un borrador de seguimiento sigue vigente aunque la empresa conteste; se descarta a mano.
  - El botón «Seguimiento enviado» del proceso registra `followup_sent` sin cerrar el borrador
    abierto (marcar ese borrador después lo rechaza el tope si ya son 2).
  - Pendiente de prueba manual: IMAP real sobre `INBOX`, la UI de «Respuestas» y «Borradores» en
    el navegador y `redactar-seguimiento` con datos reales
    (`dev/pruebas/fase-15-prueba-manual.txt`).

### 16 · Ofertas vivas, republicadas y búsqueda ampliada — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen** (dos subfases en la misma rama):
  - **16.1** · Migración 0015:
    - `jobs.signals`: `possibly_closed`, `liveness`, `open_confirmed` y `reposted`;
    - `job_sightings`, con relleno de la primera publicación de cada oferta.
  - **16.1** · `services/liveness.py`, ¿sigue abierta?:
    - ATS por su API pública (Greenhouse y Lever 404; Ashby, ausencia en el tablero);
    - el resto con un GET acotado: 404/410, redirección que pierde la oferta, frases de
      `liveness.closed_phrases`, `validThrough` pasado;
    - `unknown` ante bloqueos, anti-bot (`liveness.blocked_phrases`) o páginas que no muestran la
      oferta. LinkedIn, `skipped`.
  - **16.1** · Cuándo y cómo avisa:
    - evento `closure_suspected` sin cambio de etapa; motivo de descarte nuevo `closed`;
    - tarea `check_open` cada día (aprobadas y con CV) y al arrancar el worker;
    - `check_job_open` ↔ `jh jobs check-open`, que llama `generar-cv` antes de redactar;
    - API `check-open` y `still-open` con `require_ui`.
  - **16.1** · `services/reposts.py`: publicación anotada en el alta, por huella y en los
    conectores. Republicada = mismo canal, empresa, título comparable y ubicación, en días
    distintos dentro de 90.
  - **16.1** · UI: insignias «¿Cerrada?» y «Republicada ×N» en Bandeja y Triaje; aviso en la ficha
    con «Descartar» (ya marcado con «Ya no está publicada»), «Sigue abierta» y «Comprobar otra
    vez»; comprobación al abrir una aprobada; aviso junto a «Generar CV».
  - **16.2** · `services/search_titles.py`: `get_search_titles` ↔ `jh jobs titles`, con
    `matches_roles` (puestos que apruebas y el filtro previo deja fuera). Skill `ampliar-busqueda`
    y botón en Plataformas (acción `ampliar-busqueda`).
  - **16.2** · `services/ingestion/discover.py`: `jh sources discover --file F [--add] [--json]`
    (hasta 3 slugs por empresa en Greenhouse, Lever global/UE y Ashby; `confirmed`, `probable` o
    `doubtful`; `--add` nunca da de alta las dudosas). Sin MCP, a propósito.
  - Docs: FUENTES_OFERTAS, DATA_MODEL, AGENT_INTERFACE, POLICIES §2, ARCHITECTURE, AGENTS_COMPAT,
    README, RESUMEN_FASES, ADR-028 y `dev/pruebas/fase-16-prueba-manual.txt`.
  - Tests: última pasada completa con 1937 de backend y 195 de frontend en verde, antes de
    aplicar la revisión. Los tests añadidos después (revisión y botón de Plataformas) pasan por
    separado. La pasada completa final la paró Claude Code por falta de memoria: pendiente.
- **Pruebas reales** (carpeta de datos aislada, sin tocar `data/`):
  - las APIs de Greenhouse, Lever y Ashby responden 404 a una oferta o tablero inexistente y 200 a
    uno vivo; `check_ats` lo interpreta bien con ofertas reales de Stripe, Palantir y Ramp;
  - `jh sources discover` encontró los tableros de las tres y nada para una empresa inventada;
  - en las páginas, Tecnoempleo responde 410 a una oferta inexistente (detectada), Indeed responde 401
    y InfoJobs sirve un control anti-bot con HTTP 200. Por eso se añadió la detección de anti-bot y
    la exigencia de ver la oferta en la página antes de decir «abierta».
- **Decisiones:**
  - Señales en una columna propia y no en `risk_flags`, que sigue siendo solo riesgo de inyección
    (ADR-028, aprobado antes de empezar). Desviación respecto al encargo.
  - Republicadas por canal y ubicación, en días distintos: ni varias ubicaciones el mismo día ni la
    misma oferta en varios portales cuentan.
  - «Sigue abierta» silencia ese motivo hasta que una comprobación vea la oferta abierta.
  - El aviso solo en etapas anteriores al envío; la comprobación diaria, solo de aprobadas y con CV.
  - Las URLs que comprueba el worker vienen de contenido no confiable: se resuelve el DNS y se
    rechaza la red local; del destino de una redirección solo se guarda el dominio.
  - `discover` sin herramienta MCP; «confirmada» exige el nombre completo (no `token_set_ratio`).
  - Revisión del rol `revisor` aplicada: ids en la query (`gh_jid`) y el id de la fuente en el ref,
    `confirmed` estricto, DNS, URL de redirección fuera de los textos, «Sigue abierta» que caduca,
    `InvalidURL`, ubicación en el grupo, textos de API limpios, slugs, Ashby sin mayúsculas, lógica
    de la migración congelada y aviso del servidor MCP matizado.
- **Deuda:**
  - `reposted` no caduca sola: se recalcula al ver otra publicación.
  - Las frases de «oferta cerrada» y anti-bot son heurísticas sin páginas reales cerradas de
    InfoJobs e Indeed (que en la práctica dan `unknown`).
  - El plazo de lectura es por petición, no total (como en el alta por URL).
  - `discover` no enseña progreso y Lever devuelve el tablero entero.
  - Descubrir empresas desde la UI («Empresas»), pendiente.
  - Pendiente de prueba manual: una oferta cerrada real en la ficha, `/generar-cv` con aviso,
    `/ampliar-busqueda` con datos reales y `discover` con tus empresas
    (`dev/pruebas/fase-16-prueba-manual.txt`).

### 17 · Entrevistas: simulacro, repaso y banco de historias — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen:**
  - Migración 0016: `milestones.prep_plan` (JSON), `debrief_notes`, `next_steps` y
    `debriefed_at`. `notes` sigue siendo del usuario.
  - `services/interviews.py` y `schemas/interviews.py`, con tres herramientas y paridad:
    - `get_interviews` ↔ `jh interviews list`: entrevistas de una oferta con plan y repaso,
      contactos (nombre y cargo), `offer_received` y `today`;
    - `save_interview_plan` ↔ `jh interviews plan`: bloques de 15-120 min de hoy al día de la
      entrevista, solo en una programada por empezar y con el proceso abierto;
    - `save_interview_notes` ↔ `jh interviews notes`: solo en una entrevista ya empezada y no
      cancelada.
  - Ninguna registra eventos, cambia el estado del hito ni toca el perfil.
  - Skills: `preparar-entrevista` (dosier por entrevista y plan por días que se guarda con tu OK),
    `simular-entrevista` (nuevo) y `repasar-entrevista` (nuevo, con el modo «dudas antes de
    aceptar»).
  - Botones ADR-024 en el hito: «Preparar», «Simulacro» y «Repasar». En la ficha, «Dudas antes de
    aceptar» con un `offer_received`. `POST /agent/launch` acepta `milestone_id`; la oferta sale
    del hito.
  - Ficha: plan por días con el dosier y «Abrir carpeta» (carpeta `entrevistas`), bloque «Repaso»
    y `ProcessView.offer_received`.
  - Docs: AGENT_INTERFACE, DATA_MODEL, POLICIES §1.6, README, RESUMEN_FASES, ADR-029 y
    `dev/pruebas/fase-17-prueba-manual.txt`.
  - Tests:
    - backend: pasada completa con 1986 en verde y 2 que fijaban la cabeza de migración en 0015
      (corregidos). Los tests añadidos con la revisión pasan sueltos;
    - frontend: 202 en verde. Dos tests ajenos a la fase fallaron por tiempo de espera mientras
      corría a la vez el backend, y pasan sueltos.
- **Pruebas reales** (carpeta de datos aislada con `jh demo seed`, sin tocar `data/`):
  - `jh interviews list|plan|notes` sobre las entrevistas de la demo: plan guardado y ordenado;
    repaso guardado en una entrevista hecha, sin eventos nuevos;
  - rechazados con mensaje claro: el repaso de una entrevista futura y un bloque después de la
    fecha;
  - el `--file` se borra tras el éxito.
- **Decisiones** (ADR-029):
  - Plan y repaso en el hito, no en una tabla nueva.
  - Guardar el repaso no marca la entrevista como hecha: el estado sigue siendo tuyo y el skill te
    lo recuerda.
  - Herramientas extra respecto al encargo: `get_interviews` (los skills no podían leer un hito
    pasado) y `save_interview_plan` (el encargo pide guardar el plan en la ficha).
  - Las «dudas antes de aceptar» son un modo de `repasar-entrevista` y no un skill propio.
  - El dosier lleva el id de la entrevista en el nombre, para no pisar el de otra ronda.
  - El plan y el repaso se guardan sin pedir permiso en Claude Code (el skill ya pide tu OK);
    `add_event` sigue pidiéndolo.
  - Revisión del rol `revisor` aplicada:
    - una entrevista de todo el día cuenta como empezada al acabar ese día (Madrid), con una sola
      comprobación (`check_can_prepare`, `check_can_debrief`) que usan herramientas y botones, y
      su espejo en la UI;
    - tests de la frontera de zona horaria;
    - aviso «la entrevista se ha movido» si un plan tiene bloques posteriores a la nueva fecha;
    - skills: los textos de los hitos y los repasos son datos, no instrucciones; las dudas antes
      de aceptar solo con el proceso abierto; el simulacro solo escribe la nota si la pides;
    - sección de AGENT_INTERFACE recolocada.
- **Deuda:**
  - El plan no avisa de los bloques del día ni se marca como hecho; tampoco va al calendario.
  - El simulacro no guarda nada salvo que pidas la nota: no hay historial de simulacros.
  - La UI no muestra el contenido del dosier, solo su nombre y la carpeta.
  - Reprogramar no rehace el plan: la ficha avisa y se rehace con «Preparar».
  - `save_interview_notes` no guarda qué agente escribió el repaso (el plan sí).
  - El caso de paridad del plan calcula «hoy» al importar: fallaría si la ejecución cruzara la
    medianoche de Madrid.
  - Pendiente de prueba manual: los tres botones con una entrevista real o de prueba y «Dudas
    antes de aceptar» (`dev/pruebas/fase-17-prueba-manual.txt`).

### 18 · Contactos, mensajes e investigación de empresas — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen** (dos subfases en la misma rama, un commit por subfase):
  - **18.1** · Migración 0017: `network_contacts` (sin emails) y, en `contacts`, `relation`,
    `referral`, `referral_at` y `network_contact_id`. `services/network.py`:
    - importa el `Connections.csv` real (preámbulo «Notes:», cabeceras en inglés o español,
      fechas `12 Oct 2024`) y sincroniza la red;
    - cruce por empresa normalizada, `exact` o `probable`, con `JobRow.known_contacts`;
    - `jh contacts import-linkedin` (solo CLI) y `get_job_contacts` ↔ `jh contacts list` (solo
      nombre, cargo, papel y referencia).
  - **18.1** · API `/network`, `/network/import` (`require_ui`, solo la ruta de siempre),
    `/jobs/{id}/network`, `/jobs/{id}/contacts/from-network` y `/contacts/{id}/referral`. UI:
    panel «Tu red» en la ficha, «Conoces a N» en bandeja y triaje, papel y referencia en los
    contactos del proceso, bloque «Por referencia» en el embudo. CSV ficticio en `demo/linkedin/`,
    que importa `jh demo seed`.
  - **18.2** · Migración 0018: `message_drafts` admite `linkedin` y `email` (`recipient_role`,
    `contact_id`, `network_contact_id`, `recipient_name`, `attachments`; `subject` opcional) y la
    tabla `company_research`. `services/company_research.py`: dosier por empresa con citas `[n]`
    validadas, `.md` en `data/documentos/empresas/`, copia `empresa.md` al archivar la
    candidatura y detección de frases de inyección. `get_company_research` ↔ `jh companies
    research` y `save_company_research` ↔ `jh companies save-research`.
  - **18.2** · Skills `redactar-mensaje` e `investigar-empresa`; `preparar-entrevista` usa el
    dosier y `generar-carta` deja explícito que no. Botones «Redactar mensaje» e «Investigar
    empresa»; «Borradores» desde `approved`; sección «Empresa»; carpeta `empresas` en
    «Abrir carpeta».
  - Docs: DATA_MODEL, AGENT_INTERFACE, POLICIES §4, §5, §6 y §7, AGENTS_COMPAT, README,
    RESUMEN_FASES, ADR-030, ADR-031 y `dev/pruebas/fase-18-prueba-manual.txt`.
  - Tests: pasada completa final con 2059 de backend y 212 de frontend en verde; ruff limpio y
    `sync_agents.py --check` en verde.
- **Pruebas reales** (carpeta de datos aislada con `jh demo seed`, sin tocar `data/`):
  - la red demo cruza con 9 ofertas; Brétema Analytics sale con 3 personas, una `probable`;
  - `jh companies save-research`, `research` y `drafts save` con un mensaje de LinkedIn, sin MCP:
    dosier en `documentos/empresas/Bretema-Analytics_3.md` y borrador guardado; `--file` borrado.
- **Decisiones:**
  - Dosier en `data/documentos/empresas/` y no en la carpeta de la candidatura, desviación del
    encargo aprobada antes de empezar (ADR-031).
  - No se guardan los emails de la exportación (aprobado antes de empezar). Un CSV vacío no borra
    la red.
  - La referencia es una marca del contacto, no un evento. Los mensajes amplían `message_drafts`
    y marcarlos enviados no registra evento.
  - Arreglado fuera de la fase: 7 tests de `test_liveness.py` usaban una fecha fija de hoy a las
    08:00 UTC y fallaban en cuanto el reloj la pasaba; ahora son relativas.
  - Revisión del rol `revisor` aplicada:
    - reimportar la red ya no falla si un borrador apunta a alguien que sale del CSV (el borrador
      guarda el nombre del destinatario);
    - la persona de la red de un mensaje tiene que trabajar en la empresa de la oferta;
    - el dosier rechaza fuentes de LinkedIn, escapa títulos y URLs en el `.md`, se enseña antes de
      guardarlo y, con `risk_flags`, los skills no lo usan;
    - «Investigar empresa» solo con la oferta extraída; recuento de caracteres de LinkedIn igual
      que el backend; el README del archivo dice que `empresa.md` no se envió;
    - aviso si una importación quita más de la mitad de la red;
    - ADR-031 separado del 030 y viñeta de `save_message_draft` aclarada.
- **Deuda:**
  - El cruce no conoce filiales ni nombres comerciales («Inditex» / «Zara»).
  - El dosier no caduca solo (aviso a los 30 días) y su `.md` se escribe antes del commit.
  - Un mensaje marcado como enviado no deja rastro en el historial de la oferta.
  - La red solo se pone al día al reimportar; sin URL, quien cambia de empresa se recrea con otro
    id.
  - Pendiente de prueba manual: tu exportación real de LinkedIn, «Investigar empresa» con una
    empresa real y «Redactar mensaje» (`dev/pruebas/fase-18-prueba-manual.txt`).

### 19 · Lote en segundo plano y cola de encargos — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen** (dos subfases en la misma rama):
  - **19.1** · En el manifiesto, `launch.headless` de Claude Code (`claude -p` con `stream-json`,
    `--tools Skill,Agent,Read`, `dontAsk`, `--strict-mcp-config`, `{allowed_tools}` y
    `{denied_tools}`, `skill_rule`) y `launch.resume`. Migración 0019 (`agent_runs`,
    `agent_requests`) y política `background_runs` (30 min, 200 líneas).
    - `agent_launch.ACTIONS[...].background` con las herramientas mínimas de `procesar-ofertas`,
      `evaluar-encaje` y `generar-cv`; `headless_command` permite esas, el skill de la acción y
      `Read(./docs/**)`, y deniega todas las demás del registro.
    - `services/agent_runs.py` (encolar con dedupe, `generar-cv` solo sin obligatorias ausentes o
      con todas marcadas «No la tengo», cancelar, «Abrir en terminal» que retoma la sesión).
    - `services/agent_runner.py`: reclamar con `UPDATE` condicionado (una a la vez), lectura en
      streaming, progreso sin entradas, `PREGUNTA:` → `needs_user`, tiempo máximo, cancelación,
      parada del worker y excepciones que paran el árbol entero (`taskkill /T`), recuperación al
      arrancar. `services/agent_output.py`: el lector de `stream-json`.
    - El worker las ejecuta en su propio hilo; `jh worker --once` también. API `/agent/runs`.
  - **19.2** · Cola de encargos: `services/agent_requests.py`; `list_agent_requests` ↔
    `jh requests list` y `complete_agent_request` ↔ `jh requests complete` (7 casos de paridad);
    `get_status.agent_requests`; skill `atender-encargos` y mención en `resumen-diario`; API
    `/agent/requests`. Acción «Atender encargos».
  - **19.2** · UI: `AgentButton` partido (desplegable con «En terminal», «En segundo plano» y «Dejar
    para mi próxima sesión»), página «Agente» (ejecuciones con estado, progreso, resultado,
    preguntas, Cancelar, Abrir o Contestar en terminal; encargos pendientes y cerrados), aviso
    arriba mientras trabaja, contador en el menú y refresco de todo al terminar una.
  - Docs: ADR-032, AGENTS_COMPAT, AGENT_INTERFACE, DATA_MODEL, POLICIES §6, ARCHITECTURE, README,
    RESUMEN_FASES y `dev/pruebas/fase-19-prueba-manual.txt`.
  - Tests: agente falso (`tests/fixtures/fake_agent.py`) que imita `stream-json` con 10 modos; 64
    tests de agente (comando y herramientas, runner, cola, API, árbol de procesos). Pasada
    completa final: 2108 de backend y 217 de frontend en verde; ruff limpio, build y lint del
    frontend limpios y `sync_agents.py --check` en verde.
- **Pruebas reales** (con `claude` 2.1.296, modelo haiku, BD sin migrar, sin tocar datos): ver
  «Comprobado con claude» en AGENTS_COMPAT. Lo importante: el allow de `.claude/settings.json` se
  colaba (también en subagentes) y por eso las demás herramientas se deniegan; `Skill(nombre)`
  acota y `Agent(nombre)` no.
- **Decisiones:**
  - Herramientas por acción en vez de `mcp__jobhunter__*` (aprobado en el plan), y todas las demás
    denegadas (de la revisión).
  - Codex sin segundo plano (aprobado en el plan): no puede limitar las herramientas MCP.
  - `agent_runs` como cola propia en un hilo aparte del worker, no en `tasks`.
  - La prueba con el `claude` real queda como manual (aprobado en el plan); solo se comprobaron
    las reglas de permisos.
  - Revisión del rol `revisor` aplicada:
    - los POST de cancelar, abrir y quitar exigen cuerpo JSON (`EmptyBody`) y la UI lo manda (si
      no, `require_ui` daba 403 desde el navegador);
    - techo de herramientas con `--disallowedTools` y `Skill(<skill>)` (ver arriba);
    - nunca queda un agente vivo: `try/finally` en `execute`, `stop_active` al parar el worker,
      `recover_interrupted` para el `pid` huérfano si es el agente, y salida a los 10 s si ya
      respondió y no sale;
    - cancelar y terminar condicionados al estado (sin carrera con el worker);
    - el lector de cada agente en su propio módulo (regla dura 2), sin flags de un agente en
      POLICIES;
    - los errores de herramienta solo dicen en cuál fallaron; `can_resume` mira si el agente sabe
      retomar; «Atender encargos» no puede ser un encargo; refresco tras terminar por la fecha y
      no por un recuento; zona horaria de `lib/time`.
- **Deuda:**
  - Sin Job Object de Windows: si el worker muere de golpe, el agente sigue hasta el próximo
    arranque del worker, que lo para. Dos `jh worker` a la vez no están soportados.
  - `Agent` no se puede acotar a los roles de la acción; el techo es el de la sesión.
  - Las preguntas dependen de que el agente use `PREGUNTA:`.
  - El entorno del agente es el del worker menos `unset_env` (sin shell no es explotable).
  - Si `claude` cambia sus flags, se corrige el manifiesto; si se instala como `.cmd` (npm), los
    argumentos pasan por `cmd.exe` (las órdenes son de la app).
  - Pendiente de prueba manual: el recorrido completo con el `claude` real
    (`dev/pruebas/fase-19-prueba-manual.txt`).

### 20 · Calibración y patrones — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen:**
  - Antes de empezar, `fase/19-lote-segundo-plano` se fusionó en `main` (sin push), a petición del
    usuario; la rama de la 20 sale de ahí.
  - `services/analytics.py` → `get_calibration(since, min_cases=10)`. Reutiliza el CTE `_per_job`
    del embudo («con respuesta» y «entrevista» son los mismos pasos). Sobre las enviadas, da la
    tasa de respuesta y de entrevista con intervalo de Wilson al 95 %, `awaiting` y `low_data` por:
    - tramo de score (< 60, 60-74, 75-84, ≥ 85, sin score);
    - veredicto;
    - fuente;
    - portal;
    - plantilla del CV enviado;
    - carta;
    - referencia;
    - días entre alta y envío.

    Todo medido en el primer envío (detalle en `DATA_MODEL.md` §Calibración).
  - `get_calibration` ↔ `jh stats calibration [--since] [--min-cases]` (4 casos de paridad), con
    salida de texto, y `GET /stats/calibration`. Va en el allow de `.claude/settings.json` porque
    es solo lectura.
  - Skill `revisar-busqueda` (retrospectiva: qué funciona, qué cambiar). Solo tiene `read`,
    `get_calibration` y `get_funnel_stats`, y nunca cambia pesos ni filtros. Acción «Revisar mi
    búsqueda» (solo en terminal).
  - UI: sección «¿Acierta el score?» en Embudo, con aviso de que es orientativa, pestañas por
    desglose, tasa con intervalo (texto y barra), «pocos datos» y el botón del agente. También
    sale con un periodo sin ofertas nuevas pero con envíos.
  - Docs: AGENT_INTERFACE (§Calibración), DATA_MODEL, ARCHITECTURE, `evals/matching/README.md`
    (§Calibración: el cambio lo hace el usuario, con `jh eval matching` antes y después), README,
    RESUMEN_FASES, PENDIENTES y `dev/pruebas/fase-20-prueba-manual.txt`.
  - Tests:
    - `tests/test_calibration.py` (14), con un histórico sintético y cifras exactas: score
      anterior y posterior al envío, veredicto posterior ignorado, carta posterior, días en el
      límite, `since` en Madrid, Wilson y vacío;
    - paridad;
    - rendimiento: 1 000 ofertas con matches, veredicto, carta y CV en ≈ 0,15 s (límite 1 s);
    - 4 de frontend.
- **Decisiones** (aprobadas en el plan):
  - `since` por fecha del primer envío, no de alta.
  - Mínimo de 10 casos para quitar «pocos datos».
  - Score: el último antes del envío o, si no hay, el primero después (lo calcula código).
    Veredicto: solo uno anterior al envío.
  - Sin migraciones: todo sale de `events`, `matches`, `documents` y `document_renders`.
  - Revisión del rol `revisor` aplicada:
    - prueba de rendimiento con datos que ejercitan todas las subconsultas;
    - `awaiting` igual al paso «Con respuesta» del embudo;
    - `LETTER_KIND` en vez del literal;
    - calibración visible con el embudo vacío;
    - umbral de 20 como constante;
    - notas en `DATA_MODEL` (días negativos, cifra de rendimiento).
- **Deuda:**
  - La demo no tiene veredictos, cartas, plantillas en los envíos ni portales: en la demo esas
    pestañas salen con un solo grupo.
  - Los portales se muestran con su clave (`linkedin`), sin nombre bonito.
  - Una plantilla del usuario con id `none` se sumaría a «Sin CV de la app».
  - Pendiente de prueba manual: la retrospectiva con un agente real y datos reales
    (`dev/pruebas/fase-20-prueba-manual.txt`).

### 21 · Ofertas recibidas y salario — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen:**
  - Tabla `received_offers` (migración 0020): una por oferta y solo la escribe el usuario desde la
    ficha. Campos: fijo (anual o mensual), variable (anual), moneda, beneficios, modalidad,
    ubicación, incorporación, fecha límite, notas y `amounts_private` (por defecto `true`).
    Guardarla registra `offer_received` si falta. Cada cambio deja una `note` con los campos
    cambiados, sin valores.
  - `services/received_offers.py`:
    - `compare` (solo la API, `GET /received-offers`): fijo y total anuales, diferencia con
      `private.salary_floor_eur` y con el rango publicado, con `remarks` para lo no comparable;
    - `agent_view`: lo que ve el agente, sin el mínimo y sin importes si son privados.
  - `get_received_offer` ↔ `jh received-offers show` (4 casos de paridad), en el allow de
    `.claude/settings.json` (solo lectura). La acción `preparar-negociacion` del lanzador va solo
    en terminal y necesita `offer_received`.
  - Skill `preparar-negociacion`: argumentos del perfil con su id, qué negociar además del fijo,
    preguntas, un guion con el hueco `[tu cifra]` y revisión del contrato cláusula a cláusula,
    que no es asesoramiento legal. `repasar-entrevista` lo sugiere tras las dudas antes de aceptar.
  - Datos de mercado: `data/documentos/salarios.csv` opcional, con el formato de
    `demo/salarios.example.csv`. Solo los cita el skill; el código no busca salarios.
  - UI:
    - sección «Oferta recibida» en la ficha (formulario, resumen, «Preparar negociación»);
    - tabla «Ofertas recibidas» en Procesos, con las ofertas lado a lado y las diferencias en
      verde o rojo.
  - Docs: POLICIES §4, DATA_MODEL, AGENT_INTERFACE, RESUMEN_FASES, PENDIENTES y
    `dev/pruebas/fase-21-prueba-manual.txt`.
  - Tests:
    - `test_received_offers.py` (22), `test_api_received_offers.py` (2) y el lanzador;
    - **`test_privacy_mcp.py`**: los 175 casos de la paridad con un mínimo y unos importes
      privados centinela, sin que aparezcan en ninguna respuesta. Comprobado que falla si se
      quita la ocultación;
    - 5 de frontend.
- **Decisiones** (aprobadas en el plan):
  - «Importes privados» por oferta, marcado por defecto.
  - El `offer_received` se registra solo.
  - Una oferta recibida por oferta de empleo, sobrescrita al cambiar.
  - Se usa la clave existente `salary_floor_eur`.
  - Comando `jh received-offers` en vez de `jh offers`: en la app, «ofertas» son las de empleo.
  - Revisión del rol `revisor` aplicada:
    - el variable es siempre anual y `period` es solo del fijo;
    - sin fijo no hay total;
    - un rango publicado sin moneda o sin periodo no se compara y lo explica;
    - una extracción con salario mal formado no rompe la tabla;
    - en la CLI, un 0 cuenta como importe;
    - en la UI, `Number.isFinite` en los importes;
    - límite de beneficios y notas documentado en POLICIES §4;
    - tests nuevos.
- **Deuda:**
  - Beneficios y notas son texto libre que el agente ve siempre. Solo hay un aviso en la UI; no
    se detectan cifras al guardar.
  - Dos guardados simultáneos de la primera vez podrían dar un 500 por la restricción única (raro
    en local).
  - La demo no trae ofertas recibidas anotadas.
  - Tras guardar desde `applied`, la oferta pasa a `in_process` (por el `offer_received`), así que
    el botón sale siempre.
  - Pendiente de prueba manual con un agente real (`fase-21-prueba-manual.txt`).


### 22 · LinkedIn por sus endpoints públicos (opcional) — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen:**
  - ADR-033, que matiza la 016 y la 009; `AGENTS.md` (regla 6), POLICIES §8, `FUENTES_OFERTAS.md`,
    `DATA_MODEL.md`, `AGENT_INTERFACE.md` y el skill `buscar-ofertas` actualizados.
  - `services/ingestion/linkedin_public.py`: fuente `linkedin_public` que consulta
    `jobs-guest/jobs/api/seeMoreJobPostings/search` con las búsquedas de la plataforma LinkedIn, sin
    cookies ni redirecciones y con un user-agent honesto. Límites en `policies.yaml` →
    `linkedin_public` (mínimos en el esquema): ≤ 2 páginas, ≥ 10 s entre peticiones, una ejecución
    al día, búsquedas y descripciones con tope. Corte inmediato ante 429/999/401/403/3xx o captcha y
    3 días sin volver a intentarlo.
  - Lo que pasa el filtro previo entra como resumen (`pending_detail`); la descripción por
    `jobPosting/{id}` es un segundo interruptor, también apagado.
  - Tarea `run_linkedin_public` (sin reintentos) con la ingesta diaria y al arrancar el worker;
    API `GET /sources/linkedin-public`, `POST …/settings` y `POST …/run` (con `require_ui`); CLI
    `jh sources linkedin-public status|run`.
  - UI: bloque «Búsqueda pública sin sesión» en la tarjeta de LinkedIn de Plataformas, con su
    interruptor, diálogo de riesgo, «Descargar también la descripción», búsquedas, aviso de
    bloqueo, última ejecución y «Buscar ahora».
  - Tests: 22 de backend (`test_linkedin_public.py`, HTML inventado en
    `fixtures/linkedin_public/`) y 4 nuevos de frontend. Sin migraciones ni dependencias.
- **Decisiones** (aprobadas en el plan):
  - Fuente propia `linkedin_public` (una fila), con las búsquedas sacadas de la plataforma
    LinkedIn: así el embudo por fuente la separa y `save_source` del agente no puede tocarla.
  - El filtro previo se aplica **antes** de guardar (a diferencia del correo): menos volumen.
  - User-agent honesto aunque LinkedIn pueda responder 999: no se disfraza de navegador.
  - Tras un bloqueo, 3 días sin ejecutar (no se apaga sola).
  - Revisión del rol `revisor` aplicada:
    - la ejecución del día se reserva con un `UPDATE` condicionado y un commit antes de salir a la
      red, para que dos ejecuciones simultáneas no lancen dos ráfagas;
    - la descripción no se puede encender sin la búsqueda;
    - comandos en `AGENT_INTERFACE.md`;
    - texto del botón del diálogo de la descripción.
- **Deuda:**
  - **Sin probar contra LinkedIn real:** el formato de `jobs-guest` se ha imitado con HTML inventado
    y no se ha hecho ninguna petición real. Es posible que responda 999 al user-agent honesto
    (`fase-22-prueba-manual.txt`).
  - El cuerpo de la respuesta se descarga entero antes de recortarlo a 2 MB (sin `stream`).
  - `require_ui` no para a un proceso local que falsifique el origen (riesgo residual de la
    ADR-016).
  - `blocked_at` se escribe al final de la ejecución, justo después del corte: si el proceso muere
    en ese instante, el día cuenta igualmente, pero no el periodo de 3 días.
  - Ejecutada por CLI, la ejecución queda con actor `user` aunque la lance un agente.

### 23.1 · Renombrado a CandidatAI — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen:** «Job Hunter» pasa a **CandidatAI** en todo lo vivo: UI y logo «CA», extensión
  («Enviar a CandidatAI», iconos nuevos con `scripts/build_icons.py`), favicon (era el de Vite),
  docs, README en los dos idiomas, skills y roles. Lo técnico también: CLI `cai` y `cai-mcp`,
  servidor MCP `candidatai` (`mcp__candidatai__*`), variables `CAI_*`, paquete `candidatai`,
  `cai.local`, `data-cai-*` y `cai_iso_week`. Repositorio de GitHub renombrado a
  `DiegoPrieto23/candidatai`. ADR-034. Encargos de toda la fase 23 en `dev/prompts/23*.md`.
  2355 tests de backend y los de frontend en verde.
- **Decisiones:**
  - Sin alias `jh` (decisión del usuario): lo de fuera del repositorio se actualiza a mano.
  - Compatibilidades: `JH_*` se leen si falta la `CAI_*` (`AliasChoices`) y `data/jobhunter.db`
    se usa si no hay `candidatai.db`. `cai doctor` («Nombres de antes de CandidatAI») lo avisa con
    los nombres, nunca con los valores. La clave antigua del tema se lee como respaldo.
  - El historial (este registro, `RESUMEN_FASES.md`, encargos anteriores) no se reescribe.
  - Renombrado con reglas ordenadas y revisión de cada coincidencia arriesgada; la revisión del
    rol `revisor` encontró las plantillas integradas sin regenerar (autor del docx) y restos de
    `jh` en el frontend y en un test que, con el patrón antiguo, no comprobaba nada.
- **Deuda:**
  - `uv sync` pendiente con el agente cerrado: hasta entonces no existen los ejecutables `cai`
    y `cai-mcp` (en esta sesión se probó todo con `uv run --no-sync` y llamando a la CLI desde
    Python).
  - `~/.claude/settings.json` del usuario sigue mencionando `jh` y el repositorio `job-search`
    (decidió no tocarlo).
  - Medios del README (banner, capturas, GIF y vídeo) aún con «Job Hunter»: la 23.5.

### 23.2 · Skills y roles en inglés — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen:** los 23 skills pasan a inglés (`process-jobs`, `assess-fit`, `generate-cv`,
  `prepare-interview`, `daily-summary`…) y los roles a `writer`, `verifier`, `classifier`,
  `reviewer` (`extractor` igual). También las tres acciones de la UI que no son skill:
  `add-skills`, `draft-follow-ups`, `offer-questions`. Descripciones, UI y docs siguen en
  español, y cada `description` termina con «Antes se llamaba …» para que el agente los encuentre
  por su nombre de siempre. Migración `0021` que traduce acción, orden y comando de los encargos y
  ejecuciones guardados (con `downgrade`). `sync_agents.py` borra también las carpetas vacías de
  los generados obsoletos.
- **Decisiones:**
  - Los roles se renombran solo donde son identificadores (entre comillas invertidas, rutas,
    «rol X», `Agent(X)`); la prosa y la UI en castellano («el verificador encontró problemas»)
    se quedan.
  - La migración no traduce nombres de fichero (`plan-formacion-<fecha>.md` en `data/`) ni el
    historial de progreso de ejecuciones pasadas (lo encontró la revisión).
- **Deuda:**
  - Esta sesión de desarrollo cargó los subagentes con su nombre antiguo; desde una sesión nueva
    ya aparecen `writer`, `verifier`…

### 23.3 · Barra lateral — 2026-10-12 · Claude Code (Opus 5.5)
- **Resumen:** la fila de 13 enlaces de la cabecera pasa a una barra lateral
  (`components/Sidebar.tsx`) con grupos (Búsqueda, Procesos, Análisis, Configurar), iconos,
  recuentos, plegable a solo iconos (con tooltip y recordado en `localStorage`) y, por debajo de
  1024 px, un cajón que se abre con un botón y se cierra al navegar. «Empresas» y «Plataformas»
  se unen en **Fuentes**, con pestañas (`/fuentes/empresas`, `/fuentes/plataformas`); las rutas
  antiguas redirigen. La cabecera se queda con la fila de recuentos por etapa y «Nueva oferta» en
  una sola línea. Docs y mensajes («Fuentes → Plataformas») al día. 235 tests de frontend.
- **Decisiones:**
  - Sin título de sección en la cabecera (el encargo lo pedía): cada página ya tiene su `h1`.
  - El recuento va en el nombre accesible del enlace («Por revisar (3 por revisar)»); antes se
    leía pegado («Por revisar,3por revisar»).
  - Los títulos de grupo son etiquetas de lista, no encabezados, para no competir con el `h1`.
  - «Bandeja» queda activa también en la ficha de una oferta y en «Nueva oferta».
  - El cajón se cierra con cualquier navegación (también la marca) y al pasar a escritorio.
- **Deuda:**
  - Márgenes de los tests subidos (`testTimeout` 15 s, `asyncUtilTimeout` 4 s): con la suite
    completa en paralelo en Windows algunas páginas tardaban más de 5 s. Provisional: sin medir la
    causa (sospecha: el import de barril de los iconos).
  - Un test de Plataformas fallaba a veces por dos `Date.now()` distintos; corregido.
  - La UI sigue solo en español (punto 9 de «Lo que nos falta» en `docs/COMPARATIVA.md`).

### 23.4 · Instalación fácil — 2026-10-13 · Claude Code (Opus 5.5)
- **Resumen:**
  - **La API sirve la UI compilada** (`app/api/ui.py`): navegación del navegador a una ruta de la
    UI → `index.html`; el resto, la API. La UI compilada llama a su propio origen.
  - **`cai start`** (`services/launcher.py`): migraciones, API y worker como procesos hijos, espera
    a que la API responda y abre el navegador; Ctrl+C o cerrar la ventana lo para todo sin
    huérfanos; `--dev` añade Vite. Logs en `data/logs/start-*.log`.
  - **`install.ps1`**: uv, release (o zip/carpeta local con `-Source`), `%LOCALAPPDATA%\CandidatAI`
    con los datos aparte, entorno, Chromium, base de datos y accesos directos con icono
    (provisional, `frontend/public/candidatai.ico`); `-WhatIf`, `-Uninstall`, `-RemoveData`.
  - **Releases** con `.github/workflows/release.yml` (etiqueta `v*` → `candidatai.zip`).
  - Encargos de la 23.6 (UI bilingüe) y la 23.5 (logo) redactados; orden 23.4 → 23.6 → 23.5.
  - ADR-035. 2380 tests de backend y 235 de frontend. Probado de verdad: `cai start` sobre la
    demo; instalar desde la carpeta del repositorio, actualizar conservando el `.env`, negarse a
    actualizar con la app abierta y desinstalar dejando los datos.
- **Decisiones:**
  - `require_ui` acepta el mismo origen solo en `127.0.0.1`/`localhost`, y
    `TrustedHostMiddleware` (el más externo) rechaza cualquier otro `Host` también en las
    lecturas: contra DNS rebinding.
  - Cada fichero suelto de la UI tiene una ruta fija sin parámetros (con el fichero como
    parámetro por defecto, FastAPI lo habría convertido en `?file=` y permitido leer cualquiera).
  - El puerto se comprueba intentando escuchar y conectar: en Windows conectar a un puerto cerrado
    tarda ~2 s y parecía «ocupado por otro programa».
  - El instalador se ejecuta descargándolo a un fichero: con `irm | iex` no es un script avanzado y
    `-WhatIf` falla (lo encontró la revisión). Solo sustituye o borra carpetas que sean una app de
    CandidatAI, se niega con la raíz o la carpeta de usuario y prepara la versión nueva aparte.
- **Deuda:**
  - El instalador de una línea necesita una release pública: hoy el repositorio es privado y no hay
    ninguna (se instala con `-Source <carpeta>`).
  - El acceso directo y Ctrl+C en una consola real no se han probado aquí (sin consola
    interactiva); queda en `PENDIENTES.md`.
  - El frontend sigue teniendo algún fallo intermitente por carga en la suite completa (importación
    de FunnelPage); por separado y en una segunda pasada, todo en verde.
  - Pendiente de la 23.5: el icono definitivo.

### 23.5a · Logo — 2026-10-13 · Claude Code (Opus 5.5)
- **Resumen:** logo de CandidatAI: **el torso de una persona con un sello de verificado en lugar
  de la cabeza** (candidato y *candid*: verificado, nada inventado), plano, sin degradados ni
  adornos, verde `#0F766E` con la figura en blanco. Elegido por el usuario en varias rondas:
  conceptos (persona verificada, «C» con chispa, lupa con persona), color (verde, tinta, papel) y
  forma final (cabeza en círculo, sello o trazo: ganó el sello). Fuente en
  `docs/brand/` (`mark.svg`, `mark-mono.svg`, `logo.svg`, `logo-dark.svg` y su README con
  colores y usos). `scripts/build_icons.py` rasteriza `mark.svg` con Chromium: iconos de la
  extensión, favicon, `apple-touch-icon` y `.ico` de Windows. La barra lateral (`BrandMark`) y la
  extensión usan el isotipo; el banner del README pasa a fondo plano con el logo.
- **Decisiones:**
  - El logotipo es «Candidat» + «AI» en verde, en peso medio; el texto usa la pila de fuentes del
    sistema (Geist si está), sin convertir a trazados.
  - El banner pierde la cuadrícula y los círculos decorativos: el mismo criterio minimalista.
- **Deuda:** capturas, GIF y vídeo del README siguen con la marca anterior: la 23.5b, tras la 23.6.

### 23.6 · UI en inglés y español — 2026-10-13 · Claude Code (Opus 5.5)
- **Resumen:** toda la UI en español y en inglés con i18next (ADR-036). Textos en
  `frontend/src/locales/{es,en}/` (33 ficheros por idioma, uno por zona), claves tipadas, plurales
  de i18next y fechas y números con `Intl` según el idioma. Selector de idioma (globo, nombre del
  idioma y su bandera en SVG, con menú) junto al del tema en la barra lateral y en el cajón; se recuerda en
  `cai-language` y, si no hay, sigue al navegador. `lib/labels.ts` traduce al leer; los códigos
  del servidor (`error.type`, avisos de render y de candidatura, filtros duros, pasos del embudo,
  grupos de calibración, acciones del agente) se traducen y su mensaje queda como detalle
  (`lib/errors.ts`, `serverText`). Docs: guía en los dos idiomas (sección «Idioma»; la inglesa ya
  cita los nombres en inglés), notas de los README, `COMPARATIVA` (punto 9 hecho) y `AGENTS.md`.
- **Tests:** 250 en verde (15 nuevos): mismas claves y variables en los dos idiomas y ninguna vacía,
  ningún texto en español fuera de `locales/`, ninguna etiqueta de `Trans` vacía en HTML, el
  selector (cambia al momento, se recuerda, `<html lang>`, idioma del navegador) e Inicio, Por
  revisar, la ficha y Procesos en inglés, y `SafeTrans` con un valor malicioso. `tsc`, `pnpm lint` (sin avisos nuevos) y `pnpm build`.
  Comprobación visual de todas las páginas en inglés con la demo.
- **Decisiones:**
  - Al cambiar de idioma se vuelven a montar las páginas (`key` del idioma): más simple y seguro
    que asegurar que cada componente se repinta; se pierde lo escrito a medias en un formulario.
  - En `Trans`, `<link>` no sirve como etiqueta (es un elemento vacío de HTML): se usa `<to>`.
  - De paso, el aviso de oferta cerrada ya no dice «Job Hunter», sino «CandidatAI».
  - Banderas en SVG, no emojis: Windows no pinta los emojis de banderas.
  - A petición del usuario, en Inicio «Nueva oferta» va junto a las acciones de la página y la
    fila de arriba desaparece en escritorio; en el resto de páginas sigue en la cabecera.
  - Revisión (rol `reviewer`): en el diálogo de envío de la candidatura asistida, el nombre del
    botón y el dominio (de la web del formulario) se interpolaban en un `Trans` sin escapar y
    podían colarse como marcado. Ahora van como nodos de React, y los demás `Trans` con datos de
    fuera usan `SafeTrans` (ADR-036).
- **Deuda:** traducir los mensajes del servidor que no traen código (avisos del doctor, motivos del
  prefiltro, resultados de ejecuciones, notas del score); los datos de la demo siguen en español
  (para las capturas en inglés de la 23.5b, valorar una demo en inglés).

### 23.5b · Medios y README — 2026-10-13 · Claude Code (Opus 5.5)
- **Resumen:** medios nuevos del README, por idioma: `docs/img/en/` para `README.md` y
  `docs/img/es/` para `README.es.md` (14 capturas, 3 en oscuro, GIF de triaje, CV y arranque) y
  `docs/video/tour-{en,es}.mp4`. Se retiran los antiguos, con la marca anterior. Diagrama
  `how-it-works-en.svg`. Los scripts de `scripts/readme_media/` toman el idioma y usan nombres en
  inglés; escena nueva `start`, que graba la salida real de `cai start`. Los README pierden la
  sección de comparativa (la tabla de documentación sigue enlazando `COMPARATIVA.md`), ganan la
  barra lateral y el GIF de arranque, y la cifra de ADR, fases y tests al día.
  `scripts/check_links.py` comprueba los enlaces e imágenes relativos de los `.md`.
- **Demo en inglés:** `cai demo seed --lang en` (candidata en Dublín, `demo/en/`); los textos del
  historial, la oferta de riesgo, las plataformas y las fuentes salen del catálogo de cada idioma.
  La demo española trae ahora también sus plataformas (InfoJobs, Tecnoempleo, Indeed y LinkedIn,
  desactivada). Guía para recorrer todas las funciones con la demo:
  `dev/pruebas/guia-prueba-demo.md`.
- **Arreglos encontrados al grabar:**
  - **la demo leía el buzón real**: `cai start` sobre una demo arrancaba el worker con el IMAP de
    `.env` y metía en ella los correos reales. Ahora `imap_configured` es falso en la demo y el
    doctor lo explica (ADR-020, añadido);
  - las notas del score («Similitud semántica desactivada…») salen traducidas en la UI
    (`lib/scoreNotes.ts`, por patrón sobre el texto del servidor);
  - el detector de inyección reconoce también «ignore the previous instructions»;
  - en Plataformas, el selector de acceso muestra solo el nombre y el de prioridad es más ancho.
- **Tests:** 3 de la demo (siembra en inglés, idioma desconocido, nunca el buzón real) y los de
  `scoreNotes`, un caso del patrón de inyección y el doctor en la demo. 2384 tests de backend y 252
  de frontend en verde; ruff, `tsc`, `pnpm lint` (sin avisos nuevos), `pnpm build`,
  `sync_agents.py --check` y `check_links.py` limpios.
- **Decisiones:**
  - Cada README lleva capturas de la demo en su idioma, con la UI en ese idioma.
  - En el GIF de arranque inglés, la salida de `cai start` sale en español: la CLI no está
    traducida (ADR-036).
  - Las miniaturas de las plantillas muestran a la candidata española: son imágenes fijas de
    `templates/`.
  - Revisión (rol `reviewer`), sin nada bloqueante: la nota de error del score se traduce aunque
    traiga saltos de línea, y el doctor explica también en «Respuestas por correo» que la demo no
    usa el IMAP de `.env`.
- **Deuda:** traducir la CLI y los mensajes del servidor sin código; los niveles de las skills en
  la ficha siguen como códigos del perfil (F, C, B) con su nombre en el tooltip; los iconos de los
  portales caen a la inicial cuando no cargan.

### 24.1 · Registro de agentes y diagnóstico — 2026-10-16 · Claude Code (Opus 5.5)
- **Resumen:** manifiesto v2. Cada agente lleva `config` (`generated` o `none`), `info`
  (proveedor, licencia, open-source, instalación por sistema, `detect`, cómo se invoca un skill,
  qué instrucciones lee) y `capabilities` (MCP, subagentes, nivel de aislamiento A/B/C, visión,
  web, navegador, modelos locales; `null` = sin comprobar).
  - Claude Code y Codex: con lo ya comprobado en `AGENTS_COMPAT.md`.
  - Cursor CLI, Copilot CLI, Pi y goose: entran como «solo compatibles vía `AGENTS.md`»
    (`enabled: false`, `config: none`, nivel C), con datos comprobados en sus webs.
- **`services/agent_registry.py`:** único lector del manifiesto en el backend.
  - Pydantic estricto: una clave mal escrita falla nombrando agente y clave.
  - Caché por fecha de modificación.
  - `capabilities.headless` derivada de `launch.headless`.
  - Detección con 5 s de máximo y sin las variables de `unset_env`. Va en caché 5 min, o 30 s si
    no está instalado, con una sola detección a la vez por agente.
  - `agent_launch` y `agent_runner` lo usan sin cambiar su comportamiento: sus tests no se tocan.
- **Comandos y API:**
  - `cai agents list [--json] [--refresh]`;
  - `cai agents doctor`: cuál se usaría hoy y por qué, el segundo plano y qué falta para los
    demás;
  - `GET /agent/agents`: lo mismo que `list --json`;
  - sección «Agentes» en `cai doctor`.
  - Con el manifiesto roto, la UI dice que el manifiesto no es válido, en vez de «ningún agente».
  - `sync_agents.py` valida `config`.
- **En este equipo:** Claude Code 2.1.301, habilitado, con segundo plano. Copilot CLI 1.0.75
  instalado, solo compatible. Codex, Cursor, Pi y goose, no instalados.
- **Tests:** 25 nuevos en `test_agent_registry.py`:
  - clave mal escrita y anidada;
  - valores inválidos y caché por mtime;
  - ejecutable falso que tarda (corte por tiempo) y que lee la clave (no la recibe);
  - caché de la detección;
  - CLI y API iguales;
  - doctor con el manifiesto roto y con `CAI_AGENT`.
  2409 tests de backend en verde, ruff limpio, `sync_agents.py --check` en verde y OpenAPI
  regenerado.
- **Decisiones:** ADR-037 (borrador; lo completan la 24.4 y la 24.5).
  - `install` es un texto por sistema que solo se enseña, nunca se ejecuta.
  - La API no tiene `--refresh`: la UI de la 24.4 decidirá si lo necesita.
  - Revisión (rol `reviewer`), sin nada bloqueante. Se aplicó:
    - el motivo con un manifiesto roto;
    - el aviso en el log una vez por mensaje;
    - una sola detección a la vez;
    - TTL corto para los no instalados;
    - `clean_env` compartido con el runner;
    - `load()` de solo lectura;
    - errores sin rutas absolutas;
    - la sección en `AGENT_INTERFACE.md`;
    - tests de paridad CLI/API y de `CAI_AGENT` desconocido.
- **Deuda:**
  - `shutil.which` en Windows también mira la carpeta actual; habría que pasarle el `PATH`
    explícito en los tres sitios a la vez (registro, `agent_launch` y los tests que lo sustituyen).
  - El registro importa `_kill_tree` de `agent_runner` dentro de la función, por el ciclo de
    imports. Conviene llevarlo a un módulo de procesos común.
  - Falta un test con un `.cmd` real de Windows en una ruta con espacios.

### 24.2 · Esquemas y errores para cualquier modelo — 2026-10-16 · Claude Code (Opus 5.5)
- **Resumen:** lo que necesita un modelo pequeño para acertar sin MCP.
  - **Esquemas:** `get_schema` / `cai schema [NOMBRE] [--example true] --json`, con 17 esquemas
    (`agent_interface/schemas.py`). Cada uno es exactamente lo que va en `--file`: el modelo del
    campo o un objeto con las claves de `file_keys`. Ejemplos mínimos en `demo/schemas/`, con los
    ids del perfil demo; el del CV pasa las comprobaciones del perfil.
  - **Errores accionables** (formato aditivo, decidido con el usuario): se conservan `field`,
    `received` y `reason`, y se añaden `expected` y `hint`.
    - `field` es siempre un path con puntos, también en las comprobaciones del CV, la carta y
      las respuestas (con `content.` delante desde la interfaz para agentes; sin él en la API).
    - Pistas: campo obligatorio, campo inexistente (el más parecido), enumeración casi bien
      escrita, `language` con el nombre del idioma, texto vacío, skill que no está en el perfil
      (el nombre tal cual, sin traducir) y evidencia o id inexistente (los 5 más parecidos).
    - `scrub`: ningún error devuelve más de 80 caracteres seguidos de la entrada.
  - **`--file` tolerante:** JSON en un bloque de código Markdown, o con texto antes o después.
  - **Roles y skills:** nombran su `cai schema …`. Regla común: corregir solo los `field` del
    error y reenviar, como mucho dos veces.
  - **Tokens:** `cai agents doctor --tokens`.
- **Tokens medidos** (4 caracteres por token):
  - `AGENTS.md`, ~2 200. Una valoración (AGENTS.md + `assess-fit`), ~2 900. Un CV (AGENTS.md +
    `generate-cv` + `writer` + `verifier`), ~6 200, sin contar `POLICIES.md`. career-ops: ~26 000.
  - El skill más largo es `import-cv-template`, con ~2 500. Ninguno pasa de 6 000: sin deuda.
- **Tests:**
  - 40 en `test_schemas_errors.py`:
    - catálogo completo frente al registro, cada ejemplo valida;
    - los casos de la matriz: skill traducida, evidencia inexistente, `language`;
    - campos que faltan o mal escritos;
    - el límite de 80 caracteres, también en las pistas, las claves de `--file` y las copias
      parciales;
    - `--file` tolerante, y un JSON truncado que no se acepta;
    - la salida de texto de la CLI y los tokens.
  - 4 casos de paridad de `get_schema`.
  - Al día: los tests de paths con puntos y el detalle de error de la paridad.
  - 2457 tests de backend en verde (los dos de render real con LibreOffice, repetidos aparte
    tras agotar los 60 s con la máquina cargada) y 252 de frontend, `tsc`, ruff y
    `sync_agents.py --check` limpios.
- **Decisiones:**
  - `get_schema` va en el allow de `.claude/settings.json`, pero en ningún techo de segundo plano
    (ADR-032 sin cambios).
  - «Sección en otro idioma»: sin validaciones nuevas (fuera de alcance), la pista sale del
    `language` mal puesto.
  - Revisión (rol `reviewer`), sin nada bloqueante. Se aplicó:
    - `lenient_json` solo acepta el primer objeto si no hay otro detrás;
    - recorte en las claves desconocidas de `--file` y en `unknown_tool`;
    - `esperado:` y `pista:` en la salida de texto;
    - el mensaje de los errores de contenido se rehace desde los paths;
    - test de que las pistas no citan la entrada;
    - una sola regla de reintento en el `extractor`.
- **Deuda:**
  - `scrub` no reconoce un texto que un servicio normalice antes de citarlo.
  - La pista de la skill traducida solo sugiere nombres parecidos por escritura (`difflib`), no
    traducciones.
  - Medir en la 24.6 si los modelos pequeños aciertan al segundo intento.

### 24.3 · Agentes nuevos — 2026-10-16 · Claude Code (Opus 5.5)
- **Resumen:** configuración generada para OpenCode, Qwen Code y Antigravity CLI. Codex con modelos
  locales. Gemini CLI fuera.
  - **Comprobado con su binario** (vía `npx`, sin instalar): OpenCode 1.19.3, Qwen Code 0.25.2 y
    codex-cli 0.163.0. Antigravity, solo con su documentación (no está en npm). Versiones y fechas
    en `docs/AGENTS_COMPAT.md`.
  - **OpenCode:**
    - `opencode.json` con el MCP local y `permission` (`tools` está obsoleto desde la 1.1.1): en
      la sesión principal, `candidatai_*` pide permiso y las de `policy.auto_allow` van sin
      preguntar;
    - `.opencode/agents/<rol>.md` en modo subagente, con `"*": "deny"` y solo sus herramientas.
      `opencode debug agent extractor` confirma que solo tiene `get_job` y `save_extraction`;
    - skills: los lee de `.agents/skills` y `.claude/skills` sin duplicar (se queda con una copia;
      `debug skill`);
    - se lanza con `opencode --prompt`.
  - **Qwen Code:**
    - `.qwen/settings.json` con el MCP, `context.fileName: AGENTS.md`, los permisos de `policy` y
      `"$version": 4`. Sin la versión, Qwen reescribe el fichero al abrirlo (lo vimos con
      `qwen mcp list`);
    - copia de los skills en `.qwen/skills/`, porque solo lee esa carpeta (decisión del usuario: se
      invocan con `/skill`);
    - subagentes con lista `tools` exclusiva;
    - se lanza con `qwen -i`.
  - **Antigravity:**
    - `.agents/mcp_config.json`, el único fichero generado dentro de `.agents/`;
    - sin subagentes (nivel C) y sin `launch`, porque no está documentado cómo abrirlo con una
      orden.
  - **Gemini CLI:** deshabilitado con `info.note`. `GEMINI.md`, vacío a propósito. Fuera del README
    (en los dos idiomas), de `AGENTS.md` y de `AGENTS_COMPAT.md`.
  - **Modelos:**
    - `models` pasa a ser un objeto estricto (`fast`, `capable`, `flag`, `presets`);
    - `AgentSpec.model_args()` aplica la `flag` o un preset. Codex trae el preset `local`
      (`--oss -m gpt-oss:20b`);
    - `cai agents list --json` y `GET /agent/agents` dicen qué admite cada agente (`models`).
  - **`policy`** (nueva en el manifiesto): `auto_allow`, `deny_read` y `deny_edit`. La traduce cada
    emisor. `--check` falla si `.claude/settings.json` no dice lo mismo.
- **Tests:**
  - 15 nuevos en `test_sync_agents.py`:
    - salida determinista;
    - el extractor con sus dos herramientas en los tres agentes;
    - ningún rol con terminal que no declare;
    - permisos de la sesión principal de OpenCode y de Qwen;
    - Antigravity;
    - `GEMINI.md`;
    - herramienta lógica desconocida;
    - `settings.json` frente a `policy`.
  - 3 nuevos en `test_agent_registry.py` (modelos, presets, orden con modelo); los suyos, al día
    con los agentes nuevos y la nota.
  - 2475 tests de backend en verde, ruff limpio, `sync_agents.py --check` en verde, OpenAPI regenerado
    y `tsc` limpio.
- **Prueba de aislamiento con modelo:** no se pudo hacer.
  - Los modelos gratuitos de OpenCode Zen rechazan cualquier agente con instrucciones propias
    («free tier can only be used from within OpenCode»), también los subagentes. Probado con dos
    modelos, sobre una demo aparte, ya borrada.
  - OpenCode y Qwen quedan en nivel B hasta la prueba manual (`dev/pruebas/fase-24.3-prueba-manual.txt`)
    con un modelo local o una clave.
- **Decisiones:** ADR-037 ampliado (policy, roles acotados, models, Gemini). ADR-010 y ADR-011, con
  una nota.
  - Revisión (rol `reviewer`), sin nada bloqueante. Se aplicó:
    - el `reviewer` va sin terminal en Qwen (`git_read: []`): `run_shell_command(git diff)` no
      está comprobado y, si no acotara, daría la terminal entera;
    - la prueba manual comprueba que un subagente de Qwen no lee `.env`;
    - `DESARROLLO_POR_FASES.md` al día;
    - `note` documentada como «no recomendado».
- **Deuda:**
  - OpenCode también carga la copia de `.claude/skills` (con el frontmatter de Claude), que tapa la
    de `.agents/skills`. Es inofensivo: el cuerpo es el mismo y solo sale un aviso en el log.
  - Los `deny_read` de OpenCode son rutas relativas: falta comprobar que encajan con las rutas
    absolutas de Windows. El `.env` ya lo cubre su regla por defecto (`*.env: ask`).
  - Nombres de las herramientas MCP en Qwen (`mcp__candidatai__…`) y en los subagentes de
    Antigravity, sin probar con un modelo.
  - `launch` de Antigravity, pendiente de su `--help`.

### 24.4 · Elegir y cambiar de agente — 2026-10-16 · Claude Code (Opus 5.5)
- **Resumen:** el agente y el modelo se eligen desde la UI, globalmente o por acción.
  - **Preferencias en la base de datos** (`agent_preferences`, migración 0022): agente por
    defecto, modelo o preset por agente y agente (y modelo) por acción. `agent_runs` guarda el
    modelo y el preset.
  - **`services/agent_prefs.py`**, el único sitio con la precedencia: botón > acción > por defecto
    > `CAI_AGENT` > el primero habilitado e instalado, con el motivo (código y texto).
  - **Comprobaciones:** capacidades del registro (`search-jobs` → navegador; `research-company` y
    `training-plan` → web; `import-cv-template` → visión, aún sin botón). `false` bloquea, `null`
    avisa. Nivel C con contenido no confiable: aviso en terminal, nunca en segundo plano. Un
    agente preferido sin instalar no se cambia por otro.
  - **Modelo:** texto libre validado sin red (`MODEL_RE` y `models.pattern`, nuevo en el
    manifiesto para OpenCode); va con `models.flag` o el preset detrás del programa, en terminal y
    en segundo plano.
  - **Auditoría:** `CAI_CLIENT_NAME=<agente>` en la terminal y en el runner.
  - **`agent_actions.py`:** el catálogo de acciones sale de `agent_launch` (que lo reexporta) para
    que `agent_prefs` no tenga un import circular.
  - **API y CLI:** `GET /agent` con el agente efectivo y las alternativas de cada acción;
    `GET /agent/agents` y `cai agents list --json` con `launchable`, `preferences` y `effective`;
    `PUT /agent/preferences`; `agent`, `model` y `preset` en `POST /agent/launch` y
    `/agent/runs`. Los encargos no eligen agente. El doctor tiene en cuenta las preferencias.
  - **UI:** sección «Agentes» en la página «Agente» (tarjetas con versión o instalación para
    copiar, insignias, modelo o preset y qué modelo usan los subagentes), selector «Agente por
    defecto», tabla «Por acción» con el efectivo y su motivo, «con Claude Code ▾» y «Abrir con…»
    en cada botón, y agente y modelo en cada ejecución. Textos en `locales/` (es/en, `agents.json`
    nuevo).
- **Tests:** 23 en `test_agent_prefs.py` (precedencia, modelo por nivel, no instalado,
  `CAI_AGENT`, capacidades, nivel C, formato del modelo, bandera de cada agente, guardar,
  extremo a extremo por la API en terminal y en segundo plano, `CAI_AGENT` sin preferencias,
  errores); `CAI_CLIENT_NAME` en el runner y en PowerShell; 10 de Vitest nuevos (sección,
  selector, modelo, tabla, error, desplegable, capacidad, aviso y la lista de ejecuciones).
  2498 tests de backend en verde (los 2 de `test_cli_db.py`, al día con la 0022 y repetidos aparte), 262 de frontend, `tsc`, ruff y `sync_agents.py --check` limpios.
- **Decisiones:** ADR-037 ampliado (preferencias, precedencia, comprobaciones, modelo,
  auditoría). Con el usuario: capacidad `null` = aviso; agente preferido sin instalar = bloquea
  sin cambiar; `import-cv-template` sin botón por ahora.
  - Revisión (rol `reviewer`), sin nada bloqueante. Se aplicó:
    - por qué `assess-fit` y `generate-cv` no cuentan como contenido no confiable (sin
      `get_job`), en el código y en el ADR;
    - «Abrir en terminal» avisa si el agente que la ejecutó ya no se puede usar;
    - controles bloqueados mientras se guarda (el `PUT` sustituye todo);
    - el preset de una acción deshabilita su modelo;
    - `re.ASCII` en `MODEL_RE` y el docstring de `agent_launch`.
- **Deuda:**
  - La UI deduce el sistema por `navigator.userAgent` para la orden de instalación; mejor que lo
    diga el backend.
  - `GET /agent` resuelve acciones × agentes en cada petición (barato con la caché de `which`;
    medir si crecen los agentes).
  - El `pattern` de OpenCode, sin probar con `opencode models`.
  - Con otro idioma, los motivos detallados del servidor se resumen con un texto genérico por
    código.
  - `RESUMEN_FASES.md` se pone al día al cerrar la fase 24 entera.

### 24.5 · Segundo plano con varios agentes — 2026-10-16 · Claude Code (Opus 5.5)
- **Resumen:** «En segundo plano» también con OpenCode, sin rebajar el techo de herramientas.
  - **`launch.headless.ceiling`:** `args` (Claude Code, el techo en la orden, como antes) o
    `config`: una configuración propia de cada ejecución. `HeadlessSpec.complete` exige una forma
    de denegar el resto y rechaza banderas que lo aprueban todo (`--auto`, `--yolo`…). `{model}`
    en la orden marca dónde va el modelo.
  - **`services/agent_run_config.py` (nuevo):** escribe en `data/tmp/agent-runs/<id>/` un agente
    `cai-run` con `"*": "deny"` y, detrás, solo las MCP de la acción, su skill y sus roles. El
    runner se la pasa en `OPENCODE_CONFIG_CONTENT`, quita `OPENCODE_CONFIG`,
    `OPENCODE_CONFIG_DIR` y `OPENCODE_PERMISSION` (`clear_env`) y la borra en un `finally`. Si
    queda alguna de un worker caído, la borra `recover_interrupted`.
  - **`Action.roles`:** con techo por configuración, un rol solo se lanza si sus herramientas caben
    en las de la acción. `generate-cv` queda sin segundo plano con OpenCode (`writer` y
    `verifier` leen ficheros).
  - **`agent_runs.run_config`** (migración 0023): cómo se limitó cada ejecución. El runner no
    relee el manifiesto.
  - **Lector `opencode-json`** en `agent_output.py`: pasos, herramientas (sin entradas ni salidas),
    subagentes, denegaciones, errores, resultado y uso (tokens, coste, turnos). Fixtures grabadas
    de OpenCode 1.19.3 sobre una demo aparte.
  - **Manifiesto:** `headless` y `resume` de OpenCode
    (`opencode run --format json --pure --agent cai-run`).
  - **API y UI:** `BackgroundInfo.suggested`/`suggested_name` en `GET /agent`. El desplegable
    ofrece «En segundo plano con X» si el agente de la acción no puede. La tarjeta de cada
    ejecución enseña el uso. Textos en es/en.
  - **Cola:** sin cambios de lógica; los tests cubren ejecuciones de agentes distintos y la
    recuperación tras reiniciar.
- **Comprobado con OpenCode 1.19.3** (vía `npx`, en `AGENTS_COMPAT.md`):
  - `debug agent cai-run`: las reglas de `cai-run` van detrás de las de `opencode.json`, sin bash,
    read, edit ni web;
  - `--tool`: bash y webfetch, deshabilitados; un skill ajeno y el subagente `writer`, denegados;
  - el `extractor` sigue acotado con la configuración de la ejecución cargada;
  - sin `--auto`, lo que queda en `ask` se rechaza solo y la ejecución se para.
  - **Sin comprobar con un modelo:** los gratuitos de Zen rechazan agentes propios. Va en la
    prueba manual.
- **Codex 0.163.0 y Qwen Code 0.25.2, reevaluados, sin segundo plano:**
  - Codex solo deja apagar herramientas (una lista negra) y sin terminal no lee los skills;
  - Qwen tiene lista blanca, pero no hay forma de comprobarla sin un modelo.
- **Tests:**
  - 36 en `test_agent_run_config.py`:
    - la configuración solo enciende lo de la acción;
    - los roles caben en su acción y coinciden con los de cada `SKILL.md`;
    - `generate-cv` bloqueado con OpenCode;
    - validación de `headless` y `{model}`;
    - el runner con el OpenCode falso: progreso, uso, entorno limpio;
    - la configuración se borra al cancelar, fallar, agotar el tiempo, con una excepción, al parar
      el worker y al recuperar;
    - una configuración que no se puede escribir no lanza;
    - denegación, preguntas, cola con dos agentes y recuperación;
    - el lector sobre las salidas grabadas;
    - la sugerencia en la API.
  - El agente falso imita también `opencode run --format json`.
  - 2 de Vitest nuevos: «En segundo plano con Claude Code» y la línea de uso.
  - 2534 tests de backend en verde (los 2 de `test_cli_db.py`, al día con la 0023 y repetidos aparte). 264 de frontend, `tsc`, ruff y `sync_agents.py --check` limpios.
- **Decisiones:** ADR-037 ampliado (criterio, dos techos, roles, `run_config`, Codex y Qwen) y nota
  en la ADR-032. Con el usuario: sin modelo de pago ni local en esta sesión (la ejecución completa
  queda en la prueba manual); Qwen sin segundo plano hasta poder comprobarlo.
  - Revisión (rol `reviewer`), sin nada bloqueante. Se aplicó:
    - `clear_env` para las variables de OpenCode;
    - rechazar banderas que lo aprueban todo;
    - test de roles frente a los skills;
    - tests de limpieza al parar el worker y de carpetas huérfanas;
    - mensaje al usuario sin nombre de agente;
    - el shim `.cmd`, en la prueba manual.
- **Deuda:**
  - OpenCode en segundo plano, sin probar con un modelo (`dev/pruebas/fase-24.5-prueba-manual.txt`).
  - Si OpenCode se instala con npm, el worker lo lanza por `opencode.cmd` (cmd.exe). La orden la
    compone la app (sin texto de ofertas), pero «» y acentos sin probar por esa vía.
  - `generate-cv` con OpenCode, posible si `read` de `writer`/`verifier` se acota a `docs/` en la
    configuración de la ejecución.
  - El motivo «un rol no cabe» usa `blocked_code` `no_headless`; con otro idioma se ve el texto del
    servidor.
  - `agent_runs.start` devuelve una ejecución activa de la misma acción aunque sea de otro agente.
  - Con `value: content`, `config.json` también se escribe en disco (para auditar y probar), aunque
    se pasa por el entorno.
  - Qwen Code: lector `stream-json` y `headless` en la 24.6, con modelos locales.

### 24.6 · Modelos gratuitos, niveles de gasto y matriz — 2026-10-16 · Claude Code (Opus 5.5)
- **Estado:** ✅ cerrada el 2026-10-22, con el criterio de cierre cambiado (decisión del usuario).
  El encargo pedía la matriz con al menos un agente open-source con un modelo local. Se intentó con
  OpenCode y Ollama, y en el equipo de pruebas (16 GB de RAM, sin gráfica dedicada) no es viable:
  `gpt-oss:20b` no cabe y `qwen3:8b` tarda 13-25 minutos en la primera respuesta (medidas en
  `docs/MODELOS_GRATIS.md`; el resultado de `gpt-oss`, en `evals/compat/results/`). La 24.6 se
  cierra con lo que el usuario quería comprobar, que la app funciona con agentes que no son Claude
  Code. La pasada con un modelo local queda en `dev/pruebas/PENDIENTES.md`.
- **Matriz real (2026-10-22, `evals/compat/REPORT.md` y `docs/AGENTS_COMPAT.md`):**
  - Claude Code con MCP, en segundo plano: 53/55 campos, 5/5 valoraciones, 5/5 CVs que pasan
    `eval cv`, 8,5 min;
  - Codex (ChatGPT) con una oferta (`--cases 1`): 11/11 campos, 1/1 valoración y 1/1 CV;
  - Antigravity CLI: 54/55 campos y 5/5 valoraciones; el CV se cortó por el cupo semanal gratuito;
  - OpenCode con Ollama: no viable en ese equipo; con OpenRouter gratis, cortado por su cupo diario
    (50 peticiones).
- **Cierre (2026-10-22):**
  - `cai eval compat --cases N`: pasada corta con las N primeras ofertas, con su demo y su
    resultado, para no agotar un cupo gratuito;
  - pasos manuales en lenguaje natural para los agentes sin sintaxis de skills;
  - Codex: `pass_env` del manifiesto → `env_vars` (Codex solo pasa una lista blanca del entorno y
    la demo abría `data/`), y `approval_mode = "approve"` para las herramientas de
    `policy.auto_allow`;
  - Antigravity: `/skill` y subagentes heredados (sigue en nivel C);
  - `docs/MODELOS_GRATIS.md`: medidas en un portátil sin gráfica, cómo ahorrar memoria en Ollama y
    OpenCode con OpenRouter.
- **Resumen:**
  - **Guía `docs/MODELOS_GRATIS.md`:**
    - tres vías (local, nube gratis y suscripción) y qué sale de tu equipo en cada una;
    - Ollama en Windows con `OLLAMA_CONTEXT_LENGTH`;
    - modelos por memoria, con etiquetas y tamaños comprobados hoy en ollama.com (`qwen3:8b`,
      `gpt-oss:20b`, `qwen3:14b`, `devstral:24b`, `qwen3-coder:30b`) y el aviso de los de ~8B;
    - la configuración personal de cada agente, fuera del repo;
    - `unset_env`, niveles de gasto y `cai eval compat`.
    Resumen en `GUIA.md` y `GUIDE.md`.
  - **Diagnóstico de Ollama** (`services/local_models.py`):
    - solo `GET /api/version`, `GET /api/tags` y `POST /api/show`, con una lista blanca en la
      llamada y en un `event_hook`;
    - solo direcciones de este equipo (`CAI_OLLAMA_URL`);
    - contexto por `num_ctx`, `OLLAMA_CONTEXT_LENGTH` o el valor por defecto (4 096), limitado al
      máximo del modelo;
    - avisos de contexto bajo (< 32 768), de modelo pequeño (≤ ~8B, umbral 9B) elegido para
      `generate-cv` y de un Ollama sin modelos;
    - superficie: `cai agents doctor`, `GET /agent/local-models` y la tarjeta de los agentes con
      modelos locales.
  - **Niveles de gasto** (`services/spend_tiers.py`):
    - «Económico», «Equilibrado» y «Máximo» para `process-jobs`, `assess-fit`, `review-replies` y
      `generate-cv`, en `agent_preferences` (`scope` `tier` y `tier_undo`), sin migración;
    - propuesta desde el manifiesto y lo instalado, sin nombres de modelos en el código;
    - aplicar copia antes las preferencias por acción y «Deshacer» las devuelve;
    - API `GET /agent/tiers`, `PUT /agent/tiers/{nivel}`, `POST …/reset`, `…/apply` y
      `/agent/tiers/undo`, todas las de escritura con `require_ui`;
    - UI «Niveles de gasto» en la página «Agente».
  - **`cai eval compat`** (`services/evals/compat.py`):
    - demo propia, con el segundo plano (`agent_runs` y `agent_runner.run_next`, en el mismo
      proceso);
    - aprueba y marca las obligatorias que faltan solo en la demo;
    - mide 11 campos de la extracción, valoraciones, `eval cv`, tiempo, turnos y tokens;
    - pasos manuales con `--approve` y `--import` para los agentes sin segundo plano;
    - guarda `evals/compat/results/` y genera `evals/compat/REPORT.md`, que de momento está vacío.
    El lector de Claude Code guarda ahora los tokens del resultado.
  - **Docs:**
    - README (es/en): tabla «Agentes compatibles» con licencia, gratis, en local y estado; se
      mantiene el badge;
    - `AGENTS_COMPAT.md`: matriz con una columna por agente y modelo, con insignias, y sección de
      modelos locales;
    - `COMPARATIVA.md`, `AGENT_INTERFACE.md`, `evals/README.md`, `RESUMEN_FASES.md` (fase 24
      entera), `PENDIENTES.md` y `dev/pruebas/fase-24.6-matriz.md`.
- **Tests:**
  - 20 en `test_local_models.py`: modelos y contexto, solo metadatos, 7 rutas de inferencia
    rechazadas en la llamada y en el hook, un test que busca rutas de inferencia en el código,
    variable de entorno, tope del modelo, modelo pequeño por nombre, preset y `:latest`, Ollama
    caído, fuera del equipo, sin modelos, API y doctor;
  - 12 en `test_spend_tiers.py`: propuesta, preset `local`, sin agente local, aplicar y deshacer,
    deshacer sin preferencias, guardar preferencias borra la copia, «Económico» exige el modelo
    local, editar y volver, validación y `require_ui`;
  - 10 en `test_eval_compat.py`: flujo completo con un agente falso (54/55, resultado e informe),
    paso manual e `--import`, primer paso manual, CLI, el runner de verdad con el proceso falso
    (que recibe `CAI_DATA_DIR` de la demo), errores, normalización y nombres;
  - 5 de Vitest nuevos (niveles, deshacer, editar, Ollama, Ollama caído).
  - 2574 tests de backend en verde, 269 de frontend; `tsc`, ruff y `sync_agents.py --check` limpios; OpenAPI regenerado.
- **Decisiones:** ADR-037 cerrado salvo la decisión sobre el ADR-001, que espera a la matriz. Nota
  en el ADR-001: leer metadatos de un servidor local no es llamar a un LLM.
  - Revisión (rol `reviewer`), sin nada bloqueante. Se aplicó:
    - «Económico» no se aplica sin modelo local (API y botón);
    - guardar preferencias a mano borra la copia para deshacer;
    - errores de la demo y del manifiesto como error de la CLI;
    - `--approve --json`;
    - test de que el agente recibe la carpeta de la demo;
    - texto de privacidad en segundo plano;
    - recorte de los metadatos;
    - nota de tokens en el informe y «Pendiente» en la ADR-037.
- **Deuda:**
  - Sin probar con un modelo local (no viable en el equipo de pruebas) ni la matriz entera con
    Codex (solo con una oferta).
  - Qwen Code sigue sin segundo plano y sin lector `stream-json`: sin un modelo no se puede
    comprobar el techo.
  - El diagnóstico solo conoce Ollama, no LM Studio.
  - El contexto real del servidor no se ve por los endpoints de metadatos: se lee
    `OLLAMA_CONTEXT_LENGTH` de este proceso (si la cambias, reinicia la app).
  - «Deshacer» guarda un solo nivel.
  - La propuesta de «Económico» con OpenCode no trae modelo (no hay preset `local` en el manifiesto).
  - Los tokens de la matriz no cuentan la caché.

### 25.1 · Conectores de ATS y portales con API — 2026-10-16 · Claude Code (Opus 5.5)
- **Hecho:**
  - cinco ATS nuevos con su conector (`services/ingestion/`):
    - **Personio**: feed XML oficial; la descripción solo viene en el idioma pedido, así que se
      prueba `es` y luego `en`, o el `language` de la fuente;
    - **Teamtailor**: RSS paginado con `per_page` y `offset`, sin repetir si el feed no pagina;
    - **Workable**: widget documentado, más el detalle por el JSON de su página de empleo;
    - **SmartRecruiters**: Posting API paginada, con el detalle solo de lo que pasa el filtro;
    - **Recruitee**: Careers Site API;
  - dos portales sin claves:
    - **Manfred**: filtra por el título, porque la API no busca; nunca guarda los datos de su
      «scout»;
    - **freehire.me**: por título, país y remoto, con la URL base cambiable con
      `CAI_FREEHIRE_BASE_URL`;
  - `base.py`: `get_xml` con lxml sin entidades ni red (test de XXE) y `RawJob.detail_url`;
  - `cai sources discover` prueba también los cinco ATS:
    - Workable y SmartRecruiters confirman el slug por el nombre de la empresa;
    - en SmartRecruiters, una lista vacía cuenta como «no encontrado»;
  - CLI: `--language` (Personio), `--lang` (Manfred) y `--country` y `--remote-only` (freehire);
    `SourceInput` rechaza las opciones de otro tipo;
  - UI «Empresas objetivo»: los tipos nuevos con su ejemplo de slug, el enlace «Cómo encontrarlo»
    y los campos propios. Textos en es y en;
  - Docs:
    - `FUENTES_OFERTAS.md`: tabla de fuentes con endpoint y cobertura, y «Cómo encontrar el slug»;
    - `COMPARATIVA.md`, `AGENT_INTERFACE.md`, `DATA_MODEL.md`, README y guía en los dos idiomas;
    - nota de la 25.1 en la ADR-016.
- **Comprobado en vivo** (2026-10-16), contra las APIs reales, con un script fuera de los tests:
  - los siete conectores devuelven ofertas con texto completo;
  - un slug inexistente da 404 con su pista, salvo en SmartRecruiters (lista vacía y aviso
    `empty`);
  - los fixtures copian la forma de esas respuestas con contenido inventado (Acme Datos).
- **Tests:**
  - 22 en `test_connectors_ats.py`: listado, detalle, oferta mal formada como `Issue`, 404,
    paginación, idioma de Personio, XXE, feed que no pagina, Manfred en inglés y URL base de
    freehire;
  - extremo a extremo con Personio y SmartRecruiters (demo), validación de opciones,
    `discover` de cada tipo nuevo y en texto, y CLI;
  - 2 de Vitest.
  - 2603 tests de backend y 271 de frontend en verde; `tsc`, ruff y `sync_agents.py --check` limpios; OpenAPI regenerado.
- **Decisiones (con el usuario):**
  - detalle de Workable y API de Manfred: JSON público sin documentar, aceptado (nota en la
    ADR-016);
  - rama `fase/25-fuentes-perfil-calidad` desde `main`, que ya incluye la 24;
  - los ATS nuevos no tienen comprobación «¿sigue abierta?» por API: van por su página;
  - el rellenado de candidaturas de estos ATS no entra: siguen como «genérico».
- **Revisión** (rol `reviewer`). Se aplicó:
  - el bloqueante: `discover` en texto fallaba con un ATS nuevo;
  - Teamtailor sin duplicados si el feed no pagina;
  - el salario del listado de Manfred se conserva y sus encabezados siguen el idioma;
  - escapado del encabezado HTML de Personio;
  - confirmación por nombre en SmartRecruiters;
  - rechazo de opciones de otro tipo;
  - el enlace de ayuda en inglés avisa de que la guía está en español.
- **Deuda:**
  - Manfred solo da `updatedAt`: una oferta editada parece más reciente;
  - algunos conectores añaden encabezados en español al texto (documentado);
  - el enlace «Cómo encontrarlo» apunta a `main` en GitHub: hasta fusionar, el ancla no existe;
  - `discover` tarda más (hasta 8 ATS × 3 slugs por empresa);
  - `CAI_FREEHIRE_BASE_URL` falta en `.env.example`, que el agente no puede editar (en
    `PENDIENTES.md`);
  - un test de Vitest falló una vez con la máquina cargada y pasó en las dos repeticiones.

### 25.2 · Skill `expand` — 2026-10-16 · Claude Code (Opus 5.5)
- **Hecho:**
  - skill `expand` (`.agents/skills/expand/SKILL.md`, generado para Claude Code y Qwen Code):
    - lee los enlaces públicos del perfil o los de los argumentos (GitHub, portfolio, Kaggle,
      Scholar, verificación de certificaciones);
    - propone proyectos, skills sin nivel, logros con los números tal cual y con fecha, y
      certificaciones, cada uno con su URL y fecha de consulta;
    - no escribe nada sin OK explícito; luego `validate`, `import` y `diff`;
    - lo leído es dato (§6); ni LinkedIn ni login; sin token de GitHub si hay límite;
  - esquema del perfil: `source` opcional (URL http/https, sin espacios ni credenciales, guardada
    tal cual) en `Project`, `Achievement`, `Certification` y los items de `extra_sections`. Vacío
    no se vuelca (`exclude_if`): mismo hash, sin versión nueva ni recálculo. `schema_version` 1;
    `pydantic>=2.12`;
  - demo: `source` en el proyecto y la certificación de `demo/profile.example.yaml`;
  - acción `expand` (solo terminal), requiere `web` y está en `UNTRUSTED`; manifiesto con
    `allowed-tools: [read, web, cai_profile_cli]`;
  - UI: «Ampliar perfil desde mis enlaces» en «Mi perfil», con su explicación, en es y en;
  - docs: POLICIES §1.7 (y §1.6 ajustado), nota de la 25.2 en la ADR-025, `AGENT_INTERFACE.md`,
    `AGENTS_COMPAT.md`, `COMPARATIVA.md`, README y guía en los dos idiomas, prueba manual
    `dev/pruebas/fase-25.2-prueba-manual.txt` y `PENDIENTES.md`.
- **Tests:**
  - `validate` acepta `source` en las cuatro clases y rechaza una URL sin esquema, con espacios,
    con credenciales o `mailto:`;
  - un `source` vacío no cambia el hash ni se guarda; uno relleno crea versión;
  - `expand` bloqueada sin `web` y con aviso en nivel C;
  - Vitest: el botón lanza `expand`, se deshabilita sin web y no ofrece segundo plano.
  - 2605 tests de backend y 272 de frontend en verde; `tsc`, ruff y `sync_agents.py --check`
    limpios; OpenAPI regenerado. Una primera pasada de Vitest dio dos timeouts (AppShell y Embudo)
    con el backend corriendo a la vez; repetida sola, en verde.
- **Decisiones (con el usuario):**
  - una skill sin nivel va a `basic_skills` o no se añade (`Skill.level` sigue obligatorio);
  - los números de un proyecto personal van en su `text` con fecha; publicaciones, en
    `extra_sections`; un `achievement` solo si es de una experiencia.
- **Revisión** (rol `reviewer`), sin bloqueantes. Se aplicó: `pydantic>=2.12`, rechazo de URLs con
  credenciales, casos malos de `achievements` y `extra_sections` en el test, y qué hacer con el
  límite de la API de GitHub.
- **Deuda:**
  - `cai_profile_cli` permite `cai profile import` sin preguntar, como en `update-profile`: la
    barrera previa es el texto del skill (editar `data/profile.yaml` sí pide permiso);
  - `_public_url` no comprueba que el dominio exista ni rechaza `a..b`;
  - sin probar con un GitHub real: queda en la prueba manual.

### 25.3 · Ofertas dudosas y banderas rojas — 2026-10-17 · Claude Code (Opus 5.5)
- **Hecho:**
  - cinco señales de oferta dudosa en `jobs.signals` (ADR-028), sin migración:
    - `salary_range_wide`: máximo > mínimo + `doubtful.salary_range_max_pct` % (60);
    - `employer_hidden`: agencia (por la extracción o el nombre, también si dice para quién, con
      otro texto) o nombre que no dice quién contrata;
    - `fixed_term`: `contract_type: fixed_term`;
    - `ai_screening`: `mentions_ai_screening` o una frase del texto (palabras completas);
    - `stale_repost` (en `reposts.py`): todo el historial, en el canal con más días, ≥ 4 días con
      publicación nueva o ≥ 60 días entre la primera y la última;
  - `services/doubtful.py`: se calculan al guardar la extracción y con `cai jobs signals
    --recompute` (en lote, tolerante a extracciones mal formadas); patrones en
    `config/doubtful_patterns.yaml` y umbrales en `doubtful` de `config/policies.yaml`;
  - `JobExtraction`: `contract_type`, `hiring_entity`, `is_agency` y `mentions_ai_screening`,
    opcionales y sin volcarse vacíos (las extracciones guardadas no cambian; `schema_version` 1);
    rol `extractor` actualizado y regenerado;
  - no cambian el score; `preferences.exclude_signals` (`employer_hidden`, `fixed_term`) los
    convierte en filtro duro `signal` (vacío no se vuelca: el hash del perfil no cambia);
  - `get_match` devuelve `signals` (`[{code, text}]`) y `cai match show` las enseña; `assess-fit`
    las cita en `risks` y cuenta como deal-breaker la que choca con `criterios.md`;
  - dosier de empresa: `red_flags` con `kind`, `text` con cita y `date` obligatorios, en la copia
    Markdown y en la detección de inyección; `research-company` las busca y `prepare-interview`
    las convierte en preguntas;
  - UI: insignias con icono y texto en la bandeja y el triaje, nota «Antes de dedicarle tiempo» en
    la ficha, banderas rojas en «Empresa» y pestaña «Señal» en «¿Acierta el score?»
    (`by_signal`). Textos en es y en; OpenAPI regenerado;
  - docs: POLICIES §2 (señales de oferta dudosa), DATA_MODEL, AGENT_INTERFACE, nota de la 25.3 en
    la ADR-028, `config/README.md`, COMPARATIVA, prueba manual y PENDIENTES.
- **Tests:**
  - `test_doubtful.py` (41): cada señal con casos que la disparan y que no, umbral configurable,
    palabras completas, un solo canal en `stale_repost`, recálculo (también sin extracción o con
    una rota), el comando de la CLI, el score igual con y sin señales y el filtro opcional;
  - `get_match` con señales, `exclude_signals` que cierra la oferta, `red_flags` sin cita, con
    cita inexistente, sin fecha o de tipo desconocido rechazadas, y `by_signal` en la calibración;
  - Vitest: insignias, nota de la ficha, banderas rojas y pestaña «Señal».
  - 2654 tests de backend y 274 de frontend en verde (backend en tres tandas: la ejecución entera
    se paró una vez por falta de memoria); `tsc`, ruff y `sync_agents.py --check` limpios; OpenAPI
    regenerado. En la suite de Vitest, AppShell y Embudo dieron timeout con la máquina cargada;
    solos, en verde.
- **Decisiones (con el usuario):**
  - una agencia que dice para quién es también avisa, con otro texto;
  - las ofertas extraídas antes solo tienen las señales del nombre, el texto, el salario y las
    publicaciones: no se vuelven a extraer solas;
  - el embudo agrupa por las señales de ahora, no por las que tenía al enviarla;
  - umbrales: 60 %, 4 días o 60 días.
- **Revisión** (rol `reviewer`), sin bloqueantes. Se aplicó: el intervalo de `stale_repost`, solo
  en un canal; `recompute_all` en lote y sin parar por una extracción rota; frases del texto como
  palabras completas; fuera «recruiting» y «talent acquisition» de las agencias; el comando en
  `AGENT_INTERFACE.md`; tests del comando, de varios canales y del recálculo sin extracción.
- **Deuda:**
  - una vacante nueva con la misma empresa, título y ciudad cuenta para `stale_repost`;
  - las frases de cribado casan también negadas («no usamos AI screening»);
  - la fecha de una bandera roja no se limita en código (el skill pide 24 meses);
  - los evals de matching no pasan la empresa a los filtros: `exclude_signals` solo mira la
    extracción ahí;
  - sin probar con ofertas reales: queda en la prueba manual.

### 25.4 · Coste y lote en paralelo — 2026-10-17 · Claude Code (Opus 5.5)
- **Hecho:**
  - **uso normalizado** (`services/agent_usage.py`): los dos lectores (Claude Code y OpenCode)
    rellenan `input_tokens`, `output_tokens`, `cached_tokens`, `turns`, `duration_ms` y
    `cost_usd`; las filas de antes se traducen al leer; `cai eval compat` y la UI usan las nuevas;
  - **coste** (`services/agent_costs.py`): por acción, agente y modelo en 7 y 30 días, con los
    tokens del skill de cada acción; por oferta (la ejecución con oferta, entera; las de lote,
    repartidas entre las ofertas que escribieron según `mcp_calls`); en el embudo, por candidatura
    enviada, por entrevista y por fuente. `GET /agent/costs` y `GET /jobs/{id}/costs`;
  - **umbral antes de gastar** (`services/assess_threshold.py`): «Evaluar encaje» en segundo plano
    lleva en la orden solo los ids con score ≥ el umbral (página «Agente», `background_runs.
    assess_min_score` o el de triaje menos 10; como mucho 30); si no queda ninguna, no se lanza y
    dice por qué; el triaje y la ficha lo explican. `GET`/`PUT /agent/assess-threshold`;
    `cai eval compat` las valora todas;
  - **varias a la vez** (`agent_runner.py`): `background_runs.max_parallel` (1-4) y `per_agent`;
    reclamo atómico con hueco, tope por agente y sin chocar (misma oferta o misma acción de lote);
    hilos en `run_pending`; reintentos ante `database is locked`;
  - UI: sección «Coste» en «Agente» (pestañas 7/30 días, por acción, agente y modelo, y el umbral),
    «Coste del agente» en la ficha, aviso de «sin valorar en segundo plano» y coste en el embudo.
    Textos en es y en; OpenAPI regenerado;
  - docs: ADR-038 (extiende el ADR-032), POLICIES §6, DATA_MODEL, AGENT_INTERFACE, ARCHITECTURE,
    COMPARATIVA, guía en los dos idiomas, prueba manual y PENDIENTES.
- **Tests:**
  - `test_agent_costs.py`: claves viejas, sumas y medias por acción, agente y modelo con
    ejecuciones falsas (con y sin coste), reparto de un lote entre ofertas y coste en el embudo;
  - `test_assess_threshold.py`: por defecto, `policies.yaml` y la UI, las de debajo fuera de la
    orden, sin ninguna no se lanza, las ya valoradas fuera y la API solo desde la UI;
  - `test_agent_parallel.py`: reglas del reclamo, tope por agente, **con N=2 dos ofertas a la vez
    y la misma nunca dos veces** (agente falso lento), parar el worker con dos en curso, cancelar
    una de dos, recuperar tras reiniciar y reintento ante bloqueo;
  - Vitest: vista de coste y umbral, panel de la ficha, aviso del triaje y coste del embudo.
  - 2671 tests de backend (en tres tandas) y 285 de frontend en verde; `tsc`, ruff y
    `sync_agents.py --check` limpios; OpenAPI regenerado.
- **Decisiones (con el usuario):**
  - atribución de los lotes por `mcp_calls` y ventana de tiempo, sin migración;
  - «misma acción» = misma acción de lote: dos CVs de ofertas distintas sí van a la vez;
  - el paralelo solo en `policies.yaml`; el umbral, también en la UI;
  - sin `cost_usd`, tokens; nada se pasa a euros.
- **Revisión** (rol `reviewer`), sin bloqueantes. Se aplicó: `attributed()` con solo las columnas
  necesarias y una consulta a `mcp_calls` para todos los lotes (y en la ficha, solo los suyos);
  `run_pending(max_parallel=1)` pasa su límite al reclamo; tests de parar y cancelar con varias en
  curso; el agente falso lento, más holgado; docstrings, el componente `Window` renombrado, los
  endpoints en AGENT_INTERFACE y el aviso de reiniciar el worker tras cambiar el paralelo.
- **Deuda:**
  - la atribución de un lote cuenta también lo que se haga a la vez en una terminal o con otro
    agente con las mismas herramientas (`client_name` es el del cliente MCP, no el agente);
  - un lote sigue siendo una sola ejecución: el paralelo es entre acciones y entre ofertas;
  - el umbral va en la orden, no en las herramientas (`list_jobs` seguiría viendo las demás);
  - el coste por fuente del embudo no sale en la calibración;
  - sin probar con agentes reales: queda en la prueba manual.

### 25.5 · Maquetación del PDF — 2026-10-17 · Claude Code (Opus 5.5)
- **Hecho:**
  - `services/documents/layout.py`: lee el PDF renderizado con `pypdfium2` (ya era dependencia)
    y avisa de `orphan_heading`, `large_gap` (también al pie de una página que no es la última),
    `footer_overlap`, `nearly_empty_last_page` y `text_layer` (nombre, correo y teléfono en el
    texto del PDF y el nombre antes que los títulos). Los títulos salen del contexto del render
    (secciones presentes y puesto de cada experiencia), también con espaciado entre letras y sin
    confundir una frase que empieza igual. Umbrales en `layout` de `config/policies.yaml`;
  - avisos, no bloqueos: `RenderWarning` gana `page` y `fix` (`template` o `content`), vacíos no
    se guardan; solo `too_long` sigue impidiendo «Usar este para enviar». En el CV y la carta;
  - ficha: cada aviso con su página y cómo arreglarlo (`RenderWarnings`, en CV y carta), en es y en;
  - `generate-cv` y el rol `writer`: con `fix: content`, se recorta lo menos relevante para la
    oferta (por relevancia, no por antigüedad), como con `too_long`; con `template`, se le dice al
    usuario que cambie la plantilla en la UI;
  - `cai eval cv`: comprobación `layout` sobre el render que se enviaría;
  - **plantilla `moderna-2col` corregida:** la barra iba antes que el nombre en el HTML y el texto
    del PDF (lo que lee un ATS) empezaba por ella; ahora va después y el CSS la coloca igual (la
    vista previa en PNG no cambia);
  - docs: `CV_TEMPLATES.md` §Avisos (tabla de maquetación y cómo hacer una plantilla de dos
    columnas), POLICIES §3, DATA_MODEL, AGENT_INTERFACE, `evals/README.md`, COMPARATIVA, prueba
    manual y PENDIENTES.
- **Tests:**
  - `test_layout.py` (19): un PDF de prueba por aviso (con un generador de PDFs con texto colocado
    en `tests/cv_support.py`), CVs correctos de una y dos páginas sin avisos, título al pie de la
    última página, frase que empieza como un título, títulos y nombre con espaciado, correo
    partido, teléfono por dígitos, umbrales de `policies.yaml` y apagado;
  - `test_layout_builtin.py`: el CV y la carta de la demo con todas las plantillas integradas, con
    LibreOffice y Chromium de verdad, sin avisos (se salta si faltan);
  - el aviso se guarda con el render y no bloquea; `layout` en `cai eval cv`; Vitest de la ficha;
  - en los demás tests la maquetación va apagada (`tests/conftest.py`): el conversor falso no
    maqueta. Los que la prueban llevan `@pytest.mark.layout`.
  - 2698 tests de backend (en tres tandas) y 286 de frontend en verde; `tsc`, ruff y
    `sync_agents.py --check` limpios; OpenAPI regenerado.
- **Decisiones (con el usuario):**
  - títulos del contexto del render, no adivinados por la fuente;
  - el hueco al pie de una página que no es la última cuenta como `large_gap`;
  - la maquetación se apaga en los tests desde `conftest.py`, no con una marca en el PDF.
- **Revisión** (rol `reviewer`), sin bloqueantes. Se aplicó: una frase que empieza como un título
  ya no es un título; nombre y correo comparados sin espacios; cierre de cada página aunque falle;
  fuera los `fix` que nunca se emitían (`hide_section`, `page_size`); `layout` en las listas de
  `cai eval cv`; el límite de las dos columnas en `CV_TEMPLATES.md`; y los tests que faltaban.
- **Deuda:**
  - en dos columnas, las líneas se juntan por altura: un huérfano o un hueco de una columna
    puede quedar tapado por la otra (falta un aviso, nunca sobra);
  - el teléfono se busca en los dígitos de todo el texto (podría casar por coincidencia);
  - sin probar con plantillas importadas reales: queda en la prueba manual.


### 25.6 · CHANGELOG y la historia con números — 2026-10-17 · Claude Code (Opus 5.5)
- **Hecho:**
  - `CHANGELOG.md` (Keep a Changelog 1.1.0 en español, versionado semántico): `[0.1.0] -
    2026-10-16` con las fases 01 a 23 (commit `4d9d8b4`, nunca publicada como release) y
    `[Sin publicar]` con la 24 y la 25, en Añadido, Cambiado, Eliminado, Corregido y Seguridad;
  - `scripts/release_notes.py` (solo biblioteca estándar): saca la sección de una etiqueta y
    comprueba la estructura (`--check`: «Sin publicar» primero, versiones de más nueva a más
    vieja, grupos conocidos y en orden, una entrada por versión y su enlace al final);
  - `release.yml`: un job `notes` (permiso de lectura) saca las notas y las deja en el resumen;
    `release` (escritura, solo con `push` de una etiqueta) compila y publica con `--notes-file`.
    Sin sección, falla antes de compilar. `workflow_dispatch` hace la prueba en seco;
  - `analytics.get_search_story` + `cai stats story [--json]` + `GET /stats/story`: toda la
    búsqueda (sin periodo y sin duplicadas) en números agregados, fechas en Europe/Madrid y una
    línea para el README en español e inglés. Solo CLI y API: el agente no la necesita;
  - Embudo: tarjeta «Tu búsqueda en números» con las cifras, la línea en el idioma de la UI y
    «Copiar en español» / «Copiar en inglés» (es y en);
  - regla de cierre: `AGENTS.md` (regla 8) y `implement-phase` piden actualizar «Sin publicar»;
  - docs: `CONTRIBUTING.md` (§Changelog, versiones y releases, en los dos idiomas), README en los
    dos idiomas (bloque comentado para tus cifras y fila del `CHANGELOG`), AGENT_INTERFACE,
    GUIA/GUIDE, `docs/README.md`, COMPARATIVA, RESUMEN_FASES, prueba manual y PENDIENTES.
- **Tests:**
  - `test_changelog.py` (13): estructura del `CHANGELOG` real, «Sin publicar» con lo de la 24 y
    la 25, versión igual a la de `pyproject.toml`, notas de una etiqueta, errores con su motivo y
    la CLI del script;
  - `test_search_story.py` (3): sin ofertas, recuentos y fechas con un histórico a mano
    (duplicada fuera, filtros duros cuentan como evaluadas) y `cai stats story --json` sobre la
    demo, igual que el embudo y sin ningún nombre de empresa, puesto, fuente ni lugar;
  - `test_start.py`: el workflow nuevo (disparadores, permisos por job, notas desde el script);
  - Vitest de la tarjeta del Embudo (cifras, fechas, copiar);
  - prueba en seco local del paso de notas con `bash -eo pipefail` (como Actions): `v0.1.0` da
    sus notas y `v0.2.0` sale con 1;
  - 2714 tests de backend (en tres tandas) y 287 de frontend en verde; `tsc`, ruff,
    `sync_agents.py --check` y `check_links.py` limpios; OpenAPI regenerado.
- **Decisiones:**
  - no había ninguna release publicada: la 0.1.0 es el estado de `main` al cerrar la fase 23 (es
    la versión de `pyproject.toml`) y la primera release pública será la 0.2.0 con «Sin publicar»;
    los enlaces del final apuntan a ese commit, no a una etiqueta;
  - «Evaluadas» = ofertas con extracción, pasaran o no los filtros duros (como el «evaluadas» de
    career-ops);
  - las cifras del README van en un comentario: publicarlas es decisión del usuario;
  - `cai stats story` sin herramienta MCP (la paridad es de MCP a CLI, no al revés).
- **Revisión** (rol `reviewer`), sin bloqueantes. Se aplicó: la prueba en seco explicada bien
  (usa el `CHANGELOG` de la rama; la etiqueta solo elige la sección), permisos de escritura solo
  en el job que publica y una línea larga del skill.
- **Deuda:**
  - la prueba en seco en GitHub queda para cuando el usuario haga push (PENDIENTES);
  - la línea del README no dice «qué funcionó»: lo escribe el usuario.

### 25.7a · «Mi perfil» editable: backend — 2026-10-17 · Claude Code (Opus 5.5)
- **Hecho:**
  - `services/profile_editor.py`: guarda una sección de `data/profile.yaml` desde la UI con
    ruamel.yaml en modo ida y vuelta y **fusión** con lo que había (claves en su sitio, listas por
    `id`, escalares sin tocar si no cambian), así que el diff solo toca lo cambiado; comillas para
    lo que YAML leería como otro tipo y bloques para el texto con saltos de línea. Concurrencia
    optimista por el sha256 de los bytes (`conflict`), validación entera (`ProfileIssue` con su
    ruta), ids generados (`exp-…`, `a<n>`, `prj-…`, `st-…`) que no cambian al renombrar, rechazo al
    borrar lo que cita una historia (`referenced`) y aviso si lo cita un CV o carta, `dry_run` con el
    diff, copia en `data/profile-history/` (20) y «Deshacer», con lock e importación dentro;
  - «Usar por defecto» de Plantillas pasa por el editor (copia, auditoría, lock);
  - contexto editable (`GET`/`PUT /context/{section}`): el fichero tal cual, comentarios-guía
    incluidos, plantilla si no existía, 20 KB antes de escribir (`too_large`) y `conflict`;
  - muestras de estilo (`services/style_samples.py`, `data/documentos/estilo/`): subida en JSON
    base64, `.txt`/`.md`/`.docx`/`.pdf`, texto extraído en `.texto/`, detección de inyección,
    límites en `profile_editing` de `policies.yaml`, lock; `get_context.style_samples` envueltas
    en `<untrusted_style_sample>` (el escape de etiquetas lo cubre) y recortadas a 20 KB;
  - API (`routes/profile.py`, `routes/context.py`): escrituras con `require_ui`, lecturas con
    contacto o texto tuyo con `require_ui_read` (nuevo: sin `Origin` ajeno ni `Sec-Fetch-Site:
    cross-site`); errores `conflict` y `referenced` (409), `validation_error` con los campos;
  - auditoría `profile_edits` (migración 0024): qué, cuándo y hashes, sin texto;
  - skills: `update-profile` con «Mejorar un elemento» y «Proponer historias»; `writer`,
    `generate-cover-letter` y `verifier` con las muestras (tono sí, hechos y frases enteras no);
  - docs: ADR-039 (y nota en el ADR-025), POLICIES §1.5, DATA_MODEL, AGENT_INTERFACE; el encargo
    y el plan de la fase recogen la partición en 25.7a y 25.7b.
- **Tests:** `test_profile_editor.py` (18: comentarios y formato intactos byte a byte, `conflict`,
  validación sin escribir ni copia ni auditoría, versión + rescore + copia + deshacer, sin cambios
  no crea versión, `dry_run`, ids estables y sin choques, borrar lo citado, contacto y textos que
  YAML leería mal, bloques, fichero inválido, límite de copias, CRLF, BOM al deshacer y clave no
  enviada); `test_api_profile_editor.py` (20: guardar, `conflict`, campos de validación,
  `referenced`, diff, escrituras y lecturas solo para la UI, ninguna herramienta MCP ni comando que
  escriba el perfil, contexto con guías, 20 KB y auditoría, muestras con `.docx`, inyección,
  límites y envoltorio que no se puede cerrar desde dentro); los de `cli db` con la cabecera 0024;
  2752 tests de backend y 287 de frontend en verde; `tsc`, ruff y `sync_agents.py --check` limpios.
- **Decisiones (con el usuario):** auditoría en una tabla propia y no en `events`; el nivel de
  idioma será un desplegable que conserva los valores libres (sin cambiar el esquema, en la
  25.7b); dos commits. Mías: subida de muestras en JSON para que valga `require_ui`; el servidor no
  quita los comentarios-guía del contexto (la UI los enseña); el id del elemento en la orden de
  «Mejorar con mi agente» va con los botones en la 25.7b, porque toca también la cola de encargos.
- **Revisión** (rol `reviewer`), sin bloqueantes. Se aplicó: `require_ui_read` en `GET
  /profile/diff` y en la lista de muestras; hash correcto al deshacer una copia con BOM; copia
  después de escribir e importación dentro del lock; lock en las subidas; un solo modelo de muestra;
  `section` a 128; el límite de «sección entera» y de las listas sin `id` en el docstring y el ADR;
  y los tests de CRLF, BOM, rollback, envoltorio y clave no enviada.
- **Deuda:** reordenar una lista mueve sus elementos sin sus comentarios; las listas sin `id` se
  reescriben enteras si cambian; `require_ui_read` no frena a un programa local (`curl`), que de
  todos modos lee el fichero; al pasar del límite de 20 KB, las muestras que no caben no se avisan
  al agente; el CHANGELOG espera a la 25.7b, que es cuando el usuario ve el cambio.


### 25.7b · «Mi perfil» editable: la página — 2026-10-17 · Claude Code (Opus 5.5)
- **Hecho:**
  - «Mi perfil» por pestañas (Datos, Experiencia, Proyectos y formación, Skills e idiomas,
    Historias STAR, Búsqueda, CV y carta, Contexto y estilo, Historial), con `forceMount` para no
    perder lo que no se ha guardado al cambiar de pestaña;
  - `components/profile/editor.tsx`: `useBlockEditor` (un borrador por bloque que se pone al día si
    otro bloque guarda y adopta los ids del servidor tras guardar), guardado por secciones con el
    `file_hash` que vuelve de cada una, errores de validación en el campo de su ruta, `conflict`
    con «Recargar», aviso de guardado a medias, y aviso de cambios sin guardar al cerrar la pestaña
    (`beforeunload`) o seguir un enlace de la app (con `BrowserRouter` no hay `useBlocker`);
  - bloques: datos y resumen (contacto marcado como privado), experiencia con logros (meses,
    «Actualidad», skills con las de tu perfil, NDA, fuente, reordenar y borrar), proyectos,
    formación, certificaciones y secciones extra, idiomas (desplegable A1–C2/Nativo que conserva el
    valor libre) y skills (F/C+/C/B) con básicas, historias STAR (pistas, evidencias por nombre, sin
    evidencia no se guarda), lo que buscas, CV y carta; lo que buscas y las skills enseñan el diff
    (`dry_run`) y avisan del recálculo antes de guardar; las claves que la UI no enseña (`source`,
    `exclude_signals`, `template_rules`…) vuelven tal cual;
  - contexto con editor y vista previa propia del Markdown (títulos, párrafos, listas, negrita y
    cursiva, sin comentarios ni HTML), contador de tamaño y `conflict`; muestras de estilo con
    «Subir», «Ver texto extraído», aviso de inyección y «Borrar»; el estado de ficheros y carpetas
    de la fase 13 y el botón de `expand` siguen;
  - historial: «Ver cambios» y «Deshacer el último cambio»;
  - agente: acciones `improve-profile-item` (con `profile_item`, solo con formato de id y solo si
    es un logro o historia del perfil vigente; sin «Dejar para mi próxima sesión» ni segundo plano)
    y `propose-stories`; `AgentButton` con `profileItem`;
  - textos en `locales/{es,en}/profileEditor.json` (y `conflict`/`referenced` en los errores);
  - docs: GUIA y GUIDE (la UI como camino principal), README en los dos idiomas, CHANGELOG,
    RESUMEN_FASES, COMPARATIVA, ADR-039 (la página y el matiz a la ADR-024), PENDIENTES y
    `dev/pruebas/fase-25.7-prueba-manual.txt`.
- **Tests:** `ProfileEditor.test.tsx` (11: logro guardado con su hash y sus claves ocultas, error
  en su campo, historia sin evidencia, diff de lo que buscas con `exclude_signals` intacto, nivel de
  idioma libre, contexto con guías y vista previa sin ellas, Markdown sin HTML, conflicto, contacto
  privado, botón del agente con su id y sin «Dejar para luego», aviso al salir e inglés);
  `ProfilePage.test.tsx` adaptado (sin perfil); `test_agent_launch.py` (+7: id válido, inexistente,
  un proyecto, inyección en el id, sin cola ni segundo plano).
  2759 tests de backend y 298 de frontend en verde (el de guardar un logro escribe mucho texto y
  lleva 30 s de tiempo máximo: con la batería entera en paralelo pasaba de 15); `tsc`, ruff y
  `sync_agents.py --check` limpios.
- **Decisiones (con el usuario):** vista previa del Markdown propia y sin dependencias; nivel de
  idioma con desplegable que conserva el texto libre. Mías: pestañas montadas siempre; las tres
  partes de `preferences` (búsqueda, CV, carta) son bloques que guardan la sección entera con lo de
  los demás tal cual; `template_rules` no se edita en la UI (se conserva y se explica); `private`
  (tu mínimo salarial) sigue solo en el YAML.
- **Revisión** (rol `reviewer`), sin bloqueantes. Se aplicó: modo «Otro» del nivel de idioma sin
  centinela ni recortes; aviso y recarga si un bloque de varias secciones se guarda a medias; no
  escribir titular ni resumen vacíos si el fichero no los tenía; `fullmatch` en el id; los enlaces
  de ancla y de descarga no avisan; imports juntos; y los tests de claves ocultas, botones del
  agente, Markdown sin HTML y aviso al salir.
- **Deuda:** borrar una muestra no pide confirmación; los grupos de evidencias que no son de
  experiencia se traducen con una lista fija; reordenar una lista mueve sus elementos sin sus
  comentarios (de la 25.7a); la prueba manual con un agente de verdad queda en PENDIENTES.


### 26.1 · Núcleo multiplataforma — 2026-10-17 · Claude Code (Opus 5.5)
- **Hecho:**
  - `services/terminals.py`: Terminal.app (o iTerm2) con `osascript` en macOS; en Linux,
    `CAI_TERMINAL`, `$TERMINAL` o la primera de `x-terminal-emulator` (con la forma de la terminal a
    la que apunta), `gnome-terminal`, `konsole`, `xfce4-terminal`, `kitty`, `wezterm` y
    `alacritty`; sin pantalla, ninguna. La orden en bash o zsh con `shlex.quote` (`cd`, `unset`
    de `unset_env` con nombres validados, `CAI_CLIENT_NAME`, el agente y el shell abierto al
    salir); si la terminal sale con error en el primer segundo, la UI copia la orden;
  - `agent_launch`: `no_terminal()` sustituye a `WINDOWS_ONLY` en los botones, «Abrir en
    terminal» y `resumable_agents`; `terminal_command` elige PowerShell o POSIX. Windows, igual;
  - `agent_runner._alive_as` en macOS y Linux (`kill -0`, jefe de su grupo y el programa, o el
    primer argumento de un intérprete, por `/proc` o `ps`), así que `recover_interrupted` ya para
    huérfanos fuera de Windows;
  - `cai start`: cada hijo en su grupo, `SIGTERM` al grupo y hasta 10 s antes de `killpg`, y
    `SIGTERM`/`SIGHUP` paran `cai start` y el worker como Ctrl+C;
  - LibreOffice: `libreoffice` en el `PATH` y rutas de macOS y Linux, sin Flatpak ni Snap (su
    sandbox no ve el `/tmp` donde se convierte; ADR-040); «Abrir carpeta» con `open` o `xdg-open`; `cai demo seed` da las indicaciones en bash fuera de Windows; `cai agents
    doctor` dice qué terminal usaría;
  - `config.install_dir()`, `installed_data_dir()` y `cai paths --json` para que el instalador (26.2) y la app
    coincidan; `CAI_TERMINAL` en la configuración;
  - ADR-040, `AGENTS_COMPAT.md` y `dev/pruebas/fase-26-prueba-manual.txt` (sección 26.1).
- **Inventario** de suposiciones de Windows: `git grep -n win32 backend/app` solo encuentra ramas
  con su equivalente para macOS y Linux (`agent_launch`, `agent_runner`, `agent_registry`,
  `launcher`, `pdf`, `folders`, `cli`, `core/config`). `os.startfile` y `taskkill`/`tasklist`
  quedan solo en su rama de Windows.
- **Tests:** `test_terminals.py` (forma de cada terminal, precedencia, sin pantalla, AppleScript,
  entrecomillado, `soffice` por sistema, carpeta de datos, `cai paths`, `cai start` y, en macOS y
  Linux de verdad, el shell real, `SIGTERM` y matar el árbol); los dos tests de matar el árbol de
  `test_agent_runs.py` ya no son solo de Windows; los de «sin terminal» de `test_agent_launch.py`
  simulan Linux sin terminal y hay uno con terminal; `test_api_context.py` con `open`/`xdg-open`.
  2797 tests de backend: en Windows pasan todos menos 3 que se saltan (los de POSIX real); ruff y
  `sync_agents.py --check` limpios. Sin cambios en el frontend.
- **Decisiones:** de acuerdo con el usuario, `cai paths --json` para que el instalador coincida con
  la app y `CAI_TERMINAL` ignorada en Windows. Mías: sin Flatpak ni Snap para LibreOffice
  (se aparta del encargo; motivo en la ADR-040); `x-terminal-emulator` con la forma de la
  terminal a la que apunta; `gnome-terminal` sin título; la terminal que sale con error en el
  primer segundo cuenta como no abierta.
- **Revisión** (rol `reviewer`), sin bloqueantes. Se aplicó: `_alive_as` compara el programa (o
  el primer argumento de un intérprete) y no cualquier argumento, y lee `/proc` en Linux; la
  segunda señal se ignora para no cortar la limpieza, también en el worker; `SIGKILL` a lo que
  quede del grupo; procesos recogidos en un hilo (sin zombis); fuera Flatpak y Snap;
  `CAI_TERMINAL` en GUIA y GUIDE; COMPARATIVA al día; comentarios en `_realpath` y `shell()`.
- **Deuda:** los tests de POSIX se saltan en Windows hasta la CI de la 26.4 (o la prueba en WSL);
  las formas de cada terminal salen de su documentación, no de probarlas todas (iTerm2, sin
  probar); Terminal.app puede abrir una ventana vacía de más si no estaba abierto; un
  `$TERMINAL` con argumentos («alacritty -e») no se usa; `.env.example` no lo puede tocar el
  agente (en PENDIENTES).

### 26.2 · Instalador para macOS y Linux — 2026-10-18 · Claude Code (Opus 5.5)
- **Hecho:**
  - `install.sh` (bash 3.2+, para `curl | bash`): uv si falta, release (o zip o repositorio local),
    `app.new` y sustitución solo de una CandidatAI, `.env` conservado con `CAI_DATA_DIR`, `uv
    sync`, Chromium (con la pista de `playwright install-deps` en Linux, sin sudo), `cai db
    upgrade`, y acceso directo: `.desktop` con `Terminal=true` en Linux y `.app` con icono que abre
    un `.command` en Terminal en macOS. `--dry-run`, `--uninstall`, `--remove-data` (confirmación
    por `/dev/tty`), `--no-shortcuts` y `--no-setup` (tests y CI); se niega con `/`, `HOME` y las
    carpetas del sistema;
  - `config.install_dir()` (y `installed_data_dir()` pasa a ser su `data/`, como en Windows: en la
    26.1 apuntaba a la carpeta de CandidatAI) y `install_dir` en `cai paths`;
  - `scripts/build_icons.py` genera también `candidatai.png` (512 px) y `candidatai.icns` (Pillow);
  - `.gitattributes` con `*.sh text eol=lf`, `install.sh` ejecutable en git y el workflow de release
    comprueba que el zip lleva `install.sh` y el `.icns`;
  - README y guía en los dos idiomas, ADR-041, COMPARATIVA y la sección 26.2 de la prueba manual.
- **Corregido de la 26.1** al pasar la suite en Linux (WSL2, Ubuntu): al parar el worker, `killpg`
  cerraba la salida del agente antes de que el runner viera la parada y la ejecución quedaba como
  «terminó sin resultado (código -9)» en vez de «Se paró el worker»; dos tests suponían Windows
  (`test_open_in_terminal_resumes_the_session` simulaba `win32` antes de lanzar el agente falso) o
  partían con un separador que estaba en el texto. La suite entera en Linux sacó tres más, de antes
  de la fase 26: el archivo de candidaturas (`application_archive`) daba por archivada una carpeta
  vacía de otro proceso porque en macOS y Linux `rename` la sustituye sin error (ahora se comprueba
  antes); las plantillas de `templates/` no salían idénticas fuera de Windows (el zip guarda el
  sistema que lo creó: `create_system = 0`); y `test_agent_prefs` simulaba `win32` en todo el
  proceso (ahora fuerza solo PowerShell y la terminal). Y la foto de la demo se compara por píxeles,
  no por bytes (el zlib de cada sistema comprime distinto).
- **Tests:** `test_install_sh.py` (en macOS y Linux: `--dry-run` no escribe nada y anuncia las
  rutas de `config.install_dir`, reinstalar conserva datos y `.env` y crea el acceso directo,
  desinstalar sin terminal no borra datos, carpetas protegidas y ajenas, repositorio local sin UI y
  sin `data/`, `shellcheck`; en todos: bash con LF, `main "$@"` al final, `100755` en git e
  iconos); `test_start.py` comprueba el workflow. `shellcheck` 0.11 limpio.
  2799 tests de backend: en Windows pasan todos salvo 12 de macOS y Linux que se saltan; en
  Ubuntu (WSL2) pasan todos salvo los de Windows, Chromium sin librerías del sistema y LibreOffice;
  ruff y `sync_agents.py --check` limpios.
- **Revisión** (rol `reviewer`). Un bloqueante, aplicado: `--uninstall --remove-data` con un
  `--install-dir` ajeno borraba su `data/` (y `install.ps1` igual). Ahora la carpeta lleva una marca
  (`.candidatai`, en los dos instaladores) y sin ella ni una app de CandidatAI no se borran datos ni
  se instala en una carpeta con cosas. También: rutas normalizadas (`.`, `..`, `//`), comprobar
  antes de borrar, `rm -f` para ficheros, la `.app` solo si es nuestra, volver a la versión anterior
  si se corta el cambio, `</dev/null` en lo que se lanza, `--remove-data` sin `--uninstall` da error,
  `chmod +x` de `install.sh` tras `python -m zipfile`, `UV_INSTALL_DIR` y `XDG_BIN_HOME`, `trim` de
  `XDG_DATA_HOME` como en Python, y tests de carpeta ajena, rutas con `..` y espacios, `.env` con
  espacios (dotenv) y `-RemoveData` ajeno en `install.ps1`.
- **Decisiones (con el usuario):** `.app` con icono en macOS; `--no-setup`. Mías: bash y no `sh`
  (arrays, `printf %q`), compatible con el 3.2 de macOS; `CAI_DATA_DIR` entre comillas en el
  `.env` (las rutas de macOS llevan espacios); rutas sin comillas, `\`, `` ` ``, `$` ni `%`.
- **Deuda:** la `.app` de macOS y el `.desktop` dependen del escritorio y no se pueden comprobar en
  un test; macOS, sin probar hasta la CI de la 26.4.

### 26.3 · Docker opcional — 2026-10-18 · Claude Code (Opus 5.5)
- **Hecho:**
  - `Dockerfile` en dos etapas (UI con Node 24 y pnpm; final con `uv:0.9.30-python3.12`, el
    backend, la UI compilada y el Chromium sin ventana de Playwright con sus librerías), usuario
    `cai` (uid 1000), sin LibreOffice ni torch, la caché de uv fuera de la imagen (1,7 GB);
    `.dockerignore` deja fuera `data*`, `.env` y `.git`;
  - `docker-compose.yml`: `cai start --no-browser`, contenedor `candidatai`, puerto solo en
    `127.0.0.1:8000`, volúmenes con nombre fijo `candidatai-data` (`/data`) y `candidatai-demo`
    (`/data-demo`), `.env` opcional con `CAI_IN_DOCKER` y `CAI_DATA_DIR` por delante, healthcheck
    sobre `/status` e `init`; `docker-compose.demo.yml` abre la demo;
  - `services/container.py`: `listen_host()` (todas las interfaces solo con `CAI_IN_DOCKER=1` y
    marca de contenedor) y los motivos. Con `CAI_IN_DOCKER`: los botones de terminal copian la
    orden, el segundo plano se bloquea (`no_headless`), la candidatura asistida no prepara, rellena
    ni envía (código `docker`, también para las tareas ya encoladas en el worker) y la ficha ofrece
    abrir la oferta en tu navegador y «Marcar como enviada»; `cai doctor` con sección «Docker» y sin
    avisos de LibreOffice ni de agentes; `cai demo seed` va a `/data-demo`;
  - guía «Con Docker» en los dos idiomas (tabla de qué funciona, MCP para Claude Code, Codex y
    OpenCode, `cai … --json`, copia de seguridad del volumen), README, ADR-042 (matiza la 007),
    AGENT_INTERFACE, COMPARATIVA, AGENTS.md y la sección 26.3 de la prueba manual.
- **Probado con Docker Desktop (Windows):** `docker compose up -d --build`, `/status` y la UI desde
  Windows, `cai demo seed` con 2 CVs en PDF (motor html), un cliente MCP por stdio con
  `docker exec -i candidatai cai-mcp` (50 herramientas, los datos de la demo), `cai doctor` «Todo
  listo», `docker compose stop` limpio (código 0) y la copia del volumen con `alpine tar`.
- **Tests:** `test_docker.py` (dónde escucha la API, `cai serve`, botones, segundo plano por el
  servicio y la API, candidatura asistida por la API, el servicio y el worker, diagnóstico, demo,
  Dockerfile y compose) y un test de vitest de la ficha en Docker. 2813 tests de backend en Windows
  (12 de macOS y Linux se saltan), frontend en verde (typecheck, lint y vitest), ruff y
  `sync_agents.py --check` limpios.
- **Revisión** (rol `reviewer`), sin bloqueantes. Aplicado: las tareas del navegador ya encoladas
  fallan con el motivo en Docker; `demo._pdf_engine` solo lanza Chromium para comprobarlo en Docker
  (Windows queda igual); `.dockerignore` con `**/data*` y `**/.env`; «Docker · límites» en OK
  (esperados); aviso en el compose de no quitar `127.0.0.1:`; imagen de uv fijada.
- **Decisiones:** volumen con nombre (usuario). Mías: `docker exec -i candidatai cai-mcp` en vez de
  `docker compose exec -T` (un cliente MCP que arranca el servidor con un entorno mínimo no
  encuentra el plugin `compose`, y no depende de la carpeta); la demo en su propio volumen; el
  Chromium sin ventana (`--only-shell`), porque dentro no hay candidatura asistida.
- **Deuda:** el agente procesando la demo por MCP y Docker en WSL2 quedan para la prueba manual; la
  imagen no se publica en un registro (26.4 si se quiere); la parada tarda unos 13 s.

### 26.4 · CI en tres sistemas y docs — 2026-10-18 · Claude Code (Opus 5.5)
- **Hecho:**
  - `ci.yml`: backend en matriz (Windows y Ubuntu en cada push; macOS en `main`, etiquetas y
    «Run workflow», por coste: macOS se factura ×10 en un repositorio privado), con caché de uv y de
    Chromium (`PLAYWRIGHT_BROWSERS_PATH` común, clave con la versión de Playwright), Chromium con
    sus librerías en Linux, shellcheck en macOS, ruff, pytest con la cobertura mínima (85 %) y la
    demo de humo en `pwsh` en los tres; job `installer` (shellcheck, `--dry-run` que no escribe
    nada, instalar, reinstalar conservando los datos y desinstalar con `--no-setup`) en Ubuntu y
    macOS; job `docker` (imagen con caché de Actions, `/status`, `cai demo seed` con 60 ofertas y 2
    CVs, y la sección «Docker» de `cai doctor`). `install.ps1 -WhatIf` ya lo probaba `test_start.py`;
  - `release.yml`: la prueba en seco compila y comprueba `candidatai.zip` (con `install.sh`
    ejecutable, el `.icns` y la UI) y lo deja como artefacto; `package` va sin permiso de
    escritura y `release` (publicar) solo con la etiqueta;
  - docs: badge «Windows · macOS · Linux», carpeta de datos de cada sistema y copia de seguridad en
    la guía (es y en), «Por sistema» en AGENTS_COMPAT, COMPARATIVA, DESARROLLO_POR_FASES.
- **La CI en la rama** (ejecución a mano, 2026-10-18): todo en verde en los tres sistemas. Backend:
  2814 tests en Ubuntu y macOS (13 se saltan), cobertura del 94 %; 40 min en Windows, 18 en Ubuntu
  y 10 en macOS. Instalador en Ubuntu y macOS, Docker, frontend y agents en verde. La prueba en seco
  de la release deja el zip (4,8 MB) sin publicar.
- **Lo que encontró la primera CI:** `install.sh` fallaba en macOS (el `chmod` de BSD lee `--` como
  un fichero cuando va tras el modo); `test_run_with_questions_needs_the_user` suponía un escritorio
  (en un Linux sin `DISPLAY` no hay terminal donde reanudar); y una descarga de PyPI caída en macOS.
- **Revisión** (rol `reviewer`), sin fallos de seguridad. Aplicado: la release en dos jobs, para que
  el token de escritura no exista en la prueba en seco; `bash` con pipefail y `timeout-minutes` en
  los jobs de Docker y del instalador; las afirmaciones de la COMPARATIVA y AGENTS_COMPAT, solo tras
  la CI en verde.
- **Decisiones:** macOS solo en `main`, etiquetas y a mano (con los números); la imagen no se
  publica en GHCR (el repositorio es privado); la demo de humo sigue en `pwsh`.
- **Deuda:** la guía de cero a la app abierta en WSL2 y Docker en WSL2 quedan para la prueba manual;
  los agentes no se han probado con la app en macOS ni en Linux; `ruff` y la cobertura corren en los
  tres sistemas (bastaría uno).

### 26.5 · Demo completa — 2026-10-19 · Claude Code (Opus 5.5)
- **Por qué:** al probar las fases 24-26 con la demo, muchas pantallas salían vacías (Respuestas,
  dosier, carta, mensajes, plan y repaso de entrevistas, oferta recibida, Skills, encargos,
  contexto y muestras de estilo): la demo solo traía el embudo y dos CVs.
- **Hecho:**
  - `services/demo_extras.py`, llamado al final de `demo.seed`, con el contenido de
    `demo/<idioma>/seed/extras.yaml` y siempre por los servicios: valoración del encaje de las dos
    ofertas con CV; carta (con indicaciones y verificada) y respuestas de screening de la primera;
    mensaje de LinkedIn de la segunda; seguimiento de una candidatura enviada; dosier de las dos
    empresas (la segunda con un ERE como bandera roja); plan de la primera entrevista programada y
    repaso de dos ya hechas; datos de la oferta recibida (importes privados); tres correos en
    `inbox/respuestas/` leídos con `poll_replies` (entrevista y descarte con propuesta, y un acuse
    con texto oculto para una IA sin clasificar); «No la tengo» en Looker y Databricks; un encargo
    «Generar CV» pendiente; el contexto (`demo/contexto/` y el nuevo `demo/en/contexto/`), una
    muestra de estilo y `documentos/salarios.csv`;
  - los eventos que los servicios fechan «ahora» se recolocan: la valoración, una hora antes de
    la aprobación; la carta y las respuestas, unos minutos antes de `now`. La demo sigue siendo
    determinista;
  - **los botones «en tu agente» ponen `CAI_DATA_DIR` en una demo** (`launch_env`): una pestaña
    nueva de Windows Terminal (`wt -w 0`) no hereda el entorno de `cai start`, así que el agente
    podía escribir en `data/` en vez de en la demo;
  - guía (es y en): qué trae la demo y compilar la UI tras cambiar de rama;
    `dev/pruebas/fases-24-26-pruebas.md`: comprobación de la UI compilada, `CAI_DATA_DIR` en cada
    terminal del bloque 1 y un recorrido por lo que trae la demo.
- **Decisiones:** sin recorridos de plataformas ni ejecuciones del agente inventados: activar la
  búsqueda con navegador es cosa del usuario y el coste tiene que ser real. La carta solo se
  genera si hay con qué hacer el PDF, como los CVs.

### 27.1 · Ayudas en los botones de los skills — 2026-10-23 · Claude Code (Opus 5.5)
- **Por qué:** «Ampliar búsqueda» no decía qué hacía; el único texto al pasar el ratón era el
  `title` nativo, que explicaba cómo se abre el agente y no para qué sirve el skill.
- **Hecho:**
  - `locales/{es,en}/agentActions.json` (namespace nuevo): la ayuda de las 23 acciones de
    `ACTIONS` (qué hace, qué cambia en la app y qué te pide), redactada desde cada `SKILL.md`; el
    nombre sale de `agent.json` (`actions.*`), que ya existía, para no tener dos;
  - `components/Hint.tsx`: globo sobre el `Tooltip` de shadcn, con un disparador propio o con un
    icono ⓘ enfocable;
  - `AgentButton`: el globo (nombre, ayuda, motivo del bloqueo en color de aviso o, si no, cómo se
    abre en una línea atenuada) sustituye al `title`. El disparador es un `<span>` alrededor del
    botón porque un `<button disabled>` no dispara eventos; si está bloqueado, ese `<span>` recibe
    el foco (`role="group"` con el nombre del botón). La ayuda y el motivo o el mecanismo van
    también en `aria-describedby` (`sr-only`), y la ayuda abre el desplegable ▾, para quien no
    tiene ratón;
  - Fuentes → Plataformas: ⓘ con su explicación junto a «Prioridad», «Acceso» y «Ofertas por
    recorrido»;
  - tests: completitud de `agentActions` contra el enum `LaunchBody.action` del OpenAPI (en los dos
    idiomas, sin que falte ni sobre ninguna), el globo con el teclado y con el botón bloqueado, la
    ayuda en el desplegable y los globos de Plataformas. Los tests que buscaban el `title` miran
    ahora la descripción accesible, y los que buscaban el ▾ por `parentElement` usan
    `[data-slot="agent-button"]`;
  - revisión (rol `reviewer`): nombres unificados con `agent.json`, «Por revisar» en vez de
    «Triaje», `handle-requests` pregunta qué encargos hacer, sin nombres de skill en las ayudas de
    Plataformas y el mecanismo de vuelta para lectores de pantalla.
- **Decisiones:** cuando el botón está bloqueado, el globo enseña el motivo y no el mecanismo
  («Abre Claude Code…»), que entonces no ocurriría. Los textos de las acciones viven en la UI y no
  en la API: `label` de `ACTIONS` sigue en español para la CLI y los encargos.
- **Deuda:** la ayuda de «Prioridad» describe el orden actual; la 27.3 la cambia a «puesto sin
  empates» y tendrá que actualizar ese texto. El bundle sigue por encima de 500 kB (aviso ya
  conocido).
- 318 tests de frontend en verde; `tsc` y `pnpm build` limpios; `oxlint` sin avisos nuevos.

### 27.2 · «Experiencia» plegable — 2026-10-23 · Claude Code (Opus 5.5)
- **Por qué:** cada empresa salía entera, con todos sus campos y logros, y recorrer el historial
  obligaba a mucho scroll; dentro de una empresa no se veía dónde acababa un logro.
- **Hecho:**
  - `ExperienceBlock`: cada empresa es un `Collapsible` plegado por defecto. La cabecera es un
    `<button>` (con `aria-expanded` y `aria-controls`) con puesto · empresa, fechas, ciudad y
    «N logros»; subir, bajar y borrar quedan fuera de él y funcionan con la empresa plegada;
  - se abren solas la empresa recién añadida (con el foco en «Empresa») y las que tienen un error
    de validación (`experience.<i>…`), con un aviso de cuántas son;
  - «Desplegar todo / Plegar todo» junto a «Añadir empresa»;
  - las empresas y los logros nuevos llevan una clave local `_key` (contador) que `write` quita
    antes de guardar: lo desplegado sigue a la empresa al reordenar. Al guardar, el servidor
    devuelve la empresa con su id y sin `_key`; un alias id → clave local (emparejado por posición,
    solo para ids que acaban de aparecer) evita que la tarjeta se vuelva a montar plegada;
  - las empresas con errores se apuntan por su clave al llegar los errores (que van por posición),
    y el aviso dice cuántas hay que revisar;
  - tarjetas sin esquinas redondeadas (también la cabecera, el foco y el hover), con su franja de
    color; los logros llevan número («Logro 1»), fondo alterno y una línea fina entre ellos;
  - `TextField` admite `autoFocus`;
  - tests: arranca plegada, desplegar una no abre otras, «Desplegar/Plegar todo», añadir abre y
    enfoca, reordenar mantiene lo desplegado (también con una empresa nueva), plegar conserva un
    cambio sin guardar, un error despliega su empresa y una empresa nueva sigue desplegada tras
    guardarla (sin mandar `_key`). El perfil de prueba tiene dos empresas y los tests que escriben
    en una la despliegan con `openCompany`;
  - revisión (rol `reviewer`): la empresa nueva se plegaba al guardar (corregido con el alias),
    errores desfasados al reordenar, claves estables para los logros nuevos y más contraste en el
    fondo alterno (`bg-muted/25` y `bg-muted`).
- **Decisiones:** sin `sessionStorage` (era opcional): al entrar, siempre plegado. Los campos y
  botones de dentro de la tarjeta conservan sus esquinas: el encargo habla de las tarjetas.
- **Deuda:** los errores de validación de cada campo siguen yendo por posición
  (`experience.<i>.…`, de `useBlockEditor`): si reordenas antes de volver a guardar, un error puede
  quedar en el campo de otra empresa hasta el siguiente guardado.
- 325 tests de frontend en verde; `tsc` y `pnpm build` limpios; `oxlint` sin avisos nuevos.

### 27.3 · Prioridades únicas — 2026-10-23 · Claude Code (Opus 5.5)
- **Por qué:** todas las plataformas entraban con prioridad 5 y el selector dejaba elegir un número
  ya ocupado; con empates, el orden de recorrido lo decidía el nombre. Con más de 10 plataformas,
  la unicidad era imposible.
- **Hecho:**
  - `AgentBrowseSource.priority`: `int | None` (≥ 1, sin tope). Sin valor, una nueva va al final y
    una existente conserva su puesto;
  - `browse.place`: la única función que coloca una plataforma. Una nueva en un puesto ocupado se
    inserta (las siguientes bajan uno), una existente se intercambia, fuera de 1…N da un error con
    el rango, y siempre renumera 1…N. Pasan por ella `save_source` (MCP y `cai sources save`),
    `add_platform` (UI y demo) y `update_settings` (UI). `SaveSourceResult` devuelve `priority` y
    el mensaje dice a quién ha movido;
  - red de seguridad: un `before_flush` en `models/sources.py` rechaza dos `agent_browse` con la
    misma prioridad (`PriorityConflictError` → `conflict`, 409) y nombra la que ya tenía el puesto;
  - `POST /sources/{id}/browse` acepta `expected_priority` (lo manda la UI): si otra pestaña cambió
    el orden, 409, y la UI recarga la lista (`onSettled`);
  - migración de datos `0026`: numera las plataformas por `(prioridad, nombre)`; sin eventos. El
    `downgrade` deja las prioridades en 1…10;
  - UI: el selector ofrece 1…N con quién ocupa cada puesto («3 · InfoJobs (pasará al puesto 5)»).
    «Añadir plataforma» ofrece «antes de X» o «la última» (por defecto), y sin elegir no manda
    `priority`. La ayuda ⓘ de «Prioridad» (deuda de la 27.1) explica el intercambio;
  - docs: `FUENTES_OFERTAS.md`, `AGENT_INTERFACE.md` y `DATA_MODEL.md`. En los skills,
    `search-jobs` explica la regla y `broaden-search` ya no reenvía `priority`, para no deshacer
    el orden del usuario;
  - tests:
    - servicio: alta al final, más de 10, inserción, intercambio, conservar sin `priority`, fuera
      de rango, desactivar conserva el puesto, conflicto por pestaña desfasada, huecos y datos
      antiguos, red de seguridad;
    - migración 0026;
    - API: intercambio, 409 y 422;
    - paridad: `source-save-swap` y `source-save-out-of-range`;
    - frontend: ocupantes, aviso, reordenar, 409 que recarga, y el alta por defecto «la última»;
  - revisión (rol `reviewer`): el alta ya no manda «la última» calculada en la UI, `check_priority`
    no compara si el servidor no tiene prioridad, el listener ignora `bool` y las borradas, y la
    migración y el servicio ordenan igual lo que no tiene prioridad.
- **Decisiones (confirmadas por el usuario):**
  - intercambio en vez de rechazo; el servidor solo rechaza un empate como red de seguridad;
  - puesto 1…N sin tope;
  - desactivar la búsqueda con navegador **conserva** el puesto. Las plataformas no se pueden
    borrar: si algún día se puede, `place` cierra el hueco al renumerar.
- **Deuda:**
  - `expected_priority` solo protege a la plataforma que se mueve. Si otra pestaña cambió a la
    que ocupaba el puesto, el intercambio se hace con la que esté ahí ahora. El orden sigue sin
    empates, y la lista recargada lo enseña;
  - un agente con skills antiguos que mande `priority: 5` con menos de 5 plataformas recibe
    `invalid_request` con el rango.
- 2877 tests de backend (en Windows se saltan 12 de macOS y Linux) y 329 de frontend en verde;
  ruff, `tsc`, `pnpm build` y `sync_agents.py --check` limpios; `oxlint` sin avisos nuevos;
  OpenAPI regenerado.

### 27.4 · Alertas con varios buzones — 2026-10-23 · Claude Code (Opus 5.5)
- **Por qué:** solo se podía leer una cuenta de correo, configurada a mano en `.env`, y la pantalla
  vacía de Alertas mandaba a editar `.env` sin más ayuda.
- **Hecho (27.4a, backend):**
  - ADR-045. Tablas `mail_sources` y `mail_source_changes` (migración 0027). La cuenta
    `CAI_IMAP_*` aparece sola como «Principal» (`from_env`, lee respuestas) y sus datos siguen en
    `.env`;
  - `core/env_file.py`: contraseñas solo en `.env`, una variable por buzón
    (`CAI_IMAP_<ALIAS>_PASSWORD`, sin pisar una que ya exista), escritas de forma atómica, con un
    candado y permisos 600 fuera de Windows. Las lee sin expandir `${…}`. En Docker no se escriben:
    la respuesta dice qué línea añadir. En los tests, `CAI_ENV_FILE` apunta a una carpeta
    temporal;
  - `services/mail_sources.py`:
    - altas, cambios (validando el buzón entero) y bajas, que quitan su línea de `.env`;
    - prueba de conexión antes y después de guardar (login y `EXAMINE`);
    - servidor sin esquema; ni IP privadas ni locales salvo `allow_private`, también tras resolver
      el nombre;
    - en una demo, ningún IMAP;
  - `mailboxes.py`:
    - recibe una `ImapAccount` (con la contraseña fuera del `repr`);
    - STARTTLS con el certificado verificado;
    - usuario o contraseña con tildes o ñ: error claro (antes, excepción sin capturar);
  - `poll_email` lee todos los buzones activos uno detrás de otro: el fallo de uno queda en su
    `last_error` y no frena a los demás, con un tope de 5 minutos por pasada y sin duplicar por
    `Message-ID`. `replies` solo lee los que tienen `read_replies`. `cai doctor` gana «Buzones»;
  - API `/mail-sources` (`require_ui`) y la herramienta MCP de solo lectura `list_mail_sources`
    (con `cai mail-sources list` y, solo en la CLI, `cai mail-sources test`), en el `auto_allow`
    del manifiesto;
  - los errores de validación nunca repiten un campo `password` ni una entrada que lo contenga
    (`core/validation.py`);
  - docs: `FUENTES_OFERTAS`, `DATA_MODEL`, `AGENT_INTERFACE` y `POLICIES`.
- **Hecho (27.4b, UI y guías):**
  - Alertas:
    - «Añadir buzón» y panel plegable «Buzones» con última lectura, último error y su ayuda,
      interruptor, «Probar», «Editar» y «Quitar» (con confirmación);
    - el panel se abre solo si hay un error;
    - la pantalla vacía lleva al botón;
    - los atajos J/K/O/D no actúan con el diálogo abierto ni con el foco en el panel;
  - asistente con pestañas Gmail · Outlook/Hotmail · Yahoo · iCloud · Otro (IMAP) · Carpeta de
    `.eml`:
    - servidor ya puesto, pasos y enlaces oficiales (comprobados el 2026-10-23) y la sección de la
      guía;
    - «Probar conexión» antes de guardar;
    - Outlook propone reenviar a Gmail o exportar `.eml`, con IMAP plegado como último recurso;
  - `Switch` pasa a ser un componente común (Plataformas y Alertas). Namespace `mailboxes` en es y
    en;
  - `docs/CONFIGURAR_CORREO.md` reescrita con una sección por proveedor y la cuenta de `.env`;
    `GUIA.md` y `GUIDE.md` a la vez.
- **Revisión (rol `reviewer`):**
  - la contraseña salía en el 422 (bloqueante, corregido);
  - separadores Unicode que partían `.env`;
  - `last_run_at` frenado por un buzón roto;
  - variable de `.env` ya existente;
  - atajos con el foco en el panel;
  - etiqueta en blanco y nombres de carpeta reservados de Windows;
  - dos riesgos aceptados en el ADR.
- **Decisiones (confirmadas por el usuario):** contraseñas en `.env`, con el aviso en Docker.
  Outlook, con reenvío o `.eml` e IMAP como último recurso. Proton Bridge no se ofrece: su
  certificado propio no pasa la verificación de TLS.
- **Deuda:**
  - sin OAuth (Gmail y Outlook);
  - la comprobación del servidor y la conexión resuelven el nombre por separado (riesgo aceptado
    en el ADR);
  - la «Principal» se da de alta al listar.
- 2912 tests de backend (12 de macOS y Linux se saltan en Windows) y 335 de
  frontend en verde; `tsc`, ruff, `pnpm build`, `sync_agents.py --check` y `check_links.py`
  limpios; OpenAPI regenerado.

### 27.5 · Preferencias de búsqueda — 2026-10-23 · Claude Code (Opus 5.5)
- **Por qué:** «Mi perfil → Búsqueda» era un solo bloque descuadrado (las etiquetas iban encima del
  campo) y faltaban filtros: años mínimos, sueldo, palabras que descartan (solo en
  `policies.yaml`), contrato, jornada y tipo de empresa. Las ofertas dudosas no se veían.
- **Hecho (27.5a, backend):**
  - ADR-046. Perfil: `min_years_required`, `discard_title_keywords`, `contract_types`,
    `employment_types` y `excluded_employer_kinds`, que vacíos no se vuelcan (mismo YAML y hash);
    coherencia mínimo ≤ máximo y `private.salary_floor_eur` entero > 0 o `null` (sin repetir la
    cifra en el error);
  - filtros duros `salary` (EUR por año o mes ×12; el motivo no lleva cifras), `contract` (con
    `exclude_signals: [fixed_term]` como «no acepto temporal») y `employer_kind` (`is_agency`
    cuenta como `agency`); años con mínimo y la misma tolerancia; palabras del perfil más las de
    `policies.yaml`, también en el filtro previo de las fuentes;
  - extracción: `employer_kind` opcional y el rol `extractor` con cómo distinguirlo;
  - API solo para la UI: `GET`/`PUT /profile/salary-floor` (sin diff) y
    `GET /jobs/{id}/salary-gap`; `GET /profile/editable` trae las palabras y la tolerancia de
    `policies.yaml`;
  - demo con valores para todo; docs `POLICIES`, `DATA_MODEL`, `FUENTES_OFERTAS`,
    `AGENT_INTERFACE`, `GUIA` y `GUIDE`.
- **Hecho (27.5b, la pantalla):**
  - «Búsqueda» en cuatro bloques con su «Guardar»: Puesto, Experiencia y sueldo, Dónde y cómo, y
    Contrato y empresa;
  - `TagsField` con el campo arriba y las etiquetas debajo; ubicaciones en dos columnas como mucho
    y «Solo si no es presencial» con la regla de `Locations.allowed`;
  - años como un rango con la tolerancia en la pista; sueldo con candado y su propio botón;
    casillas de contrato, jornada, tipo de empresa y empresa oculta; «Temporal» es una sola casilla
    y guardar escribe solo `contract_types`;
  - en la ficha, el descarte por sueldo dice cuánto queda por debajo (solo la UI);
  - comprobado con Playwright a 1400 y 375 px, en claro y oscuro, contra una API de demo aparte.
- **Revisión (rol `reviewer`):**
  - 27.5a: un test roto por los valores nuevos de la demo (corregido), `employer_kind` concreto
    frente a `is_agency` (probado) y dos notas en el ADR (el agente podría acotar el mínimo por
    sondeo; los descartes antiguos por temporal siguen como `signal`);
  - 27.5b: el diff de vista previa de una sección enseñaba como contexto las líneas de `private`
    (bloqueante, ya pasaba antes de la fase): ahora `_mask_private` las oculta, con test;
    «Recargar» en el conflicto del sueldo, sin parpadeo al guardarlo, aviso si no se pudo leer,
    unidad asociada al campo y la casilla de empresa oculta sin borrar otras señales.
- **Decisiones (confirmadas por el usuario):** el sueldo mínimo filtra y sigue en `private`;
  ×12 y no ×14; si la oferta solo publica el mínimo, ese cuenta; `employment_type: contract` no
  dice la jornada y pasa.
- **Deuda:** las extracciones antiguas no tienen `employer_kind` hasta que se vuelvan a extraer; sin
  conversión de moneda ni sueldo por horas.
- 27.5a: 2952 tests de backend en tres tandas (los 2 que fallaron, corregidos y repetidos con
  los ficheros tocados: 707 en verde). 27.5b: los de perfil y editor del backend (120) y los 342 de
  frontend en verde; `tsc`, ruff, build y `sync_agents.py --check` limpios; OpenAPI regenerado.

### 27.6 · Descartar desde la Bandeja — 2026-10-23 · Claude Code (Opus 5.5)
- **Por qué:** completar un resumen (abrirlo en LinkedIn y usar la extensión) o extraer una oferta
  cuesta, y no había forma de quitarla desde la Bandeja si el título o la empresa ya no gustaban.
  «Cerrada» solo enseñaba y ordenaba por la fecha de alta.
- **Hecho (27.6a, backend):**
  - `ProjectionState.closed_at`/`closed_by` y sus columnas en `applications` (migración 0028): el
    `occurred_at` y el tipo del evento que cierra; `reopened` los limpia y una nota posterior no los
    mueve. El relleno de la migración va en SQL (el último evento de cierre de cada oferta cerrada)
    y no con `rebuild_projection`, para no depender del código de mañana; sin eventos nuevos;
  - `JobSort` gana `closed` (sin fecha, al final; desempate por fecha de alta) y `JobRow` trae
    `closed_at` y `closed_by`; OpenAPI y `schema.d.ts` regenerados;
  - motivo `not_interested` en `DiscardReason`; el embudo lo cuenta y la calibración no lo ve (solo
    mira enviadas), con test;
  - lote del agente: cada `save_extraction` es una llamada aparte, así que una oferta descartada a
    mitad falla sola con `invalid_transition` (sin extracción a medias) y el resto sigue. La
    transición `extracted` lleva una pista para saltarla y `process-jobs` la cuenta como saltada;
  - `DATA_MODEL`, `GUIA`/`GUIDE` y `CHANGELOG`.
- **Hecho (27.6b, Bandeja):**
  - en «Por completar» y «Por extraer» (solo con ese filtro), «Descartar» por fila en un clic con
    `not_interested`, que oculta la fila ya, avisa con «Deshacer» y la devuelve si la API falla;
    el ▾ abre el diálogo de siempre para otro motivo; nombre accesible con el título;
  - casillas y «Descartar N» (uno a uno en serie, con un «Deshacer» para todas); los descartes
    seguidos se acumulan en el mismo aviso; «Abrir» en el portal en «Por completar»;
  - con `stage=closed`, columna «Cerrada» (relativa, con fecha y evento en el `title`) y las dos
    cabeceras ordenan; en el móvil, «Cerradas hace menos / más». Un `sort=closed` con otra etapa
    se ignora. El orden por defecto sigue siendo «Alta».
- **Revisión (rol `reviewer`):** sin bloqueantes. Aplicado: los descartes seguidos ya no pisan el
  «Deshacer» anterior, un `reopened` que falla se queda en el aviso para reintentarlo, la celda de
  la casilla no abre la ficha y la pista de `extracted` no da por hecho que esté cerrada.
- **Decisiones (confirmadas por el usuario):** descarte en un clic con ▾ para otro motivo; motivo
  nuevo `not_interested` en lugar de `company` u `other`; con selección múltiple.
- **Deuda:** `tracking.py` recalcula cómo se cerró cada oferta releyendo eventos; podría leer
  `applications.closed_by`. Una oferta oculta que se reabre desde la CLI con la Bandeja abierta no
  reaparece hasta cambiar de vista. Sin atajos de teclado en la Bandeja (los de Alertas siguen allí).
- Backend: 2971 tests en verde, 12 saltados (los de macOS y Linux) y 2 rotos por la revisión
  cabeza nueva (`test_cli_db`), corregidos y repetidos junto con los tocados tras la revisión (326 en
  verde). Frontend: 349 en verde y los 17 de la Bandeja repetidos tras la revisión. `tsc`, ruff,
  oxlint (sin avisos nuevos) y `sync_agents.py --check` limpios; OpenAPI regenerado.

### 28.1 · Auditoría y primera release — 2026-10-23 · Claude Code (Opus 5.5)
- **Por qué:** el repo ya es público, no había ninguna release (el comando de instalación del README
  daba 404), el historial no se había escaneado y los instaladores ejecutaban lo descargado sin
  verificarlo.
- **Hecho:**
  - auditoría (`dev/pruebas/fase-28.1-auditoria.md`): gitleaks y trufflehog sobre todas las
    ramas, sin secretos (un falso positivo de un test); ningún dato personal del perfil en el árbol
    ni en el historial; capturas, GIF y vídeos, todos de la demo;
  - GitHub: escaneo de secretos, protección de push, alertas y actualizaciones de Dependabot y aviso
    privado de vulnerabilidades activados por `gh api`; `.github/dependabot.yml` (uv, pnpm y
    Actions, agrupado y semanal), `CODEOWNERS` y `SECURITY.md` con el enlace al aviso privado y el
    alcance de la suma; commits desde ahora con el correo noreply;
  - `release.yml` publica `candidatai.zip.sha256`; `install.ps1` e `install.sh` la descargan y la
    comprueban antes de descomprimir (con zip local, si está al lado), con
    `-SkipChecksum`/`--skip-checksum`. En PowerShell 5.1 la suma va con .NET: `Get-FileHash` respeta
    `-WhatIf` y no calcula nada;
  - `CHANGELOG.md`: la `0.1.0` (nunca publicada) y «Sin publicar» juntas en una sola `0.1.0`,
    reescrita para quien usa la app;
  - README: distintivos de CI y última release en lugar del fijo de tests; sin cifras de tests ni de
    ADR; `test_readme_numbers.py` comprueba que las del eval coinciden con `evals/REPORT.md`;
  - guías (es/en) con la comprobación de la suma.
- **Revisión (rol `reviewer`):** sin bloqueantes. Aplicado: `SECURITY.md` explica que la suma
  detecta descargas corruptas o alteradas, no una release comprometida; el aviso de zip local sin
  suma dice dónde conseguirla; fuera el correo noreply de los docs.
- **Decisiones (con el usuario):** `v0.1.0` es la primera versión publicada y recoge todo; no se
  reescribe el historial por el correo; los ajustes de GitHub los activa el agente.
- **Deuda:** `install.sh` se ejecuta con `curl | bash` desde `main`, sin verificar (lo habitual);
  los patrones genéricos y la validez del escaneo de secretos requieren GitHub Advanced Security.
- **Demo de una app instalada (2026-10-24):** se guardaba en `app/data-demo`, y `app/` se sustituye
  entera al actualizar, así que se perdía. `config.data_root()`: en una app instalada (`app/` con la
  marca `.candidatai` de los instaladores en la carpeta de arriba), una carpeta de datos relativa
  (`CAI_DATA_DIR=data-demo`, `cai demo seed --dir`) se resuelve junto a `data/`; en el repositorio,
  como siempre. `cai demo seed` dice cómo abrirla con `cai start` y la guía lo explica. Probado con
  una instalación de verdad: la demo sobrevive a la actualización. Decisión del usuario: la demo se
  mantiene para quien usa la app (no solo para desarrollo).
  Además, los instaladores ignoran un `CAI_DATA_DIR`/`CAI_DB_URL` de la terminal (la demo abierta
  en la misma ventana) al preparar la base de datos, y en Windows la variable vuelve como estaba.
- **Pendiente:** fusionar, etiquetar `v0.1.0` y la prueba manual de `fase-28.1-prueba-manual.md`
  (Windows Sandbox, WSL, Docker; macOS por la CI). Ya probado: empaquetado local, instalación en
  Windows desde ese zip con suma, `cai doctor`, reinstalar conservando datos y suma alterada
  rechazada; tests de `install.sh` en un contenedor Linux.

### 28.2 · Raíz limpia — 2026-10-24 · Claude Code (Opus 5.5)
- **Por qué:** la raíz y `docs/` enseñaban al visitante lo interno (87 encargos, el ROADMAP de
  240 KB, los ADR, las pruebas manuales) y GitHub no deja ocultar carpetas.
- **Hecho:**
  - `git mv` a `dev/`: `prompts/` → `dev/prompts/`, `docs/pruebas/` → `dev/pruebas/`, y `ROADMAP`,
    `RESUMEN_FASES`, `DESARROLLO_POR_FASES` y `DECISIONS` a `dev/`. `docs/` se queda con lo de
    quien usa la app o contribuye; `evals/`, las carpetas de agentes y los instaladores no se mueven;
  - referencias reescritas en 120 ficheros con un script de un solo uso (`--dry-run`): menciones
    en texto o código (`prompts/` solo si no va tras `/`, para no tocar `/prompts/pending` ni
    `cai prompts`) y enlaces Markdown relativos, recalculados desde la ubicación nueva. Incluye
    `AGENTS.md`, el skill `implement-phase` (regenerados `.claude/` y `.qwen/`), las guías y los
    README en los dos idiomas, `SECURITY.md`, `CONTRIBUTING.md` y dos comentarios del backend;
  - índices: `dev/README.md` (nuevo: lo interno y qué es cada carpeta de la raíz), `docs/README.md`
    enlaza a él en vez de listar lo interno, `AGENTS.md` cita los dos; `.agents/README.md` explica
    que es la fuente única y que lo demás se genera;
  - `scripts/check_links.py` revisa también `dev/` y `.agents/` (salvo `dev/prompts/`, que cita
    rutas futuras) y la CI lo ejecuta en el job de backend (los tres sistemas);
  - `.gitattributes`: `dev/**` y `docs/**` como `linguist-documentation`; `openapi.json`,
    `schema.d.ts` y lo que genera `sync_agents.py` como `linguist-generated`; `dev/` con
    `export-ignore`.
- **Revisión (rol `reviewer`):** sin bloqueantes. Aplicado: `check_links.py` salta solo
  `dev/prompts/` (no cualquier carpeta `prompts`) y los dos índices dicen que `dev/` no va en el zip.
- **Decisiones (con el usuario):** `dev/` fuera del zip de la release (en la copia instalada, los
  enlaces a `dev/` de README, guías y `AGENTS.md` no resuelven; en GitHub sí); el script de
  movimiento no se queda en el repo (este registro lo describe).
- **Deuda:** `check_links.py` revisa el árbol, no el zip. La barra de lenguajes solo se ve tras el
  push.
- **Pendiente:** comprobar en GitHub la portada y la barra de lenguajes (`PENDIENTES.md`).

### 28.3a · Lista de funcionalidades y comprobación — 2026-10-24 · Claude Code (Opus 5.5)
- **Por qué:** el README se había quedado atrás (Calendario, Respuestas, varios buzones, «Mi perfil»
  y «Búsqueda», prioridades de plataformas, descartar desde la Bandeja, ayudas de los botones…) y
  nada impedía que volviera a pasar.
- **Hecho:**
  - `docs/FEATURES.md` y `docs/FUNCIONALIDADES.md`: cada funcionalidad en una frase, en el orden
    del recorrido (conseguir ofertas → triar → CV y carta → candidatar → seguimiento y respuestas →
    entrevistas y ofertas → estrategia y perfil → ajustes y agentes), con su página (ruta) o su
    skill y la captura que ya existe. Sacadas de las rutas de `App.tsx`, los skills, el resumen
    de fases y el CHANGELOG;
  - los dos README enlazan a su lista tras «Qué hace» (con lo que el resumen deja fuera) y en
    «Documentación»; `docs/README.md` también;
  - `scripts/check_readme_coverage.py`, en la CI: falla si una página de `App.tsx` (sin
    redirecciones ni la ruta que solo agrupa las pestañas de Fuentes) o un skill falta en alguna de
    las dos listas, si un README no enlaza a la suya, si se cita un nombre con guiones que no es un
    skill (excepciones explicadas: plantillas y el nombre antiguo `generar-cv`) o si los dos README
    no tienen las mismas secciones ni los mismos desplegables. `implement-phase` no cuenta (es de
    desarrollo);
  - `test_readme_coverage.py`: el repo pasa y cada forma de romperlo se detecta, sobre una copia.
- **Revisión (rol `reviewer`):** sin bloqueantes. Aplicado: las dos listas tienen que coincidir
  fila a fila (mismas filas por sección y lo mismo en «Dónde»); el análisis de rutas ignora `<Routes>`
  y los comentarios JSX, acepta `Component=` y `lazy=` y avisa si las etiquetas no cuadran; tests
  con un `App.tsx` sintético, redirecciones y excepciones; `AGENTS.md` cita las listas y las suma
  a la regla bilingüe; la mención al script en las listas pasa a un comentario. Sin aplicar:
  comparar también tablas e imágenes de los README (bastan encabezados y desplegables).
- **Mejoras de UI que salen del inventario** (no caben en una frase o no tienen pantalla):
  - la página «Agente» mezcla dos cosas: ajustes (agente por acción, niveles de gasto, umbral) y el
    seguimiento de las ejecuciones;
  - «Ofertas recibidas» vive dentro de Procesos, sin entrada propia en la barra lateral;
  - `cai sources discover` (encontrar el tablero de tus empresas) solo existe en la terminal.
- **Deuda:** la columna de capturas está a medias hasta la 28.3b (páginas sin captura: Alertas,
  Calendario, Respuestas, Mi perfil, alta de oferta). La 28.3b puede hacer que el script exija una
  captura por página.

### 28.3b · Medios nuevos — 2026-10-25 · Claude Code (Opus 5.5)
- **Por qué:** las capturas, los GIF y el vídeo eran de la fase 23 y no enseñaban media app
  (Alertas con buzones, Calendario, Respuestas, Mi perfil, descartar desde la Bandeja…).
- **Hecho:**
  - `scripts/readme_media/`: `screenshots.py` (24 capturas por idioma a 1600×1000 en WebP, 5 en
    oscuro), `recordings.py` (seis escenas de menos de 20 s con leyenda: `triage`, `discard`,
    `mailbox`, `cv`, `profile` y `apply`, en WebP animado), `all.py` (todo un idioma de una vez,
    con su demo, API y worker) y `apply-form.html` (formulario local para `apply`, con
    `CAI_APPLIER_ALLOW_LOOPBACK=1` solo en esa demo). Su `README.md`, reescrito;
  - banner, diagrama «cómo funciona» e imagen social (`social-en.png`, 1280×640) rehechos;
  - los dos README y las dos listas apuntan a los medios nuevos, con `alt` en cada imagen; los
    README suman «Candidatura asistida», «Alertas y respuestas» y «Mi perfil», y pierden el vídeo
    y `start.gif`. Borrados los PNG, GIF y MP4 viejos (el historial no se reescribe);
  - `check_readme_coverage.py` exige una captura por página en cada lista;
  - la demo trae 5 ofertas de alertas en dos buzones (65 en total), para que «Alertas» no salga
    vacía.
- **Decisiones (del usuario):** nada de vídeos ni YouTube; al final, tampoco tour. Medios
  generados y revisados por el usuario fuera de Claude Code.
- **Revisión (rol `reviewer`):** sin bloqueantes. Aplicado: quitar de `PENDIENTES.md` el punto del
  vídeo. Sin aplicar: la entrada de la 23.5b sigue nombrando los medios viejos (es historia).
- **Deuda:** `docs/img` pesa 7,98 MB, al límite de los 8 MB del presupuesto: una captura más pide
  comprimir las animaciones. La escena `start` sigue en `recordings.py` pero no se usa.
- 2999 tests de backend en verde en cuatro tandas (14 saltados, los de macOS y Linux); uno que
  esperaba la demo de 60 ofertas, corregido. Sin cambios en el frontend. Ruff, `sync_agents.py
  --check`, `check_links.py`, `check_readme_coverage.py` y `release_notes.py --check` en verde.

### 28.4 · Portada y GitHub — 2026-10-25 · Claude Code (Opus 5.5)
- **Por qué:** la primera pantalla del README enseñaba un banner, ocho distintivos y arquitectura
  antes que la app; el comando de instalación iba a la mitad; no decía por qué elegirla ni que hace
  falta un agente de IA, la mayor fricción para quien no es técnico.
- **Hecho (28.4a):**
  - `README.md` y `README.es.md` de unas 420 a 215 líneas, con las mismas secciones: promesa,
    animación del triaje y tres botones (Windows, macOS/Linux, Docker) en la primera pantalla;
    distintivos solo dinámicos (versión, CI, licencia); nota «En qué punto está» con lo probado de
    verdad; «Lo que necesitas» (el agente incluido); «Por qué CandidatAI», tabla corta con fecha y
    fuentes frente a AI Job Search y career-ops (vueltos a mirar con `gh` el 25-10) y lo que ellos
    hacen mejor; instalar, garantías, cómo funciona y la línea del eval. Las tablas de skills,
    fuentes y agentes, los diagramas y las decisiones salen del README (están en las listas de
    funcionalidades, `docs/` y `dev/DECISIONS.md`);
  - `docs/START_HERE.md` y `docs/EMPEZAR.md`: qué necesitas, con una tabla de agentes (coste,
    adónde van tus datos, qué tal funciona aquí; precios de Claude Pro y ChatGPT Plus comprobados
    hoy), instalación paso a paso (SmartScreen: con el comando no sale; «Desbloquear» si el `.ps1`
    se baja con el navegador), la suma a mano, la página «Agente» para instalar el tuyo, la demo,
    crear el perfil con `update-profile`, la primera búsqueda y preguntas frecuentes;
  - enlaces desde `docs/README.md` y las dos guías de uso; `AGENTS.md` suma las guías nuevas a la
    regla bilingüe y deja `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` y `.github/` solo en inglés;
  - `test_readme_coverage.py` adaptado al README corto y fuera la excepción `generar-cv`, que ya
    no se cita.
- **Hecho (28.4b):** `CONTRIBUTING.md` en inglés (una línea en español) con el entorno y tres
  caminos fáciles: conector de ATS, idioma de la UI y probar un agente con `cai eval compat`;
  `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1, avisos por el formulario privado de GitHub);
  `.github/ISSUE_TEMPLATE/` (fallo, idea, «Works with my agent» y `config.yml` sin incidencias en
  blanco) y `PULL_REQUEST_TEMPLATE.md`; `dev/pruebas/fase-28.4-github.md` con los ajustes de la web
  (descripción, sitio, temas, imagen social, etiquetas, Discussions y categorías), 10 incidencias
  redactadas, la decisión sobre Pages y la prueba con un lector.
- **Revisión (rol `reviewer`):** sin bloqueantes. Aplicado: OpenCode sí se probó (con un 20B local
  que no terminó), dicho así en la portada y las guías; aviso de `--force` si la demo ya existe; la
  interfaz real del conector (`FetchResult`, `complete()`, `_ATS_DOMAINS`) y las claves de
  referencia (`es/`) en `CONTRIBUTING.md`; el aviso privado activado en la 28.1, anotado.
- **Decisiones (del usuario):** los ajustes públicos de GitHub los hace el usuario con la lista; «Mi
  búsqueda en números» se queda en hueco (cifras reales del 9 al 24-10: 2 candidaturas, aún poco
  para gancho); `CONTRIBUTING.md` solo en inglés; conducta por el aviso privado de GitHub. GitHub
  Pages: recomendado no por ahora (decide el usuario).
- **Deuda:** las capturas de la guía son de la app, no del instalador en la terminal; los enlaces a
  Discussions dan 404 hasta activarlas; la tabla «Por qué» caduca: revisarla con la comparativa.
- **Pendiente:** los ajustes de la web y la prueba con un lector no técnico (cierra la subfase).
- Sin cambios de código de la app. Tests de README, CHANGELOG, `sync_agents` y configuración (89)
  en verde; ruff, `sync_agents.py --check`, `check_links.py`, `check_readme_coverage.py` y
  `release_notes.py --check` limpios. La suite completa no se ha ejecutado (solo cambian docs, un
  test y una excepción del script).
