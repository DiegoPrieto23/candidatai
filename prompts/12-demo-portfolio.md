# Fase 12 · Modo demo, compatibilidad y portfolio

## Contexto
Lee `docs/ROADMAP.md` (registro de fases) y `docs/DECISIONS.md`.

## Subfases
La fase se hace en tres subfases, cada una con su encargo, en la misma rama
`fase/12-demo-portfolio` y con un commit por subfase. Este fichero es la referencia común; cada
subfase dice qué puntos cubre y las decisiones tomadas al planificarla.

| Subfase | Encargo | Puntos del alcance |
|---|---|---|
| 12.1 | `prompts/12.1-modo-demo.md` | 1 (modo demo y banner) |
| 12.2 | `prompts/12.2-evals.md` | 2 y 3 (eval de matching con informe y `jh eval cv`) |
| 12.3 | `prompts/12.3-compatibilidad-portfolio.md` | 4, 5 y 6, CI y el cierre de la fase |

## Objetivo
Que cualquiera pueda clonar, arrancar y entender el proyecto sin tus datos, y que el repo cuente
bien lo que has construido.

## Alcance
1. `jh demo seed`: crea `data-demo/` con el perfil ficticio, unas 60 ofertas sintéticas con
   extracciones ya hechas, eventos repartidos en 8 semanas (para que el dashboard tenga forma) y
   dos CVs generados. `JH_DATA_DIR=data-demo` arranca la app en modo demo, con un banner visible.
2. Ampliar `evals/matching` a 60-100 casos y publicar el informe
   (`evals/REPORT.md`: métricas, umbral elegido, errores típicos).
3. Eval de CV: 10 casos con perfil demo + oferta y comprobaciones automáticas (evidencias
   válidas, una página, cobertura de keywords, sin skills básicas no pedidas) con
   `jh eval cv`, pensado para ejecutarlo tras el skill `generar-cv` sobre cada caso.
4. **Matriz de compatibilidad probada**: con el modo demo, ejecuta en Claude Code y en Codex
   (y en cualquier otro agente disponible) `procesar-ofertas`, `evaluar-encaje` y `generar-cv`
   sobre las mismas 5 ofertas. Registra en `docs/AGENTS_COMPAT.md` qué funcionó, qué hubo que
   ajustar en el manifiesto y los resultados de `jh eval cv` por agente.
5. README principal de portfolio: problema, arquitectura (diagramas en Mermaid), decisiones
   clave con enlace a los ADR, capturas de la UI demo, métricas del eval, cómo arrancarlo y
   límites éticos (POLICIES §5 y §6), agentes compatibles y cómo añadir uno. Crédito al proyecto
   original.
6. Revisión final de seguridad: grep de datos personales en el historial de git y comprobación de
   que `data/` nunca se ha commiteado.

## Criterios de aceptación
- Clon limpio + `jh demo seed` + `jh serve` + `pnpm dev` muestra la app llena en menos de 5 minutos.
- CI en verde.

## Al terminar
Actualiza `docs/ROADMAP.md`. Propón al usuario un texto corto para LinkedIn o el CV que describa
el proyecto con datos reales (sin exagerar).
