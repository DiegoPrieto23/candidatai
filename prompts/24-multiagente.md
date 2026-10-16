# Fase 24 · Varios agentes: open-source, gratuitos y a elegir desde la UI

Rama `fase/24-multiagente`. Seis subfases, cada una con su encargo y un commit en la misma rama, en
este orden: 24.1 → 24.2 → 24.3 → 24.4 → 24.5 → 24.6. **Una subfase por sesión** (contexto limpio,
plan antes de código): están cortadas para que ninguna reviente una sesión de Claude Code.
Decisión del usuario (2026-10-16) tras revisar `docs/COMPARATIVA.md`: imitar a
[career-ops](https://github.com/career-ops-hq/career-ops) en lo que más nos saca, que es la
cantidad de agentes y modelos que admite y lo fácil que es cambiar entre ellos.

## Contexto
Lee `docs/COMPARATIVA.md` (sección «Agentes y modelos»), `docs/AGENTS_COMPAT.md`,
`docs/DECISIONS.md` ADR-001, ADR-010, ADR-011, ADR-012, ADR-024 y ADR-032, `.agents/manifest.yaml`,
`scripts/sync_agents.py`, `backend/app/services/agent_launch.py`, `agent_runs.py`,
`agent_runner.py` y `agent_output.py`.

## Objetivo
Que CandidatAI se pueda usar con **varios agentes de IA, algunos open-source y con modelos
gratuitos o locales**, que el usuario vea en la UI cuáles tiene, qué sabe hacer cada uno y **cambie
de agente (y de modelo) en un clic**, globalmente o por acción, sin perder ninguna de las garantías
que hoy dependen del código.

## Decisiones tomadas con el usuario
- **Se mantiene el ADR-001: la app no llama a ningún LLM.** Los modelos gratuitos o locales
  (Ollama, LM Studio, OpenRouter `:free`…) se usan **a través de agentes open-source** que ya saben
  hablar con ellos (OpenCode, Qwen Code, Codex con `--oss`). Que la app llame a un modelo queda
  fuera de esta fase y solo se reconsiderará con los datos de la matriz de la 24.6.
- **Agentes de la fase**, por este orden de prioridad:

  | Agente | Licencia | Por qué |
  |---|---|---|
  | Claude Code | cerrado | Referencia; cerrar la prueba con MCP que sigue pendiente |
  | Codex | Apache-2.0 | Ya hay configuración generada; con `--oss` usa modelos locales por Ollama |
  | **OpenCode** | MIT | Lee `AGENTS.md` y `.agents/skills/` de serie, habla MCP, limita herramientas por agente y funciona con Ollama, LM Studio, OpenRouter o cualquier API compatible con OpenAI |
  | **Qwen Code** | Apache-2.0 | Open-source, MCP con `includeTools`/`excludeTools`; su plan gratuito cerró el 15/04/2026, así que se usa con modelos locales o claves propias |
  | Antigravity CLI | cerrado | Sustituye a Gemini CLI en cuentas gratuitas; plan gratuito; lee `AGENTS.md` y `.agents/skills/` |
  | Cursor, Copilot CLI, Pi, Goose… | varias | Solo en el registro como «compatibles vía `AGENTS.md`, sin probar» (nivel C), sin configuración generada |

- **Gemini CLI deja de figurar como compatible**: desde el 18/06/2026 no funciona con cuentas
  gratuitas ni Pro. `GEMINI.md` pasa a ser un archivo vacío a propósito, como en career-ops, porque
  Antigravity lee `AGENTS.md` y `GEMINI.md` y este manda.
- **Las preferencias de cada persona (agente por defecto, por acción, modelos) viven en la base de
  datos (`data/`)**, nunca en el repositorio ni en la configuración generada, que se commitea.
- **El segundo plano solo se abre a un agente si se puede comprobar su techo de herramientas** con
  su binario real, como se hizo con Claude Code en la fase 19 (ADR-032). Si no, ese agente solo se
  lanza en terminal, y la UI explica por qué.
- **Los formatos de configuración de cada agente cambian cada pocas semanas.** Antes de escribir un
  emisor o un comando, el agente que implemente comprueba el formato en la documentación oficial y
  en el binario instalado, y anota en `docs/AGENTS_COMPAT.md` la versión y la fecha comprobadas.
  Los ejemplos de estos encargos son orientativos.

## Subfases
| | Encargo | Resultado visible |
|---|---|---|
| 24.1 | `prompts/24.1-registro-agentes.md` | `cai agents list` y `cai agents doctor`: qué agentes hay, cuáles están instalados, qué saben hacer y si son open-source; un único lector del manifiesto |
| 24.2 | `prompts/24.2-esquemas-errores.md` | `cai schema` y `get_schema`; errores de validación que dicen qué campo arreglar y cómo; más fácil para modelos pequeños |
| 24.3 | `prompts/24.3-agentes-nuevos.md` | Configuración generada para OpenCode, Qwen Code y Antigravity; Codex con modelos locales; Gemini CLI fuera |
| 24.4 | `prompts/24.4-elegir-agente.md` | Página «Agente» con los agentes, sus capacidades y un selector global y por acción; «con Claude Code ▾» en cada botón |
| 24.5 | `prompts/24.5-segundo-plano-multiagente.md` | «En segundo plano» también con OpenCode (y con Codex o Qwen Code si su techo se puede comprobar) |
| 24.6 | `prompts/24.6-modelos-gratis-matriz.md` | Guía de modelos gratuitos y locales, diagnóstico de Ollama, niveles de gasto y matriz probada por agente y modelo |

Dependencias: la 24.1 es la base de todas. La 24.2 no depende de la 24.1 y se puede adelantar si
conviene. La 24.4 necesita la 24.3 para tener algo que elegir. La 24.6 mide lo que dejan las
anteriores.

## Fuera de alcance
- Que la app llame a un modelo (ADR-001, regla dura 1).
- Ejecutar varias ejecuciones en segundo plano a la vez (sigue una sola; se pueden encolar con
  agentes distintos).
- Conectores de ATS nuevos, `expand`, señales de oferta dudosa y el resto de «Lo que nos falta» de
  `docs/COMPARATIVA.md`: van después de esta fase.
- macOS y Linux: los botones de terminal siguen siendo solo de Windows. El registro, los emisores y
  el segundo plano no deben suponer Windows.

## Criterios de aceptación de la fase
- Con solo OpenCode y un modelo local instalados (sin Claude Code ni Codex), se puede procesar,
  valorar y generar el CV de las 5 ofertas de `evals/compat/` desde la UI. El resultado medido
  queda en la matriz de `docs/AGENTS_COMPAT.md`.
- Cambiar de agente por defecto o para una acción se hace desde la UI y se respeta en la siguiente
  ejecución, en terminal y en segundo plano.
- Ningún agente obtiene más herramientas de las que tenía su acción en la fase 19. Hay un test por
  agente con segundo plano.
- README (en los dos idiomas), `docs/AGENTS_COMPAT.md` y `docs/COMPARATIVA.md` dicen la verdad sobre
  cada agente: probado, configurado sin probar o solo compatible vía `AGENTS.md`.
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde, `pnpm typecheck && pnpm test` en
  verde, y `docs/ROADMAP.md`, `docs/RESUMEN_FASES.md` y `docs/pruebas/PENDIENTES.md` al día.
