# Fase 08b · Motor html e importación de CVs en cualquier formato

## Contexto
Lee `docs/CV_TEMPLATES.md` (§Motor html), `docs/DECISIONS.md` ADR-014 y
`.agents/skills/importar-plantilla-cv/SKILL.md`. Requiere la fase 08 completa (08.1, 08.2 y 08.3):
lee su registro en `docs/ROADMAP.md`.

### Qué deja hecho la fase 08 y aquí se reutiliza
- `TemplateMeta` ya admite `engine: html`; renderizar una plantilla html da el error «motor html:
  fase 08b», que esta fase sustituye por el motor real.
- La detección de fuentes sustituidas (`pdf.py`), las comprobaciones y avisos (`checks.py`), la
  resolución de opciones y el contexto del contrato de variables son comunes a los dos motores.
- `preview.py` (PDF + PNG con `pypdfium2`) y `jh templates preview`, `validate` e `inspect`
  (solo `.docx`): aquí se amplían, no se reescriben.
- La galería de Plantillas y el bloque «Mi CV» con la subida de ficheros a `data/uploads/` (que ya
  acepta PDF e imagen y avisa de que requieren esta fase) y «Usar por defecto».
- `inspect` ya da para `.docx` el orden de secciones y la `capacity` medida en el original, y el
  contrato ya tiene `extra_sections` (08.3).
- Si la 08c ya está hecha: el contrato de carta, `TemplateMeta.letter` y `carta-simple`.

## Objetivo
Poder usar como plantilla («Mi CV» incluido) un CV que solo existe en PDF o imagen (Canva, diseños
descargados, exportaciones de otras herramientas), recreando su diseño con fidelidad y con el mismo
orden de secciones y extensión que el original.

## Alcance
1. **Motor html** (`engines/html.py`): Jinja2 con autoescape + `style.css` + `fonts/` → PDF con
   Chromium vía Playwright (`page.pdf`), JavaScript desactivado y red bloqueada (solo se sirven
   ficheros de la carpeta de la plantilla). Tamaño de página y márgenes desde CSS `@page`.
2. **Saneado** al validar: fuera `<script>`, atributos `on*`, `<iframe>`, `<object>`, URLs remotas
   en `src`, `href` y `url()`. Si hay algo, `validate` falla indicando qué y dónde.
3. **Fuentes**: se cargan con `@font-face` desde `fonts/` de la plantilla o de `data/fonts/`.
   Aviso `font_substituted` si el PDF acaba con otra fuente.
4. **Plantilla integrada** `moderna-2col` (html, dos columnas, color de acento configurable, foto
   circular opcional, con `extra_sections`) con preview demo.
5. **Importación desde PDF, imagen o HTML** (`jh templates …`):
   - `inspect` amplía su salida para PDF e imágenes: página renderizada a PNG en `data/tmp/`,
     bloques de texto con posición, tamaño y fuente (PDF), paleta de colores dominante,
     estimación de columnas y márgenes y, como en `.docx`, el orden de secciones y la `capacity`
     medida (en imágenes, aproximada: lo que el agente lea en la imagen);
   - `scaffold-html --id <id>` crea la carpeta con un `template.html` y `style.css` base según esa
     estructura, para que el agente los ajuste;
   - `compare <id> --source <fichero>`: pone lado a lado el original y la preview de la plantilla
     con el perfil demo, en un PNG, y calcula una métrica simple de parecido (SSIM) como orientación.
6. **UI**: en la galería y en «Mi CV», para plantillas importadas, vista "Original | Recreación" y
   aviso "solo PDF" en plantillas html (aviso `pdf_only` en los renders). La subida deja de avisar
   de que PDF e imagen requieren esta fase.
7. **Carta en html** (solo si la 08c ya está hecha; si no, la 08c lo hará al llegar): el motor html
   también renderiza `letter.html` con el contrato de la carta; `moderna-2col` trae la suya y el
   skill `importar-plantilla-cv` crea `letter.html` a partir de la cabecera del diseño recreado.
8. **`jh doctor`**: comprueba que Playwright tiene Chromium instalado y que renderiza
   `moderna-2col` sin red (si falta, indica `uv run playwright install chromium`). Playwright
   entra aquí como dependencia; la fase 11 la reutiliza.

## Fuera de alcance
Conversión de html a DOCX (la calidad sería mala: si hace falta Word, se usa una plantilla docx).

## Criterios de aceptación
- Tests: render de `moderna-2col` con y sin foto, con los cuatro colores y con `extra_sections`
  (y su carta, si la 08c está hecha); el saneado elimina un
  `<script>` y una URL remota; ningún render hace peticiones de red (test con red bloqueada).
- `inspect` + `scaffold-html` + `compare` funcionan con un CV de ejemplo en PDF **ficticio**
  guardado en `backend/tests/fixtures/`.
- Prueba manual: importar un CV en PDF con el skill `importar-plantilla-cv` y renderizar con él
  un CV de una oferta real.

## Al terminar
Actualiza `docs/ROADMAP.md` y `docs/AGENTS_COMPAT.md` (qué agentes han podido recrear diseños desde
imagen en la prueba manual).
