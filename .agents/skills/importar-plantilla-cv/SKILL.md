---
name: importar-plantilla-cv
description: Convierte un CV con cualquier diseño (Word, PDF, imagen, HTML, exportado de Canva o Google Docs) en una plantilla de Job Hunter para generar CVs con ese estilo. Úsalo cuando se quiera usar el diseño de un CV propio o de un modelo como plantilla.
---

Especificación completa: `docs/CV_TEMPLATES.md`. Los comandos se ejecutan desde la raíz del repo
(`jh` = `uv run --directory backend jh`) y solo trabajan dentro de `data/`.

Este skill se ocupa **solo del diseño**. El contenido de tus CVs sale siempre de tu perfil: si
el CV subido tiene información que no está en `data/profile.yaml`, se anota al final y se propone
el skill `actualizar-perfil`. Nunca se copia texto del CV subido a la plantilla.

## 1. Recibir el fichero
- Argumentos: ruta del fichero. Si no la hay, pídela. Tiene que estar en `data/uploads/` (si está
  en otro sitio, pide al usuario que lo copie ahí o súbelo desde la UI, página Plantillas).
- Formatos: `.docx` (mejor: el diseño se conserva exacto), `.pdf`, `.png`, `.jpg`, `.html`.
  Desde Google Docs, exporta a `.docx`; desde Canva y similares, a PDF.
- Pregunta un nombre corto para la plantilla y genera su `id` (minúsculas y guiones).

## 2. Analizar
`jh templates inspect <fichero> --json`. Con el resultado, explica en 3-4 líneas qué has visto:
columnas, foto, colores, fuentes, secciones y si es apto para ATS (una columna, sin tablas ni
cuadros de texto de maquetación, datos clave fuera de cabecera y pie).

## 3. Construir según el formato

**`.docx` → motor docx (se conserva el diseño original):**
1. Con la lista de párrafos de `inspect`, prepara `data/tmp/<id>-mapping.json`: para cada párrafo,
   si es estático (títulos de sección que se sustituyen por `labels.*`, adornos), una variable
   (`name`, `subtitle`, `summary`…) o el inicio o fin de un bucle o condicional (`experience`,
   `bullets`, `photo`…). Usa solo variables del contrato de `CV_TEMPLATES.md`.
2. Un solo ejemplo por bloque repetido: si el CV tiene tres experiencias, la primera se convierte
   en el cuerpo del bucle y las otras dos se marcan para eliminar.
3. `jh templates build-docx --source <fichero> --mapping data/tmp/<id>-mapping.json --id <id>`.
   Si falla, corrige el mapeo según el error y reintenta.

**`.pdf`, imagen o `.html` → motor html (se recrea el diseño; requiere la fase 08b):**
1. Necesitas poder ver la imagen de la página que genera `inspect`. Si tu agente no puede ver
   imágenes, dilo y propón exportar el original a `.docx` o usar una plantilla integrada.
2. `jh templates scaffold-html --id <id>` y ajusta `template.html` y `style.css` hasta parecerse
   al original: disposición, márgenes, jerarquía tipográfica, colores, forma y posición de la
   foto, separadores e iconos (dibújalos con CSS o SVG en línea; nada remoto).
3. Fuentes: si el original usa una fuente que no está en `fonts/` ni en `data/fonts/`, pide al
   usuario el fichero (si tiene licencia para usarla) o propone la alternativa libre más parecida.

## 4. Metadatos
Escribe `template.yaml` con la honestidad de `inspect`: `ats_friendly` solo si cumple de verdad,
`photo.supported` según haya hueco para foto, `capacity` estimada a partir del espacio real y
`options.accent_color` si has parametrizado el color. Luego `jh templates validate <id>`.

## 5. Comparar e iterar
1. `jh templates preview <id> --profile demo` y, en html, `jh templates compare <id> --source <fichero>`.
2. Si puedes ver imágenes, compara con el original y corrige diferencias visibles (máximo 3 vueltas).
3. `jh templates preview <id> --profile real`: si el contenido real no cabe en `page.max_pages`,
   dilo y ajusta `capacity`, o propón `max_pages: 2` si el diseño lo pide.
4. Pide al usuario que lo revise en la UI (Plantillas → vista original | recreación) y aplica sus
   correcciones.

## 6. Cerrar
- Pregunta si quiere usarla por defecto o solo en ciertos casos. Propón la regla
  (`preferences.cv.default_template` o una entrada de `template_rules`, p. ej. «ofertas de startups
  y diseño» o «envíos por email») y aplícala con el skill `actualizar-perfil`.
- Si la plantilla no es apta para ATS, recomienda mantener `ats-simple` para ofertas con ATS
  (la regla por defecto ya lo hace) y explica por qué en una frase.
- Lista la información del CV subido que no está en el perfil, si la hay.
- Recuerda que puede tener todas las plantillas que quiera y elegir en cada oferta, desde la UI,
  plantilla, foto y color sin volver a usar el agente.
- Borra los ficheros temporales de `data/tmp/`.
