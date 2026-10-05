# Qué hace cada fase

Lo principal que aporta cada fase y subfase de Job Hunter: qué puedes hacer gracias a ella y las
piezas que la sostienen. El detalle (decisiones, deuda, cifras de tests) está en el registro de
`docs/ROADMAP.md`. Las pruebas manuales, en `docs/pruebas/`.

**Estado a 2026-10-05:**
- Hechas las 12 fases, con la 05b, la 08b y la 08c.
- 29 herramientas MCP con su comando `jh` equivalente, 12 skills, 4 roles y 11 migraciones.
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
