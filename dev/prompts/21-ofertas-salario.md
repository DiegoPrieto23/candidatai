# Fase 21 · Ofertas recibidas y salario

Plan 13-22 (`dev/ROADMAP.md`). Rama `fase/21-ofertas-salario`. Inspirada en la investigación
salarial, `salary-gap`, `offer-prep` y los guiones de negociación de career-ops.

## Contexto
Lee `docs/POLICIES.md` §4 (el salario nunca se propone ni se deduce; `private` nunca sale por la
MCP), `services/profile.py` (`public_view`), la extracción (`salary`) y el evento `offer_received`.

## Objetivo
Decidir bien cuando llega una oferta: compararla, ver la diferencia con lo que pides y preparar la
negociación, sin exponer tus cifras al agente.

## Alcance
1. **Datos de la oferta recibida** en la ficha (UI, solo usuario): salario fijo y variable,
   beneficios, modalidad, fecha de respuesta. Tabla `received_offers` (migración).
2. **Comparación** (código, sin agente): tabla de ofertas recibidas lado a lado y diferencia con
   `private.salary_floor` y con el rango publicado en la extracción. Se calcula en la API y solo
   lo ve la UI; el agente nunca recibe `private`.
3. **Skill `preparar-negociacion`**: con la oferta recibida (sin tus cifras privadas, salvo que tú
   las escribas en el chat), prepara argumentos desde el perfil, preguntas y un guion; revisa el
   contrato cláusula a cláusula si lo pegas (no es asesoramiento legal).
4. **Datos de mercado propios**: `data/documentos/salarios.csv` opcional (fuentes que tú recojas)
   para dar contexto; nunca se inventan rangos.
5. **Docs**: `POLICIES.md` §4.

## Fuera de alcance
Buscar salarios en webs desde el código. Recomendar una cifra.

## Criterios de aceptación
- Test de que ninguna herramienta MCP devuelve `private` ni las cifras de `received_offers`
  marcadas como privadas.
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde.
