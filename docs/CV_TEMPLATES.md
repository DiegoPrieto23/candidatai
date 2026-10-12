# Plantillas de CV

El CV se genera en dos pasos independientes (ADR-014):

1. **Contenido** (`CvContent`): lo redacta el agente para cada oferta a partir de tu perfil. No
   sabe nada de colores, columnas ni fotos.
2. **Presentación**: el código combina ese contenido con una **plantilla** y unas **opciones de
   render** (foto, color, secciones…). Es determinista y no usa IA: cambiar de estilo o quitar la
   foto no gasta cuota.

Un mismo contenido puede tener varios renders (por ejemplo, uno sin foto para un ATS y otro con
foto para enviar por email), y tú marcas cuál se envía.

## Tu CV como base

El camino habitual es usar **tu propio CV** como plantilla (página Plantillas → «Mi CV», fase 08.3;
desde PDF o imagen, fase 08b): lo subes, tu agente lo convierte **una vez** con el skill
`importar-plantilla-cv` y lo marcas «Usar por defecto». A partir de ahí, cada CV a medida sale con
tu diseño, tu orden de secciones y una extensión parecida a la del original (la `capacity` se mide
en él), con el texto redactado desde tu perfil para cada oferta. La IA no reescribe tu Word en cada
oferta: así el estilo no se degrada, la verificación es la misma y cambiar de foto o color no gasta
cuota. Lo que tu CV tenga y el perfil no (incluidas secciones como voluntariado o premios) se pasa
antes al perfil con `actualizar-perfil`, a `extra_sections` si no encaja en otra sección.

## Dónde viven

| Carpeta | Qué contiene | En git |
|---|---|---|
| `templates/<id>/` | Plantillas integradas, genéricas y sin datos personales | Sí |
| `data/templates/<id>/` | Tus plantillas, creadas a partir de tus CVs o de diseños que tengas | No |
| `data/uploads/` | Los ficheros originales que subes para convertirlos en plantilla | No |
| `data/photo.<ext>` | Tu foto original (jpg, png, webp; heic si Pillow lo abre). Otra ruta dentro de `data/` con `preferences.cv.photo_file` | No |
| `data/cache/photo/` | La foto recortada para cada forma y tamaño (se regenera sola) | No |
| `data/cache/previews/` | Previews con tu perfil y de las integradas (se regeneran solas) | No |

Si una plantilla tuya tiene el mismo `id` que una integrada, gana la tuya.

## Estructura de una plantilla

```
<id>/
  template.yaml        metadatos (obligatorio)
  template.docx        motor docx: Word con marcadores docxtpl
  template.html        motor html: Jinja2 + HTML
  style.css            motor html
  fonts/               fuentes locales opcionales (.ttf, .otf, .woff2)
  letter.docx|html     diseño de carta a juego (opcional, fase 08c)
  letter.css           motor html: estilos propios de la carta (opcional; no cuentan para el CV)
  source.<ext>         original del que se creó (solo en data/, nunca en templates/)
  preview.pdf|png      generadas con el perfil y la foto demo (no se editan a mano); el PNG es la
                       primera página y es la miniatura de la UI
```

### `template.yaml`

```yaml
id: moderno-azul                  # igual que la carpeta; minúsculas, números y guiones
name: Moderno azul
engine: docx                      # docx | html
kind: cv                          # cv (por defecto) | letter: solo diseño de carta (`carta-simple`),
                                  # sin `template.*`; no se ofrece como plantilla de CV
origin: user                      # builtin | user
source_file: source.pdf           # solo en plantillas del usuario
description: Dos columnas, barra lateral azul con contacto y aptitudes.
tags: [moderno, tech]
layout:
  columns: 2
  uses_tables: true               # tablas o cuadros de texto para maquetar
  header_paragraphs: [0, 1, 2]    # solo docx importadas: párrafos de cabecera, para crear la carta
ats_friendly: false               # true solo si: 1 columna, sin tablas ni cuadros de texto de maquetación,
                                  # sin datos clave en cabecera o pie, y texto seleccionable en orden lógico
photo:
  supported: true
  shape: circle                   # circle | square | rounded
  size_mm: 32
page:
  size: A4                        # A4 | Letter
  max_pages: 1
capacity:                         # orientativo, para que el redactor ajuste la extensión; en las
                                  # importadas, medido en el original por `inspect`
  summary_chars: 450
  experience_bullets: 9
  skill_groups: 4
sections: [summary, experience, projects, education, certifications, extra_sections, skills, languages]
                                  # en el orden en que aparecen; en las importadas, el del original
letter:                           # opcional (fase 08c): diseño de carta a juego
  file: letter.docx               # letter.docx (docx) o letter.html (html, con su style.css)
options:
  accent_color:                   # opcional; solo si la plantilla usa {{ accent_color }}
    default: "#1F4E79"
    choices: ["#1F4E79", "#2E7D32", "#6A1B9A", "#37474F"]
    free: false                   # true: admite cualquier #RRGGBB (p. ej. `carta-simple`)
fonts: [Lato, Source Sans 3]      # las que usa; se comprueba que estén disponibles al renderizar
languages: [es, en]
```

`cai templates validate <id>` comprueba este fichero contra el modelo Pydantic `TemplateMeta` y
que el `template.*` solo usa variables del contrato (y el `letter.*`, solo las del contrato de la
carta).

## Contrato de variables

Lo que recibe cualquier plantilla, en los dos motores:

| Variable | Contenido |
|---|---|
| `name`, `subtitle`, `summary` | Texto |
| `contact.email`, `contact.phone`, `contact.city`, `contact.linkedin`, `contact.github` | Texto; vacíos si no aplican |
| `photo` | Imagen ya recortada con la forma de `photo.shape`, o vacío si esta vez no lleva foto |
| `experience[]` | `role`, `company`, `city`, `start`, `end`, `bullets[]` |
| `projects[]` | `name`, `date`, `url` (enlace del proyecto, vacío si no tiene), `bullets[]` |
| `education[]` | `title`, `center`, `start`, `end`, `detail` |
| `certifications[]` | `name`, `issuer`, `date` |
| `skills[]` | `group`, `items[]` (objetos, no diccionarios: `{{ s.items }}` funciona) |
| `extra_sections[]` | `title` (en el idioma del CV), `items[]` con `text` y `date` (desde la 08.3) |
| `languages[]` | `language`, `level` |
| `labels.*` | Títulos de sección en el idioma del CV (`labels.experience` = «Experiencia» / «Experience») |
| `accent_color` | Color elegido, si la plantilla lo admite |
| `show.<sección>` | `false` si esa sección se ha ocultado para esta oferta o está vacía (así no quedan títulos sin contenido) |

Las fechas llegan ya formateadas en el idioma del CV: `start` = «mar. 2024» / «Mar 2024» y
`end` = «actualidad» / «Present» si sigue. El contacto lo pone el código desde el perfil (el
agente no lo ve). `education[].detail` va vacío de momento: el perfil no tiene ese campo.

**Enlaces (ADR-023):** `contact.linkedin`, `contact.github` y `projects[].url` se pintan como
texto; al renderizar, el código los convierte en enlaces que se pueden pulsar en el PDF, con el
formato que les dé la plantilla. La plantilla no pone `href` externos (en html los quita el
saneado); en html conviene `a { color: inherit; text-decoration: none; }` para que no cambie
el diseño.

### Motor docx (docxtpl)
- Variables `{{ subtitle }}`; bucles de párrafo `{%p for e in experience %}` … `{%p endfor %}`;
  filas de tabla `{%tr for … %}`; condicionales `{%p if photo %}`.
- La foto es un `InlineImage` y se coloca donde esté `{{ photo }}`.
- **No escribas los marcadores a mano en Word**: Word los parte en fragmentos y dejan de
  funcionar. Usa el skill `importar-plantilla-cv`, que marca la plantilla con
  `cai templates build-docx`: el código fusiona los fragmentos de cada párrafo e inserta cada
  marcador de una pieza.
- Genera DOCX y PDF (con LibreOffice o Word).

### Importar desde Word (fase 08.3)

Lo hace el skill `importar-plantilla-cv` con tres comandos que solo trabajan dentro de `data/`:

1. **`cai templates inspect <fichero> --json`**: página (tamaño, márgenes, columnas), fuentes que
   se ven (por caracteres, resolviendo estilos y tema), colores, tablas, cuadros de texto,
   imágenes (con su tamaño y si parecen una foto), cabecera y pie, las secciones en su orden (las
   que no están en el contrato salen como `extra`), la `capacity` medida en el original y una
   estimación de `ats_friendly` con sus motivos. Y los **párrafos numerados** (cuerpo, tablas y
   cuadros de texto, y después cabeceras y pies) con sus fragmentos ya fusionados cuando comparten
   formato.
2. **`cai templates build-docx --source <fichero> --mapping <json> --id <id> [--name N] [--force]`**
   aplica el mapeo del agente:
   ```json
   {"paragraphs": [
     {"index": 0, "action": "variable", "text": "{{ name }}", "header": true},
     {"index": 4, "action": "variable", "text": "{{ labels.experience|upper }}",
      "start": ["if show.experience"]},
     {"index": 5, "action": "variable", "start": ["for e in experience"],
      "runs": [{"text": "{{ e.role }}", "like": 0}, {"text": " | {{ e.company }}", "like": 1}]},
     {"index": 6, "action": "variable", "text": "{{ b }}",
      "start": ["for b in e.bullets"], "end": ["endfor", "endfor", "endif"]},
     {"index": 7, "action": "delete"}
   ]}
   ```
   - `action`: `static` (por defecto: se queda como está), `delete`, `variable` (`text`, o `runs`
     para mezclar formatos: cada parte copia el del fragmento `like`) o `photo` (la imagen del
     párrafo pasa a ser `{{ photo }}`).
   - `start` abre bloques antes del párrafo (`for x in y`, `if cond`) y `end` los cierra después
     (`endfor`, `endif`). Con `scope: row`, el bloque es la fila de tabla entera (`{%tr … %}`).
   - `header` marca la cabecera (nombre, subtítulo, contacto, foto): queda en
     `layout.header_paragraphs` para la carta a juego de la fase 08c.
   - Una fila de tabla cuyos párrafos se borran todos desaparece; las copias de compatibilidad de
     los cuadros de texto (`mc:Fallback`) se quitan para que no conserven el texto original.

   Antes de tocar el fichero, el mapeo se monta como una plantilla de borrador y se renderiza con
   todo el perfil demo: bloques sin cerrar, variables fuera del contrato o atributos que no existen
   (`e.rol`) salen juntos, con el `index` del párrafo. Después, cada párrafo mapeado se reescribe
   en un solo fragmento (o uno por parte de `runs`) con el formato del original. Escribe
   `template.docx`, `source.docx`, `source.png` (primera página del original) y un `template.yaml`
   con las secciones en el orden en que las usa el mapeo, la `capacity` y las páginas del
   original, la foto, la cabecera y el `ats_friendly` de `inspect`. Si la plantilla resultante no
   renderiza, no deja nada.
3. **`cai templates validate <id>`** (yaml, contrato y render con el perfil demo) y
   **`cai templates preview <id> [--profile demo|real]`**: PDF y PNG; con `demo`, en la carpeta de
   una plantilla tuya (es su miniatura); con `real` o en una integrada, en `data/cache/previews/`.
   Avisa si no cabe en `page.max_pages` o si falta una fuente.

Limitaciones: una foto flotante pasa a ir en línea en su párrafo (se avisa), y el color de acento
no se parametriza en las plantillas importadas (sigue el del original).

### Motor html (fase 08b)
- `template.html` es Jinja2 (sandbox, autoescape y variables estrictas: `e.rol` falla al validar)
  con las mismas variables que el docx: `{{ name }}`, `{% for e in experience %}`… La foto es
  una ruta local: `{% if photo %}<img src="{{ photo }}">{% endif %}`. El color de acento llega en
  `accent_color`; lo habitual es `<style>:root { --accent: {{ accent_color }}; }</style>` y usar
  `var(--accent)` en `style.css`.
- Se imprime a PDF con Chromium (Playwright) **sin JavaScript y sin red**: la página se carga
  desde un origen virtual y solo se sirven ficheros de la carpeta de la plantilla, `fonts/` (de la
  plantilla o, si no está ahí, de `data/fonts/`) y la foto recortada. Cualquier otra petición se
  aborta.
- Tamaño de página y márgenes, con CSS `@page` (`@page { size: A4; margin: 0; }`). El tamaño de
  las opciones de render (`page_size`) se impone sobre el de la plantilla.
- **Saneado** en dos capas. `cai templates validate` falla, indicando fichero y línea, si
  `template.html` o `style.css` tienen `<script>`, atributos `on*`, `<iframe>`, `<object>`,
  `<embed>`, `<base>`, `javascript:` o URLs remotas en `src`, `href`, `srcset`, `url()`,
  `image-set()` o `@import`. Al renderizar, además, se quitan del HTML generado y de los CSS
  servidos, y Chromium arranca sin resolución de nombres. Se admiten rutas relativas, `data:`, `mailto:`
  y `tel:`.
- **Fuentes** con `@font-face` desde `fonts/` (woff2, ttf u otf). Si el PDF acaba con otra
  fuente, aviso `font_substituted`, como en docx. `moderna-2col` trae Lato (OFL) en sus `fonts/`.
- Solo genera PDF: cada render html lleva el aviso `pdf_only`. Si un portal exige Word, se
  renderiza ese CV con una plantilla docx (la UI lo indica).
- Requiere Chromium de Playwright: `uv run --directory backend playwright install chromium`.
  `cai doctor` comprueba que está y que imprime `moderna-2col` sin red. Cada render tarda unos
  2 s.

### Importar desde PDF, imagen o HTML (fase 08b)

El diseño no se puede reutilizar como en Word: se **recrea** en HTML. El agente necesita ver
imágenes. Los comandos, igual que en Word, solo trabajan dentro de `data/`:

1. **`cai templates inspect <fichero> --json`** (`.pdf`, `.png`, `.jpg` o `.html`):
   - **Páginas en PNG** en `data/tmp/inspect/<fichero>/` (`page_images`; hasta 3), para que el
     agente las vea.
   - **Bloques de texto** (PDF y HTML): cada línea con posición y tamaño en mm, cuerpo en pt,
     fuente, negrita y cursiva. **Imágenes**, con su posición y si parecen una foto
     (`photo_candidate`). **Fuentes** que usa.
   - **Paleta dominante** (`colors`, con la fracción de página) y **maquetación** estimada sobre
     la imagen (`layout`): columnas y dónde se separan, barra lateral a sangre y su color, banda
     de cabecera, fondo y márgenes.
   - Como en Word: **secciones en su orden**, con la columna de cada una (`extra` = fuera del
     contrato), la **`capacity` medida** (logros por experiencia, por viñeta o por sangría) y la
     estimación de **ATS** (una plantilla html nunca es `ats_friendly`).
   - Un HTML se imprime antes con el motor html (saneado, sin red ni JavaScript y sin cargar
     ningún otro fichero: su carpeta es `data/uploads/`, con tus otros CVs). Sus imágenes y
     fuentes propias no se ven; el agente recrea el diseño mirando la página. Una **imagen** no
     tiene texto: secciones y `capacity` salen vacías y `capacity_note` pide al agente que las
     lea en la imagen.
2. **`cai templates scaffold-html --source <fichero> --id <id> [--name N] [--sections a,b,c]
   [--side x,y] [--force]`** crea `data/templates/<id>/` con una base que ya se parece al
   original:
   - `template.html`: cabecera (con banda de color si la había), columna principal y lateral en
     su lado (la barra a sangre ocupa toda la página) y foto donde estaba.
   - `style.css`: márgenes, colores, fuentes del texto y de los títulos, y el acento como
     `var(--accent)`.
   - `template.yaml`, `source.<ext>` y `source.png`.

   Las secciones salen de `inspect` (primero la columna principal, después la lateral) o de
   `--sections`/`--side`, que en una imagen son obligatorias en la práctica. El acento detectado
   queda como color por defecto, con los cuatro habituales como alternativa. Si la base no
   renderiza con el perfil demo, no queda nada.
3. El agente **ajusta** `template.html` y `style.css` mirando `source.png`: tipografía, tamaños,
   separadores, iconos (CSS o SVG en línea, nada remoto) y la forma de la foto. Las fuentes que
   no estén instaladas van en `fonts/` (si su licencia lo permite) o se cambian por la libre más
   parecida.
4. **`cai templates validate <id>`** (yaml, saneado, contrato y render con el perfil demo) y
   **`cai templates compare <id> --source <fichero>`**: el original y la preview con el perfil
   demo lado a lado en `data/tmp/compare/<id>/comparacion.png`, con una **SSIM** (0-1) sobre las
   páginas desenfocadas y en baja resolución. Es orientativa: sirve para ver si un cambio acerca
   o aleja la recreación, no como nota (diseños distintos dan 0,4-0,65). Lo que cuenta es mirar la
   imagen.

Limitaciones: la recreación es aproximada; columnas, márgenes y logros se estiman y pueden
fallar en diseños muy irregulares. Una plantilla html solo da PDF. Su carta a juego (`letter.html`)
la escribe el skill `importar-plantilla-cv` desde la cabecera recreada (§Cartas de presentación).

## Opciones de render por oferta (`CvRenderOptions`)

```yaml
template_id: null          # null = según reglas
photo: auto                # auto | include | exclude
accent_color: null         # null = el de la plantilla
max_pages: null            # null = preferences.cv.max_pages o, si tampoco, el de la plantilla
hidden_sections: []        # p. ej. [projects, extra_sections]
page_size: null            # null = el de la plantilla
```

Cómo se resuelve lo que queda en `null` o `auto`:

1. **Plantilla**: la opción explícita, si la hay; si no, la primera regla de
   `preferences.cv.template_rules` que encaje con la oferta; si no, `preferences.cv.default_template`;
   si no, la integrada `ats-simple`.
2. **Foto** (`auto`): se incluye si la plantilla la admite, hay foto y
   `preferences.cv.photo_policy` la permite para el país de la oferta. La foto es
   `preferences.cv.photo_file` (relativa a `data/`) y, si ese fichero no existe, el primer
   `data/photo.*`. Se recorta centrada a la forma y tamaño de la plantilla (`circle` y `rounded`
   con fondo transparente), respetando la orientación EXIF.
3. **Páginas**: la opción > `preferences.cv.max_pages` > `page.max_pages` de la plantilla.
4. Lo demás, lo que diga la plantilla.

Las reglas pueden mirar el país de la oferta, el ATS detectado por su URL
(`config/policies.yaml` → `ats_platforms`, el dominio o un subdominio suyo), el `domain` de la
extracción (palabras completas, sin tildes) y el idioma del CV. Encaja la regla que cumple
todas sus condiciones; la primera que encaje decide, y si su plantilla no existe se avisa
(`template_not_found`) y se sigue con `default_template`.

El **país** sale de las ubicaciones de la extracción y de la oferta con `config/countries.yaml`
(nombres de país, regiones y ciudades en es/en, por palabra completa y sin tildes; los nombres
ambiguos, como Valencia, no cuentan). Si la oferta está en varios países, una regla de país
encaja si alguno está en su lista y la foto `auto` solo va si la política la permite en todos.
Si no se reconoce ningún país, se aplica `photo_policy.default`.

```yaml
template_rules:
  - when: {ats: [workday, taleo, successfactors, icims]}
    use: ats-simple
  - when: {country: [GB, IE, US, NL]}
    use: ats-simple
  - when: {domain: [diseño, marketing, producto]}
    use: moderno-azul
```

## Avisos al renderizar

El render nunca se bloquea en silencio: devuelve avisos que ves en la UI y recibe el agente.

| Aviso | Cuándo |
|---|---|
| `too_long` | Supera `max_pages` |
| `template_not_found` | Una regla o `default_template` piden una plantilla que no existe o no es válida; se usa la siguiente opción |
| `not_ats_friendly` | La oferta usa un ATS conocido y la plantilla no es `ats_friendly` |
| `photo_excluded` | Pediste foto pero la plantilla no la admite o no hay foto |
| `section_not_supported` | El contenido tiene una sección que la plantilla no muestra |
| `font_substituted` | Falta una fuente de la plantilla y el PDF usa otra |
| `pdf_only` | Motor html: no hay DOCX |
| `letter_fallback` | Carta: la plantilla elegida no tiene diseño de carta y se usa `carta-simple` con su color |

## Renders

Cada render guarda sus opciones resueltas, sus ficheros en `data/cvs/<job_id>/<document_id>/<render_id>/`
y el hash de la plantilla. En la ficha de la oferta, sección «CV», eliges plantilla (con su
miniatura), foto, color y secciones ocultas y pulsas «Renderizar»: crea un render nuevo con el
mismo contenido verificado, sin agente. Puedes ver dos renders lado a lado y marcar con «Usar este
para enviar» el que irá en la candidatura (uno por CV). Si los ficheros de una plantilla cambian
después de un render, la UI lo marca como «Plantilla cambiada».

## Plantillas integradas

| id | Motor | Fase | Estilo |
|---|---|---|---|
| `ats-simple` | docx | 08 | Una columna, sin foto, tipografía estándar. La opción segura para portales con ATS |
| `clasica-foto` | docx | 08 | Una columna con cabecera y foto circular, sobria; color de acento a elegir entre 4. No apta para ATS (cabecera en tabla) |
| `moderna-2col` | html | 08b | Dos columnas con barra lateral de color a sangre (foto circular, contacto, habilidades, idiomas y certificaciones), 4 colores de acento y fuente Lato incluida. Solo PDF; no apta para ATS |
| `carta-simple` | docx | 08c | Solo carta: cabecera sobria sin foto y color de acento libre. Respaldo cuando la plantilla del CV no trae carta |

Desde la 08c, `ats-simple`, `clasica-foto` y `moderna-2col` traen también su `letter.*`.

## Cartas de presentación (fase 08c)

La carta sigue la misma separación que el CV: el agente redacta `CoverLetterContent` (saludo,
párrafos con evidencias y despedida) según tus indicaciones, y el código la presenta.

- **A juego con el CV**: por defecto se renderiza con la plantilla, la foto y el color del render
  seleccionado del CV de esa oferta, usando el `letter.*` de la plantilla. Si no tiene, se usa
  `carta-simple` con el mismo color y se avisa (`letter_fallback`).
- **Integradas**:
  - `ats-simple` y `clasica-foto` traen `letter.docx`, con su misma cabecera (la de
    `clasica-foto`, con foto en tabla), generado por `scripts/build_builtin_templates.py`;
  - `moderna-2col` trae `letter.html` y `letter.css`, con la barra lateral (foto y contacto) y la
    cabecera del CV.
- **`cai templates build-letter <id> [--force] [--json]`** (plantillas docx del usuario):
  - parte de su `template.docx`;
  - conserva los bloques del principio (párrafos y tablas) que solo usan variables de cabecera
    (`name`, `subtitle`, `contact`, `photo`), con los párrafos de control que los cierran;
  - quita el resto y añade el cuerpo de la carta con el formato del primer párrafo de contenido
    del CV (no de los títulos);
  - lo comprueba con el contrato de la carta y renderizándolo, y declara `letter` en
    `template.yaml`.

  Errores:
  - sin cabecera (`layout.header_paragraphs` vacío), o con la cabecera mezclada con el cuerpo
    (p. ej. en una tabla a dos columnas): error claro, y la carta sigue saliendo con
    `carta-simple`;
  - una integrada o una html: error;
  - si ya tiene carta: `exists` salvo con `--force`.

  En html, el skill `importar-plantilla-cv` escribe `letter.html` desde la cabecera del diseño
  recreado.
- **Ver y validar**: `cai templates preview <id> --letter` la renderiza con una carta de muestra
  (en `data/cache/previews/`). `cai templates validate <id>` también renderiza la carta. Una
  plantilla cuyo `letter` declarado no existe, o usa variables fuera del contrato de la carta, es
  inválida.
- **Hash**: el del CV no mira `letter.*` ni el bloque `letter:` de `template.yaml`, y el de la
  carta no mira `template.docx|html`. Añadir o retocar la carta no marca los CVs ya renderizados
  como «Plantilla cambiada», ni al revés.
- **Contrato de la carta**: la cabecera del CV (`name`, `subtitle`, `contact.*`, `photo`,
  `accent_color`, `labels`) más `date` (hoy en Europe/Madrid, «3 de octubre de 2026» / «3 October
  2026»), `place` (tu ciudad), `recipient` (vacío si es genérica), `greeting`, `paragraphs[]`
  (textos) y `sign_off`. `subtitle` es el del CV de la oferta o, si no lo hay, tu `headline`.
- **Resolución** (`CoverLetterRenderOptions`, todo `null`/`auto` por defecto):
  - plantilla base: la de la opción > la del render seleccionado del CV > las reglas del perfil;
  - si la base no tiene `letter`, se usa `cover_letter.fallback_template` (`carta-simple`) con el
    aviso `letter_fallback`;
  - color, foto y tamaño de página, los del render seleccionado del CV (o los de las reglas): el
    color se mantiene si el diseño de carta lo admite (o es `free`); si no, el suyo por defecto;
  - una plantilla elegida a mano que no tiene carta da `not_found`.
- **Renders**: van con los del CV en `data/cvs/<job_id>/<document_id>/<render_id>/` como
  `Carta-<Nombre>.pdf|docx`. No registran eventos. El primero que cabe queda seleccionado. La
  fecha es la del día del render: renderizar de nuevo una carta antigua la actualiza.
- **Texto plano**: saludo, párrafos, despedida y nombre, separados por líneas en blanco, en UTF-8
  con saltos `\r\n`. Sin destinatario, fecha ni contacto: es para pegar en un formulario.
- **Formatos**: PDF (y DOCX en motor docx) por render, una página como máximo (`too_long` si no
  cabe), y **texto plano** generado al vuelo desde el contenido, para pegarlo en formularios.
