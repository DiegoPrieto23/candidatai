# Set de evaluación del matching

`seed.jsonl` son 80 casos **inventados** (40 `encaja` y 40 `no_encaja`) que se evalúan contra el
perfil de `demo/`. Sirven para comprobar que el score y los filtros hacen lo esperado y para
ajustar `config/policies.yaml` (`scoring.weights`, `triage_threshold`, `semantic`…) sin datos
personales. Siete fallan con la configuración por defecto, y están explicados en
`evals/REPORT.md` (p. ej. `sales-engineer-data`, que solo se descarta si añades `sales` a
`hard_filters.discard_title_keywords`).

Tus casos reales van en `data/evals/*.jsonl` (no se versionan) y se evalúan contra
`data/profile.yaml`. Mismo formato, un caso por línea (las líneas que empiezan por `#` se ignoran):

```json
{"id": "acme-data-eng", "job_fixture": {"title": "Data Engineer (m/f/d)", "extraction": {…}}, "label": "encaja", "note": "opcional"}
```

- `title`: el título tal cual (ahí se buscan las palabras de descarte).
- `extraction`: un `JobExtraction` completo (`docs/AGENT_INTERFACE.md`). El de una oferta ya
  extraída sale de `jh jobs extraction ID --json` (campo `extraction`).
- `label`: `encaja` o `no_encaja`, según **tu** criterio.

La app predice `encaja` si la oferta pasa los filtros duros y su score llega a `triage_threshold`.

```powershell
cd backend
uv run jh eval matching                   # semilla + data/evals; embeddings si están instalados
uv run jh eval matching --no-embeddings   # solo cobertura de skills y preferencias
uv run jh eval matching --no-seed         # solo tus casos
```

Imprime precision, recall y F1 con el umbral actual y la curva por umbral, y guarda el informe en
`data/evals/reports/` (JSON y Markdown). Para elegir el modelo de embeddings (ADR-006), cambia
`scoring.semantic.model` y compara los informes.
