# Medios del README

Cómo se generan las capturas, las animaciones y las ilustraciones de `README.md`, `README.es.md`,
las listas de funcionalidades y las guías. Todo sale de la **demo** (datos inventados), nunca de
`data/`.

| Fichero | Genera | Destino |
|---|---|---|
| `illustrations.py` | Banner, diagrama «cómo funciona» (SVG, con modo oscuro en el diagrama) e imagen social (PNG 1280×640) | `docs/img/*.svg`, `docs/img/social-en.png` |
| `screenshots.py` | Capturas de la UI a 1600×1000 (×1,5) en WebP, en un idioma; las de `DARK`, también en oscuro | `docs/img/<idioma>/` y `docs/img/<idioma>/dark/` |
| `recordings.py` | Animaciones cortas (< 20 s, WebP animado con leyenda abajo) de una escena: `triage`, `discard`, `mailbox`, `cv`, `profile`, `apply` o `start` | `docs/img/<idioma>/anim/` |
| `all.py` | Todo lo de un idioma de una vez: siembra su demo, arranca API y worker, hace capturas y escenas y lo para | lo de las dos filas anteriores |
| `apply-form.html` | El formulario de prueba que rellena la escena `apply`, servido en 127.0.0.1:8030 | — |

Los medios van por idioma: `docs/img/en/` para `README.md` y `docs/img/es/` para `README.es.md`.
**No hay vídeos en el repositorio** (decisión de la fase 28.3): solo capturas y animaciones cortas,
con un presupuesto de 8 MB para todo `docs/img/`.

## Pasos

Hazlo **fuera de Claude Code**, en tus propias ventanas: abre la API, el worker, la UI y varios
Chromium, y Claude Code mata sus tareas cuando falta memoria.

1. **Ventana 1**, la UI de las capturas en otro puerto (tu app sigue en 8000/5173). Déjala abierta
   hasta el final:

   ```powershell
   cd frontend
   $env:VITE_API_URL = "http://127.0.0.1:8010"
   pnpm exec vite --port 5181 --strictPort
   ```

2. **Ventana 2**, todo un idioma (desde `backend/`; `imageio-ffmpeg` trae ffmpeg sin tocar las
   dependencias del proyecto):

   ```powershell
   cd backend
   uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py en
   uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py es
   ```

   Con un segundo argumento solo hace esas escenas (`all.py es apply,triage`); las capturas las
   repite siempre. `all.py` siembra su propia demo (`data-demo-shots` o `data-demo-en-shots`, en
   `.gitignore`), apunta la primera oferta con CV al formulario de prueba y arranca el worker con
   `CAI_APPLIER_ALLOW_LOOPBACK=1`, que es lo único que le deja abrir un formulario local. Durante
   `apply` se abre un Chromium aparte: no lo cierres; se para antes de enviar.

3. **Ilustraciones** (no dependen de la demo):

   ```powershell
   uv run python ../scripts/readme_media/illustrations.py ../docs/img
   ```

4. **Revisa a ojo** cada imagen (arrastra el `.webp` a una pestaña del navegador para verlo
   animado): nada real, nada cortado, modo oscuro legible y animaciones que se entienden sin
   sonido. La lista completa está en `dev/pruebas/fase-28.3b-prueba-manual.md`.

5. Comprueba que los README y las listas enlazan bien y que cada página tiene captura:

   ```powershell
   uv run python ../scripts/check_links.py
   uv run python ../scripts/check_readme_coverage.py
   ```

## Una sola captura o escena

Con la API de una demo en 8010 y la UI en 5181 (pasos 1 y 2 de arriba, o `cai serve --port 8010`
con `CAI_DATA_DIR` de la demo):

```powershell
uv run python ../scripts/readme_media/screenshots.py ../docs/img/en en light "home,inbox"
uv run python ../scripts/readme_media/screenshots.py ../docs/img/en/dark en dark "home"
uv run --with imageio-ffmpeg python ../scripts/readme_media/recordings.py ../docs/img/en/anim cv en
```

Los nombres de las capturas están en `SHOTS`, al principio de `screenshots.py`. Las escenas
`triage`, `discard`, `mailbox` y `cv` cambian la demo: usa una solo para esto y graba `triage` la
última, porque aprueba una oferta.

La escena `start` (la salida de `cai start` en un terminal) no la hace `all.py`: necesita un
`cai start` aparte sobre la misma demo, con su salida en `START_LOG` y su URL en `START_URL`
(por defecto `http://127.0.0.1:8020`). Hoy no se usa en el README: la app se abre con el acceso
directo.

## Por qué así

- La API solo acepta el origen `http://127.0.0.1:5173`. Los scripts lanzan Chromium con
  `--disable-web-security` y reescriben el `Origin` de cada petición. Es solo para capturar en
  local; no cambia nada de la app.
- Los textos con los que se busca un botón, una pestaña o un título salen de
  `frontend/src/locales/<idioma>/`, así que los mismos scripts sirven para los dos idiomas.
- WebP en vez de PNG y GIF: pesa varias veces menos y GitHub lo muestra (también animado).
