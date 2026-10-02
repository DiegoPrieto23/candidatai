# Fase 08c · Carta de presentación a medida

## Contexto
Lee `docs/CV_TEMPLATES.md` (§Contrato de variables, §Cartas de presentación), `docs/POLICIES.md`
§1, §4 y §7, `docs/AGENT_INTERFACE.md` (herramientas de la 08c, `CoverLetterContent`,
`CoverLetterRenderOptions`), `docs/DATA_MODEL.md` (`cover_letter_briefs`, eventos de carta),
`docs/DECISIONS.md` ADR-014, ADR-017 y ADR-018, el skill `.agents/skills/generar-carta/SKILL.md`,
el rol `.agents/roles/verificador.md` y el registro de la fase 08 en `docs/ROADMAP.md`.

Requiere la fase 08 completa (08.1, 08.2 y 08.3). No requiere la 08b: si la 08b aún no está
hecha, ella añadirá el diseño de carta a las plantillas html (su punto 7); si ya lo está, hazlo
aquí (punto 4). Rama: `fase/08c-carta-presentacion`.

### Qué deja hecho la fase 08 y aquí se reutiliza
- `documents` ya admite `kind = cover_letter`; `document_renders`, el registro de plantillas, la
  resolución de opciones, el motor docx, el PDF con LibreOffice o Word, `preview.py`, la foto y
  `select_render`.
- `jh templates build-docx` (08.3) guarda en `template.yaml` → `layout.header_paragraphs` qué
  párrafos forman la cabecera del CV importado. Aquí se usa para crear su diseño de carta.

## Objetivo
De una oferta aprobada, una carta de presentación que dice lo que el usuario quiere decir (según
sus indicaciones generales y las de esa oferta), verificada contra el perfil, en texto para pegar
en un formulario y en PDF con la misma cabecera y estilo que su CV.

## Alcance
1. **Indicaciones del usuario**, en dos niveles (las de la oferta mandan sobre las del perfil):
   - **perfil**: bloque opcional `preferences.cover_letter` (`max_words`, `tone`, `sign_off`
     es/en, `instructions`, `avoid`, `default_format`) en `CandidateProfile`,
     `demo/profile.example.yaml` y el skill `actualizar-perfil` (que lo pregunta la primera vez
     que se pide una carta). Un perfil sin el bloque sigue validando;
   - **oferta**: tabla `cover_letter_briefs` (migración de Alembic) con `instructions` y
     `max_words` opcional. Se edita desde la UI o desde el skill (`save_cover_letter_brief`, para
     que lo que el usuario dicte en el chat quede guardado y visible).
2. **Esquemas** (`app/schemas/cover_letter.py`): `CoverLetterContent`, `CoverLetterRenderOptions`
   y la verificación reutiliza `CvVerification`. Cada párrafo lleva `evidence`: ids del perfil,
   `extraction` (lo dice la oferta) o `user` (lo dicen las indicaciones). `save_cover_letter`
   rechaza con `validation_error` una evidencia del perfil que no existe, `user` sin indicaciones
   guardadas, una skill que no está en el perfil, una skill básica que la oferta no pide y más
   palabras que el límite resuelto (oferta > perfil > 180 de `config/policies.yaml`).
3. **Servicio** `app/services/documents/cover_letter.py`: guardar (copia las indicaciones usadas en
   el documento, como respaldo de lo que se verifica), verificar, texto plano, renders y selección.
   Solo en ofertas `approved` o `cv_ready`. Eventos `cover_letter_generated` y
   `cover_letter_verified` (con `passed`), sin cambio de etapa; los renders no registran evento.
4. **Diseño a juego con el CV**:
   - `TemplateMeta` admite `letter: {file}`; el contrato de la carta (`CV_TEMPLATES.md`) comparte
     cabecera con el del CV (`name`, `subtitle`, `contact.*`, `photo`, `accent_color`, `labels`) y
     añade `date`, `place`, `recipient`, `greeting`, `paragraphs[]` y `sign_off`;
   - `clasica-foto` y `ats-simple` traen `letter.docx` (generado por
     `scripts/build_builtin_templates.py`) y hay una integrada `carta-simple` (docx, sin foto,
     acento libre) como respaldo;
   - `jh templates build-letter <id>`: crea `letter.docx` de una plantilla docx del usuario a
     partir de su cabecera (`layout.header_paragraphs`) y del estilo de su cuerpo, y lo valida.
     El skill `importar-plantilla-cv` lo ejecuta al final si la plantilla tiene cabecera;
   - resolución (`CoverLetterRenderOptions`, todo `null`/`auto` por defecto): plantilla, foto y
     color del render **seleccionado** del CV de la oferta; si no hay CV, las reglas del perfil
     (`options.resolve`). Si la plantilla no tiene diseño de carta, `carta-simple` con su color de
     acento y aviso `letter_fallback`;
   - una carta de más de una página da `too_long`;
   - **solo si la 08b ya está hecha**: el motor html renderiza `letter.html`, `moderna-2col` trae
     la suya y `importar-plantilla-cv` crea `letter.html` desde la cabecera del diseño recreado.
5. **Texto plano**: se genera al pedirlo, desde el contenido (no depende de la plantilla ni se
   guarda en disco): saludo, párrafos, despedida y nombre, en UTF-8 con saltos de línea de Windows.
6. **Interfaz para agentes** (MCP y CLI con paridad, `AGENT_INTERFACE.md`):
   `save_cover_letter_brief`, `get_cover_letter`, `save_cover_letter`, `render_cover_letter` y
   `save_cover_letter_verification`. `get_cover_letter` devuelve las indicaciones (las de la oferta
   y `preferences.cover_letter`), el límite de palabras resuelto, el contenido vigente con sus
   evidencias resueltas, la verificación y los renders.
7. **API y UI**, en la ficha de la oferta, sección «Carta de presentación» (desde `approved`; en
   `closed`, solo si la hubo):
   - indicaciones para esta oferta (texto y máximo de palabras opcional) y resumen de las
     generales del perfil; recordatorio de qué pedirle al agente (`generar-carta 42`);
   - con carta: texto con recuento de palabras, estado de la verificación, «Copiar texto»,
     «Descargar TXT», selector de diseño («A juego con el CV» por defecto u otra plantilla con
     diseño de carta), foto, color, «Renderizar», renders con avisos, «Descargar PDF / DOCX» y
     «Usar esta para enviar»;
   - «Editar»: el usuario puede retocar el texto a mano. Se guarda como documento nuevo (actor
     `user`) sin verificación y la UI lo muestra como «Editada por ti»; las comprobaciones del
     código (palabras, skills) siguen aplicándose.
   La API sirve los ficheros solo desde `data/cvs/` (los renders de la carta van en
   `data/cvs/<job_id>/<document_id>/<render_id>/Carta-<Nombre>.pdf`).
8. **Skills y roles** (en `.agents/` y regenerando con `scripts/sync_agents.py`): revisa
   `generar-carta` con lo implementado, amplía `verificador` para cartas (herramientas
   `get_cover_letter` y `save_cover_letter_verification`) y deja `preparar-candidatura`
   delegando la carta en `generar-carta`.

## Fuera de alcance
Enviar la carta o adjuntarla en un formulario (fase 11). Mostrarla en el paquete de candidatura
(fase 10). Importar un diseño de carta propio distinto del de su CV.

## Criterios de aceptación
- Tests: un párrafo con evidencia inexistente, `user` sin indicaciones o más palabras que el límite
  se rechaza; las indicaciones de la oferta mandan sobre las del perfil; render de la carta con
  `clasica-foto` usando el color y la foto del render seleccionado del CV; plantilla sin diseño de
  carta → `carta-simple` y `letter_fallback`; `build-letter` con un Word ficticio de cabecera en
  tabla; el TXT respeta tildes y saltos de línea; editar a mano crea un documento sin verificación;
  paridad MCP ↔ CLI de las herramientas nuevas; tests de frontend de la sección.
- Prueba manual: con indicaciones en el perfil y otras en la oferta (p. ej. «menciona que uso su
  producto desde 2023» y «máximo 150 palabras»), `/generar-carta` → carta verificada que las
  cumple → en la UI, PDF a juego con el CV seleccionado y TXT copiado sin errores de codificación.

## Al terminar
Actualiza `docs/ROADMAP.md` (fila 08c y registro), `README.md` y los docs que hayan cambiado.
Propón el mensaje de commit.
