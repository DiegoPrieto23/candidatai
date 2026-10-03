---
name: actualizar-perfil
description: Crea o actualiza data/profile.yaml (la fuente de verdad del candidato) a partir de su CV o de lo que cuente, lo valida y lo versiona. Úsalo cuando se quiera añadir experiencia, skills, logros o historias, o crear el perfil por primera vez.
allowed-tools: Read Bash(uv run --directory backend jh profile *)
---

<!-- GENERADO por scripts/sync_agents.py desde .agents/skills/actualizar-perfil/SKILL.md. No editar a mano: edita la fuente y regenera. -->

Sigue `docs/POLICIES.md` §1 y §4. El formato de referencia es `demo/profile.example.yaml`.
Los comandos se ejecutan desde la raíz del repo.

**Si `data/profile.yaml` no existe:**
1. Ejecuta `uv run --directory backend jh profile init`.
2. Pide el CV. Lo más cómodo es en PDF (si tu agente puede leerlo) o como texto pegado.
3. Rellena el perfil sección a sección. Pregunta en bloques cortos lo que el CV no dice: niveles
   F/C+/C/B de cada skill, métricas de los logros, NDAs, preferencias de búsqueda, política de
   foto e historias STAR (al menos 4).
   En `seniority_target`, pregunta **todos** los niveles a los que se presentaría, por arriba y
   por abajo (p. ej. «¿y puestos junior?, ¿y senior?»): los que no estén se descartan solos. No
   lo deduzcas de sus años de experiencia.

**Si ya existe:** aplica solo los cambios que se pidan. Para un logro nuevo, pregunta la métrica
real si no la dan; si no hay métrica, se escribe sin ella.

**Secciones que no encajan en las demás** (voluntariado, premios, publicaciones, cursos…): van en
`extra_sections`, con `id`, `title` en es y en, e `items` (`id`, `text` y `date` opcional). Salen
en el CV tal cual, así que escribe cada item como debe leerse. Si vienes de `importar-plantilla-cv`
con una lista de lo que el CV subido tiene y el perfil no, propón dónde va cada cosa y confírmalo
antes de escribirlo.

**Indicaciones para las cartas** (`preferences.cover_letter`, opcional): la primera vez que se
pide una carta (te lo dirá `generar-carta`), pregunta en un solo mensaje:
- extensión máxima (por defecto 180 palabras);
- tono;
- despedida en español y en inglés;
- qué quiere contar siempre: motivación, cómo llegó a su campo… Va en `instructions`. Es lo único
  que la carta puede citar como `user`, así que escríbelo con sus palabras;
- qué evitar siempre (`avoid`);
- si suele enviarla como texto o en PDF (`default_format`).

No rellenes nada que no diga. Las indicaciones de cada oferta mandan sobre estas y se guardan con
`save_cover_letter_brief`, no aquí.

**Siempre:**
- Nada inventado ni "mejorado": si algo es ambiguo, pregunta.
- Ids estables (`exp-<empresa>`, `a1`, `a2`…). No renumeres los existentes: los CVs antiguos los citan.
- Al terminar, ejecuta `uv run --directory backend jh profile validate`, corrige los errores y
  luego `uv run --directory backend jh profile import`. Enseña el resultado de
  `uv run --directory backend jh profile diff`.
- Recuerda que importar una versión nueva recalcula los scores de todas las ofertas.
