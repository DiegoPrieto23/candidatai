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

## Calibración con tus candidaturas (fase 20)

Los evals miden si el score separa lo que **tú** etiquetas como `encaja`; la calibración mira si
predice lo que pasa de verdad con lo que envías: tasa de respuesta y de entrevista por tramo de
score, veredicto del agente, fuente, portal, plantilla, carta, referencia y rapidez al enviar.
Está en la página «Embudo» (sección «¿Acierta el score?») y en `jh stats calibration`
(`get_calibration` para los agentes). Tiene sentido a partir de unas 20-30 candidaturas enviadas.

Para la retrospectiva semanal, pide a tu agente el skill `revisar-busqueda`. **Solo propone:**
nunca cambia `config/policies.yaml`. Si una propuesta te convence, el cambio lo haces tú, con los
evals como red de seguridad:

1. `uv run jh eval matching` y apunta F1 (y precision y recall) con la configuración actual.
2. Cambia **un** valor en `config/policies.yaml` (`triage_threshold`, un peso de
   `scoring.weights`, una palabra de `hard_filters.discard_title_keywords`…).
3. Vuelve a pasar `uv run jh eval matching`. Si F1 baja, o se cae algún caso tuyo de
   `data/evals/` que antes acertaba, deshaz el cambio.
4. Si lo mantienes, los scores se recalculan solos al consultarlos (cambia la huella de
   `scoring`; `triage_threshold` no la cambia). La calibración usa el score que había al enviar,
   así que compárala dentro de unas semanas, con envíos hechos ya con la configuración nueva.

Lee la calibración con cuidado: con pocos casos (`low_data`) no hay conclusión, dos grupos con
intervalos solapados no son distintos y las enviadas que aún esperan (`awaiting`) bajan la tasa
sin ser un «no». Las ofertas que te interesan y las que respondieron también son buenos casos
para `data/evals/`, pero etiquétalas por **tu** criterio de encaje, no por si respondieron.
