# Evals

Tres evaluaciones con datos **inventados** contra el perfil de `demo/`. Resultados y lectura en
`REPORT.md`.

| Eval | Qué mide | Casos | Comando (desde `backend/`) |
|---|---|---|---|
| Matching | Si la app separa las ofertas que encajan de las que no (filtros duros + score frente al umbral de triaje) | `matching/seed.jsonl` (80) | `uv run cai eval matching [--no-embeddings]` |
| CV | Los CVs que deja el agente con `generate-cv` | `cv/cases.jsonl` (10) | `uv run cai eval cv [--agent NOMBRE]` |
| Compatibilidad | Un agente y un modelo recorren `process-jobs`, `assess-fit` y `generate-cv` sobre 5 ofertas, en su propia demo | `compat/jobs.txt` (5 de `cv/`) | `uv run cai eval compat --agent NOMBRE [--model M]` |

## Matching

Detalle del formato y de tus propios casos (`data/evals/*.jsonl`) en `matching/README.md`.

## CV

Cada caso es una oferta inventada (empresa, título, `JobExtraction`) que pasa los filtros del perfil
demo, más lo que se espera del CV:

```json
{"id": "cv04-de-no-basics", "job": {"title": "…", "company": "…", "location": "…"},
 "extraction": {…}, "expect": {"keywords": ["Python", "SQL", "AWS"],
 "forbidden_skills": ["Docker", "Apache Airflow", "dbt"]}, "note": "…"}
```

- `keywords`: deben aparecer en el CV.
- `forbidden_skills`: no deben aparecer, porque la candidata no las tiene o la oferta no las pide.

Flujo, con cualquier agente:

```powershell
cd backend
uv run cai demo seed --eval-cv          # en una demo existente, solo añade los casos que falten
# arranca tu agente con CAI_DATA_DIR=data-demo y lanza generate-cv sobre las 10 ofertas
# de empleo.example.com/eval-cv/ (aprobadas y sin CV)
$env:CAI_DATA_DIR = "data-demo"; uv run cai eval cv --agent claude-code
```

`cai eval cv` no genera nada: mide el último CV guardado de cada caso (o el último del agente de
`--agent`, según `agent_name` de su evento `cv_generated`). Un caso sin CV sale como **pendiente**.
Comprobaciones:

| Comprobación | Pasa si |
|---|---|
| Evidencias | Todas las evidencias de los bullets existen en el perfil |
| Skills | Todas las skills están en el perfil y no aparece ninguna de `forbidden_skills` |
| Skills básicas | No hay skills básicas (`basic_skills` o nivel B) que la oferta no pida |
| Una página | El render seleccionado (o el último) tiene 1 página; sin PDF, «sin medir» |
| Maquetación | Fase 25.5: el render seleccionado (o el último) no tiene avisos de maquetación (`orphan_heading`, `large_gap`, `footer_overlap`, `nearly_empty_last_page`, `text_layer`); un render anterior a la 25.5 no los tiene; sin PDF, «sin medir» |
| Cobertura | Aparecen al menos el 80 % (`--min-coverage`) de las skills pedidas **que la candidata tiene** más las `keywords` del caso |
| Idioma | El CV está en el idioma de la oferta |
| Verificado | El rol `verifier` lo dejó en `passed` |

Informe en JSON y Markdown en `data-demo/evals/reports/cv-*`. Solo funciona en la demo
(`CAI_DATA_DIR` con la marca `.demo`): los casos se escriben para el perfil ficticio.

## Compatibilidad

`cai eval compat` (fase 24.6) es la matriz de `docs/AGENTS_COMPAT.md` automatizada:

1. crea `data-demo-compat-<agente>-<modelo>/` y lanza tu agente en segundo plano;
2. aprueba las 5 ofertas en esa demo;
3. mide la extracción (11 campos frente a la esperada), las valoraciones, `eval cv`, el tiempo y
   los tokens.

Resultados en `compat/results/` (uno por agente, modelo y día) y el resumen, en `compat/REPORT.md`
(generado). Con un agente sin segundo plano da los pasos manuales; después, `--import`.

