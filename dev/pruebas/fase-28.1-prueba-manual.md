# Fase 28.1 · Prueba manual: release `v0.1.0` e instaladores

Objetivo: comprobar que la primera release existe, que los instaladores la descargan, verifican su
suma SHA-256 e instalan desde cero en Windows, Linux y macOS, y que Docker arranca.

## Ya hecho por el agente (2026-10-23)

- [x] Empaquetado como en `release.yml`, en local (contenedor Linux): el zip lleva
  `frontend/dist`, `install.sh` sale `-rwxr-xr-x` y `sha256sum -c` da OK.
- [x] **Windows, desde ese zip con su `.sha256` al lado**, en una carpeta temporal y sin accesos
  directos: «Suma SHA-256 comprobada», `uv sync`, Chromium, base de datos y `cai doctor` → «Todo
  listo».
- [x] Reinstalar sobre lo anterior conserva `data/` (un fichero propio sigue ahí).
- [x] Con una suma alterada: «no coincide con la publicada», sale con error y la app instalada
  queda como estaba.
- [x] Tests de `install.sh` en Linux (contenedor): suma buena, mala, sin suma y `--skip-checksum`.
- [x] (2026-10-24) La demo de una app instalada se crea en `CandidatAI\data-demo` y sobrevive a una
  actualización (antes iba en `app\data-demo` y se perdía).

## Por hacer (con la release publicada)

Antes: la rama fusionada en `main` y la etiqueta `v0.1.0` empujada (el workflow `Release` la
publica). Comprueba que <https://github.com/DiegoPrieto23/candidatai/releases/latest/download/candidatai.zip>
y el mismo enlace con `.sha256` descargan.

### 1. Windows 11 limpio (Windows Sandbox)

Windows Sandbox: «Activar o desactivar características de Windows» → «Espacio aislado de
Windows» (necesita Windows Pro; en Home, una máquina virtual con VirtualBox: paso a paso en
[`maquina-virtual-windows.md`](maquina-virtual-windows.md), que trae también los comandos exactos de
esta prueba). Dentro no hay Python, Node ni uv.

1. Abre PowerShell y pega la línea de instalación del README.
2. Apunta qué dice **SmartScreen / Defender** (captura si sale un aviso: la 28.4 lo explica en la
   guía).
3. Debe decir «Suma SHA-256 comprobada» en el paso 2 y terminar en «Listo».
4. Abre el acceso directo: se abre el navegador en `http://127.0.0.1:8000`.
5. Siembra la demo (`uv run --directory "$env:LOCALAPPDATA\CandidatAI\app\backend" cai demo seed`)
   y recorre Inicio, Bandeja y una ficha con CV.
6. `cai doctor` desde la misma carpeta.

**Resultado (2026-10-25, hecho por el agente en VirtualBox):** ✅ con la release `v0.1.0` real, en
Windows 11 Home 10.0.26300 recién instalado (es-ES), usuario sin uv, Python ni Node. El agente lanzó
las dos líneas del README en una ventana de PowerShell del escritorio del usuario y leyó la salida.

- [x] SmartScreen / Defender (protección en tiempo real activa, firmas al día): **ningún aviso**.
  Con `iwr` el script no lleva la marca «descargado de internet»; queda por ver el caso de
  descargarlo con el navegador (opcional en `maquina-virtual-windows.md`).
- [x] «Suma SHA-256 comprobada.» y «Listo.» (código de salida 0), con red solo IPv4 (ver abajo).
- [x] El acceso directo abre la ventana «CandidatAI en marcha: http://127.0.0.1:8000» y Edge en esa
  dirección.
- [x] `cai demo seed` crea la demo en `CandidatAI\data-demo` (60 ofertas, 281 eventos, 2 CVs en PDF
  con Chromium); con la línea que imprime, la app arranca en modo demo. Inicio, Bandeja y la ficha
  #1 (CV listo) se ven bien; el PDF del CV se sirve (`/renders/1/pdf`, 80 KB).
- [x] `cai doctor` → «Todo listo», con los avisos esperables: sin LibreOffice, sin agentes, sin el
  extra de embeddings.

Encontrado por el camino (para la 28.4 o una fase de arreglos):

- **Con IPv6 roto, el paso 4 falla:** «No se pudo instalar Chromium (1).» y no llega a «Listo».
  La red NAT de VirtualBox anuncia IPv6 pero no lo enruta; la descarga de Playwright
  (`cdn.playwright.dev` → `storage.googleapis.com`) se queda esperando por IPv6 y agota sus 30 s
  (PyPI, GitHub y uv sí funcionan). Forzar IPv4 en Node no lo arregla. Raro en un PC real, pero el
  mensaje no da ninguna pista: el instalador podría decir que es un problema de red y que basta
  con volver a ejecutarlo, o reintentar.
- **`cai doctor` se contradice:** «Conversión a PDF: sin LibreOffice ni Word: no se pueden generar
  los PDF de los CVs» como aviso, cuando dos líneas más abajo «Motor html (Chromium)» genera el PDF
  y la demo ya trae 2 CVs en PDF. Solo afecta a las plantillas `.docx`; el aviso debería decirlo.
- **El instalador de uv habla en inglés** («To add C:\Users\…\.local\bin to your PATH, either
  restart your shell…»). El nuestro ya se ocupa del PATH; la guía puede decir que se ignore.
- **`uv sync` instala también el grupo `dev`** (ruff y lo de los tests) en la app de quien la usa:
  `uv sync --no-dev` en los instaladores ahorraría descarga y espacio.
- Edge sale la primera vez con su bienvenida encima de la página (gris); es de Edge, no de la app.

### 2. Linux (WSL2 Ubuntu o máquina virtual)

1. `curl -fsSL https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.sh | bash`
2. «Suma SHA-256 comprobada», «Listo» y la entrada en el menú de aplicaciones (en WSL, arranca
   con `~/.local/share/candidatai/candidatai-start`).
3. Demo y `cai doctor` como en Windows.

### 3. macOS

Sin Mac: la CI de `main` y de la etiqueta pasa la suite en `macos-latest` y el humo del
instalador desde la carpeta. La instalación desde la release real en un Mac queda pendiente hasta
tener uno (o lo hace quien lo pruebe primero).

### 4. Docker

`docker compose up -d --build` en una copia limpia de la etiqueta; `/status` responde y
`docker exec candidatai cai demo seed` siembra.

### 5. Actualizar sin perder datos

Para no publicar una `v0.1.1` de prueba: con la `v0.1.0` instalada, una oferta tuya dada de alta y
la demo sembrada, haz un zip con la prueba en seco del workflow (artefacto `candidatai-zip`, que
trae su `.sha256`) y reinstala con `-Source <ruta>\candidatai.zip` / `--source`. Tu oferta y la
demo (en `CandidatAI\data-demo`, junto a `data`) tienen que seguir ahí.

## Resultados

| Sistema | Instala | Suma | Primera apertura | Demo | `cai doctor` | Actualizar | Notas |
|---|---|---|---|---|---|---|---|
| Windows (local, zip de prueba) | ✅ | ✅ | — | — | ✅ | ✅ | sin accesos directos |
| Windows 11 limpio en VirtualBox (release) | ✅ | ✅ | ✅ | ✅ | ✅ | — | SmartScreen: ningún aviso (con `iwr`); con IPv6 roto falla Chromium |
| Linux / WSL (release) | | | | | | | |
| macOS (CI) | | | | | | | |
| Docker | | | | | | | |
