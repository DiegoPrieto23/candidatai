---
name: generar-carta
description: Redacta y verifica la carta de presentación de una oferta aprobada de Job Hunter siguiendo las indicaciones del usuario (generales y de esa oferta). Úsalo cuando se pida una carta de presentación o cover letter.
argument-hint: '[job_id] [indicaciones para esta carta]'
allowed-tools: mcp__jobhunter__get_cover_letter mcp__jobhunter__get_extraction mcp__jobhunter__get_profile mcp__jobhunter__get_cv_content
---

<!-- GENERADO por scripts/sync_agents.py desde .agents/skills/generar-carta/SKILL.md. No editar a mano: edita la fuente y regenera. -->

Sigue `docs/POLICIES.md` §1, §4 y §7, y `docs/CV_TEMPLATES.md` §Cartas de presentación.
Argumentos: `job_id` y, opcionalmente, indicaciones para esta carta («máximo 150 palabras»,
«menciona que uso su producto desde 2023», «en inglés», «más formal»…).

## 1. Reunir las indicaciones
1. `get_cover_letter(job_id)`: indicaciones de la oferta (`brief`), las generales del perfil
   (`preferences`), el límite de palabras resuelto y la carta anterior, si la hay.
2. Si los argumentos o el chat traen indicaciones nuevas, guárdalas con
   `save_cover_letter_brief` (junto con las que ya hubiera, si siguen valiendo), para que queden
   visibles en la UI y respalden lo que cuentes. Si contradicen las del perfil, mandan las de la
   oferta; dilo en una línea.
3. Si no hay indicaciones en ningún sitio, pregunta una sola vez, en un mensaje: qué quiere
   destacar, por qué le interesa esta empresa (si no lo sabes, no lo inventes) y tono. Si no
   quiere dar ninguna, sigue con los valores por defecto de §7. Si el perfil no tiene
   `preferences.cover_letter`, propón al final guardarlas con `actualizar-perfil`.

## 2. Redactar
1. `get_extraction(job_id)`, `get_profile()` y, si hay CV, `get_cv_content(job_id)` para no
   contradecirlo y reforzar sus mismos logros.
2. Escribe un `CoverLetterContent` (`docs/AGENT_INTERFACE.md`) en el idioma de la oferta, salvo
   indicación:
   - cada párrafo con sus `evidence`: ids del perfil para tus logros, `extraction` para lo que dice
     la oferta y `user` para lo que el usuario contó en sus indicaciones;
   - de la empresa, solo lo que dice la oferta o el usuario; nada buscado ni supuesto;
   - sin clichés (§7), sin salario y dentro del límite de palabras;
   - el contacto, la fecha y el nombre los pone el código.
3. `save_cover_letter(job_id, content)` sin `render_options` salvo que el usuario pida otro diseño
   (por defecto va a juego con su CV). Si lo rechaza, corrige exactamente lo que dice y reintenta
   (máximo 3 veces).

## 3. Verificar
Delega en el rol `verificador` con el `document_id` de la carta. Tiene que ser una ejecución
distinta de la tuya. Si falla, corrige los `blocker` y vuelve a guardar; máximo 2 vueltas, después
para y enseña los problemas.

## 4. Resumen
Enseña el texto de la carta, el número de palabras, qué indicaciones has seguido (y cuál no, y por
qué), el resultado de la verificación y los avisos del render (p. ej. `letter_fallback`).
Recuerda que en la ficha de la oferta puede copiar el texto, descargar TXT o PDF, cambiar el
diseño, la foto o el color sin agente, retocar el texto a mano y marcar la carta para enviar.
**No envíes nada ni abras formularios.**
