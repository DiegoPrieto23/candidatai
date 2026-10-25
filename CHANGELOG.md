# Changelog

Lo que cambia en cada versión de CandidatAI para quien la usa. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[versionado semántico](https://semver.org/lang/es/). Cómo se versiona y se publica: `CONTRIBUTING.md`.

Cada fase añade lo suyo a «Sin publicar». Al publicar, esa sección pasa a ser la de la versión nueva
y su texto son las notas de la release en GitHub (`scripts/release_notes.py`).

## [Sin publicar]

### Cambiado
- **Capturas y animaciones nuevas** en los README y en las listas de funcionalidades, en español
  e inglés: cada página tiene la suya, las principales también en modo oscuro, y seis animaciones
  cortas enseñan el triaje, descartar desde la Bandeja, añadir un buzón, cambiar el CV, «Mi perfil»
  y la candidatura asistida. Pesan mucho menos (WebP) y ya no hay vídeo.
- **La demo trae alertas por correo:** 65 ofertas, 5 de ellas de dos buzones de alertas, así que la
  página «Alertas» ya no sale vacía.

## [0.1.0] - 2026-10-24

Primera versión publicada de CandidatAI: una app local para llevar tu búsqueda de empleo de
principio a fin (ofertas, triaje, CV a medida, candidatura, seguimiento y análisis) con el agente de
IA que ya usas. La app no llama a ningún modelo: el razonamiento lo pone tu agente y las reglas
(qué se envía, qué se inventa, qué ve tu agente) las aplica el código.

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
- **Triaje que se explica:** filtros de lo que no quieres (ubicación, sueldo mínimo privado, años,
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
