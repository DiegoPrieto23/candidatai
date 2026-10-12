# Matriz de compatibilidad · Claude Code sin MCP (fase 12.3)

Pasada del 2026-10-05 sobre `data-demo` (`cai demo seed --compat`), Claude Code con Opus 5.5,
una ejecución por rol siguiendo `.agents/roles/*.md`, solo con comandos `cai … --json`.
Ofertas 61-65 = casos `cv01`, `cv03`, `cv05`, `cv07` y `cv09` de `evals/cv/cases.jsonl`.

## Extracción frente a la esperada

11 campos por oferta (título normalizado, nivel, años, modalidad, ubicaciones, idiomas, salario,
obligatorias, deseables, dominio e idioma de la oferta): **54 de 55 iguales**. Única diferencia:
`cv09-etl-migracion`, `title_normalized` «Desarrollador/a ETL» en vez de «ETL Developer».
`employment_type` no se compara: el texto generado no lo dice y el agente puso `unknown`, que es
lo correcto.

## Valoración

5/5 guardadas: 4 `strong` (scores 96, 68, 97 y 78) y 1 `possible` (73).

## `cai eval cv --agent claude-code`

(Salen como «sin alta» los casos del eval de CV que no forman parte de la matriz.)

### Informe

- Fecha: 2026-10-05 18:39 UTC
- Agente: claude-code
- Cobertura mínima: 80%
- Evaluados: 5 · pasan: 5 · pendientes: 5

| Caso | Estado | Agente | Evidencias que existen en el perfil | Sin skills inventadas ni prohibidas | Sin skills básicas que la oferta no pide | Una página | Cobertura de keywords | Idioma de la oferta | Verificado por el rol verificador |
|---|---|---|---|---|---|---|---|---|---|
| `cv01-de-snowflake` | pasa | claude-code | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `cv02-ae-dbt` | sin alta |  |  |  |  |  |  |  |  |
| `cv03-analyst-powerbi` | pasa | claude-code | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `cv04-de-no-basics` | sin alta |  |  |  |  |  |  |  |  |
| `cv05-de-orquestacion` | pasa | claude-code | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `cv06-genai` | sin alta |  |  |  |  |  |  |  |  |
| `cv07-english` | pasa | claude-code | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `cv08-bi-developer` | sin alta |  |  |  |  |  |  |  |  |
| `cv09-etl-migracion` | pasa | claude-code | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `cv10-ds-series` | sin alta |  |  |  |  |  |  |  |  |

Pendientes: lanza `generar-cv` sobre esos casos (`sin alta`: antes, `cai demo seed --eval-cv`).

## Verificador (ejecución independiente)

5/5 `passed`, 0 bloqueantes, 4 avisos de redacción: un plural no respaldado («modelos
dimensionales»), DAX (nivel C) en el subtítulo, «cuadros de mando» sin respaldo literal en el
perfil y «heredados» copiado de la oferta. Son los matices que el eval automático no puede ver y
que justifican el rol verificador.
