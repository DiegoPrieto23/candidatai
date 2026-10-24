# Fase 28 · Repo público: raíz limpia, release, medios nuevos y lanzamiento

Rama `fase/28-lanzamiento-repo`. Cinco subfases, cada una con su encargo y su commit (o commits) en la
misma rama, en este orden: 28.1 → 28.2 → 28.3 → 28.4 → 28.5. **Una subfase por sesión.** Va después de
la 27: **las capturas y vídeos de la 28.3 enseñan la UI, así que no se rehacen hasta que la 27.4, la
27.5 y la 27.6 estén fusionadas.** Petición del usuario (2026-10-23).

## Objetivo
Que CandidatAI sea un repositorio que cualquiera pueda **instalar, entender en un minuto y
recomendar**, y que se dé a conocer. El argumento de venta frente a AI Job Search y career-ops es
cierto y comprobable: **tiene interfaz**, instalador, verificación en código y un recorrido completo
(ofertas → CV → candidatura → seguimiento) que se usa sin editar ficheros. El repo tiene que
demostrarlo sin que el visitante tenga que leer nada de lo interno.

## Lo que se ha comprobado antes de escribir esto (2026-10-23)
- **El repo ya es público.** Por eso la auditoría de privacidad (28.1) va primero, no al final.
- **No existe ninguna release ni etiqueta** (`git tag` y `git ls-remote --tags` salen vacíos), y
  `install.ps1` e `install.sh` descargan `releases/latest/download/candidatai.zip`. Hoy, el comando de
  instalación del README **devuelve 404**. Es el bloqueo número uno y no se promociona nada hasta
  resolverlo.
- La raíz tiene ~35 entradas, y GitHub ordena las carpetas primero y alfabéticamente: lo primero que
  ve el visitante son `.agents`, `.claude`, `.codex`, `.github`, `.opencode`, `.qwen`, `backend`,
  `config`… y `prompts` y `evals`. GitHub **no permite ocultar carpetas**: lo que está en git se ve.
  La única palanca es **moverlas** (y marcar lo generado con `.gitattributes`).
- El historial pesa ~55 MiB (los GIF y vídeos de `docs/img` y `docs/video` son ~20 MB). No se reescribe
  el historial por eso; los medios nuevos no deben engordar el repo.
- El árbol actual no contiene secretos (`.env` y `data/` nunca se commitearon, las pruebas usan datos
  ficticios), pero **el historial completo no se ha escaneado** (el análisis completo se agotó por
  tiempo) y los commits llevan el correo personal del autor.
- Frente a la competencia, según un artículo de terceros (sin verificar contra GitHub), AI Job Search
  ronda las 19.500 estrellas y llegó al nº 1 de tendencias en julio de 2026 con un gancho simple («haz
  fork, ejecuta `/setup`»), un post personal en LinkedIn y vídeos. **Comprueba la cifra y la fecha en
  GitHub antes de citar nada.**

## Decisiones tomadas con el usuario
- **Público: inglés primero, español a la vez.** El README en inglés es la portada; `README.es.md`
  sale el mismo día con el mismo contenido.
- **La raíz se limpia moviendo lo interno a `dev/`** (encargos de fase, pruebas manuales, ROADMAP,
  ADR y resúmenes). Las carpetas de agentes (`.claude`, `.agents`, `.codex`, `.qwen`, `.opencode`)
  **se quedan en la raíz** porque los agentes las buscan ahí.
- **Comparativa honesta y visible** en el README (frente a AI Job Search y career-ops), con fecha y
  fuentes, incluyendo lo que ellos hacen mejor.
- **Rehacer todos los medios** (capturas, GIF y vídeos, en inglés y español) y que el README
  **mencione todas las funcionalidades** que hay, con una comprobación automática para que no vuelva a
  quedarse atrás.

## Subfases
| | Encargo | Resultado visible |
|---|---|---|
| 28.1 | `dev/prompts/28.1-auditoria-y-release.md` | Historial y repo auditados, **primera release `v0.1.0`** y los instaladores probados contra ella |
| 28.2 | `dev/prompts/28.2-raiz-limpia.md` | Sin `dev/prompts/` ni documentos internos en la raíz: viven en `dev/`; nada se rompe (enlaces, CI, skills) |
| 28.3 | `dev/prompts/28.3-medios-y-funcionalidades.md` | Capturas, GIF y vídeos nuevos en los dos idiomas y un README que recoge todas las funcionalidades |
| 28.4 | `dev/prompts/28.4-portada-y-github.md` | Portada con gancho, «Por qué CandidatAI», guía para quien no es técnico, y ajustes de GitHub (descripción, temas, imagen social, plantillas) |
| 28.5 | `dev/prompts/28.5-lanzamiento.md` | Borradores de publicación (Show HN, Reddit, X, LinkedIn…), listas «awesome» y plan de respuesta |

## Riesgos que la fase tiene que vigilar
- **Prometer de más.** La promesa «para quien no es técnico» tiene una fricción real: hace falta un
  agente de IA (Claude Code, Codex…) instalado y una terminal para algunos botones. Se cuenta
  tal cual, con una guía paso a paso, en vez de esconderla (28.4).
- **Cifras que caducan.** El README tiene un distintivo fijo de «2.827 tests» y listas de agentes
  «probados». Todo número va comprobado por un script o se quita.
- **Madurez.** macOS y Linux son nuevos y OpenCode y Qwen Code están «configurados, sin probar con un
  modelo». El lanzamiento lo dice igual que el README (la honestidad es parte del producto).
- **LinkedIn.** Las condiciones de LinkedIn prohíben el acceso automatizado; el aviso del README se
  mantiene visible en toda la difusión.
- **Cambiar rutas de golpe.** Mover carpetas toca cientos de referencias (ver 28.2); se hace con
  `git mv`, un script y `scripts/check_links.py`.

## Fuera de alcance
Reescribir el historial de git, publicar paquetes nativos (`.exe` firmado, `.dmg`, Homebrew), comprar
publicidad, traducir a más idiomas y un sitio web propio (se valora una página de GitHub Pages en 28.4,
sin comprometerla).

## Criterios de aceptación de la fase
- Existe la release `v0.1.0` y `install.ps1`, `install.sh` y Docker funcionan desde cero contra ella.
- La raíz ya no muestra `dev/prompts/` ni documentos internos (lo interno vive en `dev/`) y ningún enlace
  del README ni de las guías está roto (`scripts/check_links.py` en verde), con la CI en verde en los tres sistemas.
- Cada página de la UI y cada skill aparece en el README y tiene captura o, al menos, mención, y un
  script lo comprueba.
- Medios nuevos en inglés y español, sacados de la demo, sin datos personales.
- Los borradores de lanzamiento están listos para que el usuario los publique; nada se publica sin él.
