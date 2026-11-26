# Changelog

Lo que cambia en cada versión de CandidatAI para quien la usa. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[versionado semántico](https://semver.org/lang/es/). Cómo se versiona y se publica: `CONTRIBUTING.md`.

Cada fase añade lo suyo a «Sin publicar». Al publicar, esa sección pasa a ser la de la versión nueva
y su texto son las notas de la release en GitHub (`scripts/release_notes.py`).

## [Sin publicar]

### Cambiado

- **«Valorar las ofertas nuevas» lee y valora todas las pendientes de una vez**, sin parar en 20
  (ni valorar como mucho 30): con 60 ofertas por leer, las lee y valora las 60.
- **En la Bandeja, en «Por leer», junto a «Valorar las ofertas nuevas»** se ve si la comparación
  por significado está activada; al pulsarlo, explica para qué sirve y permite instalarla.
- **«Bandeja de ofertas», en la ficha de una oferta, vuelve a la vista de la Bandeja de la que se
  venía**, con su etapa, filtros, orden y página (p. ej. «Aprobada»), como el «atrás» del navegador.
- **La terminal de CandidatAI («Arrancando CandidatAI…», «CandidatAI en marcha…») sale en inglés**
  si el portal está en inglés, aunque nunca se haya cambiado el idioma a mano, y desde el primer
  arranque si se instaló en inglés.
- **El instalador de Windows habla en el idioma de la web** desde la que se copia la línea (español
  o inglés); sin indicarlo, en el de Windows. Con ` -Lang es` o ` -Lang en` se elige.
- **Al terminar de instalar, CandidatAI se abre sola** en el navegador. Las próximas veces, con su
  acceso directo, como siempre.

## [1.1.0] - 2026-11-25

### Añadido

- **Aviso de versión nueva en Inicio**, con un enlace a sus novedades. Con el instalador de
  Windows, **«Actualizar ahora»** cierra la app, instala la versión nueva en una ventana aparte
  (comprobando su suma SHA-256) y la vuelve a abrir; la pestaña se recarga sola. Si el agente de IA
  está abierto, la ventana pide cerrarlo y espera. En macOS, Linux y Docker, el aviso da la orden
  para copiarla. Los datos no se tocan. Para saberlo, la app pregunta a GitHub cuál es la última
  versión como mucho cada 12 horas, sin enviar nada del usuario; `CAI_UPDATE_CHECK=off` lo desactiva.
- Pregunta frecuente «¿Cómo se actualiza CandidatAI?» en la ayuda.

### Cambiado

- **Instalar en Windows es una sola línea** que se pega en Windows+R, sin abrir una terminal
  (también sirve en PowerShell o en `cmd`). La de antes, de dos líneas, sigue funcionando.

## [1.0.1] - 2026-11-25

### Corregido

- Lo que se acababa de guardar (una oferta nueva, un cambio de estado) a veces no aparecía si se
  abría al instante: la app respondía antes de terminar de guardarlo.
- Aprobar, descartar o reabrir una oferta (o registrar un hito del proceso) podía fallar con «Error
  interno (OperationalError)» si coincidía con una tarea en segundo plano guardando algo. Ahora
  espera a que termine.

## [1.0.0] - 2026-11-24

Primera versión estable de CandidatAI: una app local para llevar la búsqueda de empleo de principio
a fin (ofertas, revisión con score, CV a medida, candidatura asistida, seguimiento y resultados) con
el agente de IA que ya usas. La app no llama a ningún modelo: el razonamiento lo pone tu agente, y
las reglas (qué se envía, qué no se inventa, qué ve tu agente) las aplica el código.

**Lo más importante desde la 0.3.0:**
- **Un portal nuevo:** aspecto renovado, barra lateral ordenada por grupos, ayuda en cada página, un
  Asistente en la esquina para pedirle cosas a tu agente y avisos de lo que está haciendo, que se
  puede detener. Los textos, en tono profesional.
- **Buscar ofertas en un solo sitio:** portales y empresas en «Buscar ofertas», «Buscar ahora» que
  trae solo ofertas nuevas, resumen de cada búsqueda y ofertas repetidas o republicadas detectadas.
- **El CV, bajo tu control:** corregirlo pidiéndolo en palabras, editar tú el texto, versiones,
  foto encuadrada y plantillas que se suben, renombran y restauran.
- **Seguimiento más claro:** Tablero con columnas a tu gusto, «Respuestas» agrupadas por
  candidatura, motivo de cierre de cada oferta y «Resultados» con el tiempo y la tasa de respuesta
  de cada canal.
- **Más seguro:** contraseñas de los buzones en el llavero del sistema, ninguna web puede cambiar
  nada en la app y las ofertas con texto dirigido a una IA no salen como encaje fuerte.

**Madurez:** es una herramienta para una persona en su propio ordenador (no para el móvil), y hace
falta un agente de IA, que la app no incluye. Windows 11 y Claude Code son lo más probado; el
detalle de sistemas y agentes, en «Limitaciones conocidas» del README y en `docs/AGENTS_COMPAT.md`.

**Cómo actualizar desde la 0.3.0:** con CandidatAI y tu agente cerrados, vuelve a ejecutar el
instalador (o, desde el repositorio, `git pull`, `uv sync` y `pnpm build`; con Docker, `git pull` y
`docker compose up -d --build`). Tus datos no se tocan y las migraciones se aplican solas al
arrancar. El detalle de cada cambio sigue aquí debajo.

### Añadido
- **Detener a tu agente desde el aviso:** lo que va en segundo plano («Generando el CV…», «Leyendo
  ofertas…») tiene un botón «Detener» en el aviso de arriba, con una confirmación corta. El aviso
  pasa a «Deteniendo…» y, en unos segundos, a «Detenida», y lo que tu agente ya había guardado se
  queda. Si lo abriste en una terminal, el aviso explica que se para cerrando esa ventana y ofrece
  «Marcar como terminada».
- **Por qué se cerró cada oferta, en la Bandeja:** columna «Motivo» en «Cerrada» y en «Todas»
  (descartada, no pasó los filtros, rechazada, retirada, caducada, cerrada por la empresa,
  duplicada o aceptada) y filtro «Motivo de cierre». Una duplicada ya no sale como «Descartada».
- **Varias etapas a la vez en «Todas»:** el desplegable «Etapas» tiene una casilla por etapa (todas
  marcadas al principio), «Todas» y «Ninguna», y lo marcado queda en la dirección de la página, así
  que se puede guardar o compartir la vista (p. ej. solo «CV listo» y «Cerrada»).
- **Borrar las ofertas duplicadas:** la Bandeja avisa de las ofertas duplicadas que se guardaban
  antes (la misma vacante que otra, con un título casi igual, cerrada como duplicada). «Ver y
  borrar» enseña la lista, cada una con su original, y las borra con una confirmación corta, tras
  una copia de seguridad de la base de datos. Las que se reabrieron o tienen algo propio (un CV,
  notas, una candidatura…) se quedan, y la lista dice por qué. La original conserva sus enlaces, así
  que una búsqueda nueva los reconoce sin abrirlos. Tu agente puede consultarlas con
  `list_duplicates` (`cai jobs duplicates`).
- **Borrar una oferta o vaciarlo todo:** arriba en la ficha de cada oferta, junto a «Ver original»,
  «Borrar oferta» la quita con todo lo suyo (historial, CVs, cartas, entrevistas, borradores y los
  correos que solo eran de ella); su aviso explica que borrar no es descartar, que la cierra y la
  guarda en tu historial. En la barra de la Bandeja, detrás de «Revisión rápida», «Vaciar todo» borra
  todas las ofertas y candidaturas, para empezar de cero; se quedan tu perfil, tus plantillas, tus fuentes, tus buzones, tu red de contactos y la
  configuración. Los dos piden pasar uno o dos avisos y escribir el nombre de la empresa o «BORRAR»,
  y antes guardan una copia de seguridad de la base de datos en la carpeta `backups` de tus datos (las
  10 últimas), que es la forma de recuperarlo. Los ficheros de tu carpeta de datos no se tocan.
- **Cómo acabó cada candidatura cerrada:** en «Procesos» y en la ficha, un rechazo dice hasta dónde
  llegaste («Rechazada sin entrevista», «tras entrevista» o «tras la oferta»), en rojo, y la columna de
  cerradas tiene un filtro: descartadas por ti, rechazadas sin entrevista, rechazadas tras entrevista
  y el resto.
- **El Asistente funciona con Codex y con Antigravity CLI:** con Codex, lo que escribes en
  «Asistente» se contesta en segundo plano, como con Claude Code u OpenCode, con solo las
  herramientas de consulta del asistente (sin terminal, ficheros ni web). Con Antigravity CLI (y Qwen
  Code), que no pueden trabajar en segundo plano con garantías, se abre tu agente en una terminal a
  la vista y la respuesta aparece igual en el panel; puedes cancelarla desde ahí (la ventana la cierras
  tú) y, si en 2 horas no contesta, deja de esperar. Solo queda como
  encargo para tu próxima sesión si no hay terminal que abrir.
- **Ofertas que vuelven a publicarse:** si una vacante que cerró la empresa (te rechazaron, caducó o
  la descartaste porque la habían cerrado) se publica otra vez pasados 30 días, entra como oferta
  nueva con la etiqueta **Reabierta**, y su ficha dice de qué oferta viene y cómo acabó. Si la cerraste
  tú (la retiraste o la descartaste por otro motivo), no entra: la Bandeja te avisa de que **ha vuelto
  a publicarse** y puedes reabrirla o ignorar el aviso (no vuelve a salir en 30 días). Si una oferta
  que caducó vuelve a aparecer tal cual, se reabre sola. «Republicada» y «Publicada hace meses» ya no
  cuentan lo que pasó con la vacante anterior. El umbral es `dedup.reopen_after_days`.
- **Tu agente sabe qué ofertas ya tienes antes de abrirlas:** con la herramienta nueva `check_known`
  (`cai jobs known`) comprueba de una vez la lista de resultados de un portal y distingue las nuevas,
  las que ya están (por su id o su dirección, aunque lleve parámetros de seguimiento), la misma
  oferta publicada con otro id y las que cerraste hace más de 30 días y vuelven a publicarse. El
  umbral es `dedup.reopen_after_days` en `config/policies.yaml`.
- **El botón «Enviar a CandidatAI» funciona en más portales:** Glassdoor (también con la oferta
  abierta a la derecha de la búsqueda), Manfred, Ticjob, JobFluent, Domestika, Welcome to the
  Jungle y las webs de empleo de las empresas que usan Greenhouse, Lever, Workday, Ashby,
  SmartRecruiters, Teamtailor, Recruitee, Personio o Workable. En una web que cambia de oferta sin
  recargar la página (Workday, Ashby…) ya no manda por error los datos de la oferta anterior.
  Recarga la extensión (⟳ en `chrome://extensions`) para tenerlo.
- **Tiempo y tasa de respuesta por canal:** en **Resultados**, cuánto te responden y en cuántos días
  (mediana) por referencia, en la web de la empresa, en los portales de empleo y en las ofertas que
  añades tú. También en `cai stats funnel` y en la interfaz para agentes.
- **Columnas del Tablero a tu gusto:** con **Personalizar columnas** eliges entre 3 y 5 columnas. Cada
  columna sale en una fila con su nombre y sus etapas como etiquetas, y se ordena arrastrándola o con
  sus flechas; cada etapa elige su columna en un selector, aunque no vayan seguidas (p. ej. «Aprobada»
  con «Cerrada»). Una vista previa enseña el tablero en pequeño con cuántas ofertas tendrá cada
  columna. Solo cambia la vista, y el diálogo lo explica: las etapas de tus ofertas siguen igual, las
  tarjetas solo avanzan a una etapa posterior y cada tarjeta de una columna con varias etapas dice la
  suya. **Restablecer** vuelve a las de siempre y se aplica al guardar.
- **Añadir hitos desde el Calendario:** con **Añadir hito**, el «+» de un día o pulsando una hora
  libre de la semana o del día. Eliges la oferta en una lista con buscador (por empresa o puesto,
  sin importar tildes ni mayúsculas) y el hito se guarda en su ficha, con la fecha ya puesta.
- **Avisos sin correos:** el fichero del calendario y la suscripción llevan alarmas (un día y una
  hora antes de cada hito con hora; a las 9:00 del día anterior en los plazos) para que Outlook o
  Apple Calendar te avisen solos. Y con **Avisos del navegador** en el Calendario, mientras la app
  está abierta, el navegador te avisa de las entrevistas, las pruebas, los plazos y los seguimientos
  pendientes.
- **Puestos en cualquier idioma:** da igual si escribes tus puestos buscados o tus palabras de
  descarte en español o en inglés: «Ingeniero de datos» encuentra ofertas de «Data Engineer» y al
  revés, también en el encaje por título. La lista de equivalencias trae puestos de datos,
  desarrollo, producto y negocio, y se puede ampliar en `config/title_aliases.yaml`.
- **Idiomas y países por su nombre:** en «Idiomas de trabajo», «Países sin foto» y los campos de país
  e idioma de las fuentes escribes «francés» o «Reino Unido», con autocompletado en el idioma de la
  app, en vez de códigos de dos letras.
- **Elige tu navegador antes de instalar «Enviar a CandidatAI»:** en **Dónde buscar → Botón del
  navegador** eliges Chrome, Edge o Brave (se propone el que usas) y los pasos se adaptan a él. Con
  Firefox o Safari, o con la app abierta en otro navegador, el aviso sale al principio.
- **Encuadrar la foto del CV:** al subirla en **Mi perfil → Sobre ti**, la colocas con zoom y arrastre
  antes de guardarla, con la forma (redonda o cuadrada) de tu plantilla por defecto. Se hace en tu
  navegador, y **Volver a encuadrar** parte de la foto original.
- **Generar resumen en inglés:** un botón junto a «Resumen (inglés)» pide a tu agente que traduzca tu
  resumen en español, sin añadir nada. La propuesta aparece junto al campo para usarla, editarla o
  descartarla antes de guardar; puede ir en segundo plano.
- **Subir una plantilla, más cómodo:** en **Plantillas de CV** puedes arrastrar el fichero, eliges su
  nombre antes de subirlo («Mi CV» por defecto, o «Mi CV 2» si ya existe) y la tarjeta dice
  «Convirtiendo en plantilla…» mientras tu agente trabaja.
- **Ayuda del periodo en Habilidades por desarrollar:** junto a 30/60/90/180 días, qué ofertas cuenta
  cada ventana y para qué sirve cambiarla.
- **Asistente:** un botón con rótulo abajo a la derecha, junto al de ayuda, abre un chat para
  pedirle algo a tu agente con tus palabras. Escribes abajo y pulsas Intro o la flecha (Mayús+Intro
  salta de línea); tu pregunta queda a la derecha y la respuesta a la izquierda, con enlaces a la
  oferta o a la pantalla de la que habla, separadas por días. La primera vez propone ejemplos («¿qué
  tengo pendiente esta semana?») que se escriben en la caja al pulsarlos. Si tu agente trabaja en
  segundo plano desde la app, se lanza al momento; si no, queda como encargo para tu próxima sesión
  y el hilo lo dice. Cada vez que lo abres empiezas una conversación nueva; las anteriores están en
  una barra lateral por fechas (Hoy, Ayer, Últimos 7 días, Antes), se vuelven a abrir con un clic y
  se borran con la papelera. En una misma conversación, tu agente recuerda lo que ya le
  preguntaste. El panel se distingue del resto del portal por su cabecera y su borde. Puede
  consultar tus datos, valorar una oferta ya leída y guardar las indicaciones de una carta. Enviar una
  candidatura, aprobar, descartar y borrar los sigues confirmando tú.
- **Ayuda en todas las páginas:** un botón abajo a la derecha (o la tecla `?`) abre un buscador sobre
  las preguntas frecuentes y la guía de uso. Cada respuesta lleva a la pantalla donde se hace.
  Funciona sin conexión y sin agente, en español y en inglés, y `Esc` lo cierra. Las mismas preguntas
  están en `docs/PREGUNTAS.md` y `docs/FAQ.md`.
- **Importar información desde un CV, en Mi perfil:** con tu perfil ya hecho, un botón nuevo sube un CV (PDF
  o Word) y tu agente añade a tu perfil lo que le falte, como experiencia o logros. Te enseña las
  diferencias y tú decides qué se guarda.
- **Eliminar y restaurar plantillas de la app:** en **Plantillas de CV**, todas las plantillas ofrecen
  **Eliminar**. Las tuyas se borran como hasta ahora; una de la app se quita de tu lista y de las que elige
  tu agente (no se borra del programa, para que tus CVs ya hechos sigan funcionando) y vuelve desde
  **Plantillas eliminadas**, con **Restaurar**.
- **Filtros en la Bandeja:** bajo el buscador, tres desplegables para filtrar la lista: **Modalidad**
  (presencial, híbrido, remoto o sin especificar), **Salario** (con o sin salario) y **Encaje** (sin encaje, o
  de 50, 70 u 85 o más). Se suman a la etapa y a la búsqueda, se guardan en la dirección (se puede recargar o
  compartir la vista) y **Limpiar filtros** los quita.
- **Avisos de lo que hace tu agente:** lo que lanzas con un botón (leer ofertas, valorarlas, revisar
  respuestas, generar o corregir un CV, la carta, investigar la empresa, preparar una entrevista…) sale
  en un aviso en cualquier página, con lo que lleva hecho, y cambia cuando termina o si no ha podido. Se
  puede minimizar o cerrar, y cerrarlo no para a tu agente.
- **Tu agente te pregunta en el portal:** si necesita saber algo para generar un CV, una carta o una guía,
  te sale un aviso para contestar ahí mismo, sin ir a su ventana. También puedes contestarle en ella. Los
  permisos que pide tu agente (y las conversaciones, como un simulacro) siguen en su ventana.
- **Descartar o cerrar desde cualquier oferta:** la ficha de una oferta tiene **Descartar**, con motivo, en
  todas las etapas hasta enviarla (también en **Aprobada** y **CV listo**), y **Cerrar candidatura** si ya la
  enviaste (te han rechazado, te retiras o ha caducado). **Reabrir** lo deshace.
- **Renombrar y eliminar tus plantillas:** en cada plantilla tuya, el lápiz cambia el nombre y **Eliminar**
  la borra con el CV que subiste para crearla. Los CVs ya generados conservan sus ficheros.
- **Buscar ofertas:** una página nueva, con su lupa en el menú. Eliges en qué portales buscar, ves
  cuándo se buscó por última vez y cuántas salieron, afinas con puesto y ubicación solo para esa vez, y
  lanzas a tu agente. Un aviso dice **Buscando…** en cualquier página, con los portales que lleva y las
  ofertas nuevas, y cambia cuando tu agente termina o si no ha podido buscar. Se puede minimizar o cerrar.
- **Dónde buscar**, dentro de **Buscar ofertas:** es una pestaña más, junto a **Buscar** y **Qué buscas**,
  y **Buscar ofertas** va antes que la **Bandeja** en el menú.
- **Problemas y notas de cada portal:** lo que antes se llamaba «incidentes» se separa en lo que impidió
  leer el portal (captcha, inicio de sesión) y lo que tu agente apuntó sin que fallara nada.
- **Portada más compacta:** tu embudo se ve sin bajar. En «Recorrido de tus ofertas», **Enviada** y **En
  proceso** llevan a su etapa en la Bandeja, y al cambiar de página siempre se empieza por arriba.
- **Tu embudo:** un gráfico nuevo, también en la portada, que enseña hasta dónde ha llegado cada candidatura
  y dónde están las que pararon. Cada rama lleva a esas candidaturas, y **Ver las cifras** da el detalle.
- **Nuevo aspecto:** todas las páginas arrancan a la misma distancia del menú, con un solo estilo de
  título. Barra lateral en el verde del logo, tipografía nueva, casillas propias, pestañas sin cajas y menos
  recuadros. Los botones de tu agente llevan un robot en vez de destellos.
- **Foto para el CV en «Mi perfil»:** en «Sobre ti» la subes, la cambias o la quitas sin tocar ficheros.
  Es opcional, y se queda en tu equipo.
- **Filtro de skills:** en «Experiencia y formación», todas, solo las F, las C+… con su recuento. Cada
  skill ocupa una línea, para no tener que hacer tanto scroll.
- **Corregir un CV ya generado:** en la ficha, escribe qué quieres cambiar («el resumen más corto»,
  «quita el proyecto X») y tu agente toca solo eso, sin inventar nada, y verifica el resultado. Si
  el perfil no respalda algo, no lo añade y te lo dice. Se abre al momento, en segundo plano o queda
  para tu próxima sesión.
- **Editar tú el texto del CV:** resumen, subtítulo, viñetas y skills, sin agente y sin gastar
  cuota. La app avisa de las skills y las cifras que tu perfil no respalda, pero la decisión es tuya.
  Esa versión queda sin verificar, con un botón **Verificar esta versión**.
- **Versiones del CV:** cada corrección o edición es una versión nueva. La ficha enseña de dónde
  sale cada una y qué cambió, sección a sección, y **Volver a esta versión** no borra ninguna.
- **Editor del CV:** en la pestaña Candidatura, el CV se ve a tamaño de lectura y, a su lado, un panel
  con **Pedir cambios** (con sugerencias), **Editar texto** y **Diseño**. Un diseño recién generado
  pasa a verse solo, y los demás salen con su miniatura.
- **Cambiar una guía de entrevista:** bajo la guía, **Pedir cambios a la guía** deja escribir qué
  cambiar y tu agente toca solo eso, también después de la entrevista. La versión anterior se
  conserva: ves qué cambió, sección a sección, y **Volver a la versión anterior** rehace el PDF sin
  agente y se puede deshacer. Si la entrevista está cancelada o el proceso cerrado, te dice por qué no
  se pueden pedir cambios.
- **«Cómo funciona»:** una página nueva, con su enlace al pie del menú, que cuenta quién hace qué (tú,
  tu agente y la app) y el recorrido completo en cinco pasos, de preparar tu búsqueda a seguir tus
  procesos, con un enlace a cada pantalla y a las guías. «Primeros pasos» enlaza a ella.
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
- **Skills por categoría:** en «Mi perfil», además de por nivel, filtras tus skills por categoría
  (Lenguajes, Cloud…, o «Sin categoría»), y los dos filtros se combinan. Cada filtro dice cuántas
  quedarían, los que dejarían la lista vacía se ven atenuados y **Quitar filtros** vuelve a todas. Con
  muchas categorías, eliges la tuya en una lista con buscador. Una skill que cambias con un filtro
  puesto ya no desaparece mientras la editas.

### Cambiado
- **Textos del portal en tono formal e impersonal:** en español, la app ya no tutea ni habla en primera
  persona: «Pulsa «Guardar» para subir tu CV» pasa a «Se pulsa «Guardar» para subir el CV», y «tu agente», a
  «el agente». Algunos botones cambian de nombre, como «Aceptar la oferta» (antes «Acepto la oferta»), «Marcar
  como enviado» (antes «Ya lo he enviado»), «Dejar para la próxima sesión» o «Crear el perfil desde un CV». En
  inglés, sin contracciones. También la ayuda (con sus preguntas frecuentes), los avisos y errores que
  muestra la app y lo que imprime `cai start`, y lo que el agente deja en la app (valoraciones, respuestas
  del Asistente, preguntas). También las guías (Primeros pasos, antes «Empieza aquí», la guía de uso,
  las funcionalidades y el README); en inglés, sin contracciones. Las capturas de las guías son provisionales.
- **Capturas y animaciones con el portal actual:** todas las capturas de la documentación, en español e
  inglés, rehechas con la interfaz de ahora, más nítidas (las principales, al doble de resolución) y con
  cuatro nuevas: el Asistente, la ayuda, el historial de «Mi perfil» y las alertas por correo. La
  animación de la demo es más corta (unos 25 s) y pesa menos de la mitad, y las animaciones cortas de las
  funcionalidades enseñan las pantallas nuevas. El diagrama «Cómo funciona» y la imagen para redes, al
  día y también en español. Los README, las guías y la lista de funcionalidades las enseñan con
  descripciones que dicen lo que se ve, y las cifras de rendimiento del README están medidas de nuevo.
- **Editar el CV tú, con más margen:** en «Editar texto», las skills se ven por grupos: el nombre del
  grupo arriba y cada skill como una etiqueta con «×» para quitarla y un campo para añadir otra con
  Intro. Hay «Añadir grupo» y botones para subir, bajar o quitar cada grupo (con confirmación si tiene
  skills). Los logros de cada experiencia y proyecto también se quitan o reordenan con sus flechas;
  para añadir uno, «Pedir cambios». Como antes, la versión queda sin verificar hasta «Verificar esta
  versión».
- **Tus empresas, a la vista en «Buscar»:** bajo los portales, las empresas con portal propio salen
  en tarjetas compactas (logo, Activa o Pausada y su último recorrido), las activas primero y hasta
  ocho; el resto y su gestión, en «Dónde buscar». La dirección de cada portal y de la web de cada
  empresa se escribe tal cual la usa el sitio, con `www.` cuando lo lleva (`www.infojobs.net`).
- **Portada más clara:** en «¿Cómo van mis candidaturas?», «Aceptadas» se alinea igual que los
  demás pasos y la explicación pasa al ⓘ junto al título. «Ver las cifras» es más corto (paso,
  cantidad y % del anterior) y agrupa en una línea por paso dónde pararon las candidaturas; lo
  mismo en «Resultados». En «Recorrido de tus ofertas», cada etapa explica qué es y quién actúa al
  pasar el ratón por encima o al llegar con el teclado.
- **Tu agente, en el idioma del portal:** con el portal en inglés, lo que lanzas («Generar CV»,
  «Buscar ofertas», el Asistente, «En segundo plano», «Dejar para mi próxima sesión») abre la
  ventana con la orden y el título en inglés, y tu agente te contesta en inglés. La app recuerda el
  idioma elegido para lo que se lanza sin el portal (tareas en segundo plano y programadas) y para
  los mensajes de `cai start`. El CV y la carta siguen saliendo en el idioma de la oferta.
- **La misma vacante con un título casi igual ya no se da de alta otra vez:** en lugar de guardarse
  como oferta nueva y cerrarse como duplicada, se anota como una publicación más de la original,
  venga de un alta manual, de la extensión, de un conector, de una alerta o de una búsqueda de tu
  agente. `check_known` la reconoce antes de abrirla (`same_offer`), y si la original la cerró la
  empresa hace más de 30 días, entra como reapertura. El resumen de cada fuente ya no cuenta
  «cerradas como duplicadas»: entran en «ya estaban».
- **«Respuestas» agrupa los correos de cada candidatura:** los de una misma oferta salen juntos, el
  más reciente arriba y los anteriores plegados debajo («4 correos anteriores de esta candidatura»),
  que despliegas con un clic. Un rechazo propuesto, y la opción «Rechazo» al cambiar o decidir qué
  significa un correo, se ven en rojo.
- **«Configurar agentes», más ancho y con los desplegables de siempre:** al abrirlo ocupa todo el
  ancho de la página «Agente», así que las tarjetas de los agentes caben de tres en tres en una
  pantalla grande, y sus selectores (agente por defecto, preset, agente de cada acción y niveles de
  gasto) tienen el mismo aspecto que los del resto de la app.
- En «Fuentes de ofertas» › «Extensión», «Ver cómo se hace» va junto al título del paso 3, no en el
  otro extremo.
- **Página «Agente» más clara:** cada agente lleva su logo, arriba en «Tu agente» y en su tarjeta de
  «Configurar agentes». Ya no está la sección «En segundo plano» con cada ejecución ni la nota sobre
  Claude y Claude Code: un aviso te dice cuándo termina lo que lanzas sin ventana.
- **«Tu embudo» se llama ahora «¿Cómo van mis candidaturas?»**, en Inicio y en «Resultados».
- **«Dónde buscar»** tiene un icono nuevo, y en «Botón del navegador» el enlace **Ver cómo se hace**
  va junto al paso 3, a la vista sin bajar.
- **Qué trajo cada búsqueda, de un vistazo:** cada portal de «Buscar» enseña una barra con las
  **vistas**, las que **pasan tus filtros**, las que **ya tenías** y las **nuevas** (de ellas, las
  **reabiertas**), con la leyenda de esas mismas cifras, y una nota de por qué paró: «Llegó a lo de la
  búsqueda anterior» o «Alcanzó el límite: quedan 5 sin abrir». «Dónde buscar», el aviso «Buscando…» al
  terminar y el resumen de tu agente usan los mismos números, y `cai sources list` también.
- **Tarjetas de empresas más simples:** cada empresa con portal propio tiene un interruptor, **Activa** o
  **Pausada**, y un menú **⋯** con **Buscar ahora**, su web y los lugares a los que se limita. **Probar**
  queda solo al añadir una empresa, donde enseña lo que traería antes de guardarla.
- **«Buscar ahora» revisa también tus empresas:** el mismo botón lanza a tu agente en los portales y, a
  la vez, la app revisa las webs de empleo de tus empresas con portal propio (sin gastar tokens; se
  saltan las revisadas hace menos de 6 horas). El panel dice «N portales · M empresas», el aviso
  «Buscando…» espera a las dos cosas y su resumen las junta. Sin portales elegidos, revisa solo las
  empresas. Fuera el enlace «Cambiar» del panel: los portales se eligen en sus tarjetas, debajo.
- **«Buscar ahora» trae ofertas nuevas de verdad:** el número de ofertas por portal cuenta solo las
  **nuevas**. Tu agente ya no abre las que tienes: comprueba cada página de resultados antes de
  abrir nada y deja de leer cada búsqueda al llegar a lo que vio la vez anterior. Lee hasta 5 páginas
  por búsqueda (antes, 2), y anota cuántas vio, cuántas no pasan tus filtros, cuántas ya tenías y
  cuántas quedaron sin abrir por el límite.
- **«Buscar ofertas»: buscar y configurar en un solo panel.** En la franja de arriba, además de tus
  puestos y lugares, marcas la **modalidad** y el **nivel** con un clic, y al pulsar un lugar eliges
  qué aceptas en él (cualquier modalidad, solo híbrido o remoto, o descartarlo). Cada cambio se guarda
  al momento, con **Deshacer**. **Más ajustes** (con el número de grupos que tienen algo puesto) se
  despliega en el mismo panel con los años de experiencia, el sueldo mínimo, los idiomas, el contrato y
  la jornada, y las ofertas que no quieres. Esos se guardan juntos con **Guardar cambios**, y tienes
  **Restablecer**, **Descartar cambios** y **Deshacer**. A la derecha, una columna nueva dice en qué
  portales buscará tu agente (con sus logos) y cuántas ofertas como mucho, junto a **Buscar ahora**.
  Desaparecen la sección aparte «Configuración de tu búsqueda» (su dirección abre ahora el panel con
  «Más ajustes» desplegado) y «Buscar otra cosa solo esta vez».
- **Añadir una empresa es pegar su web de empleo:** en «Empresas con portal propio», su nombre y la
  dirección de su web de empleo tal como la ves (`https://careers.acme.com/madrid/`), sin saber qué
  sistema usa ni qué es un «slug». La app lo detecta, respeta la ciudad de la dirección («Solo
  Madrid», que cambias en su tarjeta) y pone su logo. Si no reconoce la web, la añade a tus portales
  para que tu agente la recorra al buscar. Lo de antes (sistema y nombre en la dirección) sigue en
  **Más opciones**. En la terminal, `cai sources add --name … --url …`.
- **Solo lo que encaja contigo:** «Probar» y cada empresa enseñan solo las ofertas que pasan tus
  filtros («Encontrada: usa Greenhouse · 3 ofertas para ti», «Hoy: 2 ofertas nuevas para ti»), sin
  «encontradas», «tras filtros» ni «Ver también las filtradas». Igual en la búsqueda pública de
  LinkedIn. Los totales siguen en `cai sources list` y `cai sources test`.
- **Una oferta de LinkedIn en «Nueva oferta» te guía en vez de dar un error:** si pegas su
  enlace, la app te da dos caminos. El primero, **Abrir la oferta** y pulsar allí el botón
  «Enviar a CandidatAI» (si aún no lo tienes, un enlace te lleva a instalarlo; si ya está
  conectado, te lo dice). El segundo, **Pegar texto**, con el enlace ya rellenado. **Ver cómo se
  hace** enseña el gesto en una animación corta, que también está en «Botón del navegador».
- **«Buscar ofertas», más visual y más fácil de cambiar:** arriba, una franja con tus puestos y
  lugares como etiquetas. Las quitas con su ✕ y añades más con **+ Añadir puesto** o **+ Añadir
  lugar**. Cada cambio se guarda en tu perfil al momento, con **Deshacer**, y al añadir un puesto te
  sugiere los títulos de las ofertas que apruebas y que tus puestos aún no cubren. A la derecha,
  **Buscar ahora** con los portales y el total de ofertas. Tus portales pasan a tarjetas que se marcan
  con un clic, con su estado y lo que dieron la última vez (vistas, las que pasan tus filtros y
  nuevas); los que no se pueden usar dicen por qué. Al pie, la última búsqueda con enlace a la
  bandeja. **Afinar esta búsqueda** desaparece: lo que buscas se cambia en la misma franja.
- **«Buscar ofertas», número de ofertas en un solo sitio:** junto a «Buscar ahora», «Hasta N ofertas
  por portal» cambia a la vez el límite de todos los portales elegidos y el de los que añadas
  después. Si cada portal tiene el suyo, lo dice («varía») y elegir un número los iguala. El de un
  portal suelto se sigue cambiando en «Dónde buscar».
- **Sin nombres de agentes en «Buscar ofertas»:** fuera «Ten el navegador conectado a tu agente» y
  su ayuda, que hablaba de un agente concreto (si al tuyo le falta el navegador, te lo dice al
  empezar). La ventana para copiar la orden dice «pégala en tu agente», sin ejemplos.
- **Arranque:** la página «Arrancando CandidatAI» dice «Se abrirá en unos segundos».
- **Tu CV se sube arrastrándolo:** en **Mi perfil** («Empieza por tu CV» e «Importar información
  desde un CV») y en los primeros pasos de **Inicio**, una caja donde soltar el PDF o el Word, o
  hacer clic para elegirlo. Si el formato no vale, lo dice sin subirlo. Con el CV ya subido, la caja
  se queda en una línea con su nombre, y puedes soltar otro encima.
- **«Embudo» pasa a llamarse «Resultados»** y responde a qué te funciona. Arriba, frases sacadas de
  tus datos («Te responden más por referencia: 40 % frente a 12 % en el resto», cuánto tardan las
  empresas, por dónde responden antes y tu mejor fuente), que salen cuando hay candidaturas
  suficientes. Debajo, todo agrupado por pregunta: por dónde te responden, dónde se quedan tus
  candidaturas, qué puestos te responden y por qué descartas. Los enlaces guardados a la dirección
  antigua siguen funcionando.
- **Tablero que se ajusta al ancho:** las columnas reparten el espacio de la pantalla, los títulos
  largos pasan a otra línea en vez de cortarse y solo aparece la barra de desplazamiento si de verdad
  no caben.
- **Calendario más fácil de leer:** hoy resaltado, fines de semana con su fondo, días de otro mes
  rayados y cada tipo de hito con su icono, además de su color, en claro y en oscuro.
- **Buzones con mensajes que dicen qué hacer:** al editar o quitar la cuenta configurada al instalar, o
  al añadir un buzón en Docker, la app explica con palabras dónde se cambia y deja los nombres técnicos
  en «Detalles técnicos».
- **Ubicaciones más claras:** en **Configuración de tu búsqueda → Dónde y cómo**, cada ubicación lleva
  un selector: «Cualquier modalidad», «Solo híbrido o remoto» o «Descartar». Sustituye a los tres
  campos de antes («Ubicaciones preferidas», «Solo si no es presencial» y «Excluidas»); tus
  ubicaciones guardadas siguen igual.
- **«Puntos a revisar»** sustituye a «Señales de oferta dudosa» en la ficha, en Resultados y en la
  CLI: rango salarial amplio, empresa oculta, temporal, publicada hace meses y cribado con IA son
  cosas que conviene mirar, no un veredicto. «Excluir las que no dicen qué empresa contrata» pasa
  a «Tipo de empresa».
- **La regla de los datos que faltan, una sola vez:** la cabecera de la configuración de tu búsqueda
  dice que cada filtro se aplica solo cuando la oferta indica ese dato, con un ejemplo en su ayuda.
- **El encaje se vuelve a calcular** una vez al actualizar, por las equivalencias de puestos.
- **«Buscar ofertas» tiene dos pestañas**, como «Mi perfil», cada una con su dirección y sin saltos de
  la página: **Buscar** (con lo que buscas y **Más ajustes**, que sustituye a la pestaña «Qué buscas»)
  y **Dónde buscar** (portales, empresas, correo y botón del navegador). Abrir o plegar «Más ajustes» no
  te mueve de donde estás. Los enlaces de siempre llevan a su sitio.
- **Seleccionar los portales:** una casilla encima de la lista los selecciona o los quita todos.
- **Qué ofertas entran:** junto a «Hasta N ofertas» se dice cuáles: las más recientes que encajan
  con tu perfil, en cada portal. Tu agente sigue ese orden.
- **«Buscar ofertas» en Inicio:** sin portales en los que buscar, el botón dice **Ir a buscar
  ofertas** y lleva a elegirlos.
- **«Empresas objetivo» pasa a llamarse «Empresas con portal propio»** (en inglés, «Company career
  sites»).
- **Contraseña de aplicación del correo:** el enlace a la página de Google, Yahoo o iCloud va dentro
  del paso que lo pide.
- **«Skills que te faltan» pasa a llamarse «Habilidades por desarrollar»** (en inglés, «Skills to
  build»), con textos que hablan de lo que piden tus ofertas.
- **Plantillas importadas:** la tarjeta enseña la plantilla; el CV original se ve con **Comparar con
  el original**.
- **Textos más claros y profesionales en toda la app:** en español y en inglés, dicen lo que puedes
  hacer en vez de lo que no se hace, explican cada regla una sola vez y dejan las explicaciones largas
  en una ayuda (ⓘ). Algunos ejemplos: «Correo electrónico» en vez de «Usuario (tu dirección)»,
  «Inicia sesión en…», «Tipo de contrato» y «Tipo de jornada», la intro del **Tablero** en una línea
  con su ayuda y **Cómo funciona → Quién hace qué** en viñetas. Los avisos sobre LinkedIn dicen en
  concreto qué puede pasar.
- **Buzones:** si falta la contraseña de un buzón, el aviso dice qué hacer («escríbela en Editar»)
  en vez de nombrar ajustes internos, también en **Respuestas**. La explicación de «Leer aquí también
  las respuestas de las empresas» pasa a una ayuda junto a la casilla.
- **README nuevo, en inglés y en español:** se lee en dos minutos. Demo, funcionalidades, capturas,
  cómo instalarla y abrirla paso a paso, documentación, cómo funciona, por qué CandidatAI (con la
  comparativa en un desplegable), limitaciones conocidas, rendimiento y seguridad. La comparativa
  con AI Job Search y career-ops está al día (6 de noviembre de 2026).
- **Guías al día con la app:** la guía de uso, «Empieza aquí» y la lista de funcionalidades
  describen el menú actual (nueve entradas y sus pestañas), el editor del CV con sus versiones, los
  avisos de lo que hace tu agente y dónde está cada cosa ahora. Los precios de los agentes están
  comprobados a 6 de noviembre de 2026 y el README trae cifras de rendimiento medidas.
- **La candidata de la demo en inglés se llama ahora Olivia Smith.** Si ya tenías la demo cargada,
  `cai demo seed --lang en --force` la vuelve a crear con el nombre nuevo.
- **Bandeja:** las pestañas de arriba pasan a «Bandeja de ofertas», «Por completar» y «Revisión
  rápida» (el orden en que avanzan las ofertas), y en «Por revisar» se quita el botón «Valorar las que
  están por revisar», porque «Valorar las ofertas nuevas» ya valora también esas ofertas. El botón desaparece también de
  Inicio, y la acción ya no sale en la página «Agente» ni en los niveles de gasto.
- **Pantalla de arranque más sobria:** un solo indicador de espera (el anillo alrededor del logo), sin
  tarjeta ni barra, con un texto más corto y en español e inglés a la vez (la página se abre desde el
  disco y no puede saber el idioma de la app). Se quita el enlace «Abrir CandidatAI», que llevaba a un
  error si la app aún no respondía; si tarda más de dos minutos, aparece un botón «Reintentar».
- **Plantillas: «Subir nueva plantilla» y «Usar por defecto» en todas:** el botón «Subir mi CV» de **Plantillas
  de CV** pasa a llamarse **Subir nueva plantilla** y su sección explica que sirve para crear una plantilla a
  partir de un CV de ejemplo, no para rellenar tu perfil (eso es **Importar información desde un CV**, en
  **Mi perfil**). Todas las plantillas, también las de la app, tienen **Usar por defecto**.
- **Mejorar el contenido de mi perfil:** el botón «Ampliar perfil desde mis enlaces» de **Mi perfil** pasa a llamarse **Mejorar
  el contenido de mi perfil** y hace más. Tu agente revisa el perfil entero (logros sin cifra, textos de relleno, huecos,
  incoherencias) y te propone cambios; con tus enlaces públicos (GitHub, portfolio, Kaggle, Scholar) sigue
  proponiendo proyectos, skills, logros y certificaciones, cada uno con su fuente. Solo escribe con tu OK:
  los números y los niveles que falten te los pregunta, nunca los pone. Ya no hace falta que tu agente tenga
  búsqueda web: sin ella, revisa el perfil y se salta los enlaces.
- **Hora a las 14:00 si no sabes la hora:** al elegir un día en un selector de fecha y hora, la hora se pone
  a las 14:00 y no se queda vacía; **Sin hora concreta (14:00)** la devuelve a esas horas. Al programar una
  entrevista o una prueba desde un movimiento, «Hora (opcional)» viene también con las 14:00 (si la borras,
  cuenta todo el día).
- **Selector de fechas y horas:** al registrar un rechazo o una entrevista, programar un hito, aceptar la
  propuesta de una respuesta o elegir «desde» en el embudo, la fecha se elige en un calendario propio, con
  los colores de la app (claro y oscuro), en español e inglés, y no en el desplegable del navegador. La hora
  se escribe en dos casillas (con ↑ y ↓ para subir y bajar) y hay **Hoy**, **Ahora** y **Borrar**. Se maneja
  también con el teclado.
- **Pantalla de arranque:** al abrir CandidatAI, mientras espera a la app, sale el logo con un anillo que
  gira, el mensaje de carga y una barra de espera, en claro y en oscuro. Sigue pasando sola a la app en
  cuanto responde.
- **Ejemplo de modelo en «Agente»:** Claude Code, Codex y Qwen Code también enseñan, en el campo de modelo, un
  ejemplo de cómo se escribe (`sonnet`, `gpt-6.1-sol`, `qwen3-coder-plus`), como ya hacían Antigravity CLI y
  OpenCode.
- **Valorar las ofertas nuevas, en un solo paso:** «Leer las ofertas nuevas» y «Valorar las pendientes» se
  unen en un botón, **Valorar las ofertas nuevas**. Tu agente lee cada oferta nueva (como antes, con un
  subagente aislado que es el único que ve su texto), la app calcula su encaje de 0 a 100 y, a
  continuación, tu agente deja una valoración explicada de por qué encaja contigo o no, también para las
  que ya esperaban en **Por revisar**. Un solo aviso (**Leyendo y valorando las ofertas nuevas…**) y, en
  segundo plano, el mismo umbral antes de gastar. Para solo las que ya están leídas queda **Valorar las que
  están por revisar** (antes «Valorar las pendientes»), en la etapa **Por revisar**; en **Inicio** sale solo
  cuando no hay ofertas por leer.
- **Plantillas:** una sola lista, **Todas las plantillas**, con **Usar por defecto** en cada tuya. Los
  bloques «Original / Con tu perfil» de cada CV subido desaparecen; en **Mi CV** solo queda lo que falta por
  convertir.
- **Corregir un CV es más fiable:** tu agente mide cuántas páginas ocupa antes de guardar. Si pides «que
  ocupe 1 página», la app lo exige: una versión que no cabe no se guarda ni aparece en la ficha, y la que
  tenías sigue igual. El aviso de **CV listo** ya no sale hasta que cabe y está verificado.
- **Investigar empresa:** ya no pregunta nada, ni antes ni después. Busca menos (8 búsquedas y 10 páginas
  como mucho), guarda el dosier, avisa y lo ves en la ficha, en **Empresa**.
- **«Qué cambió»** sale siempre plegado en el historial de versiones del CV.
- **«Qué buscas» se muda a «Buscar ofertas»:** puestos, sueldo, lugar y contrato se editan ahora en esa
  página, no en «Mi perfil». Se siguen guardando en tu perfil.
- **Los botones ya no se mueven:** el aviso de los botones de tu agente («Se ha abierto…») flota debajo
  en vez de empujarlos, y los que cambian de texto («Guardando…») mantienen su ancho.
- **Buscar ofertas, más útil:** portales en tarjetas con su logo, cuántas búsquedas y ofertas implica
  cada uno y qué pasó la última vez; un resumen de tu búsqueda con lo que hay que preparar antes (el
  navegador conectado, la sesión en los portales que la piden); y «Consultar ahora» para las fuentes
  que no necesitan navegador ni agente.
- **Tablero de procesos:** las tarjetas solo se arrastran hacia la derecha, y al arrastrar se ve a qué
  columnas puedes soltarlas. Reabrir una oferta cerrada sigue en «Actualizar estado».
- **«Experiencia y formación»** empieza por Experiencia y sigue con Skills.
- **«Agente»:** la configuración se abre con un botón «Configurar agentes» que dice lo que hay dentro.
- **Leer las respuestas de las empresas se activa a propósito** en cada buzón, también en la cuenta de
  `.env`. La guía de configurar el correo explica exactamente qué puede leer la app y qué lee.
- **Un menú más claro:** Inicio y Mi perfil; en Búsqueda, Bandeja de ofertas, Buscar ofertas y Dónde
  buscar; en Procesos, Tablero, Calendario, Respuestas y Embudo; y Agente. Lo demás sigue ahí, en
  pestañas, y tus enlaces guardados te llevan a su sitio nuevo:
  - **Bandeja de ofertas**: «Revisión rápida» (antes «Por revisar») y «Por completar» (antes
    «Alertas»), con los mismos atajos de teclado. La entrada del menú cuenta lo que tienes por revisar.
  - **Dónde buscar**: «Alertas por correo», con tus buzones, la guía para añadir uno y «Revisar correo
    ahora».
  - **Mi perfil**: ahora es la segunda entrada, con «Skills que te faltan» y «Plantillas de CV». Un
    punto en el menú te avisa si aún no tienes perfil o hay cambios sin guardar.
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
- **«Mi perfil › Documentos», mucho más ligero:** tres tarjetas en lugar de nueve bloques. En
  **Cómo quieres tus CVs y cartas**, cada una resume en una línea lo que elegiste (plantilla, páginas,
  foto, tono…) y se despliega para cambiarlo. En **Notas para tu agente**, tus notas de estilo,
  perfil conductual, criterios y narrativa, y tus muestras de estilo, cada una con su estado y su
  editor debajo al pulsar. En **Tus archivos**, tus carpetas con su botón para subir. Las
  explicaciones largas están en el icono ⓘ, y lo que tiene cambios sin guardar se queda abierto.
- **El historial de «Mi perfil» se entiende sin saber programar:** en vez de un diff del fichero,
  una lista de versiones con cuándo se hizo cada una («Hoy, 18:05»), de dónde viene (la app, tu
  agente, al deshacer) y qué bloques cambió. Al abrir una ves sus cambios por bloques, como
  «Antes → Ahora», con lo añadido en verde y lo quitado tachado, cada uno con su etiqueta. Con
  **Volver a esta versión** recuperas cualquiera: antes te dice qué bloques cambiarán, y se guarda
  como una versión nueva que también puedes deshacer. El cambio técnico sigue ahí, plegado al final.
  Las versiones de antes de esta actualización salen sin origen.
- **Idiomas más claros en «Mi perfil»:** «Idioma» y «Nivel» van en columnas alineadas, también con
  un nivel escrito a mano, y sale de la pantalla «Dónde ponerlo». Si ya lo tenías relleno, se
  conserva en tu perfil y tus CVs lo siguen teniendo en cuenta.

### Corregido
- **El Asistente y la Ayuda ya no cambian de tamaño:** el panel mide lo mismo en las dos pestañas y
  con la barra de conversaciones abierta o cerrada, así que no se mueve al cambiar. Solo su cuerpo
  hace scroll (la cabecera, las pestañas y la caja de escribir quedan fijas), también con el
  teclado, y una conversación larga se lee entera. Con avisos encima, el panel encoge en lugar de
  salirse de la pantalla.
- **Aceptar un correo que cuenta algo ya anotado:** si marcabas como «Rechazo» el correo de una
  candidatura que ya habías cerrado a mano como rechazada, salía un error de fechas. Ahora el correo
  se enlaza a ese registro, sin duplicarlo.
- **Asistente: la respuesta de tu agente sale en cuanto vuelves a él.** Si tu agente contestaba
  desde su ventana una petición que esperaba a tu próxima sesión, al volver al Asistente podía
  tardar hasta 20 segundos en verse. Ahora se pide al momento cada vez que lo abres.
- **Cerrar una candidatura con la fecha en que pasó:** si después habías anotado algo que no encaja
  con el cierre (un seguimiento, o cerrarla y reabrirla para probar), la app ya no da un error
  confuso. Te enseña qué es y te propone quitarlo, si lo anotaste por error, o anotar el cierre
  justo después. Lo que la app recalcula sola, como el encaje, ya no impide cerrarla con una
  fecha pasada.
- **Tu agente no podía conectarse a la app** si esta seguía abierta tras actualizarla: en Windows el
  servidor MCP fallaba con «fichero en uso» o no llegaba a arrancar, y tu agente iba más lento, por otro camino.
- **Tablero:** ya se puede agarrar una tarjeta justo después de soltar otra. Antes, durante un instante, el
  clic no llegaba a la tarjeta y se seleccionaba texto.
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
- **Ninguna web que visites puede cambiar nada en CandidatAI:** antes, una página cualquiera
  abierta en tu navegador podía disparar sin que lo vieras algunas acciones de la app (subir un
  fichero, borrar un hito o un contacto, marcar una candidatura como enviada, abrir el navegador de
  las candidaturas…). Ahora la app solo acepta cambios de su propia ventana, de la CLI y de tu
  agente, y del botón del navegador solo el envío de ofertas, con su clave.
- **«Añadir desde URL» no descarga direcciones de tu red local** aunque lleguen con un nombre de
  dominio que apunte a ellas (por ejemplo, desde el enlace de un correo de alertas).
- **Contraseñas cifradas en el llavero del sistema:** las de tus buzones de correo y las claves de
  Adzuna e InfoJobs se guardan en el Administrador de credenciales de Windows, el Llavero de macOS o
  el llavero de tu escritorio en Linux, y ya no en un fichero de texto. Si tenías alguna guardada
  así, una banda arriba de **Inicio** y de **Alertas por correo** te ofrece **Mover al llavero** (o
  **Ahora no**), y cada buzón dice dónde está su contraseña. Sin llavero (Linux sin sesión
  gráfica) se siguen guardando en el fichero, avisado; en Docker van como secreto o variable del
  contenedor. `cai doctor` avisa de las que siguen en claro.
  Al copiar tus datos a otro equipo, vuelve a escribirlas en **Editar**.
- **pypdf** sube a la 6.21.4, que corrige 7 vulnerabilidades conocidas.
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

[Sin publicar]: https://github.com/DiegoPrieto23/candidatai/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/DiegoPrieto23/candidatai/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/DiegoPrieto23/candidatai/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/DiegoPrieto23/candidatai/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/DiegoPrieto23/candidatai/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/DiegoPrieto23/candidatai/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/DiegoPrieto23/candidatai/releases/tag/v0.1.0
