"""Todos los medios de un idioma, de principio a fin (fase 28.3b).

Uso (desde backend/): uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py IDIOMA [ESCENAS]
  IDIOMA: en o es. ESCENAS: las de recordings.py separadas por comas (por defecto, todas salvo
  `start`, que necesita su propio `cai start`; ver README.md).

1. Siembra una demo solo para esto (`data-demo-shots` o `data-demo-en-shots`, con `--force`).
2. Apunta la primera oferta con CV al formulario de `apply-form.html`, servido en 127.0.0.1:8030.
3. Arranca la API (8010) y el worker de esa demo con `CAI_APPLIER_ALLOW_LOOPBACK=1` (solo así
   abren un formulario local). La UI (5181) la arrancas tú antes, en otra terminal:
   `cd frontend; $env:VITE_API_URL = "http://127.0.0.1:8010"; pnpm exec vite --port 5181 --strictPort`.
4. Capturas en claro y en oscuro (`screenshots.py`) en `docs/img/<idioma>/` y escenas
   (`recordings.py`) en `docs/img/<idioma>/anim/`. `triage` va la última: aprueba una oferta.
5. Lo para todo. Nunca toca `data/` ni la app que tengas en 8000/5173.
"""

import os
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BACKEND = ROOT / "backend"
LANG = sys.argv[1]
assert LANG in ("en", "es"), "IDIOMA: en o es"
SCENES = (
    sys.argv[2].split(",")
    if len(sys.argv) > 2
    else ["profile", "discard", "mailbox", "cv", "apply", "triage"]
)
DEMO = "data-demo-en-shots" if LANG == "en" else "data-demo-shots"
OUT = ROOT / "docs" / "img" / LANG
FORM = "http://127.0.0.1:8030/apply-form.html"


def wait_for(url: str, seconds: int = 90) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"{url} no responde")


def up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except OSError:
        return False


# La CLI en este mismo Python (no el lanzador `cai`): así `terminate()` para el proceso de verdad.
CAI = [sys.executable, "-c", "from app.cli import app; app(prog_name='cai')"]


def run(*args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run([sys.executable, *args], cwd=BACKEND, check=True, env=env)


def main() -> None:
    env = {**os.environ, "CAI_DATA_DIR": DEMO, "CAI_APPLIER_ALLOW_LOOPBACK": "1"}
    if not up("http://127.0.0.1:5181"):
        sys.exit("Arranca antes la UI en 5181 (ver arriba).")
    seed = [*CAI, "demo", "seed", "--dir", DEMO, "--force", "--lang", LANG]
    subprocess.run(seed, cwd=BACKEND, check=True)
    with closing(sqlite3.connect(ROOT / DEMO / "candidatai.db")) as db, db:
        db.execute("UPDATE jobs SET url = ? WHERE id = 1", (FORM,))

    procs = [
        subprocess.Popen([sys.executable, "-m", "http.server", "8030", "--bind", "127.0.0.1"],
                         cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
        subprocess.Popen([*CAI, "serve", "--port", "8010"], cwd=BACKEND, env=env),
        subprocess.Popen([*CAI, "worker"], cwd=BACKEND, env=env),
    ]
    try:
        wait_for("http://127.0.0.1:8010/status")
        wait_for(FORM)
        run(str(HERE / "screenshots.py"), str(OUT), LANG, "light")
        run(str(HERE / "screenshots.py"), str(OUT / "dark"), LANG, "dark")
        for scene in SCENES:
            run(str(HERE / "recordings.py"), str(OUT / "anim"), scene, LANG)
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=30)


main()
