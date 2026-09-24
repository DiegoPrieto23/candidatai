# Registro de decisiones (ADR)

Formato corto: contexto → decisión → consecuencias. Añade una entrada nueva en lugar de editar
una antigua; si una decisión cambia, la nueva la marca como sustituida.

## ADR-001 · El razonamiento lo pone el agente del usuario, sin API de LLM
- **Contexto:** el coste debe asumirlo la suscripción que cada persona ya tenga; la API se factura aparte.
- **Decisión:** la app no llama a ningún modelo. Expone una interfaz para agentes (ADR-010) y el
  agente del usuario hace el razonamiento mediante skills y roles.
- **Consecuencias:** sin coste extra por uso. Lo que necesita LLM queda en cola hasta que se
  ejecuta un skill (o una tarea programada del agente, si la soporta). Los botones de la UI no
  pueden generar texto por sí solos. Toda la frontera con el LLM está en la interfaz para agentes,
  así que añadir una vía por API en el futuro no obliga a rehacer los servicios.

## ADR-002 · SQLite + SQLAlchemy 2 + Alembic
- **Contexto:** un solo usuario en local; despliegue más adelante.
- **Decisión:** SQLite en modo WAL con migraciones de Alembic desde el primer día.
- **Consecuencias:** cero administración. Pasar a Postgres es cambiar la URL de conexión.

## ADR-003 · FastAPI + React (Vite, TypeScript)
- **Contexto:** hace falta kanban, flujos de confirmación y tareas largas; además, es portfolio.
- **Decisión:** API REST en FastAPI y SPA en React con shadcn/ui y TanStack Query; cliente
  tipado generado desde OpenAPI.
- **Descartado:** Streamlit (modelo de re-ejecución incompatible con kanban y confirmaciones),
  Next.js (segundo backend en JS), Reflex (ecosistema pequeño).

## ADR-004 · CV con `docxtpl` a partir de datos estructurados
- **Contexto:** reemplazar texto en `document.xml` falla porque Word parte el texto en varios `<w:r>`.
- **Decisión:** plantilla `.docx` con marcadores Jinja; el agente produce `CvContent` y el código renderiza.
  PDF con LibreOffice headless; páginas con `pypdf`.
- **Consecuencias:** hay que preparar la plantilla una vez. A cambio, el render es determinista y
  el contenido verificable.

## ADR-005 · Eventos como fuente de verdad
- **Decisión:** cada cambio de estado es un evento; la etapa es una proyección.
- **Consecuencias:** histórico completo, analítica del embudo con SQL y nada se pierde al
  descartar o cerrar.

## ADR-006 · Embeddings locales
- **Contexto:** Anthropic no ofrece API de embeddings y no queremos otro proveedor de pago.
- **Decisión:** sentence-transformers con un modelo multilingüe pequeño en CPU (candidatos:
  `paraphrase-multilingual-MiniLM-L12-v2`, `intfloat/multilingual-e5-small`), elegido con el set de evaluación.
- **Consecuencias:** descarga inicial del modelo; sin coste ni red después.

## ADR-007 · Ejecución nativa en Windows, sin Docker de momento
- **Decisión:** `uv` + `pnpm` en nativo. Playwright con navegador visible y LibreOffice del sistema.
- **Consecuencias:** configuración por variables de entorno para rutas de herramientas.

## ADR-008 · Aislamiento del texto crudo (sustituido parcialmente por ADR-012)
- **Decisión original:** el texto crudo de las ofertas solo lo ve el rol `extractor`, con
  herramientas mínimas; el resto trabaja con `JobExtraction`.
- **Estado:** se mantiene donde el agente lo permite, pero ya no es la única defensa (ADR-012).

## ADR-009 · Sin automatización en LinkedIn ni captchas
- **Decisión:** LinkedIn y cualquier web con anti-bot se tratan en modo "preparar y abrir".
- **Consecuencias:** algo menos de automatización a cambio de no arriesgar cuentas.

## ADR-010 · Interfaz para agentes neutral: MCP + CLI con paridad
- **Contexto:** el proyecto debe poder usarse con distintos agentes (Claude Code, Codex, Gemini
  CLI, Cursor, Copilot…), no solo con uno de pago concreto.
- **Decisión:** toda la interacción del agente con la app pasa por una interfaz con dos canales
  equivalentes: servidor MCP y CLI `jh … --json`. Un test garantiza la paridad.
- **Consecuencias:** cualquier agente que hable MCP o ejecute comandos sirve. El listón queda algo
  por encima del proyecto original (que solo pedía leer y escribir ficheros), a cambio de estado
  fiable y validación.

## ADR-011 · `.agents/` como fuente única y configuración nativa generada
- **Contexto:** cada agente espera instrucciones, skills, subagentes y servidores MCP en rutas y
  formatos distintos. Mantener copias a mano diverge enseguida.
- **Decisión:** `AGENTS.md` para instrucciones (`CLAUDE.md` y `GEMINI.md` solo lo importan);
  `.agents/skills/` con skills en el estándar Agent Skills y frontmatter mínimo (`name`,
  `description`); `.agents/roles/` con subagentes en un formato propio y neutral;
  `.agents/manifest.yaml` con lo específico de cada agente. `scripts/sync_agents.py` genera
  `.claude/`, `.codex/` y `.mcp.json`, y `--check` falla en CI si no están al día. Se copian
  ficheros en vez de usar enlaces simbólicos, porque en Windows requieren permisos especiales.
- **Consecuencias:** añadir un agente nuevo es añadir un bloque al manifiesto y, si hace falta, un
  emisor al script. Los ficheros generados se commitean para que el repo funcione tras clonarlo.

## ADR-012 · Seguridad que no depende del agente
- **Contexto:** no todos los agentes permiten restringir las herramientas de un subagente. En Codex,
  por ejemplo, los subagentes heredan la política de sandbox de la sesión padre.
- **Decisión:** las defensas críticas viven en el código: detección de texto oculto y frases de
  inyección al guardar, envoltorio con `risk_flags`, validación estricta de todo lo que devuelve el
  agente, comprobación determinista del CV e interfaz sin capacidad de enviar nada. El
  aislamiento por rol es una capa adicional donde exista.
- **Consecuencias:** las garantías mínimas son iguales para todos los agentes; `AGENTS_COMPAT.md`
  documenta las capas extra de cada uno.
