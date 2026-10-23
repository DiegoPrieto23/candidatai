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

CandidatAI se desarrolla y se prueba en **Windows 11**. En macOS y Linux tiene instalador y los
botones que abren tu agente funcionan (fase 26), pero se están probando todavía: Linux en WSL2 y
macOS en la CI.

**Para usarla** solo hace falta Windows, macOS o Linux y, si quieres CVs en Word además de en PDF,
LibreOffice. El
instalador se encarga del resto (uv, Python y el Chromium que genera los PDF). Para que el agente
haga su parte necesitas también **un agente de IA** (Claude Code, Codex…; ver la sección 5).

**Para desarrollar** (clonar el repositorio y cambiar el código):

| Qué | Para qué | Cómo |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python 3.12 y las dependencias del backend (no hace falta instalar Python aparte) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Node LTS + pnpm | Compilar la UI y desarrollarla | Node desde nodejs.org; `npm install -g pnpm` (desde Node 25 ya no viene `corepack`) |
| LibreOffice **o** el Chromium de Playwright | Los PDF de los CVs y las cartas | LibreOffice desde libreoffice.org (si no está en `C:\Program Files\LibreOffice` ni en el `PATH`, define `SOFFICE_PATH` en `.env`); Chromium con `uv run playwright install chromium` |
| Git | Clonar y actualizar | git-scm.com |

Abre una terminal nueva después de instalar para que el `PATH` se actualice.

## 2. Instalación

### Para usarla: el instalador

En PowerShell (no hace falta ser administrador):

```powershell
iwr -useb https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.ps1 -OutFile $env:TEMP\cai-install.ps1
powershell -ExecutionPolicy Bypass -File $env:TEMP\cai-install.ps1
```

El instalador:

1. instala [uv](https://docs.astral.sh/uv/) si no está (con él viene Python 3.12);
2. descarga la última versión de CandidatAI, con la UI ya compilada (no hace falta Node);
3. la deja en `%LOCALAPPDATA%\CandidatAI\app`, y tus datos en `%LOCALAPPDATA%\CandidatAI\data`;
4. prepara el entorno, el Chromium de los PDF y la base de datos;
5. crea un acceso directo **«CandidatAI»** en el escritorio y en el menú Inicio.

Al abrir el acceso directo se arranca todo y se abre el navegador en `http://127.0.0.1:8000`. Deja
abierta la ventana que aparece mientras la uses; para cerrar CandidatAI, cierra esa ventana.

- **Antes de instalar**, `-WhatIf` (al final de la segunda línea) explica lo que haría sin cambiar
  nada. En los ejemplos de abajo, si PowerShell no deja ejecutar scripts, usa
  `powershell -ExecutionPolicy Bypass -File .\install.ps1 …` en vez de `.\install.ps1 …`.
- **Actualizar:** vuelve a ejecutar el instalador (con CandidatAI cerrada). Tus datos no se
  tocan, y el `.env` de la app (`…\CandidatAI\app\.env`) se conserva.
- **Desinstalar:** `.\install.ps1 -Uninstall` quita la app y los accesos directos, no tus datos
  (con `-RemoveData`, también tus datos, previa confirmación).
- Mientras el repositorio sea privado o no haya ninguna versión publicada, el comando de una línea
  no tiene qué descargar: instala desde tu copia del repositorio (abajo) con
  `.\install.ps1 -Source <carpeta del repositorio>`, después de compilar la UI (`pnpm build`).

### En macOS y Linux: `install.sh`

En una terminal (no hace falta `sudo`):

```bash
curl -fsSL https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.sh | bash
```

Hace lo mismo que el de Windows:

1. instala uv si no está;
2. descarga la última versión, con la UI ya compilada;
3. la deja en `~/Library/Application Support/CandidatAI/app` (macOS) o en
   `~/.local/share/candidatai/app` (Linux, o `$XDG_DATA_HOME/candidatai/app`), y tus datos al
   lado, en `…/data` (`uv run cai paths` te dice dónde);
4. prepara el entorno, el Chromium de los PDF y la base de datos. En Linux, si a Chromium le faltan
   librerías del sistema, te dice el comando de tu distribución (lleva `sudo`: lo ejecutas tú);
5. crea el acceso directo **«CandidatAI»**: en macOS, `~/Applications/CandidatAI.app`, que abre
   Terminal; en Linux, en el menú de aplicaciones, que abre tu terminal. Deja esa ventana abierta
   mientras la uses; para cerrar CandidatAI, ciérrala.

- **Antes de instalar:** `curl -fsSL …/install.sh | bash -s -- --dry-run` explica lo que haría.
- **Actualizar:** vuelve a ejecutarlo con CandidatAI cerrada; tus datos y tu `.env` se conservan.
- **Desinstalar:** `bash install.sh --uninstall` quita la app y el acceso directo, no tus datos (con
  `--remove-data`, también tus datos, si lo confirmas escribiendo «borrar»). Solo toca carpetas que
  creó él (llevan un fichero `.candidatai`).
- **Desde tu copia del repositorio**, con la UI compilada: `bash install.sh --source <carpeta>`.
- En macOS, la primera vez puede pedirte permiso para que la app controle Terminal: acéptalo.

### Con Docker (opcional)

Si prefieres no instalar Python ni Chromium en tu equipo, CandidatAI arranca en un contenedor. Es
una alternativa con límites: **lo recomendado sigue siendo el instalador**. Tu agente de IA no va
dentro del contenedor, así que lo que necesita abrirle una ventana no funciona igual.

Necesitas Docker (en Windows, Docker Desktop) y una copia del repositorio. Desde su carpeta:

```bash
docker compose up -d --build        # la primera vez tarda unos minutos (construye la imagen)
```

La app queda en `http://127.0.0.1:8000`, solo en tu equipo. Tus datos van en el volumen
`candidatai-data`, que sobrevive a parar, actualizar o borrar el contenedor. Si hay un `.env` en
la carpeta, el contenedor lo lee (claves de portales, IMAP…): con IMAP configurado, su worker lee
tus alertas por correo igual que el de la instalación nativa, pero las guarda en el volumen.

- **Parar y arrancar:** `docker compose stop` y `docker compose start`.
- **Actualizar:** `git pull` y `docker compose up -d --build`.
- **Diagnóstico:** `docker compose exec candidatai cai doctor`. La sección «Docker» dice dónde
  están tus datos y qué no funciona dentro.
- **La demo:** `docker compose exec candidatai cai demo seed` la crea en otro volumen. Para abrirla,
  `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d`. Para volver a tus datos,
  `docker compose up -d`.

**Qué funciona y qué no dentro de Docker:**

| | Con Docker |
|---|---|
| UI, ofertas, triaje, seguimiento y embudo | Sí |
| Fuentes de ofertas y alertas por correo (el worker) | Sí |
| CVs y cartas en PDF | Sí, con las plantillas html (`moderna-2col`…). Las docx salen solo en Word: no hay LibreOffice |
| Tu agente por MCP o `cai … --json` | Sí, desde fuera del contenedor (abajo) |
| Botones «en tu agente» | Copian la orden para que la pegues en tu agente |
| «En segundo plano» | No: el agente no está en el contenedor |
| Candidatura asistida | La oferta se abre en tu navegador, la envías tú y pulsas «Marcar como enviada» |
| Similitud semántica del score | No (la imagen no trae torch); el score funciona igual |

**Tu agente, desde fuera.** El agente se ejecuta en tu equipo, en la carpeta del repositorio (lee
de ahí los skills y `AGENTS.md`), y habla con la app del contenedor:

- **Por MCP**, con la orden `docker exec -i candidatai cai-mcp`. Funciona desde cualquier carpeta.
  - **Claude Code:** `claude mcp add --scope local candidatai -- docker exec -i candidatai cai-mcp`.
    La configuración local manda sobre la del proyecto (`.mcp.json`, que es la de la instalación
    nativa); `claude mcp remove --scope local candidatai` la quita.
  - **Codex**, en `.codex/config.toml`:
    ```toml
    [mcp_servers.candidatai]
    command = "docker"
    args = ["exec", "-i", "candidatai", "cai-mcp"]
    ```
  - **OpenCode**, en `opencode.json`:
    `"candidatai": {"type": "local", "command": ["docker", "exec", "-i", "candidatai", "cai-mcp"], "enabled": true}`.
  - En Codex y OpenCode cambias un fichero generado: `uv run scripts/sync_agents.py` lo devolvería
    a la orden nativa.
- **Sin MCP**, los comandos `cai … --json` van con `docker exec -i candidatai cai …`. Por ejemplo:
  `docker exec -i candidatai cai status --json`. Las entradas largas se pasan con `--file`, en un
  fichero dentro del contenedor: `docker cp entrada.json candidatai:/data/tmp/`.

**Copia de seguridad.** Tus datos están en el volumen, no en una carpeta de tu equipo. Para copiarlo
(con la app parada, para que la base de datos esté quieta):

```bash
docker compose stop
docker run --rm -v candidatai-data:/data -v "$PWD":/backup alpine tar czf /backup/candidatai-data.tgz -C /data .
docker compose start
```

Sirve igual en PowerShell. Para restaurarla en un volumen vacío:
`docker run --rm -v candidatai-data:/data -v "$PWD":/backup alpine tar xzf /backup/candidatai-data.tgz -C /data`.
Si prefieres tus datos en una carpeta de tu equipo, cambia en `docker-compose.yml` el volumen por
esa carpeta (la línea comentada); en Linux, la carpeta tiene que poder escribirla el uid 1000.

### Para desarrollar: clonar el repositorio

```powershell
git clone https://github.com/DiegoPrieto23/candidatai.git candidatai
cd candidatai\backend
uv sync                                # dependencias del backend (crea .venv)
uv run playwright install chromium     # plantillas html y PDF sin LibreOffice
uv run cai doctor                      # comprueba el entorno y dice qué falta
uv run cai agents doctor               # qué agentes de IA tienes, cuál se usa y qué falta
cd ..\frontend
pnpm install
pnpm build                             # la UI compilada que sirve `cai start`
```

Opcional: `uv sync --extra matching` instala la similitud semántica local (trae torch, ~1 GB). Sin
ella el score funciona igual, sin ese componente.

## 3. Probar la demo

La demo es una candidata inventada con 60 ofertas, 8 semanas de historial y 2 CVs. Vive en su
propia carpeta y nunca toca tus datos. Hay dos: en español (una candidata en Galicia) y en inglés
(una candidata en Dublín, con `--lang en`).

Trae también lo que habrían dejado ella y su agente, para que ninguna pantalla salga vacía:
valoración del encaje, carta y respuestas de screening de una oferta, un mensaje de LinkedIn y un
seguimiento, dos dosieres de empresa (uno con bandera roja), el plan de una entrevista y el repaso
de dos, los datos de la oferta recibida, tres correos de empresas en «Respuestas» (dos con
propuesta y uno sin clasificar, con texto oculto para una IA), dos huecos en «Skills», un encargo
pendiente, el contexto, una muestra de estilo y una tabla de salarios.

```powershell
cd backend
uv run cai demo seed                         # --force para recrearla
$env:CAI_DATA_DIR = "data-demo"; uv run cai start
# en inglés: uv run cai demo seed --lang en --dir data-demo-en
```

Se abre el navegador en `http://127.0.0.1:8000` con un banner «Modo demo». Los botones «en tu
agente» abren tu agente ya apuntando a la demo. Si lo abres tú, arráncalo con
`CAI_DATA_DIR=data-demo` para que su servidor MCP use esa carpeta y no tus datos.

Si clonaste el repositorio, compila antes la UI (`cd frontend; pnpm install; pnpm build`) y repítelo
cada vez que cambies de rama o actualices: `cai start` sirve la UI compilada, y con una vieja no
ves lo que se haya añadido después.

## 4. Tus datos y tu perfil

Todo lo tuyo vive en `data/`, que está fuera de git: base de datos, perfil, CVs, plantillas, foto,
documentos y correos. Las claves van en `.env`, también fuera de git.

| Qué | Dónde | Cómo |
|---|---|---|
| **Perfil** (la fuente de verdad de todo lo que se escribe sobre ti) | `data/profile.yaml` | Para empezar, el skill `update-profile`: lee tu CV, te pregunta lo que falte y lo valida. Después, **rellénalo y retócalo en «Mi perfil»**: experiencia y logros, proyectos, formación, skills e idiomas, historias STAR, qué buscas y tus preferencias de CV y carta, por bloques. Cada bloque se guarda solo, conserva el formato y los comentarios de tu fichero, avisa si lo cambiaste por fuera y se puede deshacer. Cada cambio crea una versión. Si prefieres, sigue valiendo editar el YAML |
| **Tu CV como diseño** | `data/templates/<id>/` | Sube tu CV en «Plantillas → Mi CV» y pulsa «Convertir en plantilla» (usa el skill `import-cv-template`). Vale Word, PDF, imagen o HTML (Canva, Google Docs…) |
| **Foto** | `data/photo.jpg` (o png) | Cada plantilla la recorta a su forma; se incluye o no según el país de la oferta |
| **Contexto** (estilo, narrativa, criterios) | `data/contexto/*.md` | Se edita en «Mi perfil → Contexto y estilo» (con vista previa) o en tu editor. Orienta al agente, pero nunca respalda un hecho del CV |
| **Muestras de estilo** (cartas, correos o posts tuyos) | `data/documentos/estilo/` | Súbelas en «Mi perfil → Contexto y estilo» (.txt, .md, .docx, .pdf). Tu agente toma de ellas el tono, nunca los hechos, y las lee como dato: si traen texto de otros con órdenes, no las sigue |
| **Documentos fuente** (CVs antiguos, títulos, referencias) | `data/documentos/` | `update-profile` los puede leer, confirmando antes de escribir |
| **Lo que has hecho en público** (repositorios, portfolio, Kaggle, Scholar, certificaciones verificables) | `data/profile.yaml` | Skill `expand`, o «Ampliar perfil desde mis enlaces» en «Mi perfil». Úsalo **justo después de crear el perfil**: propone proyectos, skills (sin nivel: lo pones tú), logros con los números que da la fuente y certificaciones, cada uno con su enlace en `source`, y solo escribe lo que aceptes. Solo web pública: ni LinkedIn ni nada con login. Necesita un agente con búsqueda web |

Tu mínimo salarial va en `private.salary_floor_eur` del perfil: la app lo usa para comparar
ofertas, pero el agente nunca lo recibe.

**Dónde están tus datos y cómo copiarlos.** `uv run cai paths` (o `cai paths` en la carpeta de la
app) dice qué carpeta usas. Con el instalador:

| Sistema | Carpeta de datos |
|---|---|
| Windows | `%LOCALAPPDATA%\CandidatAI\data` |
| macOS | `~/Library/Application Support/CandidatAI/data` |
| Linux | `~/.local/share/candidatai/data` (o `$XDG_DATA_HOME/candidatai/data`) |
| Docker | el volumen `candidatai-data` (ver «Con Docker») |
| Repositorio clonado | `data/` en la raíz |

Para hacer una copia de seguridad, **cierra CandidatAI** (la base de datos tiene que estar quieta) y
copia esa carpeta entera donde quieras: un zip, otro disco o tu nube. Para restaurarla, con la app
cerrada, pon la copia en su sitio. Guarda también el `.env` de la app si tiene claves tuyas.

En «Mi perfil», cada logro y cada historia tienen **«Mejorar con mi agente»**: tu agente propone
una versión más clara, te pregunta los números que falten (nunca los inventa) y solo escribe con tu
OK. En «Historias STAR», **«Proponer historias desde mi experiencia»** te sugiere historias a partir
de los logros que aún no tienen. Tu correo y tu teléfono se editan ahí, pero tu agente sigue sin
verlos. Tu mínimo salarial (`private`) solo se edita en el YAML.

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

### Sin pagar por tokens: modelos gratuitos y locales

Además de tu suscripción (Claude, ChatGPT), puedes usar agentes open-source con un **modelo local**
(Ollama o LM Studio: gratis y nada sale de tu equipo) o con un **modelo gratuito en la nube**
(OpenRouter `:free`, el plan gratuito de Antigravity: gratis, con límites diarios, y las ofertas y tu
perfil van al proveedor). Con Ollama, pon `OLLAMA_CONTEXT_LENGTH=32768` o más: con los 4 096 que trae
por defecto, los agentes no funcionan. `cai agents doctor` y la tarjeta de cada agente dicen qué
modelos tienes y si el contexto llega. Los modelos de unos 8B o menos suelen fallar con el CV.
Guía completa, con los modelos recomendados según tu memoria y qué sale de tu equipo en cada vía:
[`MODELOS_GRATIS.md`](MODELOS_GRATIS.md).

## 6. Arrancar la app cada día

- **Con el instalador:** abre el acceso directo «CandidatAI». Para cerrarla, cierra su ventana.
- **Desde el repositorio:** `cd backend; uv run cai start`. Arranca la API (que sirve también la
  UI) y el worker en un solo comando, aplica las migraciones pendientes y abre el navegador.
  Ctrl+C para cerrar. Sus registros van a `data/logs/start-*.log`.
- **Para desarrollar la UI** con recarga en caliente: `uv run cai start --dev` arranca además Vite
  y abre `http://127.0.0.1:5173`. También se pueden arrancar por separado `cai serve`,
  `cai worker` y `pnpm dev`, cada uno en su ventana.

Arranca CandidatAI **fuera de tu agente** (una ventana propia o el acceso directo): si el agente se
queda sin memoria, puede cerrar lo que haya lanzado él.

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
| **Empresas objetivo** (Greenhouse, Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters, Recruitee) | Página «Fuentes → Empresas objetivo» o `cai sources add --kind greenhouse --name "Acme" --slug acme`. `cai sources discover --file empresas.txt` busca el tablero de cada empresa de una lista. Cómo encontrar el slug, en [`FUENTES_OFERTAS.md`](FUENTES_OFERTAS.md#cómo-encontrar-el-slug) |
| **InfoJobs y Adzuna** | Sus claves en `.env` (`CAI_INFOJOBS_CLIENT_ID`/`_SECRET`, `CAI_ADZUNA_APP_ID`/`_KEY`) y una búsqueda con `cai sources add` |
| **Manfred y freehire.me** | Sin claves: una búsqueda en la misma página o con `cai sources add --kind manfred --name Manfred --query "data engineer"` (en freehire, también `--country` y `--remote-only`) |
| **Alertas por correo** | Crea alertas en LinkedIn, InfoJobs, Indeed… y que lleguen a una etiqueta de tu correo. Configura IMAP de solo lectura en `.env`: paso a paso en [`CONFIGURAR_CORREO.md`](CONFIGURAR_CORREO.md). Sin IMAP, deja los `.eml` en `data/inbox/`. Lo que llega aparece en «Alertas» |
| **Botón «Enviar a CandidatAI»** | Carga `extension/` como extensión sin empaquetar en Chrome o Edge y pega el token de `cai capture token` en sus opciones. Instrucciones: [`extension/README.md`](../extension/README.md) |
| **Tu agente con tu navegador** | `search-jobs configurar` elige portales y búsquedas (página «Fuentes → Plataformas»); `search-jobs` los recorre. LinkedIn queda desactivado hasta que lo actives tú |
| **Búsqueda pública de LinkedIn** | Interruptor «Búsqueda pública sin sesión» en la tarjeta de LinkedIn de «Fuentes → Plataformas». Apagado por defecto: va contra las condiciones de LinkedIn y puede bloquear tu IP un tiempo |

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
- **Calendario:** todos tus hitos (entrevistas, pruebas, plazos y otros, también los pasados) por
  mes, semana, día o agenda. Pulsa uno para ver sus datos e ir a la oferta.
- **Seguimientos:** te avisa de las candidaturas sin respuesta; `draft-follow-up` deja los
  borradores (máximo 2 por candidatura) y el de agradecimiento tras una entrevista. Los envías tú.
- **Respuestas:** con IMAP configurado, la app lee los correos de las empresas de tus procesos;
  `review-replies` propone qué ha pasado y tú lo aceptas en «Respuestas».
- **Embudo:** conversión por paso, fuente, puesto, semana, plantilla, carta y referencia, y
  «¿Acierta el score?». `review-search` hace la retrospectiva semanal. Al final, «Tu búsqueda en
  números» (o `cai stats story`): tus cifras desde el principio, sin empresas, y una línea para
  contarlo en un README si quieres.
- **Red:** importa tus contactos de LinkedIn (exportación CSV) con `cai contacts import-linkedin`
  y verás «Conoces a N» en las ofertas de sus empresas; `draft-message` prepara el mensaje.

## 10. Entrevistas y ofertas recibidas

- `prepare-interview 42`: dosier y plan por días hasta la fecha, guardados en la ficha.
- `mock-interview 42`: una pregunta cada vez, con feedback y una versión mejor basada en tu
  perfil.
- `debrief-interview 42`: cuentas cómo fue; guarda notas y próximos pasos y propone historias STAR
  nuevas para tu perfil (con tu OK).
- **Ofertas recibidas:** las anotas en la ficha y las comparas en «Procesos → Ofertas recibidas»
  (aparece con dos o más) con tu mínimo y con el rango publicado. `prepare-negotiation 42` prepara argumentos y guion sin
  proponer cifras.

## 11. El agente desde la UI

Muchas pantallas tienen botones que abren tu agente con la orden ya escrita:

- **En terminal:** abre una ventana con tu agente; tú ves y apruebas lo que hace.
- **En segundo plano** (Claude Code; OpenCode en `process-jobs` y `assess-fit`): para los skills
  que no preguntan (`process-jobs`, `assess-fit`, `generate-cv`). Corre sin ventana, solo con las
  herramientas de la app que necesita, y ves el progreso y el uso en la página «Agente». Si tu
  agente no puede, el desplegable propone uno que sí. Necesita `cai worker` en marcha.
  - **Coste:** la sección «Coste» de la página «Agente» suma tokens, tiempo y, si el agente lo da,
    dinero, por acción, agente y modelo (7 y 30 días), con lo que pesa cada skill; la ficha dice lo
    gastado en esa oferta y el embudo, por candidatura enviada y por entrevista. Lo que hagas en una
    terminal no cuenta: ahí el agente no devuelve su uso.
  - **Umbral antes de gastar:** `assess-fit` en segundo plano solo valora las ofertas con un score
    mínimo (por defecto, el de triaje menos 10; lo cambias en «Coste»). El triaje dice por qué se
    queda sin valorar una oferta por debajo.
  - **Varias a la vez:** por defecto, de una en una. Con `background_runs.max_parallel` (hasta 4)
    en `config/policies.yaml` van varias a la vez, nunca dos de la misma oferta; con
    `per_agent: {opencode: 1}` limitas un modelo local.
- **Dejar para mi próxima sesión:** guarda el encargo; `handle-requests` lo hace cuando abras tu
  agente.

**Qué agente se abre.** En la página «Agente», la sección «Agentes» enseña los agentes que tienes,
qué sabe hacer cada uno y cómo instalar los que faltan. Ahí eliges el agente por defecto, el modelo
de cada agente y, en la tabla «Por acción», otro agente o modelo para una acción concreta (p. ej.
OpenCode con un modelo local para procesar ofertas y Claude Code para el CV). El desplegable de cada
botón dice con qué agente iría («con Claude Code ▾») y te deja usar otro solo esa vez. Si un agente
no sirve para una acción (le falta el navegador para buscar ofertas, p. ej.), el botón lo dice y no
lo lanza. Sin nada elegido, se usa `CAI_AGENT` del `.env` o el primero instalado.
En macOS y Linux, los botones abren Terminal.app o la terminal de tu escritorio; para usar otra
(iTerm2, kitty…), pon `CAI_TERMINAL=iterm` (o su nombre o ruta) en el `.env`.

**Niveles de gasto.** En la misma página, «Económico», «Equilibrado» y «Máximo» guardan el agente y
el modelo de las acciones principales. «Económico» usa un modelo local para procesar, valorar y
clasificar respuestas, y tu agente más capaz para el CV. Rellénalos una vez y aplica uno con un clic.
«Deshacer el último» deja las preferencias como estaban.

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

### Idioma

La interfaz está en **español** y en **inglés**. El botón del globo, abajo en la barra lateral (o
en el menú, en el móvil), abre la lista de idiomas; el cambio es instantáneo y la app lo recuerda
en ese navegador. La primera vez sigue el idioma del navegador: español si es español; si no,
inglés. Las fechas y los números también siguen el idioma. Al cambiarlo se vuelve a pintar la
página: un diálogo o un formulario a medias se cierran, así que termínalo antes.

Lo que la interfaz no traduce: tus datos (ofertas, perfil, notas), lo que redacta tu agente (los
CVs, las cartas y las valoraciones siguen el idioma de cada oferta) y algunos mensajes que escribe
el servidor sin un código que traducir (ciertos avisos y resultados de ejecuciones), que siguen en
español.

## 13. Actualizar

**Con el instalador:** vuelve a ejecutarlo; tus datos (`%LOCALAPPDATA%\CandidatAI\data`) no se
tocan y las migraciones se aplican solas.

**Desde el repositorio**, con tu agente **cerrado** (su servidor MCP bloquea el entorno de Python):

```powershell
copy data\candidatai.db data\candidatai.db.bak     # copia de seguridad
git pull
cd backend; uv sync
cd ..\frontend; pnpm install; pnpm build
```

`cai start` aplica las migraciones al arrancar. Reinicia CandidatAI y tu agente.

## 14. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| Algo no funciona y no sabes qué | `uv run cai doctor` comprueba base de datos, PDF, Chromium, plantillas, foto, correo y captura |
| «Ejecuta `cai db upgrade`» | Hay migraciones nuevas: `uv run cai db upgrade` |
| `uv sync` falla con «fichero en uso» | Cierra tu agente (su servidor MCP usa `cai-mcp.exe`) y repite |
| Los PDF no salen | Instala LibreOffice o `uv run playwright install chromium`; `cai doctor` lo comprueba |
| La UI dice que no conecta con la API | Arranca CandidatAI (`cai start` o el acceso directo) y no cierres su ventana |
| «El puerto 8000 lo usa otro programa» | Cierra ese programa o usa `cai start --port 8001` |
| No está la UI compilada | En el repositorio, `cd frontend; pnpm install; pnpm build` (con el instalador ya viene) |
| Nada entra solo por la mañana | CandidatAI tiene que estar abierta (`cai start` arranca el worker) |
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
