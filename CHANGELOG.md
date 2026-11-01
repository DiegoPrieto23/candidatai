# Changelog

Lo que cambia en cada versión de CandidatAI para quien la usa. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[versionado semántico](https://semver.org/lang/es/). Cómo se versiona y se publica: `CONTRIBUTING.md`.

Cada fase añade lo suyo a «Sin publicar». Al publicar, esa sección pasa a ser la de la versión nueva
y su texto son las notas de la release en GitHub (`scripts/release_notes.py`).

## [Sin publicar]

### Añadido
- **Crear tu perfil sin agente:** en «Mi perfil», **Empezar a mano** pide tu nombre, tu titular, el
  puesto que buscas y los niveles que aceptas, crea el perfil y abre el editor para seguir bloque a
  bloque. Nada sale del perfil de ejemplo.
- **«Necesitas un agente de IA»:** si no tienes ningún agente instalado, Inicio y «Agente» lo dicen
  y explican cómo instalar Claude Code paso a paso (dónde pegar la orden, con «Copiar», y cómo
  entrar con tu cuenta), con un enlace a la guía.
- **Los ficheros de contexto se crean desde la app:** en «Mi perfil → Contexto», cada fichero que
  aún no existe tiene su botón **Crear**, que abre su plantilla con las preguntas que te guían,
  aunque todavía no tengas perfil.
- **Cada etapa de la Bandeja explica qué es y cómo avanzar:** al elegir «Por completar», «Por
  leer», «Por revisar»… sale qué falta y quién lo hace, con el botón que lo hace («Leer las ofertas
  nuevas», «Valorar las pendientes», «Ir a Por revisar»). Así se ve la diferencia: «Leer las
  ofertas nuevas» saca sus datos y les calcula el encaje; «Valorar las pendientes» añade la opinión
  de tu agente a las que ya lo tienen.
- **Desde una oferta se ve qué falta para saber si te encaja:** si no tiene encaje, su ficha dice
  «Para saber si te encaja: 1. crea tu perfil, 2. que tu agente la lea», con lo ya hecho marcado y
  el botón de lo que falta. En la Bandeja, «Sin encaje» dice el porqué al pasar el ratón.
- **Las ofertas «Por completar» dicen qué les falta:** en su ficha, un aviso explica que falta la
  descripción, abre la oferta en su portal y te dice que pulses «Enviar a CandidatAI», con un
  enlace a la guía para instalar el botón. En la Bandeja, los mismos pasos.
- **Índice en «Mi perfil → Experiencia y formación»:** una fila de enlaces lleva a cada apartado
  (Skills, Idiomas, Experiencia, Proyectos…), con cuántos tiene y un punto si falta guardar.
- **Instalar el botón «Enviar a CandidatAI» sin terminal:** nueva pestaña **Dónde buscar → Botón
  del navegador**. Detecta la extensión sola, te guía para cargarla en Chrome, Edge o Brave (con
  un botón que abre su carpeta), avisa si tienes una versión antigua y la conecta con un clic: ya
  no hace falta generar un token y pegarlo en sus opciones.
- **«Escribir carta» en la ficha:** la carta de presentación tiene su botón, con el mismo
  desplegable que «Generar CV»: abrir tu agente, en segundo plano o dejarla para tu próxima sesión.
  En segundo plano no pregunta: si no hay indicaciones, usa las de por defecto. Con carta, «Volver
  a redactar».
- **Aviso al aceptar o ignorar una respuesta:** en «Respuestas», antes de pasar al siguiente
  correo, un aviso dice en qué oferta ha quedado registrada, con su enlace. «Ignorar» se puede
  deshacer desde el aviso.
- **El resumen del día cuenta las respuestas de las empresas:** dice cuántos correos quedan por
  clasificar (con `review-replies`) y cuántas propuestas te esperan en Procesos, como Inicio.
- **Ampliar la búsqueda comprueba los títulos antes de proponerlos:** `broaden-search` sabe, sin
  mirar el código, cómo casa un título con tus puestos buscados, qué ofertas aprobadas dejaría
  entrar y cuáles descartadas colaría. Va más rápido y gasta menos.
- **Navegar con teclado:** el primer Tab de cada página enseña **Saltar al contenido**, que se
  salta el menú y te deja en la página: la acción principal queda a unos pocos Tab (en Inicio, 6 en
  vez de 23).

### Cambiado
- **El Embudo ya tiene forma de embudo:** una franja por etapa y, al lado, su cifra, el porcentaje
  sobre la etapa anterior y el porcentaje sobre el total. Las etapas a 0 también se ven, en gris y
  con su cifra real. Con lector de pantalla, los mismos datos llegan como tabla.
- **Lenguaje claro en el encaje y las etapas:** el número de cada oferta se llama ahora «encaje» y
  dice su escala y qué tal es («74/100 · buen encaje»); al pasar el ratón explica qué mide. El
  desglose («De dónde sale el número») explica cada parte y cuántos puntos suma, las letras de
  nivel de las skills (F, C, bás.) llevan leyenda y el aviso de la comparación por significado va
  en llano. En la ficha, «Seniority» pasa a «Nivel» y el texto original explica qué se hace con
  las instrucciones que pudiera traer; en «Mi perfil», «Deal-breakers» se explica.
- **Nombres nuevos:** la etapa «Por extraer» pasa a **«Por leer»**; el botón «Procesar ofertas», a
  **«Leer las ofertas nuevas»**; «Evaluar encaje» (todas), a **«Valorar las pendientes»**, y
  «Valorar encaje» (una), a **«Valorar esta oferta»**, para que no se confundan.
- **Inicio explica qué hace la app y qué es tu agente:** el programa de IA que tienes instalado
  (Claude Code, Codex…) y que lee las ofertas y escribe tus CVs, con un enlace a «Agente». Mientras
  faltan los primeros pasos, el titular lo dice («Te quedan 2 primeros pasos para empezar») y la
  única acción destacada es la del paso que toca.
- **«Agente» empieza por lo que importa:** arriba, «Tu agente: Claude Code, listo» (o cómo instalar
  uno) y qué distingue a Claude, la app de chat, de Claude Code; versiones, licencias, niveles y
  modelos, plegados en «Tus agentes en detalle».
- **Cuando un botón no puede abrir tu agente,** enseña la orden entera en un recuadro con «Copiar» y
  dice dónde pegarla. Ya no desaparece a los pocos segundos ni va en letra pequeña.
- **Las carpetas de «Documentos»** salen con su nombre («Títulos», «Referencias»…), no con el de la
  carpeta en disco.
- **Instalar la extensión, más claro:** el paso «Cargar descomprimida» enseña la ruta de su carpeta
  con un botón para copiarla y dice dónde pegarla en la ventana de elegir carpeta (en Windows,
  macOS y Linux).
- **«Mi perfil», más fácil de recorrer:** proyectos, formación, certificaciones, otras secciones e
  historias STAR arrancan plegados, como las empresas, con «Desplegar todo». Skills e Idiomas van
  arriba, cada uno en su bloque con su botón de guardar. El aviso de cambios sin guardar nombra
  los bloques («Sin guardar: Idiomas, Puesto») y, al pulsar uno, te lleva hasta él.
- **«Ajustes y registro» de cada plataforma, plegado siempre:** los incidentes del último
  recorrido ya se cuentan en su línea.
- **Extensión 0.2.0:** si no está conectada, su botón ofrece «Conectar con CandidatAI», que abre
  esa página de la app; sus avisos ya no piden comandos. «Abrir ficha» usa la dirección de
  `cai start` (antes, la del modo desarrollo). Si ya la tenías, pulsa ⟳ en su tarjeta en
  `chrome://extensions` para actualizarla.
- **Antigravity CLI, tercera opción de pago:** con Google AI Pro o Ultra (o su plan gratuito)
  aparece justo detrás de Claude Code y Codex en «Agente», en los desplegables y en la guía. Los
  botones ya lo abren en una terminal con la orden escrita (`agy -i`), como con Claude Code y Codex,
  y puedes elegir su modelo (`agy models` los lista). Probado con Antigravity CLI 1.4.5.
- **«¿Qué ha pasado?» completo en «En proceso»:** ya deja anotar otra respuesta, otra entrevista,
  una prueba o la oferta recibida sin cambiar de etapa, y enlaza a «Anotar oferta» y a «Hitos» para
  los detalles. «Acepto la oferta» solo sale cuando hay una oferta registrada.
- **«Dar de alta» dice qué falta:** al pegar el texto de una oferta, «Puesto» y «Empresa» se marcan
  como obligatorios y, mientras el botón está desactivado, una línea dice qué falta.
- **Aviso honesto si una página falla:** distingue «La app no responde» (con «Recargar») de «Esta
  página ha fallado», que ya no culpa a una actualización: ofrece volver a Inicio y dice dónde ver
  el detalle y dónde avisar.
- **CandidatAI arranca antes:** `cai start` ya no carga la app entera solo para vigilar a la API y
  al worker, y las migraciones se comprueban una sola vez. La API responde unos segundos antes, el
  proceso que se queda en la ventana ocupa mucha menos memoria y `cai --help` sale al momento.
- **Los iconos de «Dónde buscar» los sirve la app:** los descarga una vez y los guarda en tu
  carpeta de datos, así que tu navegador ya no visita la web de cada portal y de cada empresa al
  abrir la página. Si una web no tiene icono, o no hay red, se ve la inicial, como antes. LinkedIn
  se queda siempre con la inicial: la app no consulta LinkedIn por su cuenta.
- **La app arranca algo antes y no se frena con los iconos:** la API ya no carga al arrancar lo
  que solo hace falta para generar documentos, importar plantillas o aplicar con el navegador.
  Un icono que tarda en descargarse ya no ocupa la app mientras tanto: sale la inicial y el icono
  aparece unos segundos después.
- **Menos Tab en la Bandeja y en «Respuestas»:** los filtros de etapa (y los de «Respuestas») son
  una sola parada de Tab y se recorren con las flechas. En «Respuestas», `J`/`K` pasan de un
  correo a otro, `A` acepta la propuesta e `I` la ignora, como en «Por revisar».
- **La app carga antes la primera vez:** los textos de tu idioma se descargan a la vez que el
  resto, y los iconos pesan un tercio menos. Con una conexión lenta, Inicio se ve un 20 % antes.
- **El embudo va más rápido con muchas ofertas:** «Por semana» y «Por puesto» se calculan sin
  leer cada oferta una a una.

### Corregido
- **El foco de teclado se ve siempre:** en «Respuestas», el correo con el foco lleva un anillo y
  ya no se confunde con el seleccionado. Las pestañas de la ficha, de «Mi perfil» y de «Nueva
  oferta» y los títulos de la Bandeja lo enseñan también, igual que los apartados de «Mi perfil»
  cuando llegas a ellos desde su índice o desde el aviso «Sin guardar», en claro y en oscuro.
- **Generar un CV o una carta con LibreOffice ya no cierra la app:** mientras se convertía a PDF,
  el resto de la app no podía escribir en tu base y, si la conversión pasaba de 5 segundos, el
  proceso de segundo plano se caía y con él toda la app. Ahora, si la base está ocupada, cada
  escritura espera hasta 90 segundos, más que lo que se deja tardar a una conversión. Además, el
  PDF se prepara antes de tocar la base, así que mientras convierte ya no bloquea nada, y un
  bloqueo pasajero al arrancar ya no tumba la app.
- **Sin LibreOffice ni Word, «Generar CV» ya no falla y pierde el CV:** si la plantilla que tocaba
  es de Word («ATS sencilla», «Clásica con foto» o una tuya importada de Word), se usa «Moderna a
  dos columnas» y la ficha te lo avisa. Lo mismo con la carta. Si la plantilla de Word la eliges
  tú, te dice que instales LibreOffice. `cai doctor` y la guía lo explican.
- **No se proponen seguimientos a quien ya te ha contestado:** si un correo de la empresa está por
  revisar en «Respuestas» (un rechazo, una entrevista…), esa candidatura deja de salir como
  «seguimiento pendiente» en Inicio, en Procesos y en la ficha, y tu agente no le redacta uno.
- **Una oferta cuya página no se puede abrir** (sin red, con inicio de sesión o con una web que lo
  bloquea) ya no enseña el error técnico de Windows ni manda escribir un comando: lo explica y
  ofrece «Pegar el texto», con el enlace ya puesto.
- **Un paso registrado justo después de otro** («Me han respondido» en el mismo minuto en que la
  marcaste enviada) ya no se rechaza: queda detrás del anterior.
- **«Skills» sin perfil** conserva su título y ya no deja un error en la consola del navegador.
- **Con la UI en inglés, las plantillas integradas** salen con su nombre y su descripción en inglés.
- **La carta, verificada contra la empresa correcta:** la verificación ya ve a qué empresa y a qué
  puesto va, y no avisa de un saludo que está bien. Para los agentes, `get_cover_letter` (y
  `cai letter show`) devuelve también `company` y `job_title`.
- **El perfil de la demo** ya no da a Snowflake los años de toda su experiencia: los CVs que se
  generan con ella dicen desde cuándo.
- **Textos que no cuadraban:** `cai doctor` y los avisos de la extensión llaman a la pestaña por su
  nombre («Dónde buscar → Botón del navegador»); el README dice «Generar», como el botón; la guía
  ya no dice que el sueldo mínimo solo se edita en el YAML ni que aprobar se deshace en el aviso
  (se reabre en la ficha), y «¿Qué datos salen de mi equipo?» cuenta que tu navegador pide el
  icono de cada portal y empresa a su web.
- **Desinstalar ya no se lleva los accesos directos de otra instalación:** `install.ps1 -Uninstall`
  (e `install.sh --uninstall`) solo borra el acceso del escritorio y del menú Inicio (o el de
  Aplicaciones en macOS y Linux) si abre la instalación que se está quitando. Antes, desinstalar
  cualquier otra carpeta borraba también los de tu instalación, y CandidatAI desaparecía de la
  búsqueda de Windows.
- En «Nueva oferta», el menú ya no marca «Bandeja de ofertas»: el activo es el botón «Nueva
  oferta».

### Seguridad
- **Las ofertas con texto dirigido a una IA nunca salen como encaje fuerte:** tu agente avisa
  siempre de ellas al valorarlas y en el resumen del día, y la app rechaza una valoración «fuerte»
  hasta que la revises. Su salario y su modalidad salen solo de los datos extraídos, nunca de lo
  que pida el texto.

## [0.3.0] - 2026-10-28

### Añadido
- **Primeros pasos en Inicio:** con la app recién instalada, Inicio te propone los dos pasos para
  empezar, con su botón: subir tu CV para que tu agente cree tu perfil y elegir dónde buscar con tu
  agente. Cada paso se marca al hacerlo y la tarjeta desaparece cuando están los dos.
- **Configurar los portales con tu agente:** en «Dónde buscar → Portales de empleo», «Configurar
  con mi agente» te pregunta en qué portales buscas, te recomienda otros según tu perfil y prepara
  sus búsquedas con tus puestos y ubicaciones. No guarda nada sin tu OK.
- **Búsquedas desde tu perfil, sin escribir URLs:** al añadir InfoJobs, Tecnoempleo, Indeed o
  LinkedIn, las búsquedas salen solas de los puestos que buscas y tus ubicaciones («Mi perfil →
  Búsqueda»), en remoto si lo aceptas. Debajo se ve qué buscará cada una («Data Engineer · Vigo») y
  se pueden retocar; «Rellenar desde mi perfil» las vuelve a generar.
- **Editar un portal:** el lápiz de cada portal cambia su nombre y sus búsquedas.
- **Indicaciones para el CV de una oferta:** junto a «Generar CV», una caja para decir qué quieres
  que tenga en cuenta (qué proyecto destacar, el idioma, qué dejar fuera). Se guardan solas y tu
  agente las usa cada vez que redacta o rehace ese CV.

### Cambiado
- **«Fuentes» pasa a llamarse «Dónde buscar»**, y su pestaña «Plataformas», «Portales de empleo».
- **CandidatAI arranca antes y se ve desde el primer momento:** al pulsar el acceso directo se
  abre enseguida el navegador con «Arrancando CandidatAI…», que pasa solo a la app en cuanto
  responde (si no responde, dice dónde mirar). Además arranca más rápido: el instalador deja la
  app precompilada (la primera vez tras instalar o actualizar ya no tarda el triple), no se
  vuelven a revisar las migraciones si están al día y las tareas en segundo plano arrancan
  cuando la app ya responde. Si el navegador no se puede abrir, la ventana dice la dirección.

## [0.2.0] - 2026-10-28

### Añadido
- **Crear tu perfil desde tu CV, sin salir de la app:** en «Mi perfil», mientras no tengas perfil,
  subes tu CV (PDF o Word) y pulsas «Crear mi perfil desde mi CV». Tu agente lo lee, te pregunta lo
  que el CV no dice y no guarda nada sin tu OK; al terminar, el perfil aparece solo para revisarlo.
  En «Mi perfil → Documentos» también puedes subir más CVs y tu exportación de LinkedIn.
- **Valorar el encaje de una oferta desde su ficha:** en «Valoración del agente», «Valorar encaje»
  si aún no tiene valoración (p. ej. su score quedó por debajo del umbral del segundo plano) y
  «Volver a valorar» si la tiene desfasada (cambió tu perfil, la oferta o el score). Con una
  valoración al día no sale: con los mismos datos solo gastaría y el veredicto variaría al azar.
- **Comparación por significado desde la UI:** en el desglose del score, «Qué aporta y cómo
  activarla» explica qué mejora (sinónimos, ofertas en otro idioma, el 30 % del score que es la
  «Similitud») y la instala con un botón, en segundo plano. Es permanente: se usa en todas las
  ofertas desde entonces, las abiertas se recalculan solas y, si actualizas la app, se reinstala.
  También está en la página **Agente**, sección «Comparación por significado», con su estado
  bien a la vista (sin activar, instalándose, activada o con error).
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
- **Comparación por significado junto al score:** si no está instalada, debajo del score de cada
  oferta sale el aviso de que instalándola el encaje sale más fino, con el botón para hacerlo. Si
  está activa, dice cuánto se parecen tu perfil y la oferta: así se ve que funciona.
- **Sin flechas de scroll en las pestañas:** la fila de pestañas de la ficha y de «Mi perfil» y los
  filtros de la Bandeja ya no enseñan una barra con flechas que no servía (salía con zoom en
  Windows). Las tablas tampoco.
- **Botones de icono con explicación:** al pasar el ratón (o enfocar con el teclado) por los
  botones de un hito (descargar para el calendario, editar, hecho, cancelar, deshacer «hecha»,
  borrar), de un contacto y de anterior/siguiente en el calendario, sale qué hace cada uno.
- **Inicio:** «Próximos 7 días» sube a la esquina superior derecha, junto a lo que tienes
  pendiente hoy.
- **Valoración antigua del agente:** si el score ha cambiado desde que tu agente valoró la oferta,
  la ficha dice con qué score la valoró y cuál tiene ahora, en vez de solo «De un cálculo
  anterior».
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
- **Error de `transformers` tras instalar la comparación por significado:** si el score de una
  oferta se calculaba mientras se instalaba, salía «No se pudo hacer la comparación por
  significado (ImportError…)» y no se arreglaba solo. Ahora, mientras se instala, el score se
  calcula como antes; el error ya no se queda pegado y las ofertas con el score así se recalculan
  solas al arrancar la app.
- **Entrevistas futuras que se quedaron como «Hecho»:** las que se marcaron como hechas antes de su
  día (antes de que la app lo impidiera) vuelven solas a «Programado» al actualizar, y salen otra
  vez en «Próximos 7 días».
- **«Mover proceso» sin scroll lateral:** con un título de oferta largo, el diálogo ya no se sale
  por la derecha (tampoco los de descartar ni el de aceptar una respuesta).
- **Una entrevista ya no se puede dar por hecha antes de su día:** el ✓ de una entrevista futura está
  desactivado (te dice desde cuándo podrás). Un clic de más la sacaba de «Próximos 7 días» en Inicio.
  Si ya marcaste alguna antes de su día, la flecha ↺ junto a ella la devuelve a programada, sin
  perder su guía ni su plan.
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

[Sin publicar]: https://github.com/DiegoPrieto23/candidatai/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/DiegoPrieto23/candidatai/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/DiegoPrieto23/candidatai/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/DiegoPrieto23/candidatai/releases/tag/v0.1.0
