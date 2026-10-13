# Fase 23 · CandidatAI: nombre y logo, identificadores en inglés, barra lateral, UI bilingüe e
# instalación fácil

Rama `fase/23-candidatai`. Seis subfases, cada una con su encargo y un commit en la misma rama, en
este orden: 23.1 → 23.2 → 23.3 → 23.4 → **23.6 → 23.5** (la 23.5, la de los medios, va la última
para que las capturas salgan con la UI traducida y con el logo nuevo). Decisiones del usuario
(2026-10-12) tras la comparativa con AI Job Search y career-ops (`docs/COMPARATIVA.md`) y la página
de GitHub nueva.

## Objetivo
Que la herramienta tenga un nombre y un logo propios y coherentes en todas partes, que se pueda
instalar y usar sin saber de backend ni de frontend, en inglés o en español, y que su navegación
aguante las 13 páginas que ya tiene.

## Decisiones tomadas con el usuario
- **Nombre:** «Job Hunter» pasa a **CandidatAI** (*candidato* + *AI*; también *candid*: un CV que
  no inventa nada). Comprobado el 2026-10-12: sin producto con ese nombre y libre en PyPI y npm.
- **Renombrado completo, también lo técnico y sin alias:** la CLI `jh` pasa a `cai`, `jh-mcp` a
  `cai-mcp`, `JH_*` a `CAI_*` (las `JH_*` se siguen leyendo como respaldo), el servidor MCP
  `jobhunter` a `candidatai` y el logo «JH» a «CA». Sin alias de `jh`: el usuario es el único
  usuario y se actualiza lo que haya fuera del repositorio.
- **Skills y roles en inglés:** son identificadores (regla de `AGENTS.md`). Sus descripciones, la
  UI y los docs siguen en español.
- **Barra lateral** con grupos en vez de la fila de 13 enlaces.
- **Instalación:** un comando de PowerShell que instala lo necesario y deja un acceso directo; al
  abrirlo arranca todo en un solo proceso y se abre el navegador. Sin Node para quien solo la usa.
- **README:** fuera la sección «Compared with similar projects» (la comparativa sigue enlazada en
  la tabla de documentación).
- **Logo:** el monograma «CA» es provisional; la 23.5 diseña un logo de verdad (el usuario elige
  entre propuestas) y lo aplica en la UI, el favicon, la extensión, el icono de Windows y el README.
- **UI en inglés y en español** con un selector de idioma junto al del tema (decisión del usuario
  tras la 23.3, 2026-10-12).

## Subfases
| | Encargo | Resultado visible |
|---|---|---|
| 23.1 | `prompts/23.1-renombrado.md` | Todo dice CandidatAI; `cai` en vez de `jh`; MCP `candidatai`; repositorio renombrado |
| 23.2 | `prompts/23.2-skills-ingles.md` | `/generate-cv 42`, `/prepare-interview 42`…; roles `writer`, `verifier`… |
| 23.3 | `prompts/23.3-barra-lateral.md` | Navegación lateral agrupada, plegable y con cajón en el móvil |
| 23.4 | `prompts/23.4-instalacion.md` | `cai start`, `install.ps1`, acceso directo y releases con la UI compilada |
| 23.6 | `prompts/23.6-idioma-ui.md` | Toda la UI en inglés o en español, con un selector junto al del tema |
| 23.5 | `prompts/23.5-medios-readme.md` | Logo nuevo; banner, capturas (en los dos idiomas), GIF y vídeo; README sin la comparativa |

## Criterios de aceptación de la fase
- `git grep -i "job hunter\|jobhunter\|\bjh\b"` solo encuentra el historial (`docs/ROADMAP.md`,
  `docs/RESUMEN_FASES.md`, `prompts/` anteriores) y las compatibilidades documentadas (`JH_*` como
  respaldo, `data/jobhunter.db` heredada).
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde, `pnpm typecheck && pnpm test` en
  verde, `docs/ROADMAP.md` y `docs/pruebas/PENDIENTES.md` al día.
