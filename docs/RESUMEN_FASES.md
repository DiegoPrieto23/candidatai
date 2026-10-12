# Qué hace cada fase

Lo principal que aporta cada fase y subfase de Job Hunter: qué puedes hacer gracias a ella y las
piezas que la sostienen. El detalle (decisiones, deuda, cifras de tests) está en el registro de
`docs/ROADMAP.md`. Las pruebas manuales, en `docs/pruebas/`.

**Estado a 2026-10-05:**
- Hechas las 12 fases, con la 05b, la 08b y la 08c.
- 31 herramientas MCP con su comando `jh` equivalente, 12 skills, 4 roles y 12 migraciones.
- 1 627 tests de backend y 125 de frontend.

**La idea de fondo:** la app no llama a ningún LLM. Ingesta, triaje, CVs, cartas, seguimiento y
analítica viven en la app (FastAPI + SQLite, UI en React, CLI `jh`). Lo que necesita razonar
(extraer ofertas, valorar el encaje, redactar el CV y la carta) lo hace tu agente (Claude Code,
Codex…) a través de herramientas MCP o de la CLI, siempre contra tu perfil y con verificación.

---

## 01 · Arranque del repo
- Esqueleto del proyecto: backend Python 3.12 con `uv`, frontend Vite + React + TypeScript, CI en
  Windows y sincronización de la configuración de agentes.
- `jh doctor`: diagnóstico del entorno que crece fase a fase (LibreOffice, Chromium, plantillas,
  correo, captura…).

## 02 · Núcleo de datos
- Base de datos SQLite con el modelo completo y migraciones de Alembic.
- **Cada cambio de una oferta es un evento** y la etapa se deriva de ellos. Las transiciones
  válidas están en una tabla (`pipeline.py`) probada combinación a combinación. Eso da el
  historial y lo que permite la analítica.
- Normalización de empresa, título y ubicación, y una huella para detectar duplicados.

## 03 · Alta de ofertas
- Alta **por URL** (descarga y extrae el texto, también del JSON-LD) o **pegando el texto**.
- Duplicados exactos y parecidos: un duplicado se cierra y apunta a la original.
- **Detección de inyección**: texto oculto en el HTML y frases sospechosas marcan la oferta. El
  texto de las ofertas siempre se trata como datos, nunca como instrucciones.
- Descarga protegida: nada de LinkedIn ni de IPs locales tras una redirección; tamaño máximo.

## 04 · Interfaz para agentes
- **Servidor MCP `jobhunter`** y **CLI `jh … --json`** con paridad: cada herramienta existe en
  los dos con la misma entrada, salida y errores. Un test lo comprueba. Así la app funciona con
  cualquier agente, tenga MCP o no.
- Formato de error común y auditoría de las llamadas de los agentes.
- `JobExtraction` y el skill `procesar-ofertas`: el agente extrae cada oferta (rol `extractor`,
  aislado) y la app la guarda validada.

## 05 · Perfil del candidato
- `data/profile.yaml`, validado y **versionado**: la única fuente de verdad para CVs, cartas y
  respuestas.
- Niveles privados de skill (F, C+, C, B), logros con métricas, historias STAR y marcas de NDA.
- `get_profile` nunca devuelve email, teléfono ni los datos privados.
- Skill `actualizar-perfil`.

### 05b · Preferencias de CV en el perfil
- Plantilla por defecto, foto, política de foto por país y **reglas de plantilla**: por ejemplo,
  `ats-simple` sin foto para ofertas en Workday o en el Reino Unido.

## 06 · Frontend base
- API REST local (`jh serve`, solo en 127.0.0.1) y UI: **bandeja** con filtros y búsqueda,
  **ficha de la oferta** (extracción, historial, notas), **alta** por URL o texto.
- Tema claro y oscuro, móvil, cliente de API generado desde el OpenAPI.

## 07 · Matching y triaje
- **Filtros duros** al extraer: seniority, años, modalidad, zona, idiomas y palabras de descarte.
- **Score 0-100 explicado**: cobertura de skills ponderada por tu nivel, similitud semántica
  opcional y preferencias.
- **Triaje con teclado** (J/K, A aprobar, D descartar con motivo, O abrir) y «Deshacer».
- Skill `evaluar-encaje`: valoración del agente con riesgos y preguntas.
- Cola de tareas y `jh worker`. Evaluación del matching con `jh eval matching`.

## 08 · CV a medida con plantillas
La idea: **contenido y presentación separados**. El agente redacta el contenido una vez; cambiar
de plantilla, foto o color no vuelve a usarlo.

### 08.1 · Contenido, verificación y motor docx
- Skill `generar-cv`:
  - el rol `redactor` escribe el `CvContent`, donde **cada bullet cita su evidencia** del perfil;
  - el código rechaza lo que no existe en el perfil;
  - el rol `verificador`, en otra ejecución, revisa que nada esté inventado ni exagerado.
- Motor docx (Word con marcadores) y PDF con LibreOffice o Word. Plantilla `ats-simple`.
- La oferta pasa a **«CV listo»** solo cuando el mismo CV está verificado y tiene un PDF que cabe.
- El contacto lo pone el código: el agente nunca lo ve.

### 08.2 · Foto, renders múltiples y UI
- Sección **«CV»** en la ficha, sin agente:
  - eliges plantilla con miniatura, foto (automática, con o sin), color y secciones, y pulsas
    «Renderizar»;
  - comparas renders lado a lado y marcas cuál envías.
- Plantilla `clasica-foto` y recorte automático de tu foto.
- Página **Plantillas**.

### 08.3 · Importar plantillas desde Word y «Mi CV»
- **Tu CV de Word se convierte una vez en plantilla**, con su diseño exacto, su orden de
  secciones y su extensión medida. Lo hace el skill `importar-plantilla-cv`.
- «Mi CV» en Plantillas: el original y la versión con tu perfil, lado a lado, y «Usar por
  defecto». Este último solo toca esa línea de tu perfil y conserva los comentarios.
- Secciones extra del perfil (voluntariado, premios…).

## 08b · Motor html e importación de CVs en cualquier formato
- **Motor html**: Jinja2 y Chromium, sin red ni JavaScript, con saneado en dos capas.
- Plantilla `moderna-2col`: dos columnas, foto y 4 colores.
- **CVs en PDF o imagen** (Canva y similares) se recrean como plantilla html. La app los analiza
  (`inspect`), crea una base (`scaffold-html`) y compara el resultado con el original
  (`compare`); el agente la afina.

## 08c · Carta de presentación
La carta es un documento propio, con sus indicaciones, su verificación y sus renders.

### 08c.1 · Indicaciones, contenido, verificación y render básico
- **Indicaciones en dos niveles**: generales en tu perfil (`preferences.cover_letter`: tono,
  extensión, despedida, qué contar y qué evitar) y las de cada oferta, que mandan.
- Skill `generar-carta`. Cada párrafo cita su respaldo: tu perfil, la oferta (`extraction`) o
  lo que contaste en tus indicaciones (`user`).
- El código rechaza:
  - evidencias que no existen y `user` sin indicaciones;
  - más palabras que el límite;
  - skills que no tienes y skills básicas que la oferta no pide.
- Verificación por el rol `verificador`. **TXT** para pegar en formularios y PDF. Plantilla
  `carta-simple`.

### 08c.2 · Diseño a juego con el CV
- La carta sale con **la misma cabecera, foto y color que el CV seleccionado**: `ats-simple`,
  `clasica-foto` y `moderna-2col` traen su carta.
- `jh templates build-letter` crea la carta de **tu plantilla de Word** a partir de su cabecera.
- Añadir cartas no marca tus CVs ya hechos como «Plantilla cambiada».

### 08c.3 · API, UI y paquete de candidatura
- Sección **«Carta de presentación»** en la ficha:
  - escribes las indicaciones de la oferta;
  - copias el texto, descargas el TXT o el PDF;
  - cambias el diseño, la foto o el color;
  - retocas el texto a mano: se guarda como una carta nueva «Editada por ti», sin verificar;
  - marcas cuál envías.
- La carta aparece en el paquete de candidatura.

## 09 · Conectores de ATS y scheduler
- **Ingesta diaria sin intervención** de tus empresas objetivo en Greenhouse, Lever y Ashby.
  InfoJobs y Adzuna son opcionales, con claves.
- Filtro previo por título y zona, sin duplicados al repetir y recuperación si el worker estuvo
  apagado.
- Pantalla **«Empresas»**: «Probar» («12 encontradas, 3 tras filtros») y luego seguir la empresa.

## 09b · Alertas, captura y búsqueda con navegador

### 09b.1 · Ofertas resumen y alertas por correo
- **Las alertas de empleo que te llegan por correo entran solas**: LinkedIn, InfoJobs, Indeed,
  Tecnoempleo…
  - por IMAP en solo lectura, o dejando los `.eml` en `data/inbox/`;
  - entran como ofertas «resumen», ordenadas por el filtro previo;
  - caducan solas a los 21 días.
- Pantalla **«Alertas»** con teclado y descarte con motivo.

### 09b.2 · Botón «Enviar a Job Hunter»
- **Extensión de Chrome/Edge**: un clic manda la oferta que estás viendo (LinkedIn incluido) o
  completa el resumen de una alerta, sin duplicarla.
- Protegida con token y origen.

### 09b.3 · Plataformas y búsqueda con navegador
- Skill `buscar-ofertas`:
  - te ayuda a elegir portales;
  - recorre tus búsquedas con tu navegador, con límites de páginas y pausas;
  - da de alta lo que encaja, sin duplicar;
  - para ante captchas.
- Pantalla **«Plataformas»**. **LinkedIn solo si lo activas tú**, con aviso de riesgo; el agente
  no puede activarlo.

## 10 · Seguimiento y analítica

### 10.1 · Kanban, ficha de proceso y calendario
- **Kanban «Procesos»** (Aprobada → CV listo → Enviada → En proceso → Cerrada). Moverse siempre
  registra un evento, con su fecha, nota y canal; funciona con ratón, teclado y táctil.
- Ficha de proceso:
  - **hitos con hora de Madrid** (entrevistas, pruebas, plazos) y contactos;
  - **aviso de seguimientos** a los 10 días sin respuesta.
- **Calendario**: `.ics` por hito y un feed con todos, que se importan en Google Calendar sin
  duplicar.

### 10.2 · Analítica: dashboard del embudo
- Página **«Embudo»**:
  - conversión paso a paso (encontradas → … → aceptadas);
  - desgloses por fuente, puesto y semana;
  - tiempo hasta la primera respuesta y motivos de descarte.
- Carga en menos de 1 s con 1 000 ofertas. También para el agente: `get_funnel_stats`.

### 10.3 · Paquete de candidatura
- Todo lo necesario para enviar a mano, en un sitio: el CV elegido, las **respuestas de
  screening** con un botón de copiar cada una y la carta.
- Skill `preparar-candidatura`:
  - el salario y cualquier dato que no esté en tu perfil quedan pendientes de ti, nunca
    inventados;
  - las respuestas se editan sin agente.
- Ningún botón envía nada: el envío es de la fase 11.

## 11 · Candidatura asistida

### 11.1 · Motor de rellenado y envío protegido
- El worker abre su propio navegador (visible, con tus sesiones en `data/browser-profile/`) y
  **rellena** formularios de Greenhouse, Lever, Ashby y webs con formulario: datos del perfil, CV
  elegido, carta y respuestas del paquete, localizando cada campo por su etiqueta.
- **Se para antes de enviar** y hace una captura. Con captcha, anti-bot o login, te pasa la
  pestaña.
- Nunca rellena datos sensibles (género, origen, salud…).
- Solo envía con una **confirmación de un solo uso**, sin reintentos. Un test comprueba que nada
  más pulsa el envío.

### 11.2 · Revisión, envío y UI
- Sección **«Candidatura asistida»** en la ficha:
  - «Preparar candidatura» y la **pantalla de revisión**: captura, tabla de campos (qué se
    rellenó y de dónde sale, qué falta) y avisos;
  - **«Enviar»**: escribes el nombre de la empresa; te dice qué botón pulsará, en qué web y qué
    consentimientos aceptas;
  - «Volver a revisar» tras completar algo a mano, «Lo termino yo» y «Marcar como enviada».
- La candidatura queda registrada como enviada con la **captura de confirmación** como prueba.
- LinkedIn y webs desconocidas: solo «Abrir y preparar».

## 12 · Demo, compatibilidad y portfolio

### 12.1 · Modo demo
- **`jh demo seed`** crea `data-demo/` con una búsqueda ficticia: la candidata de `demo/`, 60
  ofertas inventadas con extracción y score, 8 semanas de historial (descartes, envíos,
  respuestas, entrevistas, una oferta) y 2 CVs verificados. Determinista y nunca toca `data/`.
- Con `JH_DATA_DIR=data-demo`, la UI muestra un banner **«Modo demo»** y `get_status` dice
  `demo_mode`.

### 12.2 · Evals de matching y de CV
- **Matching:** 80 casos inventados; precision 0,88, recall 0,95 y F1 0,92 sin embeddings, con
  los errores típicos explicados en `evals/REPORT.md`.
- **`jh eval cv`:** 7 comprobaciones automáticas sobre los CVs que deja el agente (evidencias,
  skills inventadas o básicas no pedidas, una página, cobertura, idioma y verificación), por
  agente.

### 12.3 · Compatibilidad, README y seguridad
- **Matriz probada:** las mismas 5 ofertas (`jh demo seed --compat`) por `procesar-ofertas`,
  `evaluar-encaje` y `generar-cv`. Claude Code sin MCP: 54 de 55 campos extraídos como se
  esperaba y 5/5 CVs que pasan el eval. Los roles ya traen sus comandos `jh` para agentes sin MCP.
- **README de portfolio** con arquitectura en Mermaid, decisiones, capturas de la demo, métricas
  y límites éticos; la guía de desarrollo por fases pasa a `docs/DESARROLLO_POR_FASES.md`.
- **Seguridad:** `data/` y `.env` nunca se han commiteado y no hay datos del perfil real en el
  historial. CI con una siembra de la demo como prueba de humo.

## 13 · Contexto y documentos — 2026-10-11 · Claude Code (Opus 5.5)
- **Contexto del candidato** en `data/contexto/`: `estilo-redaccion.md`, `perfil-conductual.md`,
  `criterios.md` y `narrativa.md`, que editas en tu editor (`jh context init` los crea vacíos).
  Orientan a tu agente y **nunca respaldan un hecho** (POLICIES §1.5, ADR-025):
  - los CVs y las cartas salen con tu tono;
  - `evaluar-encaje` cita tus deal-breakers como riesgo o motivo de `weak`;
  - `preparar-entrevista` usa tu perfil conductual y tu narrativa;
  - el verificador rechaza un hecho que solo esté ahí.
- **`get_context`** (MCP) y `jh context show --json`, con paridad: el texto de cada fichero con su
  hash, sin los comentarios-guía y con un aviso si pasa de 20 KB.
- **`data/documentos/`** (`cv/`, `linkedin/`, `titulos/`, `referencias/`): `actualizar-perfil` puede
  leer de ahí para crear o ampliar tu perfil, siempre preguntando antes de escribir.
- **Archivo de candidaturas:** al marcar una oferta como enviada, el worker copia a
  `data/documentos/candidaturas/<empresa>_<puesto>_<id>/` el CV, la carta (TXT y PDF), las
  respuestas y un README con fecha, canal, URL y versión del perfil. Si rehaces el CV después, lo
  archivado no cambia. Las anteriores, con `jh applications archive --all`.
- **UI:** página **«Mi perfil»** con el estado de cada fichero de contexto y de cada carpeta, y
  botones «Abrir carpeta». En la ficha de una oferta enviada, «Copia de lo que enviaste» con su
  carpeta.

## 14 · Huecos de skills y vocabulario — 2026-10-11 · Claude Code (Opus 5.5)
- **Página «Skills»:** las skills que piden tus ofertas (abiertas y aprobadas o enviadas en los
  últimos 60 días) y tu perfil no cubre. Muestra cuántas ofertas las piden como obligatorias y como
  deseables, su peso y ofertas de ejemplo.
- **«Es lo mismo que…»:** si es otra forma de llamar a una skill tuya, la eliges y se añade como
  sinónimo en `config/skill_aliases.yaml` sin tocar comentarios ni formato. El score de tus
  ofertas se recalcula solo. El score mide experiencia, no vocabulario (ADR-026).
- **«La tengo» y «No la tengo»:** las que tienes las añade tu agente al perfil con
  `actualizar-perfil` (botón «Añadir al perfil las que tengo»), preguntando nivel y dónde la
  usaste. Las que no, son huecos reales.
- **Skill `plan-formacion`** (botón «Plan de formación»): convierte los huecos en un plan con
  recursos verificados, cada uno con su URL, horas y orden, en `data/documentos/plan-formacion.md`.
  También valora un curso o proyecto que propongas.
- **`get_skill_gaps`** (MCP) y `jh skills gaps --json`, con paridad.

## 15 · Respuestas por correo y seguimientos — 2026-10-11 · Claude Code (Opus 5.5)
- **Respuestas de las empresas:** la app lee tu correo en solo lectura (por defecto, la bandeja
  de entrada) y guarda solo los correos de las empresas a las que has enviado candidatura,
  posteriores al envío. Del resto solo mira remitente, fecha y asunto, y no guarda nada.
- **Skill `revisar-respuestas`** (botón «Revisar respuestas» en Inicio): tu agente propone qué es
  cada correo (entrevista con su fecha, prueba, oferta, rechazo, respuesta o nada) con un
  subagente aislado. Si el correo trae instrucciones para una IA, se marca y no se obedece.
- **Pantalla «Respuestas»** y aviso en la ficha («Parece una invitación a entrevista el jueves 8
  de octubre a las 10:00»): Aceptar, Cambiar o Ignorar. Nada cambia de etapa hasta que aceptas;
  aceptar una entrevista crea su hito en el calendario.
- **Skill `redactar-seguimiento`:** borradores de seguimiento (como mucho 2 por candidatura) y de
  agradecimiento tras una entrevista, en la sección «Borradores» de la ficha. La app nunca envía
  nada: los copias, los mandas tú y pulsas «Ya lo he enviado».
- **Herramientas** `list_replies`, `get_reply`, `save_reply_proposal` y `save_message_draft` (MCP)
  con sus comandos `jh`, con paridad.

## 16 · Ofertas vivas, republicadas y búsqueda ampliada — 2026-10-12 · Claude Code (Opus 5.5)
- **¿Sigue abierta?:** la app comprueba si una oferta sigue publicada: por la API del ATS
  (Greenhouse, Lever, Ashby) o con una petición ligera a su página (404/410, redirección a una
  lista, frases de «oferta cerrada», fecha de caducidad pasada). LinkedIn nunca. Cada día revisa
  las aprobadas y con CV listo, y también al abrir su ficha.
- **Nunca la cierra sola:** la ficha avisa «Puede que ya no esté publicada» con el motivo y ofrece
  «Descartar» (motivo nuevo «Ya no está publicada»), «Sigue abierta» o «Comprobar otra vez». El
  botón «Generar CV» y el skill `generar-cv` avisan antes de gastar cuota.
- **Republicadas:** «Republicada ×N» en bandeja, triaje y ficha cuando la misma empresa vuelve a
  publicar el mismo puesto en el mismo portal en días distintos. Es una observación, no un
  veredicto.
- **Skill `ampliar-busqueda`** (botón en Plataformas): con tus aprobadas y descartadas propone
  títulos cercanos (p. ej. «Analytics Engineer») y, solo con tu OK, los añade a tus puestos o a
  las búsquedas de tus plataformas. Detecta puestos que apruebas y la ingesta automática se deja
  fuera.
- **`jh sources discover --file empresas.txt`:** encuentra el tablero de Greenhouse, Lever o Ashby
  de tus empresas por sus APIs públicas y propone darlas de alta (`--add` lo hace).
- **Herramientas** `check_job_open` y `get_search_titles` (MCP) con sus comandos `jh`, con paridad.

## 17 · Entrevistas: simulacro, repaso y banco de historias — 2026-10-12 · Claude Code (Opus 5.5)
- **Plan de preparación:** `preparar-entrevista` hace, además del dosier, un plan por días hasta
  la entrevista (bloques de 30-60 min: lo flojo primero, historias que ensayar, la empresa, un
  simulacro y logística). Se ve en la ficha, bajo la entrevista, con «Abrir carpeta» del dosier.
- **Simulacro** (skill `simular-entrevista`, botón «Simulacro»): una pregunta cada vez según el
  tipo de entrevista, feedback concreto y una versión mejor solo con tu perfil; al final, puntos
  fuertes y flojos.
- **Repaso** (skill `repasar-entrevista`, botón «Repasar»): le cuentas cómo fue y guarda notas y
  próximos pasos en la entrevista, predice la siguiente ronda y propone historias STAR nuevas.
  Solo entran en tu perfil si dices que sí, con `actualizar-perfil`.
- **Dudas antes de aceptar** (botón en la ficha cuando hay una oferta recibida): contradicciones,
  criterios tuyos sin confirmar y lo que falta por escrito, con la pregunta que harías.
- **Herramientas** `get_interviews`, `save_interview_plan` y `save_interview_notes` (MCP) con sus
  comandos `jh interviews …`, con paridad.

## 18 · Contactos, mensajes e investigación de empresas — 2026-10-12 · Claude Code (Opus 5.5)
- **Tu red de LinkedIn:** descargas la exportación oficial (`Connections.csv`) y la importas con
  `jh contacts import-linkedin` o con «Importar» en la ficha. No guarda emails ni navega LinkedIn.
- **«Conoces a N»:** en la bandeja, el triaje y la ficha ves a quién conoces en cada empresa, con
  su cargo; si el nombre de LinkedIn solo se parece, te lo dice. «Añadir al proceso» lo pasa a los
  contactos de la oferta como referencia, recruiter o responsable.
- **Referencias:** marca «referencia pedida / dada» en el contacto; el embudo enseña si las
  candidaturas con referencia reciben más respuesta.
- **Skill `redactar-mensaje`** (botón «Redactar mensaje»): mensaje de LinkedIn de ≤ 300 caracteres
  o correo de candidatura con asunto y adjuntos, para el recruiter, el responsable o un compañero.
  Se guarda en «Borradores» para copiarlo; nunca se envía.
- **Skill `investigar-empresa`** (botón «Investigar empresa»): dosier con fuentes (producto,
  noticias, cultura de ingeniería, stack) en la sección «Empresa» de la ficha y en
  `data/documentos/empresas/`; se copia al archivo de la candidatura. Lo usan `preparar-entrevista`
  y `redactar-mensaje`; la carta no, salvo lo que copies a sus indicaciones.
- **Herramientas** `get_job_contacts`, `get_company_research` y `save_company_research` (MCP) con
  sus comandos `jh`, con paridad; `save_message_draft` admite `linkedin` y `email`.

## 19 · Lote en segundo plano y cola de encargos — 2026-10-12 · Claude Code (Opus 5.5)
- **«En segundo plano»:** en «Procesar ofertas», «Evaluar encaje» y «Generar CV», el desplegable
  del botón lanza tu agente sin ventana desde el worker, con tu suscripción y solo con las
  herramientas de la app que necesita ese skill (sin terminal ni web). De una en una.
- **Página «Agente»:** cada ejecución con su estado, el progreso (qué herramientas usa), el
  resultado, «Cancelar» y, si el skill necesita algo, sus preguntas con «Contestar en terminal»,
  que sigue en la misma sesión. Un aviso arriba mientras trabaja.
- **Generar CV en segundo plano** solo si no hay skills obligatorias que preguntarte (o las has
  marcado «No la tengo» en Skills); si no, te manda a «En terminal».
- **«Dejar para mi próxima sesión»:** cualquier botón guarda la orden para tu agente. La ve al
  empezar (`get_status`, `resumen-diario`) y la hace con el skill `atender-encargos`, que la cierra
  con un resumen.

## 20 · Calibración y patrones — 2026-10-12 · Claude Code (Opus 5.5)
- **«¿Acierta el score?»** (al final del Embudo): de tus candidaturas enviadas, cuántas tuvieron
  respuesta y entrevista según el score y el veredicto que tenían **al enviarlas**, la fuente, el
  portal, la plantilla del CV, si llevaban carta o referencia y cuánto tardaste en enviarlas.
- **Honesta con pocos datos:** cada tasa lleva su intervalo al 95 % y los grupos con menos de 10
  enviadas se marcan «pocos datos». Si dos intervalos se solapan, no hay diferencia clara.
- **Retrospectiva semanal** con el skill `revisar-busqueda` (botón «Revisar mi búsqueda»): qué
  funciona y qué cambiar, con sus cifras. Solo propone: los pesos y filtros de
  `config/policies.yaml` los cambias tú, con `jh eval matching` antes y después.
- Para agentes y terminal: `get_calibration` ↔ `jh stats calibration`.

## 21 · Ofertas recibidas y salario — 2026-10-12 · Claude Code (Opus 5.5)
- **«Oferta recibida» en la ficha:** anotas lo que te ofrecen (fijo, variable, beneficios,
  modalidad, incorporación y fecha límite para responder). Si faltaba, registra «oferta recibida».
- **«Ofertas recibidas» en Procesos:** tus ofertas lado a lado, con la diferencia con tu mínimo
  (`private.salary_floor_eur`) y con el rango que publicaba la oferta. Solo lo ves tú: tu agente
  nunca recibe tu mínimo ni esas diferencias, y los importes tampoco si los dejas como privados
  (por defecto). Son cuentas, no una recomendación.
- **Skill `preparar-negociacion`** (botón «Preparar negociación»): argumentos sacados de tu
  perfil, qué negociar además del fijo, preguntas y un guion con el hueco de la cifra para que lo
  rellenes tú; revisa el contrato si lo pegas (no es asesoramiento legal).
- **Datos de mercado propios:** `data/documentos/salarios.csv`, opcional, con las fuentes que tú
  recojas; el agente solo cita filas que encajen y nunca inventa rangos.
- Para agentes y terminal: `get_received_offer` ↔ `jh received-offers show`.


## 22 · LinkedIn por sus endpoints públicos (opcional) — 2026-10-12 · Claude Code (Opus 5.5)
- **«Búsqueda pública sin sesión»** en la tarjeta de LinkedIn de Plataformas, **apagada por
  defecto**: si la activas (aceptando el aviso), la app consulta una vez al día la búsqueda pública
  de LinkedIn con tus búsquedas, sin tu cuenta ni cookies. Lo nuevo que pasa tus filtros entra como
  resumen en «Alertas» y lo completas con el botón «Enviar a Job Hunter».
- **Con riesgo y con freno:** va contra las condiciones de LinkedIn y puede bloquear tu IP. Por eso
  va despacio (≥ 10 s entre peticiones, 2 páginas por búsqueda, una vez al día), se corta en el acto
  ante un bloqueo o un captcha y no lo vuelve a intentar en 3 días. Tu agente no puede activarla.
- **Opcional dentro de lo opcional:** «Descargar también la descripción» (otro interruptor
  apagado) trae la oferta completa, a costa de más peticiones.
- Desde la terminal: `jh sources linkedin-public status` y `run`.
