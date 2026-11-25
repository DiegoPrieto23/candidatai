<#
.SYNOPSIS
  Actualiza una instalación de CandidatAI desde la propia app (botón «Actualizar ahora» de Inicio).

.DESCRIPTION
  La app copia este script y su install.ps1 a una carpeta temporal (la de la app se sustituye
  entera), los abre en una ventana nueva y se cierra. Este script:
  1. espera a que se cierre CandidatAI (el proceso de `cai start`);
  2. espera a que ningún programa use la carpeta de la app: el servidor MCP de un agente abierto la
     bloquea, y entonces dice cuál es para cerrarlo;
  3. ejecuta el instalador, que descarga la última versión, comprueba su suma SHA-256 y la instala
     sin tocar los datos;
  4. vuelve a abrir CandidatAI sin otra pestaña: la que estaba abierta se recarga sola.
#>
param(
  [Parameter(Mandatory = $true)][string]$InstallDir,
  [Parameter(Mandatory = $true)][string]$Installer,
  # El proceso de `cai start`, que se cierra solo al pulsar el botón.
  [int]$WaitPid = 0,
  [string]$Uv = "uv",
  [ValidateSet("es", "en")][string]$Lang = "es",
  [int]$CloseTimeoutSeconds = 60,
  # Solo tests: no vuelve a abrir la app ni espera a que se pulse Intro.
  [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$texts = @{
  es = @{
    title = "CandidatAI · actualización"
    waiting = "Esperando a que se cierre CandidatAI…"
    busy = "Hay programas que usan CandidatAI ({0}). Si es el agente de IA, hay que cerrarlo: la actualización sigue sola en cuanto se cierre."
    installing = "Instalando la última versión. Los datos no se tocan."
    failed = "La actualización no ha terminado: {0}"
    retry = "Se puede reintentar con el botón de Inicio o con la orden de la guía (sección «Actualizar»)."
    starting = "Abriendo CandidatAI…"
    done = "Listo. Esta ventana se cierra sola."
    press = "Pulsa Intro para cerrar esta ventana"
  }
  en = @{
    title = "CandidatAI · update"
    waiting = "Waiting for CandidatAI to close…"
    busy = "Some programs are using CandidatAI ({0}). If it is your AI agent, close it: the update continues as soon as it closes."
    installing = "Installing the latest version. Your data is not touched."
    failed = "The update did not finish: {0}"
    retry = "Try again with the button on Home or with the command in the guide (section ""Updating"")."
    starting = "Opening CandidatAI…"
    done = "Done. This window closes by itself."
    press = "Press Enter to close this window"
  }
}
$t = $texts[$Lang]
try { $Host.UI.RawUI.WindowTitle = $t.title } catch { }

$app = Join-Path $InstallDir "app"
$prefix = $app.TrimEnd('\') + '\'

function Get-AppProcess {
  # Los programas que se ejecutan desde la carpeta de la app (su Python, `cai-mcp`…): mientras
  # sigan abiertos, Windows no deja sustituirla.
  @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
      $_.Path -and $_.Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
    })
}

$ok = $false
try {
  if ($WaitPid -gt 0) {
    Write-Host $t.waiting
    Wait-Process -Id $WaitPid -Timeout $CloseTimeoutSeconds -ErrorAction SilentlyContinue
  }
  $warned = $false
  while ($true) {
    $busy = Get-AppProcess
    if ($busy.Count -eq 0) { break }
    if (-not $warned) {
      $names = ($busy | ForEach-Object { $_.ProcessName } | Sort-Object -Unique) -join ", "
      Write-Host ($t.busy -f $names) -ForegroundColor Yellow
      $warned = $true
    }
    Start-Sleep -Seconds 2
  }
  # La ventana de la app (cmd y uv, fuera de su carpeta pero dentro como directorio de trabajo)
  # termina de cerrarse justo después.
  Start-Sleep -Seconds 2
  Write-Host ""
  Write-Host $t.installing -ForegroundColor Cyan
  & $Installer -InstallDir $InstallDir
  $ok = $true
} catch {
  Write-Host ""
  Write-Host ($t.failed -f $_.Exception.Message) -ForegroundColor Red
  Write-Host $t.retry
}

if ($NoRestart) {
  if (-not $ok) { exit 1 }
  exit 0
}

# Se vuelve a abrir aunque haya fallado: si falló antes de sustituir la app, sigue la de antes.
$backend = Join-Path $app "backend"
if (Test-Path (Join-Path $backend "pyproject.toml")) {
  Write-Host $t.starting
  $cmd = Join-Path $env:SystemRoot "System32\cmd.exe"
  Start-Process -FilePath $cmd -WorkingDirectory $backend `
    -ArgumentList "/c `"`"$Uv`" run --directory `"$backend`" cai start --no-browser || pause`""
}

# Esta carpeta temporal ya no hace falta (solo si es la que crea la app).
if ((Split-Path $PSScriptRoot -Leaf) -like "candidatai-update-*") {
  Set-Location $env:TEMP
  Remove-Item -LiteralPath $PSScriptRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if ($ok) {
  Write-Host $t.done -ForegroundColor Green
  Start-Sleep -Seconds 5
} else {
  Read-Host $t.press | Out-Null
}
