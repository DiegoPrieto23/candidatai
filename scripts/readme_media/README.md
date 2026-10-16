# Medios del README

Cómo se generan las capturas, los GIF, el vídeo y las ilustraciones de `README.md`, `README.es.md`
y las guías. Todo sale de la **demo** (datos inventados), nunca de `data/`.

| Fichero | Genera | Destino |
|---|---|---|
| `illustrations.py` | Banner y diagrama «cómo funciona», en inglés y español (SVG, con modo oscuro en el diagrama) | `docs/img/*.svg` |
| `screenshots.py` | Capturas de la UI a 1600×1000 (×1,5), en un idioma | `docs/img/<idioma>/*.png` y, con `dark`, `docs/img/<idioma>/dark/` |
| `recordings.py` | Grabaciones en `.webm` de cuatro escenas: `tour`, `cv`, `triage` y `start` | Carpeta temporal; luego ffmpeg (abajo) |

Los medios van por idioma: `docs/img/en/` para `README.md` y `docs/img/es/` para `README.es.md`.
Los pasos 2 a 5 se repiten con cada idioma, cada uno con su demo.

## Pasos

1. Demo aparte, para no tocar la tuya (`data-demo*/` está en `.gitignore`):

   ```powershell
   cd backend
   uv run cai demo seed --dir data-demo-shots --force                # español (README.es.md)
   uv run cai demo seed --lang en --dir data-demo-en-shots --force   # inglés (README.md)
   ```

   Cada README lleva capturas de su demo con la UI en su idioma (`cai-language` en el navegador).

2. API y UI de la demo en **otros puertos**, para no chocar con tu app en 8000/5173:

   ```powershell
   $env:CAI_DATA_DIR = "data-demo-shots"; uv run cai serve --port 8010   # o data-demo-en-shots
   # en otra terminal
   cd frontend; $env:VITE_API_URL = "http://127.0.0.1:8010"; pnpm exec vite --port 5181 --strictPort
   ```

   La API solo acepta el origen `http://127.0.0.1:5173`. Los scripts lanzan Chromium con
   `--disable-web-security` y reescriben el `Origin` de cada petición a la API. Es solo para
   capturar en local; no cambia nada de la app.

3. Capturas e ilustraciones (desde `backend/`, que tiene Playwright). Los argumentos son la
   carpeta, el idioma (`en` o `es`), el tema y, si quieres, solo algunas capturas por nombre (`home`,
   `inbox`, `triage`, `job`, `job-cv`, `job-process`, `processes`, `funnel`, `skills`, `templates`,
   `sources-companies`, `sources-platforms`, `agent`, `sidebar-collapsed`):

   ```powershell
   uv run python ../scripts/readme_media/illustrations.py ../docs/img
   uv run python ../scripts/readme_media/screenshots.py ../docs/img/en en light
   uv run python ../scripts/readme_media/screenshots.py ../docs/img/en/dark en dark "home,triage,job-cv"
   ```

4. Grabaciones (carpeta, escena, idioma). Graba `triage` la última, porque aprueba una oferta de
   la demo. La escena `start` reproduce la salida real de `cai start`: arráncalo antes sobre la
   misma demo en otro puerto y pásale su salida y su URL:

   ```powershell
   uv run python ../scripts/readme_media/recordings.py $env:TEMP\cai-rec tour en
   uv run python ../scripts/readme_media/recordings.py $env:TEMP\cai-rec cv en
   # en otra terminal, con CAI_DATA_DIR de la demo:
   #   uv run cai start --port 8020 --no-browser > $env:TEMP\cai-rec\start.log
   $env:START_LOG = "$env:TEMP\cai-rec\start.log"; $env:START_URL = "http://127.0.0.1:8020"
   uv run python ../scripts/readme_media/recordings.py $env:TEMP\cai-rec start en
   uv run python ../scripts/readme_media/recordings.py $env:TEMP\cai-rec triage en
   ```

   En la escena inglesa, la salida de `cai start` sale en español: la CLI aún no está traducida.

5. Conversión con ffmpeg. Si no lo tienes, el paquete `imageio-ffmpeg` trae uno, sin tocar las
   dependencias del proyecto:
   `uv run --no-project --with imageio-ffmpeg python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`.

   ```powershell
   # vídeo
   ffmpeg -ss 0.8 -i tour.webm -vf "scale=1280:-2" -c:v libx264 -crf 26 -preset slow -pix_fmt yuv420p -movflags +faststart ..\docs\video\tour-en.mp4
   # GIF (triage, cv y start, con el mismo nombre)
   ffmpeg -ss 0.8 -i triage.webm -vf "fps=8,scale=880:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" ..\docs\img\en\triage.gif
   ```

   Los GIF deben quedar por debajo de ~3 MB para que GitHub los cargue rápido.

## El vídeo en GitHub

GitHub no reproduce un `.mp4` del repositorio dentro del README: el enlace abre el fichero. Para
que se vea incrustado, edita el README en github.com, arrastra `docs/video/tour-en.mp4` (o `tour-es.mp4`) al
editor y deja la URL `https://github.com/user-attachments/assets/…` que genera en su propia línea.
