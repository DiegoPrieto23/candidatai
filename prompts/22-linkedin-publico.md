# Fase 22 · LinkedIn por sus endpoints públicos (opcional, desactivada)

Plan 13-22 (`docs/ROADMAP.md`). Rama `fase/22-linkedin-publico`. Inspirada en `linkedin-search` de
AI Job Search, que usa los endpoints públicos `jobs-guest` sin sesión, «solo para uso personal» y
avisando de que el acceso automatizado va contra las condiciones de LinkedIn. Decisión del usuario
(2026-10-11): incluirla como fase opcional, **desactivada por defecto**.

## Contexto
Lee `docs/DECISIONS.md` ADR-009 y ADR-016, `docs/POLICIES.md` §8, la regla dura 6 de `AGENTS.md`,
`services/platforms.py` (`_NO_FETCH`) y el conector de alertas por correo (09b.1). Esta fase
**cambia una regla**: hoy el código nunca descarga páginas de LinkedIn.

## Objetivo
Tener ofertas de LinkedIn sin depender del correo y sin usar tu cuenta, con el menor volumen y
riesgo posibles, y solo si tú lo activas.

## Alcance
1. **ADR nueva** que matiza la ADR-016: el código puede consultar la búsqueda pública
   (`jobs-guest`) de LinkedIn **sin sesión**, solo si el usuario la activa en Plataformas con un
   aviso de riesgo (condiciones de uso, bloqueo de IP); nunca con cookies ni cuenta; nunca para
   candidaturas (la regla 6 sigue igual). Actualiza `AGENTS.md` (regla 6), `POLICIES.md` §8 y
   `FUENTES_OFERTAS.md`.
2. **Conector `linkedin_public`**: búsquedas con palabras clave y ubicación (desde la
   configuración de la plataforma), límites estrictos en `config/policies.yaml` (p. ej. ≤ 2
   páginas por búsqueda, ≥ 10 s entre peticiones, ≤ 1 recorrido al día, user-agent honesto),
   corte inmediato ante 429/999 o captcha y aviso en la UI. Las ofertas entran como **resumen**
   (`pending_detail`), igual que las del correo, con el prefiltro; se completan con la extensión.
   La descripción completa por el endpoint público queda como opción separada, también apagada.
3. **UI**: interruptor propio en la tarjeta de LinkedIn de Plataformas, distinto de «el agente la
   recorre», con el diálogo de riesgo y confirmación (como la 09b.3).
4. **Docs y tests**: `respx` con respuestas guardadas (HTML de ejemplo en fixtures, sin datos
   reales), test de que con el interruptor apagado no sale ninguna petición.

## Fuera de alcance
Iniciar sesión, usar cookies, enviar candidaturas o mensajes en LinkedIn, esquivar captchas.

## Criterios de aceptación
- Apagado por defecto y sin peticiones mientras esté apagado (test).
- Límites de volumen aplicados y corte ante bloqueo (tests).
- ADR, `AGENTS.md`, `POLICIES.md` y `FUENTES_OFERTAS.md` actualizados.
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde.
