# Fase 11 · Candidatura asistida (envío tras confirmación)

## Contexto
Lee `docs/POLICIES.md` §5 entero (es la especificación de esta fase) y `docs/DECISIONS.md` ADR-009.

## Subfases
La fase se hace en dos subfases, cada una con su encargo, en la misma rama
`fase/11-candidatura-asistida` y con un commit por subfase. Este fichero es la referencia común;
cada subfase dice qué puntos cubre y las decisiones tomadas al planificarla.

| Subfase | Encargo | Puntos del alcance |
|---|---|---|
| 11.1 | `prompts/11.1-motor-rellenado.md` | 1, 2, 5 y 6, y el envío protegido por el token (servicio y worker) |
| 11.2 | `prompts/11.2-revision-envio-ui.md` | 3 y 4 (API y UI), la prueba manual y el cierre de la fase |

## Objetivo
Rellenar formularios de ATS sin intervención y enviar solo cuando confirmes en la UI.

## Alcance
1. Playwright para Python con **contexto persistente** en `data/browser-profile/` y navegador
   visible. La primera vez abres el navegador desde la UI ("Preparar navegador") e inicias tú las
   sesiones que quieras.
2. `app/services/applier/`:
   - detector de plataforma a partir de la URL (Greenhouse, Lever, Ashby, formulario genérico,
     LinkedIn y desconocida);
   - rellenadores por plataforma que mapean campos estándar (nombre, email, teléfono, LinkedIn,
     CV, carta, respuestas del paquete) usando etiquetas accesibles, no posiciones. La carta es la
     seleccionada en la fase 08c: su PDF si el campo pide un fichero y su texto plano si es un
     cuadro de texto; si el formulario la pide como obligatoria y no hay, cuenta como obligatorio
     vacío;
   - **nunca pulsan el botón de envío**: al terminar, capturan la pantalla completa, listan los
     campos rellenados, los vacíos y los obligatorios sin respuesta, y se detienen;
   - si detectan captcha, anti-bot o login inesperado, paran y marcan `needs_user`.
3. Flujo en la UI:
   - "Preparar candidatura" → el rellenado se ejecuta en el worker → pantalla de revisión con
     captura, tabla de campos y avisos;
   - "Enviar" solo se activa si no quedan obligatorios vacíos y pide una segunda confirmación
     con el nombre de la empresa;
   - al confirmar, se pulsa el envío, se captura la pantalla de confirmación y se registra
     `applied` con la captura como evidencia;
   - "Lo termino yo" abre la pestaña preparada y registra `applied_manually` cuando lo marques.
4. LinkedIn y plataformas desconocidas: solo "abrir y preparar" (se abre la URL y se muestra el
   paquete para copiar). Sin automatización.
5. Sin reintentos automáticos. Timeout por paso y registro detallado en `data/logs/applier/`.
6. No existe ninguna herramienta MCP ni comando `--json` de la interfaz para agentes en esta fase
   (a propósito): el envío solo se desencadena desde la UI.

## Fuera de alcance
Crear cuentas, resolver captchas, enviar mensajes a recruiters.

## Criterios de aceptación
- Tests de los rellenadores contra formularios HTML locales de prueba (servidos en el propio
  test), incluido uno con captcha simulado que debe detenerse.
- Test de que ninguna ruta de código pulsa el envío sin el token de confirmación de la UI.
- Prueba manual con una oferta real de Greenhouse o Lever hasta la pantalla de revisión, sin enviar.

## Al terminar
Actualiza `docs/ROADMAP.md` y propón mensaje de commit.
