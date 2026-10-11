# Fase 14 · Huecos de skills y vocabulario

Plan 13-22 (`docs/ROADMAP.md`). Rama `fase/14-huecos-skills`. Inspirada en `upskill` (AI Job
Search y career-ops) y en un hallazgo con datos reales: la mayoría de las skills «ausentes» de las
ofertas abiertas eran nombres que no casaban («data warehousing», «cloud», «modelado semántico»,
«orquestación de workflows») y no huecos de verdad.

## Contexto
Lee `docs/POLICIES.md` §1-§2, `backend/app/services/matching/` (desglose `must_have` /
`nice_to_have`, `scoring_key`), `config/skill_aliases.yaml` y `config/title_aliases.yaml`.

## Objetivo
Que el score mida experiencia y no vocabulario, y que los huecos reales se conviertan en un plan
de formación.

## Alcance
1. **`services/skill_gaps.py`**: agrega las skills ausentes (obligatorias y deseables, por
   separado) de las ofertas abiertas y de las aprobadas/enviadas de los últimos N días, con
   frecuencia, peso (obligatoria > deseable, score de la oferta) y ejemplos de ofertas. Normaliza
   con `fold` y los alias existentes.
2. **Página «Skills»** (o pestaña en Embudo): tabla de ausentes por frecuencia con tres acciones:
   - **«Es lo mismo que…»**: elige una skill del perfil y añade el sinónimo a
     `config/skill_aliases.yaml` (escritura segura del YAML, conservando comentarios; el
     `scoring_key` cambia y el worker recalcula);
   - **«La tengo»**: abre el agente (botón ADR-024) con `actualizar-perfil` para añadirla con su
     nivel y dónde la usó;
   - **«No la tengo»**: la marca como hueco real (tabla nueva `skill_gap_marks` con migración).
3. **Skill `plan-formacion`** (nuevo, en `.agents/skills/`): con los huecos reales y su frecuencia,
   busca en la web recursos (cursos, certificaciones, documentación oficial), estima tiempo y
   propone un orden; guarda el plan como Markdown en `data/documentos/plan-formacion.md`. Sin
   inventar: cada recurso con su URL. También valora un curso o un proyecto concreto que el
   usuario proponga frente a los huecos (como `training`/`project` de career-ops).
4. **Botón** «Plan de formación» que lo lanza (ADR-024) y acción en `agent_launch.ACTIONS`.
5. **Docs**: `POLICIES.md` §2 (alias desde la UI), `AGENTS_COMPAT.md`, README de `config/`.

## Fuera de alcance
Cambiar pesos del score. Proponer alias automáticamente sin confirmación del usuario.

## Criterios de aceptación
- Agregación con tests sobre matches sintéticos.
- Añadir un alias desde la UI recalcula y cambia el score de las ofertas afectadas (test).
- La escritura del YAML conserva comentarios y orden (test de ida y vuelta).
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde.
