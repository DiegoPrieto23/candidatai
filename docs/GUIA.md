# Guía de uso

[English](GUIDE.md) · **Español**

Cómo instalar CandidatAI, probarlo con la demo y usarlo cada día con los datos reales y el agente de
IA. Para saber qué es y por qué funciona así, conviene empezar por el [README](../README.es.md). La
primera vez, antes conviene leer [Primeros pasos](EMPEZAR.md): lo que hace falta, dicho claro, y los
primeros pasos.

## Índice

1. [Requisitos](#1-requisitos)
2. [Instalación](#2-instalación)
3. [Probar la demo](#3-probar-la-demo)
4. [Los datos y el perfil](#4-los-datos-y-el-perfil)
5. [Conectar el agente](#5-conectar-el-agente)
6. [Arrancar la app cada día](#6-arrancar-la-app-cada-día)
7. [Configurar las fuentes de ofertas](#7-configurar-las-fuentes-de-ofertas)
8. [De la oferta al envío](#8-de-la-oferta-al-envío)
9. [Seguimiento, respuestas y resultados](#9-seguimiento-respuestas-y-resultados)
10. [Entrevistas y ofertas recibidas](#10-entrevistas-y-ofertas-recibidas)
11. [El agente desde la UI](#11-el-agente-desde-la-ui)
12. [Configuración](#12-configuración)
13. [Actualizar](#13-actualizar)
14. [Problemas frecuentes](#14-problemas-frecuentes)
15. [Desarrollo](#15-desarrollo)

## 1. Requisitos

CandidatAI se desarrolla y se prueba en **Windows 11**. En macOS y Linux tiene instalador y los
botones que abren el agente funcionan, pero se están probando todavía: Linux en WSL2 y macOS en la
CI.

**Para usarla** solo hace falta Windows, macOS o Linux y, para las plantillas de Word («ATS
sencilla», «Clásica con foto» o un diseño propio importado de Word), LibreOffice. Sin él, los CVs y
las cartas salen igual en PDF con la plantilla «Moderna a dos columnas», y la app avisa. El
instalador se encarga del resto (uv, Python y el Chromium que genera los PDF). Para que el agente
haga su parte hace falta también **un agente de IA** (Claude Code, Codex, Antigravity CLI…; ver la
sección 5).

**Para desarrollar** (clonar el repositorio y cambiar el código):

| Qué | Para qué | Cómo |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python 3.12 y las dependencias del backend (no hace falta instalar Python aparte) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Node LTS + pnpm | Compilar la UI y desarrollarla | Node desde nodejs.org; `npm install -g pnpm` (desde Node 25 ya no viene `corepack`) |
| LibreOffice **o** el Chromium de Playwright | Los PDF de los CVs y las cartas | LibreOffice desde libreoffice.org (si no está en `C:\Program Files\LibreOffice` ni en el `PATH`, se define `SOFFICE_PATH` en `.env`); Chromium con `uv run playwright install chromium` |
| Git | Clonar y actualizar | git-scm.com |

Después de instalar, hay que abrir una terminal nueva para que el `PATH` se actualice.

## 2. Instalación

### Para usarla: el instalador

En PowerShell (no hace falta ser administrador):

```powershell
iwr -useb https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.ps1 -OutFile $env:TEMP\cai-install.ps1
powershell -ExecutionPolicy Bypass -File $env:TEMP\cai-install.ps1
```

El instalador:

1. instala [uv](https://docs.astral.sh/uv/) si no está (con él viene Python 3.12);
2. descarga la última versión de CandidatAI, con la UI ya compilada (no hace falta Node), y
   comprueba su suma SHA-256 antes de abrirla: si no coincide con la publicada, no instala nada;
3. la deja en `%LOCALAPPDATA%\CandidatAI\app`, y los datos en `%LOCALAPPDATA%\CandidatAI\data`;
4. prepara el entorno, el Chromium de los PDF y la base de datos;
5. crea un acceso directo **«CandidatAI»** en el escritorio y en el menú Inicio.

Al abrir el acceso directo se abre enseguida el navegador con «Arrancando CandidatAI…», y en cuanto
la app responde pasa sola a `http://127.0.0.1:8000`. La ventana que aparece debe quedarse abierta
mientras se usa la app; al cerrarla, se cierra CandidatAI.

- **Antes de instalar**, `-WhatIf` (al final de la segunda línea) explica lo que haría sin cambiar
  nada. En los ejemplos de abajo, si PowerShell no deja ejecutar scripts, se usa
  `powershell -ExecutionPolicy Bypass -File .\install.ps1 …` en vez de `.\install.ps1 …`.
- **Actualizar:** se vuelve a ejecutar el instalador (con CandidatAI cerrada). Los datos no se
  tocan, y el `.env` de la app (`…\CandidatAI\app\.env`) se conserva.
- **Desinstalar:** `.\install.ps1 -Uninstall` quita la app y los accesos directos, no los datos
  (con `-RemoveData`, también los datos, previa confirmación).
- **Desde una copia del repositorio:** `.\install.ps1 -Source <carpeta del repositorio>`, después
  de compilar la UI (`pnpm build`). Con un zip local, `-Source .\candidatai.zip` comprueba la suma
  si tiene al lado su `candidatai.zip.sha256`. `-SkipChecksum` no la comprueba: solo para una URL
  propia que no la publique.

### En macOS y Linux: `install.sh`

En una terminal (no hace falta `sudo`):

```bash
curl -fsSL https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.sh | bash
```

Hace lo mismo que el de Windows:

1. instala uv si no está;
2. descarga la última versión, con la UI ya compilada, y comprueba su suma SHA-256;
3. la deja en `~/Library/Application Support/CandidatAI/app` (macOS) o en
   `~/.local/share/candidatai/app` (Linux, o `$XDG_DATA_HOME/candidatai/app`), y los datos al lado,
   en `…/data` (`uv run cai paths` indica dónde);
4. prepara el entorno, el Chromium de los PDF y la base de datos. En Linux, si a Chromium le faltan
   librerías del sistema, indica el comando de la distribución (lleva `sudo` y se ejecuta a mano);
5. crea el acceso directo **«CandidatAI»**: en macOS, `~/Applications/CandidatAI.app`, que abre
   Terminal; en Linux, en el menú de aplicaciones, que abre la terminal. Esa ventana debe quedarse
   abierta mientras se usa la app; al cerrarla, se cierra CandidatAI.

- **Antes de instalar:** `curl -fsSL …/install.sh | bash -s -- --dry-run` explica lo que haría.
- **Actualizar:** se vuelve a ejecutar con CandidatAI cerrada; los datos y el `.env` se conservan.
- **Desinstalar:** `bash install.sh --uninstall` quita la app y el acceso directo, no los datos (con
  `--remove-data`, también los datos, tras confirmarlo escribiendo «borrar»). Solo toca carpetas que
  creó él (llevan un fichero `.candidatai`).
- **Desde una copia del repositorio**, con la UI compilada: `bash install.sh --source <carpeta>`.
  `--skip-checksum` no comprueba la suma del zip: solo para una URL propia que no la publique.
- En macOS, la primera vez puede pedir permiso para que la app controle Terminal: hay que aceptarlo.

### Con Docker (opcional)

Para no instalar Python ni Chromium en el equipo, CandidatAI arranca en un contenedor. Es una
alternativa con límites: **lo recomendado sigue siendo el instalador**. El agente de IA no va dentro
del contenedor, así que lo que necesita abrirle una ventana no funciona igual.

Hace falta Docker (en Windows, Docker Desktop) y una copia del repositorio. Desde su carpeta:

```bash
docker compose up -d --build        # la primera vez tarda unos minutos (construye la imagen)
```

La app queda en `http://127.0.0.1:8000`, solo en el equipo. Los datos van en el volumen
`candidatai-data`, que sobrevive a parar, actualizar o borrar el contenedor. Si hay un `.env` en la
carpeta, el contenedor lo lee (claves de portales, IMAP…): con IMAP configurado, su worker lee las
alertas por correo igual que el de la instalación nativa, pero las guarda en el volumen. El
contenedor no tiene llavero: la contraseña de un buzón añadido desde la UI va como secreto de Docker
o variable de entorno ([`CONFIGURAR_CORREO.md`](CONFIGURAR_CORREO.md#docker)) y luego se recrea el
contenedor (`docker compose up -d`).

- **Parar y arrancar:** `docker compose stop` y `docker compose start`.
- **Actualizar:** `git pull` y `docker compose up -d --build`.
- **Diagnóstico:** `docker compose exec candidatai cai doctor`. La sección «Docker» indica dónde
  están los datos y qué no funciona dentro.
- **La demo:** `docker compose exec candidatai cai demo seed` la crea en otro volumen. Para abrirla,
  `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d`. Para volver a los datos
  reales, `docker compose up -d`.

**Qué funciona y qué no dentro de Docker:**

| | Con Docker |
|---|---|
| UI, ofertas, revisión, seguimiento y resultados | Sí |
| Fuentes de ofertas y alertas por correo (el worker) | Sí |
| CVs y cartas en PDF | Sí, con las plantillas html (`moderna-2col`…). Las docx no, porque no hay LibreOffice: si toca una, se usa `moderna-2col` y la app avisa |
| El agente por MCP o `cai … --json` | Sí, desde fuera del contenedor (abajo) |
| Botones del agente | Copian la orden para pegarla en el agente |
| «En segundo plano» | No: el agente no está en el contenedor |
| Candidatura asistida | La oferta se abre en el navegador habitual, se envía a mano y se pulsa «Marcar como enviada» |
| Similitud semántica del score | No (la imagen no trae torch); el score funciona igual |
| Contraseñas de los buzones | No hay llavero en el contenedor: van como secreto de Docker o variable de entorno ([`CONFIGURAR_CORREO.md`](CONFIGURAR_CORREO.md#docker)) |

**El agente, desde fuera.** El agente se ejecuta en el equipo, en la carpeta del repositorio (lee de
ahí los skills y `AGENTS.md`), y habla con la app del contenedor:

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
  - En Codex y OpenCode se cambia un fichero generado: `uv run scripts/sync_agents.py` lo devolvería
    a la orden nativa.
- **Sin MCP**, los comandos `cai … --json` van con `docker exec -i candidatai cai …`. Por ejemplo:
  `docker exec -i candidatai cai status --json`. Las entradas largas se pasan con `--file`, en un
  fichero dentro del contenedor: `docker cp entrada.json candidatai:/data/tmp/`.

**Copia de seguridad.** Los datos están en el volumen, no en una carpeta del equipo. Para copiarlo
(con la app parada, para que la base de datos esté quieta):

```bash
docker compose stop
docker run --rm -v candidatai-data:/data -v "$PWD":/backup alpine tar czf /backup/candidatai-data.tgz -C /data .
docker compose start
```

Sirve igual en PowerShell. Para restaurarla en un volumen vacío:
`docker run --rm -v candidatai-data:/data -v "$PWD":/backup alpine tar xzf /backup/candidatai-data.tgz -C /data`.
Para tener los datos en una carpeta del equipo, se cambia en `docker-compose.yml` el volumen por esa
carpeta (la línea comentada); en Linux, la carpeta tiene que poder escribirla el uid 1000.

### Para desarrollar: clonar el repositorio

```powershell
git clone https://github.com/DiegoPrieto23/candidatai.git candidatai
cd candidatai\backend
uv sync                                # dependencias del backend (crea .venv)
uv run playwright install chromium     # plantillas html y PDF sin LibreOffice
uv run cai doctor                      # comprueba el entorno e indica qué falta
uv run cai agents doctor               # qué agentes de IA hay, cuál se usa y qué falta
cd ..\frontend
pnpm install
pnpm build                             # la UI compilada que sirve `cai start`
```

Opcional: la similitud semántica local («comparación por significado»: trae torch, 1-2 GB). Se
instala desde la UI: en la página **Agente**, sección «Comparación por significado» (o junto al
encaje de cualquier oferta, donde avisa si falta), «Qué aporta y cómo activarla» → «Instalar».
Mientras se instala, ahí mismo lo indica. La elección se guarda en los datos: se usa en todas las
ofertas desde entonces y, al actualizar la app (o con `uv sync` sin el extra), el worker la vuelve a
instalar al arrancar. A mano: `uv sync --extra matching`. Sin ella el encaje se calcula igual, sin
ese componente.

## 3. Probar la demo

La demo es una candidata inventada con 65 ofertas (5 de ellas, de dos buzones de alertas), 8
semanas de historial y 2 CVs. Vive en su propia carpeta y nunca toca los datos reales. Hay dos: en
español (una candidata en Galicia) y en inglés (una candidata en Dublín, con `--lang en`).

Trae también lo que habrían dejado ella y su agente, para que ninguna pantalla salga vacía:
valoración del encaje, carta y respuestas de screening de una oferta, un mensaje de LinkedIn y un
seguimiento, dos dosieres de empresa (uno con bandera roja), el plan de una entrevista y el repaso
de dos, los datos de la oferta recibida, tres correos de empresas en «Respuestas» (dos con
propuesta y uno sin clasificar, con texto oculto para una IA), dos huecos en «Habilidades por
desarrollar», un encargo pendiente, el contexto, una muestra de estilo y una tabla de salarios.

```powershell
cd backend                                   # instalada: cd $env:LOCALAPPDATA\CandidatAI\app\backend
uv run cai demo seed                         # --force para recrearla
$env:CAI_DATA_DIR = "data-demo"; uv run cai start
# en inglés: uv run cai demo seed --lang en --dir data-demo-en
```

Con la app instalada, antes se cierra CandidatAI. La demo se guarda junto a los datos (por ejemplo,
`%LOCALAPPDATA%\CandidatAI\data-demo`), así que actualizar no la borra. Para volver a los datos
reales, se cierra la ventana y se abre CandidatAI como siempre.

Se abre el navegador en `http://127.0.0.1:8000` con un banner «Modo demo». Los botones del agente lo
abren ya apuntando a la demo. Para abrirlo a mano, se arranca con `CAI_DATA_DIR=data-demo` para que
su servidor MCP use esa carpeta y no los datos reales.

Con el repositorio clonado, antes hay que compilar la UI (`cd frontend; pnpm install; pnpm build`) y
repetirlo cada vez que se cambie de rama o se actualice: `cai start` sirve la UI compilada, y con una
vieja no aparece lo que se haya añadido después.

## 4. Los datos y el perfil

Todos los datos viven en `data/`, que está fuera de git: base de datos, perfil, CVs, plantillas,
foto, documentos y correos. Las claves van en `.env`, también fuera de git.

| Qué | Dónde | Cómo |
|---|---|---|
| **Perfil** (la fuente de verdad de todo lo que se escribe sobre la persona) | `data/profile.yaml` | Para empezar, se sube el CV en «Mi perfil» y se pulsa «Crear el perfil desde un CV» (o se le pide al agente): el skill `update-profile` lo lee, pregunta lo que falte y lo valida. Sin agente, «Empezar a mano» crea un perfil mínimo (nombre, titular, puesto y niveles) y abre el editor. Después, **se rellena y se retoca en «Mi perfil»**: experiencia y logros, proyectos, formación, skills e idiomas, historias STAR, qué se busca y las preferencias de CV y carta, por bloques. Cada bloque se guarda solo, conserva el formato y los comentarios del fichero, avisa si se cambió por fuera y se puede deshacer. Cada cambio crea una versión: la pestaña «Historial» muestra cuándo se hizo, de dónde viene (la app, el agente, al deshacer) y qué cambió, bloque a bloque y como «Antes → Ahora», sin YAML; se puede volver a cualquiera, y eso es otra versión que también se deshace. Con el perfil ya hecho, «Importar información desde un CV» añade lo que le falte desde otro CV y muestra las diferencias antes de escribir. Editar el YAML a mano sigue siendo posible |
| **Un CV propio como diseño** | `data/templates/<id>/` | Se sube un CV con el diseño deseado en «Mi perfil → Plantillas de CV → Subir nueva plantilla» y se pulsa «Convertir en plantilla» (usa el skill `import-cv-template`). Vale Word, PDF, imagen o HTML (Canva, Google Docs…) |
| **Foto** | `data/photo.jpg` (o png), y la original en `data/photo-original.*` | Se sube, se encuadra (zoom y arrastre, en el navegador), se vuelve a encuadrar o se quita en «Mi perfil → Datos personales». Cada plantilla la recorta a su forma; se incluye o no según el país de la oferta |
| **Contexto** (estilo, narrativa, criterios) | `data/contexto/*.md` | Se edita en «Mi perfil → Documentos», en «Notas para el agente» (con vista previa), o en un editor. Orienta al agente, pero nunca respalda un hecho del CV |
| **Muestras de estilo** (cartas, correos o posts propios) | `data/documentos/estilo/` | Se suben en «Mi perfil → Documentos», en «Notas para el agente» (.txt, .md, .docx, .pdf). El agente toma de ellas el tono, nunca los hechos, y las lee como dato: si traen texto de otros con órdenes, no las sigue |
| **Documentos fuente** (CVs antiguos, títulos, referencias) | `data/documentos/` | El CV y la exportación de LinkedIn se suben en «Mi perfil → Documentos», en «Archivos»; el resto, en su carpeta. `update-profile` los puede leer, confirmando antes de escribir |
| **Lo hecho en público** (repositorios, portfolio, Kaggle, Scholar, certificaciones verificables) | `data/profile.yaml` | Skill `expand`, o «Mejorar el contenido del perfil» en «Mi perfil». Conviene usarlo **justo después de crear el perfil** y cada vez que haga falta pulirlo: revisa el perfil entero (logros sin cifra, textos de relleno, huecos) y propone proyectos, skills (sin nivel: se pone a mano), logros con los números que da la fuente y certificaciones, cada uno con su enlace en `source`, y solo escribe lo aceptado. Solo web pública: ni LinkedIn ni nada con login. Leer los enlaces necesita un agente con búsqueda web; revisar el perfil, no |

El mínimo salarial va en «Buscar ofertas → Más ajustes» (o en `private.salary_floor_eur` del
perfil): la app descarta las ofertas que publican un sueldo por debajo y lo usa para comparar las
ofertas recibidas, pero el agente nunca ve la cifra; solo sabe que una oferta cayó «por debajo del
mínimo salarial». En «Más ajustes» también se eligen años mínimo y máximo, idiomas, palabras que
descartan, tipo de contrato y jornada, y si se excluyen consultoras o agencias de selección.

**Dónde están los datos y cómo copiarlos.** `uv run cai paths` (o `cai paths` en la carpeta de la
app) indica qué carpeta se usa. Con el instalador:

| Sistema | Carpeta de datos |
|---|---|
| Windows | `%LOCALAPPDATA%\CandidatAI\data` |
| macOS | `~/Library/Application Support/CandidatAI/data` |
| Linux | `~/.local/share/candidatai/data` (o `$XDG_DATA_HOME/candidatai/data`) |
| Docker | el volumen `candidatai-data` (ver «Con Docker») |
| Repositorio clonado | `data/` en la raíz |

Para hacer una copia de seguridad, **se cierra CandidatAI** (la base de datos tiene que estar
quieta) y se copia esa carpeta entera a otro sitio: un zip, otro disco o la nube. Para restaurarla,
con la app cerrada, se pone la copia en su sitio. Conviene guardar también el `.env` de la app si
tiene claves propias. Las contraseñas del llavero del sistema no van en la copia: en otro equipo, se
vuelven a escribir en «Editar» de cada buzón.

En «Mi perfil», cada logro y cada historia tienen **«Mejorar con el agente»**: el agente propone una
versión más clara, pregunta los números que falten (nunca los inventa) y solo escribe con
confirmación. En «Historias STAR», **«Proponer historias desde la experiencia»** sugiere historias a
partir de los logros que aún no tienen. El correo y el teléfono se editan ahí, pero el agente sigue
sin verlos. Lo mismo el mínimo salarial (`private`), en «Buscar ofertas → Más ajustes».

## 5. Conectar el agente

El agente se abre **en la raíz del repositorio**: ahí encuentra las instrucciones (`AGENTS.md`), los
skills y el servidor MCP ya configurados.

- **Claude Code:** `claude` en la raíz. Con `/mcp` se comprueba que el servidor `candidatai` está
  conectado. Los skills se invocan como `/generate-cv 42`.
- **Codex:** usa `.codex/` (generado). Los skills se invocan como `$generate-cv 42`.
- **Antigravity CLI:** `agy` en la raíz. Lee `AGENTS.md`, los skills de `.agents/skills/` y el
  servidor MCP de `.agents/mcp_config.json` (generado). Los skills se invocan como `/generate-cv 42`.
  Sirve con Google AI Pro o Ultra y con el plan gratuito, que tiene un cupo semanal.
- **Otros agentes:** si leen `AGENTS.md` y hablan MCP, se registra el servidor `candidatai` con el
  comando de `.mcp.json`. Si no hablan MCP, cada herramienta tiene su comando
  `uv run --directory backend cai … --json` (tabla en
  [`AGENT_INTERFACE.md`](AGENT_INTERFACE.md)).

Más detalle, y cómo añadir un agente: [`AGENTS_COMPAT.md`](AGENTS_COMPAT.md).

### Sin pagar por tokens: modelos gratuitos y locales

Además de una suscripción (Claude, ChatGPT), se pueden usar agentes open-source con un **modelo
local** (Ollama o LM Studio: gratis y nada sale del equipo) o con un **modelo gratuito en la nube**
(OpenRouter `:free`, el plan gratuito de Antigravity: gratis, con límites diarios, y las ofertas y el
perfil van al proveedor). Con Ollama, hay que poner `OLLAMA_CONTEXT_LENGTH=32768` o más: con los
4 096 que trae por defecto, los agentes no funcionan. `cai agents doctor` y la tarjeta de cada agente
indican qué modelos hay y si el contexto llega. Los modelos de unos 8B o menos suelen fallar con el
CV. Guía completa, con los modelos recomendados según la memoria y qué sale del equipo en cada vía:
[`MODELOS_GRATIS.md`](MODELOS_GRATIS.md).

## 6. Arrancar la app cada día

- **Con el instalador:** el acceso directo «CandidatAI». Para cerrarla, se cierra su ventana.
- **Desde el repositorio:** `cd backend; uv run cai start`. Arranca la API (que sirve también la
  UI) y el worker en un solo comando, aplica las migraciones pendientes y abre el navegador.
  Ctrl+C para cerrar. Sus registros van a `data/logs/start-*.log`.
- **Para desarrollar la UI** con recarga en caliente: `uv run cai start --dev` arranca además Vite
  y abre `http://127.0.0.1:5173`. También se pueden arrancar por separado `cai serve`,
  `cai worker` y `pnpm dev`, cada uno en su ventana.

CandidatAI se arranca **fuera del agente** (una ventana propia o el acceso directo): si el agente se
queda sin memoria, puede cerrar lo que haya lanzado él.

La primera vez, **Cómo funciona**, al pie del menú, explica el recorrido completo y quién hace qué.

Para una duda concreta, el botón **Ayuda** (el `?` de abajo a la derecha, en todas las páginas;
también se abre con la tecla `?` y se cierra con `Esc`) busca en las
[preguntas frecuentes](PREGUNTAS.md) y en esta guía, y cada respuesta lleva a la pantalla donde se
hace. Funciona sin conexión y sin agente.

Al lado, el botón **Asistente** (el del destello, también en todas las páginas) abre el mismo panel
en su otra pestaña, que funciona como un chat: abajo se escribe la petición al agente en lenguaje
natural («¿qué tengo pendiente esta semana?», «valora la oferta de Acme») y se pulsa Intro o la
flecha (Mayús+Intro salta de línea). La pregunta queda a la derecha y la respuesta a la izquierda,
separadas por días. La primera vez propone unos ejemplos; al pulsar uno se escribe en la caja, y el
envío es manual. La app no llama a ningún modelo: le pasa la petición al agente que ya se usa.

- **Si el agente trabaja en segundo plano desde la app,** la petición se lanza al momento. El panel
  muestra el progreso y la respuesta, con enlaces a la oferta o a la pantalla de la que habla. Si el
  agente necesita un dato, lo pregunta en un aviso de la app.
- **Si no,** se guarda como encargo para la próxima sesión (`handle-requests`) y el hilo lo indica.
- **Conversaciones:** cada vez que se abre el panel empieza una conversación nueva (salvo que el
  agente esté trabajando en una, que se abre). En una misma conversación, el agente recibe lo que ya
  se le preguntó y lo que contestó, para poder seguir («¿y la de Acme?»). El botón de la barra
  lateral, en la cabecera, abre las conversaciones anteriores por fechas (Hoy, Ayer, Últimos 7 días,
  Antes); el del lápiz empieza otra. Cada una se borra con la papelera, tras confirmarlo.
- **Qué puede hacer:** consultar las ofertas, los procesos, las entrevistas, el perfil y los
  resultados, valorar una oferta ya leída y guardar las indicaciones de una carta. Para lo que tiene
  su propio botón (un CV, una carta, una guía de entrevista) indica dónde está. No lee el texto
  original de las ofertas ni de los correos, solo lo que la app ya extrajo de ellos.
- **Qué requiere siempre confirmación manual:** enviar una candidatura, aprobar o descartar una
  oferta, aceptar la respuesta de una empresa y borrar. El agente lo deja preparado; nunca lo
  confirma.

Sin agente instalado, la pestaña lo indica y la ayuda sigue funcionando. El panel guarda las últimas
20 peticiones en el equipo.

El menú tiene nueve entradas: **Inicio** y **Mi perfil**; en Búsqueda, **Buscar ofertas** y
**Bandeja de ofertas**; en Procesos, **Tablero**, **Calendario**, **Respuestas** y **Resultados**; y
**Agente**. Lo demás son pestañas dentro de ellas: la Bandeja tiene **Revisión rápida** y **Por
completar**, y Mi perfil, **Habilidades por desarrollar** y **Plantillas de CV**. Buscar ofertas
tiene dos pestañas, cada una con su dirección: **Buscar** (lo que se busca, con «Más ajustes», y los
portales) y **Dónde buscar** (portales, empresas, correo y botón del navegador).

Un día normal:

1. **Inicio** muestra lo pendiente (ofertas por revisar, CVs listos, seguimientos vencidos).
2. El agente ejecuta `process-jobs` (lee y valora las nuevas), o se pulsa «Valorar las ofertas
   nuevas» en la UI.
3. Se aprueba o se descarta en **Revisión rápida**, en la Bandeja de ofertas.
4. `generate-cv` para las aprobadas y, en su momento, el envío desde la ficha.
5. `daily-summary` resume todo eso en una respuesta.

## 7. Configurar las fuentes de ofertas

| Fuente | Cómo se configura |
|---|---|
| **Alta manual** | «Nueva oferta» en la UI (URL o texto pegado; con texto, el puesto y la empresa son obligatorios porque con ellos se detectan duplicados, y el botón indica qué falta). Con una URL de LinkedIn, la app guía: «Abrir la oferta» para pulsar allí el botón del navegador, o «Pegar texto» con el enlace ya rellenado |
| **Empresas con portal propio** (Greenhouse, Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters, Recruitee) | En «Buscar ofertas», pestaña «Dónde buscar → Empresas con portal propio»: «Añadir empresa», su nombre y la dirección de su web de empleo tal como aparece en el navegador (`https://careers.acme.com/madrid/`). La app deduce qué sistema usa y los lugares de la dirección («Solo Madrid»), y solo muestra las ofertas que encajan con el perfil. En cada empresa, el interruptor la pausa o la reactiva, y su menú ⋯ trae «Buscar ahora», su web y sus lugares. Si no reconoce la web, la añade a los portales para que el agente la recorra. Por terminal, `cai sources add --name "Acme" --url https://careers.acme.com/`; `cai sources discover --file empresas.txt` busca el tablero de cada empresa de una lista. Si la detección falla, «Más opciones» permite poner el sistema y su nombre en la dirección: [`FUENTES_OFERTAS.md`](FUENTES_OFERTAS.md#cómo-encontrar-el-slug) |
| **InfoJobs y Adzuna** | Sus claves en `.env` (`CAI_INFOJOBS_CLIENT_ID`/`_SECRET`, `CAI_ADZUNA_APP_ID`/`_KEY`) y una búsqueda con `cai sources add` |
| **Manfred y freehire.me** | Sin claves: una búsqueda en la misma página o con `cai sources add --kind manfred --name Manfred --query "data engineer"` (en freehire, también `--country` y `--remote-only`) |
| **Alertas por correo** | Se crean alertas en LinkedIn, InfoJobs, Indeed… y se hace que lleguen a una etiqueta del correo. En «Dónde buscar → Alertas por correo → Añadir buzón» se conectan uno o varios buzones (Gmail, Outlook, Yahoo, iCloud u otro IMAP, siempre en solo lectura) o una carpeta de `.eml`; el asistente explica cada proveedor y prueba la conexión antes de guardar. La contraseña se guarda cifrada en el llavero del sistema (Administrador de credenciales en Windows, Llavero en macOS) y no vuelve a salir. Paso a paso en [`CONFIGURAR_CORREO.md`](CONFIGURAR_CORREO.md). Lo que llega aparece en la **Bandeja de ofertas**; las que solo traen título y enlace esperan en su pestaña «Por completar» |
| **Botón «Enviar a CandidatAI»** | En **Dónde buscar → Botón del navegador**: la app guía para cargar `extension/` en Chrome, Edge o Brave y la conecta con un clic. Instrucciones: [`extension/README.md`](../extension/README.md) |
| **El agente con el navegador** | En «Dónde buscar → Portales de empleo», «Configurar con el agente» (`search-jobs configurar`) elige portales y búsquedas; o se añaden a mano: en InfoJobs, Tecnoempleo, Indeed y LinkedIn las búsquedas salen solas de los puestos y las ubicaciones del perfil, y cada portal se edita con su lápiz; `search-jobs` los recorre. LinkedIn queda desactivado hasta que se active a mano. En la franja de arriba de «Buscar», los puestos y lugares se quitan con su ✕ y se añaden con «+ Añadir puesto» o «+ Añadir lugar»; al pulsar un lugar se elige qué se acepta en él (cualquier modalidad, solo híbrido o remoto, o descartarlo), y la modalidad y el nivel se marcan como chips. Cada cambio se guarda en el perfil al momento, con «Deshacer», y al añadir un puesto se sugieren los títulos de las ofertas aprobadas que los puestos aún no cubren. En la misma franja, «Hasta N ofertas por portal» cambia a la vez el límite de los portales elegidos y el de los que se añadan (el de uno solo, en «Dónde buscar»). «Más ajustes» (con el número de grupos que tienen algo puesto) despliega debajo los años de experiencia, el sueldo mínimo, los idiomas, el contrato y la jornada, y lo que se descarta; esos se guardan juntos con «Guardar cambios», con «Deshacer» después. `/buscar/ajustes` abre la página con «Más ajustes» desplegado. Al pulsar «Buscar ahora», la app revisa a la vez las webs de empleo de las empresas con portal propio (sin el agente y sin gastar tokens; las revisadas hace poco se saltan) y un aviso dice «Buscando…» en todas las páginas hasta que terminan el agente y las empresas. Sin portales elegidos, el botón revisa solo las empresas, que se ven en tarjetas bajo los portales (Activa o Pausada y su último recorrido). En cada portal, los **problemas** son lo que impidió leerlo (captcha, inicio de sesión, página cambiada) y las **notas**, lo que el agente apuntó sin que fallara nada, como las búsquedas que dejó sin recorrer. Cada tarjeta indica qué trajo la última búsqueda, con las mismas cifras que su leyenda (**Vistas · Pasan los filtros · Ya estaban · Nuevas**, y de las nuevas, las **Reabiertas**), y por qué paró: «Llegó a lo de la búsqueda anterior» (no vuelve a abrir lo ya visto), «Alcanzó el límite: quedan 5 sin abrir» (si son muchas, conviene subir las ofertas por recorrido de ese portal), etc. El aviso «Buscando…» las suma al terminar |
| **Búsqueda pública de LinkedIn** | Interruptor «Búsqueda pública sin sesión» en la tarjeta de LinkedIn de «Dónde buscar → Portales de empleo». Apagado por defecto: va contra las condiciones de LinkedIn y puede bloquear la IP un tiempo |

El worker ejecuta las fuentes automáticas cada día a la hora de `connectors.daily_at`
(`config/policies.yaml`) y al arrancar si se perdió alguna. Detalle de cada vía:
[`FUENTES_OFERTAS.md`](FUENTES_OFERTAS.md).

## 8. De la oferta al envío

1. **Extraer:** antes, si un título o una empresa no interesan, la oferta se quita desde la Bandeja
   («Por completar» o «Por leer») con «Descartar», una a una o seleccionando varias: no gasta agente
   y se puede deshacer. `process-jobs` convierte el texto de cada oferta en datos estructurados (es
   la primera fase de «Valorar las ofertas nuevas», que sigue con el paso 2). El texto de las
   ofertas es contenido no confiable: si trae texto oculto o frases dirigidas a una IA, la ficha lo
   avisa.
2. **Valorar:** la app calcula el encaje (de 0 a 100: «buen encaje», «encaje posible» o «encaje
   bajo», y al pasar el ratón, de dónde sale) y aplica los filtros duros; `assess-fit` añade una
   valoración razonada: «Valorar las ofertas nuevas» la hace justo después de leerlas y «Valorar
   esta oferta» en su ficha, para una sola. Si una oferta no tiene encaje, su ficha indica qué
   falta: el perfil, que el agente la lea o las dos cosas.
3. **Revisar:** en la Bandeja, pestaña «Revisión rápida», `J`/`K` para moverse, `A` para aprobar,
   `D` para descartar (con motivo) y `O` para abrir la ficha. Un descarte se deshace en el aviso;
   una aprobación, con «Reabrir» en la ficha.
4. **CV:** `generate-cv 42` redacta el contenido, el código lo valida y lo genera y el rol
   `verifier` lo revisa. En la ficha, la pestaña «Candidatura» muestra el CV a tamaño de lectura y,
   a su lado, un panel con:
   - **Pedir cambios:** se escribe qué cambiar («el resumen más corto», «quita el proyecto X») y el
     agente (`correct-cv`) toca solo eso, sin inventar nada, y lo verifica. Si se pide que ocupe una
     página, una versión que no cabe no se guarda.
   - **Editar texto:** se cambian a mano el resumen y las viñetas, se quitan o reordenan logros con
     sus flechas y se organizan las skills por grupos: cada grupo con su nombre y sus skills como
     etiquetas (× para quitar, Intro para añadir), y «Añadir grupo», subir, bajar o quitar grupos.
     Todo sin agente. Para añadir un logro, se piden cambios. La app avisa de lo que el perfil no
     respalda, y esa versión queda sin verificar hasta pulsar «Verificar esta versión» (`verify-cv`).
   - **Diseño:** plantilla, foto, color y secciones ocultas, sin gastar agente.

   Cada corrección o edición es una versión nueva: la ficha muestra qué cambió, sección a sección,
   y «Volver a esta versión» no borra ninguna.
5. **Carta:** «Escribir carta» en la ficha (o `generate-cover-letter 42`), con el mismo desplegable
   que «Generar CV». Sigue las indicaciones generales (perfil) y las de la oferta (ficha); en segundo
   plano, si no hay ninguna, usa las de por defecto. Sale a juego con el CV.
6. **Candidatura:** `prepare-application 42` prepara las respuestas de screening. En la ficha,
   «Preparar candidatura» abre un navegador propio (perfil en `data/browser-profile/`), rellena el
   formulario y se para. Tras la revisión, solo envía si se escribe el nombre de la empresa. Ante un
   captcha o un login, se para y deja la pestaña para seguir a mano. Si se envía por otro lado, se
   marca como enviada a mano.

## 9. Seguimiento, respuestas y resultados

- **Tablero:** kanban por etapas. Una tarjeta solo cambia de columna registrando lo que pasó
  (respuesta, entrevista, prueba, oferta, rechazo), y las tarjetas solo van hacia una etapa
  posterior: al arrastrar una, se marcan las columnas a las que puede ir. Reabrir una oferta cerrada
  está en «Actualizar estado». Entrevistas y pruebas crean un hito con fecha, exportable al
  calendario (`.ics`). En la ficha, «¿Qué ha pasado?» registra también lo que no cambia de etapa
  (otra respuesta, otra entrevista, una prueba, la oferta) y enlaza a «Anotar oferta» y a «Hitos»
  para los detalles; «Aceptar la oferta» sale cuando ya hay una oferta.
  Con «Personalizar columnas» se eligen entre 3 y 5 columnas: cada etapa va a la columna elegida con
  su selector (p. ej. «Aprobada» y «CV listo» juntas), cada columna lleva sus etapas como etiquetas y
  un nombre, y se ordenan arrastrándolas o con sus flechas. Una vista previa muestra cómo quedará el
  tablero. Es solo la vista: las etapas de las ofertas no cambian y las tarjetas siguen avanzando
  solo a una etapa posterior. «Restablecer» vuelve a las de siempre al guardar. Se guarda en el
  navegador.
- **Calendario:** todos los hitos (entrevistas, pruebas, plazos y otros, también los pasados) por
  mes, semana, día o agenda. Al pulsar uno se ven sus datos y se puede ir a la oferta. Para añadir
  uno, «Añadir hito», el «+» de un día o una hora libre de la semana: se elige la oferta (con muchas,
  se busca por empresa o puesto) y se guarda en su ficha. Hoy, los fines de semana y los días de
  otro mes se distinguen a simple vista, y cada tipo de hito lleva su color y su icono.
- **Avisos:** el `.ics` y el feed llevan alarmas, para que el calendario avise sin que la app envíe
  correos: un día y una hora antes de cada hito con hora, y a las 9:00 del día anterior de cada
  plazo. Outlook y Apple Calendar las usan; Google Calendar aplica sus propias notificaciones.
  Además, con «Avisos del navegador» (en el Calendario) y la app abierta, el navegador avisa una hora
  antes de cada entrevista o prueba, el día anterior de cada plazo y una vez al día de los
  seguimientos pendientes.
- **Seguimientos:** la app avisa de las candidaturas sin respuesta; `draft-follow-up` deja los
  borradores (máximo 2 por candidatura) y el de agradecimiento tras una entrevista. Se envían a mano.
- **Respuestas:** si se activa en un buzón, la app lee los correos de las empresas de los procesos;
  `review-replies` propone qué ha pasado y la propuesta se acepta en «Respuestas». Al aceptar o
  ignorar, un aviso indica en qué oferta ha quedado, con su enlace; «Ignorar» se puede deshacer
  desde él. Con el teclado: `J`/`K` para pasar de un correo a otro, `A` para aceptar, `I` para
  ignorar. Sin activarlo, se anota en su ficha o en el tablero con «Actualizar estado». Qué lee
  exactamente: [`CONFIGURAR_CORREO.md`](CONFIGURAR_CORREO.md#respuestas-de-las-empresas).
- **Resultados:** qué funciona. Arriba, frases sacadas de los datos: por qué canal responden más
  (referencia, web de la empresa, portales de empleo o las ofertas añadidas a mano), cuánto tardan
  las empresas en responder, por dónde responden antes y la mejor fuente. Cada frase sale cuando hay
  datos suficientes (unas 10 candidaturas enviadas por grupo; 5 respuestas para los tiempos) y una
  diferencia clara. Debajo, agrupado por pregunta: «¿Por dónde responden más y antes?» (por canal,
  con la tasa y la mediana de días, por fuente y por referencia); «¿Dónde se quedan las
  candidaturas?» («¿Cómo van las candidaturas?», también en Inicio, con una rama por cada grupo que
  paró, la primera respuesta y la gráfica por semana); «¿Qué puestos reciben respuesta?» y «¿Por qué
  se descartan ofertas?». En «Más análisis», plegado al final: «¿Acierta el encaje?» (por encaje,
  veredicto, plantilla, carta…), el coste del agente y «La búsqueda en números» (o
  `cai stats story`): las cifras desde el principio, sin empresas, con una línea para compartir si
  interesa. `review-search` hace la retrospectiva semanal.
- **Red:** los contactos de LinkedIn (exportación CSV) se importan con
  `cai contacts import-linkedin`, y las ofertas de sus empresas muestran «N contactos»;
  `draft-message` prepara el mensaje.

## 10. Entrevistas y ofertas recibidas

- **Varias rondas:** cada entrevista es un hito propio en la ficha (sección «Proceso»), con su
  **tipo** (RR. HH. o encaje cultural, técnica, caso práctico, final u otra), su guía, su plan y su
  repaso. La guía y el simulacro se adaptan al tipo y tienen en cuenta el repaso de las rondas
  anteriores.
- **Indicaciones para prepararla:** en una entrevista programada, la caja «Indicaciones para
  preparar y ensayar» guarda lo que deben tener en cuenta «Preparar» y «Simulacro» («más peso a
  SQL», «habrá un caso de negocio», «feedback más duro»…). Son de esa entrevista y se quedan
  guardadas hasta que se cambien.
- **Corregir una entrevista:** el lápiz la edita mientras está programada; la X la cancela (se
  queda en la ficha). Si se anotó por error, la papelera la **borra** del todo, también del
  historial y del embudo, y la etapa de la oferta se recalcula. Vale para cualquier hito.
- `prepare-interview 42`: lee todo lo que hay de la oferta, el perfil, lo ya enviado y la web,
  pregunta lo que falte y deja en la ficha una **guía en PDF** (el rol, las responsabilidades
  desglosadas, el encaje, lo ya respondido, la empresa y el sector, conceptos a repasar, preguntas
  probables con idea de respuesta, preguntas que hacer, la presentación personal y el plan), con el
  color de la empresa y en el idioma de la entrevista, y el plan por días. Bajo la guía, «Pedir
  cambios a la guía» (`correct-interview-guide`) toca solo lo pedido, conserva la versión anterior y
  muestra qué cambió; «Volver a la versión anterior» rehace el PDF sin agente.
- `mock-interview 42`: una pregunta cada vez, con feedback y una versión mejor basada en el perfil.
- `debrief-interview 42`: a partir de cómo fue, guarda notas y próximos pasos y propone historias
  STAR nuevas para el perfil (con confirmación).
- **Ofertas recibidas:** se anotan en la ficha y se comparan en «Ofertas recibidas», al pie del
  **Tablero** (aparece con dos o más), con el sueldo mínimo y con el rango publicado.
  `prepare-negotiation 42` prepara argumentos y guion sin proponer cifras.

## 11. El agente desde la UI

Muchas pantallas tienen botones que abren el agente con la orden ya escrita:

- **En una ventana aparte:** abre una ventana con el agente, donde se ve y se aprueba lo que hace.
  Si un botón no puede abrir el agente, muestra la orden entera en un recuadro con «Copiar» e indica
  dónde pegarla.
- **Avisos de lo que hace el agente:** lo que se lanza con un botón (leer y valorar ofertas, revisar
  respuestas, generar o corregir un CV, la carta, investigar la empresa, preparar una entrevista…)
  sale en un aviso en cualquier página, con lo que lleva hecho, y cambia cuando termina o si no ha
  podido. Se puede minimizar o cerrar; cerrarlo no para el agente. Cuando un CV o una guía de
  entrevista está listo, el aviso ofrece **Abrir PDF**; con permiso de notificaciones y otra ventana
  delante, también una notificación del sistema. El CV queda además en `data/cvs/` y la guía en
  `data/entrevistas/`.
- **El agente pregunta en la app:** si necesita un dato para escribir un CV, una carta o una guía,
  un aviso permite contestar ahí mismo. También se puede contestar en su ventana. Los permisos que
  pide y las conversaciones (un simulacro, p. ej.) siguen en su ventana.
- **En segundo plano** (Claude Code; OpenCode solo en `process-jobs` y `assess-fit`): para los
  skills que no preguntan (`process-jobs`, `assess-fit`, `generate-cv`, `correct-cv`, `verify-cv`,
  `generate-cover-letter` y el resumen en inglés). Corre sin ventana, solo con las herramientas de la
  app que necesita, y un aviso indica cuándo termina. Si el agente no puede, el desplegable propone
  uno que sí. Necesita `cai worker` en marcha.
  - **Coste:** la sección «Coste» de la página «Agente» suma tokens, tiempo y, si el agente lo da,
    dinero, por acción, agente y modelo (7 y 30 días), con lo que pesa cada skill; la ficha indica lo
    gastado en esa oferta y el embudo, por candidatura enviada y por entrevista. Lo que se hace en una
    terminal no cuenta: ahí el agente no devuelve su uso.
  - **Umbral antes de gastar:** en segundo plano, «Valorar las ofertas nuevas» y `assess-fit` solo
    valoran las ofertas con un encaje mínimo (por defecto, el mínimo de «Por revisar» menos 10; se
    cambia en «Coste»). «Por revisar» indica por qué se queda sin valorar una oferta por debajo.
  - **Varias a la vez:** por defecto, de una en una. Con `background_runs.max_parallel` (hasta 4)
    en `config/policies.yaml` van varias a la vez, nunca dos de la misma oferta; con
    `per_agent: {opencode: 1}` se limita un modelo local.
- **Dejar para la próxima sesión:** guarda el encargo; `handle-requests` lo hace al abrir el
  agente, o con «Atender encargos» en la página «Agente».

**Qué agente se abre.** La página «Agente» empieza por el agente y si está listo (o cómo instalar
uno). «Configurar agentes» muestra los agentes instalados, qué sabe hacer cada uno y cómo instalar
los que faltan. Ahí se eligen el agente por defecto, el modelo de cada agente y, en la tabla «Por
acción», otro agente o modelo para una acción concreta (p. ej. OpenCode con un modelo local para
procesar ofertas y Claude Code para el CV). El desplegable de cada botón (la flecha ▾) indica con qué
agente se abre y permite usar otro solo esa vez. Si un agente no sirve para una acción (le falta el
navegador para buscar ofertas, p. ej.), el botón lo indica y no lo lanza. Sin nada elegido, se usa
`CAI_AGENT` del `.env` o el primero instalado. En macOS y Linux, los botones abren Terminal.app o la
terminal del escritorio; para usar otra (iTerm2, kitty…), se pone `CAI_TERMINAL=iterm` (o su nombre
o ruta) en el `.env`.

**Niveles de gasto.** En la misma página, «Económico», «Equilibrado» y «Máximo» guardan el agente y
el modelo de las acciones principales. «Económico» usa un modelo local para procesar, valorar y
clasificar respuestas, y el agente más capaz para el CV. Se rellenan una vez y se aplica uno con un
clic. «Deshacer el último» deja las preferencias como estaban.

## 12. Configuración

- **`.env`** (en la raíz, fuera de git): `CAI_DATA_DIR`, `SOFFICE_PATH`, claves de InfoJobs y
  Adzuna, IMAP (`CAI_IMAP_HOST`, `CAI_IMAP_PORT`, `CAI_IMAP_USER`, `CAI_IMAP_PASSWORD`,
  `CAI_IMAP_FOLDER`, `CAI_IMAP_REPLIES_FOLDER`), `CAI_BROWSER_CHANNEL` (`chrome` o `msedge` para la
  candidatura asistida), `CAI_EMBEDDINGS=off`, `UV_PATH` (uv fuera del PATH), `CAI_LANG` (`es` o
  `en`: idioma de los mensajes de `cai start` en la terminal y de las órdenes al agente mientras no
  se elija idioma en el portal; sin ella, el del sistema). Nada es obligatorio. Las contraseñas y
  claves (`CAI_IMAP_PASSWORD`, `CAI_ADZUNA_APP_KEY`, `CAI_INFOJOBS_CLIENT_SECRET`) mejor en el
  llavero del sistema: si están en `.env`, la app ofrece moverlas allí.
- **`config/policies.yaml`:** umbral de score, pesos del score, hora de la ingesta diaria,
  frecuencia del correo, límites de la búsqueda con navegador y de la búsqueda pública de
  LinkedIn, frases de oferta cerrada… Tras cambiar el score, `cai match rescore` recalcula y
  `cai eval matching` mide el efecto.
- **El perfil:** preferencias (puestos, nivel, modalidad, zonas, idiomas), plantilla por defecto,
  reglas de plantilla y política de foto por país.

### Idioma

La interfaz está en **español** y en **inglés**. El botón del globo, abajo en la barra lateral, abre la lista
de idiomas; el cambio es instantáneo y la app lo recuerda
en ese navegador. La primera vez sigue el idioma del navegador: español si es español; si no,
inglés. Las fechas y los números también siguen el idioma. Al cambiarlo se vuelve a pintar la
página: un diálogo o un formulario a medias se cierran, así que conviene terminarlo antes.

Lo que la interfaz no traduce: los datos (ofertas, perfil, notas), lo que redacta el agente (los
CVs, las cartas y las valoraciones siguen el idioma de cada oferta) y algunos mensajes que escribe
el servidor sin un código que traducir (ciertos avisos y resultados de ejecuciones), que siguen en
español.

## 13. Actualizar

**Con el instalador:** se vuelve a ejecutar; los datos (`%LOCALAPPDATA%\CandidatAI\data`) no se
tocan y las migraciones se aplican solas.

**Desde el repositorio**, con el agente **cerrado** (su servidor MCP bloquea el entorno de Python):

```powershell
copy data\candidatai.db data\candidatai.db.bak     # copia de seguridad
git pull
cd backend; uv sync
cd ..\frontend; pnpm install; pnpm build
```

`cai start` aplica las migraciones al arrancar. Después se reinician CandidatAI y el agente.

## 14. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| Algo no funciona y no se sabe qué | `uv run cai doctor` comprueba base de datos, PDF, Chromium, plantillas, foto, correo y captura |
| «Hay que ejecutar `cai db upgrade`» | Hay migraciones nuevas: `uv run cai db upgrade` |
| `uv sync` falla con «fichero en uso» | Hay que cerrar el agente (su servidor MCP usa `cai-mcp.exe`) y la app (`cai.exe`), y repetir |
| Los PDF no salen | Instalar LibreOffice o `uv run playwright install chromium`; `cai doctor` lo comprueba |
| La UI dice que no conecta con la API | Arrancar CandidatAI (`cai start` o el acceso directo) y no cerrar su ventana |
| «El puerto 8000 lo usa otro programa» | Cerrar ese programa o usar `cai start --port 8001` |
| No está la UI compilada | En el repositorio, `cd frontend; pnpm install; pnpm build` (con el instalador ya viene) |
| Nada entra solo por la mañana | CandidatAI tiene que estar abierta (`cai start` arranca el worker) |
| Una plantilla sale «Sin permiso para leer la carpeta» (o «Plantillas» da `PermissionError`) | La creó un agente con *sandbox* (Codex en Windows) sin dar permisos al usuario del sistema. En un PowerShell **como administrador**: `takeown /f "<carpeta>" /r /d S` y `icacls "<carpeta>" /reset /t` |
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

Reglas del proyecto y arquitectura: [`AGENTS.md`](../AGENTS.md) y
[`ARCHITECTURE.md`](ARCHITECTURE.md).
Contribuir: [`CONTRIBUTING.md`](../CONTRIBUTING.md).
