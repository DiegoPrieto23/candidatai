# Plantillas de CV

El CV se genera en dos pasos independientes (ADR-014):

1. **Contenido** (`CvContent`): lo redacta el agente para cada oferta a partir de tu perfil. No
   sabe nada de colores, columnas ni fotos.
2. **Presentación**: el código combina ese contenido con una **plantilla** y unas **opciones de
   render** (foto, color, secciones…). Es determinista y no usa IA: cambiar de estilo o quitar la
   foto no gasta cuota.

Un mismo contenido puede tener varios renders (por ejemplo, uno sin foto para un ATS y otro con
foto para enviar por email), y tú marcas cuál se envía.

## Dónde viven

| Carpeta | Qué contiene | En git |
|---|---|---|
| `templates/<id>/` | Plantillas integradas, genéricas y sin datos personales | Sí |
| `data/templates/<id>/` | Tus plantillas, creadas a partir de tus CVs o de diseños que tengas | No |
| `data/uploads/` | Los ficheros originales que subes para convertirlos en plantilla | No |
| `data/photo.<ext>` | Tu foto original, en cualquier formato de imagen | No |

Si una plantilla tuya tiene el mismo `id` que una integrada, gana la tuya.

## Estructura de una plantilla

```
<id>/
  template.yaml        metadatos (obligatorio)
  template.docx        motor docx: Word con marcadores docxtpl
  template.html        motor html: Jinja2 + HTML
  style.css            motor html
  fonts/               fuentes locales opcionales (.ttf, .otf, .woff2)
  source.<ext>         original del que se creó (solo en data/, nunca en templates/)
  preview.pdf|png      generadas con el perfil demo (no se editan a mano)
```

### `template.yaml`

```yaml
id: moderno-azul                  # igual que la carpeta; minúsculas, números y guiones
name: Moderno azul
engine: docx                      # docx | html
origin: user                      # builtin | user
source_file: source.pdf           # solo en plantillas del usuario
description: Dos columnas, barra lateral azul con contacto y aptitudes.
tags: [moderno, tech]
layout:
  columns: 2
  uses_tables: true               # tablas o cuadros de texto para maquetar
ats_friendly: false               # true solo si: 1 columna, sin tablas ni cuadros de texto de maquetación,
                                  # sin datos clave en cabecera o pie, y texto seleccionable en orden lógico
photo:
  supported: true
  shape: circle                   # circle | square | rounded
  size_mm: 32
page:
  size: A4                        # A4 | Letter
  max_pages: 1
capacity:                         # orientativo, para que el redactor ajuste la extensión
  summary_chars: 450
  experience_bullets: 9
  skill_groups: 4
sections: [summary, experience, projects, education, certifications, skills, languages]
options:
  accent_color:                   # opcional; solo si la plantilla usa {{ accent_color }}
    default: "#1F4E79"
    choices: ["#1F4E79", "#2E7D32", "#6A1B9A", "#37474F"]
fonts: [Lato, Source Sans 3]      # las que usa; se comprueba que estén disponibles al renderizar
languages: [es, en]
```

`jh templates validate <id>` comprueba este fichero contra el modelo Pydantic `TemplateMeta` y
que el `template.*` solo usa variables del contrato.

## Contrato de variables

Lo que recibe cualquier plantilla, en los dos motores:

| Variable | Contenido |
|---|---|
| `name`, `subtitle`, `summary` | Texto |
| `contact.email`, `contact.phone`, `contact.city`, `contact.linkedin`, `contact.github` | Texto; vacíos si no aplican |
| `photo` | Imagen ya recortada con la forma de `photo.shape`, o vacío si esta vez no lleva foto |
| `experience[]` | `role`, `company`, `city`, `start`, `end`, `bullets[]` |
| `projects[]` | `name`, `date`, `bullets[]` |
| `education[]` | `title`, `center`, `start`, `end`, `detail` |
| `certifications[]` | `name`, `issuer`, `date` |
| `skills[]` | `group`, `items[]` (objetos, no diccionarios: `{{ s.items }}` funciona) |
| `languages[]` | `language`, `level` |
| `labels.*` | Títulos de sección en el idioma del CV (`labels.experience` = «Experiencia» / «Experience») |
| `accent_color` | Color elegido, si la plantilla lo admite |
| `show.<sección>` | `false` si esa sección se ha ocultado para esta oferta o está vacía (así no quedan títulos sin contenido) |

Las fechas llegan ya formateadas en el idioma del CV: `start` = «mar. 2024» / «Mar 2024» y
`end` = «actualidad» / «Present» si sigue. El contacto lo pone el código desde el perfil (el
agente no lo ve). `education[].detail` va vacío de momento: el perfil no tiene ese campo.

### Motor docx (docxtpl)
- Variables `{{ subtitle }}`; bucles de párrafo `{%p for e in experience %}` … `{%p endfor %}`;
  filas de tabla `{%tr for … %}`; condicionales `{%p if photo %}`.
- La foto es un `InlineImage` y se coloca donde esté `{{ photo }}`.
- **No escribas los marcadores a mano en Word**: Word los parte en fragmentos y dejan de
  funcionar. Usa el skill `importar-plantilla-cv`, que marca la plantilla con
  `jh templates build-docx`: el código fusiona los fragmentos de cada párrafo e inserta cada
  marcador de una pieza.
- Genera DOCX y PDF (con LibreOffice o Word).

### Motor html (fase 08b)
- Jinja2 con autoescape; se imprime a PDF con Chromium (Playwright) sin red y sin JavaScript.
- Solo recursos locales: `style.css` y `fonts/`. Al validar se eliminan `<script>`, atributos
  `on*`, `<iframe>` y cualquier URL remota.
- Solo genera PDF. Si un portal exige Word, la UI lo avisa y propone una plantilla docx.

## Opciones de render por oferta (`CvRenderOptions`)

```yaml
template_id: null          # null = según reglas
photo: auto                # auto | include | exclude
accent_color: null         # null = el de la plantilla
max_pages: null            # null = el de la plantilla
hidden_sections: []        # p. ej. [projects]
page_size: null            # null = el de la plantilla
```

Cómo se resuelve lo que queda en `null` o `auto`:

1. **Plantilla**: la opción explícita, si la hay; si no, la primera regla de
   `preferences.cv.template_rules` que encaje con la oferta; si no, `preferences.cv.default_template`;
   si no, la integrada `ats-simple`.
2. **Foto** (`auto`): se incluye si la plantilla la admite, existe `data/photo.*` y
   `preferences.cv.photo_policy` la permite para el país de la oferta.
3. Lo demás, lo que diga la plantilla.

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

## Plantillas integradas

| id | Motor | Fase | Estilo |
|---|---|---|---|
| `ats-simple` | docx | 08 | Una columna, sin foto, tipografía estándar. La opción segura para portales con ATS |
| `clasica-foto` | docx | 08 | Una columna con cabecera y foto circular, sobria |
| `moderna-2col` | html | 08b | Dos columnas con barra lateral y color de acento configurable |
