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
| **Alta de una oferta** pegando su URL o su texto (con puesto y empresa, y el botón dice qué falta); la misma oferta con otro enlace o un título casi igual no se da de alta otra vez: se anota en la original | `/nueva` | <!-- media:provisional --> [Alta](img/es/new-job.webp) |
| **Bandeja**: todas las ofertas con filtros (etapa, en «Todas» **varias etapas a la vez** con casillas, **modalidad**, **con o sin salario** y **encaje**: sin encaje o de 50, 70 u 85 o más), búsqueda, señales y etapa; cada etapa explica qué es y qué hacer para avanzar, con su botón; las que están por completar o por leer se quitan con **Descartar** y **Deshacer**; «Cerrada» con su fecha, ordenable, y su **motivo** (descartada, no pasó los filtros, rechazada, retirada, caducada, cerrada por la empresa, duplicada o aceptada), que también filtra; **Reabierta** en las vacantes que vuelven tras cerrarlas la empresa, y aviso **Ha vuelto a publicarse** (Reabrir o Ignorar) en las que cerraste tú | `/bandeja` | <!-- media:provisional --> [Bandeja](img/es/inbox.webp) · <!-- media:provisional --> [▶ Descartar](img/es/anim/discard.webp) |
| **Empresas con portal propio**: sus ofertas llegan cada día desde Greenhouse, Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters y Recruitee (APIs públicas, sin scraping). Se añaden con su nombre y la dirección de su web de empleo: la app deduce el sistema y los lugares de la dirección («Solo Madrid»), y solo enseña las ofertas que encajan contigo. Cada empresa tiene un interruptor (Activa o Pausada) y un menú ⋯ con «Buscar ahora», su web y sus lugares | `/fuentes/empresas` | <!-- media:provisional --> [Empresas](img/es/sources-companies.webp) |
| **Portales de empleo** (en «Buscar ofertas → Dónde buscar»): «Configurar con mi agente» te recomienda portales y prepara sus búsquedas; al añadir uno conocido (InfoJobs, Tecnoempleo, Indeed, LinkedIn), las búsquedas salen solas de los puestos y las ubicaciones de tu perfil, y cada portal se puede editar. Los que recorre tu agente, cada uno con su prioridad (sin empates), su acceso y sus ofertas por recorrido, explicados con su ⓘ; InfoJobs y Adzuna con claves, Manfred y freehire.me sin ellas | `/fuentes/plataformas` | <!-- media:provisional --> [Plataformas](img/es/sources-platforms.webp) |
| **Buscar ofertas**, con dos pestañas («Buscar» y «Dónde buscar», cada una con su dirección). En «Buscar», un solo panel con lo que buscas, editable ahí mismo: tus puestos y lugares como etiquetas (cada lugar con lo que aceptas en él), la modalidad y el nivel como chips, y cuántas ofertas por portal; cada cambio se guarda en tu perfil, con «Deshacer», y al añadir un puesto te sugiere los títulos de lo que apruebas que aún no cubres. A la derecha, en qué portales buscará tu agente, cuántas empresas con portal propio se revisan a la vez, cuántas ofertas nuevas como mucho en los portales y «Buscar ahora», que lanza las dos cosas con un clic (sin portales elegidos, solo las empresas). Debajo, tus portales en tarjetas que se marcan, con su estado y lo que dieron la última vez: una barra con las vistas, las que pasan tus filtros, las que ya tenías y las nuevas (de ellas, las reabiertas), y por qué paró («Llegó a lo de la búsqueda anterior», «Alcanzó el límite: quedan 5 sin abrir»). Bajo los portales, tus empresas con portal propio en tarjetas compactas (logo, Activa o Pausada y su último recorrido; hasta ocho, y el resto en «Dónde buscar»). Un aviso dice «Buscando…» en todas las páginas y cambia cuando terminan tu agente y las empresas, con esas mismas cifras sumadas | `/buscar` | <!-- media:provisional --> [Buscar ofertas](img/es/search.webp) |
| **Descartar o cerrar desde la ficha**: en cualquier etapa, sin pasar por el Tablero. Hasta enviarla se descarta con motivo; ya enviada se cierra la candidatura (rechazo, te retiras o caducada). **Reabrir** lo deshace | `/jobs/:id` | |
| **Avisos de tu agente**: lo que lanzas con un botón sale en un aviso en todas las páginas, con lo que lleva hecho, y cambia al terminar. Si necesita saber algo para seguir, te lo pregunta en un aviso y contestas ahí. Lo que va en segundo plano se para desde el aviso con **Detener** (lo ya guardado se queda); lo abierto en una terminal se para cerrando su ventana, y el aviso se cierra con **Marcar como terminada** | todas | |
| **Más ajustes de tu búsqueda**: se despliegan en el mismo panel de «Buscar ofertas», con el número de grupos que tienen algo puesto: años de experiencia, sueldo mínimo (privado), idiomas, contrato y jornada, y lo que descartas (palabras del título, consultoras, agencias, ofertas sin empresa). Se guardan juntos, con «Restablecer», «Descartar cambios» y «Deshacer» | `/buscar/ajustes` | <!-- media:provisional --> [Más ajustes](img/es/search-settings.webp) |
| **Buscar en portales con tu navegador**: tu agente recorre tus búsquedas, con límites de páginas y pausas, da de alta lo que encaja y para ante captchas | `search-jobs` | |
| **Alertas de empleo por correo**: las de LinkedIn, InfoJobs, Indeed… entran solas, por IMAP en solo lectura o desde ficheros `.eml`; **varios buzones**, con guía paso a paso para Gmail, Outlook, Yahoo e iCloud; las ofertas resumen caducan a los 21 días | `/fuentes/correo` | <!-- media:provisional --> [▶ Añadir buzón](img/es/anim/mailbox.webp) |
| **Completar las ofertas resumen**: las que llegan como resumen, una a una: ábrelas en su portal, envíalas con el botón del navegador o descártalas, con `J`/`K`, `O`, `D` y Deshacer; las que no pasan tus filtros, plegadas | `/bandeja/por-completar` | <!-- media:provisional --> [Por completar](img/es/alerts.webp) |
| **Botón «Enviar a CandidatAI»**: extensión de Chrome/Edge/Brave que manda la oferta que estás viendo (LinkedIn, InfoJobs, Indeed, Glassdoor, Manfred, Ticjob y las webs de empleo de empresa con Greenhouse, Lever, Workday, Ashby…) o completa el resumen de una alerta. La pestaña «Botón del navegador» te guía para cargarla, avisa si está desactualizada y la conecta con un clic, sin terminal, y enseña cómo se usa en una animación corta. Si pegas una URL de LinkedIn en «Nueva oferta», te lleva a él o a pegar el texto | `/fuentes/extension` | <!-- media:provisional --> [Botón del navegador](img/es/sources-extension.webp) |
| **Búsqueda pública de LinkedIn** (apagada por defecto, bajo tu riesgo): una vez al día, sin tu cuenta ni cookies; tu agente no puede activarla | `/fuentes/plataformas` | |
| **Encontrar el tablero de empleo de tus empresas** a partir de una lista de nombres | `cai sources discover` | |
| **Leer y valorar las ofertas nuevas en un solo paso** («Valorar las ofertas nuevas»): extrae cada una a datos estructurados con un subagente aislado que solo ve esa oferta y después la valora frente a tu perfil; el texto dirigido a una IA se marca y nunca se obedece | `process-jobs` | |
| **¿Sigue abierta? y republicadas**: la app comprueba si una oferta sigue publicada (nunca la cierra sola) y marca «Republicada ×N» | `/jobs/:id` | |
| **Puntos a revisar en cada oferta**: rango salarial muy amplio, empresa oculta o agencia, contrato temporal, publicada hace meses y cribado con IA, cada una explicada; no cambian el encaje | `/bandeja` | |

## 2. Revisar

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Inicio**: con la app recién instalada, qué hace la app y qué es tu agente, y «Primeros pasos» (sube tu CV para crear tu perfil, o empiézalo a mano, y elige dónde buscar con tu agente); sin ningún agente instalado, «Necesitas un agente de IA» con los pasos para instalar Claude Code; luego, lo que te espera hoy (ofertas por procesar o valorar, respuestas, seguimientos), las que mejor encajan, las listas para enviar y los próximos hitos | `/` | <!-- media:provisional --> [Inicio](img/es/home.webp) |
| **Cómo funciona**: quién hace qué (tú, tu agente y la app), el recorrido completo en cinco pasos con un enlace a cada pantalla y las guías, siempre a mano en el menú | `/como-funciona` | <!-- media:provisional --> [Cómo funciona](img/es/how-it-works.webp) |
| **Ayuda en todas las páginas**: un botón abajo a la derecha (o la tecla `?`) busca en las [preguntas frecuentes](PREGUNTAS.md) y en la guía de uso, sin conexión y sin agente, y cada respuesta lleva a la pantalla donde se hace | Botón «Ayuda» | |
| **Asistente**: un botón con rótulo abajo a la derecha, junto al de ayuda, abre un chat para pedirle algo con tus palabras (Intro envía), con conversaciones independientes y un historial en una barra lateral, como ChatGPT o Claude. Va en segundo plano si tu agente puede (Claude Code, OpenCode o Codex); si no, se abre tu agente en una terminal a la vista y la respuesta llega igual al panel; sin terminal, queda para tu próxima sesión; el panel enseña el progreso, sus preguntas y la respuesta, con enlaces a lo que ha cambiado. Enviar, aprobar, descartar y borrar los confirmas siempre tú | Botón «Asistente», `assistant` | |
| **Filtros duros y un encaje 0-100 explicado** («buen encaje», «encaje posible» o «encaje bajo», y al pasar el ratón qué mide cada parte; sin encaje, la ficha dice qué falta): nivel, años, modalidad, zona, idiomas y palabras de descarte; cobertura de skills ponderada por tu nivel, preferencias y similitud semántica local opcional | `/bandeja/revision` | <!-- media:provisional --> [Por revisar](img/es/triage.webp) |
| **Revisar con el teclado**: `J`/`K` para moverte, `A` aprobar, `D` descartar con motivo, `O` abrir, y Deshacer | `/bandeja/revision` | <!-- media:provisional --> [▶ Teclado](img/es/anim/triage.webp) |
| **El veredicto de tu agente**: encaje con riesgos y preguntas, citando tus deal-breakers; en segundo plano se salta las de poco encaje. Avisa siempre de las ofertas con posible texto dirigido a una IA, que nunca salen como encaje fuerte. En cada oferta, «Valorar esta oferta»; para las ofertas nuevas, «Valorar las ofertas nuevas» | `assess-fit` | |
| **«Conoces a N personas aquí»**: tus contactos de LinkedIn (exportación oficial en CSV) cruzados con cada empresa | `/jobs/:id` | |
| **La ficha de la oferta**, en pestañas (Oferta, Candidatura, Proceso, Empresa, Historial y notas) que se abren en la que toca según la fase: extracción, desglose del encaje, señales, historial, notas, coste en tiempo de agente y todas las secciones de abajo | `/jobs/:id` | <!-- media:provisional --> [Ficha](img/es/job.webp) |

## 3. CV y carta

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **CV a medida**: con tus indicaciones para esa oferta, si quieres (qué destacar, el idioma…); tu agente lo redacta citando la evidencia de tu perfil de cada línea; el código rechaza lo que no está y otro rol lo verifica; la ficha avisa con el PDF en cuanto está | `generate-cv` | |
| **Editor del CV**: el CV a tamaño de lectura junto a un panel para pedir cambios, editar el texto o cambiar el diseño | | |
| **Corregir un CV ya hecho**: di qué cambiar y tu agente toca solo eso, sin inventar nada y verificando el resultado, o edita tú el texto, quita o reordena logros y organiza las skills por grupos con etiquetas (la app avisa de lo que tu perfil no respalda); se conservan todas las versiones, con qué cambió y «Volver a esta versión» | `correct-cv`, `verify-cv` | |
| **El mismo contenido, cualquier diseño**: plantilla, foto, color y secciones en la ficha, renderizado en segundos sin agente; comparas renders y marcas el que envías; la maquetación del PDF se revisa | `/jobs/:id` | <!-- media:provisional --> [CV](img/es/job-cv.webp) · <!-- media:provisional --> [▶ Otro diseño](img/es/anim/cv.webp) |
| **Carta de presentación** según tus indicaciones generales y las de cada oferta, verificada, en TXT y PDF a juego con el CV; la puedes retocar a mano. En la ficha, «Escribir carta» la pide como «Generar CV»: en terminal, en segundo plano o para tu próxima sesión | `generate-cover-letter` | <!-- media:provisional --> [Carta](img/es/job-letter.webp) |
| **Plantillas de CV**: integradas (Word y HTML) y las tuyas; todas se pueden usar por defecto y eliminar (las de la app se quitan de tu lista y se restauran desde «Plantillas eliminadas»; las tuyas, además, se renombran); «Subir nueva plantilla» (o arrastrar el fichero) convierte un CV de ejemplo en una plantilla nueva, con el nombre que elijas («Mi CV» por defecto) y la tarjeta en «Convirtiendo…» mientras tu agente trabaja; «Comparar con el original» pone el CV subido junto a la plantilla | `/perfil/plantillas` | <!-- media:provisional --> [Plantillas](img/es/templates.webp) |
| **Importar tu propio diseño de CV** desde Word, PDF, una imagen, HTML, Canva o Google Docs como plantilla | `import-cv-template` | |

## 4. Candidatar

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Paquete de candidatura**: el CV elegido, las respuestas de screening con un botón de copiar cada una y la carta; el salario y lo que no esté en tu perfil quedan para ti | `prepare-application` | <!-- media:provisional --> [Paquete](img/es/job-package.webp) |
| **Candidatura asistida**: la app rellena formularios de Greenhouse, Lever, Ashby o genéricos en su propio navegador, se para antes de enviar, enseña qué rellenó y de dónde sale, y **solo envía cuando escribes el nombre de la empresa** | `/jobs/:id` | <!-- media:provisional --> [▶ Candidatura asistida](img/es/anim/apply.webp) |
| **Correos de candidatura y mensajes de LinkedIn** (≤ 300 caracteres) para el recruiter, el responsable o un compañero, guardados como borradores que envías tú | `draft-message` | |
| **Archivo de lo que enviaste**: CV, carta, respuestas y un README en su carpeta, sin cambios si rehaces el CV después | `/jobs/:id` | |

## 5. Seguimiento y respuestas

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Tablero** (en Procesos): un kanban que solo se mueve con eventos registrados (ratón, teclado o táctil) y solo hacia una etapa posterior, con 3 a 5 columnas a tu gusto (cualquier etapa en cualquier columna, en el orden que quieras y con nombre propio, con vista previa), las ofertas recibidas lado a lado y los avisos de seguimiento. Las cerradas dicen cómo acabaron (descartada, rechazada sin entrevista, tras entrevista o tras la oferta, en rojo los rechazos) y se filtran por eso | `/procesos` | <!-- media:provisional --> [Procesos](img/es/processes.webp) |
| **Ficha del proceso**: hitos con fecha y hora (se editan, se cancelan o, si los anotaste por error, se borran), contactos y referencias, borradores y «¿Qué ha pasado?», que ya en proceso registra otra entrevista, una prueba o la oferta, y solo deja aceptar cuando hay una oferta | `/jobs/:id` | <!-- media:provisional --> [Proceso](img/es/job-interview.webp) |
| **Calendario**: entrevistas, pruebas y plazos, con alta desde cualquier día, un `.ics` por hito y un feed con alarmas para tu calendario, y avisos del navegador con la app abierta (sin correos) | `/calendario` | <!-- media:provisional --> [Calendario](img/es/calendar.webp) |
| **Respuestas de las empresas**: la app lee tu correo en solo lectura y guarda solo los de las empresas a las que te has presentado. Los de una misma candidatura van juntos, el último arriba y los anteriores plegados. Si ya habías anotado lo que cuenta un correo (p. ej. el rechazo), se enlaza a eso. Al aceptar o ignorar, un aviso dice en qué oferta ha quedado; «Ignorar» se deshace desde él. Con el teclado: `J`/`K` para moverte, `A` aceptar, `I` ignorar | `/respuestas` | <!-- media:provisional --> [Respuestas](img/es/replies.webp) |
| **Clasificar las respuestas**: tu agente propone entrevista (con su fecha), prueba, oferta, rechazo o nada; nada cambia de etapa hasta que aceptas | `review-replies` | |
| **Seguimientos y agradecimientos** como borradores (como mucho 2 seguimientos por candidatura) | `draft-follow-up` | |

## 6. Entrevistas y ofertas

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Investigar la empresa** con fuentes: producto, noticias, cultura de ingeniería, stack y banderas rojas. No pregunta nada: avisa al terminar y lo ves en la ficha | `research-company` | <!-- media:provisional --> [Dosier](img/es/job-research.webp) |
| **Preparar la entrevista**: una guía en PDF y un plan por días, que se ven bajo la entrevista; cada ronda con su tipo (RR. HH., técnica, caso, final) y tus indicaciones, que también usa el simulacro; puedes pedir cambios a una guía ya hecha, incluso tras la entrevista, y tu agente toca solo eso; la versión anterior se conserva, con lo que cambió y **Volver a la versión anterior** | `prepare-interview`, `correct-interview-guide` | <!-- media:provisional --> [Plan](img/es/job-interview.webp) |
| **Simulacro de entrevista**: una pregunta cada vez, feedback concreto y una respuesta mejor solo con tu perfil | `mock-interview` | |
| **Repaso**: notas y próximos pasos, la siguiente ronda predicha y historias STAR nuevas propuestas; con una oferta recibida, qué aclarar antes de aceptar | `debrief-interview` | |
| **Ofertas recibidas** comparadas con tu mínimo y con el rango publicado, **sin que tu agente vea nunca tu mínimo** | `/procesos` | <!-- media:provisional --> [Oferta recibida](img/es/job-offer.webp) |
| **Negociación**: argumentos sacados de tu perfil, preguntas, un guion con la cifra para que la pongas tú y revisión del contrato cláusula a cláusula (no es asesoramiento legal) | `prepare-negotiation` | |

## 7. Estrategia y perfil

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **¿Cómo van mis candidaturas?**, también en la portada: de lo enviado a lo aceptado, con una rama por cada grupo que se quedó en un paso y cómo está ahora (esperando, rechazada, en entrevistas…); cada rama lleva a esas candidaturas | `/` · `/resultados` | |
| **Resultados**: qué te funciona, en frases (por qué canal te responden más, cuánto tardan, por dónde responden antes, tu mejor fuente), y debajo, por pregunta: tasa y tiempo de respuesta por canal, conversión por fuente, puesto, semana y referencia, y motivos de descarte | `/resultados` | <!-- media:provisional --> [Embudo](img/es/funnel.webp) |
| **«¿Acierta el encaje?»**: tasas de respuesta y de entrevista por encaje, veredicto, fuente, plantilla, carta y referencia, con intervalos al 95 %, en «Más análisis» de Resultados | `/resultados` | |
| **Tu búsqueda en números**, lista para compartir (solo cifras, nunca empresas), en «Más análisis» de Resultados | `/resultados` · `cai stats story` | |
| **Retrospectiva semanal**: qué funciona y qué cambiar, sin tocar pesos ni filtros | `review-search` | |
| **Habilidades por desarrollar**: lo que piden tus ofertas y aún no figura en tu perfil; sinónimos «Es lo mismo que…», «La tengo» y «No la tengo», de 25 en 25 | `/perfil/skills` | <!-- media:provisional --> [Skills](img/es/skills.webp) |
| **Plan de formación** con recursos verificados para tus huecos reales, y valoración de un curso o proyecto | `training-plan` | |
| **Ampliar la búsqueda** con títulos de puesto cercanos a lo que apruebas y descartas | `broaden-search` | |
| **Mi perfil, editable**: sin perfil, subes tu CV y tu agente lo crea a partir de él, o lo empiezas a mano (nombre, titular, puesto y niveles); los ficheros de contexto se crean desde su plantilla aunque aún no tengas perfil; un índice para saltar a cada apartado; skills e idiomas arriba, con las skills filtrables por nivel y por categoría; experiencia, proyectos, formación, certificaciones e historias STAR plegables; en «Documentos», tres tarjetas con filas plegadas (cómo quieres tus CVs y cartas, con un resumen de una línea; notas para tu agente y muestras de estilo; tus archivos); el aviso de cambios sin guardar dice qué bloques y lleva hasta ellos; conserva los comentarios de tu fichero, con Deshacer; en «Historial», cada versión con cuándo, de dónde viene y qué bloques cambió, el detalle en «Antes → Ahora» (lo añadido en verde, lo quitado tachado) y «Volver a esta versión» | `/perfil` | <!-- media:provisional --> [Experiencia](img/es/profile-experience.webp) · <!-- media:provisional --> [▶ Plegable](img/es/anim/profile.webp) |
| **Foto para el CV (opcional)**: súbela, encuádrala con zoom y arrastre (la vista previa tiene la forma de tu plantilla), vuelve a encuadrarla desde la original, cámbiala o quítala en «Mi perfil → Sobre ti»; se queda en tu equipo y tu agente no la lee | `/perfil` | |
| **Resumen en inglés**: «Generar resumen en inglés» pide a tu agente que traduzca tu resumen en español sin añadir nada; la propuesta sale junto al campo para usarla, editarla o descartarla antes de guardar | `/perfil` | |
| **Crear o actualizar tu perfil** desde tu CV o lo que le cuentes a tu agente | `update-profile` | |
| **Importar información desde un CV** («Mi perfil»): sube un CV y tu agente añade a tu perfil lo que le falte, enseñándote las diferencias y sin guardar nada sin tu OK | `update-profile` | |
| **Mejorar tu perfil** («Mejorar el contenido de mi perfil»): revisa el perfil entero (logros sin cifra, textos de relleno, huecos) y propone cambios; además, con tu GitHub, portfolio, Kaggle o Scholar públicos, proyectos, skills y certificaciones, cada cosa con su fuente y solo con tu OK | `expand` | |
| **Revisión de tu perfil de LinkedIn** frente a tu perfil y a las ofertas que apruebas | `review-linkedin` | |

## 8. Ajustes, agentes y la app

| Funcionalidad | Dónde | Captura |
|---|---|---|
| **Agente**: arriba, si tu agente está listo (con su logo) o cómo instalar uno, y lo que dejas para tu próxima sesión; plegados, agente por defecto y uno por acción, coste por acción y modelo, niveles de gasto y la comparación por significado del score | `/agente` | <!-- media:provisional --> [Agente](img/es/agent.webp) |
| **Cada botón de agente se explica**: qué hace el skill, qué cambia y qué necesita, al pasar el ratón o con el foco del teclado | Todas las páginas | |
| **Navegar con teclado**: el primer Tab enseña «Saltar al contenido», que se salta el menú, y el foco se ve siempre, también en claro y en oscuro. Una fila de filtros (las etapas de la Bandeja, las respuestas) es una sola parada de Tab, y se recorre con las flechas | Todas las páginas | |
| **Dejar para tu próxima sesión**: cualquier botón guarda la orden para tu agente | `handle-requests` | |
| **Borrar una oferta o vaciarlo todo**: arriba en la ficha, una oferta con todo lo suyo (borrar no es descartar: descartar la guarda en tu historial); en la barra de la Bandeja, todas las ofertas y candidaturas (se quedan el perfil, las plantillas, las fuentes y la configuración). Con avisos, confirmación escrita y una copia de seguridad previa en tu carpeta de datos. Las **ofertas duplicadas** que se guardaban antes (ya no se crean) se borran desde un aviso de la Bandeja, con vista previa y confirmación corta; las que tienen algo propio se quedan | `/jobs/:id`, `/bandeja` | |
| **Resumen del día**: ofertas pendientes (con aviso si alguna lleva texto dirigido a una IA), seguimientos vencidos, próximos hitos y respuestas de empresas por revisar | `daily-summary` | |
| **Barra lateral** agrupada y plegable con lo que te espera, tema claro y oscuro, español e inglés (el idioma elegido es también el de las órdenes a tu agente, su ventana y sus respuestas; el CV y la carta, en el de la oferta) | `/` | <!-- media:provisional --> [Barra lateral](img/es/sidebar-collapsed.webp) |
| **Modo demo** con una búsqueda ficticia en la que cada página tiene algo | `cai demo seed` | |
| **Instalación** con una línea en Windows, macOS y Linux, o con Docker; `cai doctor` lo revisa todo | [Guía](GUIA.md) | |
| **Cinco agentes**: Claude Code, Codex, Antigravity CLI, OpenCode y Qwen Code, por MCP o con `cai … --json`; modelos gratuitos y locales | [`AGENTS_COMPAT.md`](AGENTS_COMPAT.md) | |
