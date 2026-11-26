<#
.SYNOPSIS
  Instala (o actualiza) CandidatAI en Windows y crea un acceso directo para abrirla.

.DESCRIPTION
  1. Instala uv si no está (el instalador oficial de astral.sh). uv trae Python 3.12 por su cuenta.
  2. Descarga la última release de CandidatAI (la UI ya va compilada: no hace falta Node) y
     comprueba su suma SHA-256 (candidatai.zip.sha256, publicada con ella) antes de abrirla.
  3. La deja en <InstallDir>\app. Tus datos van en <InstallDir>\data y nunca se tocan al actualizar;
     tu .env de la app tampoco (solo se fija CAI_DATA_DIR).
  4. Prepara el entorno (uv sync), el Chromium de Playwright (PDF de los CVs) y la base de datos.
  5. Crea el acceso directo «CandidatAI» en el escritorio y en el menú Inicio. Al abrirlo se
     arranca todo (`cai start`) y se abre el navegador; para cerrarla, cierra esa ventana.
  6. Abre la app con ese acceso directo (salvo con -NoLaunch o -NoShortcuts).

  Habla en el idioma de -Lang (es o en); sin él, en el de Windows (español o, si no, inglés).
  No pide permisos de administrador. Con -WhatIf solo explica lo que haría, sin cambiar nada.

.EXAMPLE
  # Instalar o actualizar a la última versión (descarga este script y lo ejecuta). Una sola línea,
  # que se pega en Windows+R, en PowerShell o en cmd: sin $, que PowerShell sustituiría al pegarla.
  powershell -ExecutionPolicy Bypass -NoExit -Command "cd ([IO.Path]::GetTempPath()); iwr -useb https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.ps1 -OutFile cai-install.ps1; .\cai-install.ps1"

.EXAMPLE
  .\install.ps1 -WhatIf
  .\install.ps1 -Lang en                    # los mensajes, en inglés
  .\install.ps1 -Source .\candidatai.zip     # un zip local en vez de la última release
  .\install.ps1 -Source C:\ruta\al\repo      # o tu repositorio clonado, con la UI compilada
  .\install.ps1 -Uninstall                   # quita la app y los accesos directos; tus datos no
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  # Zip de la release (ruta local o URL), o una carpeta con el repositorio (con `frontend\dist`
  # compilado). Por defecto, la última release publicada.
  [string]$Source = "https://github.com/DiegoPrieto23/candidatai/releases/latest/download/candidatai.zip",
  [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "CandidatAI"),
  [switch]$Uninstall,
  # Con -Uninstall, borra también tus datos (pide confirmación).
  [switch]$RemoveData,
  # No crea los accesos directos (pruebas, instalaciones desatendidas).
  [switch]$NoShortcuts,
  # No comprueba la suma SHA-256 del zip (solo con una URL tuya que no publique <zip>.sha256).
  [switch]$SkipChecksum,
  # No abre la app al terminar (el actualizador la abre él).
  [switch]$NoLaunch,
  # Idioma de los mensajes: es o en. Sin él, el de Windows.
  [ValidateSet("es", "en")][string]$Lang
)

$ErrorActionPreference = "Stop"
# En PowerShell 7.3+, que un comando externo escriba en stderr no es un error (en la 5.1 ya no lo es).
$PSNativeCommandUseErrorActionPreference = $false

if (-not $Lang) {
  $Lang = if ((Get-UICulture).TwoLetterISOLanguageName -eq "es") { "es" } else { "en" }
}
$texts = @{
  es = @{
    noDir = "Falta -InstallDir."
    badDir = "-InstallDir no puede ser {0}: usa una carpeta propia, p. ej. {1}."
    badSumFormat = "La suma de verificación ({0}) no tiene el formato esperado."
    badSum = "La suma SHA-256 del zip no coincide con la publicada: no se instala. Vuelve a intentarlo y, si se repite, avísanos en el repositorio."
    sumOk = "Suma SHA-256 comprobada."
    uninstalling = "Desinstalando CandidatAI de {0}"
    notOursUninstall = "{0} no parece una instalación de CandidatAI: no se borra nada."
    otherShortcut = "{0} abre otra instalación de CandidatAI: no se borra."
    doRemoveShortcut = "Borrar el acceso directo"
    doRemoveApp = "Borrar la app"
    dataNotOurs = "{0} no parece una instalación de CandidatAI: {1} no se borra."
    confirmData = "Se borrarán tus datos de {0} (perfil, ofertas, CVs). No se puede deshacer."
    confirmDataTitle = "¿Borrar tus datos?"
    doRemoveData = "Borrar tus datos"
    dataKept = "Tus datos se quedan en {0} (bórralos a mano o usa -Uninstall -RemoveData)."
    done = "Listo."
    title = "CandidatAI · instalación en {0}"
    step1 = "1/5 · uv (gestor de Python)"
    uvFound = "Ya está: {0}"
    doUv = "Instalar con el instalador oficial (astral.sh)"
    step2 = "2/5 · Descargar CandidatAI"
    noUi = "En {0} falta la UI compilada: ejecuta antes 'cd frontend; pnpm install; pnpm build'."
    localFolder = "Carpeta local: {0}"
    localZip = "Zip local: {0}"
    noCheck = "Sin comprobar la suma (-SkipChecksum)."
    noSumFile1 = "No hay {0}.sha256 al lado: no se comprueba la suma. Si lo bajaste de"
    noSumFile2 = "la página de releases, descarga también su .sha256 a la misma carpeta."
    doDownloadNoCheck = "Descargar sin comprobar la suma (-SkipChecksum)"
    doDownload = "Descargar y comprobar su suma SHA-256"
    noSumDownload = "No se pudo descargar {0}.sha256 para comprobar el zip. Si la URL es tuya y no la publica, usa -SkipChecksum."
    step3 = "3/5 · Copiar la app"
    doInstall = "Instalar (o sustituir) la app; tus datos de {0} no se tocan"
    notOursInstall = "{0} existe y no es una instalación de CandidatAI: elige otra carpeta con -InstallDir."
    copyFailed = "No se pudo copiar {0} (robocopy {1})."
    badZip = "El zip no tiene la carpeta candidatai\: no parece una release de CandidatAI."
    notCandidatai = "Lo descargado no parece CandidatAI (falta backend\pyproject.toml)."
    appOpen = "No se puede sustituir la app: ¿está CandidatAI abierta? Cierra su ventana y vuelve a ejecutar el instalador."
    installed = "App en {0}; datos en {1}"
    step4 = "4/5 · Preparar el entorno (puede tardar unos minutos la primera vez)"
    doPrepare = "uv sync, Chromium de Playwright y base de datos"
    syncFailed = "uv sync ha fallado ({0})."
    compileFailed = "No se pudo compilar la app ({0})."
    chromiumFailed = "No se pudo instalar Chromium ({0})."
    dbFailed = "No se pudo preparar la base de datos ({0})."
    step5 = "5/5 · Acceso directo"
    noShortcuts = "Sin accesos directos (-NoShortcuts)."
    doShortcut = "Crear el acceso directo «CandidatAI»"
    shortcutTip = "Abre CandidatAI (cierra la ventana para pararla)"
    doLaunch = "Abrir CandidatAI"
    finished = "Listo. CandidatAI se está abriendo en el navegador."
    finishedNoLaunch = "Listo. Abre «CandidatAI» desde el escritorio o el menú Inicio."
    window = "Se abre una ventana: déjala abierta mientras la uses y ciérrala para pararla. La próxima vez, ábrela desde el acceso directo «CandidatAI» del escritorio o del menú Inicio."
    windowNoLaunch = "Se abrirá una ventana (déjala abierta mientras la uses) y el navegador en http://127.0.0.1:8000."
    update = "Para actualizar: el aviso de Inicio de la app (botón «Actualizar ahora») o vuelve a ejecutar este instalador; tus datos no se tocan."
    agent = "Para conectar tu agente de IA, mira la guía: https://github.com/DiegoPrieto23/candidatai/blob/main/docs/GUIA.md"
  }
  en = @{
    noDir = "-InstallDir is missing."
    badDir = "-InstallDir cannot be {0}: use a folder of its own, e.g. {1}."
    badSumFormat = "The checksum file ({0}) does not have the expected format."
    badSum = "The SHA-256 checksum of the zip does not match the published one: nothing is installed. Try again and, if it happens again, let us know in the repository."
    sumOk = "SHA-256 checksum verified."
    uninstalling = "Uninstalling CandidatAI from {0}"
    notOursUninstall = "{0} does not look like a CandidatAI installation: nothing is removed."
    otherShortcut = "{0} opens another CandidatAI installation: it is not removed."
    doRemoveShortcut = "Remove the shortcut"
    doRemoveApp = "Remove the app"
    dataNotOurs = "{0} does not look like a CandidatAI installation: {1} is not removed."
    confirmData = "Your data in {0} (profile, jobs, CVs) will be removed. This cannot be undone."
    confirmDataTitle = "Remove your data?"
    doRemoveData = "Remove your data"
    dataKept = "Your data stays in {0} (remove it by hand or use -Uninstall -RemoveData)."
    done = "Done."
    title = "CandidatAI · installing in {0}"
    step1 = "1/5 · uv (Python manager)"
    uvFound = "Already installed: {0}"
    doUv = "Install with the official installer (astral.sh)"
    step2 = "2/5 · Download CandidatAI"
    noUi = "The built UI is missing in {0}: run 'cd frontend; pnpm install; pnpm build' first."
    localFolder = "Local folder: {0}"
    localZip = "Local zip: {0}"
    noCheck = "Checksum not verified (-SkipChecksum)."
    noSumFile1 = "There is no {0}.sha256 next to it: the checksum is not verified. If you downloaded it"
    noSumFile2 = "from the releases page, download its .sha256 to the same folder too."
    doDownloadNoCheck = "Download without verifying the checksum (-SkipChecksum)"
    doDownload = "Download and verify its SHA-256 checksum"
    noSumDownload = "Could not download {0}.sha256 to verify the zip. If the URL is yours and does not publish one, use -SkipChecksum."
    step3 = "3/5 · Copy the app"
    doInstall = "Install (or replace) the app; your data in {0} is not touched"
    notOursInstall = "{0} exists and is not a CandidatAI installation: choose another folder with -InstallDir."
    copyFailed = "Could not copy {0} (robocopy {1})."
    badZip = "The zip has no candidatai\ folder: it does not look like a CandidatAI release."
    notCandidatai = "The download does not look like CandidatAI (backend\pyproject.toml is missing)."
    appOpen = "The app cannot be replaced: is CandidatAI open? Close its window and run the installer again."
    installed = "App in {0}; data in {1}"
    step4 = "4/5 · Prepare the environment (the first time it can take a few minutes)"
    doPrepare = "uv sync, Playwright Chromium and database"
    syncFailed = "uv sync failed ({0})."
    compileFailed = "Could not compile the app ({0})."
    chromiumFailed = "Could not install Chromium ({0})."
    dbFailed = "Could not prepare the database ({0})."
    step5 = "5/5 · Shortcut"
    noShortcuts = "No shortcuts (-NoShortcuts)."
    doShortcut = "Create the ""CandidatAI"" shortcut"
    shortcutTip = "Opens CandidatAI (close the window to stop it)"
    doLaunch = "Open CandidatAI"
    finished = "Done. CandidatAI is opening in your browser."
    finishedNoLaunch = "Done. Open ""CandidatAI"" from the desktop or the Start menu."
    window = "A window opens: keep it open while you use the app and close it to stop it. Next time, open it from the ""CandidatAI"" shortcut on the desktop or in the Start menu."
    windowNoLaunch = "A window will open (keep it open while you use it) and your browser at http://127.0.0.1:8000."
    update = "To update: the notice on the app's Home page (""Update now"" button) or run this installer again; your data is not touched."
    agent = "To connect your AI agent, see the guide: https://github.com/DiegoPrieto23/candidatai/blob/main/docs/GUIDE.md"
  }
}
$t = $texts[$Lang]

function Say([string]$Text) { Write-Host "  $Text" }
function Step([string]$Text) { Write-Host ""; Write-Host "» $Text" -ForegroundColor Cyan }

# --- Rutas: nunca se borra nada fuera de una instalación de CandidatAI ---------------------------
if ([string]::IsNullOrWhiteSpace($InstallDir)) { throw $t.noDir }
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$forbidden = @(
  [IO.Path]::GetPathRoot($InstallDir),
  [Environment]::GetFolderPath("UserProfile"),
  [Environment]::GetFolderPath("Desktop"),
  [Environment]::GetFolderPath("MyDocuments"),
  $env:LOCALAPPDATA, $env:APPDATA, $env:TEMP
) | Where-Object { $_ } | ForEach-Object { [IO.Path]::GetFullPath($_).TrimEnd('\') }
if ($forbidden -contains $InstallDir.TrimEnd('\')) {
  throw ($t.badDir -f $InstallDir, (Join-Path $env:LOCALAPPDATA 'CandidatAI'))
}
$AppDir = Join-Path $InstallDir "app"
$DataDir = Join-Path $InstallDir "data"
# Marca de una carpeta de instalación de CandidatAI (fase 26.2): sin ella ni una app de CandidatAI,
# -RemoveData no borra nada.
$Marker = Join-Path $InstallDir ".candidatai"
$Shortcuts = @(
  (Join-Path ([Environment]::GetFolderPath("Desktop")) "CandidatAI.lnk"),
  (Join-Path ([Environment]::GetFolderPath("Programs")) "CandidatAI.lnk")
)

# Comprueba el zip contra un fichero .sha256 con el formato de `sha256sum` («<suma>  candidatai.zip»).
function Assert-Checksum([string]$Zip, [string]$SumFile) {
  $expected = ("$(Get-Content $SumFile -TotalCount 1)".Trim() -split '\s+')[0].ToLowerInvariant()
  if ($expected -notmatch '^[0-9a-f]{64}$') {
    throw ($t.badSumFormat -f $SumFile)
  }
  # Con .NET y no Get-FileHash: en PowerShell 5.1, Get-FileHash respeta -WhatIf y no calcula nada.
  $sha = [Security.Cryptography.SHA256]::Create()
  $stream = [IO.File]::OpenRead($Zip)
  try { $actual = ([BitConverter]::ToString($sha.ComputeHash($stream)) -replace '-', '').ToLowerInvariant() }
  finally { $stream.Dispose(); $sha.Dispose() }
  if ($actual -ne $expected) {
    throw $t.badSum
  }
  Say $t.sumOk
}

function Test-CandidatAIApp([string]$Path) {
  # Una carpeta solo se sustituye o se borra si es una app de CandidatAI.
  $pyproject = Join-Path $Path "backend\pyproject.toml"
  return (Test-Path $pyproject) -and ((Get-Content $pyproject -Raw) -match 'name\s*=\s*"candidatai"')
}

function Test-OwnShortcut([string]$Path) {
  # Un acceso directo es de esta instalación si arranca desde su backend: desinstalar otra carpeta
  # (una copia de prueba, otra instalación) no borra los accesos de la tuya.
  $workingDir = (New-Object -ComObject WScript.Shell).CreateShortcut($Path).WorkingDirectory
  if ([string]::IsNullOrWhiteSpace($workingDir)) { return $false }
  $backend = Join-Path $AppDir "backend"
  return [IO.Path]::GetFullPath($workingDir).TrimEnd('\') -eq [IO.Path]::GetFullPath($backend).TrimEnd('\')
}

function Remove-Tree([string]$Path) {
  # Rutas largas (.venv) sin el límite de 260 caracteres.
  if (Test-Path $Path) { Remove-Item -LiteralPath "\\?\$Path" -Recurse -Force }
}

# --- Desinstalar ---------------------------------------------------------------------------------
if ($Uninstall) {
  Step ($t.uninstalling -f $InstallDir)
  # Primero se comprueba; después se borra.
  if ((Test-Path $AppDir) -and -not (Test-CandidatAIApp $AppDir)) {
    throw ($t.notOursUninstall -f $AppDir)
  }
  $owned = (Test-Path $Marker) -or (Test-CandidatAIApp $AppDir)
  foreach ($lnk in $Shortcuts) {
    if (-not (Test-Path $lnk)) { continue }
    if (-not (Test-OwnShortcut $lnk)) {
      Say ($t.otherShortcut -f $lnk)
    } elseif ($PSCmdlet.ShouldProcess($lnk, $t.doRemoveShortcut)) {
      Remove-Item $lnk -Force
    }
  }
  if (Test-Path $AppDir) {
    if ($PSCmdlet.ShouldProcess($AppDir, $t.doRemoveApp)) { Remove-Tree $AppDir }
  }
  if ($RemoveData -and (Test-Path $DataDir) -and -not $owned) {
    Say ($t.dataNotOurs -f $InstallDir, $DataDir)
  } elseif ($RemoveData -and (Test-Path $DataDir)) {
    if ($PSCmdlet.ShouldContinue(($t.confirmData -f $DataDir), $t.confirmDataTitle)) {
      if ($PSCmdlet.ShouldProcess($DataDir, $t.doRemoveData)) {
        Remove-Tree $DataDir
        Remove-Item $Marker -Force -ErrorAction SilentlyContinue
      }
    }
  } elseif (Test-Path $DataDir) {
    Say ($t.dataKept -f $DataDir)
  }
  Say $t.done
  return
}

Write-Host ($t.title -f $InstallDir) -ForegroundColor Green

# --- 1. uv -------------------------------------------------------------------------------------
Step $t.step1
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
  Say ($t.uvFound -f $uv.Source)
} elseif ($PSCmdlet.ShouldProcess("uv", $t.doUv)) {
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
  $uv = Get-Command uv -ErrorAction Stop
}

# --- 2. Descargar ------------------------------------------------------------------------------
Step $t.step2
$zip = $null
$folder = $null
$downloaded = $false
if (Test-Path $Source -PathType Container) {
  $folder = (Resolve-Path $Source).Path
  if (-not (Test-Path (Join-Path $folder "frontend\dist\index.html"))) {
    throw ($t.noUi -f $folder)
  }
  Say ($t.localFolder -f $folder)
} elseif (Test-Path $Source) {
  $zip = (Resolve-Path $Source).Path
  Say ($t.localZip -f $zip)
  if ($SkipChecksum) {
    Say $t.noCheck
  } elseif (Test-Path "$zip.sha256") {
    Assert-Checksum $zip "$zip.sha256"
  } else {
    Say ($t.noSumFile1 -f (Split-Path $zip -Leaf))
    Say $t.noSumFile2
  }
} elseif ($PSCmdlet.ShouldProcess($Source, $(if ($SkipChecksum) { $t.doDownloadNoCheck } else { $t.doDownload }))) {
  $zip = Join-Path $env:TEMP "candidatai-$([guid]::NewGuid().ToString('N')).zip"
  $downloaded = $true
  try {
    Invoke-WebRequest -UseBasicParsing $Source -OutFile $zip
    if ($SkipChecksum) {
      Say $t.noCheck
    } else {
      $sum = "$zip.sha256"
      try {
        Invoke-WebRequest -UseBasicParsing "$Source.sha256" -OutFile $sum
      } catch {
        throw ($t.noSumDownload -f $Source)
      }
      try { Assert-Checksum $zip $sum } finally { Remove-Item $sum -Force -ErrorAction SilentlyContinue }
    }
  } catch {
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    throw
  }
}

# --- 3. Instalar la app ------------------------------------------------------------------------
Step $t.step3
if (($zip -or $folder) -and $PSCmdlet.ShouldProcess($AppDir, ($t.doInstall -f $DataDir))) {
  if ((Test-Path $AppDir) -and -not (Test-CandidatAIApp $AppDir)) {
    throw ($t.notOursInstall -f $AppDir)
  }
  New-Item -ItemType Directory -Force $InstallDir | Out-Null
  if (-not (Test-Path $Marker)) { New-Item -ItemType File $Marker | Out-Null }
  # La versión nueva se prepara aparte y solo sustituye a la anterior si está completa.
  $staging = Join-Path $InstallDir "app.new"
  $previous = Join-Path $InstallDir "app.old"
  $unzipped = $null
  try {
    Remove-Tree $staging
    if ($folder) {
      # Sin tus datos (las carpetas data* de la raíz), entornos, dependencias ni el historial de git.
      $skip = @(Get-ChildItem $folder -Directory | Where-Object { $_.Name -match '^data(-demo.*)?$' } |
        ForEach-Object { $_.FullName }) + @(".venv", "node_modules", ".git", "__pycache__")
      & robocopy $folder $staging /E /NFL /NDL /NJH /NJS /NP /XD @skip /XF .env | Out-Null
      if ($LASTEXITCODE -ge 8) { throw ($t.copyFailed -f $folder, $LASTEXITCODE) }
    } else {
      $unzipped = Join-Path $env:TEMP "candidatai-$([guid]::NewGuid().ToString('N'))"
      Expand-Archive $zip -DestinationPath $unzipped
      $root = Join-Path $unzipped "candidatai"
      if (-not (Test-Path $root)) {
        throw $t.badZip
      }
      Move-Item $root $staging
    }
    if (-not (Test-CandidatAIApp $staging)) {
      throw $t.notCandidatai
    }
    # Tu .env de la app se conserva; solo se fija dónde están tus datos.
    $envLines = @()
    $oldEnv = Join-Path $AppDir ".env"
    if (Test-Path $oldEnv) {
      $envLines = @(Get-Content $oldEnv | Where-Object { $_ -notmatch '^\s*(CAI|JH)_DATA_DIR\s*=' })
    }
    $envLines += "CAI_DATA_DIR=$DataDir"
    # Sin BOM: `Set-Content -Encoding utf8` lo añade en PowerShell 5.1 y rompería la primera variable.
    $utf8 = New-Object Text.UTF8Encoding $false
    [IO.File]::WriteAllText((Join-Path $staging ".env"), (($envLines -join "`n") + "`n"), $utf8)
    if (Test-Path $AppDir) {
      Remove-Tree $previous
      try {
        Rename-Item $AppDir $previous
      } catch {
        throw $t.appOpen
      }
    }
    Rename-Item $staging $AppDir
    Remove-Tree $previous
  } finally {
    Remove-Tree $staging
    if ($unzipped) { Remove-Tree $unzipped }
    if ($downloaded -and $zip) { Remove-Item $zip -Force -ErrorAction SilentlyContinue }
  }
  New-Item -ItemType Directory -Force $DataDir | Out-Null
  Say ($t.installed -f $AppDir, $DataDir)
}

# --- 4. Preparar ---------------------------------------------------------------------------------
Step $t.step4
$backend = Join-Path $AppDir "backend"
if ($PSCmdlet.ShouldProcess($backend, $t.doPrepare)) {
  # uv escribe su progreso en stderr: no es un error. Lo que cuenta es el código de salida.
  # Compilado al instalar: si no, Python lo compila al arrancar y la primera vez tarda el triple.
  & uv sync --directory $backend --compile-bytecode
  if ($LASTEXITCODE -ne 0) { throw ($t.syncFailed -f $LASTEXITCODE) }
  & uv run --directory $backend python -m compileall -q app
  if ($LASTEXITCODE -ne 0) { throw ($t.compileFailed -f $LASTEXITCODE) }
  & uv run --directory $backend playwright install chromium
  if ($LASTEXITCODE -ne 0) { throw ($t.chromiumFailed -f $LASTEXITCODE) }
  # La base de datos que se prepara es la de tus datos (la del .env de la app), aunque en esta
  # terminal hayas abierto la demo con $env:CAI_DATA_DIR. Al terminar, tu terminal queda como
  # estaba (fase 28.1).
  $saved = @{}
  foreach ($name in "CAI_DATA_DIR", "JH_DATA_DIR", "CAI_DB_URL", "JH_DB_URL") {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    [Environment]::SetEnvironmentVariable($name, $null, "Process")
  }
  try {
    & uv run --directory $backend cai db upgrade
    if ($LASTEXITCODE -ne 0) { throw ($t.dbFailed -f $LASTEXITCODE) }
  } finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], "Process") }
  }
}

# --- 5. Accesos directos -----------------------------------------------------------------------
Step $t.step5
if ($NoShortcuts) {
  Say $t.noShortcuts
} else {
  foreach ($lnk in $Shortcuts) {
    if ($PSCmdlet.ShouldProcess($lnk, $t.doShortcut)) {
      $shell = New-Object -ComObject WScript.Shell
      $shortcut = $shell.CreateShortcut($lnk)
      # Con cmd: si `cai start` falla, la ventana se queda abierta y enseña el error. Antes abre la
      # página «Arrancando CandidatAI…», que pasa sola a la app cuando responde: así se ve algo
      # nada más pulsar, sin esperar a que cargue Python (por eso `--no-browser`).
      $starting = Join-Path $AppDir "frontend\dist\starting.html"
      $shortcut.TargetPath = Join-Path $env:SystemRoot "System32\cmd.exe"
      $shortcut.Arguments = "/c `"start `"`" `"$starting`" & `"$((Get-Command uv).Source)`" run --directory `"$backend`" cai start --no-browser || pause`""
      $shortcut.WorkingDirectory = $backend
      $shortcut.IconLocation = Join-Path $AppDir "frontend\public\candidatai.ico"
      $shortcut.Description = $t.shortcutTip
      $shortcut.Save()
    }
  }
}

# --- Abrir la app ------------------------------------------------------------------------------
# Con el mismo acceso directo que se usará después: así se abre igual que siempre.
$launched = $false
if (-not $NoLaunch -and -not $NoShortcuts -and $PSCmdlet.ShouldProcess($Shortcuts[0], $t.doLaunch)) {
  Start-Process -FilePath $Shortcuts[0]
  $launched = $true
}

Write-Host ""
if ($launched) {
  Write-Host $t.finished -ForegroundColor Green
  Say $t.window
} else {
  Write-Host $t.finishedNoLaunch -ForegroundColor Green
  Say $t.windowNoLaunch
}
Say $t.update
Say $t.agent
