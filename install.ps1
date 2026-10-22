<#
.SYNOPSIS
  Instala (o actualiza) CandidatAI en Windows y crea un acceso directo para abrirla.

.DESCRIPTION
  1. Instala uv si no está (el instalador oficial de astral.sh). uv trae Python 3.12 por su cuenta.
  2. Descarga la última release de CandidatAI (la UI ya va compilada: no hace falta Node).
  3. La deja en <InstallDir>\app. Tus datos van en <InstallDir>\data y nunca se tocan al actualizar;
     tu .env de la app tampoco (solo se fija CAI_DATA_DIR).
  4. Prepara el entorno (uv sync), el Chromium de Playwright (PDF de los CVs) y la base de datos.
  5. Crea el acceso directo «CandidatAI» en el escritorio y en el menú Inicio. Al abrirlo se
     arranca todo (`cai start`) y se abre el navegador; para cerrarla, cierra esa ventana.

  No pide permisos de administrador. Con -WhatIf solo explica lo que haría, sin cambiar nada.

.EXAMPLE
  # Instalar la última versión (descarga este script y lo ejecuta):
  iwr -useb https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.ps1 -OutFile $env:TEMP\cai-install.ps1; powershell -ExecutionPolicy Bypass -File $env:TEMP\cai-install.ps1

.EXAMPLE
  .\install.ps1 -WhatIf
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
  [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"
# En PowerShell 7.3+, que un comando externo escriba en stderr no es un error (en la 5.1 ya no lo es).
$PSNativeCommandUseErrorActionPreference = $false

function Say([string]$Text) { Write-Host "  $Text" }
function Step([string]$Text) { Write-Host ""; Write-Host "» $Text" -ForegroundColor Cyan }

# --- Rutas: nunca se borra nada fuera de una instalación de CandidatAI ---------------------------
if ([string]::IsNullOrWhiteSpace($InstallDir)) { throw "Falta -InstallDir." }
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$forbidden = @(
  [IO.Path]::GetPathRoot($InstallDir),
  [Environment]::GetFolderPath("UserProfile"),
  [Environment]::GetFolderPath("Desktop"),
  [Environment]::GetFolderPath("MyDocuments"),
  $env:LOCALAPPDATA, $env:APPDATA, $env:TEMP
) | Where-Object { $_ } | ForEach-Object { [IO.Path]::GetFullPath($_).TrimEnd('\') }
if ($forbidden -contains $InstallDir.TrimEnd('\')) {
  throw "-InstallDir no puede ser ${InstallDir}: usa una carpeta propia, p. ej. $(Join-Path $env:LOCALAPPDATA 'CandidatAI')."
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

function Test-CandidatAIApp([string]$Path) {
  # Una carpeta solo se sustituye o se borra si es una app de CandidatAI.
  $pyproject = Join-Path $Path "backend\pyproject.toml"
  return (Test-Path $pyproject) -and ((Get-Content $pyproject -Raw) -match 'name\s*=\s*"candidatai"')
}

function Remove-Tree([string]$Path) {
  # Rutas largas (.venv) sin el límite de 260 caracteres.
  if (Test-Path $Path) { Remove-Item -LiteralPath "\\?\$Path" -Recurse -Force }
}

# --- Desinstalar ---------------------------------------------------------------------------------
if ($Uninstall) {
  Step "Desinstalando CandidatAI de $InstallDir"
  # Primero se comprueba; después se borra.
  if ((Test-Path $AppDir) -and -not (Test-CandidatAIApp $AppDir)) {
    throw "$AppDir no parece una instalación de CandidatAI: no se borra nada."
  }
  $owned = (Test-Path $Marker) -or (Test-CandidatAIApp $AppDir)
  foreach ($lnk in $Shortcuts) {
    if ((Test-Path $lnk) -and $PSCmdlet.ShouldProcess($lnk, "Borrar el acceso directo")) {
      Remove-Item $lnk -Force
    }
  }
  if (Test-Path $AppDir) {
    if ($PSCmdlet.ShouldProcess($AppDir, "Borrar la app")) { Remove-Tree $AppDir }
  }
  if ($RemoveData -and (Test-Path $DataDir) -and -not $owned) {
    Say "$InstallDir no parece una instalación de CandidatAI: $DataDir no se borra."
  } elseif ($RemoveData -and (Test-Path $DataDir)) {
    if ($PSCmdlet.ShouldContinue("Se borrarán tus datos de $DataDir (perfil, ofertas, CVs). No se puede deshacer.", "¿Borrar tus datos?")) {
      if ($PSCmdlet.ShouldProcess($DataDir, "Borrar tus datos")) {
        Remove-Tree $DataDir
        Remove-Item $Marker -Force -ErrorAction SilentlyContinue
      }
    }
  } elseif (Test-Path $DataDir) {
    Say "Tus datos se quedan en $DataDir (bórralos a mano o usa -Uninstall -RemoveData)."
  }
  Say "Listo."
  return
}

Write-Host "CandidatAI · instalación en $InstallDir" -ForegroundColor Green

# --- 1. uv -------------------------------------------------------------------------------------
Step "1/5 · uv (gestor de Python)"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
  Say "Ya está: $($uv.Source)"
} elseif ($PSCmdlet.ShouldProcess("uv", "Instalar con el instalador oficial (astral.sh)")) {
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
  $uv = Get-Command uv -ErrorAction Stop
}

# --- 2. Descargar ------------------------------------------------------------------------------
Step "2/5 · Descargar CandidatAI"
$zip = $null
$folder = $null
$downloaded = $false
if (Test-Path $Source -PathType Container) {
  $folder = (Resolve-Path $Source).Path
  if (-not (Test-Path (Join-Path $folder "frontend\dist\index.html"))) {
    throw "En $folder falta la UI compilada: ejecuta antes 'cd frontend; pnpm install; pnpm build'."
  }
  Say "Carpeta local: $folder"
} elseif (Test-Path $Source) {
  $zip = (Resolve-Path $Source).Path
  Say "Zip local: $zip"
} elseif ($PSCmdlet.ShouldProcess($Source, "Descargar")) {
  $zip = Join-Path $env:TEMP "candidatai-$([guid]::NewGuid().ToString('N')).zip"
  Invoke-WebRequest -UseBasicParsing $Source -OutFile $zip
  $downloaded = $true
}

# --- 3. Instalar la app ------------------------------------------------------------------------
Step "3/5 · Copiar la app"
if (($zip -or $folder) -and $PSCmdlet.ShouldProcess($AppDir, "Instalar (o sustituir) la app; tus datos de $DataDir no se tocan")) {
  if ((Test-Path $AppDir) -and -not (Test-CandidatAIApp $AppDir)) {
    throw "$AppDir existe y no es una instalación de CandidatAI: elige otra carpeta con -InstallDir."
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
      if ($LASTEXITCODE -ge 8) { throw "No se pudo copiar $folder (robocopy $LASTEXITCODE)." }
    } else {
      $unzipped = Join-Path $env:TEMP "candidatai-$([guid]::NewGuid().ToString('N'))"
      Expand-Archive $zip -DestinationPath $unzipped
      $root = Join-Path $unzipped "candidatai"
      if (-not (Test-Path $root)) {
        throw "El zip no tiene la carpeta candidatai\: no parece una release de CandidatAI."
      }
      Move-Item $root $staging
    }
    if (-not (Test-CandidatAIApp $staging)) {
      throw "Lo descargado no parece CandidatAI (falta backend\pyproject.toml)."
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
        throw "No se puede sustituir la app: ¿está CandidatAI abierta? Cierra su ventana y vuelve a ejecutar el instalador."
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
  Say "App en $AppDir; datos en $DataDir"
}

# --- 4. Preparar ---------------------------------------------------------------------------------
Step "4/5 · Preparar el entorno (puede tardar unos minutos la primera vez)"
$backend = Join-Path $AppDir "backend"
if ($PSCmdlet.ShouldProcess($backend, "uv sync, Chromium de Playwright y base de datos")) {
  # uv escribe su progreso en stderr: no es un error. Lo que cuenta es el código de salida.
  & uv sync --directory $backend
  if ($LASTEXITCODE -ne 0) { throw "uv sync ha fallado ($LASTEXITCODE)." }
  & uv run --directory $backend playwright install chromium
  if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar Chromium ($LASTEXITCODE)." }
  & uv run --directory $backend cai db upgrade
  if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar la base de datos ($LASTEXITCODE)." }
}

# --- 5. Accesos directos -----------------------------------------------------------------------
Step "5/5 · Acceso directo"
if ($NoShortcuts) {
  Say "Sin accesos directos (-NoShortcuts)."
} else {
  foreach ($lnk in $Shortcuts) {
    if ($PSCmdlet.ShouldProcess($lnk, "Crear el acceso directo «CandidatAI»")) {
      $shell = New-Object -ComObject WScript.Shell
      $shortcut = $shell.CreateShortcut($lnk)
      # Con cmd: si `cai start` falla, la ventana se queda abierta y enseña el error.
      $shortcut.TargetPath = Join-Path $env:SystemRoot "System32\cmd.exe"
      $shortcut.Arguments = "/c `"`"$((Get-Command uv).Source)`" run --directory `"$backend`" cai start || pause`""
      $shortcut.WorkingDirectory = $backend
      $shortcut.IconLocation = Join-Path $AppDir "frontend\public\candidatai.ico"
      $shortcut.Description = "Abre CandidatAI (cierra la ventana para pararla)"
      $shortcut.Save()
    }
  }
}

Write-Host ""
Write-Host "Listo. Abre «CandidatAI» desde el escritorio o el menú Inicio." -ForegroundColor Green
Say "Se abrirá una ventana (déjala abierta mientras la uses) y el navegador en http://127.0.0.1:8000."
Say "Para actualizar, vuelve a ejecutar este instalador: tus datos no se tocan."
Say "Para conectar tu agente de IA, mira la guía: https://github.com/DiegoPrieto23/candidatai/blob/main/docs/GUIA.md"
