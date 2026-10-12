# Informe de evaluación

Resultados de los evals de CandidatAI con datos **inventados** (perfil de `demo/`). Se reproducen
con los comandos de cada sección; cómo funcionan, en `evals/README.md`.

## Matching (fase 12.2)

**Pregunta:** ¿la app separa bien las ofertas que la candidata querría revisar de las que no?
Predice «encaja» si la oferta pasa los filtros duros y su score llega a `triage_threshold`.

- **Casos:** 80 en `evals/matching/seed.jsonl`, 40 `encaja` y 40 `no_encaja`. Las etiquetas se
  pusieron a mano según lo que querría la candidata demo (Data Engineer junior o mid; Galicia, o
  Madrid sin presencialidad; Python, SQL, Snowflake y Power BI; hasta 4 años pedidos; español e
  inglés B2). Los 20 casos de la fase 07 ya se conocían; los 60 nuevos (fase 12.2) se etiquetaron
  antes de ejecutar el eval. Dos etiquetas recogen a propósito una preferencia que el perfil no
  declara (ciudades cercanas), para medir ese hueco. Hay casos trampa: títulos que engañan, el mismo stack en
  otro oficio, ciudades cercanas no listadas, niveles, años e idiomas.
- **Configuración:** `config/policies.yaml` por defecto, **sin embeddings** (el extra `matching`
  no está instalado en la máquina de desarrollo). Sin similitud semántica, el score se reparte
  entre la cobertura de skills y las preferencias.
- **Fecha:** 2026-10-05.

```powershell
cd backend
uv run cai eval matching --no-embeddings
```

### Resultado con el umbral actual (55)

| Precision | Recall | F1 | VP | FP | FN | VN |
|---|---|---|---|---|---|---|
| 0.88 | 0.95 | 0.92 | 38 | 5 | 2 | 35 |

De los 40 `no_encaja`, 18 los cortan los filtros duros y 22 llegan al score (mediana 29). De los
40 `encaja`, los 38 que pasan los filtros sacan entre 63 y 100 (mediana 83,5); los otros 2 los
corta el filtro de ubicación.

### Curva por umbral

| Umbral | Precision | Recall | F1 |
|---|---|---|---|
| 30 | 0.79 | 0.95 | 0.86 |
| 40 | 0.83 | 0.95 | 0.88 |
| 45 | 0.84 | 0.95 | 0.89 |
| 50 | 0.86 | 0.95 | 0.90 |
| **55** | **0.88** | **0.95** | **0.92** |
| 60 | 0.88 | 0.95 | 0.92 |
| 65 | 0.92 | 0.88 | 0.90 |
| 70 | 0.92 | 0.82 | 0.87 |
| 80 | 0.92 | 0.55 | 0.69 |

### Umbral elegido: 55 (sin cambios)

55 y 60 empatan en F1. Se mantiene 55 porque el umbral no descarta nada: solo atenúa la oferta
en el triaje. Perder una oferta buena cuesta más que revisar una mala, así que se prima el recall.
Por encima de 60 el recall cae rápido: a 65 se pierden tres ofertas buenas (Data Engineer con
Azure, con Spark y Power BI Developer), que son justo los saltos razonables de stack.

### Errores típicos

| Tipo | Casos | Por qué falla | Qué hacer |
|---|---|---|---|
| **Mismo stack, otro oficio** (FP) | `sales-engineer-data` (93), `preventa-datos` (62), `profesor-sql` (62) | El score mira skills y título de rol; la preventa, la docencia o la venta con Snowflake y SQL puntúan alto | Añadir sus palabras a `hard_filters.discard_title_keywords` (`sales`, `preventa`, `formador`…), que es por usuario: la configuración por defecto lo deja vacío a propósito |
| **Rol vecino no buscado** (FP) | `ml-engineer-tabular` (74) | Tiene las skills (scikit-learn, series temporales) a nivel conocido; el rol no está en `preferences.roles`, pero el rol solo pesa un tercio del 15 % de preferencias | Si molesta, `discard_title_keywords: ["machine learning"]`; con embeddings, el texto del puesto bajaría algo el score |
| **Tolerancia de años** (FP) | `de-5-years` (99) | `years_tolerance: 1` deja pasar 5 años con un máximo de 4. Es intencionado: muchas ofertas piden más de lo que necesitan | Ajustar `years_tolerance` a 0 si se prefiere ser estricto |
| **Ciudad cercana no listada** (FN) | `de-ourense-hybrid`, `de-pontevedra-hybrid` | Preferencia que el perfil no declara: el filtro de ubicación solo conoce las ciudades de `preferences.locations` y no sabe de distancias | Añadir esas ciudades a `preferences.locations.preferred` o `allowed`. Una noción de cercanía (provincia, radio) queda como mejora |

Ningún caso de otro oficio con otro stack (frontend, DevOps, DBA, SAP, Qlik, Java) se cuela: la
cobertura de skills los deja por debajo de 55 o los cortan los filtros.

### Pendiente

- Repetir con embeddings (`uv sync --extra matching` en `backend/`) y comparar el informe: el
  30 % del peso semántico debería bajar los falsos positivos de oficio (preventa, docencia) y
  servir para elegir el modelo (ADR-006).
- Casos reales: los tuyos van en `data/evals/*.jsonl` (no se versionan) y se evalúan contra tu
  perfil.

## CV (fase 12.2)

**Pregunta:** ¿los CVs que deja el agente con `generate-cv` son veraces, caben en una página y
cubren lo que la oferta pide y la candidata tiene? `cai eval cv` mide lo guardado en la demo sobre
los 10 casos de `cv/cases.jsonl` (comprobaciones en `evals/README.md`).

```powershell
cd backend
uv run cai demo seed --eval-cv
# generate-cv con tu agente sobre las 10 ofertas de los casos (CAI_DATA_DIR=data-demo)
$env:CAI_DATA_DIR = "data-demo"; uv run cai eval cv --agent claude-code
```

### Primera prueba: Claude Code sin MCP, 2 casos (2026-10-05)

Para probar el circuito se redactaron y verificaron dos casos con trampa. Fueron dos ejecuciones
distintas de Claude Code (Opus 5.5), siguiendo `.agents/roles/writer.md` y `verifier.md`,
solo con comandos `cai … --json` contra `data-demo`.

| Caso | Trampa | Resultado | Intentos del redactor |
|---|---|---|---|
| `cv04-de-no-basics` | No pide dbt, Airflow ni Docker (básicas): no deben salir | Pasa las 7 comprobaciones | 1 |
| `cv07-english` | Oferta en inglés | Pasa las 7 comprobaciones | 2: la app rechazó «Dimensional modeling», que en el perfil se llama «Modelado dimensional» |

Lo que vio el verificador (avisos, ningún bloqueante) y que el eval no puede detectar solo:

- un bullet añade «en Python» a un logro cuyo texto no lo dice (sí sus skills etiquetadas);
- en el CV en inglés, la sección extra «Volunteering» sale en español, porque el perfil solo la
  tiene en español.

Problemas de compatibilidad sin MCP: pasan a la matriz de `docs/AGENTS_COMPAT.md` (fase 12.3).

- los roles nombran herramientas MCP y no su comando `cai`;
- las skills no se pueden traducir en un CV en inglés;
- `CAI_DATA_DIR` relativo se resuelve desde la raíz del repo;
- la ayuda de Typer sale mal codificada en Git Bash sin `PYTHONIOENCODING=utf-8`.

Los 10 casos con cada agente se ejecutan en la fase 12.3.
