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

## Por hacer (con la release publicada)

Antes: la rama fusionada en `main` y la etiqueta `v0.1.0` empujada (el workflow `Release` la
publica). Comprueba que <https://github.com/DiegoPrieto23/candidatai/releases/latest/download/candidatai.zip>
y el mismo enlace con `.sha256` descargan.

### 1. Windows 11 limpio (Windows Sandbox)

Windows Sandbox: «Activar o desactivar características de Windows» → «Espacio aislado de
Windows» (necesita Windows Pro; en Home, una máquina virtual de Hyper-V o VirtualBox). Dentro no hay
Python, Node ni uv.

1. Abre PowerShell y pega la línea de instalación del README.
2. Apunta qué dice **SmartScreen / Defender** (captura si sale un aviso: la 28.4 lo explica en la
   guía).
3. Debe decir «Suma SHA-256 comprobada» en el paso 2 y terminar en «Listo».
4. Abre el acceso directo: se abre el navegador en `http://127.0.0.1:8000`.
5. Siembra la demo (`uv run --directory "$env:LOCALAPPDATA\CandidatAI\app\backend" cai demo seed`)
   y recorre Inicio, Bandeja y una ficha con CV.
6. `cai doctor` desde la misma carpeta.

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

Para no publicar una `v0.1.1` de prueba: con la `v0.1.0` instalada y la demo sembrada, haz un zip
con la prueba en seco del workflow (artefacto `candidatai-zip`, que trae su `.sha256`) y
reinstala con `-Source <ruta>\candidatai.zip` / `--source`. Los datos tienen que seguir ahí.

## Resultados

| Sistema | Instala | Suma | Primera apertura | Demo | `cai doctor` | Actualizar | Notas |
|---|---|---|---|---|---|---|---|
| Windows (local, zip de prueba) | ✅ | ✅ | — | — | ✅ | ✅ | sin accesos directos |
| Windows Sandbox (release) | | | | | | | SmartScreen: |
| Linux / WSL (release) | | | | | | | |
| macOS (CI) | | | | | | | |
| Docker | | | | | | | |
