# Medios del README

Cómo se generan las capturas, los GIF, el vídeo y las ilustraciones de `README.md`, `README.es.md`
y las guías. Todo sale de la **demo** (datos inventados), nunca de `data/`.

| Fichero | Genera | Destino |
|---|---|---|
| `illustrations.py` | Banner y diagrama «cómo funciona», en inglés y español (SVG, con modo oscuro en el diagrama) | `docs/img/*.svg` |
| `screenshots.py` | Capturas de la UI a 1600×1000 (×1,5) | `docs/img/*.png` y, con `dark`, `docs/img/dark/` |
| `recordings.py` | Grabaciones en `.webm` de tres escenas: `tour`, `cv`, `triage` | Carpeta temporal; luego ffmpeg (abajo) |

## Pasos

1. Demo aparte, para no tocar la tuya (`data-demo*/` está en `.gitignore`):

   ```powershell
   cd backend
   uv run cai demo seed --dir data-demo-shots --force
   ```

2. API y UI de la demo en **otros puertos**, para no chocar con tu app en 8000/5173:

   ```powershell
   $env:CAI_DATA_DIR = "data-demo-shots"; uv run cai serve --port 8010
   # en otra terminal
   cd frontend; $env:VITE_API_URL = "http://127.0.0.1:8010"; pnpm exec vite --port 5181 --strictPort
   ```

   La API solo acepta el origen `http://127.0.0.1:5173`. Los scripts lanzan Chromium con
   `--disable-web-security` y reescriben el `Origin` de cada petición a la API. Es solo para
   capturar en local; no cambia nada de la app.

3. Capturas e ilustraciones (desde `backend/`, que tiene Playwright):

   ```powershell
   uv run python ../scripts/readme_media/illustrations.py ../docs/img
   uv run python ../scripts/readme_media/screenshots.py ../docs/img light
   uv run python ../scripts/readme_media/screenshots.py ../docs/img/dark dark "inicio,por-revisar,ficha-cv"
   ```

4. Grabaciones. Graba `triage` la última, porque aprueba una oferta de la demo:

   ```powershell
   uv run python ../scripts/readme_media/recordings.py $env:TEMP\jh-rec tour
   uv run python ../scripts/readme_media/recordings.py $env:TEMP\jh-rec cv
   uv run python ../scripts/readme_media/recordings.py $env:TEMP\jh-rec triage
   ```

5. Conversión con ffmpeg. Si no lo tienes, el paquete `imageio-ffmpeg` trae uno, sin tocar las
   dependencias del proyecto:
   `uv run --no-project --with imageio-ffmpeg python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`.

   ```powershell
   # vídeo
   ffmpeg -ss 0.8 -i tour.webm -vf "scale=1280:-2" -c:v libx264 -crf 26 -preset slow -pix_fmt yuv420p -movflags +faststart ..\docs\video\recorrido.mp4
   # GIF (triage → triaje.gif, cv → cv.gif)
   ffmpeg -ss 0.8 -i triage.webm -vf "fps=8,scale=880:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" ..\docs\img\triaje.gif
   ```

   Los GIF deben quedar por debajo de ~3 MB para que GitHub los cargue rápido.

## El vídeo en GitHub

GitHub no reproduce un `.mp4` del repositorio dentro del README: el enlace abre el fichero. Para
que se vea incrustado, edita el README en github.com, arrastra `docs/video/recorrido.mp4` al
editor y deja la URL `https://github.com/user-attachments/assets/…` que genera en su propia línea.
