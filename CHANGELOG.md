# Changelog

Lo que cambia en cada versión de CandidatAI para quien la usa. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[versionado semántico](https://semver.org/lang/es/). Cómo se versiona y se publica: `CONTRIBUTING.md`.

Cada fase añade lo suyo a «Sin publicar». Al publicar, esa sección pasa a ser la de la versión nueva
y su texto son las notas de la release en GitHub (`scripts/release_notes.py`).

## [Sin publicar]

### Añadido

- **La conversación con el agente, en el portal**: lo que se lanza sin ventana dice en el aviso de
  abajo a la derecha en qué paso va («3/6 · Redactar» al generar el CV) o qué está haciendo, y el
  tiempo que lleva. **Ver conversación** abre un panel lateral con cada herramienta que usa el
  agente y lo que escribe; si falla, **Abrir en una ventana** retoma la misma sesión.
- **Preguntas y permisos del agente, en el portal**: sin ventana, lo que pregunta el agente sale en
  el panel de su conversación (el aviso se pone ámbar con **Responder**), y con Claude Code también
  lo que necesita permiso: «Permitir una vez», «Permitir siempre en este proyecto» o «Denegar». Sin
  respuesta en 5 minutos, se deniega. Lo permitido siempre se ve y se quita en la página «Agente».
  Un permiso nunca sustituye la confirmación de una candidatura.
- **«Abrir en una ventana»**, en la página «Agente», para quien prefiera que el botón principal abra
  siempre la ventana del agente.

### Cambiado

- **Los botones del agente ya no abren una ventana si no hace falta**: con Claude Code, Codex u
  OpenCode, «Generar CV», «Valorar esta oferta» y las demás acciones que
  no preguntan van sin ventana y se siguen en el aviso. Las que preguntan o usan el navegador
  siguen abriendo su ventana.
- **Codex y OpenCode generan el CV y la carta sin ventana**: el redactor y el verificador piden las
  políticas a la app en vez de leer el fichero, así que caben en lo que la app les deja hacer.
  Codex trabaja ya sin ventana en todo lo que lo admite salvo «Valorar las ofertas nuevas».
- **Nuevo comando `cai policies show`** (herramienta `get_policies`): las reglas de la app por
  secciones, para los agentes.
- **Claude Code ya no pregunta si usar el servidor de CandidatAI** la primera vez que se abre en la
  carpeta: va aprobado en la configuración del proyecto. Sigue preguntando si confías en la carpeta.
- **La terminal de `cai start` habla en español y en inglés a la vez**: cada mensaje sale en los dos
  idiomas, primero en el del portal.

### Eliminado

- **«Revisar ofertas caducadas»** (skill `review-expired` y herramienta `save_open_check`): abría
  ventanas del navegador para mirar las ofertas una a una. El aviso de la Bandeja sigue, con
  «Descartar las N» y «Comprobar ahora».

## [1.0.0] - 2026-11-27

Primera versión de CandidatAI: una app local para llevar la búsqueda de empleo de principio a fin
(ofertas, revisión con score, CV a medida, candidatura asistida, seguimiento y resultados) con el
agente de IA que ya usas. La app no llama a ningún modelo: el razonamiento lo pone tu agente, y las
reglas (qué se envía, qué no se inventa, qué ve tu agente) las aplica el código.

**Madurez:** es una herramienta para una persona en su propio ordenador (no para el móvil), y hace
falta un agente de IA, que la app no incluye. Windows 11 y Claude Code son lo más probado; el
detalle de sistemas y agentes, en «Limitaciones conocidas» del README y en `docs/AGENTS_COMPAT.md`.

**Cómo instalar:** una línea en Windows (se pega en Windows+R), macOS o Linux, o con Docker; los
pasos, en el README y en `docs/GUIA.md`. Tus datos van aparte y actualizar nunca los toca.

### Añadido

**Conseguir ofertas**
- **Alta de una oferta** pegando su URL o su texto; la misma oferta con otro enlace o un título casi
  igual no se da de alta otra vez, se anota en la original.
- **Empresas con portal propio:** sus ofertas llegan cada día desde Greenhouse, Lever, Ashby,
  Personio, Teamtailor, Workable, SmartRecruiters y Recruitee (APIs públicas, sin scraping), solo
  las que encajan con tu perfil.
- **Buscar ofertas en un solo sitio:** portales y empresas en «Buscar ofertas», con «Buscar ahora»,
  que trae solo ofertas nuevas, y un resumen de cada búsqueda. Tu agente recorre los portales con
  tu navegador, con límites y pausas, y para ante un captcha.
- **Alertas de empleo por correo** (LinkedIn, InfoJobs, Indeed…), por IMAP en solo lectura y con
  varios buzones, con guías para Gmail, Outlook, Yahoo e iCloud; las ofertas resumen se completan
  una a una en «Por completar».
- **Botón «Enviar a CandidatAI»:** una extensión de Chrome, Edge o Brave que manda la oferta abierta
  en el navegador, y se conecta con un clic.
- **Búsqueda pública de LinkedIn**, apagada por defecto: una vez al día, sin cuenta ni cookies, y
  solo si la activas tú.
- **¿Sigue abierta?:** la app comprueba cada día si las ofertas siguen publicadas (las de Indeed,
  en Chrome con la ventana fuera de la pantalla) y marca las de más de un mes. El aviso de la
  Bandeja las reúne, con «Descartar las N», «Comprobar ahora» y «Revisar ofertas caducadas», que
  pide a tu agente mirar las que la app no puede comprobar sola. Nada se cierra sin tu confirmación.
- **Ofertas repetidas y republicadas:** se detectan y se anotan en la original; las que vuelven a
  publicarse tras cerrarlas se pueden reabrir.

**Revisar**
- **Inicio** con lo pendiente de hoy, «Primeros pasos» con la app recién instalada y **Cómo
  funciona**, con el recorrido completo.
- **Bandeja** con filtros (varias etapas a la vez, modalidad, salario, encaje y motivo de cierre),
  búsqueda y explicación de cada etapa.
- **Filtros duros y un encaje de 0 a 100 explicado**, con similitud por significado local opcional.
- **Leer y valorar las ofertas nuevas en un solo paso:** tu agente extrae cada una con un subagente
  aislado y la valora frente al perfil, con riesgos y preguntas.
- **Revisar con el teclado** (`J`/`K`, `A`, `D`, `O` y Deshacer) y **puntos a revisar** en cada
  oferta (rango salarial muy amplio, agencia, contrato temporal…).
- **Ficha de la oferta** en pestañas, con extracción, desglose del encaje, señales, historial,
  notas y contactos de LinkedIn en la empresa.

**CV, carta y candidatura**
- **CV a medida** citando la evidencia del perfil de cada línea: el código rechaza lo que no está y
  otro rol lo verifica.
- **Editor del CV:** pedir cambios en palabras, editar el texto, versiones con «Volver a esta
  versión», y el mismo contenido en cualquier plantilla, foto, color y secciones, sin agente.
- **Plantillas de CV** integradas y propias, e **importar un diseño propio** desde Word, PDF, una
  imagen, HTML, Canva o Google Docs.
- **Carta de presentación** verificada, en TXT y PDF a juego con el CV.
- **Paquete de candidatura** con el CV, las respuestas de screening y la carta, y **candidatura
  asistida**, que rellena formularios de Greenhouse, Lever, Ashby o genéricos y solo envía tras
  escribir el nombre de la empresa.
- **Correos de candidatura y mensajes de LinkedIn** como borradores que envías tú, y **archivo** de
  lo enviado.

**Seguimiento, entrevistas y ofertas**
- **Tablero** que solo avanza con eventos registrados, con columnas a tu gusto, y **ficha del
  proceso** con hitos, contactos y «¿Qué ha pasado?».
- **Calendario** con entrevistas, pruebas y plazos, un `.ics` por hito y un feed para tu calendario.
- **Respuestas de las empresas:** la app lee el correo en solo lectura, tu agente las clasifica
  (entrevista, prueba, oferta, rechazo) y nada cambia de etapa hasta que lo aceptas.
- **Seguimientos y agradecimientos** como borradores.
- **Investigar la empresa** con fuentes, **preparar la entrevista** con una guía en PDF y un plan por
  días, **simulacro**, **repaso** con historias STAR nuevas, **ofertas recibidas** comparadas con tu
  sueldo mínimo (que tu agente nunca ve) y **negociación** con la cifra en blanco.

**Estrategia y perfil**
- **Resultados:** de lo enviado a lo aceptado, tasa y tiempo de respuesta por canal, «¿Acierta el
  encaje?» y la búsqueda en números para compartir (`cai stats story`, solo cifras).
- **Retrospectiva semanal**, **habilidades por desarrollar**, **plan de formación** y **ampliar la
  búsqueda** con títulos cercanos.
- **Mi perfil, editable**, con historial de versiones, foto opcional, resumen en inglés, crear o
  importar el perfil desde un CV y **mejorarlo** (`expand`) con tus enlaces públicos, siempre con tu
  confirmación. Revisión del perfil de LinkedIn.

**La app y los agentes**
- **Cinco agentes:** Claude Code, Codex, Antigravity CLI, OpenCode y Qwen Code, por MCP o con
  `cai … --json`, también con modelos gratuitos y locales. Agente y modelo por acción, y niveles de
  gasto.
- **Botones del agente en toda la app:** abren tu agente con la orden ya escrita en una ventana
  detrás del navegador (en Windows, minimizada en la barra de tareas), en segundo plano o para la
  próxima sesión. Lo que hace sale en un aviso, con «Detener».
- **Asistente** en la esquina para pedirle cosas a tu agente en tus palabras, con conversaciones e
  historial, y **ayuda** en todas las páginas (tecla `?`), sin conexión.
- **Barra lateral** agrupada, tema claro y oscuro, español e inglés, y navegación con el teclado.
- **Borrar una oferta o vaciarlo todo**, con confirmación y copia de seguridad previa.
- **Modo demo** con una búsqueda ficticia.
- **Instalación** con una línea en Windows, macOS y Linux (en el idioma de la web desde la que se
  copia, y la app se abre sola al terminar), o con Docker; `cai doctor` lo revisa todo.
- **Aviso de versión nueva** en Inicio; con el instalador de Windows, «Actualizar ahora» la instala
  y vuelve a abrir la app sin tocar tus datos. `CAI_UPDATE_CHECK=off` lo desactiva.

### Seguridad
- El texto de ofertas, correos y webs se trata siempre como datos: se detectan las instrucciones
  ocultas y las frases de inyección, la oferta queda marcada y nunca sale como encaje fuerte.
- Nada sale hacia terceros sin tu confirmación en la UI: la app nunca envía correos ni mensajes, y
  una candidatura solo se envía con una confirmación de un solo uso.
- La API escucha solo en 127.0.0.1, solo acepta cambios de su propia ventana, de la CLI y de tu
  agente, y las descargas rechazan direcciones locales y privadas.
- Las contraseñas de los buzones y las claves de los portales se guardan en el llavero del sistema.
- Tu agente no ve tu email, tu teléfono, tu sueldo mínimo ni esas contraseñas, y no tiene
  herramientas para escribir tu perfil sin tu confirmación.
- Los instaladores no instalan una release cuya suma SHA-256 no coincide con la publicada.

[Sin publicar]: https://github.com/DiegoPrieto23/candidatai/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/DiegoPrieto23/candidatai/releases/tag/v1.0.0
