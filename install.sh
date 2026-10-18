#!/usr/bin/env bash
# Instala (o actualiza) CandidatAI en macOS o Linux y crea un acceso directo para abrirla
# (fase 26.2; el de Windows es install.ps1, y este hace lo mismo).
#
#   1. Instala uv si no está (el instalador oficial de astral.sh). uv trae Python 3.12 por su cuenta.
#   2. Descarga la última release de CandidatAI (la UI ya va compilada: no hace falta Node).
#   3. La deja en <carpeta>/app. Tus datos van en <carpeta>/data y nunca se tocan al actualizar;
#      tu .env de la app tampoco (solo se fija CAI_DATA_DIR). La carpeta, por defecto:
#        macOS: ~/Library/Application Support/CandidatAI
#        Linux: ${XDG_DATA_HOME:-~/.local/share}/candidatai
#   4. Prepara el entorno (uv sync), el Chromium de Playwright (PDF de los CVs) y la base de datos.
#   5. Crea el acceso directo «CandidatAI»: en Linux, en el menú de aplicaciones; en macOS, en
#      ~/Applications. Al abrirlo se arranca todo (`cai start`) en una terminal y se abre el
#      navegador; para cerrarla, cierra esa ventana.
#
# No pide sudo. Con --dry-run solo explica lo que haría, sin cambiar nada. Solo sustituye o borra
# lo que es suyo: la carpeta de instalación lleva una marca (.candidatai) y la .app de macOS, su
# identificador.
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.sh | bash
#   curl -fsSL …/install.sh | bash -s -- --dry-run
#   ./install.sh --source ./candidatai.zip      # un zip local en vez de la última release
#   ./install.sh --source ~/candidatai          # o tu repositorio clonado, con la UI compilada
#   ./install.sh --uninstall                    # quita la app y el acceso directo; tus datos no
#
# Todo va dentro de `main`, que se llama en la última línea: con `curl | bash`, un script
# descargado a medias no ejecuta nada. Y como la entrada es el propio script, ningún programa que
# se lance lee de ella (`</dev/null`).

set -euo pipefail

DEFAULT_SOURCE="https://github.com/DiegoPrieto23/candidatai/releases/latest/download/candidatai.zip"
UV_INSTALLER="https://astral.sh/uv/install.sh"
GUIDE="https://github.com/DiegoPrieto23/candidatai/blob/main/docs/GUIA.md"
MARKER=".candidatai" # en la carpeta de instalación: es de CandidatAI
BUNDLE_ID="local.candidatai.launcher"

say() { printf '  %s\n' "$*"; }
step() { printf '\n» %s\n' "$*"; }
fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Uso: install.sh [opciones]

  --source <zip|URL|carpeta>  Zip de la release (ruta o URL) o tu repositorio con la UI compilada.
                              Por defecto, la última release publicada.
  --install-dir <carpeta>     Dónde instalar (por defecto, la carpeta de tu sistema).
  --dry-run                   Explica lo que haría, sin cambiar nada.
  --no-shortcuts              Sin acceso directo.
  --no-setup                  Sin uv sync, Chromium ni base de datos (pruebas, CI).
  --uninstall                 Quita la app y el acceso directo. Tus datos no.
  --remove-data               Con --uninstall, borra también tus datos (pide confirmación).
  -h, --help                  Esta ayuda.
EOF
}

# --- Opciones y rutas ------------------------------------------------------------------------------

SOURCE="$DEFAULT_SOURCE"
INSTALL_DIR=""
DRY_RUN=0
SHORTCUTS=1
SETUP=1
UNINSTALL=0
REMOVE_DATA=0

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --source)
        [ $# -ge 2 ] || fail "--source necesita un valor."
        SOURCE="$2"
        shift 2
        ;;
      --install-dir)
        [ $# -ge 2 ] || fail "--install-dir necesita un valor."
        INSTALL_DIR="$2"
        shift 2
        ;;
      --dry-run) DRY_RUN=1; shift ;;
      --no-shortcuts) SHORTCUTS=0; shift ;;
      --no-setup) SETUP=0; shift ;;
      --uninstall) UNINSTALL=1; shift ;;
      --remove-data) REMOVE_DATA=1; shift ;;
      -h | --help) usage; exit 0 ;;
      *) usage >&2; fail "Opción desconocida: $1" ;;
    esac
  done
  if [ "$REMOVE_DATA" = 1 ] && [ "$UNINSTALL" = 0 ]; then
    fail "--remove-data solo vale con --uninstall."
  fi
}

trim() { # sin espacios al principio ni al final
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  printf '%s' "${value%"${value##*[![:space:]]}"}"
}

# Ruta absoluta y normalizada (sin `.`, `..`, `//` ni barra final), sin resolver enlaces:
# `realpath -m` no está en macOS.
absolute() {
  local path="$1" part result="" parts
  # shellcheck disable=SC2088 # «~» llega sin expandir (--install-dir="~/x") y se expande aquí
  case "$path" in
    /*) ;;
    "~") path="$HOME" ;;
    "~/"*) path="$HOME/${path#"~/"}" ;;
    *) path="$PWD/$path" ;;
  esac
  IFS=/ read -r -a parts <<<"$path" # sin expandir comodines (`*`), a diferencia de `for in $path`
  for part in "${parts[@]}"; do
    case "$part" in
      "" | .) ;;
      ..) result="${result%/*}" ;;
      *) result="$result/$part" ;;
    esac
  done
  printf '%s' "${result:-/}"
}

# Lo mismo que `install_dir()` de backend/app/core/config.py (un test comprueba que coinciden).
data_home() {
  local xdg
  xdg="$(trim "${XDG_DATA_HOME:-}")"
  case "$xdg" in
    /*) absolute "$xdg" ;;
    *) absolute "$HOME/.local/share" ;; # XDG: una ruta relativa no vale
  esac
}

default_install_dir() {
  if [ "$OS" = macos ]; then
    absolute "$HOME/Library/Application Support/CandidatAI"
  else
    printf '%s/candidatai' "$(data_home)"
  fi
}

# Nunca se instala (ni se borra nada) en una carpeta del sistema ni en tu carpeta personal.
check_install_dir() {
  local forbidden
  case "$INSTALL_DIR" in
    *'"'* | *\\* | *'`'* | *'$'* | *'%'* | *$'\n'*)
      fail "La carpeta no puede llevar comillas, \\, \`, \$ ni %: $INSTALL_DIR" ;;
  esac
  for forbidden in / "$HOME" "$HOME/.local" "$HOME/.local/share" "$(data_home)" \
    "$HOME/Library" "$HOME/Library/Application Support" "$HOME/Applications" \
    "$HOME/Desktop" "$HOME/Documents" "$HOME/Downloads" /tmp "${TMPDIR:-/tmp}" /usr /opt \
    /Applications /var /etc; do
    if [ "$INSTALL_DIR" = "$(absolute "$forbidden")" ]; then
      fail "--install-dir no puede ser $INSTALL_DIR: usa una carpeta propia, p. ej. $(default_install_dir)."
    fi
  done
}

is_candidatai_app() {
  [ -f "$1/backend/pyproject.toml" ] &&
    grep -Eq '^[[:space:]]*name[[:space:]]*=[[:space:]]*"candidatai"' "$1/backend/pyproject.toml"
}

# La carpeta de instalación es de CandidatAI: lleva la marca o una app de CandidatAI.
owns_install_dir() {
  [ -f "$INSTALL_DIR/$MARKER" ] || is_candidatai_app "$APP_DIR"
}

# Se puede instalar aquí: no existe, está vacía o ya es de CandidatAI.
can_install_here() {
  [ ! -e "$INSTALL_DIR" ] && return 0
  [ -d "$INSTALL_DIR" ] || return 1
  [ -z "$(ls -A -- "$INSTALL_DIR")" ] && return 0
  owns_install_dir
}

is_our_mac_app() {
  [ -f "$1/Contents/Info.plist" ] && grep -q "<string>$BUNDLE_ID</string>" "$1/Contents/Info.plist"
}

# Con --dry-run, `would "texto"` lo dice y devuelve 0 (no se hace); si no, devuelve 1 (se hace).
would() {
  if [ "$DRY_RUN" = 1 ]; then
    say "Haría: $*"
    return 0
  fi
  return 1
}

# --- Desinstalar -----------------------------------------------------------------------------------

confirm_remove_data() {
  # La confirmación se lee de la terminal, no de la entrada: con `curl | bash`, la entrada es el
  # script. Sin terminal no se borra nada.
  local answer
  if ! { exec 3</dev/tty; } 2>/dev/null; then
    say "No hay una terminal para confirmar: tus datos de $DATA_DIR no se borran."
    return 1
  fi
  printf '  Se borrarán tus datos de %s (perfil, ofertas, CVs). No se puede deshacer.\n' "$DATA_DIR"
  printf '  Escribe «borrar» para confirmarlo: '
  read -r answer <&3 || answer=""
  exec 3<&-
  [ "$answer" = borrar ]
}

uninstall() {
  step "Desinstalando CandidatAI de $INSTALL_DIR"
  # Primero se comprueba todo; después se borra.
  if [ -e "$INSTALL_DIR" ] && ! owns_install_dir; then
    fail "$INSTALL_DIR no parece una instalación de CandidatAI: no se borra nada."
  fi
  if [ -d "$APP_DIR" ] && ! is_candidatai_app "$APP_DIR"; then
    fail "$APP_DIR no parece una instalación de CandidatAI: no se borra nada."
  fi
  if [ -n "$DESKTOP_FILE" ] && [ -f "$DESKTOP_FILE" ]; then
    would "borrar $DESKTOP_FILE" || rm -f -- "$DESKTOP_FILE"
  fi
  if [ -n "$MAC_APP" ] && [ -d "$MAC_APP" ]; then
    if is_our_mac_app "$MAC_APP"; then
      would "borrar $MAC_APP" || rm -rf -- "$MAC_APP"
    else
      say "$MAC_APP no la creó este instalador: no se borra."
    fi
  fi
  if [ -f "$LAUNCHER" ]; then
    would "borrar $LAUNCHER" || rm -f -- "$LAUNCHER"
  fi
  if [ -d "$APP_DIR" ]; then
    would "borrar la app ($APP_DIR)" || rm -rf -- "$APP_DIR"
  fi
  if [ "$REMOVE_DATA" = 1 ] && [ -d "$DATA_DIR" ]; then
    if [ "$DRY_RUN" = 1 ]; then
      say "Haría: pedir confirmación y borrar tus datos ($DATA_DIR)"
    elif confirm_remove_data; then
      rm -rf -- "$DATA_DIR"
      say "Tus datos se han borrado."
    else
      say "Tus datos se quedan en $DATA_DIR."
    fi
  elif [ -d "$DATA_DIR" ]; then
    say "Tus datos se quedan en $DATA_DIR (bórralos a mano o usa --uninstall --remove-data)."
  fi
  if [ "$DRY_RUN" = 0 ] && [ ! -e "$DATA_DIR" ]; then
    rm -f -- "$INSTALL_DIR/$MARKER"
    rmdir -- "$INSTALL_DIR" 2>/dev/null || true
  fi
  say "Listo."
}

# --- Pasos de la instalación -----------------------------------------------------------------------

find_uv() {
  local candidate
  for candidate in "$(command -v uv 2>/dev/null || true)" "${UV_INSTALL_DIR:+$UV_INSTALL_DIR/uv}" \
    "${XDG_BIN_HOME:+$XDG_BIN_HOME/uv}" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

fetch() { # fetch <url> <fichero>
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --proto '=https' -o "$2" "$1" </dev/null
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1" </dev/null
  else
    fail "Hace falta curl o wget para descargar."
  fi
}

step_uv() {
  step "1/5 · uv (gestor de Python)"
  if UV="$(find_uv)"; then
    say "Ya está: $UV"
  elif [ "$SETUP" = 0 ]; then
    UV="uv"
    say "Sin uv (--no-setup)."
  elif ! would "instalar uv con el instalador oficial ($UV_INSTALLER)"; then
    local installer
    installer="$(mktemp)"
    fetch "$UV_INSTALLER" "$installer"
    say "El instalador de uv añade su carpeta a tu PATH (en los ficheros de inicio de tu shell)."
    sh "$installer" </dev/null
    rm -f -- "$installer"
    UV="$(find_uv)" || fail "No se encuentra uv tras instalarlo: abre otra terminal y vuelve a ejecutar el instalador."
    say "Instalado: $UV"
  else
    UV="uv"
  fi
}

# Lo que se instala: ZIP (un zip local o descargado) o FOLDER (un repositorio).
ZIP=""
FOLDER=""
DOWNLOADED=""

step_download() {
  step "2/5 · Descargar CandidatAI"
  if [ -d "$SOURCE" ]; then
    FOLDER="$(absolute "$SOURCE")"
    [ -f "$FOLDER/frontend/dist/index.html" ] ||
      fail "En $FOLDER falta la UI compilada: ejecuta antes 'cd frontend && pnpm install && pnpm build'."
    say "Carpeta local: $FOLDER"
  elif [ -f "$SOURCE" ]; then
    ZIP="$(absolute "$SOURCE")"
    say "Zip local: $ZIP"
  else
    case "$SOURCE" in
      https://*) ;;
      *) fail "--source no es un zip, una carpeta ni una URL https: $SOURCE" ;;
    esac
    if ! would "descargar $SOURCE"; then
      DOWNLOADED="$(mktemp "${TMPDIR:-/tmp}/candidatai-XXXXXX")"
      fetch "$SOURCE" "$DOWNLOADED"
      ZIP="$DOWNLOADED"
    fi
  fi
}

unzip_to() { # unzip_to <zip> <carpeta>
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$1" -d "$2" </dev/null
  elif command -v python3 >/dev/null 2>&1; then
    python3 -m zipfile -e "$1" "$2" </dev/null
  elif [ -x "$UV" ] || command -v "$UV" >/dev/null 2>&1; then
    "$UV" run --no-project --python 3.12 python -m zipfile -e "$1" "$2" </dev/null
  else
    fail "Hace falta unzip (o python3) para descomprimir la release."
  fi
}

STAGING=""
UNZIPPED=""

cleanup() {
  # Si se cortó entre apartar la app anterior y poner la nueva, vuelve la anterior.
  if [ -n "$INSTALL_DIR" ] && [ ! -e "$APP_DIR" ] && [ -d "$INSTALL_DIR/app.old" ]; then
    mv -- "$INSTALL_DIR/app.old" "$APP_DIR" || true
  fi
  [ -z "$STAGING" ] || rm -rf -- "$STAGING"
  [ -z "$UNZIPPED" ] || rm -rf -- "$UNZIPPED"
  [ -z "$DOWNLOADED" ] || rm -f -- "$DOWNLOADED"
}

write_env() { # Tu .env de la app se conserva; solo se fija dónde están tus datos.
  local old="$APP_DIR/.env" new="$1/.env"
  if [ -f "$old" ]; then
    grep -Ev '^[[:space:]]*(CAI|JH)_DATA_DIR[[:space:]]*=' "$old" >"$new" || true
  else
    : >"$new"
  fi
  printf 'CAI_DATA_DIR="%s"\n' "$DATA_DIR" >>"$new"
}

step_copy() {
  step "3/5 · Copiar la app"
  if ! can_install_here; then
    fail "$INSTALL_DIR ya existe y no es una instalación de CandidatAI: elige otra carpeta con --install-dir."
  fi
  if [ -z "$ZIP" ] && [ -z "$FOLDER" ]; then
    say "Haría: dejar la app en $APP_DIR; datos en $DATA_DIR (tus datos no se tocan)"
    return 0
  fi
  if would "dejar la app en $APP_DIR; datos en $DATA_DIR (tus datos no se tocan)"; then
    return 0
  fi
  mkdir -p -- "$INSTALL_DIR"
  : >"$INSTALL_DIR/$MARKER"
  # La versión nueva se prepara aparte y solo sustituye a la anterior si está completa.
  STAGING="$INSTALL_DIR/app.new"
  rm -rf -- "$STAGING"
  if [ -n "$FOLDER" ]; then
    # Sin tus datos (las carpetas data* de la raíz), entornos, dependencias ni el historial de git.
    mkdir -p -- "$STAGING"
    (cd "$FOLDER" && tar --exclude='./data' --exclude='./data-demo*' --exclude='./.env' \
      --exclude='.venv' --exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
      -cf - .) | (cd "$STAGING" && tar -xf -)
  else
    UNZIPPED="$(mktemp -d "${TMPDIR:-/tmp}/candidatai-XXXXXX")"
    unzip_to "$ZIP" "$UNZIPPED"
    [ -d "$UNZIPPED/candidatai" ] ||
      fail "El zip no tiene la carpeta candidatai/: no parece una release de CandidatAI."
    mv -- "$UNZIPPED/candidatai" "$STAGING"
  fi
  is_candidatai_app "$STAGING" || fail "Lo descargado no parece CandidatAI (falta backend/pyproject.toml)."
  [ ! -f "$STAGING/install.sh" ] || chmod +x "$STAGING/install.sh" # `python -m zipfile` no lo conserva
  write_env "$STAGING"
  if [ -d "$APP_DIR" ]; then
    rm -rf -- "$INSTALL_DIR/app.old"
    mv -- "$APP_DIR" "$INSTALL_DIR/app.old"
  fi
  mv -- "$STAGING" "$APP_DIR"
  STAGING=""
  rm -rf -- "$INSTALL_DIR/app.old"
  mkdir -p -- "$DATA_DIR"
  say "App en $APP_DIR; datos en $DATA_DIR"
}

chromium_hint() {
  # Linux: Chromium necesita librerías del sistema que solo se instalan con sudo. No se ejecuta:
  # se explica.
  local backend="$1"
  say "Chromium no arranca: faltan librerías de tu sistema. Sin ellas, los PDF necesitan LibreOffice."
  say "Lo que instalaría Playwright (con sudo, hazlo tú si quieres):"
  "$UV" run --directory "$backend" playwright install-deps --dry-run chromium </dev/null 2>/dev/null |
    sed 's/^/    /' || true
  say "O, de una vez: sudo \"$UV\" run --directory \"$backend\" playwright install-deps chromium"
}

step_setup() {
  local backend="$APP_DIR/backend"
  step "4/5 · Preparar el entorno (puede tardar unos minutos la primera vez)"
  if [ "$SETUP" = 0 ]; then
    say "Sin preparar (--no-setup)."
    return 0
  fi
  would "uv sync, Chromium de Playwright y base de datos en $backend" && return 0
  "$UV" sync --directory "$backend" </dev/null || fail "uv sync ha fallado."
  "$UV" run --directory "$backend" playwright install chromium </dev/null ||
    fail "No se pudo instalar Chromium."
  if [ "$OS" = linux ] && ! "$UV" run --directory "$backend" python -c \
    'from playwright.sync_api import sync_playwright as s
with s() as p: p.chromium.launch().close()' </dev/null >/dev/null 2>&1; then
    chromium_hint "$backend"
  fi
  "$UV" run --directory "$backend" cai db upgrade </dev/null ||
    fail "No se pudo preparar la base de datos."
}

write_launcher() {
  # El acceso directo abre este script en una terminal: arranca todo y, si falla, deja leer el
  # error antes de cerrarse.
  local backend uv
  printf -v backend '%q' "$APP_DIR/backend"
  printf -v uv '%q' "$UV"
  cat >"$LAUNCHER" <<EOF
#!/usr/bin/env bash
# Generado por install.sh: abre CandidatAI. Deja esta ventana abierta mientras la uses.
cd $backend || exit 1
$uv run --directory $backend cai start
code=\$?
if [ "\$code" -ne 0 ]; then
  echo
  echo "CandidatAI se ha cerrado con un error (\$code). Pulsa Intro para cerrar esta ventana."
  read -r _
fi
exit "\$code"
EOF
  chmod +x "$LAUNCHER"
}

write_desktop_file() {
  mkdir -p -- "$(dirname -- "$DESKTOP_FILE")"
  # Sin comillas, \, `, $ ni % en la ruta (check_install_dir): entre comillas dobles, tal cual.
  cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=CandidatAI
Comment=Abre CandidatAI (cierra la ventana para pararla)
Exec="$LAUNCHER"
Icon=$APP_DIR/frontend/public/candidatai.png
Terminal=true
Categories=Office;
StartupNotify=false
EOF
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$(dirname -- "$DESKTOP_FILE")" </dev/null >/dev/null 2>&1 || true
  fi
}

write_mac_app() {
  # Una .app mínima con el icono que abre el lanzador en Terminal, donde se ve (y se cierra) la app.
  local contents="$MAC_APP/Contents" launcher
  printf -v launcher '%q' "$LAUNCHER"
  if [ -e "$MAC_APP" ]; then
    is_our_mac_app "$MAC_APP" || fail "$MAC_APP ya existe y no la creó este instalador: no se toca."
    rm -rf -- "$MAC_APP"
  fi
  mkdir -p -- "$contents/MacOS" "$contents/Resources"
  cat >"$contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>CandidatAI</string>
  <key>CFBundleDisplayName</key><string>CandidatAI</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>CandidatAI</string>
  <key>CFBundleIconFile</key><string>candidatai</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
</dict>
</plist>
EOF
  cat >"$contents/MacOS/CandidatAI" <<EOF
#!/usr/bin/env bash
exec open -a Terminal $launcher
EOF
  chmod +x "$contents/MacOS/CandidatAI"
  if [ -f "$APP_DIR/frontend/public/candidatai.icns" ]; then
    cp -- "$APP_DIR/frontend/public/candidatai.icns" "$contents/Resources/candidatai.icns"
  fi
  touch -- "$MAC_APP" # para que el Finder vea el icono
}

step_shortcuts() {
  step "5/5 · Acceso directo"
  if [ "$SHORTCUTS" = 0 ]; then
    say "Sin acceso directo (--no-shortcuts)."
    return 0
  fi
  if [ "$OS" = macos ]; then
    would "crear $MAC_APP, que abre $LAUNCHER en Terminal" && return 0
    write_launcher
    write_mac_app
    say "Creado: $MAC_APP"
  else
    would "crear $DESKTOP_FILE, que abre $LAUNCHER en una terminal" && return 0
    write_launcher
    write_desktop_file
    say "Creado: $DESKTOP_FILE"
  fi
}

# --- Principal -------------------------------------------------------------------------------------

main() {
  parse_args "$@"
  case "$(uname -s)" in
    Darwin) OS=macos ;;
    Linux) OS=linux ;;
    *) fail "install.sh es para macOS y Linux. En Windows, usa install.ps1." ;;
  esac
  INSTALL_DIR="$(absolute "${INSTALL_DIR:-$(default_install_dir)}")"
  check_install_dir
  APP_DIR="$INSTALL_DIR/app"
  DATA_DIR="$INSTALL_DIR/data"
  DESKTOP_FILE=""
  MAC_APP=""
  if [ "$OS" = macos ]; then
    LAUNCHER="$INSTALL_DIR/CandidatAI.command"
    MAC_APP="$HOME/Applications/CandidatAI.app"
  else
    LAUNCHER="$INSTALL_DIR/candidatai-start"
    DESKTOP_FILE="$(data_home)/applications/candidatai.desktop"
  fi
  [ "$DRY_RUN" = 0 ] || say "Prueba en seco (--dry-run): no se cambia nada."

  if [ "$UNINSTALL" = 1 ]; then
    uninstall
    return 0
  fi

  printf 'CandidatAI · instalación en %s\n' "$INSTALL_DIR"
  trap cleanup EXIT
  step_uv
  step_download
  step_copy
  step_setup
  step_shortcuts

  if [ "$DRY_RUN" = 1 ]; then
    printf '\nPrueba en seco terminada: no se ha cambiado nada.\n'
    return 0
  fi
  printf '\nListo. Abre «CandidatAI» desde '
  if [ "$OS" = macos ]; then printf 'Aplicaciones (~/Applications).\n'; else printf 'el menú de aplicaciones.\n'; fi
  say "Se abrirá una terminal (déjala abierta mientras la uses) y el navegador en http://127.0.0.1:8000."
  say "También puedes arrancarla con: $LAUNCHER"
  say "Para actualizar, vuelve a ejecutar este instalador: tus datos no se tocan."
  say "Para conectar tu agente de IA, mira la guía: $GUIDE"
}

main "$@"
