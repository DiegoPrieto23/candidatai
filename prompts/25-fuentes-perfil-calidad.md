# Fase 25 · Más fuentes, perfil más rico, ofertas dudosas, coste y calidad del CV

Rama `fase/25-fuentes-perfil-calidad`. Siete subfases, cada una con su encargo y un commit en la
misma rama, en este orden: 25.1 → 25.2 → 25.3 → 25.4 → 25.5 → 25.6 → 25.7. **Una subfase por sesión.**
Va después de la fase 24. Decisión del usuario (2026-10-16): lo que quedaba de «Lo que nos falta»
en `docs/COMPARATIVA.md` tras la fase de agentes, salvo macOS, Linux y Docker, que van en la
fase 26.

## Contexto
Lee `docs/COMPARATIVA.md` («Lo que nos falta»), `docs/DECISIONS.md` (ADR-016, ADR-019, ADR-025,
ADR-028, ADR-032 y el ADR-037 de la fase 24) y `docs/POLICIES.md`.

## Objetivo
Que entren más ofertas buenas sin scraping, que el perfil recoja lo que ya has demostrado en
público y se pueda rellenar entero desde la UI, que las ofertas fantasma o con trampa se vean antes de gastar tiempo en ellas, que sepas
qué cuesta cada oferta y con qué agente, y que el CV salga bien maquetado.

## Subfases
| | Encargo | Resultado visible |
|---|---|---|
| 25.1 | `prompts/25.1-conectores-ats.md` | Ingesta diaria de Personio, Teamtailor, Workable, SmartRecruiters y Recruitee, más Manfred y freehire.me como portales; `cai sources discover` también para esos ATS |
| 25.2 | `prompts/25.2-expand-perfil.md` | Skill `expand`: propone proyectos, skills y logros desde tu GitHub, portfolio o Scholar, con la fuente, y los añade al perfil solo con tu OK |
| 25.3 | `prompts/25.3-ofertas-dudosas.md` | Señales de oferta dudosa en la bandeja, el triaje y la ficha; banderas rojas de la empresa en el dosier |
| 25.4 | `prompts/25.4-coste-lote.md` | Coste por oferta, skill y agente en la página «Agente» y en el embudo; lote en paralelo opcional y umbral de score antes de gastar agente |
| 25.5 | `prompts/25.5-maquetacion-pdf.md` | El CV y la carta se revisan en el PDF: títulos huérfanos, huecos, pie y última página casi vacía, con aviso en la ficha |
| 25.6 | `prompts/25.6-changelog-historia.md` | `CHANGELOG.md`, notas de release desde él y README con los números reales de tu búsqueda |
| 25.7 | `prompts/25.7-perfil-desde-la-ui.md` | «Mi perfil» editable: experiencia y logros, proyectos, formación, skills, historias STAR, preferencias de búsqueda, CV y carta, contexto y muestras de estilo, con validación, diff y «Deshacer»; «Mejorar con mi agente» opcional |

Las subfases son independientes entre sí salvo la 25.4, que usa lo que la fase 24 guarda de cada
ejecución (agente, modelo, uso). Si hace falta, se pueden reordenar. La 25.7 se añadió el
2026-10-17 a petición del usuario (que la app se pueda usar entera desde la UI) y matiza el
ADR-025 con un ADR nuevo (ADR-039). Por su tamaño se parte en dos commits (decisión del usuario,
2026-10-17): la **25.7a** (backend: escritura del perfil, contexto y muestras de estilo, skills y
docs de reglas) y la **25.7b** (la página «Mi perfil» editable, los botones del agente, la guía, el
README y la prueba manual).

## Fuera de alcance
macOS, Linux y Docker (fase 26). Autorización de trabajo y visado (solo importa fuera de la UE).
Scrapers HTML de portales (ADR-016) y que la app llame a un modelo (ADR-001).

## Criterios de aceptación de la fase
- Ninguna fuente nueva usa scraping de HTML: solo APIs o feeds públicos y documentados (test por
  conector con fixtures, sin red).
- Nada entra en `data/profile.yaml` sin tu confirmación, y todo lo que añade `expand` lleva su
  fuente. Desde la UI, solo escribe el usuario (`require_ui`), con validación y sin pisar cambios
  hechos a mano.
- Tests en verde, ruff limpio, `sync_agents.py --check` en verde, `pnpm typecheck && pnpm test` en
  verde, y `docs/ROADMAP.md`, `docs/RESUMEN_FASES.md`, `docs/COMPARATIVA.md` y
  `docs/pruebas/PENDIENTES.md` al día.
