# Funcionalidades

Todo lo que hace CandidatAI, en el orden en que lo usas: conseguir ofertas → revisar → CV y carta →
candidatar → seguimiento y respuestas → entrevistas y ofertas → estrategia y perfil → ajustes y
agentes. Versión en inglés: [`FEATURES.md`](FEATURES.md).

**Dónde** es la página de la UI (su dirección tras `http://127.0.0.1:8000`) o el **skill** que
ejecuta tu agente (`/generate-cv 42` en Claude Code, `$generate-cv 42` en Codex, o pidiéndolo sin
más). Casi todos los skills tienen además un botón en la UI que abre tu agente con la orden, en una
terminal o en segundo plano. Nada sale hacia una empresa sin que lo confirmes.

<!-- scripts/check_readme_coverage.py falla si aquí falta una página o un skill, o si esta lista y
FEATURES.md dejan de coincidir fila a fila. -->


## 1. Conseguir ofertas

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Alta de una oferta** pegando su URL o su texto; los duplicados se detectan y apuntan a la original | `/nueva` | [Alta](img/es/new-job.webp) |
| **Bandeja**: todas las ofertas con filtros, búsqueda, señales y etapa; las que están por completar o por extraer se quitan con **Descartar** y **Deshacer**; «Cerrada» con su fecha, ordenable | `/bandeja` | [Bandeja](img/es/inbox.webp) · [▶ Descartar](img/es/anim/discard.webp) |
| **Empresas objetivo**: sus ofertas llegan cada día desde Greenhouse, Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters y Recruitee (APIs públicas, sin scraping); «Probar» dice cuántas pasan tus filtros | `/fuentes/empresas` | [Empresas](img/es/sources-companies.webp) |
| **Plataformas**: los portales que recorre tu agente, cada uno con su prioridad (sin empates), su acceso y sus ofertas por recorrido, explicados con su ⓘ; InfoJobs y Adzuna con claves, Manfred y freehire.me sin ellas | `/fuentes/plataformas` | [Plataformas](img/es/sources-platforms.webp) |
| **Buscar en portales con tu navegador**: tu agente recorre tus búsquedas, con límites de páginas y pausas, da de alta lo que encaja y para ante captchas | `search-jobs` | |
| **Alertas de empleo por correo**: las de LinkedIn, InfoJobs, Indeed… entran solas, por IMAP en solo lectura o desde ficheros `.eml`; **varios buzones**, con guía paso a paso para Gmail, Outlook, Yahoo e iCloud; las ofertas resumen caducan a los 21 días | `/alertas` | [Alertas](img/es/alerts.webp) · [▶ Añadir buzón](img/es/anim/mailbox.webp) |
| **Botón «Enviar a CandidatAI»**: extensión de Chrome/Edge que manda la oferta que estás viendo (LinkedIn incluido) o completa el resumen de una alerta | [`extension/`](../extension/README.md) | |
| **Búsqueda pública de LinkedIn** (apagada por defecto, bajo tu riesgo): una vez al día, sin tu cuenta ni cookies; tu agente no puede activarla | `/fuentes/plataformas` | |
| **Encontrar el tablero de empleo de tus empresas** a partir de una lista de nombres | `cai sources discover` | |
| **Extraer cada oferta** a datos estructurados con un subagente aislado que solo ve esa oferta; el texto dirigido a una IA se marca y nunca se obedece | `process-jobs` | |
| **¿Sigue abierta? y republicadas**: la app comprueba si una oferta sigue publicada (nunca la cierra sola) y marca «Republicada ×N» | `/jobs/:id` | |
| **Ofertas dudosas a la vista**: rango salarial muy amplio, empresa oculta o agencia, contrato temporal, publicada hace meses y cribado con IA, cada una explicada; no cambian el score | `/bandeja` | |

## 2. Revisar

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Inicio**: lo que te espera hoy (ofertas por procesar o valorar, respuestas, seguimientos), las que mejor encajan, las listas para enviar y los próximos hitos | `/` | [Inicio](img/es/home.webp) |
| **Filtros duros y un score 0-100 explicado**: nivel, años, modalidad, zona, idiomas y palabras de descarte; cobertura de skills ponderada por tu nivel, preferencias y similitud semántica local opcional | `/por-revisar` | [Por revisar](img/es/triage.webp) |
| **Revisar con el teclado**: `J`/`K` para moverte, `A` aprobar, `D` descartar con motivo, `O` abrir, y Deshacer | `/por-revisar` | [▶ Teclado](img/es/anim/triage.webp) |
| **El veredicto de tu agente**: encaje con riesgos y preguntas, citando tus deal-breakers; en segundo plano se salta las de poco score | `assess-fit` | |
| **«Conoces a N personas aquí»**: tus contactos de LinkedIn (exportación oficial en CSV) cruzados con cada empresa | `/jobs/:id` | |
| **La ficha de la oferta**, en pestañas (Oferta, Candidatura, Proceso, Empresa, Historial y notas) que se abren en la que toca según la fase: extracción, desglose del encaje, señales, historial, notas, coste en tiempo de agente y todas las secciones de abajo | `/jobs/:id` | [Ficha](img/es/job.webp) |

## 3. CV y carta

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **CV a medida**: tu agente lo redacta citando la evidencia de tu perfil de cada línea; el código rechaza lo que no está y otro rol lo verifica; la ficha avisa con el PDF en cuanto está | `generate-cv` | |
| **El mismo contenido, cualquier diseño**: plantilla, foto, color y secciones en la ficha, renderizado en segundos sin agente; comparas renders y marcas el que envías; la maquetación del PDF se revisa | `/jobs/:id` | [CV](img/es/job-cv.webp) · [▶ Otro diseño](img/es/anim/cv.webp) |
| **Carta de presentación** según tus indicaciones generales y las de cada oferta, verificada, en TXT y PDF a juego con el CV; la puedes retocar a mano | `generate-cover-letter` | [Carta](img/es/job-letter.webp) |
| **Plantillas de CV**: integradas (Word y HTML) y las tuyas; «Mi CV» al lado de tu perfil | `/plantillas` | [Plantillas](img/es/templates.webp) |
| **Importar tu propio diseño de CV** desde Word, PDF, una imagen, HTML, Canva o Google Docs como plantilla | `import-cv-template` | |

## 4. Candidatar

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Paquete de candidatura**: el CV elegido, las respuestas de screening con un botón de copiar cada una y la carta; el salario y lo que no esté en tu perfil quedan para ti | `prepare-application` | [Paquete](img/es/job-package.webp) |
| **Candidatura asistida**: la app rellena formularios de Greenhouse, Lever, Ashby o genéricos en su propio navegador, se para antes de enviar, enseña qué rellenó y de dónde sale, y **solo envía cuando escribes el nombre de la empresa** | `/jobs/:id` | [▶ Candidatura asistida](img/es/anim/apply.webp) |
| **Correos de candidatura y mensajes de LinkedIn** (≤ 300 caracteres) para el recruiter, el responsable o un compañero, guardados como borradores que envías tú | `draft-message` | |
| **Archivo de lo que enviaste**: CV, carta, respuestas y un README en su carpeta, sin cambios si rehaces el CV después | `/jobs/:id` | |

## 5. Seguimiento y respuestas

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Procesos**: un kanban que solo se mueve con eventos registrados (ratón, teclado o táctil), las ofertas recibidas lado a lado y los avisos de seguimiento | `/procesos` | [Procesos](img/es/processes.webp) |
| **Ficha del proceso**: hitos con fecha y hora (se editan, se cancelan o, si los anotaste por error, se borran), contactos y referencias, borradores y lo que ha pasado | `/jobs/:id` | [Proceso](img/es/job-interview.webp) |
| **Calendario**: entrevistas, pruebas y plazos, con un `.ics` por hito y un feed para Google Calendar | `/calendario` | [Calendario](img/es/calendar.webp) |
| **Respuestas de las empresas**: la app lee tu correo en solo lectura y guarda solo los de las empresas a las que te has presentado | `/respuestas` | [Respuestas](img/es/replies.webp) |
| **Clasificar las respuestas**: tu agente propone entrevista (con su fecha), prueba, oferta, rechazo o nada; nada cambia de etapa hasta que aceptas | `review-replies` | |
| **Seguimientos y agradecimientos** como borradores (como mucho 2 seguimientos por candidatura) | `draft-follow-up` | |

## 6. Entrevistas y ofertas

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Investigar la empresa** con fuentes: producto, noticias, cultura de ingeniería, stack y banderas rojas | `research-company` | [Dosier](img/es/job-research.webp) |
| **Preparar la entrevista**: una guía en PDF y un plan por días, que se ven bajo la entrevista; cada ronda con su tipo (RR. HH., técnica, caso, final) y tus indicaciones, que también usa el simulacro | `prepare-interview` | [Plan](img/es/job-interview.webp) |
| **Simulacro de entrevista**: una pregunta cada vez, feedback concreto y una respuesta mejor solo con tu perfil | `mock-interview` | |
| **Repaso**: notas y próximos pasos, la siguiente ronda predicha y historias STAR nuevas propuestas; con una oferta recibida, qué aclarar antes de aceptar | `debrief-interview` | |
| **Ofertas recibidas** comparadas con tu mínimo y con el rango publicado, **sin que tu agente vea nunca tu mínimo** | `/procesos` | [Oferta recibida](img/es/job-offer.webp) |
| **Negociación**: argumentos sacados de tu perfil, preguntas, un guion con la cifra para que la pongas tú y revisión del contrato cláusula a cláusula (no es asesoramiento legal) | `prepare-negotiation` | |

## 7. Estrategia y perfil

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Embudo**: conversión paso a paso, por fuente, puesto, semana, plantilla, carta y referencia, tiempo hasta la primera respuesta y motivos de descarte | `/embudo` | [Embudo](img/es/funnel.webp) |
| **«¿Acierta el score?»**: tasas de respuesta y de entrevista por score, veredicto, fuente, plantilla, carta y referencia, con intervalos al 95 %, en «Más análisis» del Embudo | `/embudo` | |
| **Tu búsqueda en números**, lista para compartir (solo cifras, nunca empresas), en «Más análisis» del Embudo | `/embudo` · `cai stats story` | |
| **Retrospectiva semanal**: qué funciona y qué cambiar, sin tocar pesos ni filtros | `review-search` | |
| **Skills**: lo que piden tus ofertas y tu perfil no cubre; sinónimos «Es lo mismo que…», «La tengo» y «No la tengo», de 25 en 25 | `/skills` | [Skills](img/es/skills.webp) |
| **Plan de formación** con recursos verificados para tus huecos reales, y valoración de un curso o proyecto | `training-plan` | |
| **Ampliar la búsqueda** con títulos de puesto cercanos a lo que apruebas y descartas | `broaden-search` | |
| **Mi perfil, editable**: experiencia plegable y logros, proyectos, formación, skills, historias STAR, preferencias de **Búsqueda** (años, sueldo mínimo privado, palabras que descartan, contrato, tipo de empresa), preferencias de CV y carta, contexto y muestras de estilo; conserva los comentarios de tu fichero, con Deshacer | `/perfil` | [Experiencia](img/es/profile-experience.webp) · [Búsqueda](img/es/profile-search.webp) · [▶ Plegable](img/es/anim/profile.webp) |
| **Crear o actualizar tu perfil** desde tu CV o lo que le cuentes a tu agente | `update-profile` | |
| **Ampliar tu perfil** desde tu GitHub, portfolio, Kaggle o Scholar públicos, cada cosa con su fuente y solo con tu OK | `expand` | |
| **Revisión de tu perfil de LinkedIn** frente a tu perfil y a las ofertas que apruebas | `review-linkedin` | |

## 8. Ajustes, agentes y la app

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Agente**: agente por defecto y uno por acción, ejecuciones en segundo plano con progreso, preguntas y Cancelar, coste por acción y modelo, niveles de gasto y la comparación por significado del score | `/agente` | [Agente](img/es/agent.webp) |
| **Cada botón de agente se explica**: qué hace el skill, qué cambia y qué necesita, al pasar el ratón o con el foco del teclado | Todas las páginas | |
| **Dejar para tu próxima sesión**: cualquier botón guarda la orden para tu agente | `handle-requests` | |
| **Resumen del día**: ofertas pendientes, seguimientos vencidos y próximos hitos | `daily-summary` | |
| **Barra lateral** agrupada y plegable con lo que te espera, tema claro y oscuro, español e inglés | `/` | [Barra lateral](img/es/sidebar-collapsed.webp) |
| **Modo demo** con una búsqueda ficticia en la que cada página tiene algo | `cai demo seed` | |
| **Instalación** con una línea en Windows, macOS y Linux, o con Docker; `cai doctor` lo revisa todo | [Guía](GUIA.md) | |
| **Cinco agentes**: Claude Code, Codex, OpenCode, Qwen Code y Antigravity CLI, por MCP o con `cai … --json`; modelos gratuitos y locales | [`AGENTS_COMPAT.md`](AGENTS_COMPAT.md) | |
