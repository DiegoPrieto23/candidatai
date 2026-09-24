# Arquitectura

## Idea central

La app hace todo lo determinista: guardar, deduplicar, filtrar, puntuar, detectar contenido
sospechoso, renderizar documentos y llevar el seguimiento. **El agente de IA del usuario** hace lo
que necesita criterio o redacción, llamando a la interfaz para agentes de la app (MCP o CLI).
La app nunca llama a un modelo y no depende de ningún proveedor.

```
                  ┌──────────────────────────────────────────────┐
  Tú ──── UI ─────┤  FastAPI  ─┐                                 │
  (React)         │            ├──► services/ ──► SQLite (data/) │
  Tú ─ tu agente ─┤  MCP     ──┤        │                        │
  (Claude Code,   │  CLI jh  ──┘        ├──► docxtpl + LibreOffice│
   Codex, …)      │                     ├──► embeddings locales  │
                  │  worker ────────────┘   (scheduler, ingesta) │
                  └──────────────────────────────────────────────┘
```

## Capas

| Capa | Responsabilidad | Regla |
|---|---|---|
| `app/models` | Tablas SQLAlchemy | Sin lógica |
| `app/schemas` | Modelos Pydantic de entrada/salida, incluidos los que rellena el agente | Única definición de cada esquema |
| `app/services` | Toda la lógica de negocio | Se prueba aquí; no conoce HTTP, MCP ni CLI |
| `app/api` | Endpoints REST para la UI | Solo traduce HTTP ↔ servicios |
| `app/mcp` | Herramientas MCP para agentes | Solo traduce MCP ↔ servicios; valida con Pydantic |
| `app/cli.py` | CLI `jh`, con modo `--json` equivalente a la MCP | Solo traduce CLI ↔ servicios |
| `app/worker` | Scheduler y cola de tareas en BD | Ejecuta servicios; nunca un LLM |
| `frontend/` | UI | Solo habla con la API |
| `.agents/` | Skills, roles y manifiesto, sin nada específico de un proveedor | Fuente única; lo nativo se genera |

## Etapas de una oferta

```
found ─► pending_extraction ─► pending_triage ─► approved ─► cv_ready ─► applied ─► in_process ─► closed
                  │                   │              │           │
              [agente]            [Tú en UI,     [agente:     [Tú confirmas
             rol extractor        con ayuda de   redactor +   en la UI]
                                  evaluar-encaje] verificador]
```

- Las etapas marcadas [agente] se quedan en cola hasta que ejecutas el skill correspondiente en tu
  agente, o hasta que una tarea programada de tu agente lo hace por ti, si tu herramienta lo permite.
- La etapa actual de cada oferta se calcula a partir de sus eventos (`docs/DATA_MODEL.md`).

## Qué hace el agente y qué hace el código

| Tarea | Quién | Por qué |
|---|---|---|
| Descargar ofertas (APIs de ATS, URL, texto pegado) | Código | Determinista y repetible |
| Deduplicar (huella + similitud difusa) | Código | Determinista |
| Detectar texto oculto y frases de inyección | Código | No depende del agente que se use |
| Extraer la oferta a JSON | Agente, rol `extractor` (modelo rápido) | Necesita comprensión de texto |
| Filtros duros (seniority, ubicación, idioma) | Código | Reglas explícitas en `config/policies.yaml` |
| Score de encaje (embeddings + cobertura de skills) | Código | Medible y evaluable |
| Explicar el encaje y sus riesgos | Agente | Criterio |
| Aprobar o descartar | Tú | Decisión tuya |
| Redactar el contenido del CV | Agente, rol `redactor` | Redacción |
| Verificar que no hay nada inventado | Agente, rol `verificador` (distinto del redactor) | Segunda opinión independiente |
| Comprobar evidencias, skills y páginas | Código | Determinista; no se fía del agente |
| Renderizar DOCX/PDF | Código | Determinista |
| Rellenar formularios de candidatura | Código (Playwright) | Determinista, con pausa antes de enviar |
| Enviar | Tú (confirmación en la UI) | Irreversible |

## Fronteras de seguridad (defensa en profundidad)

Las garantías se reparten en capas para que **no dependan de qué agente use cada persona**
(detalle por agente en `docs/AGENTS_COMPAT.md`):

1. **En el código, siempre activas:**
   - Al guardar una oferta se detecta texto oculto en el HTML y frases típicas de inyección
     (`config/injection_patterns.yaml`); se guardan como `risk_flags` y se registra el evento antes
     de que ningún agente la vea.
   - `get_job` entrega el texto envuelto como no confiable y con sus `risk_flags`.
   - Todo lo que devuelve un agente se valida con Pydantic. El CV se rechaza si cita evidencias
     inexistentes, skills fuera del perfil o skills básicas no pedidas.
   - La interfaz para agentes no tiene nada que envíe datos al exterior. Enviar solo ocurre desde
     la UI, con tu clic.
2. **En el agente, cuando lo permite:** el texto crudo solo lo ve el rol `extractor`, configurado
   con las herramientas mínimas (en Claude Code, solo las dos herramientas MCP que necesita; en
   Codex, sandbox de solo lectura). El resto de roles trabaja con datos ya estructurados.
3. **Auditoría:** cada llamada a la interfaz queda en la tabla `mcp_calls`.
4. **Datos personales** en `data/`, fuera del repositorio.

## Ejecución en local (Windows 11)

- Todo nativo con `uv` y `pnpm`, sin Docker: Playwright necesita un navegador visible para que
  inicies sesión y revises formularios, y LibreOffice se usa instalado en el sistema.
- `jh serve` levanta la API, `jh worker` el scheduler y `pnpm dev` la UI.
- Cada agente arranca el servidor MCP solo, según su configuración generada (`.mcp.json` para
  Claude Code, `.codex/config.toml` para Codex…).

## Despliegue futuro (fuera del alcance actual)

SQLite → Postgres cambiando la URL de conexión (las migraciones ya existen), API + worker en
contenedores, y el aplicador Playwright y la interfaz para agentes como componentes locales.
