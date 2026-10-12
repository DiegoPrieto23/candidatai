# Guía de uso

[English](GUIDE.md) · **Español**

Cómo instalar CandidatAI, probarlo con la demo y usarlo cada día con tus datos y tu agente de IA.
Para saber qué es y por qué funciona así, empieza por el [README](../README.es.md).

## Índice

1. [Requisitos](#1-requisitos)
2. [Instalación](#2-instalación)
3. [Probar la demo](#3-probar-la-demo)
4. [Tus datos y tu perfil](#4-tus-datos-y-tu-perfil)
5. [Conectar tu agente](#5-conectar-tu-agente)
6. [Arrancar la app cada día](#6-arrancar-la-app-cada-día)
7. [Configurar las fuentes de ofertas](#7-configurar-las-fuentes-de-ofertas)
8. [De la oferta al envío](#8-de-la-oferta-al-envío)
9. [Seguimiento, respuestas y embudo](#9-seguimiento-respuestas-y-embudo)
10. [Entrevistas y ofertas recibidas](#10-entrevistas-y-ofertas-recibidas)
11. [El agente desde la UI](#11-el-agente-desde-la-ui)
12. [Configuración](#12-configuración)
13. [Actualizar](#13-actualizar)
14. [Problemas frecuentes](#14-problemas-frecuentes)
15. [Desarrollo](#15-desarrollo)

## 1. Requisitos

CandidatAI se desarrolla y se prueba en **Windows 11**. En macOS y Linux debería funcionar (todo
usa `pathlib` y herramientas multiplataforma), pero aún no se ha probado.

| Qué | Para qué | Cómo |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python 3.12 y las dependencias del backend (no hace falta instalar Python aparte) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Node LTS + pnpm | La UI | Node desde nodejs.org; `npm install -g pnpm` (desde Node 25 ya no viene `corepack`) |
| LibreOffice **o** el Chromium de Playwright | Los PDF de los CVs y las cartas | LibreOffice desde libreoffice.org (si no está en `C:\Program Files\LibreOffice` ni en el `PATH`, define `SOFFICE_PATH` en `.env`); Chromium con `uv run playwright install chromium` |
| Un agente de IA | Extraer ofertas, valorar el encaje, redactar el CV | Claude Code (referencia), Codex u otro que hable MCP o ejecute comandos |
| Git | Clonar y actualizar | git-scm.com |

Abre una terminal nueva después de instalar para que el `PATH` se actualice.

## 2. Instalación

```powershell
git clone https://github.com/DiegoPrieto23/candidatai.git candidatai
cd candidatai\backend
uv sync                                # dependencias del backend (crea .venv)
uv run playwright install chromium     # plantillas html y PDF sin LibreOffice
uv run cai doctor                       # comprueba el entorno y dice qué falta
uv run cai db upgrade                   # crea la base de datos en data/
cd ..\frontend
pnpm install
```

Opcional: `uv sync --extra matching` instala la similitud semántica local (trae torch, ~1 GB). Sin
ella el score funciona igual, sin ese componente.

## 3. Probar la demo

La demo es una candidata inventada con 60 ofertas, 8 semanas de historial y 2 CVs. Vive en
`data-demo/` y nunca toca tus datos.

```powershell
cd backend
uv run cai demo seed                         # --force para recrearla
$env:CAI_DATA_DIR = "data-demo"; uv run cai serve
# en otra terminal
cd frontend; pnpm dev                       # http://127.0.0.1:5173
```

La UI muestra un banner «Modo demo». Para probar los skills sobre la demo, arranca tu agente con
`CAI_DATA_DIR=data-demo` para que su servidor MCP use esa carpeta.

## 4. Tus datos y tu perfil

Todo lo tuyo vive en `data/`, que está fuera de git: base de datos, perfil, CVs, plantillas, foto,
documentos y correos. Las claves van en `.env`, también fuera de git.

| Qué | Dónde | Cómo |
|---|---|---|
| **Perfil** (la fuente de verdad de todo lo que se escribe sobre ti) | `data/profile.yaml` | Skill `update-profile`: lee tu CV, te pregunta lo que falte y lo valida. Cada cambio crea una versión |
| **Tu CV como diseño** | `data/templates/<id>/` | Sube tu CV en «Plantillas → Mi CV» y usa el skill `import-cv-template`. Vale Word, PDF, imagen o HTML (Canva, Google Docs…) |
| **Foto** | `data/photo.jpg` (o png) | Cada plantilla la recorta a su forma; se incluye o no según el país de la oferta |
| **Contexto** (estilo, narrativa, criterios) | `data/contexto/*.md` | Orienta al agente, pero nunca respalda un hecho del CV |
| **Documentos fuente** (CVs antiguos, títulos, referencias) | `data/documentos/` | `update-profile` los puede leer, confirmando antes de escribir |

Tu mínimo salarial va en `private.salary_floor_eur` del perfil: la app lo usa para comparar
ofertas, pero el agente nunca lo recibe.

## 5. Conectar tu agente

Abre tu agente **en la raíz del repositorio**: ahí encuentra las instrucciones (`AGENTS.md`), los
skills y el servidor MCP ya configurados.

- **Claude Code:** `claude` en la raíz. Comprueba con `/mcp` que el servidor `candidatai` está
  conectado. Los skills se invocan como `/generate-cv 42`.
- **Codex:** usa `.codex/` (generado). Los skills se invocan como `$generate-cv 42`.
- **Otros agentes:** si leen `AGENTS.md` y hablan MCP, registra el servidor `candidatai` con el
  comando de `.mcp.json`. Si no hablan MCP, cada herramienta tiene su comando
  `uv run --directory backend cai … --json` (tabla en
  [`AGENT_INTERFACE.md`](AGENT_INTERFACE.md)).

Más detalle, y cómo añadir un agente: [`AGENTS_COMPAT.md`](AGENTS_COMPAT.md).

## 6. Arrancar la app cada día

Tres procesos, mejor cada uno en su ventana de terminal y **fuera de tu agente** (si el agente se
queda sin memoria, puede cerrar lo que haya lanzado él):

```powershell
cd backend; uv run cai serve       # API en http://127.0.0.1:8000 (solo en local)
cd backend; uv run cai worker      # ingesta diaria, scores, correo, candidatura asistida, segundo plano
cd frontend; pnpm dev             # UI en http://127.0.0.1:5173
```

Un día normal:

1. Abre **Inicio**: te dice qué tienes (ofertas por revisar, CVs listos, seguimientos vencidos).
2. Pide a tu agente `process-jobs` y `assess-fit`, o pulsa sus botones en la UI.
3. Triaga en **Por revisar**.
4. `generate-cv` para las aprobadas y, cuando quieras, envía desde la ficha.
5. `daily-summary` resume todo eso en una respuesta.

## 7. Configurar las fuentes de ofertas

| Fuente | Cómo se configura |
|---|---|
| **Alta manual** | «Nueva oferta» en la UI (URL o texto pegado) |
| **Empresas objetivo** (Greenhouse, Lever, Ashby) | Pantalla «Empresas» o `cai sources add --kind greenhouse --name "Acme" --slug acme`. `cai sources discover --file empresas.txt` busca el tablero de cada empresa de una lista |
| **InfoJobs y Adzuna** | Sus claves en `.env` (`CAI_INFOJOBS_CLIENT_ID`/`_SECRET`, `CAI_ADZUNA_APP_ID`/`_KEY`) y una búsqueda con `cai sources add` |
| **Alertas por correo** | Crea alertas en LinkedIn, InfoJobs, Indeed… y que lleguen a una etiqueta de tu correo. Configura IMAP de solo lectura en `.env`: paso a paso en [`CONFIGURAR_CORREO.md`](CONFIGURAR_CORREO.md). Sin IMAP, deja los `.eml` en `data/inbox/`. Lo que llega aparece en «Alertas» |
| **Botón «Enviar a CandidatAI»** | Carga `extension/` como extensión sin empaquetar en Chrome o Edge y pega el token de `cai capture token` en sus opciones. Instrucciones: [`extension/README.md`](../extension/README.md) |
| **Tu agente con tu navegador** | `search-jobs configurar` elige portales y búsquedas (pantalla «Plataformas»); `search-jobs` los recorre. LinkedIn queda desactivado hasta que lo actives tú |
| **Búsqueda pública de LinkedIn** | Interruptor «Búsqueda pública sin sesión» en la tarjeta de LinkedIn de «Plataformas». Apagado por defecto: va contra las condiciones de LinkedIn y puede bloquear tu IP un tiempo |

El worker ejecuta las fuentes automáticas cada día a la hora de `connectors.daily_at`
(`config/policies.yaml`) y al arrancar si se perdió alguna. Detalle de cada vía:
[`FUENTES_OFERTAS.md`](FUENTES_OFERTAS.md).

## 8. De la oferta al envío

1. **Extraer:** `process-jobs` convierte el texto de cada oferta en datos estructurados. El
   texto de las ofertas es contenido no confiable: si trae texto oculto o frases dirigidas a una
   IA, la ficha lo avisa.
2. **Valorar:** la app calcula el score y aplica tus filtros duros; `assess-fit` añade una
   valoración razonada.
3. **Triar:** en «Por revisar», `J`/`K` para moverte, `A` para aprobar, `D` para descartar (con
   motivo) y `O` para abrir la ficha. Se puede deshacer.
4. **CV:** `generate-cv 42` redacta el contenido, el código lo valida y renderiza y el rol
   `verifier` lo revisa. En la ficha cambias plantilla, foto, color y secciones sin gastar
   agente, comparas renders y marcas cuál envías.
5. **Carta:** `generate-cover-letter 42`, con tus indicaciones generales (perfil) y las de la oferta
   (ficha). Sale a juego con el CV.
6. **Candidatura:** `prepare-application 42` prepara las respuestas de screening. En la ficha,
   «Preparar candidatura» abre un navegador propio (perfil en `data/browser-profile/`), rellena el
   formulario y se para. Revisas, y solo si escribes el nombre de la empresa, envía. Ante un
   captcha o un login, se para y te pasa la pestaña. Si la envías tú por otro lado, márcala como
   enviada a mano.

## 9. Seguimiento, respuestas y embudo

- **Procesos:** kanban por etapas. Una tarjeta solo cambia de columna registrando lo que pasó
  (respuesta, entrevista, prueba, oferta, rechazo). Entrevistas y pruebas crean un hito con fecha,
  exportable a tu calendario (`.ics`).
- **Seguimientos:** te avisa de las candidaturas sin respuesta; `draft-follow-up` deja los
  borradores (máximo 2 por candidatura) y el de agradecimiento tras una entrevista. Los envías tú.
- **Respuestas:** con IMAP configurado, la app lee los correos de las empresas de tus procesos;
  `review-replies` propone qué ha pasado y tú lo aceptas en «Respuestas».
- **Embudo:** conversión por paso, fuente, puesto, semana, plantilla, carta y referencia, y
  «¿Acierta el score?». `review-search` hace la retrospectiva semanal.
- **Red:** importa tus contactos de LinkedIn (exportación CSV) con `cai contacts import-linkedin`
  y verás «Conoces a N» en las ofertas de sus empresas; `draft-message` prepara el mensaje.

## 10. Entrevistas y ofertas recibidas

- `prepare-interview 42`: dosier y plan por días hasta la fecha, guardados en la ficha.
- `mock-interview 42`: una pregunta cada vez, con feedback y una versión mejor basada en tu
  perfil.
- `debrief-interview 42`: cuentas cómo fue; guarda notas y próximos pasos y propone historias STAR
  nuevas para tu perfil (con tu OK).
- **Ofertas recibidas:** las anotas en la ficha y las comparas en «Procesos → Ofertas recibidas»
  con tu mínimo y con el rango publicado. `prepare-negotiation 42` prepara argumentos y guion sin
  proponer cifras.

## 11. El agente desde la UI

Muchas pantallas tienen botones que abren tu agente con la orden ya escrita:

- **En terminal:** abre una ventana con tu agente; tú ves y apruebas lo que hace.
- **En segundo plano** (Claude Code): para los skills que no preguntan (`process-jobs`,
  `assess-fit`, `generate-cv`). Corre sin ventana, solo con las herramientas de la app que
  necesita, y ves el progreso en la página «Agente». Necesita `cai worker` en marcha.
- **Dejar para mi próxima sesión:** guarda el encargo; `handle-requests` lo hace cuando abras tu
  agente.

## 12. Configuración

- **`.env`** (en la raíz, fuera de git): `CAI_DATA_DIR`, `SOFFICE_PATH`, claves de InfoJobs y
  Adzuna, IMAP (`CAI_IMAP_HOST`, `CAI_IMAP_PORT`, `CAI_IMAP_USER`, `CAI_IMAP_PASSWORD`,
  `CAI_IMAP_FOLDER`, `CAI_IMAP_REPLIES_FOLDER`), `CAI_BROWSER_CHANNEL` (`chrome` o `msedge` para la
  candidatura asistida), `CAI_EMBEDDINGS=off`. Nada es obligatorio.
- **`config/policies.yaml`:** umbral de triaje, pesos del score, hora de la ingesta diaria,
  frecuencia del correo, límites de la búsqueda con navegador y de la búsqueda pública de
  LinkedIn, frases de oferta cerrada… Tras cambiar el score, `cai match rescore` recalcula y
  `cai eval matching` mide el efecto.
- **Tu perfil:** preferencias (puestos, nivel, modalidad, zonas, idiomas), plantilla por defecto,
  reglas de plantilla y política de foto por país.

## 13. Actualizar

Con tu agente **cerrado** (su servidor MCP bloquea el entorno de Python):

```powershell
copy data\candidatai.db data\candidatai.db.bak     # copia de seguridad
git pull
cd backend; uv sync; uv run cai db upgrade
cd ..\frontend; pnpm install
```

Reinicia `cai serve`, `cai worker` y tu agente.

## 14. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| Algo no funciona y no sabes qué | `uv run cai doctor` comprueba base de datos, PDF, Chromium, plantillas, foto, correo y captura |
| «Ejecuta `cai db upgrade`» | Hay migraciones nuevas: `uv run cai db upgrade` |
| `uv sync` falla con «fichero en uso» | Cierra tu agente (su servidor MCP usa `cai-mcp.exe`) y repite |
| Los PDF no salen | Instala LibreOffice o `uv run playwright install chromium`; `cai doctor` lo comprueba |
| La UI dice que no conecta con la API | Arranca `cai serve`; la UI espera la API en `127.0.0.1:8000` |
| El puerto 5173 está ocupado | Otro `pnpm dev` sigue abierto: ciérralo (la API solo acepta la UI en ese puerto) |
| Nada entra solo por la mañana | `cai worker` tiene que estar en marcha |
| Las tildes salen mal en `cai --help` | Problema conocido de la consola de Windows con cp1252; la salida `--json` está bien |

## 15. Desarrollo

```powershell
cd backend
uv run pytest                                   # tests
uv run ruff check --fix; uv run ruff format     # estilo
uv run cai eval matching                         # calidad del matching
cd ..\frontend
pnpm typecheck; pnpm test; pnpm build
pnpm gen:api                                    # regenera el cliente tras cambiar la API
cd ..
uv run scripts/sync_agents.py                   # regenera la configuración de agentes desde .agents/
```

Reglas del proyecto, arquitectura y forma de trabajar por fases: [`AGENTS.md`](../AGENTS.md),
[`ARCHITECTURE.md`](ARCHITECTURE.md) y [`DESARROLLO_POR_FASES.md`](DESARROLLO_POR_FASES.md).
Contribuir: [`CONTRIBUTING.md`](../CONTRIBUTING.md).
