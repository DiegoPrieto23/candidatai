# Fase 08b · Motor html e importación de CVs en cualquier formato

## Contexto
Lee `docs/CV_TEMPLATES.md` (§Motor html), `docs/DECISIONS.md` ADR-014 y
`.agents/skills/importar-plantilla-cv/SKILL.md`. Requiere la fase 08.

## Objetivo
Poder usar como plantilla un CV que solo existe en PDF o imagen (Canva, diseños descargados,
exportaciones de otras herramientas), recreando su diseño con fidelidad.

## Alcance
1. **Motor html** (`engines/html.py`): Jinja2 con autoescape + `style.css` + `fonts/` → PDF con
   Chromium vía Playwright (`page.pdf`), JavaScript desactivado y red bloqueada (solo se sirven
   ficheros de la carpeta de la plantilla). Tamaño de página y márgenes desde CSS `@page`.
2. **Saneado** al validar: fuera `<script>`, atributos `on*`, `<iframe>`, `<object>`, URLs remotas
   en `src`, `href` y `url()`. Si hay algo, `validate` falla indicando qué y dónde.
3. **Fuentes**: se cargan con `@font-face` desde `fonts/` de la plantilla o de `data/fonts/`.
   Aviso `font_substituted` si el PDF acaba con otra fuente.
4. **Plantilla integrada** `moderna-2col` (html, dos columnas, color de acento configurable, foto
   circular opcional) con preview demo.
5. **Importación desde PDF, imagen o HTML** (`jh templates …`):
   - `inspect` amplía su salida para PDF e imágenes: página renderizada a PNG en `data/tmp/`,
     bloques de texto con posición, tamaño y fuente (PDF), paleta de colores dominante y
     estimación de columnas y márgenes;
   - `scaffold-html --id <id>` crea la carpeta con un `template.html` y `style.css` base según esa
     estructura, para que el agente los ajuste;
   - `compare <id> --source <fichero>`: pone lado a lado el original y la preview de la plantilla
     con el perfil demo, en un PNG, y calcula una métrica simple de parecido (SSIM) como orientación.
6. **UI**: en la galería, para plantillas importadas, vista "Original | Recreación" y aviso
   "solo PDF" en plantillas html.

## Fuera de alcance
Conversión de html a DOCX (la calidad sería mala: si hace falta Word, se usa una plantilla docx).

## Criterios de aceptación
- Tests: render de `moderna-2col` con y sin foto y con los cuatro colores; el saneado elimina un
  `<script>` y una URL remota; ningún render hace peticiones de red (test con red bloqueada).
- `inspect` + `scaffold-html` + `compare` funcionan con un CV de ejemplo en PDF **ficticio**
  guardado en `backend/tests/fixtures/`.
- Prueba manual: importar un CV en PDF con el skill `importar-plantilla-cv` y renderizar con él
  un CV de una oferta real.

## Al terminar
Actualiza `docs/ROADMAP.md` y `docs/AGENTS_COMPAT.md` (qué agentes han podido recrear diseños desde
imagen en la prueba manual).
