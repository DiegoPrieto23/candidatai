# Changelog

Lo que cambia en cada versión de CandidatAI para quien la usa. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[versionado semántico](https://semver.org/lang/es/). Cómo se versiona y se publica: `CONTRIBUTING.md`.

Cada fase añade lo suyo a «Sin publicar». Al publicar, esa sección pasa a ser la de la versión nueva
y su texto son las notas de la release en GitHub (`scripts/release_notes.py`).

## [Sin publicar]

### Añadido
- **Calendario:** página nueva en «Procesos» con tus entrevistas, pruebas, plazos y otros hitos por
  mes, semana, día o agenda, como en Google Calendar o Apple Calendar. Incluye los ya hechos o
  cancelados y los plazos de las ofertas que aún no has enviado; al pulsar un hito ves sus datos, el
  enlace a la oferta y su `.ics`.
- **Una demo con todo:** `cai demo seed` trae también lo que dejarían la candidata y su agente
  (carta, respuestas de screening, mensajes, dosieres de empresa, plan y repaso de entrevistas,
  oferta recibida, correos en «Respuestas», huecos en «Skills», un encargo, contexto y una muestra
  de estilo), así que ninguna pantalla sale vacía.
- **Instalador para macOS y Linux:** `curl -fsSL …/install.sh | bash` instala CandidatAI sin
  `sudo`, con tus datos aparte, y crea el acceso directo (la app «CandidatAI» en macOS y una entrada
  en el menú de aplicaciones en Linux). `--dry-run` explica lo que haría y `--uninstall` nunca
  borra tus datos sin que lo confirmes.
- **Botones «en tu agente» en macOS y Linux:** abren Terminal.app (o iTerm2) en macOS y la
  terminal de tu escritorio en Linux (GNOME Terminal, Konsole, Xfce, kitty, WezTerm, Alacritty…).
  `CAI_TERMINAL` en `.env` elige otra. Sin terminal, el botón copia la orden, como antes.
- **`cai paths`** dice qué carpeta de datos usas y dónde va la app instalada en tu sistema.
- **Probado en Windows, macOS y Linux:** la CI pasa la suite en los tres y prueba el instalador y
  Docker. La guía dice dónde guarda tus datos cada sistema y cómo hacer copia de seguridad.
- **Docker, opcional:** `docker compose up -d --build` arranca CandidatAI sin instalar Python ni
  Chromium, solo en tu equipo (`127.0.0.1:8000`) y con tus datos en un volumen. Tu agente se queda
  fuera y usa la app por MCP (`docker exec -i candidatai cai-mcp`) o `cai … --json`. Dentro, los
  botones «en tu agente» copian la orden, no hay segundo plano y la candidatura asistida abre la
  oferta en tu navegador para que la envíes tú. Lo recomendado sigue siendo el instalador.
- **Varios agentes, a elegir desde la UI.** Además de Claude Code y Codex, configuración lista para
  OpenCode y Qwen Code (open-source) y Antigravity CLI. `cai agents list` y `cai agents doctor` dicen
  cuáles tienes y qué sabe hacer cada uno (MCP, subagentes, segundo plano, web, navegador, modelos
  locales). En la UI eliges el agente por defecto, uno por acción y «con Claude Code ▾» en cada botón.
- **Segundo plano con OpenCode** para `process-jobs` y `assess-fit`, con el mismo límite de
  herramientas que Claude Code.
- **Modelos gratuitos y locales:** la guía `docs/MODELOS_GRATIS.md` (Ollama en Windows, qué modelo
  según tu memoria y qué sale de tu equipo), el diagnóstico de tu Ollama y los niveles de gasto
  «Económico», «Equilibrado» y «Máximo», que se aplican con un clic y se deshacen. Con medidas
  reales: con 16 GB de RAM y sin gráfica, `gpt-oss:20b` no es viable y un agente con un modelo
  local tarda 15-20 minutos en su primera respuesta, así que la guía explica cómo ahorrar memoria
  en Ollama y cómo usar OpenCode con un modelo gratuito de OpenRouter. `cai eval compat --cases 1`
  prueba tu agente con una sola oferta, para no gastar el cupo gratuito en la matriz entera.
- **Codex, probado:** extrae, valora y genera el CV de la matriz de una oferta. Ahora usa la carpeta
  de la demo (antes abría `data/`) y no pide permiso para las herramientas que Claude Code tampoco
  pide.
- **Esquemas para cualquier modelo:** `cai schema` y `get_schema` dan cada entrada con un ejemplo, y
  los errores dicen qué campo arreglar y cómo.
- **`cai eval compat`** pasa la matriz de compatibilidad a cualquier agente y modelo.
- **Más fuentes de ofertas sin scraping:** Personio, Teamtailor, Workable, SmartRecruiters y
  Recruitee para tus empresas objetivo, y los portales Manfred y freehire.me. `cai sources discover`
  busca también en esos cinco ATS.
- **Skill `expand`** y botón «Ampliar perfil desde mis enlaces»: tu agente lee tu GitHub, portfolio,
  Kaggle o Scholar públicos y te propone proyectos, skills, logros y certificaciones, cada uno con su
  fuente. Solo entra en el perfil lo que aceptes.
- **Señales de oferta dudosa** en la bandeja, el triaje y la ficha: rango salarial muy amplio,
  empresa oculta o agencia, contrato temporal, publicada hace meses y cribado con IA. No cambian el
  score; «¿Acierta el score?» enseña si esas ofertas responden peor.
- **Banderas rojas de la empresa** en el dosier (despidos, rotación, reseñas, impagos, conflictos),
  cada una con su fuente y su fecha.
- **Coste por oferta, acción, agente y modelo** en la página «Agente», la ficha y el embudo (por
  candidatura enviada y por entrevista).
- **Umbral de score** antes de «Evaluar encaje» en segundo plano y **hasta 4 ejecuciones a la vez**,
  nunca dos de la misma oferta.
- **Revisión de la maquetación del PDF** del CV y la carta: títulos huérfanos, huecos, texto en el
  pie, una última página casi vacía o un PDF que no deja leer tu nombre, con la página y el arreglo.
- **Tu búsqueda en números:** `cai stats story` y una tarjeta en el Embudo con las ofertas evaluadas,
  las candidaturas, las respuestas, las entrevistas y las ofertas desde el principio, y una línea
  para tu README en español y en inglés. Solo cifras, sin empresas; publicarlo o no lo decides tú.
- **Este `CHANGELOG`**, del que salen las notas de cada release.
- **«Mi perfil» editable, sin YAML:** experiencia y logros, proyectos, formación, certificaciones,
  otras secciones, idiomas y skills, historias STAR (con sus evidencias elegidas por nombre), qué
  buscas, y tus preferencias de CV y carta, por bloques. Cada bloque se guarda solo, valida en el
  campo que toca, conserva los comentarios y el formato de tu `profile.yaml`, avisa si lo cambiaste
  por fuera y deja una copia que se puede deshacer. Cambiar lo que buscas o tus skills enseña antes
  el cambio y recalcula los scores.
- **Contexto y muestras de estilo en la UI:** los cuatro ficheros de contexto se editan con vista
  previa, y puedes subir cartas, correos o posts tuyos para que tu agente copie tu tono (nunca tus
  hechos).
- **«Mejorar con mi agente»** en cada logro e historia, y **«Proponer historias desde mi
  experiencia»**: tu agente propone, te pregunta los números que falten y solo escribe con tu OK.

### Cambiado
- «Procesos»: la tabla «Ofertas recibidas» solo aparece cuando tienes dos o más ofertas que
  comparar (con una, repetía la ficha) y va al final, tras «Próximos 7 días».
- En macOS y Linux, cancelar una ejecución en segundo plano o cerrar `cai start` para también lo que
  lanzó el agente, y al arrancar el worker se paran las que quedaron huérfanas. LibreOffice se busca
  también en las rutas de macOS y Linux (no en Flatpak ni Snap, que no pueden convertir los
  ficheros de la app), y «Abrir carpeta» abre el explorador de archivos.
- Las releases de GitHub llevan como notas la sección de su versión en este `CHANGELOG`, en lugar de
  la lista de commits; la release falla si esa sección no existe.
- Codex puede usar modelos locales con el preset `local`.
- «Usar por defecto» en Plantillas deja una copia de tu perfil en `data/profile-history/`, como el
  resto de cambios desde «Mi perfil».

### Eliminado
- Gemini CLI deja de estar soportado: Antigravity CLI ocupa su lugar.

### Corregido
- En macOS y Linux, archivar una candidatura a la vez desde dos sitios (el worker y la CLI) ya no
  puede dar por archivada una carpeta vacía.
- La plantilla `moderna-2col` deja que un ATS lea primero tu nombre.
- En una demo, los botones «en tu agente» abren el agente sobre la demo: antes, una pestaña nueva
  de Windows Terminal podía dejarlo sobre tus datos reales.

### Seguridad
- Solo la UI puede escribir tu perfil, tu contexto y tus muestras, y leer tu perfil con contacto;
  tu agente sigue sin ninguna herramienta para escribir el perfil. Las muestras de estilo le llegan
  como contenido no confiable, con la detección de inyección.

## [0.1.0] - 2026-10-16

Primera versión: todo lo hecho hasta la fase 23. No llegó a publicarse como release de GitHub.

### Añadido
- **Alta de ofertas** por URL (también con el JSON-LD de la página) o pegando el texto, con
  duplicados exactos y parecidos.
- **Interfaz para agentes:** servidor MCP `candidatai` y CLI `cai … --json` con las mismas
  herramientas, entradas y salidas, para que funcione con cualquier agente, tenga MCP o no.
- **Perfil del candidato** en `data/profile.yaml`, validado y versionado, con niveles privados de
  skill, logros con métricas, historias STAR y preferencias de CV (plantilla, foto y reglas por
  portal o país).
- **Contexto del candidato** (`data/contexto/`: estilo, perfil conductual, criterios y narrativa) y
  `data/documentos/`, con archivo de lo que enviaste en cada candidatura.
- **UI local** en español e inglés, con tema claro y oscuro, barra lateral y móvil: bandeja, triaje
  con teclado, ficha de la oferta, procesos, embudo, skills, respuestas, plataformas y agente.
- **Matching y triaje:** filtros duros, score 0-100 explicado, triaje con teclado y «Deshacer», y el
  skill `assess-fit`. Evals de matching con `cai eval matching`.
- **CV a medida** con contenido y presentación separados: cada bullet cita su evidencia del perfil,
  un verificador independiente revisa que nada esté inventado, y cambiar de plantilla, foto o color
  no gasta agente. Motores docx y html, plantillas `ats-simple`, `clasica-foto` y `moderna-2col`, y
  tus propios CVs (Word, PDF, imagen o HTML) convertidos en plantilla.
- **Carta de presentación** con indicaciones generales y por oferta, verificación, TXT y PDF a juego
  con el CV.
- **Fuentes de ofertas:** Greenhouse, Lever y Ashby a diario (InfoJobs y Adzuna opcionales), alertas
  por correo (IMAP en solo lectura o `.eml`), la extensión «Enviar a CandidatAI» para Chrome y Edge,
  búsqueda en portales con tu navegador y, opcional y apagada, la búsqueda pública de LinkedIn sin
  sesión.
- **Seguimiento:** kanban de procesos, hitos con hora, contactos, avisos de seguimiento, calendario
  `.ics`, paquete de candidatura con respuestas de screening y candidatura asistida que rellena el
  formulario y se para antes de enviar.
- **Respuestas por correo** de las empresas a las que enviaste candidatura, clasificadas por tu
  agente y aceptadas por ti; borradores de seguimiento y agradecimiento que envías tú.
- **Ofertas vivas y republicadas:** aviso si una oferta ya no está publicada (nunca la cierra sola)
  y «Republicada ×N».
- **Entrevistas:** plan por días, simulacro, repaso con historias STAR nuevas y dudas antes de
  aceptar una oferta.
- **Red de LinkedIn** desde su exportación oficial, «Conoces a N» en cada empresa, mensajes y correos
  de candidatura redactados y dosier de empresa con fuentes.
- **Lote en segundo plano** (procesar, evaluar y generar CV sin ventana) y «Dejar para mi próxima
  sesión».
- **Analítica:** embudo con desgloses por fuente, puesto, semana y referencia, tiempo hasta la
  primera respuesta y «¿Acierta el score?» con intervalos de confianza.
- **Ofertas recibidas y salario:** comparativa con tu mínimo (que tu agente nunca ve) y preparación
  de la negociación sin proponer cifras.
- **Huecos de skills** con sinónimos, plan de formación con recursos verificados.
- **Modo demo** con una búsqueda ficticia en español o inglés (`cai demo seed`).
- **Instalación con un clic** en Windows (`install.ps1`) y `cai start` para arrancarlo todo.

### Seguridad
- El texto de ofertas, correos y webs se trata siempre como datos: se detectan instrucciones ocultas
  y frases de inyección, y la oferta queda marcada.
- Descargas protegidas: nada de LinkedIn ni de IPs locales tras una redirección, y tamaño máximo.
- La API escucha solo en 127.0.0.1 y la extensión va con token y origen.
- Nada sale hacia terceros sin tu confirmación en la UI: la candidatura asistida solo envía con una
  confirmación de un solo uso, y la app nunca envía correos ni mensajes.
- `get_profile` nunca da a tu agente tu email, tu teléfono ni tus datos privados.

[Sin publicar]: https://github.com/DiegoPrieto23/candidatai/compare/4d9d8b4...HEAD
[0.1.0]: https://github.com/DiegoPrieto23/candidatai/tree/4d9d8b4
