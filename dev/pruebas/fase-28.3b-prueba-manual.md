# Fase 28.3b · Prueba manual: generar y revisar los medios nuevos

Objetivo: generar las capturas y animaciones que faltan (todas las de inglés y dos escenas en
español), revisarlas a ojo y dejar lista la imagen social. Todo sale de la demo: ningún dato tuyo.

Hay que hacerlo **fuera de Claude Code**, en tus propias ventanas de PowerShell: la generación
abre la API, el worker, la UI y varios Chromium, y Claude Code mata sus tareas cuando falta memoria
(ya pasó una vez en esta fase).

## Ya hecho por el agente (2026-10-24)

- [x] Español: las 24 capturas en claro y las 5 en oscuro (`docs/img/es/`, WebP de 41-98 KB).
- [x] Español: 4 de las 6 animaciones en `docs/img/es/anim/` (descartar, añadir buzón, Mi perfil y
  CV).
- [x] Banner y diagrama «cómo funciona» rehechos (entrevistas, buzones, respuestas) y la imagen
  social `docs/img/social-en.png` (1280×640).
- [x] La demo trae dos buzones con alertas (5 ofertas resumen), así que «Alertas» ya no sale vacía.

## 1. Generar lo que falta (unos 15 minutos)

Antes: cierra el `node.exe` que se quedó escuchando en el puerto 5181 (Administrador de tareas →
Detalles), si sigue ahí. Tu app normal (8000/5173) no se toca.

**Ventana 1**, la UI para las capturas (déjala abierta hasta el final):

```powershell
cd frontend
$env:VITE_API_URL = "http://127.0.0.1:8010"
pnpm exec vite --port 5181 --strictPort
```

**Ventana 2**, los medios:

```powershell
cd backend
uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py en
uv run --with imageio-ffmpeg python ../scripts/readme_media/all.py es apply,triage
```

- [x] `all.py en` termina sin error y deja `docs/img/en/` (24 `.webp`), `docs/img/en/dark/`
  (5) y `docs/img/en/anim/` (6: `profile`, `discard`, `mailbox`, `cv`, `apply`, `triage`).
- [x] `all.py es apply,triage` termina sin error y añade `apply.webp` y `triage.webp` a
  `docs/img/es/anim/`. (Vuelve a hacer también las capturas en español: es normal.)
- [x] Durante la escena `apply` se abre un Chromium aparte: es el navegador de la app rellenando un
  formulario de prueba **local** (127.0.0.1:8030). No lo cierres; se para antes de enviar.

Si algo falla, copia el error y pásaselo al agente. Al acabar, cierra la ventana 1.

## 2. Revisar a ojo

Abre las imágenes en el navegador (arrastra el `.webp` a una pestaña: así se ven animadas).

- [x] **Nada real:** la candidata es Aoife Brennan (inglés) o Lucía Varela Otero (español), con
  empresas inventadas. Ningún dato tuyo, ni tu correo ni tus empresas.
- [x] **Nada cortado:** cada captura enseña lo que dice su nombre (`job-interview` con el plan de
  preparación desplegado, `alerts` con los dos buzones, `profile-search` con los bloques de
  «Búsqueda»…).
- [x] **Modo oscuro legible** en `dark/` (texto y bordes se distinguen).
- [x] **Animaciones sin sonido:** se entienden solo con la leyenda de abajo, la leyenda no tapa lo
  importante y el bucle no empieza en blanco.
- [x] **`apply.webp`** llega a la pantalla de revisión (campos rellenados y de dónde sale cada uno)
  y al diálogo de confirmación con el nombre de la empresa, sin enviar nada.
- [x] **Idioma:** en `en/` toda la UI en inglés y en `es/` en español.

Apunta debajo de cada punto, con `→`, lo que no te convenza; el agente lo rehace.

**Resultado (2026-10-25):** ✅ revisado por el usuario, todo bien.

## 3. Avisar al agente

- [x] Dile que los medios están listos. Él termina la fase: apunta los README y las guías a los
  medios nuevos, comprueba el peso (≤ 8 MB en `docs/img/`), pasa los tests, la revisión y propone
  el commit.

## 4. Más adelante (fase 28.4, no ahora)

- [ ] Sube la imagen social en GitHub: Settings → General → Social preview → «Edit» → elige
  `docs/img/social-en.png`. Compruébalo pegando el enlace del repositorio en un chat o en LinkedIn.
