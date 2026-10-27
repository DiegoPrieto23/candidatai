# Changelog

Lo que cambia en cada versión de CandidatAI para quien la usa. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[versionado semántico](https://semver.org/lang/es/). Cómo se versiona y se publica: `CONTRIBUTING.md`.

Cada fase añade lo suyo a «Sin publicar». Al publicar, esa sección pasa a ser la de la versión nueva
y su texto son las notas de la release en GitHub (`scripts/release_notes.py`).

## [Sin publicar]

### Añadido
- **Miniatura de la guía de preparación:** en cada entrevista, la portada del PDF junto a su enlace,
  para reconocerla de un vistazo. Pulsarla abre la guía.
- **`cai start` en inglés:** los mensajes de la terminal salen en el idioma de tu sistema (español
  o inglés). Para elegirlo, `CAI_LANG=es` o `CAI_LANG=en` en el `.env`.
- **Aviso cuando el CV o la guía están listos:** tras «Generar CV» o «Preparar» una entrevista,
  la ficha se pone al día sola en cuanto tu agente los deja y sale un aviso con «Abrir PDF»
  (y una notificación del sistema si estás en otra ventana y la tienes permitida). Sin F5.
- **Borrar un hito anotado por error:** cada entrevista, prueba, plazo u otro hito tiene una
  papelera. Tras confirmar (te dice si se pierden la guía, el plan o el repaso), desaparece de
  la ficha, del historial y del embudo, y la etapa de la oferta se recalcula. Para lo que sí
  pasó y se canceló, sigue la X.
- **Indicaciones para preparar una entrevista:** en cada entrevista programada, una caja para
  decir qué quieres que tengan en cuenta la guía en PDF y el simulacro («más peso a SQL», «habrá
  un caso de negocio»…). Se quedan guardadas en esa entrevista y las usan «Preparar» y
  «Simulacro» cada vez que los pulsas.
- **Tipo de entrevista:** al anotar o editar una entrevista eliges qué ronda es (RR. HH. o encaje
  cultural, técnica, caso práctico, final u otra). Se ve en la ficha y la guía y el simulacro se
  adaptan a él sin tener que adivinarlo por el título.
- **Guía «Empieza aquí»** (`docs/EMPEZAR.md`, en inglés `docs/START_HERE.md`) para quien no es
  técnico: qué necesitas (incluido un agente de IA, con lo que cuesta cada opción y adónde van tus
  datos), la instalación paso a paso con la suma de verificación, la demo, crear tu perfil, tu
  primera búsqueda y preguntas frecuentes (qué sale de tu equipo, si envía solo, el correo,
  LinkedIn, cuánto cuesta).
- **Los avisos de arriba se pueden ocultar:** «Hay N ofertas por extraer» y el de seguimientos
  pendientes tienen una X que los oculta hasta que cierras la pestaña.
- **«Cómo iniciarla» en el README:** dónde queda el acceso directo en Windows, macOS y Linux, y
  cómo arrancarla desde la terminal (`cai start`) o con Docker.

### Cambiado
- **El score de una oferta, junto a su desglose:** en la ficha ya no va en la cabecera sino en
  «Encaje», al lado de lo que lo explica.
- **La app abre antes:** al arrancar descarga menos de un tercio que antes (cada página se descarga
  al entrar en ella, o antes, al pasar el ratón por su enlace, y solo el idioma que usas) y las
  respuestas viajan comprimidas. Al volver a abrirla, lo que no ha cambiado sale de la caché del
  navegador sin preguntar al servidor.
- **Rápida también con miles de ofertas:** con 5000 ofertas, el Embudo pasa de 2,5 segundos a
  0,15, la Calibración de 2 a 0,12, la historia de tu búsqueda de 0,8 a 0,08, Por revisar de 0,7 a
  0,1 y Alertas de 0,4 a 0,09. La Bandeja responde en 0,03-0,06 s en cualquier orden y la ficha,
  Procesos y la página de inicio, en menos de 0,1. Al actualizar se añaden unos índices a tu base
  de datos, sin tocar ningún dato.
- **«Tengo entrevista» sin fecha obligatoria:** la fecha y la hora van en campos separados y las dos
  son opcionales. Sin hora, la entrevista cuenta todo el día; sin fecha, se registra solo que la
  tienes. Lo mismo con la fecha de entrega de una prueba.
- **Bandeja de ofertas:** la Bandeja se llama así, las etapas ya no quedan pegadas a su barra de
  desplazamiento y, al marcar ofertas para descartarlas, la barra con «Descartar N» flota abajo en
  vez de empujar la lista hacia abajo.
- **Una interfaz más fácil de entender:**
  - **Sin jerga:** los textos ya no hablan de skills, comandos, rutas ni ficheros. Dicen qué botón
    pulsar («Procesar ofertas», «Generar CV») o qué pedirle a tu agente.
  - **Una sola acción destacada por pantalla:** la que más desbloquea ahora va en verde; los demás
    botones del agente van con borde. El agente con el que se abren se ve en su desplegable (▾).
  - **«Nueva oferta»** está siempre en la barra lateral.
  - **Fuera los avisos fijos de arriba:** lo que espera ya se cuenta en Inicio y en la barra
    lateral, donde «Procesos» enseña los seguimientos pendientes.
  - **Fuera la fila de etapas de la cabecera:** en la Bandeja, las etapas son filtros con su
    recuento, y los datos que faltan se ven como un guion discreto.
  - **Listas de 25 en 25:** la Bandeja y Alertas se paginan. En Alertas, las ofertas que no encajan
    con tus filtros van plegadas.
  - **Procesos** explica el tablero en una frase y las tarjetas llevan un botón más discreto.
  - **Mi perfil**, en cinco pestañas en vez de nueve: Sobre ti, Experiencia y formación, Búsqueda,
    Documentos (preferencias de CV y carta, y el contexto) e Historial.
  - **Plataformas:** cada portal en una línea con su último recorrido; la prioridad, el acceso,
    las búsquedas y el registro van en «Ajustes y registro». «Buscar ofertas» está arriba.
  - **Empresas objetivo:** primero las que sigues; para añadir una, «Añadir empresa». Ya no se
    habla de «slug», sino del nombre de la empresa en la dirección de su web de empleo.
  - **Agente:** arriba tus agentes y los encargos para tu próxima sesión; después lo que corre en
    segundo plano, y el umbral y el coste, plegados en «Umbral y coste». Los agentes que no tienes
    instalados y el ajuste por acción también van plegados.
  - **Buzones:** si a uno le falta la contraseña de aplicación, lo dice así y lleva un botón para
    escribirla, también en la cuenta configurada al instalar. Las variables, solo en «Detalles
    técnicos».
  - **«Generar»** en vez de «Renderizar» en el CV y la carta, y «versión» en vez de «render».
  - **Skills:** de 25 en 25, con «obligatoria en 2, deseable en 1» en vez de abreviaturas y el
    peso explicado en su ayuda (ⓘ). En el móvil, cada skill es una ficha con sus botones debajo.
  - **Embudo:** primero las cifras, el embudo, por fuente, por semana y los motivos de descarte.
    «¿Acierta el score?», por tipo de puesto, el coste y «Tu búsqueda en números» van plegados en
    «Más análisis». Las ofertas sin procesar ya no salen como un puesto más, sino en una nota, y
    la línea para compartir ya no habla de README.
  - **Plantillas:** sin «Motor docx» ni identificadores; cada una dice si da «PDF y Word» o
    «Solo PDF» y si viene «De la app». La orden para tu agente va plegada.
  - **Respuestas, Nueva oferta, Calendario y la ficha:** textos más claros («Enlace de la oferta»,
    «Añadir a mi calendario», «Importar mis contactos», «Tecnologías»…). Sin respuestas, un botón
    lleva a conectar el correo. En la pestaña Proceso, «Anotar oferta» ya no compite con «¿Qué ha
    pasado?». Las notas del score se explican en lenguaje llano.
- **La ficha de la oferta, más ligera:** en vez de apilar todas las secciones con una columna
  lateral, va en pestañas (Oferta, Candidatura, Proceso, Empresa, Historial y notas) y se abre en
  la que toca: la oferta mientras la revisas, la candidatura al aprobarla y el proceso al enviarla.
  El score se ve siempre en la cabecera y los avisos importantes, encima de las pestañas. Dentro,
  lo secundario va plegado: las opciones de diseño del CV y de la carta, sus versiones anteriores,
  los avisos del verificador cuando el documento está verificado, las indicaciones de una carta ya
  escrita y el detalle del dosier de la empresa. La extracción ya no repite las skills que enseña
  el encaje.
- **Portada nueva:** el README se lee en dos minutos. Arriba, la promesa, un recorrido animado de
  50 segundos (aprobar y descartar ofertas, el CV verificado, la candidatura que espera tu
  confirmación, los procesos y el embudo) y los botones para instalar en Windows, macOS/Linux o con Docker; una nota con lo probado de verdad y lo que aún
  no; qué necesitas antes de empezar; y «Por qué CandidatAI», una comparación corta y con fecha con
  AI Job Search y career-ops que dice también lo que ellos hacen mejor. El detalle (skills, fuentes,
  agentes, arquitectura) queda en la lista de funcionalidades y en `docs/`.
- **Adiós a «triaje»:** la UI y la documentación dicen «revisar» (como la página «Por revisar»), el
  umbral se llama «umbral de score» y en el Embudo el paso «Triadas» pasa a «Pasan filtros».
- **Capturas y animaciones nuevas** en los README y en las listas de funcionalidades, en español
  e inglés: cada página tiene la suya, las principales también en modo oscuro, y seis animaciones
  cortas enseñan «Por revisar», descartar desde la Bandeja, añadir un buzón, cambiar el CV,
  «Mi perfil» y la candidatura asistida. Pesan mucho menos (WebP) y ya no hay vídeo.
- **La demo trae alertas por correo:** 65 ofertas, 5 de ellas de dos buzones de alertas, así que la
  página «Alertas» ya no sale vacía.

### Corregido
- **Una entrevista ya no se puede dar por hecha antes de su día:** el ✓ de una entrevista futura está
  desactivado (te dice desde cuándo podrás). Un clic de más la sacaba de «Próximos 7 días» en Inicio.
- **La app ya no puede salir en blanco en algunos Windows:** si el registro de Windows tenía mal el
  tipo de los ficheros `.js`, el navegador se negaba a ejecutar la interfaz. Ahora se sirven
  siempre con el tipo correcto.
- **El Calendario carga al recargar la página** o al entrar por un enlace; antes daba «Not Found».
- **La página Agente ya no se sale de la pantalla en el móvil,** ni el Embudo ni Skills.
- **«Con tu perfil» en Plantillas** ya no enseña una imagen rota si no se puede hacer la vista:
  dice qué comprobar.
- **«Sin mínimo en tu perfil»** al comparar ofertas recibidas ya no enseña el nombre interno del
  campo: dice dónde ponerlo (Mi perfil → Búsqueda).

### Seguridad
- **Librerías sin vulnerabilidades conocidas:** Pillow 13 (la foto del CV, las miniaturas y las
  plantillas importadas desde imagen), pypdf, filelock, setuptools, opentelemetry y Vite pasan a sus
  versiones arregladas, y el resto de librerías a sus últimos parches. Al actualizar con el
  instalador se instalan solas; no cambia nada de cómo se usa.

## [0.1.0] - 2026-10-24

Primera versión publicada de CandidatAI: una app local para llevar tu búsqueda de empleo de
principio a fin (ofertas, revisión con score, CV a medida, candidatura, seguimiento y análisis)
con el agente de IA que ya usas. La app no llama a ningún modelo: el razonamiento lo pone tu agente
y las reglas (qué se envía, qué se inventa, qué ve tu agente) las aplica el código.

### Añadido
- **Instalación sin preparar nada:** `install.ps1` en Windows e `install.sh` en macOS y Linux
  descargan la release, comprueban su suma SHA-256, preparan Python y el navegador de los PDF, y
  crean el acceso directo «CandidatAI». Sin permisos de administrador; tus datos van aparte y
  actualizar nunca los toca. También con Docker (`docker compose up -d --build`), opcional.
- **Una UI en español e inglés,** con tema claro y oscuro, barra lateral y móvil, y `cai start`
  para arrancarlo todo. **Modo demo** (`cai demo seed`) con una búsqueda ficticia completa para
  probarlo sin tus datos.
- **Todo lo que hace, en una lista:** `docs/FEATURES.md` (en inglés) y `docs/FUNCIONALIDADES.md`
  recorren cada funcionalidad en el orden en que la usas, con su página o su skill y su captura.
  Los README la enlazan.
- **Funciona con tu agente:** Claude Code, Codex, OpenCode, Qwen Code y Antigravity CLI, con
  servidor MCP o con la CLI `cai … --json` (mismas herramientas). Eliges el agente por defecto y uno
  por acción desde la UI; `cai agents doctor` dice cuáles tienes. Guía de modelos gratuitos y
  locales, con niveles de gasto «Económico», «Equilibrado» y «Máximo».
- **Tu perfil, editable desde la UI** («Mi perfil»): experiencia y logros, proyectos, formación,
  skills, historias STAR, qué buscas y tus preferencias de CV y carta, con validación, vista previa
  del cambio y «Deshacer». Tu contexto (estilo, criterios, narrativa) y muestras de tu forma de
  escribir. El skill `expand` propone lo que ya has demostrado en GitHub, tu portfolio o Scholar.
- **Ofertas de muchas fuentes, sin scraping:** pegando la URL o el texto; a diario desde Greenhouse,
  Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters y Recruitee de tus empresas
  objetivo, y desde Manfred, freehire.me, InfoJobs y Adzuna; alertas de correo de varios buzones
  (Gmail, Outlook, Yahoo, iCloud o una carpeta de `.eml`, siempre en solo lectura); la extensión
  «Enviar a CandidatAI» para Chrome y Edge; y tu agente recorriendo portales con tu navegador. La
  búsqueda pública de LinkedIn, sin sesión, es opcional y está apagada.
- **Revisión con un score que se explica:** filtros de lo que no quieres (ubicación, sueldo mínimo privado, años,
  contrato, consultoras…), score 0-100 con su porqué, valoración de tu agente, ofertas cerradas o
  republicadas, señales de oferta dudosa y descartar en un clic con «Deshacer».
- **CV a medida verificado:** cada línea cita su evidencia en tu perfil y un verificador
  independiente comprueba que nada se inventa ni se exagera. Plantillas integradas o tu propio CV
  (Word, PDF, imagen, HTML) convertido en plantilla; cambiar plantilla, foto o color no gasta agente.
  Aviso de problemas de maquetación del PDF.
- **Carta de presentación** según tus indicaciones, verificada y con el diseño de tu CV, y
  **paquete de candidatura** con respuestas de screening para copiar. **Candidatura asistida**:
  rellena el formulario y se para antes de enviar; envía solo tras tu confirmación en la UI.
- **Seguimiento:** kanban de procesos, calendario de entrevistas y plazos (también `.ics`), avisos
  de seguimiento, correos de las empresas clasificados por tu agente que aceptas tú, y borradores de
  seguimiento, agradecimiento y mensajes de LinkedIn que envías tú.
- **Entrevistas y ofertas:** guía de entrevista en PDF, simulacro con feedback, repaso con historias
  STAR nuevas, dosier de la empresa con fuentes y banderas rojas, comparación de ofertas recibidas
  con tu mínimo (que tu agente nunca ve) y preparación de la negociación.
- **Tu red de LinkedIn** desde su exportación oficial: «Conoces a N» en cada empresa.
- **Análisis:** embudo por fuente, puesto, semana y referencia, «¿Acierta el score?», huecos de
  skills con plan de formación, coste por oferta y agente, y `cai stats story` con tu búsqueda en
  números.
- **Tu agente trabaja también sin ti:** procesar, valorar y generar CVs en segundo plano, o dejar
  encargos para tu próxima sesión. Cada botón que lanza tu agente explica qué hará.

### Seguridad
- El texto de ofertas, correos y webs se trata siempre como datos: se detectan las instrucciones
  ocultas y las frases de inyección, y la oferta queda marcada.
- Nada sale hacia terceros sin tu confirmación en la UI: la app nunca envía correos ni mensajes, y
  una candidatura solo se envía con una confirmación de un solo uso.
- La API escucha solo en 127.0.0.1, las descargas rechazan direcciones locales y privadas y la
  extensión va con token.
- Tu agente no ve tu email, tu teléfono, tu sueldo mínimo ni las contraseñas de tus buzones (que
  solo se guardan en `.env`), y no tiene herramientas para escribir tu perfil.
- Los instaladores no instalan una release cuya suma SHA-256 no coincide con la publicada.

[Sin publicar]: https://github.com/DiegoPrieto23/candidatai/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/DiegoPrieto23/candidatai/releases/tag/v0.1.0
