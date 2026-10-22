# Matriz de compatibilidad

Generado por `cai eval compat` (fase 24.6): las 5 ofertas de `evals/compat/jobs.txt` con
`process-jobs`, `assess-fit` y `generate-cv`, medidas igual para todos. Un resultado por
agente y modelo en `evals/compat/results/`. No lo edites a mano: se regenera.
Las columnas «· N oferta(s)» son pasadas cortas (`--cases N`): solo las N primeras.
Los tokens no cuentan los leídos de la caché, que cada agente informa a su manera.

|  | Claude Code · modelo por defecto | OpenCode · ollama/gpt-oss:20b | Antigravity CLI · modelo por defecto | Codex · modelo por defecto · 1 oferta |
|---|---|---|---|---|
| Fecha | 2026-10-22 | 2026-10-22 | 2026-10-22 | 2026-10-22 |
| Open-source | no | sí | no | sí |
| Cómo | process-jobs: 2.º plano, assess-fit: 2.º plano, generate-cv: 2.º plano | process-jobs: 2.º plano, assess-fit: 2.º plano, generate-cv: manual | a mano (`--import`) | a mano (`--import`) |
| Extracción (campos iguales) | 53/55 | 0/55 | 54/55 | 11/11 |
| Valoraciones | 5/5 {'possible': 1, 'strong': 4} | 0/5 | 5/5 {'possible': 1, 'strong': 4} | 1/1 {'strong': 1} |
| CVs que pasan `eval cv` | 5/5 de 5 | 0/0 de 5 | 0/1 de 5 | 1/1 de 1 |
| · Evidencias que existen en el perfil | 5 | 0 | 1 | 1 |
| · Sin skills inventadas ni prohibidas | 5 | 0 | 1 | 1 |
| · Sin skills básicas que la oferta no pide | 5 | 0 | 1 | 1 |
| · Una página | 5 | 0 | 1 | 1 |
| · Sin avisos de maquetación del PDF | 5 | 0 | 1 | 1 |
| · Cobertura de keywords | 5 | 0 | 1 | 1 |
| · Idioma de la oferta | 5 | 0 | 1 | 1 |
| · Verificado por el rol `verifier` | 5 | 0 | 0 | 1 |
| Tiempo | 8.5 min | 30.6 min | — | — |
| Turnos | 102 | 4 | — | — |
| Tokens (entrada + salida) | 20426 | 7403 | — | — |
| Completa | sí | no | no | sí |

## Campos de la extracción distintos

- Claude Code · modelo por defecto · `cv07-english`: languages_required
- Claude Code · modelo por defecto · `cv09-etl-migracion`: title_normalized
- Antigravity CLI · modelo por defecto · `cv09-etl-migracion`: title_normalized

## Ejecuciones que no terminaron bien

- Claude Code · modelo por defecto · generate-cv: needs_user
- OpenCode · ollama/gpt-oss:20b · process-jobs: needs_user
- OpenCode · ollama/gpt-oss:20b · assess-fit: needs_user
