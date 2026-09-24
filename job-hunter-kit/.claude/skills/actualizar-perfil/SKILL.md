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

**Si ya existe:** aplica solo los cambios que se pidan. Para un logro nuevo, pregunta la métrica
real si no la dan; si no hay métrica, se escribe sin ella.

**Siempre:**
- Nada inventado ni "mejorado": si algo es ambiguo, pregunta.
- Ids estables (`exp-<empresa>`, `a1`, `a2`…). No renumeres los existentes: los CVs antiguos los citan.
- Al terminar, ejecuta `uv run --directory backend jh profile validate`, corrige los errores y
  luego `uv run --directory backend jh profile import`. Enseña el resultado de
  `uv run --directory backend jh profile diff`.
- Recuerda que importar una versión nueva recalcula los scores de todas las ofertas.
