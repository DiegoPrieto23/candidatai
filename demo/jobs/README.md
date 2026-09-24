# Ofertas de ejemplo

Ofertas **ficticias** (empresas y datos inventados) para probar la app y los skills sin datos reales.

| Fichero | Título | Empresa | Para qué sirve |
|---|---|---|---|
| `01-data-engineer.txt` | Data Engineer | Brétema Analytics | Flujo normal de extracción |
| `02-analytics-engineer.txt` | Analytics Engineer | Lonxa Retail Tech | Lleva una instrucción dirigida a una IA: debe acabar con `risk_flags` e `injection_suspected` |

Alta por CLI (el fichero debe estar en `data/tmp/`, que se vacía tras procesarlo bien):

```powershell
New-Item -ItemType Directory -Force data/tmp | Out-Null
Copy-Item demo/jobs/01-data-engineer.txt data/tmp/
uv run --directory backend jh jobs add-text --title "Data Engineer" --company "Brétema Analytics" --location "Santiago de Compostela" --file data/tmp/01-data-engineer.txt
```
