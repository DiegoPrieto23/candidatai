# Medios del README

Cómo se generan las capturas, las animaciones y las ilustraciones de `README.md`, `README.es.md`,
las listas de funcionalidades y las guías. Todo sale de la **demo** (datos inventados), nunca de
`data/`.

| Fichero | Genera | Destino |
|---|---|---|
| `illustrations.py` | Diagrama «cómo funciona» (SVG, con modo oscuro) e imagen social (PNG 1280×640) en los dos idiomas | `docs/img/*.svg`, `docs/img/social-<idioma>.png` |
| `screenshots.py` | Capturas de la UI en una ventana de 1440×900, en WebP, en un idioma: las 9 del README (`README`) a ×2 (2880×1800) y el resto a ×1; las de `DARK`, también en oscuro | `docs/img/<idioma>/` y `docs/img/<idioma>/dark/` |
| `recordings.py` | Animaciones (WebP animado) de una escena: `tour` (la de la sección «Demo», 25-30 s, 1280×800, de hasta 1,5 MB y sin leyendas) o una corta (< 20 s, con leyenda abajo): `triage`, `discard`, `mailbox`, `cv`, `profile`, `apply`, `extension` o `start`. Y `video`: el tour en vídeo | `docs/img/<idioma>/anim/`; el vídeo, en `data/tmp/video/<idioma>/` |
| `all.py` | Todo lo de un idioma de una vez: siembra su demo, arranca API y worker, hace capturas y escenas y lo para | lo de las dos filas anteriores |
| `apply-form.html` | El formulario de prueba que rellenan `apply`, `tour` y `video`, servido en 127.0.0.1:8030 | — |

Los medios van por idioma: `docs/img/en/` para `README.md` y `docs/img/es/` para `README.es.md`
(la web toma los mismos). La franja «Modo demo» se oculta solo en capturas y grabaciones, nunca
en la app: lo dice la nota bajo cada bloque del README y de la web. Las rutas del equipo que genera
las capturas (la carpeta de la extensión, por ejemplo) llevan su nombre de usuario: `screenshots.py`
las cambia por unas inventadas (`C:\Users\olivia\…`) y se para si aún queda alguna en la página.

**Presupuesto:** todo `docs/img/` hasta 15 MB y `tour.webp` hasta 1,5 MB por idioma. Lo comprueba
`backend/tests/test_docs_img_budget.py`. Si no cabe, por este orden: quitar lo que no enlaza
nadie, bajar la calidad de lo que no está en el README (`QUALITY` en `screenshots.py`) y, por
último, la de las 9 del README (`QUALITY_2X`), sin bajar de ×2.

**El vídeo no va al repositorio.** La escena `video` deja en `data/tmp/video/<idioma>/` el tour
(`candidatai-tour-<idioma>.mp4`, 1080p y 60-90 s, con los subtítulos incrustados), sus subtítulos
(`.srt` y `.vtt`), una transcripción breve (`.txt`) y un clip cuadrado de 18 s para redes
(`candidatai-clip-<idioma>.mp4`). Se suben como activos de la release.

## Pasos

Hazlo en una ventana de PowerShell propia, no desde un agente: abre la API, el worker y varios
Chromium, y un agente puede cortar sus tareas cuando falta memoria. Tu app puede seguir abierta en
8000/5173: esto usa 8010 (API y UI de la demo) y 8030 (el formulario de prueba).

1. **La UI compilada**, que es la que se captura (la sirve la API de la demo en 8010):

   ```powershell
   cd frontend
   pnpm build
   ```

2. **Todo un idioma** (desde `backend/`; `imageio-ffmpeg` trae ffmpeg sin tocar las dependencias
   del proyecto):

   ```powershell
   cd backend
   uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py en
   uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py es
   ```

   Con un segundo argumento solo hace esas escenas (`all.py es apply,triage`); las capturas las
   repite salvo con `--sin-capturas` (`all.py es tour --sin-capturas`). La escena `extension` solo
   entra si hay `LINKEDIN_URL` (la de una oferta pública de LinkedIn). `all.py` siembra su propia
   demo (`data-demo-shots` o `data-demo-en-shots`, en `.gitignore`), apunta la primera oferta con CV al formulario de prueba y arranca el worker con
   `CAI_APPLIER_ALLOW_LOOPBACK=1`, que es lo único que le deja abrir un formulario local. Durante
   `apply` se abre un Chromium aparte: no lo cierres; se para antes de enviar.

3. **El vídeo**, aparte (siembra otra demo limpia; un par de minutos por idioma):

   ```powershell
   uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py en video --sin-capturas
   uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py es video --sin-capturas
   ```

4. **Ilustraciones** (no dependen de la demo):

   ```powershell
   uv run python ../scripts/readme_media/illustrations.py ../docs/img
   ```

5. **Revisa a ojo** cada imagen (arrastra el `.webp` a una pestaña del navegador para verlo
   animado): nada real, nada cortado, modo oscuro legible y animaciones que se entienden sin
   sonido.

6. Comprueba el presupuesto, que los README y las listas enlazan bien y que cada página tiene
   captura:

   ```powershell
   uv run pytest -q tests/test_docs_img_budget.py
   uv run python ../scripts/check_links.py
   uv run python ../scripts/check_readme_coverage.py
   ```

## Si algo se para o sale mal

- **Se corta sin error a mitad de las capturas** (el log acaba de golpe, sin `Traceback`): casi
  siempre es memoria. Cierra lo que no uses (con unos 8 GB libres va bien), lanza un idioma cada
  vez y, si vuelve a pasar, parte el trabajo: primero las capturas solas
  (`all.py es tour` regenera capturas y la escena `tour`), después el resto de escenas con
  `--sin-capturas`.
- **`apply` falla con `Timeout` esperando «Preparar candidatura» / «Prepare application»**: en la
  misma demo, `tour` ya dejó la candidatura de la oferta 1 parada en la confirmación, y ese botón
  ya no sale. Repite `apply` y `triage` sobre una demo recién sembrada, que es lo que hace cada
  llamada a `all.py`:

  ```powershell
  uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py es apply,triage --sin-capturas
  ```

- **`tour.webp` pasa de 25-30 s o de 1,5 MB:** se graba a velocidad real (unos 40 s, porque el CV
  tarda en renderizarse) y se acelera con `SPEED` en `recordings.py` (hoy ×1,5). Si cambias el
  factor, cambia también la velocidad que dice la nota bajo la demo en los README y en la web. Si
  lo que sobra es peso, baja la calidad o los fotogramas en `SHARP`.
- **`extension` no se graba con `all.py`** si no hay `LINKEDIN_URL`. Para grabarla, pon en esa
  variable la URL de una oferta pública de LinkedIn y lánzala sola:
  `$env:LINKEDIN_URL = "<url>"; uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py en extension --sin-capturas`.
  Mientras falte en un idioma, la app enseña la del otro (el gesto es el mismo).
- **Los mensajes `check_open … ConnectError` del worker** son normales: la demo no comprueba
  ofertas en internet.

## Una sola captura o escena

Con la API de una demo en 8010 (`cai serve --port 8010` con `CAI_DATA_DIR` de la demo y la UI
compilada):

```powershell
uv run python ../scripts/readme_media/screenshots.py ../docs/img/en en light "home,inbox"
uv run python ../scripts/readme_media/screenshots.py ../docs/img/en/dark en dark "home"
uv run --with imageio-ffmpeg python ../scripts/readme_media/recordings.py ../docs/img/en/anim cv en
```

Los nombres de las capturas están en `SHOTS`, al principio de `screenshots.py`. Las escenas
`triage`, `discard`, `mailbox`, `cv`, `tour` y `video` cambian la demo: usa una solo para esto y
graba `triage` la última, porque aprueba una oferta. `tour` y `video` preparan antes, sin grabar,
la candidatura de la oferta 1 (hace falta el formulario de 8030 y el worker de `all.py`).

La escena `start` (la salida de `cai start` en un terminal) no la hace `all.py`: necesita un
`cai start` aparte sobre la misma demo, con su salida en `START_LOG` y su URL en `START_URL`
(por defecto `http://127.0.0.1:8020`). Hoy no se usa en el README: la app se abre con el acceso
directo.

## Por qué así

- La UI se sirve desde la misma API que la demo, como con `cai start`: el mismo origen. La API
  rechaza cualquier escritura que no venga de su UI y el navegador no deja reescribir el `Origin`
  de un POST, así que una UI en otro puerto no podría preparar una candidatura ni mover una
  tarjeta.
- Los textos con los que se busca un botón, una pestaña o un título salen de
  `frontend/src/locales/<idioma>/`, así que los mismos scripts sirven para los dos idiomas.
- WebP en vez de PNG y GIF: pesa varias veces menos y GitHub lo muestra (también animado).
