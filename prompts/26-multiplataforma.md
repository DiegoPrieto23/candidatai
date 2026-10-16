# Fase 26 · macOS, Linux y Docker

Rama `fase/26-multiplataforma`. Cuatro subfases, cada una con su encargo y un commit en la misma
rama, en este orden: 26.1 → 26.2 → 26.3 → 26.4. **Una subfase por sesión.** Va después de la 25.
Decisión del usuario (2026-10-16): separarla de la 25 porque toca otra cosa (el instalador, los
botones que abren el agente y la CI) y porque gana sentido tras la fase 24, cuando los agentes
open-source que funcionan en los tres sistemas (OpenCode, Codex, Qwen Code) ya están soportados.

## Contexto
Lee `docs/DECISIONS.md` ADR-007 («Ejecución nativa en Windows, sin Docker de momento»), ADR-024,
ADR-032 y ADR-035, `install.ps1`, `.github/workflows/ci.yml` y `release.yml`,
`backend/app/services/launcher.py`, `agent_launch.py`, `agent_runner.py`,
`documents/pdf.py` (rutas de LibreOffice) y `core/config.py`.

## Objetivo
Que CandidatAI se instale y funcione igual en macOS y en Linux que en Windows, incluidos los botones
que abren el agente y el segundo plano, y que quien prefiera no instalar nada en su sistema pueda
levantarlo con Docker, sabiendo lo que pierde.

## Decisiones tomadas con el usuario
- **Windows 11 sigue siendo el entorno principal**: nada de lo que funciona hoy en Windows puede
  empeorar.
- **Docker es opcional y con límites claros**, no la forma recomendada: el agente vive fuera del
  contenedor, así que los botones de terminal, el segundo plano y la ventana visible de la
  candidatura asistida no funcionan igual dentro. Un ADR nuevo matiza el ADR-007.
- **Sin dependencias de sistema nuevas obligatorias**: LibreOffice sigue siendo opcional (el motor
  HTML con Chromium de Playwright basta para los PDF).
- El usuario solo tiene Windows: **Linux se prueba a mano en WSL2 o en una máquina virtual**, y
  **macOS se prueba en la CI** (y a mano si alguien con Mac puede). La guía lo dice.

## Subfases
| | Encargo | Resultado visible |
|---|---|---|
| 26.1 | `prompts/26.1-nucleo-multiplataforma.md` | El backend no supone Windows: rutas, procesos, LibreOffice y los botones «en tu agente» abren una terminal en macOS y en Linux |
| 26.2 | `prompts/26.2-instalador-unix.md` | `install.sh` para macOS y Linux, con acceso directo, datos en la carpeta de cada sistema y desinstalación |
| 26.3 | `prompts/26.3-docker.md` | `docker compose up` deja la app en `http://127.0.0.1:8000` con los datos en un volumen, y la guía explica qué no funciona dentro |
| 26.4 | `prompts/26.4-ci-docs.md` | CI con el backend en Windows, Linux y macOS, humo del instalador y de Docker, y guía y README en los dos idiomas |

## Fuera de alcance
Paquetes nativos (`.dmg`, `.deb`, Homebrew, Flatpak), firmar binarios y un servidor accesible desde
otros equipos: todo sigue escuchando solo en `127.0.0.1`.

## Criterios de aceptación de la fase
- En Linux (WSL2 o una máquina virtual) y en macOS (CI), `install.sh` deja la app instalada y `cai
  start` la arranca; la demo se siembra y genera CVs.
- Los botones «en tu agente» abren una terminal con la orden en Linux y en macOS, o copian la orden
  con un mensaje claro si no encuentran ninguna terminal.
- Windows funciona igual que antes (los tests de Windows no cambian de comportamiento).
- Tests en verde en los tres sistemas, ruff limpio, `sync_agents.py --check` en verde, frontend en
  verde, y `docs/ROADMAP.md`, `docs/RESUMEN_FASES.md`, `docs/COMPARATIVA.md` y
  `docs/pruebas/PENDIENTES.md` al día.
