<p align="center">
  <img src="docs/brand/mark.svg" alt="" width="80" height="80">
</p>

<h1 align="center">CandidatAI</h1>

<p align="center">
  La búsqueda de empleo entera, en una app: la persona decide, su agente de IA lee y escribe, y nada se envía sin confirmación.
</p>

<p align="center">
  <a href="README.md">English</a> · <b>Español</b>
</p>

<p align="center">
  <a href="#windows"><img alt="Instalar en Windows" src="https://img.shields.io/badge/Instalar-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white"></a>
  <a href="#macos-y-linux"><img alt="Instalar en macOS o Linux" src="https://img.shields.io/badge/Instalar-macOS%20%C2%B7%20Linux-333333?style=for-the-badge&logo=linux&logoColor=white"></a>
  <a href="#docker"><img alt="Arrancar con Docker" src="https://img.shields.io/badge/Arrancar-Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://github.com/DiegoPrieto23/candidatai/releases/latest"><img alt="Última versión" src="https://img.shields.io/github/v/release/DiegoPrieto23/candidatai?color=0F6E69"></a>
  <a href="https://github.com/DiegoPrieto23/candidatai/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/DiegoPrieto23/candidatai/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="LICENSE"><img alt="Licencia" src="https://img.shields.io/github/license/DiegoPrieto23/candidatai?color=0F6E69"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-UI-149ECA?logo=react&logoColor=white">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-server-555555">
</p>

CandidatAI lleva de una oferta nueva a una oferta de trabajo: reúne ofertas de muchas fuentes,
indica cuánto encaja cada una con el perfil, escribe un CV y una carta a medida sin inventar nada,
rellena el formulario de la candidatura y espera a que se confirme el envío, y después sigue cada
proceso con sus entrevistas, respuestas y seguimientos.

Es para quien busca trabajo y quiere tener toda la búsqueda en un sitio, con sus datos en su propio
equipo. Lo que hay que leer y escribir lo hace un agente de IA que ya se use (Claude Code, Codex,
Antigravity CLI…), que la app no incluye. Es un proyecto joven, con una sola persona detrás, y lo más
probado es Windows 11 con Claude Code: ver las [limitaciones conocidas](#limitaciones-conocidas).

**Para empezar:** [instalación](#instalación) · [Primeros pasos](docs/EMPEZAR.md), sin necesidad de
perfil técnico.

## Demo

<p align="center">
  <img src="docs/img/es/anim/tour.webp" alt="Un recorrido por la app: Inicio, aprobar y descartar ofertas en la revisión rápida, un CV verificado que cambia de plantilla y de color, el formulario de la candidatura rellenado y parado en la confirmación, una tarjeta arrastrada en el tablero de Procesos y los resultados" width="100%">
  <br><sub>Todo lo que se ve es la demo: una candidata, empresas y ofertas inventadas. El trabajo del
  agente (leer las ofertas, escribir el CV) ya viene hecho en ella; con un agente de verdad, cada
  paso tarda de unos segundos a unos minutos. Se reproduce a 1,5× la velocidad real.</sub>
</p>

## Funcionalidades

- **Ofertas de muchas fuentes:** un enlace o el texto pegado, empresas con portal propio seguidas por
  sus portales de empleo públicos (Greenhouse, Lever, Ashby y cinco más), las alertas de empleo por
  correo, la página abierta enviada con un botón del navegador o el agente buscando en los portales
  elegidos. Las repetidas se juntan.
- **Detecta el texto dirigido a una IA:** el texto de una oferta es solo un dato. Las instrucciones
  escondidas se detectan y se avisan, y esa oferta nunca sale como encaje fuerte.
- **Un encaje explicado para cada oferta:** filtros duros, un encaje de 0 a 100 que indica de dónde
  sale cada punto y la valoración razonada del agente. Se aprueba o se descarta con el teclado.
- **Un CV a medida para cada oferta:** el agente lo escribe con el perfil, la app lo genera con la
  plantilla, la foto y el color elegidos, y un verificador aparte lo revisa. Los cambios se piden con
  palabras normales, se editan a mano o se vuelve a cualquier versión.
- **El diseño de un CV propio:** cualquier CV (Word, PDF, una imagen, Canva) se importa como
  plantilla, y plantilla, color o secciones cambian en segundos sin usar el agente.
- **No inventa experiencia:** cada línea del CV tiene que apuntar a una evidencia del perfil, o el
  código la rechaza.
- **Cartas y respuestas de formulario** a juego con el CV y la oferta, con indicaciones propias.
- **Candidatura asistida:** la app rellena formularios de Greenhouse, Lever, Ashby o genéricos y se
  para ante captchas e inicios de sesión.
- **Nada sale sin confirmación:** enviar necesita un clic manual, candidatura a candidatura. Mensajes
  y correos son borradores que se envían a mano.
- **Todos los procesos en un tablero:** un tablero que solo se mueve con pasos registrados, un
  calendario, recordatorios de seguimiento y las respuestas de las empresas leídas del buzón y
  ordenadas para aceptarlas.
- **Entrevistas y ofertas:** una guía de preparación en PDF con un plan por días, simulacros,
  repasos, investigación de la empresa con fuentes y ofertas comparadas con el sueldo mínimo sin que
  el agente lo vea nunca.
- **Resultados que indican qué funciona:** por qué canal responden más y antes, dónde se paró cada
  candidatura, por fuente, puesto, plantilla y referencia, y si el encaje acertó con lo que pasó de
  verdad.

**Todas las funcionalidades, página a página y skill a skill:** [`docs/FUNCIONALIDADES.md`](docs/FUNCIONALIDADES.md).

## Capturas

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/es/dark/home.webp">
  <img src="docs/img/es/home.webp" alt="Inicio: lo pendiente de hoy para la persona y para el agente, los próximos siete días, el recorrido de las ofertas y cómo van las candidaturas" width="100%">
</picture>
<p align="center"><sub>Inicio muestra lo pendiente, para la persona y para el agente, y el siguiente paso.</sub></p>

<table>
  <tr>
    <td width="50%"><img src="docs/img/es/triage.webp" alt="Revisión rápida: la lista de ofertas por encaje y, al lado, la elegida con el desglose de su encaje y sus skills" width="100%"><br><sub>Ofertas por encaje, decididas con una tecla.</sub></td>
    <td width="50%"><img src="docs/img/es/job-cv.webp" alt="El CV de una oferta: verificado, junto a un panel para pedir cambios, editar el texto o cambiar el diseño" width="100%"><br><sub>Un CV verificado que se corrige pidiéndolo con palabras o se rediseña en segundos.</sub></td>
  </tr>
  <tr>
    <td><img src="docs/img/es/processes.webp" alt="Tablero de procesos: aprobadas, CV listo, enviadas, en proceso y cerradas, con fechas de entrevista y seguimientos pendientes" width="100%"><br><sub>Todas las candidaturas en un tablero, movido por pasos registrados.</sub></td>
    <td><img src="docs/img/es/funnel.webp" alt="Resultados: cuánto tardan las empresas en responder y, por canal y por fuente, la tasa y el tiempo de respuesta" width="100%"><br><sub>Qué canales consiguen respuesta, y en cuánto tiempo.</sub></td>
  </tr>
  <tr>
    <td><img src="docs/img/es/replies.webp" alt="Respuestas de las empresas leídas del buzón, cada una con un paso propuesto que aceptar" width="100%"><br><sub>Los correos de las empresas, ordenados para aceptarlos.</sub></td>
    <td><img src="docs/img/es/calendar.webp" alt="Calendario del mes con entrevistas, pruebas técnicas y el plazo de una oferta" width="100%"><br><sub>Entrevistas, pruebas y plazos en un calendario.</sub></td>
  </tr>
  <tr>
    <td><img src="docs/img/es/search.webp" alt="Buscar ofertas: puestos, lugares, modalidad y nivel como etiquetas, y los portales que recorrerá el agente" width="100%"><br><sub>Qué se busca y en qué portales lo busca el agente.</sub></td>
    <td><img src="docs/img/es/profile-experience.webp" alt="Mi perfil: la experiencia por empresa y las skills con su nivel privado, editadas por bloques" width="100%"><br><sub>El perfil, la única fuente de lo que va en un CV.</sub></td>
  </tr>
</table>

<sub>Todas las capturas usan los datos inventados de la demo. Las animaciones cortas de cada funcionalidad están en
[`docs/FUNCIONALIDADES.md`](docs/FUNCIONALIDADES.md).</sub>

## Instalación

1. **Lo que hace falta.** Un ordenador con Windows, macOS o Linux; sin Python, Node ni permisos de
   administrador, porque el instalador trae lo necesario. Y un agente de IA: Claude Code, Codex o
   Antigravity CLI con una suscripción que quizá ya se pague (Claude, ChatGPT o Google AI Pro),
   Antigravity CLI también con una cuenta gratuita de Google, o un modelo local. **La app nunca
   llama a una IA por su cuenta.** Cuál elegir y cuánto cuesta cada uno: [Primeros pasos](docs/EMPEZAR.md).
2. **Instalarla.**
   - <a id="windows"></a>**Windows** (Windows 11), en PowerShell:

     ```powershell
     iwr -useb https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.ps1 -OutFile $env:TEMP\cai-install.ps1
     powershell -ExecutionPolicy Bypass -File $env:TEMP\cai-install.ps1
     ```

   - <a id="macos-y-linux"></a>**macOS y Linux**, en una terminal (sin `sudo`):

     ```bash
     curl -fsSL https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.sh | bash
     ```

   - <a id="docker"></a>**Docker** (opcional): desde una copia del repositorio, `docker compose up -d --build`. El
     agente se queda fuera del contenedor, con algunos límites: ver
     [Con Docker](docs/GUIA.md#con-docker-opcional).

   Los instaladores descargan la [última versión](https://github.com/DiegoPrieto23/candidatai/releases/latest),
   **comprueban su suma SHA-256** y crean un acceso directo «CandidatAI». Para actualizar, se vuelven
   a ejecutar: los datos no se tocan. Para ver antes qué harían, se añade `-WhatIf` a la segunda
   línea de Windows o se usa `| bash -s -- --dry-run`.
3. **Abrirla.** Con el acceso directo «CandidatAI»: en el escritorio y en el menú Inicio en Windows,
   en `~/Applications` en macOS (Spotlight también lo encuentra) y en el menú de aplicaciones en
   Linux. Una ventana de terminal arranca la app y el navegador se abre en `http://127.0.0.1:8000`,
   que es el propio equipo. Esa ventana debe quedarse abierta mientras se usa la app. Desde una
   terminal es `uv run cai start` en la carpeta `backend` de la app:

   ```bash
   cd $env:LOCALAPPDATA\CandidatAI\app\backend               # Windows (PowerShell)
   cd ~/"Library/Application Support/CandidatAI/app/backend"   # macOS
   cd ~/.local/share/candidatai/app/backend                    # Linux
   uv run cai start
   ```

   `uv run cai --help` lista los demás comandos: `cai doctor` comprueba que no falte nada. Con
   Docker, la app arranca con el contenedor y se abre en esa misma dirección.
4. **Probar la demo y empezar con datos reales.** `uv run cai demo seed` carga una búsqueda
   inventada para curiosear. Después, se crea el perfil a partir del CV y se conecta el agente:
   [Primeros pasos](docs/EMPEZAR.md) paso a paso, o la [guía de uso](docs/GUIA.md).

## Documentación

- [Primeros pasos](docs/EMPEZAR.md): lo que hace falta y cómo instalarla, sin perfil técnico.
- [Guía de uso](docs/GUIA.md): cada página y cómo usarla en el día a día.
- [Funcionalidades](docs/FUNCIONALIDADES.md): todo lo que hace la app, página a página y skill a
  skill.
- [Políticas](docs/POLICIES.md): las reglas de veracidad, privacidad y candidaturas.
- [Agentes](docs/AGENTS_COMPAT.md): qué agentes funcionan y cuánto se han probado.
- [Todos los documentos](docs/README.md), agrupados. Los documentos técnicos están en español; las
  guías existen en los dos idiomas.
- [Registro de cambios](CHANGELOG.md): qué cambió en cada versión.

## Cómo funciona

<p align="center">
  <img src="docs/img/como-funciona-es.svg" alt="Cómo funciona en ocho pasos: entran ofertas, el agente las extrae y valora, la persona las revisa, el agente escribe el CV, la app lo verifica y lo genera, la app rellena el formulario y solo la persona lo envía, la app sigue el proceso y el agente prepara las entrevistas" width="100%">
</p>

Cada color es quién hace el paso: **la persona** decide, **el agente** razona y **la app** guarda,
comprueba y automatiza. El agente trabaja con una interfaz propia (herramientas MCP y una CLI
`cai … --json` equivalente) y solo puede rellenar esquemas estrictos que el código valida. Los
skills, como `generate-cv 42` o `process-jobs`, se lanzan desde el agente o con un botón de la app.
Más en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Por qué CandidatAI

Hay dos proyectos abiertos muy conocidos que también usan un agente de IA para buscar empleo, y los
dos han inspirado este: [AI Job Search](https://github.com/ai-job-search-dev/ai-job-search) y
[career-ops](https://github.com/career-ops-hq/career-ops). CandidatAI se diferencia en tres cosas: es
una **app** que se instala como cualquier programa y sirve sin abrir el agente; sus reglas (ninguna
línea del CV sin respaldo, nada se envía sin confirmación, el texto de una oferta es solo un dato)
**las comprueba el código**, sea cual sea el agente; y cubre la búsqueda entera, **hasta la oferta**,
en un solo sitio.

**Lo que ellos hacen mejor, hoy:** career-ops funciona con más agentes y modelos, cubre más fuentes
de ofertas y más países y está mucho más rodado; AI Job Search es más sencillo (un fork y `/setup`)
y tiene detrás una historia real de contratación. Los dos tienen comunidades grandes que este
proyecto aún no tiene.

<details>
<summary><b>Uno al lado del otro</b> (comprobado el 6 de noviembre de 2026)</summary>
<br>

| | CandidatAI | AI Job Search | career-ops |
|---|---|---|---|
| Qué es | Una **app** con UI web, base de datos y un proceso en segundo plano | Instrucciones y comandos para Claude Code sobre ficheros | Un agente con muchos modos y scripts de Node sobre ficheros, un panel de terminal y una UI web |
| Instalar | Un comando, un acceso directo, nada instalado antes | Fork, y después Claude Code, Python, Bun y LaTeX | `npx … init` con Node instalado |
| Sin el agente abierto | Revisar ofertas, tablero, calendario, resultados, perfil, diseños de CV | Nada | Buscar ofertas, el panel y la UI web |
| Reglas | **Las comprueba el código**: una línea del CV sin evidencia en el perfil se rechaza; enviar necesita un clic manual | Instrucciones, permisos mínimos y un filtro de inyección en código | Instrucciones, y comprobaciones de hechos y de redacción del CV en código |
| Agentes | 5 configurados; Claude Code probado del todo | Claude Code | 12 CLIs, modelos gratuitos y locales |
| Comunidad | Una persona, recién publicado | ~70k estrellas, ~90 contribuidores, la búsqueda real del autor | ~81k estrellas, ~470 contribuidores, Discord, muchas historias de éxito |

La comparativa completa, función a función y con sus fuentes, está en
[`docs/COMPARATIVA.md`](docs/COMPARATIVA.md).
</details>

## Limitaciones conocidas

- **Solo para ordenador.** La app está hecha para la pantalla de un ordenador; no está pensada para
  el móvil.
- **Una persona, un equipo.** Funciona en el propio equipo, en `127.0.0.1`, sin cuentas ni
  sincronización entre dispositivos.
- **Hace falta un agente de IA.** Sin él se pueden revisar ofertas, seguir los procesos y cambiar el
  diseño de los CVs, pero leer las ofertas y escribir CVs, cartas o guías de entrevista necesita un
  agente, que la app no incluye.
- **Lo que se ha probado de verdad:** Windows 11 es lo más probado, también una instalación limpia
  desde la release; macOS y Linux tienen instalador y pasan los tests en la CI, pero no se han
  instalado a mano desde una release. Claude Code está probado de principio a fin, Codex con una
  oferta y Antigravity CLI en parte; OpenCode solo se ha probado con un modelo local pequeño, que no
  terminó la prueba, y Qwen Code está configurado, pero sin probar. El detalle, en
  [`docs/AGENTS_COMPAT.md`](docs/AGENTS_COMPAT.md).
- **Solo en español e inglés**, en la app y en las guías.
- **Sin leer portales que no tienen API** y sin candidaturas automáticas en LinkedIn, a propósito:
  esas ofertas entran por las alertas de correo, el botón del navegador o el agente buscando con el
  navegador.

## Rendimiento

Medido el 24 de noviembre de 2026 en un portátil con un AMD Ryzen 7 5700U, 16 GB de RAM y sin tarjeta
gráfica dedicada, con Windows 11 y con la app ya abierta una vez antes (mediana de tres vueltas, salvo la memoria):

| Qué | Tiempo o tamaño |
|---|---|
| Arrancar la app, hasta que responde / hasta que se ve Inicio | 4,0 s / 4,8 s |
| Memoria de la app entera, en reposo / tras recorrer todas las páginas | ≈ 335 MB / ≈ 375 MB |
| Un CV con otro diseño, a PDF: plantillas de Word (LibreOffice) / plantillas HTML | 12,7 s / 4,5 s |
| Inicio, primera carga / recarga, con la demo (65 ofertas) | 0,25 s / 0,13 s |
| Inicio, primera carga / recarga, con 10 veces más ofertas (650) | 0,28 s / 0,11 s |
| Bandeja de ofertas, primera carga / recarga, con la demo | 0,52 s / 0,31 s |
| Bandeja de ofertas, primera carga / recarga, con 650 ofertas | 0,53 s / 0,31 s |

No incluye el trabajo del agente (leer una oferta, escribir un CV): depende del agente y de su
modelo. Como referencia, Claude Code tardó 8,5 minutos en leer, valorar y escribir un CV verificado
para cinco ofertas en la [matriz de agentes](evals/compat/REPORT.md).

El eval de matching (80 casos inventados, sin embeddings): precision **0,88**, recall **0,95**,
F1 **0,92** con el umbral de score por defecto ([`evals/REPORT.md`](evals/REPORT.md)).

## Seguridad

Nada sale del equipo sin confirmación, y el texto de las ofertas o de los correos nunca se sigue
como instrucciones. Para avisar de una vulnerabilidad, ver [`SECURITY.md`](SECURITY.md); las reglas
que aplica la app están en [`docs/POLICIES.md`](docs/POLICIES.md).

## Desarrollo

Para contribuir: [`CONTRIBUTING.md`](CONTRIBUTING.md) y el
[apartado de desarrollo de la guía](docs/GUIA.md#15-desarrollo).

## Licencia

[MIT](LICENSE) © 2026 Diego Prieto.

Inspirado en [ackyer/job-search-agent-template](https://github.com/ackyer/job-search-agent-template)
(MIT) y en ideas de [AI Job Search](https://github.com/ai-job-search-dev/ai-job-search) y
[career-ops](https://github.com/career-ops-hq/career-ops) (los dos MIT). Sin relación con
Anthropic, OpenAI, Google, LinkedIn ni ningún portal de empleo.
